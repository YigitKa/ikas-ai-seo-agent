import re
import tkinter as tk
from html.parser import HTMLParser

import customtkinter as ctk

from core.html_utils import has_html_markup, html_to_plain_text
from core.models import Product, SeoScore, SeoSuggestion
from ui.themes.dark import COLORS, score_color


class _FieldWidget:
    def __init__(self) -> None:
        self.widget = None

    def grid(self, **kwargs) -> None:
        if self.widget is not None:
            self.widget.grid(**kwargs)

    def set_value(self, value: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        self.set_value("")

    def get_value(self) -> str:
        raise NotImplementedError


class _PlainTextField(_FieldWidget):
    def __init__(self, master, *, height: int, text_color: str):
        super().__init__()
        self.widget = ctk.CTkTextbox(
            master,
            fg_color=COLORS["input_bg"],
            text_color=text_color,
            height=height,
            font=ctk.CTkFont(size=14),
            wrap="word",
        )

    def set_value(self, value: str) -> None:
        self.widget.delete("1.0", "end")
        self.widget.insert("1.0", value or "")

    def get_value(self) -> str:
        return self.widget.get("1.0", "end").strip()


class _HtmlPreviewParser(HTMLParser):
    _INLINE_TAGS = {
        "strong": "bold",
        "b": "bold",
        "em": "italic",
        "i": "italic",
        "u": "underline",
    }
    _HEADING_TAGS = {f"h{level}": "heading" for level in range(1, 7)}
    _BLOCK_TAGS = {"p", "div", "section", "article", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._segments: list[tuple[str, tuple[str, ...]]] = []
        self._styles: list[str] = []
        self._list_stack: list[dict[str, int | str]] = []
        self._in_pre = False

    @property
    def segments(self) -> list[tuple[str, tuple[str, ...]]]:
        return list(self._segments)

    def _tail(self, size: int = 2) -> str:
        if not self._segments:
            return ""
        recent = "".join(text for text, _ in self._segments[-4:])
        return recent[-size:]

    def _append(self, text: str, extra_tags: tuple[str, ...] = ()) -> None:
        if not text:
            return
        tags = tuple(dict.fromkeys((*self._styles, *extra_tags)))
        if self._segments and self._segments[-1][1] == tags:
            prev_text, _ = self._segments[-1]
            self._segments[-1] = (prev_text + text, tags)
        else:
            self._segments.append((text, tags))

    def _remove_style(self, name: str) -> None:
        for index in range(len(self._styles) - 1, -1, -1):
            if self._styles[index] == name:
                self._styles.pop(index)
                return

    def _ensure_line_break(self) -> None:
        if self._segments and not self._tail(1).endswith("\n"):
            self._append("\n")

    def _ensure_block_break(self) -> None:
        if not self._segments:
            return
        tail = self._tail(2)
        if tail.endswith("\n\n"):
            return
        if tail.endswith("\n"):
            self._append("\n")
        else:
            self._append("\n\n")

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()

        if lowered == "br":
            self._ensure_line_break()
            return

        if lowered in ("ul", "ol"):
            self._ensure_block_break()
            self._list_stack.append({"kind": lowered, "index": 0})
            return

        if lowered == "li":
            self._ensure_line_break()
            level = max(len(self._list_stack) - 1, 0)
            indent = "  " * level
            if self._list_stack and self._list_stack[-1]["kind"] == "ol":
                self._list_stack[-1]["index"] = int(self._list_stack[-1]["index"]) + 1
                marker = f"{self._list_stack[-1]['index']}."
            else:
                marker = "-"
            self._append(f"{indent}{marker} ", ("muted",))
            return

        if lowered in self._HEADING_TAGS or lowered == "pre":
            self._ensure_block_break()

        if lowered in self._INLINE_TAGS:
            self._styles.append(self._INLINE_TAGS[lowered])
            return

        if lowered in self._HEADING_TAGS:
            self._styles.append(self._HEADING_TAGS[lowered])
            return

        if lowered == "code":
            if not self._in_pre:
                self._styles.append("code_inline")
            return

        if lowered == "pre":
            self._styles.append("code_block")
            self._in_pre = True

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()

        if lowered in self._INLINE_TAGS:
            self._remove_style(self._INLINE_TAGS[lowered])
            return

        if lowered in self._HEADING_TAGS:
            self._remove_style(self._HEADING_TAGS[lowered])
            self._ensure_block_break()
            return

        if lowered == "code":
            if not self._in_pre:
                self._remove_style("code_inline")
            return

        if lowered == "pre":
            self._remove_style("code_block")
            self._in_pre = False
            self._ensure_block_break()
            return

        if lowered == "li":
            self._ensure_line_break()
            return

        if lowered in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self._ensure_block_break()
            return

        if lowered in self._BLOCK_TAGS:
            self._ensure_block_break()

    def handle_data(self, data: str) -> None:
        if not data:
            return

        if self._in_pre:
            self._append(data)
            return

        text = re.sub(r"\s+", " ", data)
        if not text:
            return

        tail = self._tail(1)
        if tail in ("", "\n", " "):
            text = text.lstrip()
        if tail == " ":
            text = text.lstrip()
        if not text:
            return

        self._append(text)


class _HtmlField(_FieldWidget):
    def __init__(self, master, *, line_count: int, text_color: str):
        super().__init__()
        self._value = ""
        self._text_color = text_color
        self._mode = ctk.StringVar(value="Gorunum")

        self.widget = ctk.CTkFrame(master, fg_color=COLORS["input_bg"], corner_radius=6)
        self.widget.grid_rowconfigure(1, weight=1)
        self.widget.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(self.widget, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        toolbar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            toolbar,
            text="HTML",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, sticky="w")

        self._mode_switch = ctk.CTkSegmentedButton(
            toolbar,
            values=["Gorunum", "HTML"],
            variable=self._mode,
            command=lambda _value: self._render(),
            width=140,
            height=26,
        )
        self._mode_switch.grid(row=0, column=1, sticky="e")

        body = ctk.CTkFrame(self.widget, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self._text = tk.Text(
            body,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=8,
            height=max(5, line_count * 3),
            background=COLORS["input_bg"],
            foreground=text_color,
            insertbackground=text_color,
            font=("Segoe UI", 13),
            cursor="arrow",
        )
        self._text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ctk.CTkScrollbar(body, command=self._text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        self._text.configure(yscrollcommand=scrollbar.set)

        self._configure_tags()
        self._render()

    def _configure_tags(self) -> None:
        self._text.tag_configure("body", foreground=self._text_color, spacing1=1, spacing3=2)
        self._text.tag_configure("bold", font=("Segoe UI Semibold", 13), foreground=self._text_color)
        self._text.tag_configure("italic", font=("Segoe UI", 13, "italic"), foreground=self._text_color)
        self._text.tag_configure("underline", underline=True, foreground=self._text_color)
        self._text.tag_configure("heading", font=("Segoe UI Semibold", 15), foreground=COLORS["text_primary"], spacing1=4, spacing3=4)
        self._text.tag_configure("muted", foreground=COLORS["text_secondary"])
        self._text.tag_configure(
            "code_inline",
            font=("Consolas", 12),
            background="#262b33",
            foreground="#c8facc",
        )
        self._text.tag_configure(
            "code_block",
            font=("Consolas", 12),
            background="#101318",
            foreground="#dce7f5",
            lmargin1=8,
            lmargin2=8,
            spacing1=4,
            spacing3=4,
        )

    def set_value(self, value: str) -> None:
        self._value = value or ""
        self._render()

    def get_value(self) -> str:
        return self._value.strip()

    def _insert_segments(self, segments: list[tuple[str, tuple[str, ...]]]) -> None:
        for text, tags in segments:
            active_tags = tags or ("body",)
            self._text.insert("end", text, active_tags)

    def _render_preview(self) -> None:
        value = self._value or ""
        if not value:
            self._text.insert("end", "-", ("body",))
            return

        if not has_html_markup(value):
            preview_text = html_to_plain_text(value, preserve_breaks=True) or value
            self._text.insert("end", preview_text, ("body",))
            return

        parser = _HtmlPreviewParser()
        parser.feed(value)
        parser.close()
        segments = parser.segments
        if not segments:
            fallback = html_to_plain_text(value, preserve_breaks=True) or value
            self._text.insert("end", fallback, ("body",))
            return
        self._insert_segments(segments)

    def _render_html_source(self) -> None:
        source = self._value or "-"
        self._text.insert("end", source, ("code_block",))

    def _render(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        if self._mode.get() == "HTML":
            self._render_html_source()
        else:
            self._render_preview()
        self._text.configure(state="disabled")


def _get_tr_description_value(description: str, translations: dict[str, str] | None = None) -> str:
    if translations:
        tr_desc = translations.get("tr", "")
        if tr_desc and tr_desc.strip():
            return tr_desc
    if description and description.strip():
        return description
    return ""


def _get_en_description_value(translations: dict[str, str] | None = None) -> str:
    if translations:
        en_desc = translations.get("en", "")
        if en_desc and en_desc.strip():
            return en_desc
    return ""


class _CollapsibleField(ctk.CTkFrame):
    """A collapsible section containing original/suggested inputs for a single field."""

    def __init__(
        self,
        master,
        key: str,
        label_text: str,
        line_count: int,
        start_open: bool = False,
        html_enabled: bool = False,
        on_field_rewrite=None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._key = key
        self._expanded = start_open
        self._on_field_rewrite = on_field_rewrite

        header = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=6, height=36)
        header.pack(fill="x", pady=(6, 0))
        header.pack_propagate(False)

        self._toggle_btn = ctk.CTkButton(
            header,
            text="v" if start_open else ">",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=14),
            corner_radius=4,
            command=self.toggle,
        )
        self._toggle_btn.pack(side="left", padx=(4, 0), pady=3)

        self._label = ctk.CTkLabel(
            header,
            text=label_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self._label.pack(side="left", padx=6, pady=3)
        self._label.bind("<Button-1>", lambda _event: self.toggle())
        header.bind("<Button-1>", lambda _event: self.toggle())

        self.ai_btn = ctk.CTkButton(
            header,
            text="AI ile olustur",
            width=110,
            height=26,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["accent"],
            hover_color=COLORS["bg_card"],
            command=self._request_rewrite,
        )
        self.ai_btn.pack(side="right", padx=6, pady=4)

        self._content = ctk.CTkFrame(self, fg_color="transparent")

        sub_header = ctk.CTkFrame(self._content, fg_color="transparent")
        sub_header.pack(fill="x", padx=5, pady=(4, 0))
        sub_header.grid_columnconfigure(0, weight=1)
        sub_header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            sub_header,
            text="Orijinal",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["error"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 2))
        ctk.CTkLabel(
            sub_header,
            text="Oneri",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["success"],
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))

        body = ctk.CTkFrame(self._content, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=2, pady=(2, 0))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        height = max(40, line_count * 26)
        field_cls = _HtmlField if html_enabled else _PlainTextField

        if html_enabled:
            self.orig_tb = field_cls(body, line_count=line_count, text_color=COLORS["text_secondary"])
            self.sugg_tb = field_cls(body, line_count=line_count, text_color=COLORS["text_primary"])
        else:
            self.orig_tb = field_cls(body, height=height, text_color=COLORS["text_secondary"])
            self.sugg_tb = field_cls(body, height=height, text_color=COLORS["text_primary"])

        self.orig_tb.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=2)
        self.sugg_tb.grid(row=0, column=1, sticky="nsew", padx=(3, 0), pady=2)

        if line_count >= 4:
            body.grid_rowconfigure(0, weight=1)

        if start_open:
            self._content.pack(fill="both", expand=True)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._content.pack(fill="both", expand=True)
            self._toggle_btn.configure(text="v")
        else:
            self._content.pack_forget()
            self._toggle_btn.configure(text=">")

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

        self._build_product_header()

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        field_defs = [
            ("name", "Ad", 2, False, False),
            ("meta_title", "Meta Title", 2, False, False),
            ("meta_desc", "Meta Description", 3, False, False),
            ("desc_tr", "Aciklama (TR)", 8, True, True),
            ("desc_en", "Aciklama (EN)", 6, False, True),
        ]

        self._sections: dict[str, _CollapsibleField] = {}
        self._fields_orig: dict[str, _FieldWidget] = {}
        self._fields_sugg: dict[str, _FieldWidget] = {}
        self._field_buttons: dict[str, ctk.CTkButton] = {}

        for key, label_text, line_count, start_open, html_enabled in field_defs:
            section = _CollapsibleField(
                scroll,
                key=key,
                label_text=label_text,
                line_count=line_count,
                start_open=start_open,
                html_enabled=html_enabled,
                on_field_rewrite=on_field_rewrite,
            )
            section.pack(fill="x")
            self._sections[key] = section
            self._fields_orig[key] = section.orig_tb
            self._fields_sugg[key] = section.sugg_tb
            self._field_buttons[key] = section.ai_btn

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkButton(
            btn_frame,
            text="Onayla",
            fg_color=COLORS["success"],
            hover_color="#00a844",
            command=self._approve,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Reddet",
            fg_color=COLORS["error"],
            hover_color="#d50000",
            command=self._reject,
        ).pack(side="left", padx=5)

    def _build_product_header(self) -> None:
        self._header_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=8)
        self._header_frame.pack(fill="x", padx=5, pady=5)

        product_row = ctk.CTkFrame(self._header_frame, fg_color="transparent")
        product_row.pack(fill="x", padx=10, pady=(10, 5))

        img_frame = ctk.CTkFrame(
            product_row,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            width=80,
            height=80,
        )
        img_frame.pack(side="left", padx=(0, 12))
        img_frame.pack_propagate(False)

        self.product_image_label = ctk.CTkLabel(
            img_frame,
            text="Gorsel\nyok",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=11),
        )
        self.product_image_label.pack(expand=True)

        info_frame = ctk.CTkFrame(product_row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)

        self._product_name_label = ctk.CTkLabel(
            info_frame,
            text="Urun secin",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
            wraplength=500,
        )
        self._product_name_label.pack(fill="x", pady=(0, 2))

        self._product_detail_label = ctk.CTkLabel(
            info_frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_secondary"],
            anchor="w",
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

        score_card = ctk.CTkFrame(self._header_frame, fg_color=COLORS["bg_card"], corner_radius=8)
        score_card.pack(fill="x", padx=10, pady=(5, 10))

        score_inner = ctk.CTkFrame(score_card, fg_color="transparent")
        score_inner.pack(fill="x", padx=12, pady=10)

        score_left = ctk.CTkFrame(score_inner, fg_color="transparent")
        score_left.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(
            score_left,
            text="SEO Skoru",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_secondary"],
        ).pack()

        self._score_total_label = ctk.CTkLabel(
            score_left,
            text="-",
            font=ctk.CTkFont(size=42, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        self._score_total_label.pack()

        bars_frame = ctk.CTkFrame(score_inner, fg_color="transparent")
        bars_frame.pack(side="left", fill="both", expand=True, padx=(0, 15))

        self._score_bars: dict[str, tuple[ctk.CTkLabel, ctk.CTkProgressBar]] = {}
        categories = [
            ("Baslik", 25),
            ("Aciklama", 30),
            ("Meta Title", 20),
            ("Meta Desc", 15),
            ("Keyword", 10),
        ]
        for name, max_val in categories:
            bar_row = ctk.CTkFrame(bars_frame, fg_color="transparent")
            bar_row.pack(fill="x", pady=2)

            label = ctk.CTkLabel(
                bar_row,
                text=f"{name}: -/{max_val}",
                font=ctk.CTkFont(size=13),
                text_color=COLORS["text_secondary"],
                anchor="w",
                width=150,
            )
            label.pack(side="left")

            bar = ctk.CTkProgressBar(bar_row, height=12, corner_radius=5)
            bar.pack(side="left", fill="x", expand=True, padx=(5, 0))
            bar.set(0)

            self._score_bars[name] = (label, bar)

        issues_frame = ctk.CTkFrame(score_inner, fg_color="transparent", width=280)
        issues_frame.pack(side="right", fill="y")
        issues_frame.pack_propagate(False)

        ctk.CTkLabel(
            issues_frame,
            text="Sorunlar",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_secondary"],
            anchor="w",
        ).pack(fill="x")

        self._issues_label = ctk.CTkLabel(
            issues_frame,
            text="",
            wraplength=270,
            justify="left",
            text_color=COLORS["warning"],
            font=ctk.CTkFont(size=12),
            anchor="nw",
        )
        self._issues_label.pack(fill="both", expand=True, pady=(2, 0))

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
            self._issues_label.configure(text="\n".join(f"- {issue}" for issue in score.issues[:5]))
        else:
            self._issues_label.configure(text="Sorun yok")

    def clear_score(self) -> None:
        self._score_total_label.configure(text="-", text_color=COLORS["text_secondary"])
        for name, (label, bar) in self._score_bars.items():
            label.configure(text=f"{name}: -")
            bar.set(0)
        self._issues_label.configure(text="")

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

    def _set_field(self, fields: dict[str, _FieldWidget], key: str, value: str) -> None:
        widget = fields.get(key)
        if widget:
            widget.set_value(value)

    def _clear_fields(self, fields: dict[str, _FieldWidget]) -> None:
        for widget in fields.values():
            widget.clear()

    def show_product_preview(self, product: Product) -> None:
        self.set_product_info(product)
        desc_tr = _get_tr_description_value(product.description, product.description_translations)
        desc_en = _get_en_description_value(product.description_translations)
        self._rewrite_product_btn.configure(state="normal", text="AI ile yeniden yaz")
        self._translate_en_btn.configure(state="normal", text="AI ile ceviri")

        self._set_field(self._fields_orig, "name", product.name)
        self._set_field(self._fields_orig, "meta_title", product.meta_title or "-")
        self._set_field(self._fields_orig, "meta_desc", product.meta_description or "-")
        self._set_field(self._fields_orig, "desc_tr", desc_tr or "(Aciklama yok)")
        self._set_field(self._fields_orig, "desc_en", desc_en or "-")

        self._clear_fields(self._fields_sugg)
        self._set_field(self._fields_sugg, "name", "AI ile yeniden yazma icin butonu kullanin")
        self._current_suggestion = None

    def show_suggestion(self, suggestion: SeoSuggestion) -> None:
        self._current_suggestion = suggestion

        self._set_field(self._fields_orig, "name", suggestion.original_name)
        self._set_field(self._fields_orig, "meta_title", suggestion.original_meta_title or "-")
        self._set_field(self._fields_orig, "meta_desc", suggestion.original_meta_description or "-")
        self._set_field(self._fields_orig, "desc_tr", suggestion.original_description or "(Aciklama yok)")
        self._set_field(self._fields_orig, "desc_en", suggestion.original_description_en or "-")

        self._set_field(self._fields_sugg, "name", suggestion.suggested_name or "-")
        self._set_field(self._fields_sugg, "meta_title", suggestion.suggested_meta_title or "-")
        self._set_field(self._fields_sugg, "meta_desc", suggestion.suggested_meta_description or "-")
        self._set_field(self._fields_sugg, "desc_tr", suggestion.suggested_description or "-")
        self._set_field(self._fields_sugg, "desc_en", suggestion.suggested_description_en or "-")

        for section in self._sections.values():
            section.expand()

    def get_edited_suggestion(self) -> str:
        widget = self._fields_sugg.get("desc_tr")
        if widget is None:
            return ""
        return widget.get_value()

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
