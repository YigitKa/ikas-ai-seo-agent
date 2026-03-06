import asyncio
import logging
import threading
from typing import Optional

import customtkinter as ctk

from config.settings import get_config
from core.models import Product, SeoScore, SeoSuggestion
from core.product_manager import ProductManager
from core.seo_analyzer import analyze_product
from data import db
from ui.components.diff_viewer import DiffViewer
from ui.components.product_table import ProductTable
from ui.components.score_card import ScoreCard
from ui.components.settings_panel import SettingsPanel
from ui.themes.dark import COLORS

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ikas SEO Optimizer")
        self.geometry("1400x800")
        self.configure(fg_color=COLORS["bg_primary"])

        self._manager = ProductManager()
        self._selected_product: Optional[Product] = None
        self._selected_score: Optional[SeoScore] = None
        self._products_data: list[tuple[Product, SeoScore | None]] = []
        self._filter_var = ctk.StringVar(value="all")

        self._build_toolbar()
        self._build_main_area()
        self._build_status_bar()

    def _build_toolbar(self) -> None:
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=50)
        toolbar.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(toolbar, text="Urunleri Cek", command=self._fetch_products,
                       fg_color=COLORS["accent"]).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Secilileri Analiz Et", command=self._analyze_selected,
                       fg_color=COLORS["bg_card"]).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="AI ile Yeniden Yaz", command=self._rewrite_selected,
                       fg_color=COLORS["bg_card"]).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(toolbar, text="Onayla ve Uygula", command=self._apply_approved,
                       fg_color=COLORS["success"]).pack(side="left", padx=5, pady=5)

        ctk.CTkSegmentedButton(
            toolbar, values=["Tumu", "Dusuk Skor", "Bekleyen", "Onayli"],
            variable=self._filter_var, command=self._on_filter_change,
        ).pack(side="right", padx=10, pady=5)

        ctk.CTkButton(toolbar, text="Ayarlar", width=80, command=self._open_settings,
                       fg_color=COLORS["border"]).pack(side="right", padx=5, pady=5)

    def _build_main_area(self) -> None:
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=5, pady=5)
        main.grid_columnconfigure(0, weight=2)
        main.grid_columnconfigure(1, weight=1)
        main.grid_columnconfigure(2, weight=2)
        main.grid_rowconfigure(0, weight=1)

        # Left panel - product list
        left = ctk.CTkFrame(main, fg_color=COLORS["bg_secondary"], corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

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
            fg_color=COLORS["bg_secondary"],
        )
        self._product_table.pack(fill="both", expand=True, padx=5, pady=5)

        # Middle panel - score card
        middle = ctk.CTkFrame(main, fg_color=COLORS["bg_secondary"], corner_radius=10)
        middle.grid(row=0, column=1, sticky="nsew", padx=5)

        self._product_info = ctk.CTkLabel(
            middle, text="Urun secin", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"], wraplength=250,
        )
        self._product_info.pack(padx=10, pady=10)

        self._score_card = ScoreCard(middle)
        self._score_card.pack(fill="x", padx=10, pady=5)

        # Right panel - diff viewer
        self._diff_viewer = DiffViewer(
            main, on_approve=self._on_approve, on_reject=self._on_reject,
        )
        self._diff_viewer.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

    def _build_status_bar(self) -> None:
        self._status_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=30)
        self._status_bar.pack(fill="x", padx=5, pady=(0, 5))

        self._status_label = ctk.CTkLabel(
            self._status_bar, text="Hazir",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
        )
        self._status_label.pack(side="left", padx=10)

        self._stats_label = ctk.CTkLabel(
            self._status_bar, text="",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
        )
        self._stats_label.pack(side="right", padx=10)

    def _set_status(self, text: str) -> None:
        self._status_label.configure(text=text)

    def _update_stats(self) -> None:
        total = len(self._products_data)
        analyzed = sum(1 for _, s in self._products_data if s)
        pending = len(db.get_pending_suggestions())
        self._stats_label.configure(text=f"Toplam: {total} | Analiz: {analyzed} | Bekleyen: {pending}")

    def _run_async(self, coro, callback=None) -> None:
        def runner():
            result = asyncio.run(coro)
            if callback:
                self.after(0, lambda: callback(result))
        threading.Thread(target=runner, daemon=True).start()

    def _fetch_products(self) -> None:
        self._set_status("Urunler cekiliyor...")

        def on_done(products):
            config = get_config()
            self._products_data = []
            for p in products:
                score = analyze_product(p, config.seo_target_keywords)
                db.save_score(score)
                self._products_data.append((p, score))
            self._product_table.set_products(self._products_data)
            self._update_stats()
            self._set_status(f"{len(products)} urun yuklendi")

        self._run_async(self._manager.fetch_products(), on_done)

    def _on_product_select(self, data: tuple[Product, SeoScore | None]) -> None:
        product, score = data
        self._selected_product = product
        self._selected_score = score

        self._product_info.configure(text=f"{product.name}\n\nKategori: {product.category or '-'}\nSKU: {product.sku or '-'}")

        if score:
            self._score_card.set_score(score)

        suggestions = db.get_suggestions_by_product(product.id)
        if suggestions:
            self._diff_viewer.show_suggestion(suggestions[0])
        else:
            self._diff_viewer.clear()

    def _analyze_selected(self) -> None:
        if not self._selected_product:
            return
        config = get_config()
        score = analyze_product(self._selected_product, config.seo_target_keywords)
        db.save_score(score)
        self._selected_score = score
        self._score_card.set_score(score)
        self._set_status(f"Analiz tamamlandi: {score.total_score}/100")

    def _rewrite_selected(self) -> None:
        if not self._selected_product or not self._selected_score:
            self._set_status("Once urun secin ve analiz edin")
            return
        config = get_config()
        self._set_status(f"AI ile yeniden yaziliyor ({config.ai_provider})...")

        def do_rewrite():
            suggestion = self._manager._ai.rewrite_product(
                self._selected_product, self._selected_score
            )
            db.save_suggestion(suggestion)
            return suggestion

        def on_done(suggestion):
            self._diff_viewer.show_suggestion(suggestion)
            usage = self._manager.get_token_usage()
            cost = usage.get("estimated_cost", 0)
            cost_str = f" | Maliyet: ${cost}" if cost else ""
            self._set_status(f"Rewrite tamamlandi{cost_str}")

        threading.Thread(target=lambda: self.after(0, lambda: on_done(do_rewrite())), daemon=True).start()

    def _apply_approved(self) -> None:
        suggestions = db.get_pending_suggestions()
        approved = [s for s in suggestions if s.status == "approved"]
        if not approved:
            self._set_status("Onaylanmis oneri yok")
            return

        self._set_status(f"{len(approved)} oneri uygulaniyor...")
        self._run_async(
            self._manager.apply_suggestions(approved),
            lambda count: self._set_status(f"{count} urun guncellendi"),
        )

    def _on_approve(self, suggestion: SeoSuggestion) -> None:
        self._manager.approve_suggestion(suggestion.product_id)
        self._set_status(f"Onaylandi: {suggestion.original_name}")
        self._update_stats()

    def _on_reject(self, suggestion: SeoSuggestion) -> None:
        self._manager.reject_suggestion(suggestion.product_id)
        self._set_status(f"Reddedildi: {suggestion.original_name}")
        self._diff_viewer.clear()

    def _on_search(self, event=None) -> None:
        query = self._search_entry.get()
        if query:
            self._product_table.filter_products(query)
        else:
            self._product_table.set_products(self._products_data)

    def _on_filter_change(self, value: str) -> None:
        if value == "Tumu":
            self._product_table.set_products(self._products_data)
        elif value == "Dusuk Skor":
            filtered = [(p, s) for p, s in self._products_data if s and s.total_score < 70]
            self._product_table.set_products(filtered)
        elif value == "Bekleyen":
            pending_ids = {s.product_id for s in db.get_pending_suggestions()}
            filtered = [(p, s) for p, s in self._products_data if p.id in pending_ids]
            self._product_table.set_products(filtered)

    def _open_settings(self) -> None:
        config = get_config()
        SettingsPanel(self, config, on_save=self._on_settings_save)

    def _on_settings_save(self, values: dict) -> None:
        from config.settings import save_config_to_env
        save_config_to_env(values)
        # Reload AI client with new config
        self._manager.reload_ai_client()
        config = get_config()
        self._set_status(f"Ayarlar kaydedildi | AI: {config.ai_provider}")


def launch() -> None:
    app = App()
    app.mainloop()
