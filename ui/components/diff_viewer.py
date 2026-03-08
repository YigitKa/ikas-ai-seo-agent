import re
import tkinter as tk
from html.parser import HTMLParser

import customtkinter as ctk

from core.html_utils import has_html_markup, html_to_plain_text
from core.models import Product, SeoScore, SeoSuggestion
from core.presentation import (
    clean_suggestion_value,
    get_en_description_value,
    get_tr_description_value,
    group_score_issues,
)
from core.suggestion_service import apply_suggestion_field, create_pending_suggestion, sync_suggestion_fields
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
    _INLINE_TAGS = {"strong": "bold", "b": "bold", "em": "italic", "i": "italic", "u": "underline"}
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
        ctk.CTkLabel(toolbar, text="HTML", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self._mode_switch = ctk.CTkSegmentedButton(toolbar, values=["Gorunum", "HTML"], variable=self._mode, command=lambda _value: self._render(), width=140, height=26)
        self._mode_switch.grid(row=0, column=1, sticky="e")

        body = ctk.CTkFrame(self.widget, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self._text = tk.Text(body, wrap="word", relief="flat", borderwidth=0, highlightthickness=0, padx=8, pady=8, height=max(5, line_count * 3), background=COLORS["input_bg"], foreground=text_color, insertbackground=text_color, font=("Segoe UI", 13), cursor="arrow")
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
        self._text.tag_configure("code_inline", font=("Consolas", 12), background="#262b33", foreground="#c8facc")
        self._text.tag_configure("code_block", font=("Consolas", 12), background="#101318", foreground="#dce7f5", lmargin1=8, lmargin2=8, spacing1=4, spacing3=4)

    def set_value(self, value: str) -> None:
        self._value = value or ""
        self._render()

    def get_value(self) -> str:
        return self._value.strip()

    def _render(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        if self._mode.get() == "HTML":
            self._text.insert("end", self._value or "-", ("code_block",))
        elif not self._value:
            self._text.insert("end", "-", ("body",))
        elif not has_html_markup(self._value):
            self._text.insert("end", html_to_plain_text(self._value, preserve_breaks=True) or self._value, ("body",))
        else:
            parser = _HtmlPreviewParser()
            parser.feed(self._value)
            parser.close()
            for text, tags in parser.segments or [(html_to_plain_text(self._value, preserve_breaks=True) or self._value, ("body",))]:
                self._text.insert("end", text, tags or ("body",))
        self._text.configure(state="disabled")


class _ScoreMetricRow(ctk.CTkFrame):
    def __init__(self, master, *, name: str, max_value: int):
        super().__init__(master, fg_color="transparent")
        self._name = name
        self._max_value = max_value
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        self._label = ctk.CTkLabel(top, text=f"{name}: -/{max_value}", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_secondary"], anchor="w", width=160)
        self._label.pack(side="left")
        self._bar = ctk.CTkProgressBar(top, height=12, corner_radius=5)
        self._bar.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._bar.set(0)
        self._issues_card = ctk.CTkFrame(self, fg_color="#1b2333", corner_radius=6)
        self._issues_label = ctk.CTkLabel(self._issues_card, text="", justify="left", anchor="w", wraplength=1000, text_color="#ffd166", font=ctk.CTkFont(size=12, weight="bold"))
        self._issues_label.pack(fill="x", padx=10, pady=8)

    def set_value(self, value: int, max_value: int) -> None:
        self._label.configure(text=f"{self._name}: {value}/{max_value}")
        self._bar.set(value / max_value if max_value else 0)
        self._bar.configure(progress_color=score_color(int(value / max_value * 100)) if max_value else COLORS["text_secondary"])

    def set_issues(self, issues: list[str]) -> None:
        if issues:
            self._issues_label.configure(text="\n".join(f"- {issue}" for issue in issues[:3]))
            if not self._issues_card.winfo_manager():
                self._issues_card.pack(fill="x", padx=(166, 0), pady=(6, 0))
        else:
            self._issues_label.configure(text="")
            if self._issues_card.winfo_manager():
                self._issues_card.pack_forget()

    def clear(self) -> None:
        self._label.configure(text=f"{self._name}: -/{self._max_value}")
        self._bar.set(0)
        self.set_issues([])


class _HtmlCodeEditor(ctk.CTkFrame):
    _COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
    _TAG_RE = re.compile(r"</?([a-zA-Z][\w:-]*)")
    _ATTR_RE = re.compile(r"\s([a-zA-Z_:][\w:.-]*)(?=\=)")
    _STRING_RE = re.compile(r'"[^"\n]*"|\'[^\'\n]*\'')
    _ENTITY_RE = re.compile(r"&[a-zA-Z0-9#]+;")

    def __init__(self, master, *, value: str = "", on_change=None):
        super().__init__(master, fg_color=COLORS["input_bg"], corner_radius=6)
        self._on_change = on_change
        self._refresh_job: str | None = None

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(8, 6))

        for label, command in [
            ("<p>", lambda: self._insert_pair("<p>", "</p>")),
            ("<h2>", lambda: self._insert_pair("<h2>", "</h2>")),
            ("<strong>", lambda: self._insert_pair("<strong>", "</strong>")),
            ("Liste", self._insert_list),
            ("<a>", self._insert_link),
            ("<br>", lambda: self._insert_text("<br>\n")),
        ]:
            ctk.CTkButton(
                toolbar,
                text=label,
                width=68,
                height=26,
                fg_color=COLORS["bg_secondary"],
                hover_color=COLORS["border"],
                command=command,
            ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            toolbar,
            text="Undo",
            width=60,
            height=26,
            fg_color=COLORS["bg_secondary"],
            hover_color=COLORS["border"],
            command=self._undo,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            toolbar,
            text="Redo",
            width=60,
            height=26,
            fg_color=COLORS["bg_secondary"],
            hover_color=COLORS["border"],
            command=self._redo,
        ).pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self._line_numbers = tk.Text(
            body,
            width=5,
            wrap="none",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=10,
            background="#161b28",
            foreground=COLORS["text_secondary"],
            font=("Consolas", 12),
            state="disabled",
            cursor="arrow",
            takefocus=0,
        )
        self._line_numbers.grid(row=0, column=0, sticky="ns")

        self._text = tk.Text(
            body,
            wrap="none",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            background=COLORS["input_bg"],
            foreground=COLORS["text_primary"],
            insertbackground=COLORS["text_primary"],
            selectbackground="#315a8c",
            font=("Consolas", 13),
            undo=True,
            autoseparators=True,
            maxundo=-1,
        )
        self._text.grid(row=0, column=1, sticky="nsew")

        scrollbar = ctk.CTkScrollbar(body, command=self._on_scrollbar)
        scrollbar.grid(row=0, column=2, sticky="ns", padx=(8, 0))
        self._scrollbar = scrollbar
        self._text.configure(yscrollcommand=self._on_text_scroll)

        xscroll = ctk.CTkScrollbar(body, orientation="horizontal", command=self._text.xview)
        xscroll.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        self._text.configure(xscrollcommand=xscroll.set)

        self._configure_tags()
        self._bind_events()
        self.set_value(value)

    def _configure_tags(self) -> None:
        self._text.tag_configure("html_tag", foreground="#7cc5ff")
        self._text.tag_configure("html_attr", foreground="#ffd166")
        self._text.tag_configure("html_string", foreground="#a5d6a7")
        self._text.tag_configure("html_comment", foreground="#7f8c8d")
        self._text.tag_configure("html_entity", foreground="#ff9aa2")

    def _bind_events(self) -> None:
        for event in ("<KeyRelease>", "<ButtonRelease-1>", "<MouseWheel>", "<Configure>"):
            self._text.bind(event, self._schedule_refresh, add="+")
        self._text.bind("<Tab>", self._handle_tab)
        self._text.bind("<Control-z>", lambda _event: self._undo())
        self._text.bind("<Control-y>", lambda _event: self._redo())
        self._text.bind("<Control-Shift-Z>", lambda _event: self._redo())

    def focus_editor(self) -> None:
        self._text.focus_set()

    def set_value(self, value: str) -> None:
        self._text.delete("1.0", "end")
        self._text.insert("1.0", value or "")
        self._refresh()

    def get_value(self) -> str:
        return self._text.get("1.0", "end").strip()

    def _handle_tab(self, _event=None):
        self._text.insert("insert", "    ")
        self._schedule_refresh()
        return "break"

    def _undo(self):
        try:
            self._text.edit_undo()
        except tk.TclError:
            return "break"
        self._schedule_refresh()
        return "break"

    def _redo(self):
        try:
            self._text.edit_redo()
        except tk.TclError:
            return "break"
        self._schedule_refresh()
        return "break"

    def _insert_text(self, text: str) -> None:
        self._text.insert("insert", text)
        self._schedule_refresh()
        self.focus_editor()

    def _insert_pair(self, prefix: str, suffix: str) -> None:
        try:
            start = self._text.index("sel.first")
            end = self._text.index("sel.last")
            selection = self._text.get(start, end)
            self._text.delete(start, end)
            self._text.insert(start, prefix + selection + suffix)
        except tk.TclError:
            insert_at = self._text.index("insert")
            self._text.insert(insert_at, prefix + suffix)
            self._text.mark_set("insert", f"{insert_at}+{len(prefix)}c")
        self._schedule_refresh()
        self.focus_editor()

    def _insert_list(self) -> None:
        snippet = "<ul>\n    <li></li>\n</ul>"
        self._text.insert("insert", snippet)
        self._schedule_refresh()
        self.focus_editor()

    def _insert_link(self) -> None:
        snippet = '<a href=""></a>'
        insert_at = self._text.index("insert")
        self._text.insert(insert_at, snippet)
        self._text.mark_set("insert", f"{insert_at}+9c")
        self._schedule_refresh()
        self.focus_editor()

    def _on_scrollbar(self, *args) -> None:
        self._text.yview(*args)
        self._line_numbers.yview(*args)

    def _on_text_scroll(self, first, last) -> None:
        self._scrollbar.set(first, last)
        self._line_numbers.yview_moveto(first)

    def _schedule_refresh(self, _event=None):
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except Exception:
                pass
        self._refresh_job = self.after(60, self._refresh)

    def _refresh(self) -> None:
        self._refresh_job = None
        self._update_line_numbers()
        self._highlight_syntax()
        if self._on_change is not None:
            self._on_change()

    def _update_line_numbers(self) -> None:
        total_lines = int(self._text.index("end-1c").split(".")[0])
        content = "\n".join(str(number) for number in range(1, total_lines + 1))
        self._line_numbers.configure(state="normal")
        self._line_numbers.delete("1.0", "end")
        self._line_numbers.insert("1.0", content)
        self._line_numbers.configure(state="disabled")
        first, _last = self._text.yview()
        self._line_numbers.yview_moveto(first)

    def _clear_highlight_tags(self) -> None:
        for tag in ("html_tag", "html_attr", "html_string", "html_comment", "html_entity"):
            self._text.tag_remove(tag, "1.0", "end")

    def _offset_to_index(self, offset: int) -> str:
        return f"1.0+{offset}c"

    def _highlight_matches(self, regex: re.Pattern, tag_name: str, *, group: int = 0) -> None:
        text = self._text.get("1.0", "end-1c")
        for match in regex.finditer(text):
            start, end = match.span(group)
            self._text.tag_add(tag_name, self._offset_to_index(start), self._offset_to_index(end))

    def _highlight_syntax(self) -> None:
        self._clear_highlight_tags()
        self._highlight_matches(self._COMMENT_RE, "html_comment")
        self._highlight_matches(self._STRING_RE, "html_string")
        self._highlight_matches(self._ENTITY_RE, "html_entity")
        self._highlight_matches(self._TAG_RE, "html_tag", group=1)
        self._highlight_matches(self._ATTR_RE, "html_attr", group=1)


class _HtmlEditorWindow(ctk.CTkToplevel):
    def __init__(self, master, *, title: str, original_value: str, suggestion_value: str, on_save):
        super().__init__(master)
        self._on_save = on_save
        self._preview_job: str | None = None

        self.title(title)
        self.geometry("1460x860")
        self.minsize(1200, 720)
        self.configure(fg_color=COLORS["bg_primary"])
        self.transient(master.winfo_toplevel())
        self.after(50, self.lift)

        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=48)
        header.pack(fill="x", padx=10, pady=(10, 0))
        header.pack_propagate(False)
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["text_primary"]).pack(side="left", padx=14)
        ctk.CTkButton(header, text="Kaydet ve Kapat", height=30, fg_color=COLORS["success"], hover_color="#00a844", command=self._save).pack(side="right", padx=(8, 12), pady=9)
        ctk.CTkButton(header, text="Kapat", height=30, fg_color=COLORS["border"], hover_color=COLORS["bg_card"], command=self.destroy).pack(side="right", pady=9)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=10, pady=10)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        original_card = ctk.CTkFrame(content, fg_color=COLORS["bg_secondary"], corner_radius=8)
        original_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        original_card.grid_rowconfigure(1, weight=1)
        original_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(original_card, text="Orijinal", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["error"]).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))
        original_view = _HtmlField(original_card, line_count=14, text_color=COLORS["text_secondary"])
        original_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        original_view.set_value(original_value)

        editor_card = ctk.CTkFrame(content, fg_color=COLORS["bg_secondary"], corner_radius=8)
        editor_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        editor_card.grid_rowconfigure(1, weight=1)
        editor_card.grid_rowconfigure(3, weight=1)
        editor_card.grid_columnconfigure(0, weight=1)

        editor_header = ctk.CTkFrame(editor_card, fg_color="transparent")
        editor_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        editor_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(editor_header, text="Oneri HTML Kodu", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["success"]).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(editor_header, text="Onizlemeyi Yenile", width=120, height=28, fg_color=COLORS["accent"], hover_color=COLORS["bg_card"], command=self._refresh_preview).grid(row=0, column=1, sticky="e")

        self._editor = _HtmlCodeEditor(
            editor_card,
            value=suggestion_value or "",
            on_change=self._schedule_preview_refresh,
        )
        self._editor.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        ctk.CTkLabel(editor_card, text="Canli Onizleme", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text_secondary"]).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 8))
        self._preview = _HtmlField(editor_card, line_count=12, text_color=COLORS["text_primary"])
        self._preview.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._refresh_preview()
        self.after(100, self._editor.focus_editor)

        self.bind("<Escape>", lambda _event: self.destroy())

    def _schedule_preview_refresh(self, _event=None) -> None:
        if self._preview_job is not None:
            try:
                self.after_cancel(self._preview_job)
            except Exception:
                pass
        self._preview_job = self.after(150, self._refresh_preview)

    def _refresh_preview(self) -> None:
        self._preview_job = None
        self._preview.set_value(self._editor.get_value())

    def _save(self) -> None:
        self._on_save(self._editor.get_value())
        self.destroy()


class _CollapsibleField(ctk.CTkFrame):
    def __init__(
        self,
        master,
        key: str,
        label_text: str,
        line_count: int,
        start_open: bool = False,
        html_enabled: bool = False,
        on_field_rewrite=None,
        on_open_editor=None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._key = key
        self._expanded = start_open
        self._on_field_rewrite = on_field_rewrite
        self._on_open_editor = on_open_editor
        self.editor_btn: ctk.CTkButton | None = None

        header = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=6, height=36)
        header.pack(fill="x", pady=(6, 0))
        header.pack_propagate(False)

        self._toggle_btn = ctk.CTkButton(header, text="v" if start_open else ">", width=28, height=28, fg_color="transparent", hover_color=COLORS["border"], text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=14), corner_radius=4, command=self.toggle)
        self._toggle_btn.pack(side="left", padx=(4, 0), pady=3)

        self._label = ctk.CTkLabel(header, text=label_text, font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text_primary"], anchor="w")
        self._label.pack(side="left", padx=6, pady=3)
        self._label.bind("<Button-1>", lambda _event: self.toggle())
        header.bind("<Button-1>", lambda _event: self.toggle())

        self.ai_btn = ctk.CTkButton(header, text="AI ile olustur", width=110, height=26, font=ctk.CTkFont(size=12), fg_color=COLORS["accent"], hover_color=COLORS["bg_card"], command=self._request_rewrite)
        self.ai_btn.pack(side="right", padx=6, pady=4)

        if html_enabled:
            self.editor_btn = ctk.CTkButton(header, text="HTML Editor", width=106, height=26, font=ctk.CTkFont(size=12), fg_color=COLORS["bg_secondary"], hover_color=COLORS["border"], command=self._request_editor)
            self.editor_btn.pack(side="right", padx=(0, 6), pady=4)

        self._content = ctk.CTkFrame(self, fg_color="transparent")

        sub_header = ctk.CTkFrame(self._content, fg_color="transparent")
        sub_header.pack(fill="x", padx=5, pady=(4, 0))
        sub_header.grid_columnconfigure(0, weight=1)
        sub_header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(sub_header, text="Orijinal", font=ctk.CTkFont(size=12), text_color=COLORS["error"], anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 2))
        ctk.CTkLabel(sub_header, text="Oneri", font=ctk.CTkFont(size=12), text_color=COLORS["success"], anchor="w").grid(row=0, column=1, sticky="w", padx=(4, 0))

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

    def _request_rewrite(self) -> None:
        if self._on_field_rewrite:
            self.ai_btn.configure(state="disabled", text="Yaziliyor...")
            self._on_field_rewrite(self._key)

    def _request_editor(self) -> None:
        if self._on_open_editor:
            self._on_open_editor(self._key)


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
        self._current_product: Product | None = None
        self._score_expanded = True
        self._editor_windows: dict[str, _HtmlEditorWindow] = {}

        self._build_product_header()

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        self._sections: dict[str, _CollapsibleField] = {}
        self._fields_orig: dict[str, _FieldWidget] = {}
        self._fields_sugg: dict[str, _FieldWidget] = {}
        self._field_buttons: dict[str, ctk.CTkButton] = {}
        self._editor_buttons: dict[str, ctk.CTkButton] = {}

        for key, label_text, line_count, start_open, html_enabled in [
            ("name", "Ad", 2, False, False),
            ("meta_title", "Meta Title", 2, False, False),
            ("meta_desc", "Meta Description", 3, False, False),
            ("desc_tr", "Aciklama (TR)", 8, True, True),
            ("desc_en", "Aciklama (EN)", 6, False, True),
        ]:
            section = _CollapsibleField(
                scroll,
                key=key,
                label_text=label_text,
                line_count=line_count,
                start_open=start_open,
                html_enabled=html_enabled,
                on_field_rewrite=on_field_rewrite,
                on_open_editor=self._open_html_editor,
            )
            section.pack(fill="x")
            self._sections[key] = section
            self._fields_orig[key] = section.orig_tb
            self._fields_sugg[key] = section.sugg_tb
            self._field_buttons[key] = section.ai_btn
            if section.editor_btn is not None:
                self._editor_buttons[key] = section.editor_btn

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkButton(btn_frame, text="Onayla", fg_color=COLORS["success"], hover_color="#00a844", command=self._approve).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Reddet", fg_color=COLORS["error"], hover_color="#d50000", command=self._reject).pack(side="left", padx=5)

    def _build_product_header(self) -> None:
        self._header_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], corner_radius=8)
        self._header_frame.pack(fill="x", padx=5, pady=5)

        product_row = ctk.CTkFrame(self._header_frame, fg_color="transparent")
        product_row.pack(fill="x", padx=10, pady=(10, 5))

        img_frame = ctk.CTkFrame(product_row, fg_color=COLORS["bg_card"], corner_radius=8, width=80, height=80)
        img_frame.pack(side="left", padx=(0, 12))
        img_frame.pack_propagate(False)
        self.product_image_label = ctk.CTkLabel(img_frame, text="Gorsel\nyok", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11))
        self.product_image_label.pack(expand=True)

        info_frame = ctk.CTkFrame(product_row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)
        self._product_name_label = ctk.CTkLabel(info_frame, text="Urun secin", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["text_primary"], anchor="w", wraplength=500)
        self._product_name_label.pack(fill="x", pady=(0, 2))
        self._product_detail_label = ctk.CTkLabel(info_frame, text="", font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"], anchor="w")
        self._product_detail_label.pack(fill="x")
        self.gallery_frame = ctk.CTkFrame(info_frame, fg_color="transparent", height=44)
        self.gallery_frame.pack(fill="x", pady=(4, 0))

        action_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        action_row.pack(fill="x", pady=(8, 0))
        self._rewrite_product_btn = ctk.CTkButton(action_row, text="AI ile yeniden yaz", height=30, fg_color=COLORS["accent"], hover_color=COLORS["bg_card"], command=self._request_product_rewrite, state="disabled")
        self._rewrite_product_btn.pack(side="left", padx=(0, 8))
        self._translate_en_btn = ctk.CTkButton(action_row, text="AI ile ceviri", height=30, fg_color=COLORS["bg_card"], hover_color=COLORS["border"], command=self._request_translate_en, state="disabled")
        self._translate_en_btn.pack(side="left")

        self._score_card = ctk.CTkFrame(self._header_frame, fg_color=COLORS["bg_card"], corner_radius=8)
        self._score_card.pack(fill="x", padx=10, pady=(5, 10))

        score_header = ctk.CTkFrame(self._score_card, fg_color="transparent")
        score_header.pack(fill="x", padx=12, pady=(10, 0))
        score_header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(score_header, text="SEO Ozeti", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text_primary"]).grid(row=0, column=0, sticky="w")
        self._score_summary_label = ctk.CTkLabel(score_header, text="Skor: -", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["text_secondary"])
        self._score_summary_label.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self._score_toggle_btn = ctk.CTkButton(score_header, text="Gizle", width=70, height=26, fg_color=COLORS["bg_secondary"], hover_color=COLORS["border"], command=self._toggle_score_card)
        self._score_toggle_btn.grid(row=0, column=2, sticky="e")

        self._score_body = ctk.CTkFrame(self._score_card, fg_color="transparent")
        self._score_body.pack(fill="x", padx=12, pady=(10, 12))
        score_top = ctk.CTkFrame(self._score_body, fg_color="transparent")
        score_top.pack(fill="x")

        score_left = ctk.CTkFrame(score_top, fg_color="transparent")
        score_left.pack(side="left", padx=(0, 20), anchor="n")
        ctk.CTkLabel(score_left, text="SEO Skoru", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text_secondary"]).pack()
        self._score_total_label = ctk.CTkLabel(score_left, text="-", font=ctk.CTkFont(size=42, weight="bold"), text_color=COLORS["text_secondary"])
        self._score_total_label.pack()

        bars_frame = ctk.CTkFrame(score_top, fg_color="transparent")
        bars_frame.pack(side="left", fill="both", expand=True)
        self._score_rows: dict[str, _ScoreMetricRow] = {}
        for name, max_val in [("Baslik", 25), ("Aciklama", 30), ("Meta Title", 20), ("Meta Desc", 15), ("Keyword", 10)]:
            row = _ScoreMetricRow(bars_frame, name=name, max_value=max_val)
            row.pack(fill="x", pady=(0, 8))
            self._score_rows[name] = row

        self._other_issues_card = ctk.CTkFrame(self._score_body, fg_color="#1b2333", corner_radius=6)
        self._other_issues_label = ctk.CTkLabel(self._other_issues_card, text="", justify="left", anchor="w", wraplength=1200, text_color="#ffb86b", font=ctk.CTkFont(size=12, weight="bold"))
        self._other_issues_label.pack(fill="x", padx=10, pady=8)

    def _toggle_score_card(self) -> None:
        self._score_expanded = not self._score_expanded
        if self._score_expanded:
            self._score_body.pack(fill="x", padx=12, pady=(10, 12))
            self._score_toggle_btn.configure(text="Gizle")
        else:
            self._score_body.pack_forget()
            self._score_toggle_btn.configure(text="Ac")

    def _show_other_issues(self, issues: list[str]) -> None:
        if issues:
            text = "Diger SEO Notlari\n" + "\n".join(f"- {issue}" for issue in issues[:5])
            self._other_issues_label.configure(text=text)
            if not self._other_issues_card.winfo_manager():
                self._other_issues_card.pack(fill="x", pady=(4, 0))
        else:
            self._other_issues_label.configure(text="")
            if self._other_issues_card.winfo_manager():
                self._other_issues_card.pack_forget()

    def _close_editor_windows(self) -> None:
        for key, window in list(self._editor_windows.items()):
            try:
                if window.winfo_exists():
                    window.destroy()
            except Exception:
                pass
            self._editor_windows.pop(key, None)

    def _ensure_current_suggestion(self) -> None:
        if self._current_suggestion is not None or self._current_product is None:
            return
        self._current_suggestion = create_pending_suggestion(self._current_product)

    def _apply_field_to_current_suggestion(self, field: str, value: str) -> None:
        if self._current_suggestion is None:
            return
        apply_suggestion_field(self._current_suggestion, field, value)

    def _sync_current_suggestion_from_fields(self) -> None:
        self._ensure_current_suggestion()
        if self._current_suggestion is None:
            return
        sync_suggestion_fields(
            self._current_suggestion,
            {field: widget.get_value() for field, widget in self._fields_sugg.items()},
        )

    def _close_editor_window(self, field: str) -> None:
        window = self._editor_windows.pop(field, None)
        if window is None:
            return
        try:
            if window.winfo_exists():
                window.destroy()
        except Exception:
            pass

    def _save_html_editor_value(self, field: str, value: str) -> None:
        self._set_field(self._fields_sugg, field, value)
        self._ensure_current_suggestion()
        self._apply_field_to_current_suggestion(field, value)
        section = self._sections.get(field)
        if section:
            section.expand()
        self._close_editor_window(field)

    def _open_html_editor(self, field: str) -> None:
        if field not in ("desc_tr", "desc_en"):
            return
        existing = self._editor_windows.get(field)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass

        labels = {"desc_tr": "Aciklama (TR)", "desc_en": "Aciklama (EN)"}
        original_value = self._fields_orig[field].get_value()
        suggestion_value = clean_suggestion_value(self._fields_sugg[field].get_value())
        window = _HtmlEditorWindow(
            self,
            title=f"{labels[field]} HTML Editor",
            original_value=original_value,
            suggestion_value=suggestion_value,
            on_save=lambda value, field_name=field: self._save_html_editor_value(field_name, value),
        )
        self._editor_windows[field] = window
        window.protocol("WM_DELETE_WINDOW", lambda field_name=field: self._close_editor_window(field_name))

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
        self._score_summary_label.configure(text=f"Skor: {score.total_score}", text_color=color)
        grouped_issues, other_issues = group_score_issues(score.issues)
        for name, (value, max_val) in {
            "Baslik": (score.title_score, 25),
            "Aciklama": (score.description_score, 30),
            "Meta Title": (score.meta_score, 20),
            "Meta Desc": (score.meta_desc_score, 15),
            "Keyword": (score.keyword_score, 10),
        }.items():
            self._score_rows[name].set_value(value, max_val)
            self._score_rows[name].set_issues(grouped_issues.get(name, []))
        self._show_other_issues(other_issues)

    def clear_score(self) -> None:
        self._score_total_label.configure(text="-", text_color=COLORS["text_secondary"])
        self._score_summary_label.configure(text="Skor: -", text_color=COLORS["text_secondary"])
        for row in self._score_rows.values():
            row.clear()
        self._show_other_issues([])

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
        for btn in self._editor_buttons.values():
            btn.configure(state=state)

    def set_field_value(self, field: str, value: str) -> None:
        self._set_field(self._fields_sugg, field, value)
        self._ensure_current_suggestion()
        self._apply_field_to_current_suggestion(field, value)
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
        self._close_editor_windows()
        self._current_product = product
        self._current_suggestion = None
        self.set_product_info(product)
        desc_tr = get_tr_description_value(product.description, product.description_translations)
        desc_en = get_en_description_value(product.description_translations)
        self._rewrite_product_btn.configure(state="normal", text="AI ile yeniden yaz")
        self._translate_en_btn.configure(state="normal", text="AI ile ceviri")
        self._set_field(self._fields_orig, "name", product.name)
        self._set_field(self._fields_orig, "meta_title", product.meta_title or "-")
        self._set_field(self._fields_orig, "meta_desc", product.meta_description or "-")
        self._set_field(self._fields_orig, "desc_tr", desc_tr or "(Aciklama yok)")
        self._set_field(self._fields_orig, "desc_en", desc_en or "-")
        self._clear_fields(self._fields_sugg)
        self._set_field(self._fields_sugg, "name", "AI ile yeniden yazma icin butonu kullanin")

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
        return widget.get_value() if widget is not None else ""

    def _approve(self) -> None:
        self._sync_current_suggestion_from_fields()
        if self._on_approve and self._current_suggestion:
            self._on_approve(self._current_suggestion)

    def _reject(self) -> None:
        self._sync_current_suggestion_from_fields()
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
        self._close_editor_windows()
        self._current_suggestion = None
        self._current_product = None
        self._clear_fields(self._fields_orig)
        self._clear_fields(self._fields_sugg)
        self.clear_score()
        self._product_name_label.configure(text="Urun secin")
        self._product_detail_label.configure(text="")
        self.product_image_label.configure(image=None, text="Gorsel\nyok")
        self._rewrite_product_btn.configure(state="disabled", text="AI ile yeniden yaz")
        self._translate_en_btn.configure(state="disabled", text="AI ile ceviri")
