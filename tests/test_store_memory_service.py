import asyncio

import data.db as db
from core.models import Product, SeoSuggestion
from core.services.store_memory import StoreMemoryService


def _build_product() -> Product:
    return Product(
        id="prod-memory-1",
        name="Test Urun",
        description="<p>Aciklama</p>",
        description_translations={"tr": "<p>Aciklama</p>"},
        meta_title="Eski Meta",
        meta_description="Eski Description",
        category="Ayakkabi",
    )


def test_store_memory_service_builds_prompt_context_and_extracts_preferences(monkeypatch, tmp_path):
    asyncio.run(db.close_pool())
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_store_memory.db")
    asyncio.run(db.init_db())

    try:
        service = StoreMemoryService()

        asyncio.run(service.save_memory({
            "id": "memory-tone",
            "memory_type": "brand_tone",
            "title": "Premium ton",
            "content": "Marka tonu premium ama sakin olmali. Abartili superlatif kullanma.",
            "summary": "Premium ama sakin ton kullan, abartili superlatiflerden kac.",
            "category": "Ayakkabi",
            "source": "manual",
            "enabled": True,
            "metadata": {},
        }))

        context = asyncio.run(service.build_prompt_context(
            product=_build_product(),
            applies_to="chat",
            agent_type="seo",
            max_chars=500,
            max_entries=5,
        ))

        assert "Kalici magaza hafizasi" in context.prompt
        assert "Premium ama sakin ton kullan" in context.prompt
        assert context.usage_log.enabled is True
        assert context.usage_log.entry_count == 1
        assert context.usage_log.category_matches == 1

        suggestion = SeoSuggestion(
            product_id="prod-memory-1",
            original_name="Test Urun",
            suggested_name="Test Urun Premium Seri",
            original_description="<p>Aciklama</p>",
            suggested_description="<p>Yeni aciklama</p>",
            original_description_en="",
            suggested_description_en="",
            original_meta_title="Eski Meta",
            suggested_meta_title="Premium Ayakkabi | Test Marka",
            original_meta_description="Eski Description",
            suggested_meta_description="Yeni meta description",
            status="approved",
        )

        saved = asyncio.run(service.sync_approved_suggestion_memory(
            _build_product(),
            suggestion,
            selected_fields=["suggested_meta_title"],
            source="unit_test",
        ))

        assert len(saved) == 1
        assert saved[0].memory_type == "approved_preference"
        assert saved[0].metadata["field"] == "suggested_meta_title"

        all_memories = asyncio.run(service.list_memories(enabled_only=True))
        assert len(all_memories) == 2
    finally:
        asyncio.run(db.close_pool())
