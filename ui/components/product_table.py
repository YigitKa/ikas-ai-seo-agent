import customtkinter as ctk

from core.models import Product, SeoScore
from ui.themes.dark import COLORS, score_color


class ProductTable(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._rows: list = []
        self._products: list[tuple[Product, SeoScore | None]] = []

        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"])
        header.pack(fill="x", padx=2, pady=(0, 5))
        ctk.CTkLabel(header, text="Urun Adi", width=250, anchor="w").pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Skor", width=60, anchor="center").pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Durum", width=80, anchor="center").pack(side="left", padx=5)

    def set_products(self, products: list[tuple[Product, SeoScore | None]]) -> None:
        self._products = products
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        for i, (product, score) in enumerate(products):
            row = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=5)
            row.pack(fill="x", padx=2, pady=1)

            name_label = ctk.CTkLabel(
                row, text=product.name[:40], width=250, anchor="w",
                text_color=COLORS["text_primary"],
            )
            name_label.pack(side="left", padx=5, pady=3)

            score_val = score.total_score if score else "-"
            color = score_color(score.total_score) if score else COLORS["text_secondary"]
            ctk.CTkLabel(
                row, text=str(score_val), width=60, anchor="center",
                text_color=color,
            ).pack(side="left", padx=5)

            status = product.status
            ctk.CTkLabel(
                row, text=status, width=80, anchor="center",
                text_color=COLORS["text_secondary"],
            ).pack(side="left", padx=5)

            row.bind("<Button-1>", lambda e, idx=i: self._on_click(idx))
            name_label.bind("<Button-1>", lambda e, idx=i: self._on_click(idx))
            self._rows.append(row)

    def _on_click(self, index: int) -> None:
        if self._on_select and index < len(self._products):
            self._on_select(self._products[index])

    def filter_products(self, query: str) -> None:
        query = query.lower()
        filtered = [
            (p, s) for p, s in self._products
            if query in p.name.lower() or query in (p.category or "").lower()
        ]
        self.set_products(filtered)
