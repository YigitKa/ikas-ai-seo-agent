import asyncio

import data.db as db
from api.dependencies import get_manager
from api.routers import batch, chat, settings, suggestions
from core.models import AgentEvent, Product, SeoScore, SeoSuggestion
from core.skills import store as skill_store
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_product(product_id: str = "prod-1") -> Product:
    return Product(
        id=product_id,
        name="Test Urun",
        description="<p>Turkce aciklama</p>",
        description_translations={"tr": "<p>Turkce aciklama</p>"},
        meta_title="Eski Meta",
        meta_description="Eski Meta Description",
        category="Bitki Besini",
    )


def _build_score(product_id: str = "prod-1") -> SeoScore:
    return SeoScore(
        product_id=product_id,
        total_score=72,
        title_score=11,
        description_score=14,
        english_description_score=0,
        meta_score=10,
        meta_desc_score=8,
        keyword_score=8,
        content_quality_score=9,
        technical_seo_score=8,
        readability_score=4,
        ai_citability_score=3,
        issues=["Meta title zayif"],
    )


def _build_skill_payload(slug: str = "integration-skill") -> dict[str, object]:
    return {
        "slug": slug,
        "name": "Integration Skill",
        "description": "Skill Studio entegrasyon testi icin ozel skill.",
        "when_to_use": "Test akisini dogrularken kullan.",
        "applies_to": ["chat", "rewrite", "batch"],
        "allowed_tools": ["get_product_details"],
        "prompt_layers": [
            {
                "type": "inline",
                "label": "Integration Rules",
                "content": "Sadece test amacli entegrasyon kurallarini uygula.",
            }
        ],
        "tags": ["integration", "test"],
        "priority": 55,
        "status": "active",
        "instructions_markdown": "Bu skill entegrasyon testinde composed prompt ve CRUD akislarini dogrular.",
    }


def test_skill_studio_api_flow_supports_crud_preview_and_import(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()

    app = FastAPI()
    app.include_router(settings.router, prefix="/api/settings")

    payload = _build_skill_payload()

    with TestClient(app) as client:
        list_response = client.get("/api/settings/skills")
        validate_response = client.post("/api/settings/skills/validate", json={"skill": payload})
        preview_response = client.post("/api/settings/skills/preview?applies_to=chat", json={"skill": payload})
        save_response = client.put("/api/settings/skills/item/integration-skill", json={"skill": payload})
        export_response = client.get("/api/settings/skills/item/integration-skill/export")
        delete_response = client.delete("/api/settings/skills/item/integration-skill")
        missing_response = client.get("/api/settings/skills/item/integration-skill")
        import_response = client.post("/api/settings/skills/import", json={"skill": export_response.json()})
        get_response = client.get("/api/settings/skills/item/integration-skill")

    try:
        assert list_response.status_code == 200
        assert any(item["slug"] == "brand-voice-rewrite" for item in list_response.json()["items"])

        assert validate_response.status_code == 200
        assert validate_response.json()["ok"] is True
        assert validate_response.json()["errors"] == []

        assert preview_response.status_code == 200
        preview_json = preview_response.json()
        assert preview_json["validation"]["ok"] is True
        assert preview_json["debug"]["tool_scope_mode"] == "prompt_and_tools"
        assert preview_json["debug"]["resolved_tools"] == ["get_product_details"]
        assert "Aktif skill: Integration Skill" in preview_json["composed_prompt"]

        assert save_response.status_code == 200
        assert save_response.json()["slug"] == "integration-skill"
        assert save_response.json()["source"] == "custom"

        assert export_response.status_code == 200
        assert export_response.json()["slug"] == "integration-skill"

        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Skill silindi"

        assert missing_response.status_code == 404

        assert import_response.status_code == 200
        assert import_response.json()["slug"] == "integration-skill"

        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Integration Skill"
    finally:
        skill_store._skill_cache.clear()


class _SuggestionManagerStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def rewrite_product(self, product: Product, score: SeoScore, *, skill_slug: str | None = None) -> SeoSuggestion:
        self.calls.append(("rewrite_product", product.id, skill_slug or ""))
        return SeoSuggestion(
            product_id=product.id,
            original_name=product.name,
            suggested_name="Yeni Urun Adi",
            original_description=product.description,
            suggested_description="<p>Yeni aciklama</p>",
            original_description_en="",
            suggested_description_en="",
            original_meta_title=product.meta_title,
            suggested_meta_title="Yeni Meta",
            original_meta_description=product.meta_description,
            suggested_meta_description="Yeni Meta Description",
            thinking_text=f"skill={skill_slug}",
        )

    async def stream_rewrite_product(self, product_id: str, *, skill_slug: str | None = None):
        self.calls.append(("stream_rewrite_product", product_id, skill_slug or ""))
        yield AgentEvent(type="completed", content="stream tamam", meta={"skill_slug": skill_slug or ""})

    def rewrite_field(self, field: str, product: Product, score: SeoScore, *, skill_slug: str | None = None) -> tuple[str, str]:
        self.calls.append(("rewrite_field", field, skill_slug or ""))
        return f"{field}-rewritten", "field-thinking"

    def translate_description_to_en(self, product: Product, *, skill_slug: str | None = None) -> tuple[str, str]:
        self.calls.append(("translate_description_to_en", product.id, skill_slug or ""))
        return "<p>Translated EN</p>", "translation-thinking"

    def validate_skill_for_flow(self, skill_slug: str | None, flow: str) -> dict[str, object] | None:
        self.calls.append(("validate_skill_for_flow", flow, skill_slug or ""))
        if not skill_slug:
            return None
        return {"slug": skill_slug, "applies_to": [flow]}

    def get_token_usage(self) -> dict[str, float]:
        return {"input": 12, "output": 8, "estimated_cost": 0.02}

    async def analyze_product(self, product: Product) -> SeoScore:
        return _build_score(product.id)


def test_suggestions_api_flow_passes_skill_slug_into_rewrite_runtime(monkeypatch):
    app = FastAPI()
    app.include_router(suggestions.router, prefix="/api/suggestions")

    manager = _SuggestionManagerStub()
    app.dependency_overrides[get_manager] = lambda: manager

    product = _build_product()
    score = _build_score()

    async def fake_get_product(product_id: str) -> Product | None:
        assert product_id == product.id
        return product

    async def fake_get_latest_score(product_id: str) -> SeoScore | None:
        assert product_id == product.id
        return score

    monkeypatch.setattr(suggestions.db, "get_product", fake_get_product)
    monkeypatch.setattr(suggestions.db, "get_latest_score", fake_get_latest_score)

    try:
        with TestClient(app) as client:
            generate_response = client.post("/api/suggestions/generate/prod-1?skill_slug=brand-voice-rewrite")
            stream_response = client.post("/api/suggestions/generate/prod-1/stream?skill_slug=brand-voice-rewrite")
            field_response = client.post(
                "/api/suggestions/generate-field/prod-1",
                json={"product_id": "prod-1", "field": "name", "skill_slug": "brand-voice-rewrite"},
            )
            translation_response = client.post(
                "/api/suggestions/generate-field/prod-1",
                json={"product_id": "prod-1", "field": "desc_en", "skill_slug": "launch-readiness"},
            )

        assert generate_response.status_code == 200
        assert generate_response.json()["suggestion"]["suggested_name"] == "Yeni Urun Adi"
        assert generate_response.json()["thinking_text"] == "skill=brand-voice-rewrite"

        assert stream_response.status_code == 200
        assert '"skill_slug":"brand-voice-rewrite"' in stream_response.text

        assert field_response.status_code == 200
        assert field_response.json()["field_value"] == "name-rewritten"

        assert translation_response.status_code == 200
        assert translation_response.json()["field_value"] == "<p>Translated EN</p>"

        assert ("rewrite_product", "prod-1", "brand-voice-rewrite") in manager.calls
        assert ("validate_skill_for_flow", "rewrite", "brand-voice-rewrite") in manager.calls
        assert ("stream_rewrite_product", "prod-1", "brand-voice-rewrite") in manager.calls
        assert ("rewrite_field", "name", "brand-voice-rewrite") in manager.calls
        assert ("translate_description_to_en", "prod-1", "launch-readiness") in manager.calls
    finally:
        app.dependency_overrides.clear()


class _BatchManagerStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def validate_skill_for_flow(self, skill_slug: str | None, flow: str) -> dict[str, object] | None:
        self.calls.append((flow, skill_slug or ""))
        if not skill_slug:
            return None
        return {"slug": skill_slug, "applies_to": [flow]}


def test_batch_api_flow_persists_skill_slug_and_launches_analysis(monkeypatch, tmp_path):
    asyncio.run(db.close_pool())
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_batch_skills.db")
    asyncio.run(db.init_db())

    app = FastAPI()
    app.include_router(batch.router, prefix="/api/batch")

    manager = _BatchManagerStub()
    app.dependency_overrides[get_manager] = lambda: manager

    launched: dict[str, object] = {}

    def fake_launch_batch_analysis(job_id: str, product_ids: list[str], config, batch_manager) -> None:
        launched["job_id"] = job_id
        launched["product_ids"] = list(product_ids)
        launched["config"] = config
        launched["manager"] = batch_manager

    monkeypatch.setattr(batch, "launch_batch_analysis", fake_launch_batch_analysis)

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/api/batch/jobs",
                json={
                    "product_ids": ["prod-1", "prod-2"],
                    "config": {
                        "target_fields": ["name", "meta_title"],
                        "skill_slug": "brand-voice-rewrite",
                    },
                },
            )
            job_id = create_response.json()["id"]
            detail_response = client.get(f"/api/batch/jobs/{job_id}")

        assert create_response.status_code == 200
        assert create_response.json()["status"] == "analyzing"
        assert create_response.json()["config"]["skill_slug"] == "brand-voice-rewrite"

        assert detail_response.status_code == 200
        assert detail_response.json()["job"]["config"]["skill_slug"] == "brand-voice-rewrite"
        assert detail_response.json()["items"] == []

        assert manager.calls == [("batch", "brand-voice-rewrite")]
        assert launched["product_ids"] == ["prod-1", "prod-2"]
        assert getattr(launched["config"], "skill_slug") == "brand-voice-rewrite"
        assert launched["manager"] is manager
    finally:
        app.dependency_overrides.clear()
        asyncio.run(db.close_pool())


def test_chat_websocket_flow_reports_skill_status_and_uses_selected_skill(monkeypatch):
    app = FastAPI()
    app.include_router(chat.router)

    class _ChatManagerStub:
        def __init__(self) -> None:
            self.chat_has_mcp = False
            self.chat_mcp_initialized = False
            self.chat_mcp_tool_count = 0
            self.chat_mcp_tools: list[dict[str, str]] = []
            self.active_skill: dict[str, object] | None = None

        def get_chat_active_skill(self) -> dict[str, object] | None:
            return self.active_skill

        def set_chat_active_skill(self, slug: str) -> dict[str, object]:
            self.active_skill = {
                "slug": slug,
                "name": "Brand Voice Rewrite",
                "selection_mode": "explicit",
                "merged_skill_slugs": [slug],
                "resolved_tools": ["get_product_details"],
            }
            return self.active_skill

        def clear_chat_active_skill(self) -> None:
            self.active_skill = None

        def cancel_chat_request(self) -> bool:
            return False

        def clear_chat_history(self) -> None:
            return None

        def set_chat_product_context(self, product, score=None) -> None:
            return None

        async def initialize_mcp(self) -> tuple[bool, str]:
            return False, "MCP token yok"

        def stream_chat_message(self, message: str):
            async def _events():
                yield {
                    "type": "assistant",
                    "content": f"yanit:{message}",
                    "meta": {"active_skill": self.active_skill},
                }

            return _events()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(chat, "ProductManager", _ChatManagerStub)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat") as ws:
            initial_mcp = ws.receive_json()
            initial_skill = ws.receive_json()
            ws.send_json({"action": "set_skill", "skill_slug": "brand-voice-rewrite"})
            selected_skill = ws.receive_json()
            ws.send_json({"action": "message", "message": "Marka tonunu duzelt"})
            thinking = ws.receive_json()
            response = ws.receive_json()
            ws.send_json({"action": "clear_skill"})
            cleared_skill = ws.receive_json()

    assert initial_mcp["type"] == "mcp_status"
    assert initial_skill == {
        "type": "skill_status",
        "active_skill": None,
        "message": "Aktif skill yok",
    }

    assert selected_skill["type"] == "skill_status"
    assert selected_skill["active_skill"]["slug"] == "brand-voice-rewrite"
    assert selected_skill["message"] == "Skill secildi: brand-voice-rewrite"

    assert thinking == {"type": "thinking"}
    assert response["type"] == "assistant"
    assert response["content"] == "yanit:Marka tonunu duzelt"
    assert response["meta"]["active_skill"]["slug"] == "brand-voice-rewrite"

    assert cleared_skill == {
        "type": "skill_status",
        "active_skill": None,
        "message": "Skill temizlendi",
    }
