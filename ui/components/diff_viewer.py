import re

import customtkinter as ctk

from core.models import Product, SeoSuggestion
from ui.themes.dark import COLORS


def _strip_html(text: str) -> str:
    """Remove HTML tags and clean up whitespace."""
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_description_display(description: str, translations: dict[str, str] | None = None) -> str:
    """Get the best description text available: try TR translation first, then raw description."""
    # Try TR translation first
    if translations:
        tr_desc = translations.get("tr", "")
        if tr_desc and tr_desc.strip():
            return _strip_html(tr_desc)
    # Fallback to main description
    if description and description.strip():
        return _strip_html(description)
    return "(Aciklama yok)"


def _get_en_description_display(translations: dict[str, str] | None = None) -> str:
    """Get English description if available."""
    if translations:
        en_desc = translations.get("en", "")
        if en_desc and en_desc.strip():
            return _strip_html(en_desc)
    return ""


class DiffViewer(ctk.CTkFrame):
    def __init__(self, master, on_approve=None, on_reject=None, on_field_rewrite=None, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self._on_approve = on_approve
        self._on_reject = on_reject
        self._on_field_rewrite = on_field_rewrite
        self._current_suggestion: SeoSuggestion | None = None

        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(
            title_frame, text="Oneri Karsilastirmasi",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        # Scrollable content area
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=5)
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        # --- Row builders ---
        self._fields_orig: dict[str, ctk.CTkTextbox] = {}
        self._fields_sugg: dict[str, ctk.CTkTextbox] = {}
        self._field_buttons: dict[str, ctk.CTkButton] = {}
        row_idx = 0

        field_defs = [
            ("name", "Ad", 1),
            ("meta_title", "Meta Title", 1),
            ("meta_desc", "Meta Description", 2),
            ("desc_tr", "Aciklama (TR)", 6),
            ("desc_en", "Aciklama (EN)", 4),
        ]

        for key, label_text, line_count in field_defs:
            # Label row with AI button
            label_row = ctk.CTkFrame(scroll, fg_color="transparent")
            label_row.grid(row=row_idx, column=0, columnspan=2, sticky="ew", padx=5, pady=(8, 2))
            ctk.CTkLabel(
                label_row, text=label_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLORS["text_secondary"], anchor="w",
            ).pack(side="left")

            ai_btn = ctk.CTkButton(
                label_row, text="AI ile olustur", width=100, height=22,
                font=ctk.CTkFont(size=10),
                fg_color=COLORS["accent"],
                hover_color=COLORS["bg_card"],
                command=lambda f=key: self._request_field_rewrite(f),
            )
            ai_btn.pack(side="right", padx=(10, 0))
            self._field_buttons[key] = ai_btn
            row_idx += 1

            # Sub-header: Orijinal | Oneri
            ctk.CTkLabel(
                scroll, text="Orijinal",
                font=ctk.CTkFont(size=10), text_color=COLORS["error"], anchor="w",
            ).grid(row=row_idx, column=0, sticky="w", padx=(5, 2))
            ctk.CTkLabel(
                scroll, text="Oneri",
                font=ctk.CTkFont(size=10), text_color=COLORS["success"], anchor="w",
            ).grid(row=row_idx, column=1, sticky="w", padx=(5, 2))
            row_idx += 1

            h = max(28, line_count * 22)

            orig_tb = ctk.CTkTextbox(
                scroll, fg_color=COLORS["input_bg"],
                text_color=COLORS["text_secondary"], height=h,
                font=ctk.CTkFont(size=12),
                wrap="word",
            )
            orig_tb.grid(row=row_idx, column=0, sticky="nsew", padx=(5, 3), pady=2)

            sugg_tb = ctk.CTkTextbox(
                scroll, fg_color=COLORS["input_bg"],
                text_color=COLORS["text_primary"], height=h,
                font=ctk.CTkFont(size=12),
                wrap="word",
            )
            sugg_tb.grid(row=row_idx, column=1, sticky="nsew", padx=(3, 5), pady=2)

            scroll.grid_rowconfigure(row_idx, weight=1 if line_count >= 4 else 0)
            self._fields_orig[key] = orig_tb
            self._fields_sugg[key] = sugg_tb
            row_idx += 1

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            btn_frame, text="Onayla", fg_color=COLORS["success"],
            hover_color="#00a844", command=self._approve,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Reddet", fg_color=COLORS["error"],
            hover_color="#d50000", command=self._reject,
        ).pack(side="left", padx=5)

    def _request_field_rewrite(self, field: str) -> None:
        """Called when user clicks per-field AI button."""
        if self._on_field_rewrite:
            # Disable button while processing
            btn = self._field_buttons.get(field)
            if btn:
                btn.configure(state="disabled", text="Yaziliyor...")
            self._on_field_rewrite(field)

    def set_field_loading_done(self, field: str) -> None:
        """Re-enable the AI button after rewrite completes."""
        btn = self._field_buttons.get(field)
        if btn:
            btn.configure(state="normal", text="AI ile olustur")

    def set_field_value(self, field: str, value: str) -> None:
        """Set a single suggested field value from outside."""
        self._set_field(self._fields_sugg, field, value)

    def _set_field(self, fields: dict[str, ctk.CTkTextbox], key: str, value: str) -> None:
        tb = fields.get(key)
        if tb:
            tb.delete("1.0", "end")
            tb.insert("1.0", value)

    def _clear_fields(self, fields: dict[str, ctk.CTkTextbox]) -> None:
        for tb in fields.values():
            tb.delete("1.0", "end")

    def show_product_preview(self, product: Product) -> None:
        """Show current product content on the original side without a suggestion."""
        desc_tr = _get_description_display(product.description, product.description_translations)
        desc_en = _get_en_description_display(product.description_translations)

        self._set_field(self._fields_orig, "name", product.name)
        self._set_field(self._fields_orig, "meta_title", product.meta_title or "-")
        self._set_field(self._fields_orig, "meta_desc", product.meta_description or "-")
        self._set_field(self._fields_orig, "desc_tr", desc_tr)
        self._set_field(self._fields_orig, "desc_en", desc_en or "-")

        # Clear suggested side
        self._clear_fields(self._fields_sugg)
        self._set_field(self._fields_sugg, "name", "AI ile yeniden yazma icin butonu kullanin")
        self._current_suggestion = None

    def show_suggestion(self, suggestion: SeoSuggestion) -> None:
        self._current_suggestion = suggestion

        orig_desc = _strip_html(suggestion.original_description) if suggestion.original_description else "(Aciklama yok)"
        orig_desc_en = _strip_html(suggestion.original_description_en) if suggestion.original_description_en else "-"
        sugg_desc = _strip_html(suggestion.suggested_description) if suggestion.suggested_description else "-"
        sugg_desc_en = _strip_html(suggestion.suggested_description_en) if suggestion.suggested_description_en else "-"

        # Original side
        self._set_field(self._fields_orig, "name", suggestion.original_name)
        self._set_field(self._fields_orig, "meta_title", suggestion.original_meta_title or "-")
        self._set_field(self._fields_orig, "meta_desc", suggestion.original_meta_description or "-")
        self._set_field(self._fields_orig, "desc_tr", orig_desc)
        self._set_field(self._fields_orig, "desc_en", orig_desc_en)

        # Suggested side
        self._set_field(self._fields_sugg, "name", suggestion.suggested_name or "-")
        self._set_field(self._fields_sugg, "meta_title", suggestion.suggested_meta_title or "-")
        self._set_field(self._fields_sugg, "meta_desc", suggestion.suggested_meta_description or "-")
        self._set_field(self._fields_sugg, "desc_tr", sugg_desc)
        self._set_field(self._fields_sugg, "desc_en", sugg_desc_en)

    def get_edited_suggestion(self) -> str:
        return self._fields_sugg.get("desc_tr", ctk.CTkTextbox(self)).get("1.0", "end").strip()

    def _approve(self) -> None:
        if self._on_approve and self._current_suggestion:
            self._on_approve(self._current_suggestion)

    def _reject(self) -> None:
        if self._on_reject and self._current_suggestion:
            self._on_reject(self._current_suggestion)

    def clear(self) -> None:
        self._current_suggestion = None
        self._clear_fields(self._fields_orig)
        self._clear_fields(self._fields_sugg)
