import io
import threading
from typing import Optional

import customtkinter as ctk

from core.models import Product, SeoScore
from ui.themes.dark import COLORS, score_color

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class ProductTable(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._rows: list = []
        self._products: list[tuple[Product, SeoScore | None]] = []
        self._image_cache: dict[str, Optional[ctk.CTkImage]] = {}

        self._header_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"])
        self._header_frame.pack(fill="x", padx=2, pady=(0, 5))

        ctk.CTkLabel(self._header_frame, text="Gorsel", width=50, anchor="center").pack(side="left", padx=4)
        ctk.CTkLabel(self._header_frame, text="Urun Adi", width=220, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(self._header_frame, text="Skor", width=50, anchor="center").pack(side="left", padx=4)

        self._count_label = ctk.CTkLabel(
            self._header_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        )
        self._count_label.pack(side="right", padx=8)

    def set_products(
        self,
        products: list[tuple[Product, SeoScore | None]],
        total_count: int = 0,
    ) -> None:
        self._products = products
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        listed = len(products)
        if total_count > 0:
            self._count_label.configure(text=f"{listed} / {total_count} urun")
        else:
            self._count_label.configure(text=f"{listed} urun")

        for i, (product, score) in enumerate(products):
            row = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=5)
            row.pack(fill="x", padx=2, pady=1)

            # Image thumbnail slot
            img_label = ctk.CTkLabel(row, text="", width=48, height=48)
            img_label.pack(side="left", padx=4, pady=3)
            self._load_thumbnail(product.image_url, img_label)

            # Name + description column
            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="both", expand=True, padx=4, pady=3)

            name_label = ctk.CTkLabel(
                text_frame,
                text=product.name[:45],
                anchor="w",
                text_color=COLORS["text_primary"],
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            name_label.pack(fill="x")

            desc_text = self._get_description_snippet(product)
            if desc_text:
                desc_label = ctk.CTkLabel(
                    text_frame,
                    text=desc_text,
                    anchor="w",
                    text_color=COLORS["text_secondary"],
                    font=ctk.CTkFont(size=10),
                    wraplength=210,
                )
                desc_label.pack(fill="x")
                desc_label.bind("<Button-1>", lambda e, idx=i: self._on_click(idx))

            # Score column
            score_val = score.total_score if score else "-"
            color = score_color(score.total_score) if score else COLORS["text_secondary"]
            ctk.CTkLabel(
                row, text=str(score_val), width=50, anchor="center",
                text_color=color,
                font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(side="right", padx=8)

            row.bind("<Button-1>", lambda e, idx=i: self._on_click(idx))
            name_label.bind("<Button-1>", lambda e, idx=i: self._on_click(idx))
            self._rows.append(row)

    def _get_description_snippet(self, product: Product) -> str:
        desc = product.description or ""
        if not desc:
            # Try translations
            for locale in ("tr", "en"):
                desc = product.description_translations.get(locale, "")
                if desc:
                    break
        if not desc:
            return ""
        # Strip HTML-like tags if any
        import re
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = " ".join(desc.split())
        return desc[:80] + "..." if len(desc) > 80 else desc

    def _load_thumbnail(self, url: Optional[str], label: ctk.CTkLabel) -> None:
        if not _PIL_AVAILABLE or not url:
            label.configure(text="—", text_color=COLORS["text_secondary"])
            return

        if url in self._image_cache:
            cached = self._image_cache[url]
            if cached:
                label.configure(image=cached, text="")
            else:
                label.configure(text="—", text_color=COLORS["text_secondary"])
            return

        # Placeholder while loading
        label.configure(text="...", text_color=COLORS["text_secondary"])

        def fetch():
            try:
                import httpx
                response = httpx.get(url, timeout=10, follow_redirects=True)
                response.raise_for_status()
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
                img.thumbnail((48, 48), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(48, 48))
                self._image_cache[url] = ctk_img
                try:
                    label.after(0, lambda: label.configure(image=ctk_img, text=""))
                except Exception:
                    pass
            except Exception:
                self._image_cache[url] = None
                try:
                    label.after(0, lambda: label.configure(text="—", text_color=COLORS["text_secondary"]))
                except Exception:
                    pass

        threading.Thread(target=fetch, daemon=True).start()

    def _on_click(self, index: int) -> None:
        if self._on_select and index < len(self._products):
            self._on_select(self._products[index])

    def filter_products(self, query: str, total_count: int = 0) -> None:
        query = query.lower()
        filtered = [
            (p, s) for p, s in self._products
            if query in p.name.lower() or query in (p.category or "").lower()
        ]
        self.set_products(filtered, total_count)
