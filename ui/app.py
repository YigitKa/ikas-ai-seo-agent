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
from ui.components.score_card import ScoreCard
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
        # Tam ekran: pencere renderdan sonra zoomed yap, yoksa geometry override eder
        self.after(50, lambda: self.state("zoomed"))

        self._manager = ProductManager()
        self._selected_product: Optional[Product] = None
        self._selected_score: Optional[SeoScore] = None
        self._products_data: list[tuple[Product, SeoScore | None]] = []
        self._filter_var = ctk.StringVar(value="all")
        self._total_count: int = 0
        self._current_page: int = 1
        self._page_size: int = 50
        # Image references to prevent garbage collection
        self._main_image_ref: Optional[ctk.CTkImage] = None
        self._gallery_image_refs: list[ctk.CTkImage] = []
        self._image_cache: dict[str, ctk.CTkImage] = {}
        # Shared thread pool for image loading (limit concurrent downloads)
        self._image_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gallery")
        # Search debounce timer
        self._search_timer: str | None = None

        self._build_toolbar()
        self._build_status_bar()
        self._build_main_layout()
        self._setup_console_logging()
        self._update_ai_button_state()

        # Periodic LLM health check every 30 seconds
        self._schedule_llm_check()

        # Auto-open settings on first launch (no ikas config) or if AI not configured
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
        """Build resizable panel layout with PanedWindows and DockablePanels."""
        # Vertical PanedWindow: [main area] / [console]
        self._vpaned = tk.PanedWindow(
            self, orient=tk.VERTICAL,
            sashwidth=6, sashrelief="flat",
            bg=COLORS["border"], opaqueresize=False,
            borderwidth=0, sashcursor="sb_v_double_arrow",
        )
        self._vpaned.pack(fill="both", expand=True, padx=5, pady=(5, 0))

        # Horizontal PanedWindow: [left] | [middle] | [right]
        self._hpaned = tk.PanedWindow(
            self._vpaned, orient=tk.HORIZONTAL,
            sashwidth=6, sashrelief="flat",
            bg=COLORS["border"], opaqueresize=False,
            borderwidth=0, sashcursor="sb_h_double_arrow",
        )

        # ── Left Panel: Product List ──
        self._left_panel = DockablePanel(self._hpaned, title="\u00DCr\u00FCn Listesi")
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

        # ── Middle Panel: Detail & Score ──
        self._middle_panel = DockablePanel(self._hpaned, title="Detay & Skor")
        middle = self._middle_panel.content

        self._product_image_label = ctk.CTkLabel(middle, text="", image=None, width=200, height=200)
        self._product_image_label.pack(padx=10, pady=(10, 2))

        self._gallery_frame = ctk.CTkFrame(middle, fg_color="transparent", height=55)
        self._gallery_frame.pack(fill="x", padx=10, pady=(0, 5))
        self._gallery_thumbnails: list[ctk.CTkLabel] = []

        self._product_info = ctk.CTkLabel(
            middle, text="Urun secin", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"], wraplength=250,
        )
        self._product_info.pack(padx=10, pady=(2, 5))

        self._score_card = ScoreCard(middle)
        self._score_card.pack(fill="x", padx=10, pady=5)

        # ── Right Panel: Diff Viewer ──
        self._right_panel = DockablePanel(self._hpaned, title="\u00D6neri Kar\u015F\u0131la\u015Ft\u0131rmas\u0131")
        self._diff_viewer = DiffViewer(
            self._right_panel.content,
            on_approve=self._on_approve,
            on_reject=self._on_reject,
            on_field_rewrite=self._rewrite_field,
        )
        self._diff_viewer.pack(fill="both", expand=True)

        # Add panels to horizontal PanedWindow
        self._hpaned.add(self._left_panel, minsize=200, stretch="always")
        self._hpaned.add(self._middle_panel, minsize=180, stretch="middle")
        self._hpaned.add(self._right_panel, minsize=200, stretch="always")

        # Add horizontal PanedWindow to vertical PanedWindow
        self._vpaned.add(self._hpaned, minsize=200, stretch="always")

        # ── Bottom Panel: Tabbed Console + AI Chat ──
        self._console_panel = DockablePanel(self._vpaned, title="Konsol / AI Yanit")
        console_content = self._console_panel.content

        # Add clear button to console panel header
        ctk.CTkButton(
            self._console_panel.header, text="Temizle", width=55, height=20,
            font=ctk.CTkFont(size=10),
            fg_color=COLORS["border"], hover_color=COLORS["bg_card"],
            command=self._clear_console,
        ).pack(side="right", padx=5)

        self._bottom_tabs = ctk.CTkTabview(
            console_content,
            fg_color=COLORS["bg_primary"],
            segmented_button_fg_color=COLORS["bg_card"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_unselected_color=COLORS["bg_secondary"],
            segmented_button_selected_hover_color=COLORS["accent"],
            segmented_button_unselected_hover_color=COLORS["border"],
            corner_radius=6,
            height=80,
        )
        self._bottom_tabs.pack(fill="both", expand=True, padx=2, pady=2)

        # Tab 1: Konsol (log output)
        tab_console = self._bottom_tabs.add("Konsol")
        self._console = ctk.CTkTextbox(
            tab_console, height=80,
            fg_color=COLORS["bg_primary"],
            text_color="#80cbc4",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=5,
            state="disabled",
        )
        self._console.pack(fill="both", expand=True, padx=2, pady=2)

        # Tab 2: AI Yanit (chat-style AI request/response log)
        tab_ai = self._bottom_tabs.add("AI Yanit")
        self._ai_chat = AIChatPanel(tab_ai)
        self._ai_chat.pack(fill="both", expand=True)

        self._vpaned.add(self._console_panel, minsize=40, stretch="never")

        # Set initial sash positions after window is fully rendered & zoomed
        self.after(500, self._set_initial_sash_positions)

    def _set_initial_sash_positions(self) -> None:
        """Set initial panel proportions after the window has rendered."""
        try:
            self.update_idletasks()
            total_w = self._hpaned.winfo_width()
            if total_w > 100:
                self._hpaned.sash_place(0, int(total_w * 0.28), 0)
                self._hpaned.sash_place(1, int(total_w * 0.55), 0)
            total_h = self._vpaned.winfo_height()
            if total_h > 100:
                # Console only ~12% of height
                self._vpaned.sash_place(0, int(total_h * 0.88), 0)
        except Exception:
            pass

    def _setup_console_logging(self) -> None:
        """Wire up Python logging to the console widget."""
        handler = ConsoleLogHandler(self._console)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        self._log("Uygulama baslatildi. Hazir.")

    def _log(self, message: str) -> None:
        """Write a message to the console panel."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._console.configure(state="normal")
        self._console.insert("end", f"{ts}  {message}\n")
        self._console.see("end")
        self._console.configure(state="disabled")

    def _clear_console(self) -> None:
        self._console.configure(state="normal")
        self._console.delete("1.0", "end")
        self._console.configure(state="disabled")
        self._ai_chat.clear()

    def _build_status_bar(self) -> None:
        self._status_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=32)
        self._status_bar.pack(side="bottom", fill="x", padx=5, pady=(0, 5))
        self._status_bar.pack_propagate(False)

        # ── Left: status message ──
        self._status_label = ctk.CTkLabel(
            self._status_bar, text="Hazir",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
        )
        self._status_label.pack(side="left", padx=10)

        # ── Right side labels (packed right-to-left) ──
        # Product stats (rightmost)
        self._stats_label = ctk.CTkLabel(
            self._status_bar, text="",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=10),
        )
        self._stats_label.pack(side="right", padx=(6, 10))

        self._add_separator()

        # Token usage
        self._token_label = ctk.CTkLabel(
            self._status_bar, text="Tokens: -",
            text_color="#80cbc4", font=ctk.CTkFont(family="Consolas", size=10),
        )
        self._token_label.pack(side="right", padx=6)

        self._add_separator()

        # LLM status indicator
        self._llm_status_label = ctk.CTkLabel(
            self._status_bar, text="\u25CF Baglanti yok",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=10),
        )
        self._llm_status_label.pack(side="right", padx=6)

        self._add_separator()

        # Thinking mode
        self._thinking_label = ctk.CTkLabel(
            self._status_bar, text="Think: OFF",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=10),
        )
        self._thinking_label.pack(side="right", padx=6)

        self._add_separator()

        # Max tokens
        self._maxtok_label = ctk.CTkLabel(
            self._status_bar, text="MaxTok: -",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=10),
        )
        self._maxtok_label.pack(side="right", padx=6)

        self._add_separator()

        # Model + provider
        self._model_label = ctk.CTkLabel(
            self._status_bar, text="Model: -",
            text_color="#5c9aff", font=ctk.CTkFont(size=10, weight="bold"),
        )
        self._model_label.pack(side="right", padx=6)

        self._add_separator()

        # Store name
        self._store_label = ctk.CTkLabel(
            self._status_bar, text="Magaza: -",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=10),
        )
        self._store_label.pack(side="right", padx=6)

        # Initial populate
        self._refresh_status_bar_info()

    def _add_separator(self) -> None:
        """Add a thin vertical separator to the status bar (packed right)."""
        sep = ctk.CTkFrame(self._status_bar, fg_color=COLORS["border"], width=1)
        sep.pack(side="right", fill="y", padx=2, pady=4)

    def _refresh_status_bar_info(self) -> None:
        """Update all status bar info labels from current config."""
        config = get_config()

        # Store
        store = config.ikas_store_name or "-"
        self._store_label.configure(text=f"Magaza: {store}")

        # Model + provider
        model_name = config.ai_model_name or "-"
        # Shorten long model names (e.g. "qwen/qwen3.5-9b" -> "qwen3.5-9b")
        if "/" in model_name:
            model_name = model_name.split("/")[-1]
        if len(model_name) > 25:
            model_name = model_name[:22] + "..."
        provider = config.ai_provider or "none"
        self._model_label.configure(text=f"{model_name} ({provider})")

        # Max tokens
        self._maxtok_label.configure(text=f"MaxTok: {config.ai_max_tokens}")

        # Thinking mode
        if config.ai_thinking_mode:
            self._thinking_label.configure(text="Think: ON", text_color="#69f0ae")
        else:
            self._thinking_label.configure(text="Think: OFF", text_color=COLORS["text_secondary"])

        # LLM status — check connectivity in background
        self._check_llm_status()

    def _check_llm_status(self) -> None:
        """Ping the LLM endpoint in a background thread to check availability."""
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
                # Build the base URL to ping
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

                # For OpenAI-compatible endpoints, try /v1/models
                if provider in ("ollama", "lm-studio", "custom", "openai"):
                    if not base.rstrip("/").endswith("/v1"):
                        base = base.rstrip("/") + "/v1"
                    url = f"{base}/models"
                else:
                    url = base

                resp = httpx.get(url, timeout=5)
                if resp.status_code == 200:
                    # Try to extract loaded model info from LM Studio
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
            except httpx.ConnectError:
                self.after(0, lambda: self._llm_status_label.configure(
                    text="\u25CF Cevrimdisi",
                    text_color=COLORS["error"],
                ))
            except Exception as e:
                self.after(0, lambda: self._llm_status_label.configure(
                    text=f"\u25CF Hata",
                    text_color=COLORS["error"],
                ))

        threading.Thread(target=ping, daemon=True).start()

    def _update_token_display(self) -> None:
        """Update the token counter in the status bar from the AI client."""
        try:
            usage = self._manager.get_token_usage()
            inp = usage.get("input", 0)
            out = usage.get("output", 0)
            total = inp + out
            # Format with K suffix for readability
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
        """Periodically check LLM endpoint availability (every 30s)."""
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
            """Run fetch + analysis entirely in background thread."""
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
                # Progress update every 25 products (reduce UI flooding)
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

        self._product_info.configure(
            text=f"{product.name}\n\nKategori: {product.category or '-'}\nSKU: {product.sku or '-'}"
        )
        self._load_product_gallery(product)

        if score:
            self._score_card.set_score(score)

        # Show current product content in diff viewer (original side)
        self._diff_viewer.show_product_preview(product)

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
        """Load main image and thumbnail gallery for a product."""
        # Clear previous gallery
        self._main_image_ref = None
        self._gallery_image_refs.clear()
        self._product_image_label.configure(image=None, text="")
        for thumb in self._gallery_thumbnails:
            thumb.destroy()
        self._gallery_thumbnails.clear()

        urls = product.image_urls if product.image_urls else ([product.image_url] if product.image_url else [])
        if not urls or not _PIL_AVAILABLE:
            self._product_image_label.configure(text="Gorsel yok", text_color=COLORS["text_secondary"])
            return

        # Load main image (first URL)
        self._load_main_image(urls[0], product.id)

        # Build clickable thumbnail strip if multiple images
        if len(urls) > 1:
            for idx, url in enumerate(urls):
                thumb_label = ctk.CTkLabel(
                    self._gallery_frame, text="...", width=48, height=48,
                    fg_color=COLORS["bg_card"], corner_radius=5,
                    text_color=COLORS["text_secondary"],
                )
                thumb_label.pack(side="left", padx=2, pady=2)
                thumb_label.bind("<Button-1>", lambda e, u=url, pid=product.id: self._load_main_image(u, pid))
                self._gallery_thumbnails.append(thumb_label)
                # Lazy load each thumbnail
                self._load_gallery_thumbnail(url, thumb_label, product.id)

    def _load_main_image(self, url: str, product_id: str) -> None:
        """Load a single URL into the main product image label (lazy, thread-safe)."""
        if not _PIL_AVAILABLE:
            return
        self._product_image_label.configure(text="Yukleniyor...", image=None, text_color=COLORS["text_secondary"])

        # Check cache first
        cache_key = f"main_{url}"
        if cache_key in self._image_cache:
            self._main_image_ref = self._image_cache[cache_key]
            self._product_image_label.configure(image=self._main_image_ref, text="")
            return

        def fetch():
            try:
                import httpx
                response = httpx.get(url, timeout=15, follow_redirects=True)
                response.raise_for_status()
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
                img.thumbnail((200, 200), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self._image_cache[cache_key] = ctk_img

                def apply():
                    # Only apply if we're still viewing the same product
                    if self._selected_product and self._selected_product.id == product_id:
                        self._main_image_ref = ctk_img
                        self._product_image_label.configure(image=ctk_img, text="")

                self.after(0, apply)
            except Exception:
                def on_error():
                    if self._selected_product and self._selected_product.id == product_id:
                        self._product_image_label.configure(text="Gorsel yuklenemedi", text_color=COLORS["text_secondary"])
                self.after(0, on_error)

        self._image_executor.submit(fetch)

    def _load_gallery_thumbnail(self, url: str, label: ctk.CTkLabel, product_id: str) -> None:
        """Lazy-load a small thumbnail into a gallery label."""
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
                img.thumbnail((48, 48), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(48, 48))
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
                self._score_card.set_score(score)
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

        def do_rewrite():
            try:
                suggestion = self._manager._ai.rewrite_product(
                    product, score
                )
                db.save_suggestion(suggestion)
                return suggestion
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(f"AI Hata: {e}"))
                # Log error to AI chat
                self.after(0, lambda e=e: self._ai_chat.add_entry(
                    field="all", product_name=product.name,
                    prompt=prompt_summary, error=str(e),
                ))
                self.after(0, lambda: self._bottom_tabs.set("AI Yanit"))
                self.after(0, self._update_token_display)
                return None

        def on_done(suggestion):
            if suggestion is None:
                return
            self._diff_viewer.show_suggestion(suggestion)
            usage = self._manager.get_token_usage()
            last = self._manager.get_last_token_usage()
            cost = usage.get("estimated_cost", 0)
            cost_str = f" | Maliyet: ${cost}" if cost else ""
            tok_str = ""
            last_in = last.get("input", 0)
            last_out = last.get("output", 0)
            if last_in or last_out:
                tok_str = f" | {last_in}+{last_out} tok"
            self._set_status(f"Rewrite tamamlandi{tok_str}{cost_str}")
            # Build result summary for chat panel
            result_dict = {
                "suggested_name": suggestion.suggested_name,
                "suggested_meta_title": suggestion.suggested_meta_title,
                "suggested_meta_description": suggestion.suggested_meta_description,
            }
            if suggestion.suggested_description:
                result_dict["suggested_description"] = suggestion.suggested_description[:200] + "..."
            result_text = json.dumps(result_dict, ensure_ascii=False, indent=2)
            self._ai_chat.add_entry(
                field="all", product_name=product.name,
                prompt=prompt_summary,
                thinking=suggestion.thinking_text or "",
                result=result_text,
            )
            self._update_token_display()

        def thread_target():
            result = do_rewrite()
            if result:
                self.after(0, lambda: on_done(result))

        threading.Thread(target=thread_target, daemon=True).start()

    def _rewrite_field(self, field: str) -> None:
        """Rewrite a single field using AI (called from DiffViewer per-field buttons)."""
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

        def thread_target():
            try:
                result = self._manager._ai.rewrite_field(field, product, score)
                # result can be str or (str, thinking_text) tuple
                if isinstance(result, tuple):
                    value, thinking_text = result
                else:
                    value, thinking_text = result, ""
                self.after(0, lambda: self._diff_viewer.set_field_value(field, value))
                self.after(0, lambda: self._diff_viewer.set_field_loading_done(field))
                self.after(0, lambda: self._set_status(f"{label} yazildi"))
                # Log to AI chat panel
                self.after(0, lambda: self._ai_chat.add_entry(
                    field=field, product_name=product.name,
                    prompt=prompt_summary,
                    thinking=thinking_text,
                    result=value,
                ))
                self.after(0, self._update_token_display)
            except Exception as e:
                self.after(0, lambda e=e: self._set_status(f"AI Hata ({label}): {e}"))
                self.after(0, lambda: self._diff_viewer.set_field_loading_done(field))
                # Log error to AI chat panel
                self.after(0, lambda e=e: self._ai_chat.add_entry(
                    field=field, product_name=product.name,
                    prompt=prompt_summary, error=str(e),
                ))
                self.after(0, lambda: self._bottom_tabs.set("AI Yanit"))
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
        # Debounce: wait 300ms after last keystroke before filtering
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
        """Handle page navigation from ProductTable pagination controls."""
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
        # Reload AI client with new config
        self._manager.reload_ai_client()
        config = get_config()
        self._update_ai_button_state()
        self._refresh_status_bar_info()
        self._set_status(f"Ayarlar kaydedildi | AI: {config.ai_provider}")


def launch() -> None:
    app = App()
    app.mainloop()
