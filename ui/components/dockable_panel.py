"""Dockable, collapsible, resizable panel component."""

from typing import Callable, Optional

import customtkinter as ctk

from ui.themes.dark import COLORS


class DockablePanel(ctk.CTkFrame):
    """Panel wrapper with title bar supporting collapse/expand and detach/re-dock."""

    HEADER_HEIGHT = 32

    def __init__(
        self,
        master,
        title: str = "Panel",
        collapsible: bool = True,
        detachable: bool = True,
        on_state_change: Optional[Callable] = None,
        **kwargs,
    ):
        kwargs.setdefault("fg_color", COLORS["bg_secondary"])
        kwargs.setdefault("corner_radius", 8)
        super().__init__(master, **kwargs)

        self._title = title
        self._collapsed = False
        self._detached = False
        self._collapsible = collapsible
        self._detachable = detachable
        self._on_state_change = on_state_change
        self._float_window: Optional[ctk.CTkToplevel] = None

        # ── Header bar ──
        self._header = ctk.CTkFrame(
            self, fg_color=COLORS["bg_card"], height=self.HEADER_HEIGHT, corner_radius=6,
        )
        self._header.pack(fill="x", padx=3, pady=(3, 0))
        self._header.pack_propagate(False)
        self._header.bind("<Double-Button-1>", lambda e: self.toggle_collapse())

        if self._collapsible:
            self._collapse_btn = ctk.CTkButton(
                self._header, text="▾", width=24, height=24,
                fg_color="transparent", hover_color=COLORS["border"],
                text_color=COLORS["text_secondary"],
                command=self.toggle_collapse,
                font=ctk.CTkFont(size=13),
                corner_radius=4,
            )
            self._collapse_btn.pack(side="left", padx=(4, 0), pady=3)

        self._title_label = ctk.CTkLabel(
            self._header, text=title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self._title_label.pack(side="left", padx=6, pady=3)
        self._title_label.bind("<Double-Button-1>", lambda e: self.toggle_collapse())

        if self._detachable:
            self._detach_btn = ctk.CTkButton(
                self._header, text="\u29C9", width=24, height=24,
                fg_color="transparent", hover_color=COLORS["border"],
                text_color=COLORS["text_secondary"],
                command=self.toggle_detach,
                font=ctk.CTkFont(size=13),
                corner_radius=4,
            )
            self._detach_btn.pack(side="right", padx=(0, 4), pady=3)

        # ── Content frame ── (add child widgets here)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=3, pady=(2, 3))

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def header(self) -> ctk.CTkFrame:
        """Access the header frame to add custom buttons."""
        return self._header

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    @property
    def is_detached(self) -> bool:
        return self._detached

    def toggle_collapse(self) -> None:
        """Toggle panel collapsed/expanded state."""
        if self._detached:
            return
        if self._collapsed:
            self._expand()
        else:
            self._collapse()

    def toggle_detach(self) -> None:
        """Toggle between docked and floating states."""
        if self._detached:
            self._redock()
        else:
            self._detach()

    # ── Collapse / Expand ─────────────────────────────────────────────────────

    def _collapse(self) -> None:
        if self._collapsed:
            return
        self.content.pack_forget()
        if self._collapsible:
            self._collapse_btn.configure(text="\u25B8")
        self._collapsed = True
        if self._on_state_change:
            self._on_state_change()

    def _expand(self) -> None:
        if not self._collapsed:
            return
        self.content.pack(fill="both", expand=True, padx=3, pady=(2, 3))
        if self._collapsible:
            self._collapse_btn.configure(text="\u25BE")
        self._collapsed = False
        if self._on_state_change:
            self._on_state_change()

    # ── Detach / Re-dock ──────────────────────────────────────────────────────

    def _detach(self) -> None:
        if self._detached:
            return
        self._detached = True

        w = max(500, self.winfo_width())
        h = max(400, self.winfo_height())

        self._float_window = ctk.CTkToplevel(self.winfo_toplevel())
        self._float_window.title(self._title)
        self._float_window.geometry(f"{w}x{h}")
        self._float_window.configure(fg_color=COLORS["bg_primary"])
        self._float_window.protocol("WM_DELETE_WINDOW", self._redock)
        self._float_window.after(50, lambda: self._float_window.attributes("-topmost", True))
        self._float_window.after(250, lambda: self._float_window.attributes("-topmost", False))

        # Move content to floating window
        self.content.pack_forget()
        self.content.pack(in_=self._float_window, fill="both", expand=True, padx=5, pady=5)

        # Placeholder in main layout
        self._placeholder = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=6)
        self._placeholder.pack(fill="both", expand=True, padx=3, pady=(2, 3))
        ctk.CTkLabel(
            self._placeholder,
            text=f"\U0001F4CC  {self._title}\n(ayrilmis pencere \u2014 kapatinca geri doner)",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=11),
            wraplength=200,
        ).pack(expand=True, padx=10, pady=20)

        if self._detachable:
            self._detach_btn.configure(text="\U0001F4CC")
        if self._collapsible:
            self._collapse_btn.configure(state="disabled")

        if self._on_state_change:
            self._on_state_change()

    def _redock(self) -> None:
        if not self._detached:
            return
        self._detached = False

        # Remove placeholder
        if hasattr(self, "_placeholder") and self._placeholder.winfo_exists():
            self._placeholder.destroy()

        # Move content back
        self.content.pack_forget()
        self.content.pack(in_=self, fill="both", expand=True, padx=3, pady=(2, 3))

        # Close floating window
        if self._float_window:
            try:
                self._float_window.destroy()
            except Exception:
                pass
            self._float_window = None

        if self._detachable:
            self._detach_btn.configure(text="\u29C9")
        if self._collapsible:
            self._collapse_btn.configure(state="normal")

        if self._on_state_change:
            self._on_state_change()
