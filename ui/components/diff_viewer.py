import re

import customtkinter as ctk

from core.models import Product, SeoScore, SeoSuggestion
from ui.themes.dark import COLORS, score_color


def _strip_html(text: str) -> str:
    """Remove HTML tags and clean up whitespace."""
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_description_display(description: str, translations: dict[str, str] | None = None) -> str:
    if translations:
        tr_desc = translations.get("tr", "")
        if tr_desc and tr_desc.strip():
            return _strip_html(tr_desc)
    if description and description.strip():
        return _strip_html(description)
    return "(Aciklama yok)"


def _get_en_description_display(translations: dict[str, str] | None = None) -> str:
    if translations:
        en_desc = translations.get("en", "")
        if en_desc and en_desc.strip():
            return _strip_html(en_desc)
    return ""


class _CollapsibleField(ctk.CTkFrame):
    """A collapsible section containing original/suggested textboxes for a single field."""

    def __init__(self, master, key: str, label_text: str, line_count: int,
                 start_open: bool = False, on_field_rewrite=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._key = key
        self._expanded = start_open
        self._on_field_rewrite = on_field_rewrite

        # Header row
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=6, height=36)
        header.pack(fill="x", pady=(6, 0))
        header.pack_propagate(False)

        self._toggle_btn = ctk.CTkButton(
            header, text="▾" if start_open else "▸", width=28, height=28,
            fg_color="transparent", hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=14),
            corner_radius=4, command=self.toggle,
        )
        self._toggle_btn.pack(side="left", padx=(4, 0), pady=3)

        self._label = ctk.CTkLabel(
            header, text=label_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"], anchor="w",
        )
        self._label.pack(side="left", padx=6, pady=3)
        self._label.bind("<Button-1>", lambda e: self.toggle())
        header.bind("<Button-1>", lambda e: self.toggle())

        self.ai_btn = ctk.CTkButton(
            header, text="AI ile olustur", width=110, height=26,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["accent"], hover_color=COLORS["bg_card"],
            command=self._request_rewrite,
        )
        self.ai_btn.pack(side="right", padx=6, pady=4)

        # Content frame (collapsible)
        self._content = ctk.CTkFrame(self, fg_color="transparent")

        # Sub-header: Orijinal | Oneri
        sub_header = ctk.CTkFrame(self._content, fg_color="transparent")
        sub_header.pack(fill="x", padx=5, pady=(4, 0))
        sub_header.grid_columnconfigure(0, weight=1)
        sub_header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            sub_header, text="Orijinal",
            font=ctk.CTkFont(size=12), text_color=COLORS["error"], anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 2))
        ctk.CTkLabel(
            sub_header, text="Oneri",
            font=ctk.CTkFont(size=12), text_color=COLORS["success"], anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))

        # Textboxes
        tb_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        tb_frame.pack(fill="both", expand=True, padx=2, pady=(2, 0))
        tb_frame.grid_columnconfigure(0, weight=1)
        tb_frame.grid_columnconfigure(1, weight=1)

        h = max(40, line_count * 26)

        self.orig_tb = ctk.CTkTextbox(
            tb_frame, fg_color=COLORS["input_bg"],
            text_color=COLORS["text_secondary"], height=h,
            font=ctk.CTkFont(size=14), wrap="word",
        )
        self.orig_tb.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=2)

        self.sugg_tb = ctk.CTkTextbox(
            tb_frame, fg_color=COLORS["input_bg"],
            text_color=COLORS["text_primary"], height=h,
            font=ctk.CTkFont(size=14), wrap="word",
        )
        self.sugg_tb.grid(row=0, column=1, sticky="nsew", padx=(3, 0), pady=2)

        if line_count >= 4:
            tb_frame.grid_rowconfigure(0, weight=1)

        if start_open:
            self._content.pack(fill="both", expand=True)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._content.pack(fill="both", expand=True)
            self._toggle_btn.configure(text="▾")
        else:
            self._content.pack_forget()
            self._toggle_btn.configure(text="▸")

    def expand(self) -> None:
        if not self._expanded:
            self.toggle()

    def collapse(self) -> None:
        if self._expanded:
            self.toggle()

    def _request_rewrite(self) -> None:
        if self._on_field_rewrite:
            self.ai_btn.configure(state="disabled", text="Yaziliyor...")
            self._on_field_rewrite(self._key)


class DiffViewer(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_approve=None,
        on_reject=None,
        on_field_rewrite=None,
        on_product_rewrite=None,
        on_translate_en=None,
        **kwargs,
    ):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self._on_approve = on_approve
        self._on_reject = on_reject
        self._on_field_rewrite = on_field_rewrite
        self._on_product_rewrite = on_product_rewrite
        self._on_translate_en = on_translate_en
        self._current_suggestion: SeoSuggestion | None = None

        # ── Product Summary Header ──
        self._build_product_header()

        # ── Scrollable content area for diff fields ──
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Field definitions: (key, label, line_count, start_open)
        field_defs = [
            ("name", "Ad", 2, False),
            ("meta_title", "Meta Title", 2, False),
            ("meta_desc", "Meta Description", 3, False),
            ("desc_tr", "Aciklama (TR)", 8, True),
            ("desc_en", "Aciklama (EN)", 6, False),
        ]

        self._sections: dict[str, _CollapsibleField] = {}
        self._fields_orig: dict[str, ctk.CTkTextbox] = {}
        self._fields_sugg: dict[str, ctk.CTkTextbox] = {}
        self._field_buttons: dict[str, ctk.CTkButton] = {}

        for key, label_text, line_count, start_open in field_defs:
            section = _CollapsibleField(
                scroll, key=key, label_text=label_text,
                line_count=line_count, start_open=start_open,
                on_field_rewrite=on_field_rewrite,
            )
            section.pack(fill="x")
            self._sections[key] = section
            self._fields_orig[key] = section.orig_tb
            self._fields_sugg[key] = section.sugg_tb
            self._field_buttons[key] = section.ai_btn

        # ── Bottom buttons ──
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkButton(
            btn_frame, text="Onayla", fg_color=COLORS["success"],
            hover_color="#00a844", command=self._approve,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Reddet", fg_color=COLORS["error"],
            hover_color="#d50000", command=self._reject,
        ).pack(side="left", padx=5)

    def _build_product_header(self) -> None:
        """Product info row + prominent SEO score card."""
        self._header_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=8)
        self._header_frame.pack(fill="x", padx=5, pady=5)

        # ── Row 1: [Image] [Product Name + Category + Gallery] ──
        product_row = ctk.CTkFrame(self._header_frame, fg_color="transparent")
        product_row.pack(fill="x", padx=10, pady=(10, 5))

        img_frame = ctk.CTkFrame(product_row, fg_color=COLORS["bg_card"], corner_radius=8,
                                  width=80, height=80)
        img_frame.pack(side="left", padx=(0, 12))
        img_frame.pack_propagate(False)

        self.product_image_label = ctk.CTkLabel(img_frame, text="Gorsel\nyok",
                                                 text_color=COLORS["text_secondary"],
                                                 font=ctk.CTkFont(size=11))
        self.product_image_label.pack(expand=True)

        info_frame = ctk.CTkFrame(product_row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)

        self._product_name_label = ctk.CTkLabel(
            info_frame, text="Urun secin",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text_primary"], anchor="w",
            wraplength=500,
        )
        self._product_name_label.pack(fill="x", pady=(0, 2))

        self._product_detail_label = ctk.CTkLabel(
            info_frame, text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"], anchor="w",
        )
        self._product_detail_label.pack(fill="x")

        self.gallery_frame = ctk.CTkFrame(info_frame, fg_color="transparent", height=44)
        self.gallery_frame.pack(fill="x", pady=(4, 0))

        action_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        action_row.pack(fill="x", pady=(8, 0))

        self._rewrite_product_btn = ctk.CTkButton(
            action_row,
            text="AI ile yeniden yaz",
            height=30,
            fg_color=COLORS["accent"],
            hover_color=COLORS["bg_card"],
            command=self._request_product_rewrite,
            state="disabled",
        )
        self._rewrite_product_btn.pack(side="left", padx=(0, 8))

        self._translate_en_btn = ctk.CTkButton(
            action_row,
            text="AI ile ceviri",
            height=30,
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["border"],
            command=self._request_translate_en,
            state="disabled",
        )
        self._translate_en_btn.pack(side="left")

        # ── Row 2: Full-width SEO Score Card ──
        score_card = ctk.CTkFrame(self._header_frame, fg_color=COLORS["bg_card"], corner_radius=8)
        score_card.pack(fill="x", padx=10, pady=(5, 10))

        score_inner = ctk.CTkFrame(score_card, fg_color="transparent")
        score_inner.pack(fill="x", padx=12, pady=10)

        # Left: big score number
        score_left = ctk.CTkFrame(score_inner, fg_color="transparent")
        score_left.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(
            score_left, text="SEO Skoru",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_secondary"],
        ).pack()

        self._score_total_label = ctk.CTkLabel(
            score_left, text="-",
            font=ctk.CTkFont(size=42, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        self._score_total_label.pack()

        # Center: breakdown bars
        bars_frame = ctk.CTkFrame(score_inner, fg_color="transparent")
        bars_frame.pack(side="left", fill="both", expand=True, padx=(0, 15))

        self._score_bars: dict[str, tuple[ctk.CTkLabel, ctk.CTkProgressBar]] = {}
        categories = [
            ("Baslik", 25), ("Aciklama", 30), ("Meta Title", 20),
            ("Meta Desc", 15), ("Keyword", 10),
        ]
        for name, max_val in categories:
            bar_row = ctk.CTkFrame(bars_frame, fg_color="transparent")
            bar_row.pack(fill="x", pady=2)

            label = ctk.CTkLabel(
                bar_row, text=f"{name}: -/{max_val}",
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text_secondary"], anchor="w", width=150,
            )
            label.pack(side="left")

            bar = ctk.CTkProgressBar(bar_row, height=12, corner_radius=5)
            bar.pack(side="left", fill="x", expand=True, padx=(5, 0))
            bar.set(0)

            self._score_bars[name] = (label, bar)

        # Right: issues list
        issues_frame = ctk.CTkFrame(score_inner, fg_color="transparent", width=280)
        issues_frame.pack(side="right", fill="y")
        issues_frame.pack_propagate(False)

        ctk.CTkLabel(
            issues_frame, text="Sorunlar",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_secondary"], anchor="w",
        ).pack(fill="x")

        self._issues_label = ctk.CTkLabel(
            issues_frame, text="", wraplength=270, justify="left",
            text_color=COLORS["warning"], font=ctk.CTkFont(size=12),
            anchor="nw",
        )
        self._issues_label.pack(fill="both", expand=True, pady=(2, 0))

    # ── Public API: Product Info ──

    def set_product_info(self, product: Product) -> None:
        self._product_name_label.configure(text=product.name)
        parts = []
        if product.category:
            parts.append(f"Kategori: {product.category}")
        if product.sku:
            parts.append(f"SKU: {product.sku}")
        self._product_detail_label.configure(text="  |  ".join(parts) if parts else "")

    def set_score(self, score: SeoScore) -> None:
        color = score_color(score.total_score)
        self._score_total_label.configure(text=str(score.total_score), text_color=color)

        values = {
            "Baslik": (score.title_score, 25),
            "Aciklama": (score.description_score, 30),
            "Meta Title": (score.meta_score, 20),
            "Meta Desc": (score.meta_desc_score, 15),
            "Keyword": (score.keyword_score, 10),
        }
        for name, (val, max_val) in values.items():
            label, bar = self._score_bars[name]
            label.configure(text=f"{name}: {val}/{max_val}")
            bar.set(val / max_val if max_val else 0)
            bar.configure(progress_color=score_color(int(val / max_val * 100)))

        if score.issues:
            self._issues_label.configure(text="\n".join(f"- {i}" for i in score.issues[:5]))
        else:
            self._issues_label.configure(text="Sorun yok")

    def clear_score(self) -> None:
        self._score_total_label.configure(text="-", text_color=COLORS["text_secondary"])
        for name, (label, bar) in self._score_bars.items():
            label.configure(text=f"{name}: -")
            bar.set(0)
        self._issues_label.configure(text="")

    # ── Public API: Diff Fields ──

    def set_field_loading_done(self, field: str) -> None:
        btn = self._field_buttons.get(field)
        if btn:
            btn.configure(state="normal", text="AI ile olustur")

    def set_product_action_loading_done(self, action: str) -> None:
        if action == "rewrite":
            self._rewrite_product_btn.configure(state="normal", text="AI ile yeniden yaz")
        elif action == "translate":
            self._translate_en_btn.configure(state="normal", text="AI ile ceviri")

    def set_ai_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._rewrite_product_btn.configure(state=state)
        self._translate_en_btn.configure(state=state)
        for btn in self._field_buttons.values():
            btn.configure(state=state)

    def set_field_value(self, field: str, value: str) -> None:
        self._set_field(self._fields_sugg, field, value)
        section = self._sections.get(field)
        if section:
            section.expand()

    def _set_field(self, fields: dict[str, ctk.CTkTextbox], key: str, value: str) -> None:
        tb = fields.get(key)
        if tb:
            tb.delete("1.0", "end")
            tb.insert("1.0", value)

    def _clear_fields(self, fields: dict[str, ctk.CTkTextbox]) -> None:
        for tb in fields.values():
            tb.delete("1.0", "end")

    def show_product_preview(self, product: Product) -> None:
        self.set_product_info(product)
        desc_tr = _get_description_display(product.description, product.description_translations)
        desc_en = _get_en_description_display(product.description_translations)
        self._rewrite_product_btn.configure(state="normal", text="AI ile yeniden yaz")
        self._translate_en_btn.configure(state="normal", text="AI ile ceviri")

        self._set_field(self._fields_orig, "name", product.name)
        self._set_field(self._fields_orig, "meta_title", product.meta_title or "-")
        self._set_field(self._fields_orig, "meta_desc", product.meta_description or "-")
        self._set_field(self._fields_orig, "desc_tr", desc_tr)
        self._set_field(self._fields_orig, "desc_en", desc_en or "-")

        self._clear_fields(self._fields_sugg)
        self._set_field(self._fields_sugg, "name", "AI ile yeniden yazma icin butonu kullanin")
        self._current_suggestion = None

    def show_suggestion(self, suggestion: SeoSuggestion) -> None:
        self._current_suggestion = suggestion

        orig_desc = _strip_html(suggestion.original_description) if suggestion.original_description else "(Aciklama yok)"
        orig_desc_en = _strip_html(suggestion.original_description_en) if suggestion.original_description_en else "-"
        sugg_desc = _strip_html(suggestion.suggested_description) if suggestion.suggested_description else "-"
        sugg_desc_en = _strip_html(suggestion.suggested_description_en) if suggestion.suggested_description_en else "-"

        self._set_field(self._fields_orig, "name", suggestion.original_name)
        self._set_field(self._fields_orig, "meta_title", suggestion.original_meta_title or "-")
        self._set_field(self._fields_orig, "meta_desc", suggestion.original_meta_description or "-")
        self._set_field(self._fields_orig, "desc_tr", orig_desc)
        self._set_field(self._fields_orig, "desc_en", orig_desc_en)

        self._set_field(self._fields_sugg, "name", suggestion.suggested_name or "-")
        self._set_field(self._fields_sugg, "meta_title", suggestion.suggested_meta_title or "-")
        self._set_field(self._fields_sugg, "meta_desc", suggestion.suggested_meta_description or "-")
        self._set_field(self._fields_sugg, "desc_tr", sugg_desc)
        self._set_field(self._fields_sugg, "desc_en", sugg_desc_en)

        for key, section in self._sections.items():
            section.expand()

    def get_edited_suggestion(self) -> str:
        return self._fields_sugg.get("desc_tr", ctk.CTkTextbox(self)).get("1.0", "end").strip()

    def _approve(self) -> None:
        if self._on_approve and self._current_suggestion:
            self._on_approve(self._current_suggestion)

    def _reject(self) -> None:
        if self._on_reject and self._current_suggestion:
            self._on_reject(self._current_suggestion)

    def _request_product_rewrite(self) -> None:
        if self._on_product_rewrite:
            self._rewrite_product_btn.configure(state="disabled", text="Yaziliyor...")
            self._on_product_rewrite()

    def _request_translate_en(self) -> None:
        if self._on_translate_en:
            self._translate_en_btn.configure(state="disabled", text="Ceviriliyor...")
            self._on_translate_en()

    def clear(self) -> None:
        self._current_suggestion = None
        self._clear_fields(self._fields_orig)
        self._clear_fields(self._fields_sugg)
        self.clear_score()
        self._product_name_label.configure(text="Urun secin")
        self._product_detail_label.configure(text="")
        self.product_image_label.configure(image=None, text="Gorsel\nyok")
        self._rewrite_product_btn.configure(state="disabled", text="AI ile yeniden yaz")
        self._translate_en_btn.configure(state="disabled", text="AI ile ceviri")
