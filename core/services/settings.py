from __future__ import annotations

import asyncio

from collections.abc import Iterable, Mapping
from typing import Any

from config.settings import save_config_to_db
from core.prompt_store import (
    get_prompt_editor_groups,
    get_prompt_editor_meta,
    load_prompt_template,
    reset_prompt_template,
    save_prompt_template,
)
from core.models import StoreMemoryEntry
from core.skills import (
    SkillDefinition,
    delete_skill_definition,
    export_skill_definition,
    get_available_tool_names,
    get_skill_definition,
    import_skill_definition,
    list_skill_definitions,
    preview_skill_definition,
    reset_skill_definition,
    save_skill_definition,
    validate_skill_definition,
)
from core.services.provider import (
    PROVIDER_LABELS,
    discover_provider_models,
    get_provider_model_options,
    provider_key_from_label,
    provider_label_from_key,
    test_settings_connection,
)
from core.services.store_memory import StoreMemoryService


class SettingsService:
    def __init__(self) -> None:
        self._store_memory_service = StoreMemoryService()

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

    def list_skills(self) -> list[SkillDefinition]:
        return list_skill_definitions()

    def get_skill(self, slug: str) -> SkillDefinition:
        return get_skill_definition(slug)

    def save_skill(self, skill: SkillDefinition) -> SkillDefinition:
        return save_skill_definition(skill)

    def reset_skill(self, slug: str) -> SkillDefinition:
        return reset_skill_definition(slug)

    def delete_skill(self, slug: str) -> None:
        delete_skill_definition(slug)

    def validate_skill(self, skill: SkillDefinition) -> dict[str, Any]:
        return validate_skill_definition(skill).model_dump(mode="json")

    def preview_skill(self, skill: SkillDefinition, *, applies_to: str = "chat") -> dict[str, Any]:
        return preview_skill_definition(skill, applies_to=applies_to)

    def export_skill(self, slug: str) -> dict[str, Any]:
        return export_skill_definition(slug)

    def import_skill(self, payload: dict[str, Any]) -> SkillDefinition:
        return import_skill_definition(payload)

    def get_available_tool_names(self) -> list[str]:
        return get_available_tool_names()

    async def list_store_memories(self) -> list[StoreMemoryEntry]:
        return await self._store_memory_service.list_memories()

    async def get_store_memory(self, memory_id: str) -> StoreMemoryEntry:
        memory = await self._store_memory_service.get_memory(memory_id)
        if memory is None:
            raise KeyError(f"Store memory bulunamadi: {memory_id}")
        return memory

    async def save_store_memory(self, memory: StoreMemoryEntry) -> StoreMemoryEntry:
        return await self._store_memory_service.save_memory(memory)

    async def delete_store_memory(self, memory_id: str) -> None:
        await self._store_memory_service.delete_memory(memory_id)

    def save_settings(self, values: dict[str, Any]) -> None:
        asyncio.run(save_config_to_db(values))

    def test_connection(self, values: dict[str, Any]) -> dict[str, Any]:
        return test_settings_connection(values)

    def discover_provider_models(self, provider: str, base_url: str = "") -> list[str]:
        return discover_provider_models(provider, base_url)
