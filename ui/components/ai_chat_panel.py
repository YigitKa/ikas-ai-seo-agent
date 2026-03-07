"""Chat-style AI panel with collapsible thoughts, metrics, and rich text rendering."""

from __future__ import annotations

import json
import re
import time
import tkinter as tk
from datetime import datetime
from typing import Callable, Optional

import customtkinter as ctk

from ui.themes.dark import COLORS

_CLR_USER_BG = "#2b3038"
_CLR_AI_BG = "#171a1f"
_CLR_CARD = "#1c2026"
_CLR_THINK_BG = "#1b1f24"
_CLR_BORDER = "#363c44"
_CLR_MODEL = "#b7c4ff"
_CLR_MUTED = "#9ca3af"
_CLR_THINK = "#d5b86a"
_CLR_ERROR = "#ff7b7b"
_CLR_SUCCESS = "#d7dde8"
_CLR_PILL = "#20242b"


def _short_model_name(model_name: str) -> str:
    if not model_name:
        return "AI"
    if "/" in model_name:
        return model_name.split("/")[-1]
    return model_name


def _format_duration(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    if seconds < 60:
        return f"{seconds:.2f}s" if seconds < 10 else f"{seconds:.1f}s"
    minutes, rem = divmod(int(seconds), 60)
    return f"{minutes}m {rem}s"


def _human_number(value: int | float | None, suffix: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    if value >= 1000:
        return f"{value / 1000:.1f}K{suffix}"
    return f"{value}{suffix}"


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return False
    try:
        json.loads(stripped)
        return True
    except Exception:
        return False


def _prompt_preview(prompt: str) -> str:
    cleaned = " ".join(line.strip() for line in prompt.splitlines() if line.strip())
    if len(cleaned) > 160:
        return cleaned[:157] + "..."
    return cleaned or "Istek"


class _MetricPill(ctk.CTkLabel):
    def __init__(self, master, text: str, **kwargs):
        super().__init__(
            master,
            text=text,
            fg_color=_CLR_PILL,
            text_color=COLORS["text_secondary"],
            corner_radius=999,
            padx=10,
            pady=3,
            font=ctk.CTkFont(size=11),
            **kwargs,
        )


class _RichText(ctk.CTkFrame):
    _INLINE_RE = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)")

    def __init__(
        self,
        master,
        content: str,
        *,
        bg_color: str,
        text_color: str,
        max_rows: int = 200,
        code_mode: bool = False,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._bg_color = bg_color
        self._text_color = text_color
        self._max_rows = max_rows
        self._fit_job: str | None = None
        self._text = tk.Text(
            self,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            background=bg_color,
            foreground=text_color,
            insertbackground=text_color,
            font=("Segoe UI", 13),
            spacing1=1,
            spacing3=4,
            cursor="arrow",
            height=1,
            width=1,
        )
        self._text.pack(fill="x", expand=False)
        self.bind("<Configure>", self._schedule_fit)
        self._text.bind("<Configure>", self._schedule_fit)
        self._configure_tags()
        self.set_content(content, code_mode=code_mode)

    def _configure_tags(self) -> None:
        self._text.tag_configure("body", foreground=self._text_color, spacing1=2, spacing3=4)
        self._text.tag_configure("bold", font=("Segoe UI Semibold", 13), foreground=self._text_color)
        self._text.tag_configure("italic", font=("Segoe UI", 13, "italic"), foreground=self._text_color)
        self._text.tag_configure("muted", foreground=_CLR_MUTED)
        self._text.tag_configure(
            "code_inline",
            font=("Consolas", 12),
            background="#262b33",
            foreground="#c8facc",
        )
        self._text.tag_configure(
            "code_block",
            font=("Consolas", 12),
            foreground="#dce7f5",
            background="#101318",
            lmargin1=8,
            lmargin2=8,
            spacing1=4,
            spacing3=6,
        )
        self._text.tag_configure("heading", font=("Segoe UI Semibold", 14), foreground="#f3f4f6", spacing1=6)

    def set_content(self, content: str, code_mode: bool = False) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")

        if code_mode or _looks_like_json(content):
            self._text.insert("end", content.strip(), ("code_block",))
            self._text.insert("end", "\n")
        else:
            self._render_markdown(content.rstrip())

        self._text.configure(state="disabled")
        self._schedule_fit()

    def _schedule_fit(self, event=None) -> None:
        if self._fit_job is not None:
            try:
                self.after_cancel(self._fit_job)
            except Exception:
                pass
        self._fit_job = self.after(20, self._fit_height)

    def _fit_height(self) -> None:
        self._fit_job = None
        self.update_idletasks()
        try:
            lines = int(self._text.count("1.0", "end-1c", "displaylines")[0])
        except Exception:
            lines = max(self._text.get("1.0", "end-1c").count("\n") + 1, 1)
        rows = min(max(lines, 1), self._max_rows)
        self._text.configure(height=rows)

    def _render_markdown(self, content: str) -> None:
        in_code = False
        for raw_line in content.splitlines():
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if stripped.startswith("```"):
                in_code = not in_code
                continue

            if in_code:
                self._text.insert("end", line + "\n", ("code_block",))
                continue

            if not stripped:
                self._text.insert("end", "\n")
                continue

            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
                self._insert_inline(heading, ("heading",))
                self._text.insert("end", "\n")
                continue

            bullet_match = re.match(r"^(\s*)([-*])\s+(.*)$", line)
            if bullet_match:
                indent = bullet_match.group(1)
                self._text.insert("end", indent + "• ", ("muted",))
                self._insert_inline(bullet_match.group(3), ("body",))
                self._text.insert("end", "\n")
                continue

            number_match = re.match(r"^(\s*)(\d+\.)\s+(.*)$", line)
            if number_match:
                self._text.insert("end", number_match.group(1) + number_match.group(2) + " ", ("muted",))
                self._insert_inline(number_match.group(3), ("body",))
                self._text.insert("end", "\n")
                continue

            self._insert_inline(line, ("body",))
            self._text.insert("end", "\n")

    def _insert_inline(self, line: str, base_tags: tuple[str, ...]) -> None:
        cursor = 0
        for match in self._INLINE_RE.finditer(line):
            if match.start() > cursor:
                self._text.insert("end", line[cursor:match.start()], base_tags)
            token = match.group(0)
            if token.startswith("**") and token.endswith("**"):
                self._text.insert("end", token[2:-2], base_tags + ("bold",))
            elif token.startswith("*") and token.endswith("*"):
                self._text.insert("end", token[1:-1], base_tags + ("italic",))
            elif token.startswith("`") and token.endswith("`"):
                self._text.insert("end", token[1:-1], base_tags + ("code_inline",))
            cursor = match.end()
        if cursor < len(line):
            self._text.insert("end", line[cursor:], base_tags)


class _CollapsibleSection(ctk.CTkFrame):
    def __init__(
        self,
        master,
        *,
        title: str,
        body: str,
        text_color: str,
        bg_color: str,
        start_expanded: bool = False,
        code_mode: bool = False,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._expanded = False
        self._body = _RichText(
            self,
            body,
            bg_color=bg_color,
            text_color=text_color,
            code_mode=code_mode,
            max_rows=200,
        )
        self._toggle = ctk.CTkButton(
            self,
            text=f"> {title}",
            fg_color="transparent",
            hover_color=_CLR_CARD,
            anchor="w",
            text_color=text_color,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            command=self.toggle,
        )
        self._toggle.pack(fill="x")
        if start_expanded:
            self.expand()

    def toggle(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self) -> None:
        if self._expanded:
            return
        self._toggle.configure(text="v " + self._toggle.cget("text")[2:])
        self._body.pack(fill="x", padx=(18, 2), pady=(4, 2))
        self._expanded = True

    def collapse(self) -> None:
        if not self._expanded:
            return
        self._toggle.configure(text="> " + self._toggle.cget("text")[2:])
        self._body.pack_forget()
        self._expanded = False


class _PromptBubble(ctk.CTkFrame):
    def __init__(self, master, prompt: str, timestamp: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._expanded = False
        self._prompt = prompt.strip()
        self._preview_text = _prompt_preview(self._prompt)

        self._bubble = ctk.CTkFrame(self, fg_color=_CLR_USER_BG, corner_radius=16)
        self._bubble.pack(anchor="e", padx=(80, 4), pady=(0, 10))

        top = ctk.CTkFrame(self._bubble, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            top,
            text="Prompt",
            text_color="#dbe6ff",
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left")

        self._toggle_btn = ctk.CTkButton(
            top,
            text="Tamamini Ac",
            width=72,
            height=22,
            fg_color="transparent",
            hover_color=_CLR_CARD,
            text_color=_CLR_MUTED,
            command=self.toggle,
        )
        self._toggle_btn.pack(side="right")

        self._preview = ctk.CTkLabel(
            self._bubble,
            text=self._preview_text,
            justify="left",
            wraplength=340,
            text_color=COLORS["text_primary"],
            font=ctk.CTkFont(size=13),
        )
        self._preview.pack(padx=14, pady=(0, 8))

        self._full = _RichText(
            self._bubble,
            self._prompt,
            bg_color=_CLR_USER_BG,
            text_color=COLORS["text_primary"],
            code_mode=True,
            max_rows=200,
        )

        ctk.CTkLabel(
            self._bubble,
            text=timestamp,
            text_color=_CLR_MUTED,
            font=ctk.CTkFont(size=10),
        ).pack(anchor="e", padx=12, pady=(0, 8))

    def toggle(self) -> None:
        if self._expanded:
            self._full.pack_forget()
            self._toggle_btn.configure(text="Tamamini Ac")
            self._expanded = False
        else:
            self._full.pack(fill="x", padx=14, pady=(0, 8))
            self._toggle_btn.configure(text="Gizle")
            self._expanded = True


class _PendingEntry(ctk.CTkFrame):
    _SPINNER = ["|", "/", "-", "\\"]

    def __init__(
        self,
        master,
        *,
        field: str,
        product_name: str,
        field_labels: dict[str, str],
        model_name: str,
        on_cancel: Callable[[], None] | None,
        **kwargs,
    ):
        super().__init__(master, fg_color=_CLR_AI_BG, corner_radius=14, **kwargs)
        self._running = True
        self._frame_idx = 0
        self._started_at = time.time()
        self._on_cancel = on_cancel

        field_text = field_labels.get(field, field)
        timestamp = datetime.now().strftime("%H:%M:%S")
        short_product = product_name if len(product_name) <= 64 else product_name[:61] + "..."

        ctk.CTkLabel(
            self,
            text=_short_model_name(model_name),
            text_color=_CLR_MODEL,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 2))

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(meta, text=f"[{field_text}] {short_product}", text_color=_CLR_MUTED, font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkLabel(meta, text=timestamp, text_color=_CLR_MUTED, font=ctk.CTkFont(size=11)).pack(side="right")

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=14, pady=(0, 12))
        self._status = ctk.CTkLabel(bar, text="Thinking |", text_color=_CLR_SUCCESS, font=ctk.CTkFont(size=14))
        self._status.pack(side="left")
        self._elapsed = ctk.CTkLabel(bar, text="0.0s", text_color=_CLR_MUTED, font=ctk.CTkFont(size=11))
        self._elapsed.pack(side="left", padx=(10, 0))

        if on_cancel is not None:
            ctk.CTkButton(
                bar,
                text="Stop",
                width=56,
                height=26,
                fg_color="#3a1f1f",
                hover_color="#4c2424",
                text_color="#ffd7d7",
                corner_radius=999,
                command=on_cancel,
            ).pack(side="right")

        self._animate()

    def _animate(self) -> None:
        if not self._running:
            return
        self._frame_idx = (self._frame_idx + 1) % len(self._SPINNER)
        self._status.configure(text=f"Thinking {self._SPINNER[self._frame_idx]}")
        self._elapsed.configure(text=_format_duration(time.time() - self._started_at))
        self.after(120, self._animate)

    def stop(self) -> None:
        self._running = False

    def get_elapsed(self) -> float:
        return time.time() - self._started_at


class AIChatPanel(ctk.CTkFrame):
    _FIELD_LABELS = {
        "all": "Tam Urun",
        "name": "Ad",
        "meta_title": "Meta Title",
        "meta_desc": "Meta Description",
        "desc_tr": "Aciklama (TR)",
        "desc_en": "Aciklama (EN)",
    }

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_primary"])
        super().__init__(master, **kwargs)

        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=38)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="AI Chat",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_CLR_SUCCESS,
        ).pack(side="left", padx=10, pady=6)

        self._status_lbl = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=_CLR_MUTED,
        )
        self._status_lbl.pack(side="left", padx=(2, 0))

        self._count_lbl = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=_CLR_MUTED,
        )
        self._count_lbl.pack(side="right", padx=8)

        ctk.CTkButton(
            header,
            text="Clear",
            width=60,
            height=24,
            fg_color=COLORS["border"],
            hover_color=COLORS["bg_card"],
            command=self.clear,
        ).pack(side="right", padx=6, pady=6)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=6, pady=6)

        self._entries: list[ctk.CTkFrame] = []
        self._pending: Optional[_PendingEntry] = None

    def start_thinking(
        self,
        field: str,
        product_name: str,
        *,
        prompt: str = "",
        model_name: str = "",
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        if prompt.strip():
            prompt_bubble = _PromptBubble(self._scroll, prompt, datetime.now().strftime("%H:%M:%S"))
            prompt_bubble.pack(fill="x")
            self._entries.append(prompt_bubble)

        if self._pending is not None:
            self._pending.stop()
            self._pending.destroy()
            self._pending = None

        self._pending = _PendingEntry(
            self._scroll,
            field=field,
            product_name=product_name,
            field_labels=self._FIELD_LABELS,
            model_name=model_name,
            on_cancel=on_cancel,
        )
        self._pending.pack(fill="x", pady=(0, 10))
        self._entries.append(self._pending)
        self._status_lbl.configure(text="Request running")
        self._update_count()
        self._scroll_to_bottom()

    def complete_entry(
        self,
        field: str,
        product_name: str,
        *,
        prompt: str = "",
        thinking: str = "",
        result: str = "",
        error: str = "",
        model_name: str = "",
        meta: Optional[dict] = None,
    ) -> None:
        elapsed = 0.0
        if self._pending is not None:
            elapsed = self._pending.get_elapsed()
            self._pending.stop()
            self._pending.destroy()
            try:
                self._entries.remove(self._pending)
            except ValueError:
                pass
            self._pending = None

        entry = self._build_completed_entry(
            field=field,
            product_name=product_name,
            prompt=prompt,
            thinking=thinking,
            result=result,
            error=error,
            elapsed=elapsed,
            model_name=model_name,
            meta=meta or {},
        )
        entry.pack(fill="x", pady=(0, 10))
        self._entries.append(entry)
        self._status_lbl.configure(text="")
        self._update_count()
        self._scroll_to_bottom()

    def add_entry(
        self,
        field: str,
        product_name: str,
        *,
        prompt: str = "",
        thinking: str = "",
        result: str = "",
        error: str = "",
        model_name: str = "",
        meta: Optional[dict] = None,
    ) -> None:
        entry = self._build_completed_entry(
            field=field,
            product_name=product_name,
            prompt=prompt,
            thinking=thinking,
            result=result,
            error=error,
            elapsed=0.0,
            model_name=model_name,
            meta=meta or {},
        )
        entry.pack(fill="x", pady=(0, 10))
        self._entries.append(entry)
        self._update_count()
        self._scroll_to_bottom()

    def cancel_pending(self, *, reason: str) -> None:
        if self._pending is None:
            return
        elapsed = self._pending.get_elapsed()
        self._pending.stop()
        self._pending.destroy()
        try:
            self._entries.remove(self._pending)
        except ValueError:
            pass
        self._pending = None

        entry = self._build_completed_entry(
            field="all",
            product_name="",
            prompt="",
            thinking="",
            result="",
            error=reason,
            elapsed=elapsed,
            model_name="",
            meta={"finish_reason": "cancelled"},
        )
        entry.pack(fill="x", pady=(0, 10))
        self._entries.append(entry)
        self._status_lbl.configure(text="")
        self._update_count()
        self._scroll_to_bottom()

    def clear(self) -> None:
        if self._pending is not None:
            self._pending.stop()
            self._pending.destroy()
            self._pending = None
        for entry in self._entries:
            try:
                entry.destroy()
            except Exception:
                pass
        self._entries.clear()
        self._status_lbl.configure(text="")
        self._update_count()

    def _build_completed_entry(
        self,
        *,
        field: str,
        product_name: str,
        prompt: str,
        thinking: str,
        result: str,
        error: str,
        elapsed: float,
        model_name: str,
        meta: dict,
    ) -> ctk.CTkFrame:
        is_error = bool(error)
        card = ctk.CTkFrame(
            self._scroll,
            fg_color=_CLR_AI_BG if not is_error else "#241719",
            corner_radius=14,
        )

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(
            top,
            text=_short_model_name(model_name),
            text_color=_CLR_MODEL,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")

        field_text = self._FIELD_LABELS.get(field, field)
        details = f"[{field_text}]"
        if product_name:
            details += f" {product_name}"
        ctk.CTkLabel(
            top,
            text=details.strip(),
            text_color=_CLR_MUTED,
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            top,
            text=datetime.now().strftime("%H:%M:%S"),
            text_color=_CLR_MUTED,
            font=ctk.CTkFont(size=10),
        ).pack(side="right")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 8))

        if thinking.strip():
            thought_title = f"Thought for {_format_duration(elapsed)}"
            _CollapsibleSection(
                body,
                title=thought_title,
                body=thinking.strip(),
                text_color=_CLR_THINK,
                bg_color=_CLR_THINK_BG,
                start_expanded=False,
            ).pack(fill="x", pady=(0, 8))

        main_text = error.strip() if is_error else result.strip()
        content = _RichText(
            body,
            main_text or ("No output" if not is_error else "Unknown error"),
            bg_color=_CLR_AI_BG if not is_error else "#241719",
            text_color=_CLR_ERROR if is_error else _CLR_SUCCESS,
            code_mode=(not is_error and _looks_like_json(main_text)),
        )
        content.pack(fill="x")

        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=14, pady=(8, 12))

        metrics = self._build_metrics(footer, meta=meta, elapsed=elapsed)
        if metrics:
            metrics.pack(side="left")

        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.pack(side="right")

        copy_text = main_text
        ctk.CTkButton(
            actions,
            text="Copy",
            width=52,
            height=24,
            fg_color="transparent",
            hover_color=_CLR_CARD,
            text_color=_CLR_MUTED,
            command=lambda text=copy_text: self._copy_to_clipboard(text),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            actions,
            text="Delete",
            width=60,
            height=24,
            fg_color="transparent",
            hover_color=_CLR_CARD,
            text_color=_CLR_MUTED,
            command=lambda target=card: self._delete_entry(target),
        ).pack(side="left", padx=2)

        return card

    def _build_metrics(self, master, *, meta: dict, elapsed: float) -> ctk.CTkFrame | None:
        values: list[str] = []

        tps = meta.get("tokens_per_second")
        if isinstance(tps, (int, float)) and tps > 0:
            values.append(f"{tps:.2f} tok/sec")

        output_tokens = meta.get("output_tokens") or meta.get("total_tokens")
        if isinstance(output_tokens, (int, float)) and output_tokens > 0:
            values.append(f"{_human_number(int(output_tokens))} tokens")

        if elapsed > 0:
            values.append(_format_duration(elapsed))

        stop_reason = meta.get("stop_reason") or meta.get("finish_reason")
        if stop_reason:
            values.append(f"Stop: {stop_reason}")

        if not values:
            return None

        row = ctk.CTkFrame(master, fg_color="transparent")
        for text in values:
            _MetricPill(row, text=text).pack(side="left", padx=(0, 6))
        return row

    def _delete_entry(self, target: ctk.CTkFrame) -> None:
        try:
            target.destroy()
        finally:
            try:
                self._entries.remove(target)
            except ValueError:
                pass
            self._update_count()

    def _copy_to_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    def _scroll_to_bottom(self) -> None:
        self.after(50, lambda: self._scroll._parent_canvas.yview_moveto(1.0))

    def _update_count(self) -> None:
        total = len(self._entries)
        pending = 1 if self._pending is not None else 0
        parts = []
        if total:
            parts.append(f"{total} messages")
        if pending:
            parts.append("running")
        self._count_lbl.configure(text=" | ".join(parts))
