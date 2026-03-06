"""AI Chat Panel – shows a chat-style log of AI requests and responses."""

from datetime import datetime
from typing import Optional

import customtkinter as ctk

from ui.themes.dark import COLORS

# Chat-specific colours
_CLR_PROMPT = "#5c9aff"      # soft blue for user prompt
_CLR_THINKING = "#80cbc4"    # teal for thinking
_CLR_RESULT = "#69f0ae"      # green for success
_CLR_ERROR = "#ff5252"       # red for error
_CLR_FIELD_LABEL = "#ffd740" # amber for field label
_CLR_TIMESTAMP = "#616161"   # dim grey
_CLR_SEPARATOR = COLORS["border"]


class _CollapsibleSection(ctk.CTkFrame):
    """A section with a clickable header that can expand/collapse its body text."""

    def __init__(
        self,
        master,
        icon: str,
        title: str,
        body: str,
        color: str,
        start_expanded: bool = False,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._expanded = False
        self._color = color

        # Header button
        self._btn = ctk.CTkButton(
            self,
            text=f"▶ {icon} {title}",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color="transparent",
            hover_color=COLORS["bg_card"],
            text_color=color,
            anchor="w",
            height=26,
            command=self._toggle,
        )
        self._btn.pack(fill="x")

        # Body textbox (hidden by default)
        self._text = ctk.CTkTextbox(
            self,
            fg_color=COLORS["input_bg"],
            text_color=color,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            height=1,  # will auto-size
            activate_scrollbars=False,
        )
        self._body_content = body

        if start_expanded:
            self._expand()

    def _toggle(self) -> None:
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _expand(self) -> None:
        if self._expanded:
            return
        self._text.pack(fill="x", padx=(18, 2), pady=(0, 4))
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", self._body_content)
        self._text.configure(state="disabled")
        # Auto-height: count lines
        lines = self._body_content.count("\n") + 1
        h = min(max(lines * 18, 36), 300)
        self._text.configure(height=h)
        icon_title = self._btn.cget("text")[2:]  # strip "▶ " or "▼ "
        self._btn.configure(text=f"▼ {icon_title}")
        self._expanded = True

    def _collapse(self) -> None:
        if not self._expanded:
            return
        self._text.pack_forget()
        icon_title = self._btn.cget("text")[2:]  # strip "▼ "
        self._btn.configure(text=f"▶ {icon_title}")
        self._expanded = False


class AIChatPanel(ctk.CTkFrame):
    """Scrollable chat-style panel that logs every AI request/response cycle."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_primary"])
        super().__init__(master, **kwargs)

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=30)
        toolbar.pack(fill="x", padx=5, pady=(5, 0))

        ctk.CTkButton(
            toolbar, text="Temizle", width=55, height=22,
            font=ctk.CTkFont(size=10),
            fg_color=COLORS["border"], hover_color=COLORS["bg_card"],
            command=self.clear,
        ).pack(side="right", padx=2)

        self._entry_count_label = ctk.CTkLabel(
            toolbar, text="",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_secondary"],
        )
        self._entry_count_label.pack(side="left", padx=5)

        # Scrollable area for chat entries
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
        )
        self._scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self._entries: list[ctk.CTkFrame] = []

    def add_entry(
        self,
        field: str,
        product_name: str,
        prompt: str,
        thinking: str = "",
        result: str = "",
        error: str = "",
    ) -> None:
        """Add a new chat entry for an AI call.
        
        Args:
            field: Which field was rewritten (e.g. "meta_title", "all" for full product)
            product_name: The product name for context
            prompt: The prompt sent to the AI
            thinking: The AI's thinking/reasoning text (if any)
            result: The successful result (JSON or value string)
            error: Error message if the call failed
        """
        ts = datetime.now().strftime("%H:%M:%S")

        # Container card
        card = ctk.CTkFrame(
            self._scroll,
            fg_color=COLORS["bg_secondary"],
            corner_radius=8,
        )
        card.pack(fill="x", padx=2, pady=(0, 8))

        # ── Header row: timestamp + field + product ──
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(6, 2))

        field_labels = {
            "all": "Tam Urun",
            "name": "Ad",
            "meta_title": "Meta Title",
            "meta_desc": "Meta Description",
            "desc_tr": "Aciklama (TR)",
            "desc_en": "Aciklama (EN)",
        }
        field_text = field_labels.get(field, field)

        ctk.CTkLabel(
            header, text=ts,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=_CLR_TIMESTAMP,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header, text=f"[{field_text}]",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_CLR_FIELD_LABEL,
        ).pack(side="left", padx=(0, 6))

        product_display = product_name[:50] + "..." if len(product_name) > 50 else product_name
        ctk.CTkLabel(
            header, text=product_display,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        # Status indicator
        if error:
            status_text = "HATA"
            status_color = _CLR_ERROR
        else:
            status_text = "OK"
            status_color = _CLR_RESULT
        ctk.CTkLabel(
            header, text=status_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=status_color,
        ).pack(side="right", padx=4)

        # ── Separator ──
        sep = ctk.CTkFrame(card, fg_color=_CLR_SEPARATOR, height=1)
        sep.pack(fill="x", padx=8, pady=2)

        # ── Collapsible sections ──
        sections_frame = ctk.CTkFrame(card, fg_color="transparent")
        sections_frame.pack(fill="x", padx=4, pady=(0, 6))

        # 1. Prompt (collapsed by default)
        if prompt:
            _CollapsibleSection(
                sections_frame,
                icon="📤",
                title="Prompt",
                body=prompt.strip(),
                color=_CLR_PROMPT,
                start_expanded=False,
            ).pack(fill="x")

        # 2. Thinking (collapsed by default)
        if thinking and thinking.strip():
            _CollapsibleSection(
                sections_frame,
                icon="🧠",
                title="Dusunce Sureci",
                body=thinking.strip(),
                color=_CLR_THINKING,
                start_expanded=False,
            ).pack(fill="x")

        # 3. Result or Error (expanded by default)
        if error:
            _CollapsibleSection(
                sections_frame,
                icon="❌",
                title="Hata",
                body=error.strip(),
                color=_CLR_ERROR,
                start_expanded=True,
            ).pack(fill="x")
        elif result:
            _CollapsibleSection(
                sections_frame,
                icon="✅",
                title="Sonuc",
                body=result.strip(),
                color=_CLR_RESULT,
                start_expanded=True,
            ).pack(fill="x")

        self._entries.append(card)
        self._update_count()

        # Auto-scroll to bottom
        self.after(50, lambda: self._scroll._parent_canvas.yview_moveto(1.0))

    def clear(self) -> None:
        """Remove all chat entries."""
        for entry in self._entries:
            entry.destroy()
        self._entries.clear()
        self._update_count()

    def _update_count(self) -> None:
        count = len(self._entries)
        self._entry_count_label.configure(
            text=f"{count} istek" if count else "",
        )
