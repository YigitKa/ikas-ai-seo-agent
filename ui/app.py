import asyncio
import io
import json
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from config.settings import get_config
from core.models import Product, SeoScore, SeoSuggestion
from core.product_manager import ProductManager
from core.seo_analyzer import analyze_product
from data import db
import tkinter as tk

from ui.components.ai_chat_panel import AIChatPanel
from ui.components.diff_viewer import DiffViewer
from ui.components.dockable_panel import DockablePanel
from ui.components.product_table import ProductTable
from ui.components.settings_panel import SettingsPanel
from ui.themes.dark import COLORS

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ConsoleLogHandler(logging.Handler):
    """Logging handler that writes to a CTkTextbox console widget."""

    def __init__(self, console_widget: ctk.CTkTextbox) -> None:
        super().__init__()
        self._console = console_widget

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._console.after(0, lambda: self._append(msg))
        except Exception:
            self.handleError(record)

    def _append(self, msg: str) -> None:
        self._console.configure(state="normal")
        self._console.insert("end", msg + "\n")
        self._console.see("end")
        self._console.configure(state="disabled")


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ikas SEO Optimizer")
        self.geometry("1400x800")
        self.configure(fg_color=COLORS["bg_primary"])
        self._sash_set = False
        self.after(50, lambda: self.state("zoomed"))
        self.bind("<Configure>", self._on_configure)

        self._manager = ProductManager()
        self._selected_product: Optional[Product] = None
        self._selected_score: Optional[SeoScore] = None
        self._products_data: list[tuple[Product, SeoScore | None]] = []
        self._filter_var = ctk.StringVar(value="all")
        self._total_count: int = 0
        self._current_page: int = 1
        self._page_size: int = 50
        self._main_image_ref: Optional[ctk.CTkImage] = None
        self._gallery_image_refs: list[ctk.CTkImage] = []
        self._image_cache: dict[str, ctk.CTkImage] = {}
        self._image_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gallery")
        self._search_timer: str | None = None
        self._gallery_thumbnails: list[ctk.CTkLabel] = []

        self._build_toolbar()
        self._build_status_bar()
        self._build_main_layout()
        self._setup_console_logging()
        self._update_ai_button_state()

        self._schedule_llm_check()

        config = get_config()
        if not config.ikas_store_name or not config.ikas_client_id:
            self.after(300, self._open_settings)

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=50)
        toolbar.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(toolbar, text="Urunleri Cek", command=self._fetch_products,
                       fg_color=COLORS["accent"]).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Secilileri Analiz Et", command=self._analyze_selected,
                       fg_color=COLORS["bg_card"]).pack(side="left", padx=5, pady=5)
        self._rewrite_btn = ctk.CTkButton(toolbar, text="AI ile Yeniden Yaz", command=self._rewrite_selected,
                                           fg_color=COLORS["bg_card"])
        self._rewrite_btn.pack(side="left", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Onayla ve Uygula", command=self._apply_approved,
                       fg_color=COLORS["success"]).pack(side="left", padx=5, pady=5)

        ctk.CTkSegmentedButton(
            toolbar, values=["Tumu", "Dusuk Skor", "Bekleyen", "Onayli"],
            variable=self._filter_var, command=self._on_filter_change,
        ).pack(side="right", padx=10, pady=5)

        ctk.CTkButton(toolbar, text="Ayarlar", width=80, command=self._open_settings,
                       fg_color=COLORS["border"]).pack(side="right", padx=5, pady=5)

    def _build_main_layout(self) -> None:
        """3-sütun layout: [Ürün Listesi] | [Detay+SEO] | [AI Chat] + alt konsol."""
        # Dikey PanedWindow: [ana alan] / [konsol]
        self._vpaned = tk.PanedWindow(
            self, orient=tk.VERTICAL,
            sashwidth=6, sashrelief="flat",
            bg=COLORS["border"], opaqueresize=False,
            borderwidth=0, sashcursor="sb_v_double_arrow",
        )
        self._vpaned.pack(fill="both", expand=True, padx=5, pady=(5, 0))

        # Yatay PanedWindow: [sol] | [orta] | [sağ=AI Chat]
        self._hpaned = tk.PanedWindow(
            self._vpaned, orient=tk.HORIZONTAL,
            sashwidth=6, sashrelief="flat",
            bg=COLORS["border"], opaqueresize=False,
            borderwidth=0, sashcursor="sb_h_double_arrow",
        )

        # ── Sol Panel: Ürün Listesi ──
        self._left_panel = DockablePanel(self._hpaned, title="Ürün Listesi")
        left = self._left_panel.content

        search_frame = ctk.CTkFrame(left, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=10)
        self._search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Urun ara...",
            fg_color=COLORS["input_bg"],
        )
        self._search_entry.pack(fill="x")
        self._search_entry.bind("<KeyRelease>", self._on_search)

        self._product_table = ProductTable(
            left, on_select=self._on_product_select,
            on_page_change=self._on_page_change,
            fg_color=COLORS["bg_secondary"],
        )
        self._product_table.pack(fill="both", expand=True, padx=5, pady=5)

        # ── Orta Panel: Ürün Detay & SEO Diff ──
        self._right_panel = DockablePanel(self._hpaned, title="Ürün Detay & SEO")
        self._diff_viewer = DiffViewer(
            self._right_panel.content,
            on_approve=self._on_approve,
            on_reject=self._on_reject,
            on_field_rewrite=self._rewrite_field,
        )
        self._diff_viewer.pack(fill="both", expand=True)

        # ── Sağ Panel: AI Chat (kalıcı, her zaman görünür) ──
        self._chat_panel = DockablePanel(self._hpaned, title="AI Chat")
        self._ai_chat = AIChatPanel(self._chat_panel.content)
        self._ai_chat.pack(fill="both", expand=True)

        # Panelleri yatay PanedWindow'a ekle
        self._hpaned.add(self._left_panel, minsize=180, stretch="always")
        self._hpaned.add(self._right_panel, minsize=380, stretch="always")
        self._hpaned.add(self._chat_panel, minsize=260, stretch="always")

        self._vpaned.add(self._hpaned, minsize=200, stretch="always")

        # ── Alt Panel: Sadece Konsol ──
        self._console_panel = DockablePanel(self._vpaned, title="Konsol")
        console_content = self._console_panel.content

        ctk.CTkButton(
            self._console_panel.header, text="Temizle", width=55, height=20,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["border"], hover_color=COLORS["bg_card"],
            command=self._clear_console,
        ).pack(side="right", padx=5)

        self._console = ctk.CTkTextbox(
            console_content, height=80,
            fg_color=COLORS["bg_primary"],
            text_color="#80cbc4",
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=5,
            state="disabled",
        )
        self._console.pack(fill="both", expand=True, padx=2, pady=2)

        self._vpaned.add(self._console_panel, minsize=40, stretch="never")

        # Initial sash positions will be set via _on_configure when window is zoomed

    def _on_configure(self, event=None) -> None:
        """Set sash positions once after the window is fully zoomed."""
        if self._sash_set:
            return
        # Wait until window is actually in zoomed state
        try:
            if self.state() != "zoomed":
                return
        except Exception:
            return
        try:
            total_h = self._vpaned.winfo_height()
            total_w = self._hpaned.winfo_width()
            if total_h > 100 and total_w > 100:
                self._sash_set = True
                self.unbind("<Configure>")
                # Sol panel %22, orta panel %48, sağ AI chat %30
                self._hpaned.sash_place(0, int(total_w * 0.22), 0)
                self._hpaned.sash_place(1, int(total_w * 0.70), 0)
                self._vpaned.sash_place(0, int(total_h * 0.87), 0)
        except Exception:
            pass

    def _setup_console_logging(self) -> None:
        handler = ConsoleLogHandler(self._console)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        self._log("Uygulama baslatildi. Hazir.")

    def _log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._console.configure(state="normal")
        self._console.insert("end", f"{ts}  {message}\n")
        self._console.see("end")
        self._console.configure(state="disabled")

    def _clear_console(self) -> None:
        self._console.configure(state="normal")
        self._console.delete("1.0", "end")
        self._console.configure(state="disabled")

    def _build_status_bar(self) -> None:
        self._status_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=36)
        self._status_bar.pack(side="bottom", fill="x", padx=5, pady=(0, 5))
        self._status_bar.pack_propagate(False)

        self._status_label = ctk.CTkLabel(
            self._status_bar, text="Hazir",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12),
        )
        self._status_label.pack(side="left", padx=10)

        self._stats_label = ctk.CTkLabel(
            self._status_bar, text="",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12),
        )
        self._stats_label.pack(side="right", padx=(6, 10))

        self._add_separator()

        self._token_label = ctk.CTkLabel(
            self._status_bar, text="Tokens: -",
            text_color="#80cbc4", font=ctk.CTkFont(family="Consolas", size=12),
        )
        self._token_label.pack(side="right", padx=6)

        self._add_separator()

        self._llm_status_label = ctk.CTkLabel(
            self._status_bar, text="\u25CF Baglanti yok",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12),
        )
        self._llm_status_label.pack(side="right", padx=6)

        self._add_separator()

        self._thinking_label = ctk.CTkLabel(
            self._status_bar, text="Think: OFF",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12),
        )
        self._thinking_label.pack(side="right", padx=6)

        self._add_separator()

        self._maxtok_label = ctk.CTkLabel(
            self._status_bar, text="MaxTok: -",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12),
        )
        self._maxtok_label.pack(side="right", padx=6)

        self._add_separator()

        self._model_label = ctk.CTkLabel(
            self._status_bar, text="Model: -",
            text_color="#5c9aff", font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._model_label.pack(side="right", padx=6)

        self._add_separator()

        self._store_label = ctk.CTkLabel(
            self._status_bar, text="Magaza: -",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12),
        )
        self._store_label.pack(side="right", padx=6)

        self._refresh_status_bar_info()

    def _add_separator(self) -> None:
        sep = ctk.CTkFrame(self._status_bar, fg_color=COLORS["border"], width=1)
        sep.pack(side="right", fill="y", padx=2, pady=4)

    def _refresh_status_bar_info(self) -> None:
        config = get_config()

        store = config.ikas_store_name or "-"
        self._store_label.configure(text=f"Magaza: {store}")

        model_name = config.ai_model_name or "-"
        if "/" in model_name:
            model_name = model_name.split("/")[-1]
        if len(model_name) > 25:
            model_name = model_name[:22] + "..."
        provider = config.ai_provider or "none"
        self._model_label.configure(text=f"{model_name} ({provider})")

        self._maxtok_label.configure(text=f"MaxTok: {config.ai_max_tokens}")

        if config.ai_thinking_mode:
            self._thinking_label.configure(text="Think: ON", text_color="#69f0ae")
        else:
            self._thinking_label.configure(text="Think: OFF", text_color=COLORS["text_secondary"])

        self._check_llm_status()

    def _check_llm_status(self) -> None:
        config = get_config()
        provider = config.ai_provider.lower()

        if provider == "none":
            self._llm_status_label.configure(
                text="\u25CF Provider yok",
                text_color=COLORS["text_secondary"],
            )
            return

        self._llm_status_label.configure(
            text="\u25CF Kontrol ediliyor...",
            text_color=COLORS["warning"],
        )

        def ping():
            try:
                import httpx
                if config.ai_base_url:
                    base = config.ai_base_url.rstrip("/")
                else:
                    from core.ai_client import PROVIDER_BASE_URLS
                    base = PROVIDER_BASE_URLS.get(provider, "")

                if not base:
                    self.after(0, lambda: self._llm_status_label.configure(
                        text="\u25CF URL yok",
                        text_color=COLORS["error"],
                    ))
                    return

                if provider in ("ollama", "lm-studio", "custom", "openai"):
                    if not base.rstrip("/").endswith("/v1"):
                        base = base.rstrip("/") + "/v1"
                    url = f"{base}/models"
                else:
                    url = base

                resp = httpx.get(url, timeout=5)
                if resp.status_code == 200:
                    model_info = ""
                    try:
                        data = resp.json()
                        if "data" in data and data["data"]:
                            loaded = data["data"][0].get("id", "")
                            if loaded:
                                model_info = f" [{loaded}]"
                    except Exception:
                        pass
                    self.after(0, lambda: self._llm_status_label.configure(
                        text=f"\u25CF Bagli{model_info}",
                        text_color=COLORS["success"],
                    ))
                else:
                    self.after(0, lambda: self._llm_status_label.configure(
                        text=f"\u25CF HTTP {resp.status_code}",
                        text_color=COLORS["error"],
                    ))
            except Exception:
                self.after(0, lambda: self._llm_status_label.configure(
                    text="\u25CF Cevrimdisi",
                    text_color=COLORS["error"],
                ))

        threading.Thread(target=ping, daemon=True).start()

    def _update_token_display(self) -> None:
        try:
            usage = self._manager.get_token_usage()
            inp = usage.get("input", 0)
            out = usage.get("output", 0)
            total = inp + out
            def fmt(n):
                if n >= 100_000:
                    return f"{n / 1000:.0f}K"
                if n >= 1000:
                    return f"{n / 1000:.1f}K"
                return str(n)
            if total > 0:
                self._token_label.configure(
                    text=f"Tokens: {fmt(inp)} in / {fmt(out)} out",
                    text_color="#69f0ae",
                )
            else:
                self._token_label.configure(
                    text="Tokens: -",
                    text_color="#80cbc4",
                )
        except Exception as e:
            logger.error(f"Token display update failed: {e}")

    def _schedule_llm_check(self) -> None:
        self._check_llm_status()
        self._update_token_display()
        self.after(30_000, self._schedule_llm_check)

    def _set_status(self, text: str) -> None:
        self._status_label.configure(text=text)
        self._log(text)

    def _update_stats(self) -> None:
        listed = len(self._products_data)
        analyzed = sum(1 for _, s in self._products_data if s)
        pending = len(db.get_pending_suggestions())
        if self._total_count > 0 and self._total_count != listed:
            total_str = f"Toplam: {listed}/{self._total_count}"
        else:
            total_str = f"Toplam: {listed}"
        self._stats_label.configure(
            text=f"{total_str} | Analiz: {analyzed} | Bekleyen: {pending}"
        )

    def _fetch_products(self, page: int = 1) -> None:
        self._set_status(f"Urunler cekiliyor (sayfa {page})...")
        self._current_page = page

        def background_work():
            products = asyncio.run(self._manager.fetch_products(
                limit=self._page_size, page=page
            ))
            total_count = self._manager._ikas.total_count
            config = get_config()
            products_data: list[tuple[Product, SeoScore | None]] = []
            for i, p in enumerate(products, 1):
                score = analyze_product(p, config.seo_target_keywords)
                db.save_score(score)
                products_data.append((p, score))
                if i % 25 == 0 or i == len(products):
                    self.after(0, lambda cnt=i, tot=len(products): self._set_status(
                        f"Analiz ediliyor... {cnt}/{tot}"
                    ))
            return products_data, total_count, len(products)

        def on_complete(result):
            products_data, total_count, count = result
            self._products_data = products_data
            self._total_count = total_count
            self._product_table.set_products(
                self._products_data, self._total_count,
                current_page=self._current_page, page_size=self._page_size,
            )
            self._update_stats()
            total_pages = max(1, (total_count + self._page_size - 1) // self._page_size)
            self._set_status(
                f"{count} urun yuklendi (sayfa {self._current_page}/{total_pages}, toplam {total_count})"
            )

        def thread_target():
            try:
                result = background_work()
                self.after(0, lambda: on_complete(result))
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(f"Hata: {e}"))

        threading.Thread(target=thread_target, daemon=True).start()

    def _on_product_select(self, data: tuple[Product, SeoScore | None]) -> None:
        product, score = data
        self._selected_product = product
        self._selected_score = score

        # Show product content in diff viewer (includes product info header)
        self._diff_viewer.show_product_preview(product)
        self._load_product_gallery(product)

        if score:
            self._diff_viewer.set_score(score)

        # Load suggestions in background
        def load_suggestions():
            try:
                slist = db.get_suggestions_by_product(product.id)
                def on_done():
                    if self._selected_product and self._selected_product.id == product.id:
                        if slist:
                            self._diff_viewer.show_suggestion(slist[0])
                self.after(0, on_done)
            except Exception:
                pass

        threading.Thread(target=load_suggestions, daemon=True).start()

    def _load_product_gallery(self, product: Product) -> None:
        self._main_image_ref = None
        self._gallery_image_refs.clear()
        self._diff_viewer.product_image_label.configure(image=None, text="Gorsel\nyok")
        for thumb in self._gallery_thumbnails:
            thumb.destroy()
        self._gallery_thumbnails.clear()

        urls = product.image_urls if product.image_urls else ([product.image_url] if product.image_url else [])
        if not urls or not _PIL_AVAILABLE:
            return

        self._load_main_image(urls[0], product.id)

        if len(urls) > 1:
            gallery = self._diff_viewer.gallery_frame
            for idx, url in enumerate(urls):
                thumb_label = ctk.CTkLabel(
                    gallery, text="...", width=40, height=40,
                    fg_color=COLORS["bg_card"], corner_radius=4,
                    text_color=COLORS["text_secondary"],
                )
                thumb_label.pack(side="left", padx=2, pady=2)
                thumb_label.bind("<Button-1>", lambda e, u=url, pid=product.id: self._load_main_image(u, pid))
                self._gallery_thumbnails.append(thumb_label)
                self._load_gallery_thumbnail(url, thumb_label, product.id)

    def _load_main_image(self, url: str, product_id: str) -> None:
        if not _PIL_AVAILABLE:
            return
        label = self._diff_viewer.product_image_label
        label.configure(text="...", image=None, text_color=COLORS["text_secondary"])

        cache_key = f"main_{url}"
        if cache_key in self._image_cache:
            self._main_image_ref = self._image_cache[cache_key]
            label.configure(image=self._main_image_ref, text="")
            return

        def fetch():
            try:
                import httpx
                response = httpx.get(url, timeout=15, follow_redirects=True)
                response.raise_for_status()
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
                img.thumbnail((90, 90), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self._image_cache[cache_key] = ctk_img

                def apply():
                    if self._selected_product and self._selected_product.id == product_id:
                        self._main_image_ref = ctk_img
                        self._diff_viewer.product_image_label.configure(image=ctk_img, text="")

                self.after(0, apply)
            except Exception:
                def on_error():
                    if self._selected_product and self._selected_product.id == product_id:
                        self._diff_viewer.product_image_label.configure(
                            text="Hata", text_color=COLORS["text_secondary"])
                self.after(0, on_error)

        self._image_executor.submit(fetch)

    def _load_gallery_thumbnail(self, url: str, label: ctk.CTkLabel, product_id: str) -> None:
        cache_key = f"thumb_{url}"
        if cache_key in self._image_cache:
            cached = self._image_cache[cache_key]
            self._gallery_image_refs.append(cached)
            label.configure(image=cached, text="")
            return

        def fetch():
            try:
                import httpx
                response = httpx.get(url, timeout=15, follow_redirects=True)
                response.raise_for_status()
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
                img.thumbnail((40, 40), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 40))
                self._image_cache[cache_key] = ctk_img

                def apply():
                    if self._selected_product and self._selected_product.id == product_id:
                        self._gallery_image_refs.append(ctk_img)
                        try:
                            label.configure(image=ctk_img, text="")
                        except Exception:
                            pass

                self.after(0, apply)
            except Exception:
                try:
                    label.after(0, lambda: label.configure(text="—", text_color=COLORS["text_secondary"]))
                except Exception:
                    pass

        self._image_executor.submit(fetch)

    def _analyze_selected(self) -> None:
        if not self._selected_product:
            return
        product = self._selected_product
        self._set_status(f"Analiz ediliyor: {product.name[:30]}...")

        def do_analyze():
            config = get_config()
            score = analyze_product(product, config.seo_target_keywords)
            db.save_score(score)
            return score

        def on_done(score):
            if self._selected_product and self._selected_product.id == product.id:
                self._selected_score = score
                self._diff_viewer.set_score(score)
            self._set_status(f"Analiz tamamlandi: {score.total_score}/100")

        def thread_target():
            try:
                result = do_analyze()
                self.after(0, lambda: on_done(result))
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(f"Analiz hatasi: {e}"))

        threading.Thread(target=thread_target, daemon=True).start()

    def _rewrite_selected(self) -> None:
        if not self._selected_product or not self._selected_score:
            self._set_status("Once urun secin ve analiz edin")
            return
        config = get_config()
        self._set_status(f"AI ile yeniden yaziliyor ({config.ai_provider})...")

        product = self._selected_product
        score = self._selected_score
        prompt_summary = (
            f"Urun: {product.name}\n"
            f"Kategori: {product.category or 'Belirtilmemis'}\n"
            f"Sorunlar: {'; '.join(score.issues[:5]) if score.issues else 'Yok'}\n"
            f"Provider: {config.ai_provider} | Model: {config.ai_model_name}"
        )

        # Canlı "thinking" balonu göster
        self._ai_chat.start_thinking("all", product.name)

        def do_rewrite():
            try:
                suggestion = self._manager._ai.rewrite_product(product, score)
                db.save_suggestion(suggestion)
                return suggestion
            except Exception as e:
                return e

        def on_done(result):
            if isinstance(result, Exception):
                self._set_status(f"AI Hata: {result}")
                self._ai_chat.complete_entry(
                    field="all", product_name=product.name,
                    prompt=prompt_summary, error=str(result),
                )
                self._update_token_display()
                return

            suggestion = result
            self._diff_viewer.show_suggestion(suggestion)
            last = self._manager.get_last_token_usage()
            cost = self._manager.get_token_usage().get("estimated_cost", 0)
            cost_str = f" | Maliyet: ${cost}" if cost else ""
            tok_str = ""
            last_in = last.get("input", 0)
            last_out = last.get("output", 0)
            if last_in or last_out:
                tok_str = f" | {last_in}+{last_out} tok"
            self._set_status(f"Rewrite tamamlandi{tok_str}{cost_str}")

            result_dict = {
                "suggested_name": suggestion.suggested_name,
                "suggested_meta_title": suggestion.suggested_meta_title,
                "suggested_meta_description": suggestion.suggested_meta_description,
            }
            if suggestion.suggested_description:
                result_dict["suggested_description"] = suggestion.suggested_description[:200] + "..."
            result_text = json.dumps(result_dict, ensure_ascii=False, indent=2)

            self._ai_chat.complete_entry(
                field="all", product_name=product.name,
                prompt=prompt_summary,
                thinking=suggestion.thinking_text or "",
                result=result_text,
            )
            self._update_token_display()

        def thread_target():
            result = do_rewrite()
            self.after(0, lambda: on_done(result))

        threading.Thread(target=thread_target, daemon=True).start()

    def _rewrite_field(self, field: str) -> None:
        if not self._selected_product or not self._selected_score:
            self._set_status("Once urun secin ve analiz edin")
            self._diff_viewer.set_field_loading_done(field)
            return

        field_labels = {
            "name": "Ad",
            "meta_title": "Meta Title",
            "meta_desc": "Meta Description",
            "desc_tr": "Aciklama (TR)",
            "desc_en": "Aciklama (EN)",
        }
        label = field_labels.get(field, field)
        config = get_config()
        self._set_status(f"{label} AI ile yaziliyor ({config.ai_provider})...")

        product = self._selected_product
        score = self._selected_score
        prompt_summary = (
            f"Alan: {label}\n"
            f"Urun: {product.name}\n"
            f"Provider: {config.ai_provider} | Model: {config.ai_model_name}"
        )

        # Canlı "thinking" balonu göster
        self._ai_chat.start_thinking(field, product.name)

        def thread_target():
            try:
                result = self._manager._ai.rewrite_field(field, product, score)
                if isinstance(result, tuple):
                    value, thinking_text = result
                else:
                    value, thinking_text = result, ""
                self.after(0, lambda: self._diff_viewer.set_field_value(field, value))
                self.after(0, lambda: self._diff_viewer.set_field_loading_done(field))
                self.after(0, lambda: self._set_status(f"{label} yazildi"))
                self.after(0, lambda: self._ai_chat.complete_entry(
                    field=field, product_name=product.name,
                    prompt=prompt_summary,
                    thinking=thinking_text,
                    result=value,
                ))
                self.after(0, self._update_token_display)
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(f"AI Hata ({label}): {e}"))
                self.after(0, lambda: self._diff_viewer.set_field_loading_done(field))
                self.after(0, lambda e=e: self._ai_chat.complete_entry(
                    field=field, product_name=product.name,
                    prompt=prompt_summary, error=str(e),
                ))
                self.after(0, self._update_token_display)

        threading.Thread(target=thread_target, daemon=True).start()

    def _apply_approved(self) -> None:
        self._set_status("Onaylanmis oneriler kontrol ediliyor...")

        def thread_target():
            try:
                suggestions = db.get_pending_suggestions()
                approved = [s for s in suggestions if s.status == "approved"]
                if not approved:
                    self.after(0, lambda: self._set_status("Onaylanmis oneri yok"))
                    return
                self.after(0, lambda: self._set_status(f"{len(approved)} oneri uygulaniyor..."))
                count = asyncio.run(self._manager.apply_suggestions(approved))
                self.after(0, lambda: self._set_status(f"{count} urun guncellendi"))
                self.after(0, self._update_stats)
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(f"Uygulama hatasi: {e}"))

        threading.Thread(target=thread_target, daemon=True).start()

    def _on_approve(self, suggestion: SeoSuggestion) -> None:
        def thread_target():
            try:
                self._manager.approve_suggestion(suggestion.product_id)
                self.after(0, lambda: self._set_status(f"Onaylandi: {suggestion.original_name}"))
                self.after(0, self._update_stats)
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(f"Onay hatasi: {e}"))
        threading.Thread(target=thread_target, daemon=True).start()

    def _on_reject(self, suggestion: SeoSuggestion) -> None:
        def thread_target():
            try:
                self._manager.reject_suggestion(suggestion.product_id)
                self.after(0, lambda: self._set_status(f"Reddedildi: {suggestion.original_name}"))
                self.after(0, lambda: self._diff_viewer.clear())
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(f"Red hatasi: {e}"))
        threading.Thread(target=thread_target, daemon=True).start()

    def _on_search(self, event=None) -> None:
        if self._search_timer is not None:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(300, self._do_search)

    def _do_search(self) -> None:
        self._search_timer = None
        query = self._search_entry.get()
        if query:
            self._product_table.filter_products(query, self._total_count)
        else:
            self._product_table.set_products(
                self._products_data, self._total_count,
                current_page=self._current_page, page_size=self._page_size,
            )

    def _on_page_change(self, page: int) -> None:
        self._fetch_products(page=page)

    def _on_filter_change(self, value: str) -> None:
        if value == "Tumu":
            self._product_table.set_products(
                self._products_data, self._total_count,
                current_page=self._current_page, page_size=self._page_size,
            )
        elif value == "Dusuk Skor":
            filtered = [(p, s) for p, s in self._products_data if s and s.total_score < 70]
            self._product_table.set_products(
                filtered, self._total_count,
                current_page=self._current_page, page_size=self._page_size,
            )
        elif value == "Bekleyen":
            def load_pending():
                pending_ids = {s.product_id for s in db.get_pending_suggestions()}
                filtered = [(p, s) for p, s in self._products_data if p.id in pending_ids]
                self.after(0, lambda: self._product_table.set_products(
                    filtered, self._total_count,
                    current_page=self._current_page, page_size=self._page_size,
                ))
            threading.Thread(target=load_pending, daemon=True).start()

    def _update_ai_button_state(self) -> None:
        config = get_config()
        ikas_configured = bool(config.ikas_store_name and config.ikas_client_id)
        ai_configured = config.ai_provider != "none"

        if ikas_configured and not ai_configured:
            self._rewrite_btn.configure(state="disabled", fg_color=COLORS["border"],
                                        text="AI ile Yeniden Yaz (provider sec)")
            self._set_status("Analiz modu — AI yeniden yazma icin Ayarlar'dan provider secin")
        else:
            self._rewrite_btn.configure(state="normal", fg_color=COLORS["bg_card"],
                                        text="AI ile Yeniden Yaz")

    def _open_settings(self) -> None:
        config = get_config()
        SettingsPanel(self, config, on_save=self._on_settings_save)

    def _on_settings_save(self, values: dict) -> None:
        from config.settings import save_config_to_env
        save_config_to_env(values)
        self._manager.reload_ai_client()
        config = get_config()
        self._update_ai_button_state()
        self._refresh_status_bar_info()
        self._set_status(f"Ayarlar kaydedildi | AI: {config.ai_provider}")


def launch() -> None:
    app = App()
    app.mainloop()
