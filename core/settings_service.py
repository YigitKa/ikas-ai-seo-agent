from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from config.settings import save_config_to_env
from core.prompt_store import (
    get_prompt_editor_groups,
    get_prompt_editor_meta,
    load_prompt_template,
    reset_prompt_template,
    save_prompt_template,
)
from core.provider_service import (
    PROVIDER_LABELS,
    discover_provider_models,
    get_provider_model_options,
    provider_key_from_label,
    provider_label_from_key,
    test_settings_connection,
)


class SettingsService:
    def get_provider_label(self, provider: str) -> str:
        return provider_label_from_key(provider)

    def get_provider_labels(self) -> dict[str, str]:
        return dict(PROVIDER_LABELS)

    def get_provider_label_values(self) -> list[str]:
        return list(PROVIDER_LABELS.values())

    def get_provider_key(self, label: str) -> str:
        return provider_key_from_label(label)

    def get_provider_model_options(self, provider: str) -> list[str]:
        return get_provider_model_options(provider)

    def get_prompt_editor_groups(self) -> list[tuple[str, tuple[str, ...]]]:
        return get_prompt_editor_groups()

    def get_prompt_editor_meta(self, prompt_key: str) -> dict[str, object]:
        return get_prompt_editor_meta(prompt_key)

    def load_prompt_template(self, prompt_key: str) -> str:
        return load_prompt_template(prompt_key)

    def load_prompt_templates(self, prompt_keys: Iterable[str]) -> dict[str, str]:
        return {prompt_key: load_prompt_template(prompt_key) for prompt_key in prompt_keys}

    def save_prompt_templates(self, templates: Mapping[str, str]) -> None:
        for prompt_key, content in templates.items():
            save_prompt_template(prompt_key, content)

    def reset_prompt_template(self, prompt_key: str) -> str:
        reset_prompt_template(prompt_key)
        return load_prompt_template(prompt_key)

    def reset_prompt_templates(self, prompt_keys: Iterable[str]) -> dict[str, str]:
        contents: dict[str, str] = {}
        for prompt_key in prompt_keys:
            reset_prompt_template(prompt_key)
            contents[prompt_key] = load_prompt_template(prompt_key)
        return contents

    def save_settings(self, values: dict[str, Any]) -> None:
        save_config_to_env(values)

    def test_connection(self, values: dict[str, Any]) -> dict[str, Any]:
        return test_settings_connection(values)

    def discover_provider_models(self, provider: str, base_url: str = "") -> list[str]:
        return discover_provider_models(provider, base_url)
