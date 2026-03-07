import io
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

import customtkinter as ctk

from core.models import Product, SeoScore
from ui.themes.dark import COLORS, score_color

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# Shared thread pool for image loading (limit concurrent downloads)
_image_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="img")

# Shared font instances (avoid recreating per-row)
_font_name: ctk.CTkFont | None = None
_font_cat: ctk.CTkFont | None = None
_font_score: ctk.CTkFont | None = None


def _get_fonts() -> tuple[ctk.CTkFont, ctk.CTkFont, ctk.CTkFont]:
    global _font_name, _font_cat, _font_score
    if _font_name is None:
        _font_name = ctk.CTkFont(size=14, weight="bold")
        _font_cat = ctk.CTkFont(size=12)
        _font_score = ctk.CTkFont(size=15, weight="bold")
    return _font_name, _font_cat, _font_score


@dataclass
class _PooledRow:
    """Pre-allocated row widgets that can be reused."""
    frame: ctk.CTkFrame
    img_label: ctk.CTkLabel
    text_frame: ctk.CTkFrame
    name_label: ctk.CTkLabel
    cat_label: ctk.CTkLabel
    score_label: ctk.CTkLabel
    visible: bool = True


class ProductTable(ctk.CTkScrollableFrame):
    def __init__(self, master, on_select=None, on_page_change: Optional[Callable[[int], None]] = None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._on_page_change = on_page_change
        self._pool: list[_PooledRow] = []
        self._products: list[tuple[Product, SeoScore | None]] = []
        self._all_products: list[tuple[Product, SeoScore | None]] = []
        self._image_cache: dict[str, Optional[ctk.CTkImage]] = {}
        self._current_page: int = 1
        self._total_pages: int = 1

        self._header_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"])
        self._header_frame.pack(fill="x", padx=2, pady=(0, 5))

        ctk.CTkLabel(self._header_frame, text="Gorsel", width=50, anchor="center").pack(side="left", padx=4)
        ctk.CTkLabel(self._header_frame, text="Urun Adi", width=220, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(self._header_frame, text="Skor", width=50, anchor="center").pack(side="left", padx=4)

        self._count_label = ctk.CTkLabel(
            self._header_frame, text="",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"],
        )
        self._count_label.pack(side="right", padx=8)

        # Pagination controls
        self._pagination_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=5)
        self._pagination_frame.pack(fill="x", padx=2, pady=(0, 5))

        self._prev_btn = ctk.CTkButton(
            self._pagination_frame, text="< Onceki", width=80, height=28,
            font=ctk.CTkFont(size=12), fg_color=COLORS["bg_card"],
            command=self._go_prev_page, state="disabled",
        )
        self._prev_btn.pack(side="left", padx=5, pady=4)

        self._page_label = ctk.CTkLabel(
            self._pagination_frame, text="Sayfa 1/1",
            font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"],
        )
        self._page_label.pack(side="left", expand=True, padx=5, pady=4)

        self._next_btn = ctk.CTkButton(
            self._pagination_frame, text="Sonraki >", width=80, height=28,
            font=ctk.CTkFont(size=12), fg_color=COLORS["bg_card"],
            command=self._go_next_page, state="disabled",
        )
        self._next_btn.pack(side="right", padx=5, pady=4)

    def _ensure_pool(self, count: int) -> None:
        """Ensure we have at least `count` pooled row widgets."""
        font_name, font_cat, font_score = _get_fonts()
        while len(self._pool) < count:
            idx = len(self._pool)
            row = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=5)

            img_label = ctk.CTkLabel(row, text="", width=48, height=48)
            img_label.pack(side="left", padx=4, pady=3)

            text_frame = ctk.CTkFrame(row, fg_color="transparent")
            text_frame.pack(side="left", fill="both", expand=True, padx=4, pady=3)

            name_label = ctk.CTkLabel(
                text_frame, text="", anchor="w",
                text_color=COLORS["text_primary"], font=font_name,
            )
            name_label.pack(fill="x")

            cat_label = ctk.CTkLabel(
                text_frame, text="", anchor="w",
                text_color=COLORS["text_secondary"], font=font_cat,
            )
            # cat_label is packed/unpacked dynamically

            score_label = ctk.CTkLabel(
                row, text="-", width=50, anchor="center",
                text_color=COLORS["text_secondary"], font=font_score,
            )
            score_label.pack(side="right", padx=8)

            pooled = _PooledRow(
                frame=row, img_label=img_label, text_frame=text_frame,
                name_label=name_label, cat_label=cat_label,
                score_label=score_label, visible=False,
            )
            self._pool.append(pooled)

            # Bind clicks (use default-arg capture to avoid late-binding)
            for widget in (row, name_label, cat_label):
                widget.bind("<Button-1>", lambda e, i=idx: self._on_click(i))

    def set_products(
        self,
        products: list[tuple[Product, SeoScore | None]],
        total_count: int = 0,
        current_page: int = 1,
        page_size: int = 50,
    ) -> None:
        self._products = products
        self._all_products = products
        self._current_page = current_page
        needed = len(products)

        listed = needed
        if total_count > 0:
            self._count_label.configure(text=f"{listed} / {total_count} urun")
            self._total_pages = max(1, (total_count + page_size - 1) // page_size)
        else:
            self._count_label.configure(text=f"{listed} urun")
            self._total_pages = 1

        # Update pagination controls
        self._page_label.configure(text=f"Sayfa {self._current_page}/{self._total_pages}")
        self._prev_btn.configure(state="normal" if self._current_page > 1 else "disabled")
        self._next_btn.configure(state="normal" if self._current_page < self._total_pages else "disabled")

        # Ensure enough pooled widgets exist
        self._ensure_pool(needed)

        # Update existing rows and show/hide as needed
        for i in range(len(self._pool)):
            pooled = self._pool[i]
            if i < needed:
                product, score = products[i]
                self._update_row(pooled, product, score)
                if not pooled.visible:
                    pooled.frame.pack(fill="x", padx=2, pady=1)
                    pooled.visible = True
            else:
                if pooled.visible:
                    pooled.frame.pack_forget()
                    pooled.visible = False

    def _update_row(self, pooled: _PooledRow, product: Product, score: SeoScore | None) -> None:
        """Update a pooled row's displayed data without destroying widgets."""
        pooled.name_label.configure(text=product.name[:45])

        if product.category:
            pooled.cat_label.configure(text=product.category)
            if not pooled.cat_label.winfo_manager():
                pooled.cat_label.pack(fill="x")
        else:
            if pooled.cat_label.winfo_manager():
                pooled.cat_label.pack_forget()

        score_val = score.total_score if score else "-"
        color = score_color(score.total_score) if score else COLORS["text_secondary"]
        pooled.score_label.configure(text=str(score_val), text_color=color)

        # Load thumbnail (uses cache, non-blocking)
        self._load_thumbnail(product.image_url, pooled.img_label)

    def _load_thumbnail(self, url: Optional[str], label: ctk.CTkLabel) -> None:
        if not _PIL_AVAILABLE or not url:
            label.configure(text="—", image=None, text_color=COLORS["text_secondary"])
            return

        if url in self._image_cache:
            cached = self._image_cache[url]
            if cached:
                label.configure(image=cached, text="")
            else:
                label.configure(text="—", image=None, text_color=COLORS["text_secondary"])
            return

        # Placeholder while loading
        label.configure(text="...", image=None, text_color=COLORS["text_secondary"])

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

        _image_executor.submit(fetch)

    def _on_click(self, index: int) -> None:
        if self._on_select and index < len(self._products):
            self._on_select(self._products[index])

    def _go_prev_page(self) -> None:
        if self._current_page > 1 and self._on_page_change:
            self._on_page_change(self._current_page - 1)

    def _go_next_page(self) -> None:
        if self._current_page < self._total_pages and self._on_page_change:
            self._on_page_change(self._current_page + 1)

    def filter_products(self, query: str, total_count: int = 0) -> None:
        query = query.lower()
        filtered = [
            (p, s) for p, s in self._all_products
            if query in p.name.lower() or query in (p.category or "").lower()
        ]
        self._products = filtered
        needed = len(filtered)

        # Update count
        if total_count > 0:
            self._count_label.configure(text=f"{needed} / {total_count} urun")
        else:
            self._count_label.configure(text=f"{needed} urun")

        # Reuse pooled rows
        self._ensure_pool(needed)
        for i in range(len(self._pool)):
            pooled = self._pool[i]
            if i < needed:
                product, score = filtered[i]
                self._update_row(pooled, product, score)
                if not pooled.visible:
                    pooled.frame.pack(fill="x", padx=2, pady=1)
                    pooled.visible = True
            else:
                if pooled.visible:
                    pooled.frame.pack_forget()
                    pooled.visible = False
