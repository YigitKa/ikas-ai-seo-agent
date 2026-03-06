import customtkinter as ctk

from core.models import SeoSuggestion
from ui.themes.dark import COLORS


class DiffViewer(ctk.CTkFrame):
    def __init__(self, master, on_approve=None, on_reject=None, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_primary"], **kwargs)
        self._on_approve = on_approve
        self._on_reject = on_reject
        self._current_suggestion: SeoSuggestion | None = None

        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(
            title_frame, text="Oneri Karsilastirmasi",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=10, pady=5)
        columns.grid_columnconfigure(0, weight=1)
        columns.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(columns, text="Orijinal", text_color=COLORS["error"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(columns, text="Oneri", text_color=COLORS["success"]).grid(row=0, column=1, sticky="w")

        self._original_text = ctk.CTkTextbox(
            columns, fg_color=COLORS["input_bg"],
            text_color=COLORS["text_secondary"], height=300,
        )
        self._original_text.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=5)

        self._suggested_text = ctk.CTkTextbox(
            columns, fg_color=COLORS["input_bg"],
            text_color=COLORS["text_primary"], height=300,
        )
        self._suggested_text.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=5)
        columns.grid_rowconfigure(1, weight=1)

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

    def show_suggestion(self, suggestion: SeoSuggestion) -> None:
        self._current_suggestion = suggestion

        original = (
            f"Ad: {suggestion.original_name}\n\n"
            f"Meta Title: {suggestion.original_meta_title or '-'}\n\n"
            f"Meta Description: {suggestion.original_meta_description or '-'}\n\n"
            f"Aciklama:\n{suggestion.original_description}"
        )
        suggested = (
            f"Ad: {suggestion.suggested_name or '-'}\n\n"
            f"Meta Title: {suggestion.suggested_meta_title}\n\n"
            f"Meta Description: {suggestion.suggested_meta_description}\n\n"
            f"Aciklama:\n{suggestion.suggested_description}"
        )

        self._original_text.delete("1.0", "end")
        self._original_text.insert("1.0", original)

        self._suggested_text.delete("1.0", "end")
        self._suggested_text.insert("1.0", suggested)

    def get_edited_suggestion(self) -> str:
        return self._suggested_text.get("1.0", "end").strip()

    def _approve(self) -> None:
        if self._on_approve and self._current_suggestion:
            self._on_approve(self._current_suggestion)

    def _reject(self) -> None:
        if self._on_reject and self._current_suggestion:
            self._on_reject(self._current_suggestion)

    def clear(self) -> None:
        self._current_suggestion = None
        self._original_text.delete("1.0", "end")
        self._suggested_text.delete("1.0", "end")
