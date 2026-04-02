from __future__ import annotations

import hashlib
from typing import Any, Sequence

from core.models import Product, SeoSuggestion, StoreMemoryContext, StoreMemoryEntry, StoreMemoryUsageLog
from core.utils.html import html_to_plain_text
from data import db

MEMORY_TYPE_LABELS = {
    "brand_tone": "Marka tonu",
    "forbidden_claim": "Yasak claim",
    "category_glossary": "Kategori sozlugu",
    "approved_preference": "Onayli tercih",
    "operation_note": "Operasyon notu",
}

DEFAULT_MAX_PROMPT_CHARS = 1400
DEFAULT_MAX_PROMPT_ENTRIES = 8

_SUGGESTION_FIELD_CONFIG = {
    "suggested_name": ("Urun adi", "original_name"),
    "suggested_meta_title": ("Meta title", "original_meta_title"),
    "suggested_meta_description": ("Meta description", "original_meta_description"),
    "suggested_description": ("Aciklama (TR)", "original_description"),
    "suggested_description_en": ("Aciklama (EN)", "original_description_en"),
}


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_key(value: str) -> str:
    return _normalize_text(value).casefold()


def _to_preview(value: str, *, limit: int = 180) -> str:
    plain = html_to_plain_text(str(value or ""), preserve_breaks=True)
    compact = _normalize_text(plain or value)
    if len(compact) <= limit:
        return compact
    shortened = compact[:limit].rsplit(" ", 1)[0].strip()
    return (shortened or compact[:limit].strip()) + "..."


def _memory_sort_key(entry: StoreMemoryEntry) -> tuple[int, str]:
    return (1 if entry.enabled else 0, entry.updated_at.isoformat())


class StoreMemoryService:
    async def list_memories(self, *, enabled_only: bool = False) -> list[StoreMemoryEntry]:
        return await db.list_store_memories(enabled_only=enabled_only)

    async def get_memory(self, memory_id: str) -> StoreMemoryEntry | None:
        return await db.get_store_memory(memory_id)

    async def save_memory(self, memory: StoreMemoryEntry | dict[str, Any]) -> StoreMemoryEntry:
        entry = memory if isinstance(memory, StoreMemoryEntry) else StoreMemoryEntry.model_validate(memory)
        return await db.save_store_memory(entry)

    async def delete_memory(self, memory_id: str) -> None:
        await db.delete_store_memory(memory_id)

    async def build_prompt_context(
        self,
        *,
        product: Product | None = None,
        applies_to: str = "chat",
        agent_type: str = "",
        max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
        max_entries: int = DEFAULT_MAX_PROMPT_ENTRIES,
    ) -> StoreMemoryContext:
        entries = await self.list_memories(enabled_only=True)
        if not entries:
            return StoreMemoryContext(
                prompt="",
                entries=[],
                usage_log=StoreMemoryUsageLog(enabled=False, applies_to=applies_to, agent_type=agent_type),
            )

        product_category = _normalize_key(product.category) if product and product.category else ""
        scored_entries: list[tuple[int, StoreMemoryEntry, bool]] = []
        for entry in entries:
            category_match = bool(product_category and entry.category and _normalize_key(entry.category) == product_category)
            score = 0
            if entry.memory_type == "operation_note":
                score += 5 if agent_type == "operator" else 1
            elif agent_type != "operator":
                score += 3
            if entry.memory_type == "approved_preference" and applies_to in {"rewrite", "batch", "chat"}:
                score += 2
            if entry.memory_type in {"forbidden_claim", "brand_tone"}:
                score += 2
            if category_match:
                score += 5
            elif entry.category:
                score -= 2
            scored_entries.append((score, entry, category_match))

        scored_entries.sort(
            key=lambda item: (
                item[0],
                _memory_sort_key(item[1]),
            ),
            reverse=True,
        )

        header = (
            "Kalici magaza hafizasi:\n"
            "- Bu notlari tercih ve guvenlik siniri olarak kullan.\n"
            "- Urun verisiyle celisirse veri uydurma; gerekiyorsa celiskiyi belirt."
        )
        lines = [header]
        used_entries: list[StoreMemoryEntry] = []
        used_types: list[str] = []
        char_count = len(header)
        omitted_entries = 0
        category_matches = 0
        for _, entry, category_match in scored_entries[:max_entries]:
            scope = f" | {entry.category}" if entry.category else ""
            line = f"- [{MEMORY_TYPE_LABELS.get(entry.memory_type, entry.memory_type)}{scope}] {entry.summary}"
            projected = char_count + 1 + len(line)
            if used_entries and projected > max_chars:
                omitted_entries += 1
                continue
            if projected > max_chars and not used_entries:
                allowed = max(80, max_chars - char_count - 4)
                line = line[:allowed].rsplit(" ", 1)[0].strip() or line[:allowed].strip()
                line += "..."
            lines.append(line)
            used_entries.append(entry)
            if entry.memory_type not in used_types:
                used_types.append(entry.memory_type)
            char_count += 1 + len(line)
            if category_match:
                category_matches += 1

        if not used_entries:
            return StoreMemoryContext(
                prompt="",
                entries=[],
                usage_log=StoreMemoryUsageLog(enabled=False, applies_to=applies_to, agent_type=agent_type),
            )

        return StoreMemoryContext(
            prompt="\n".join(lines),
            entries=used_entries,
            usage_log=StoreMemoryUsageLog(
                enabled=True,
                applies_to=applies_to,
                agent_type=agent_type,
                entry_count=len(used_entries),
                char_count=len("\n".join(lines)),
                truncated=bool(omitted_entries or len(scored_entries) > len(used_entries)),
                omitted_entries=max(0, len(scored_entries) - len(used_entries)),
                used_memory_ids=[entry.id for entry in used_entries],
                used_types=used_types,
                category_matches=category_matches,
            ),
        )

    async def sync_approved_suggestion_memory(
        self,
        product: Product,
        suggestion: SeoSuggestion,
        *,
        selected_fields: Sequence[str] | None = None,
        source: str = "approved_suggestion",
    ) -> list[StoreMemoryEntry]:
        fields = list(selected_fields or _SUGGESTION_FIELD_CONFIG.keys())
        saved: list[StoreMemoryEntry] = []
        for field_name in fields:
            if field_name not in _SUGGESTION_FIELD_CONFIG:
                continue
            approved_value = getattr(suggestion, field_name, None)
            if not isinstance(approved_value, str) or not approved_value.strip():
                continue

            label, original_attr = _SUGGESTION_FIELD_CONFIG[field_name]
            original_value = getattr(suggestion, original_attr, None)
            approved_preview = _to_preview(approved_value)
            if not approved_preview:
                continue
            if isinstance(original_value, str) and _normalize_key(_to_preview(original_value)) == _normalize_key(approved_preview):
                continue

            category = product.category or ""
            content = (
                f"{label} icin onaylanan tercih: {approved_preview}. "
                "Benzer urunlerde bunu referans kabul et."
            )
            if category:
                content = f"{category} kategorisi icin {content}"

            identity = "|".join([
                source,
                field_name,
                _normalize_key(category),
                _normalize_key(approved_preview),
            ])
            memory = StoreMemoryEntry(
                id=hashlib.sha1(identity.encode("utf-8")).hexdigest(),
                memory_type="approved_preference",
                title=f"{label} tercihi" if not category else f"{category} - {label} tercihi",
                content=content,
                category=category,
                source=source,
                metadata={
                    "field": field_name,
                    "product_id": product.id,
                    "product_name": product.name,
                    "approved_value_preview": approved_preview,
                },
            )
            saved.append(await self.save_memory(memory))
        return saved
