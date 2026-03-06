import customtkinter as ctk

from ui.themes.dark import COLORS


class SettingsPanel(ctk.CTkToplevel):
    def __init__(self, master, config, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Ayarlar")
        self.geometry("500x600")
        self.configure(fg_color=COLORS["bg_primary"])
        self._on_save = on_save

        main = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_primary"])
        main.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main, text="ikas API Ayarlari",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 10))

        self._store_name = self._add_field(main, "Magaza Adi:", config.ikas_store_name)
        self._client_id = self._add_field(main, "Client ID:", config.ikas_client_id)
        self._client_secret = self._add_field(main, "Client Secret:", config.ikas_client_secret, show="*")

        ctk.CTkLabel(main, text="Anthropic API",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(20, 10))

        self._api_key = self._add_field(main, "API Key:", config.anthropic_api_key, show="*")

        self._model_var = ctk.StringVar(value="claude-haiku-4-5-20251001")
        ctk.CTkLabel(main, text="Model:", text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(5, 0))
        ctk.CTkOptionMenu(
            main, variable=self._model_var,
            values=["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250514", "claude-opus-4-5-20250514"],
            fg_color=COLORS["input_bg"],
        ).pack(fill="x", pady=5)

        ctk.CTkLabel(main, text="Genel Ayarlar",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(20, 10))

        self._language_var = ctk.StringVar(value=config.store_language)
        ctk.CTkLabel(main, text="Dil:", text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(5, 0))
        ctk.CTkSegmentedButton(
            main, values=["tr", "en"], variable=self._language_var,
        ).pack(fill="x", pady=5)

        self._keywords = self._add_field(main, "Hedef Keywordler (virgul ile):",
                                          ",".join(config.seo_target_keywords))

        self._dry_run_var = ctk.BooleanVar(value=config.dry_run)
        ctk.CTkCheckBox(
            main, text="Dry Run (ikas'a yazma)",
            variable=self._dry_run_var,
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=10)

        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)

        ctk.CTkButton(
            btn_frame, text="Kaydet", fg_color=COLORS["success"],
            command=self._save,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Baglanti Testi", fg_color=COLORS["accent"],
            command=self._test,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Kapat",
            command=self.destroy,
        ).pack(side="right", padx=5)

    def _add_field(self, parent, label: str, value: str, show: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(5, 0))
        entry = ctk.CTkEntry(parent, fg_color=COLORS["input_bg"], text_color=COLORS["text_primary"])
        if show:
            entry.configure(show=show)
        entry.insert(0, value)
        entry.pack(fill="x", pady=2)
        return entry

    def _save(self) -> None:
        if self._on_save:
            self._on_save({
                "store_name": self._store_name.get(),
                "client_id": self._client_id.get(),
                "client_secret": self._client_secret.get(),
                "api_key": self._api_key.get(),
                "model": self._model_var.get(),
                "language": self._language_var.get(),
                "keywords": self._keywords.get(),
                "dry_run": self._dry_run_var.get(),
            })
        self.destroy()

    def _test(self) -> None:
        ctk.CTkLabel(self, text="Baglanti test ediliyor...",
                     text_color=COLORS["warning"]).pack(pady=5)
