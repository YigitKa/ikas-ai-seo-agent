"""Settings panel with multi-AI-provider support."""

import threading

import customtkinter as ctk

from core.provider_service import (
    PROVIDER_LABELS,
    discover_provider_models,
    get_provider_model_options,
    provider_key_from_label,
    test_settings_connection,
)
from core.prompt_store import (
    get_prompt_editor_groups,
    get_prompt_editor_meta,
    load_prompt_template,
    reset_prompt_template,
    save_prompt_template,
)
from ui.themes.dark import COLORS


class SettingsPanel(ctk.CTkToplevel):
    def __init__(self, master, config, on_save=None, on_test=None, on_discover_provider_models=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Ayarlar")
        self.geometry("900x920")
        self.resizable(True, True)
        self.configure(fg_color=COLORS["bg_primary"])
        self._on_save = on_save
        self._on_test = on_test
        self._on_discover_provider_models = on_discover_provider_models
        self._config = config
        self._prompt_editors: dict[str, ctk.CTkTextbox] = {}

        # Ollama model list (populated by discovery)
        self._ollama_models: list[str] = []
        self._lm_studio_models: list[str] = []

        main = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_primary"])
        main.pack(fill="both", expand=True, padx=20, pady=20)

        # â”€â”€ ikas API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._section(main, "ikas API Ayarlari")
        self._store_name = self._field(main, "Magaza Adi:", config.ikas_store_name)
        self._client_id = self._field(main, "Client ID:", config.ikas_client_id)
        self._client_secret = self._field(main, "Client Secret:", config.ikas_client_secret, show="*")

        # â”€â”€ AI Provider â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._section(main, "AI Provider", top_pad=20)

        ctk.CTkLabel(main, text="Provider:", text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(5, 0))
        self._provider_var = ctk.StringVar(value=PROVIDER_LABELS.get(config.ai_provider, "None (yalnizca analiz)"))
        self._provider_menu = ctk.CTkOptionMenu(
            main,
            variable=self._provider_var,
            values=list(PROVIDER_LABELS.values()),
            fg_color=COLORS["input_bg"],
            command=self._on_provider_change,
        )
        self._provider_menu.pack(fill="x", pady=5)

        # Dynamic provider fields container
        self._provider_frame = ctk.CTkFrame(main, fg_color=COLORS["bg_secondary"], corner_radius=8)
        self._provider_frame.pack(fill="x", pady=(5, 0))

        # â”€â”€ Shared temperature/max_tokens â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._section(main, "Model Parametreleri", top_pad=20)
        params_row = ctk.CTkFrame(main, fg_color="transparent")
        params_row.pack(fill="x", pady=5)
        params_row.grid_columnconfigure(0, weight=1)
        params_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(params_row, text="Temperature (0-1):", text_color=COLORS["text_secondary"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(params_row, text="Max Tokens:", text_color=COLORS["text_secondary"]).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self._temperature = ctk.CTkEntry(params_row, fg_color=COLORS["input_bg"], text_color=COLORS["text_primary"])
        self._temperature.insert(0, str(config.ai_temperature))
        self._temperature.grid(row=1, column=0, sticky="ew")
        self._max_tokens = ctk.CTkEntry(params_row, fg_color=COLORS["input_bg"], text_color=COLORS["text_primary"])
        self._max_tokens.insert(0, str(config.ai_max_tokens))
        self._max_tokens.grid(row=1, column=1, sticky="ew", padx=(10, 0))

        self._thinking_mode_var = ctk.BooleanVar(value=config.ai_thinking_mode)
        ctk.CTkCheckBox(
            main, text="AI Thinking Mode (dÃ¼ÅŸÃ¼nme zinciri)",
            variable=self._thinking_mode_var,
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=(10, 0))

        # â”€â”€ General â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._section(main, "Genel Ayarlar", top_pad=20)
        self._languages = self._field(main, "Magaza Dilleri (virgul ile):", ",".join(config.store_languages))
        self._keywords = self._field(main, "Hedef Keywordler (virgul ile):", ",".join(config.seo_target_keywords))
        self._dry_run_var = ctk.BooleanVar(value=config.dry_run)
        ctk.CTkCheckBox(
            main, text="Dry Run (ikas'a yazma)",
            variable=self._dry_run_var,
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=10)

        self._section(main, "AI Promptlari", top_pad=20)
        ctk.CTkLabel(
            main,
            text="Aciklama ve ceviri promptlarini burada duzenleyebilirsin. Kaydedilen degisiklikler bir sonraki AI isteginde kullanilir.",
            text_color=COLORS["text_secondary"],
            wraplength=820,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))
        self._build_prompt_editor(main)

        # â”€â”€ Buttons â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20)

        ctk.CTkButton(btn_frame, text="Kaydet", fg_color=COLORS["success"], command=self._save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Baglanti Testi", fg_color=COLORS["accent"], command=self._test).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Kapat", command=self.destroy).pack(side="right", padx=5)

        self._status_label = ctk.CTkLabel(main, text="", text_color=COLORS["text_secondary"], wraplength=500)
        self._status_label.pack(anchor="w", pady=5)

        # Draw initial provider fields
        self._on_provider_change(self._provider_var.get())

        # Bring window to front
        self.after(50, self._bring_to_front)

    def _bring_to_front(self) -> None:
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

    # â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _section(self, parent, text: str, top_pad: int = 0) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w", pady=(top_pad, 6))

    def _field(self, parent, label: str, value: str, show: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(4, 0))
        entry = ctk.CTkEntry(parent, fg_color=COLORS["input_bg"], text_color=COLORS["text_primary"])
        if show:
            entry.configure(show=show)
        entry.insert(0, value)
        entry.pack(fill="x", pady=2)
        return entry

    def _inner_field(self, parent, label: str, value: str, show: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(4, 0), padx=10)
        entry = ctk.CTkEntry(parent, fg_color=COLORS["input_bg"], text_color=COLORS["text_primary"])
        if show:
            entry.configure(show=show)
        entry.insert(0, value)
        entry.pack(fill="x", pady=2, padx=10)
        return entry

    def _inner_dropdown(self, parent, label: str, value: str, values: list) -> ctk.StringVar:
        ctk.CTkLabel(parent, text=label, text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(4, 0), padx=10)
        var = ctk.StringVar(value=value if value in values else (values[0] if values else ""))
        ctk.CTkOptionMenu(parent, variable=var, values=values, fg_color=COLORS["input_bg"]).pack(fill="x", pady=2, padx=10)
        return var

    def _inner_entry_var(self, parent, label: str, value: str, show: str = "") -> ctk.CTkEntry:
        """Same as _inner_field â€” kept for naming clarity."""
        return self._inner_field(parent, label, value, show=show)

    def _set_status(self, text: str, color: str = "text_secondary") -> None:
        self._status_label.configure(text=text, text_color=COLORS[color])

    def _build_prompt_editor(self, parent) -> None:
        container = ctk.CTkFrame(parent, fg_color=COLORS["bg_secondary"], corner_radius=10)
        container.pack(fill="both", expand=True, pady=(0, 8))

        tabs = ctk.CTkTabview(container, fg_color=COLORS["bg_secondary"], segmented_button_fg_color=COLORS["input_bg"])
        tabs.pack(fill="both", expand=True, padx=10, pady=10)

        for group_label, prompt_keys in get_prompt_editor_groups():
            tab = tabs.add(group_label)
            for prompt_key in prompt_keys:
                self._add_prompt_editor_card(tab, prompt_key)

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(
            actions,
            text="Promptlari Kaydet",
            fg_color=COLORS["accent"],
            command=self._save_prompt_templates,
        ).pack(side="right")
        ctk.CTkButton(
            actions,
            text="Tumunu Varsayilana Don",
            fg_color=COLORS["border"],
            hover_color=COLORS["bg_card"],
            command=self._reset_all_prompt_editors,
        ).pack(side="right", padx=(0, 8))

    def _add_prompt_editor_card(self, parent, prompt_key: str) -> None:
        meta = get_prompt_editor_meta(prompt_key)
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_primary"], corner_radius=8)
        card.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            header,
            text=str(meta["title"]),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")
        ctk.CTkButton(
            header,
            text="Varsayilan",
            width=92,
            height=28,
            fg_color=COLORS["border"],
            hover_color=COLORS["bg_card"],
            command=lambda key=prompt_key: self._reset_prompt_editor(key),
        ).pack(side="right")

        ctk.CTkLabel(
            card,
            text=str(meta["description"]),
            text_color=COLORS["text_secondary"],
            wraplength=760,
            justify="left",
        ).pack(anchor="w", padx=10)

        variables = tuple(meta.get("variables", ()))
        if variables:
            variable_text = ", ".join(f"{{{{{name}}}}}" for name in variables)
            ctk.CTkLabel(
                card,
                text=f"Kullanilabilir degiskenler: {variable_text}",
                text_color=COLORS["text_secondary"],
                wraplength=760,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(4, 0))

        textbox = ctk.CTkTextbox(
            card,
            height=int(meta.get("height", 150)),
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text_primary"],
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
        )
        textbox.pack(fill="both", expand=True, padx=10, pady=(8, 10))
        textbox.insert("1.0", load_prompt_template(prompt_key))
        self._prompt_editors[prompt_key] = textbox

    def _save_prompt_templates(self, show_status: bool = True) -> bool:
        try:
            for prompt_key, textbox in self._prompt_editors.items():
                save_prompt_template(prompt_key, textbox.get("1.0", "end-1c"))
        except Exception as exc:
            if show_status:
                self._set_status(f"Promptlar kaydedilemedi: {exc}", "warning")
            return False
        if show_status:
            self._set_status("Promptlar kaydedildi.", "success")
        return True

    def _reset_prompt_editor(self, prompt_key: str) -> None:
        try:
            reset_prompt_template(prompt_key)
            textbox = self._prompt_editors[prompt_key]
            textbox.delete("1.0", "end")
            textbox.insert("1.0", load_prompt_template(prompt_key))
            meta = get_prompt_editor_meta(prompt_key)
            self._set_status(f"{meta['title']} varsayilana donduruldu.", "success")
        except Exception as exc:
            self._set_status(f"Prompt sifirlanamadi: {exc}", "warning")

    def _reset_all_prompt_editors(self) -> None:
        try:
            for prompt_key in self._prompt_editors:
                reset_prompt_template(prompt_key)
                textbox = self._prompt_editors[prompt_key]
                textbox.delete("1.0", "end")
                textbox.insert("1.0", load_prompt_template(prompt_key))
            self._set_status("Tum promptlar varsayilana donduruldu.", "success")
        except Exception as exc:
            self._set_status(f"Promptlar sifirlanamadi: {exc}", "warning")

    # â”€â”€ Provider change â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_provider_change(self, label: str) -> None:
        provider = provider_key_from_label(label)

        # Clear the frame
        for widget in self._provider_frame.winfo_children():
            widget.destroy()

        # Reset dynamic widget references
        self._api_key_entry = None
        self._base_url_entry = None
        self._model_var = None
        self._model_entry = None
        self._ollama_model_var = None
        self._ollama_model_menu = None
        self._lm_studio_model_var = None
        self._lm_studio_model_menu = None

        pad = {"padx": 10, "pady": 5}

        if provider == "none":
            ctk.CTkLabel(
                self._provider_frame,
                text="AI yeniden yazma devre disi. Yalnizca SEO analizi yapilir.",
                text_color=COLORS["text_secondary"],
                wraplength=460,
            ).pack(anchor="w", **pad)

        elif provider == "anthropic":
            config = self._config
            self._api_key_entry = self._inner_field(self._provider_frame, "API Key (sk-ant-...):", config.ai_api_key or config.anthropic_api_key, show="*")
            self._model_var = self._inner_dropdown(
                self._provider_frame, "Model:",
                config.ai_model_name or "claude-haiku-4-5-20251001",
                get_provider_model_options("anthropic"),
            )

        elif provider == "openai":
            config = self._config
            self._api_key_entry = self._inner_field(self._provider_frame, "API Key (sk-...):", config.ai_api_key, show="*")
            self._base_url_entry = self._inner_field(self._provider_frame, "Base URL (opsiyonel):", config.ai_base_url or "https://api.openai.com/v1")
            self._model_var = self._inner_dropdown(
                self._provider_frame, "Model:",
                config.ai_model_name or "gpt-4o-mini",
                get_provider_model_options("openai"),
            )

        elif provider == "gemini":
            config = self._config
            self._api_key_entry = self._inner_field(self._provider_frame, "API Key (AIza...):", config.ai_api_key, show="*")
            self._model_var = self._inner_dropdown(
                self._provider_frame, "Model:",
                config.ai_model_name or "gemini-1.5-flash",
                get_provider_model_options("gemini"),
            )

        elif provider == "openrouter":
            config = self._config
            self._api_key_entry = self._inner_field(self._provider_frame, "API Key (sk-or-...):", config.ai_api_key, show="*")
            ctk.CTkLabel(
                self._provider_frame,
                text="Base URL: https://openrouter.ai/api/v1 (sabit)",
                text_color=COLORS["text_secondary"],
            ).pack(anchor="w", padx=10, pady=(4, 0))
            self._model_var = self._inner_dropdown(
                self._provider_frame, "Model:",
                config.ai_model_name or "openai/gpt-4o-mini",
                get_provider_model_options("openrouter"),
            )

        elif provider == "ollama":
            config = self._config
            self._base_url_entry = self._inner_field(self._provider_frame, "Base URL:", config.ai_base_url or "http://localhost:11434/v1")

            # Discovery button + status
            disc_frame = ctk.CTkFrame(self._provider_frame, fg_color="transparent")
            disc_frame.pack(fill="x", padx=10, pady=5)
            self._ollama_status = ctk.CTkLabel(disc_frame, text="", text_color=COLORS["text_secondary"])
            self._ollama_status.pack(side="right", padx=5)
            ctk.CTkButton(
                disc_frame, text="Ollama Bulundu mu?", width=180,
                fg_color=COLORS["accent"],
                command=self._discover_ollama,
            ).pack(side="left")

            # Model dropdown (populated after discovery)
            ctk.CTkLabel(self._provider_frame, text="Kurulu Model:", text_color=COLORS["text_secondary"]).pack(anchor="w", padx=10, pady=(4, 0))
            initial = config.ai_model_name or ""
            self._ollama_model_var = ctk.StringVar(value=initial)
            self._ollama_model_menu = ctk.CTkOptionMenu(
                self._provider_frame,
                variable=self._ollama_model_var,
                values=[initial] if initial else ["(once kesfet)"],
                fg_color=COLORS["input_bg"],
            )
            self._ollama_model_menu.pack(fill="x", padx=10, pady=2)

        elif provider == "lm-studio":
            config = self._config
            self._base_url_entry = self._inner_field(
                self._provider_frame, "Base URL:", config.ai_base_url or "http://localhost:1234/v1"
            )

            # Discovery button + status
            disc_frame = ctk.CTkFrame(self._provider_frame, fg_color="transparent")
            disc_frame.pack(fill="x", padx=10, pady=5)
            self._lm_studio_status = ctk.CTkLabel(disc_frame, text="", text_color=COLORS["text_secondary"])
            self._lm_studio_status.pack(side="right", padx=5)
            ctk.CTkButton(
                disc_frame, text="Modelleri Tara", width=180,
                fg_color=COLORS["accent"],
                command=self._discover_lm_studio,
            ).pack(side="left")

            # Model dropdown
            ctk.CTkLabel(self._provider_frame, text="Yuklu Model:", text_color=COLORS["text_secondary"]).pack(anchor="w", padx=10, pady=(4, 0))
            initial = config.ai_model_name or ""
            self._lm_studio_model_var = ctk.StringVar(value=initial)
            self._lm_studio_model_menu = ctk.CTkOptionMenu(
                self._provider_frame,
                variable=self._lm_studio_model_var,
                values=[initial] if initial else ["(once tara)"],
                fg_color=COLORS["input_bg"],
            )
            self._lm_studio_model_menu.pack(fill="x", padx=10, pady=2)

        elif provider == "custom":
            config = self._config
            self._api_key_entry = self._inner_field(self._provider_frame, "API Key (opsiyonel):", config.ai_api_key, show="*")
            self._base_url_entry = self._inner_field(self._provider_frame, "Base URL (zorunlu):", config.ai_base_url)
            self._model_entry = self._inner_field(self._provider_frame, "Model Adi:", config.ai_model_name)

    # â”€â”€ Ollama discovery â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _discover_ollama(self) -> None:
        base_url = self._base_url_entry.get().rstrip("/") if self._base_url_entry else "http://localhost:11434"
        self._ollama_status.configure(text="Kontrol ediliyor...", text_color=COLORS["warning"])

        def _check():
            try:
                if self._on_discover_provider_models is not None:
                    models = self._on_discover_provider_models("ollama", base_url)
                else:
                    models = discover_provider_models("ollama", base_url)
                self.after(0, lambda: self._ollama_found(models))
            except Exception as exc:
                self.after(0, lambda: self._ollama_not_found(str(exc)))

        threading.Thread(target=_check, daemon=True).start()

    def _ollama_found(self, models: list) -> None:
        self._ollama_models = models
        if models:
            self._ollama_model_menu.configure(values=models)
            self._ollama_model_var.set(models[0])
            self._ollama_status.configure(text=f"Bulundu! {len(models)} model", text_color=COLORS["success"])
        else:
            self._ollama_model_menu.configure(values=["(model yok)"])
            self._ollama_status.configure(text="Bagli, model yok", text_color=COLORS["warning"])

    def _ollama_not_found(self, reason: str) -> None:
        self._ollama_status.configure(text=f"Bulunamadi: {reason[:40]}", text_color=COLORS["error"] if "error" in COLORS else "#ff6b6b")

    # â”€â”€ LM Studio discovery â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _discover_lm_studio(self) -> None:
        base_url = self._base_url_entry.get().rstrip("/") if self._base_url_entry else "http://localhost:1234"
        self._lm_studio_status.configure(text="Kontrol ediliyor...", text_color=COLORS["warning"])

        def _check():
            try:
                if self._on_discover_provider_models is not None:
                    models = self._on_discover_provider_models("lm-studio", base_url)
                else:
                    models = discover_provider_models("lm-studio", base_url)
                self.after(0, lambda: self._lm_studio_found(models))
            except Exception as exc:
                self.after(0, lambda: self._lm_studio_not_found(str(exc)))

        threading.Thread(target=_check, daemon=True).start()

    def _lm_studio_found(self, models: list) -> None:
        self._lm_studio_models = models
        if models:
            self._lm_studio_model_menu.configure(values=models)
            self._lm_studio_model_var.set(models[0])
            self._lm_studio_status.configure(text=f"Bulundu! {len(models)} model", text_color=COLORS["success"])
        else:
            self._lm_studio_model_menu.configure(values=["(model yok)"])
            self._lm_studio_status.configure(text="Bagli, model yok", text_color=COLORS["warning"])

    def _lm_studio_not_found(self, reason: str) -> None:
        self._lm_studio_status.configure(
            text=f"Bulunamadi: {reason[:40]}",
            text_color=COLORS.get("error", "#ff6b6b"),
        )

    # â”€â”€ Save / Test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _collect_provider_key(self) -> str:
        return provider_key_from_label(self._provider_var.get())

    def _collect_model(self) -> str:
        provider = self._collect_provider_key()
        if provider == "ollama":
            return self._ollama_model_var.get() if self._ollama_model_var else ""
        elif provider == "lm-studio":
            return self._lm_studio_model_var.get() if self._lm_studio_model_var else ""
        elif provider == "custom":
            return self._model_entry.get() if self._model_entry else ""
        else:
            return self._model_var.get() if self._model_var else ""

    def _collect_settings_payload(self) -> dict:
        provider = self._collect_provider_key()
        api_key = self._api_key_entry.get() if self._api_key_entry else ""
        base_url = self._base_url_entry.get() if self._base_url_entry else ""
        model = self._collect_model()

        try:
            temperature = float(self._temperature.get())
        except ValueError:
            temperature = 0.7
        try:
            max_tokens = int(self._max_tokens.get())
        except ValueError:
            max_tokens = 2000

        return {
            "store_name": self._store_name.get(),
            "client_id": self._client_id.get(),
            "client_secret": self._client_secret.get(),
            "ai_provider": provider,
            "ai_api_key": api_key,
            "ai_base_url": base_url,
            "ai_model_name": model,
            "ai_temperature": temperature,
            "ai_max_tokens": max_tokens,
            "ai_thinking_mode": self._thinking_mode_var.get(),
            "languages": self._languages.get(),
            "keywords": self._keywords.get(),
            "dry_run": self._dry_run_var.get(),
        }

    def _save(self) -> None:
        if not self._save_prompt_templates(show_status=False):
            return

        payload = self._collect_settings_payload()

        if self._on_save:
            self._on_save(payload)
        else:
            # Default: persist to .env
            from config.settings import save_config_to_env
            save_config_to_env(payload)
            self._set_status("Ayarlar ve promptlar kaydedildi.", "success")

        self.destroy()

    def _test(self) -> None:
        provider = self._collect_provider_key()
        if provider == "ollama":
            self._discover_ollama()
            return

        self._set_status("Test ediliyor...", "warning")
        payload = self._collect_settings_payload()

        def _run():
            try:
                result = self._on_test(payload) if self._on_test is not None else test_settings_connection(payload)
                color = "text_secondary" if provider == "none" else ("success" if result.get("ok") else "warning")
                self.after(0, lambda: self._set_status(str(result.get("message") or "Test tamamlandi."), color))
                return

            except Exception as exc:
                self.after(0, lambda: self._set_status(f"Hata: {exc}", "warning"))

        threading.Thread(target=_run, daemon=True).start()

