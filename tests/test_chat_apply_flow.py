import pytest

from core.chat_service import ChatService, SAVE_SEO_SUGGESTION_TOOL_NAME
from core.models import AppConfig, ChatMessage, Product, SeoScore, SeoSuggestion


def _make_config(**overrides) -> AppConfig:
    defaults = {
        "ikas_store_name": "test-store",
        "ikas_client_id": "cid",
        "ikas_client_secret": "csec",
        "ai_provider": "lm-studio",
        "ai_model_name": "qwen-test",
        "ai_base_url": "http://localhost:1234/v1",
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


def _make_product(**overrides) -> Product:
    defaults = {
        "id": "prod-1",
        "name": "Kushie Kush 1 Litre",
        "description": "Bir test aciklamasi",
        "category": "Bitki Besini",
        "price": 2880.0,
        "meta_title": "Eski Meta Title",
        "meta_description": "Eski meta description",
        "tags": ["bitki", "besin"],
    }
    defaults.update(overrides)
    return Product(**defaults)


def _make_score(**overrides) -> SeoScore:
    defaults = {
        "product_id": "prod-1",
        "total_score": 64,
        "title_score": 9,
        "description_score": 12,
        "meta_score": 7,
        "meta_desc_score": 5,
        "keyword_score": 6,
        "content_quality_score": 8,
        "technical_seo_score": 8,
        "readability_score": 3,
        "issues": ["Meta title zayif"],
    }
    defaults.update(overrides)
    return SeoScore(**defaults)


@pytest.mark.anyio
async def test_explicit_ikas_apply_uses_save_flow_then_returns_confirmation_options(monkeypatch):
    service = ChatService(_make_config(ai_thinking_mode=False))
    product = _make_product()
    service.set_product_context(product, _make_score())
    service._schedule_history_summarization = lambda: None  # type: ignore[method-assign]

    captured_tools: dict[str, list[str]] = {}
    service._history.append(ChatMessage(role="assistant", content="Meta Title onerisi: Yeni Meta Title"))

    async def fake_chat_completion(messages, tools):
        captured_tools["names"] = [tool["function"]["name"] for tool in (tools or [])]
        return (
            "",
            "",
            [],
            {"model": "qwen-test"},
            {
                "product_id": product.id,
                "product_name": product.name,
                "fields": {"suggested_meta_title": "Yeni Meta Title"},
            },
        )

    pending_suggestion = SeoSuggestion(
        product_id=product.id,
        original_name=product.name,
        original_description=product.description,
        original_description_en="",
        original_meta_title=product.meta_title,
        original_meta_description=product.meta_description,
        suggested_meta_title="Yeni Meta Title",
        status="pending",
    )
    lookup_calls = {"count": 0}

    async def fake_get_latest_suggestion_by_product(product_id, statuses=None):
        lookup_calls["count"] += 1
        if lookup_calls["count"] == 1:
            return None
        return pending_suggestion

    monkeypatch.setattr(service, "_chat_completion", fake_chat_completion)

    import data.db as _db

    monkeypatch.setattr(_db, "get_latest_suggestion_by_product", fake_get_latest_suggestion_by_product)

    response = await service.send_message("@ikas uygula")

    assert SAVE_SEO_SUGGESTION_TOOL_NAME in captured_tools["names"]
    assert "Onay Adimi" in response.content
    assert "single_apply_all" in response.content
    assert response.tool_results == []
