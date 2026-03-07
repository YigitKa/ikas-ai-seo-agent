import asyncio
import json
import logging
import sys
import threading
import tkinter as tk
from datetime import datetime
from typing import Callable, Optional

import customtkinter as ctk

from config.settings import get_config
from core.models import Product, SeoScore, SeoSuggestion
from core.product_manager import ProductManager
from data import db
from ui.components.ai_chat_panel import AIChatPanel
from ui.components.diff_viewer import DiffViewer
from ui.components.dockable_panel import DockablePanel
from ui.components.product_table import ProductTable
from ui.components.settings_panel import SettingsPanel
from ui.image_service import get_image_service
from ui.themes.dark import COLORS

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ConsoleLogHandler(logging.Handler):
    def __init__(self, console_widget: ctk.CTkTextbox) -> None:
        super().__init__()
        self._console = console_widget

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self._console.after(0, lambda: self._append(message))
        except Exception:
            self.handleError(record)

    def _append(self, message: str) -> None:
        self._console.configure(state="normal")
        self._console.insert("end", message + "\n")
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
        self._image_service = get_image_service()
        self._selected_product: Optional[Product] = None
        self._selected_score: Optional[SeoScore] = None
        self._products_data: list[tuple[Product, SeoScore | None]] = []
        self._filter_var = ctk.StringVar(value="Tumu")
        self._total_count = 0
        self._current_page = 1
        self._page_size = 50
        self._search_timer: str | None = None
        self._main_image_ref: Optional[ctk.CTkImage] = None
        self._gallery_image_refs: list[ctk.CTkImage] = []
        self._gallery_thumbnails: list[ctk.CTkLabel] = []
        self._image_cache: dict[str, ctk.CTkImage | None] = {}

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
        ctk.CTkButton(toolbar, text="Urunleri Cek", command=self._fetch_products, fg_color=COLORS["accent"]).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Secilileri Analiz Et", command=self._analyze_selected, fg_color=COLORS["bg_card"]).pack(side="left", padx=5, pady=5)
        self._rewrite_btn = ctk.CTkButton(toolbar, text="AI ile Yeniden Yaz", command=self._rewrite_selected, fg_color=COLORS["bg_card"])
        self._rewrite_btn.pack(side="left", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Onayla ve Uygula", command=self._apply_approved, fg_color=COLORS["success"]).pack(side="left", padx=5, pady=5)
        ctk.CTkSegmentedButton(toolbar, values=["Tumu", "Dusuk Skor", "Bekleyen", "Onayli"], variable=self._filter_var, command=self._on_filter_change).pack(side="right", padx=10, pady=5)
        ctk.CTkButton(toolbar, text="Ayarlar", width=80, command=self._open_settings, fg_color=COLORS["border"]).pack(side="right", padx=5, pady=5)

    def _build_main_layout(self) -> None:
        self._vpaned = tk.PanedWindow(self, orient=tk.VERTICAL, sashwidth=6, sashrelief="flat", bg=COLORS["border"], opaqueresize=False, borderwidth=0, sashcursor="sb_v_double_arrow")
        self._vpaned.pack(fill="both", expand=True, padx=5, pady=(5, 0))
        self._hpaned = tk.PanedWindow(self._vpaned, orient=tk.HORIZONTAL, sashwidth=6, sashrelief="flat", bg=COLORS["border"], opaqueresize=False, borderwidth=0, sashcursor="sb_h_double_arrow")

        self._left_panel = DockablePanel(self._hpaned, title="Urun Listesi")
        left = self._left_panel.content
        search_frame = ctk.CTkFrame(left, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=10)
        self._search_entry = ctk.CTkEntry(search_frame, placeholder_text="Urun ara...", fg_color=COLORS["input_bg"])
        self._search_entry.pack(fill="x")
        self._search_entry.bind("<KeyRelease>", self._on_search)
        self._product_table = ProductTable(left, on_select=self._on_product_select, on_page_change=self._on_page_change, fg_color=COLORS["bg_secondary"])
        self._product_table.pack(fill="both", expand=True, padx=5, pady=5)

        self._right_panel = DockablePanel(self._hpaned, title="Urun Detay & SEO")
        self._diff_viewer = DiffViewer(self._right_panel.content, on_approve=self._on_approve, on_reject=self._on_reject, on_field_rewrite=self._rewrite_field)
        self._diff_viewer.pack(fill="both", expand=True)

        self._chat_panel = DockablePanel(self._hpaned, title="AI Chat")
        self._ai_chat = AIChatPanel(self._chat_panel.content)
        self._ai_chat.pack(fill="both", expand=True)

        self._hpaned.add(self._left_panel, minsize=180, stretch="always")
        self._hpaned.add(self._right_panel, minsize=380, stretch="always")
        self._hpaned.add(self._chat_panel, minsize=260, stretch="always")
        self._vpaned.add(self._hpaned, minsize=200, stretch="always")

        self._console_panel = DockablePanel(self._vpaned, title="Konsol")
        console_content = self._console_panel.content
        ctk.CTkButton(self._console_panel.header, text="Temizle", width=55, height=20, font=ctk.CTkFont(size=12), fg_color=COLORS["border"], hover_color=COLORS["bg_card"], command=self._clear_console).pack(side="right", padx=5)
        self._console = ctk.CTkTextbox(console_content, height=80, fg_color=COLORS["bg_primary"], text_color="#80cbc4", font=ctk.CTkFont(family="Consolas", size=12), corner_radius=5, state="disabled")
        self._console.pack(fill="both", expand=True, padx=2, pady=2)
        self._vpaned.add(self._console_panel, minsize=40, stretch="never")

    def _on_configure(self, event=None) -> None:
        if self._sash_set:
            return
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
        self._status_label = ctk.CTkLabel(self._status_bar, text="Hazir", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12))
        self._status_label.pack(side="left", padx=10)
        self._stats_label = ctk.CTkLabel(self._status_bar, text="", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12))
        self._stats_label.pack(side="right", padx=(6, 10))
        self._add_separator()
        self._token_label = ctk.CTkLabel(self._status_bar, text="Tokens: -", text_color="#80cbc4", font=ctk.CTkFont(family="Consolas", size=12))
        self._token_label.pack(side="right", padx=6)
        self._add_separator()
        self._llm_status_label = ctk.CTkLabel(self._status_bar, text="\u25CF Baglanti yok", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12))
        self._llm_status_label.pack(side="right", padx=6)
        self._add_separator()
        self._thinking_label = ctk.CTkLabel(self._status_bar, text="Think: OFF", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12))
        self._thinking_label.pack(side="right", padx=6)
        self._add_separator()
        self._maxtok_label = ctk.CTkLabel(self._status_bar, text="MaxTok: -", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12))
        self._maxtok_label.pack(side="right", padx=6)
        self._add_separator()
        self._model_label = ctk.CTkLabel(self._status_bar, text="Model: -", text_color="#5c9aff", font=ctk.CTkFont(size=12, weight="bold"))
        self._model_label.pack(side="right", padx=6)
        self._add_separator()
        self._store_label = ctk.CTkLabel(self._status_bar, text="Magaza: -", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12))
        self._store_label.pack(side="right", padx=6)
        self._refresh_status_bar_info()

    def _add_separator(self) -> None:
        ctk.CTkFrame(self._status_bar, fg_color=COLORS["border"], width=1).pack(side="right", fill="y", padx=2, pady=4)

    def _refresh_status_bar_info(self) -> None:
        config = get_config()
        self._store_label.configure(text=f"Magaza: {config.ikas_store_name or '-'}")
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
            self._llm_status_label.configure(text="\u25CF Provider yok", text_color=COLORS["text_secondary"])
            return
        self._llm_status_label.configure(text="\u25CF Kontrol ediliyor...", text_color=COLORS["warning"])

        def ping() -> None:
            try:
                import httpx
                from core.ai_client import PROVIDER_BASE_URLS

                base = config.ai_base_url.rstrip("/") if config.ai_base_url else PROVIDER_BASE_URLS.get(provider, "")
                if not base:
                    self.after(0, lambda: self._llm_status_label.configure(text="\u25CF URL yok", text_color=COLORS["error"]))
                    return
                if provider in ("ollama", "lm-studio", "custom", "openai") and not base.endswith("/v1"):
                    base = base + "/v1"
                url = f"{base}/models" if provider in ("ollama", "lm-studio", "custom", "openai") else base
                response = httpx.get(url, timeout=5)
                if response.status_code != 200:
                    self.after(0, lambda: self._llm_status_label.configure(text=f"\u25CF HTTP {response.status_code}", text_color=COLORS["error"]))
                    return
                model_info = ""
                try:
                    payload = response.json()
                    if payload.get("data"):
                        model_id = payload["data"][0].get("id", "")
                        if model_id:
                            model_info = f" [{model_id}]"
                except Exception:
                    pass
                self.after(0, lambda: self._llm_status_label.configure(text=f"\u25CF Bagli{model_info}", text_color=COLORS["success"]))
            except Exception:
                self.after(0, lambda: self._llm_status_label.configure(text="\u25CF Cevrimdisi", text_color=COLORS["error"]))

        threading.Thread(target=ping, daemon=True).start()

    def _update_token_display(self) -> None:
        try:
            usage = self._manager.get_token_usage()
            inp = usage.get("input", 0)
            out = usage.get("output", 0)
            total = inp + out

            def fmt(value: int) -> str:
                if value >= 100_000:
                    return f"{value / 1000:.0f}K"
                if value >= 1000:
                    return f"{value / 1000:.1f}K"
                return str(value)

            if total > 0:
                self._token_label.configure(text=f"Tokens: {fmt(inp)} in / {fmt(out)} out", text_color="#69f0ae")
            else:
                self._token_label.configure(text="Tokens: -", text_color="#80cbc4")
        except Exception as exc:
            logger.error("Token display update failed: %s", exc)

    def _schedule_llm_check(self) -> None:
        self._check_llm_status()
        self._update_token_display()
        self.after(30_000, self._schedule_llm_check)

    def _run_in_background(
        self,
        work: Callable[[], object],
        on_success: Callable[[object], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        def thread_target() -> None:
            try:
                result = work()
            except Exception as exc:
                if on_error is not None:
                    self.after(0, lambda exc=exc: on_error(exc))
                return

            if on_success is not None:
                self.after(0, lambda result=result: on_success(result))

        threading.Thread(target=thread_target, daemon=True).start()

    def _set_status(self, text: str) -> None:
        self._status_label.configure(text=text)
        self._log(text)

    def _render_product_table(self, products: list[tuple[Product, SeoScore | None]]) -> None:
        self._product_table.set_products(products, self._total_count, current_page=self._current_page, page_size=self._page_size)
        query = self._search_entry.get().strip()
        if query:
            self._product_table.filter_products(query, self._total_count)

    def _update_stats(self) -> None:
        listed = len(self._products_data)
        analyzed = sum(1 for _, score in self._products_data if score is not None)
        pending = self._manager.get_pending_suggestion_count()
        if self._total_count > 0 and self._total_count != listed:
            total_text = f"Toplam: {listed}/{self._total_count}"
        else:
            total_text = f"Toplam: {listed}"
        self._stats_label.configure(text=f"{total_text} | Analiz: {analyzed} | Bekleyen: {pending}")

    def _fetch_products(self, page: int = 1) -> None:
        self._set_status(f"Urunler cekiliyor (sayfa {page})...")
        self._current_page = page

        def background_work():
            products = asyncio.run(self._manager.fetch_products(limit=self._page_size, page=page))
            total_count = self._manager._ikas.total_count
            self.after(0, lambda count=len(products): self._set_status(f"{count} urun analiz ediliyor..."))
            products_data = self._manager.score_products(products)
            return products_data, total_count, len(products)

        def on_complete(result: object) -> None:
            products_data, total_count, count = result
            self._products_data = products_data
            self._total_count = total_count
            self._render_product_table(self._products_data)
            self._update_stats()
            total_pages = max(1, (total_count + self._page_size - 1) // self._page_size)
            self._set_status(f"{count} urun yuklendi (sayfa {self._current_page}/{total_pages}, toplam {total_count})")

        self._run_in_background(background_work, on_complete, lambda exc: self._set_status(f"Hata: {exc}"))

    def _on_product_select(self, data: tuple[Product, SeoScore | None]) -> None:
        product, score = data
        self._selected_product = product
        self._selected_score = score
        self._diff_viewer.show_product_preview(product)
        self._load_product_gallery(product)
        if score is not None:
            self._diff_viewer.set_score(score)
        else:
            self._diff_viewer.clear_score()

        def load_latest_suggestion():
            return self._manager.get_latest_suggestion(product.id)

        def on_suggestion_loaded(suggestion: object) -> None:
            if suggestion is not None and self._selected_product is not None and self._selected_product.id == product.id:
                self._diff_viewer.show_suggestion(suggestion)

        self._run_in_background(load_latest_suggestion, on_suggestion_loaded)

    def _load_product_gallery(self, product: Product) -> None:
        self._main_image_ref = None
        self._gallery_image_refs.clear()
        self._diff_viewer.product_image_label.configure(image=None, text="Gorsel\nyok")
        for thumb in self._gallery_thumbnails:
            thumb.destroy()
        self._gallery_thumbnails.clear()

        urls = product.image_urls if product.image_urls else ([product.image_url] if product.image_url else [])
        if not urls:
            return

        self._load_main_image(urls[0], product.id)
        if len(urls) <= 1:
            return

        gallery = self._diff_viewer.gallery_frame
        for url in urls:
            thumb_label = ctk.CTkLabel(gallery, text="...", width=40, height=40, fg_color=COLORS["bg_card"], corner_radius=4, text_color=COLORS["text_secondary"])
            thumb_label.pack(side="left", padx=2, pady=2)
            thumb_label.bind("<Button-1>", lambda e, u=url, pid=product.id: self._load_main_image(u, pid))
            self._gallery_thumbnails.append(thumb_label)
            self._load_gallery_thumbnail(url, thumb_label, product.id)

    def _load_main_image(self, url: str, product_id: str) -> None:
        label = self._diff_viewer.product_image_label
        label._image_url = url
        label.configure(text="...", image=None, text_color=COLORS["text_secondary"])
        cache_key = f"main_{url}"
        if cache_key in self._image_cache:
            cached = self._image_cache[cache_key]
            if cached is not None:
                self._main_image_ref = cached
                label.configure(image=cached, text="")
            else:
                label.configure(text="Hata", image=None, text_color=COLORS["text_secondary"])
            return

        def on_success(image) -> None:
            if getattr(label, "_image_url", None) != url or self._selected_product is None or self._selected_product.id != product_id:
                return
            cached = self._image_cache.get(cache_key)
            if cached is None:
                cached = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                self._image_cache[cache_key] = cached
            self._main_image_ref = cached
            label.configure(image=cached, text="")

        def on_error() -> None:
            if getattr(label, "_image_url", None) == url and self._selected_product is not None and self._selected_product.id == product_id:
                self._image_cache[cache_key] = None
                label.configure(text="Hata", image=None, text_color=COLORS["text_secondary"])

        self._image_service.load(url, (90, 90), label, on_success, on_error)

    def _load_gallery_thumbnail(self, url: str, label: ctk.CTkLabel, product_id: str) -> None:
        cache_key = f"thumb_{url}"
        label._image_url = url
        if cache_key in self._image_cache:
            cached = self._image_cache[cache_key]
            if cached is not None:
                self._gallery_image_refs.append(cached)
                label.configure(image=cached, text="")
            else:
                label.configure(text="-", image=None, text_color=COLORS["text_secondary"])
            return

        def on_success(image) -> None:
            if getattr(label, "_image_url", None) != url or self._selected_product is None or self._selected_product.id != product_id:
                return
            cached = self._image_cache.get(cache_key)
            if cached is None:
                cached = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
                self._image_cache[cache_key] = cached
            self._gallery_image_refs.append(cached)
            label.configure(image=cached, text="")

        def on_error() -> None:
            if getattr(label, "_image_url", None) != url:
                return
            self._image_cache[cache_key] = None
            label.configure(text="-", image=None, text_color=COLORS["text_secondary"])

        self._image_service.load(url, (40, 40), label, on_success, on_error)

    def _analyze_selected(self) -> None:
        if self._selected_product is None:
            return
        product = self._selected_product
        self._set_status(f"Analiz ediliyor: {product.name[:30]}...")

        def do_analyze():
            return self._manager.score_products([product])[0][1]

        def on_done(score: object) -> None:
            if self._selected_product is not None and self._selected_product.id == product.id:
                self._selected_score = score
                self._diff_viewer.set_score(score)
            self._set_status(f"Analiz tamamlandi: {score.total_score}/100")

        self._run_in_background(do_analyze, on_done, lambda exc: self._set_status(f"Analiz hatasi: {exc}"))

    def _rewrite_selected(self) -> None:
        if self._selected_product is None or self._selected_score is None:
            self._set_status("Once urun secin ve analiz edin")
            return

        config = get_config()
        product = self._selected_product
        score = self._selected_score
        self._set_status(f"AI ile yeniden yaziliyor ({config.ai_provider})...")
        prompt_summary = (
            f"Urun: {product.name}\n"
            f"Kategori: {product.category or 'Belirtilmemis'}\n"
            f"Sorunlar: {'; '.join(score.issues[:5]) if score.issues else 'Yok'}\n"
            f"Provider: {config.ai_provider} | Model: {config.ai_model_name}"
        )
        self._ai_chat.start_thinking("all", product.name)

        def do_rewrite():
            suggestion = self._manager._ai.rewrite_product(product, score)
            db.save_suggestion(suggestion)
            return suggestion

        def on_done(result: object) -> None:
            suggestion = result
            self._diff_viewer.show_suggestion(suggestion)
            last = self._manager.get_last_token_usage()
            cost = self._manager.get_token_usage().get("estimated_cost", 0)
            cost_text = f" | Maliyet: ${cost}" if cost else ""
            token_text = ""
            if last.get("input", 0) or last.get("output", 0):
                token_text = f" | {last.get('input', 0)}+{last.get('output', 0)} tok"
            self._set_status(f"Rewrite tamamlandi{token_text}{cost_text}")

            result_dict = {
                "suggested_name": suggestion.suggested_name,
                "suggested_meta_title": suggestion.suggested_meta_title,
                "suggested_meta_description": suggestion.suggested_meta_description,
            }
            if suggestion.suggested_description:
                result_dict["suggested_description"] = suggestion.suggested_description[:200] + "..."

            self._ai_chat.complete_entry(field="all", product_name=product.name, prompt=prompt_summary, thinking=suggestion.thinking_text or "", result=json.dumps(result_dict, ensure_ascii=False, indent=2))
            self._update_token_display()

        def on_error(exc: Exception) -> None:
            self._set_status(f"AI Hata: {exc}")
            self._ai_chat.complete_entry(field="all", product_name=product.name, prompt=prompt_summary, error=str(exc))
            self._update_token_display()

        self._run_in_background(do_rewrite, on_done, on_error)

    def _rewrite_field(self, field: str) -> None:
        if self._selected_product is None or self._selected_score is None:
            self._set_status("Once urun secin ve analiz edin")
            self._diff_viewer.set_field_loading_done(field)
            return

        labels = {
            "name": "Ad",
            "meta_title": "Meta Title",
            "meta_desc": "Meta Description",
            "desc_tr": "Aciklama (TR)",
            "desc_en": "Aciklama (EN)",
        }
        field_label = labels.get(field, field)
        config = get_config()
        product = self._selected_product
        score = self._selected_score
        self._set_status(f"{field_label} AI ile yaziliyor ({config.ai_provider})...")
        prompt_summary = (
            f"Alan: {field_label}\n"
            f"Urun: {product.name}\n"
            f"Provider: {config.ai_provider} | Model: {config.ai_model_name}"
        )
        self._ai_chat.start_thinking(field, product.name)

        def do_rewrite():
            result = self._manager._ai.rewrite_field(field, product, score)
            if isinstance(result, tuple):
                return result
            return result, ""

        def on_done(result: object) -> None:
            value, thinking_text = result
            self._diff_viewer.set_field_value(field, value)
            self._diff_viewer.set_field_loading_done(field)
            self._set_status(f"{field_label} yazildi")
            self._ai_chat.complete_entry(field=field, product_name=product.name, prompt=prompt_summary, thinking=thinking_text, result=value)
            self._update_token_display()

        def on_error(exc: Exception) -> None:
            self._set_status(f"AI Hata ({field_label}): {exc}")
            self._diff_viewer.set_field_loading_done(field)
            self._ai_chat.complete_entry(field=field, product_name=product.name, prompt=prompt_summary, error=str(exc))
            self._update_token_display()

        self._run_in_background(do_rewrite, on_done, on_error)

    def _apply_approved(self) -> None:
        self._set_status("Onaylanmis oneriler kontrol ediliyor...")

        def load_approved():
            return self._manager.get_approved_suggestions()

        def on_loaded(result: object) -> None:
            approved = result
            if not approved:
                self._set_status("Onaylanmis oneri yok")
                return

            self._set_status(f"{len(approved)} oneri uygulaniyor...")

            def apply_work():
                return asyncio.run(self._manager.apply_suggestions(approved))

            def on_applied(count: object) -> None:
                self._set_status(f"{count} urun guncellendi")
                self._update_stats()

            self._run_in_background(apply_work, on_applied, lambda exc: self._set_status(f"Uygulama hatasi: {exc}"))

        self._run_in_background(load_approved, on_loaded, lambda exc: self._set_status(f"Uygulama hatasi: {exc}"))

    def _on_approve(self, suggestion: SeoSuggestion) -> None:
        def work():
            self._manager.approve_suggestion(suggestion.product_id)
            return suggestion.original_name

        def on_done(result: object) -> None:
            self._set_status(f"Onaylandi: {result}")
            self._update_stats()

        self._run_in_background(work, on_done, lambda exc: self._set_status(f"Onay hatasi: {exc}"))

    def _on_reject(self, suggestion: SeoSuggestion) -> None:
        def work():
            self._manager.reject_suggestion(suggestion.product_id)
            return suggestion.original_name

        def on_done(result: object) -> None:
            self._set_status(f"Reddedildi: {result}")
            self._diff_viewer.clear()
            self._update_stats()

        self._run_in_background(work, on_done, lambda exc: self._set_status(f"Red hatasi: {exc}"))

    def _on_search(self, event=None) -> None:
        if self._search_timer is not None:
            self.after_cancel(self._search_timer)
        self._search_timer = self.after(300, self._do_search)

    def _do_search(self) -> None:
        self._search_timer = None
        query = self._search_entry.get().strip()
        if query:
            self._product_table.filter_products(query, self._total_count)
        else:
            self._render_product_table(self._products_data)

    def _on_page_change(self, page: int) -> None:
        self._fetch_products(page=page)

    def _filter_products_by_suggestion_status(self, status: str) -> None:
        def work():
            return self._manager.get_suggestion_product_ids(status)

        def on_done(result: object) -> None:
            product_ids = result
            filtered = [(product, score) for product, score in self._products_data if product.id in product_ids]
            self._render_product_table(filtered)

        self._run_in_background(work, on_done, lambda exc: self._set_status(f"Filtre hatasi: {exc}"))

    def _on_filter_change(self, value: str) -> None:
        if value == "Tumu":
            self._render_product_table(self._products_data)
            return
        if value == "Dusuk Skor":
            filtered = [(product, score) for product, score in self._products_data if score is not None and score.total_score < 70]
            self._render_product_table(filtered)
            return
        if value == "Bekleyen":
            self._filter_products_by_suggestion_status("pending")
            return
        if value == "Onayli":
            self._filter_products_by_suggestion_status("approved")

    def _update_ai_button_state(self) -> None:
        config = get_config()
        ikas_configured = bool(config.ikas_store_name and config.ikas_client_id)
        ai_configured = config.ai_provider != "none"
        if ikas_configured and not ai_configured:
            self._rewrite_btn.configure(state="disabled", fg_color=COLORS["border"], text="AI ile Yeniden Yaz (provider sec)")
            self._set_status("Analiz modu - AI yeniden yazma icin Ayarlar'dan provider secin")
        else:
            self._rewrite_btn.configure(state="normal", fg_color=COLORS["bg_card"], text="AI ile Yeniden Yaz")

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
    if "--cli" in sys.argv:
        return
    app = App()
    app.mainloop()
