import pytest

from core.chat import ChatService, SAVE_SEO_SUGGESTION_TOOL_NAME
from core.models import AppConfig, ChatMessage, Product, SeoScore


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


def _stub_routing(service: ChatService, agent_type: str = "general") -> None:
    async def fake_route_to_agent(user_message: str) -> str:
        return agent_type

    service._route_to_agent = fake_route_to_agent  # type: ignore[method-assign]


@pytest.mark.anyio
async def test_apply_uses_save_flow_then_returns_confirmation_options(monkeypatch):
    service = ChatService(_make_config(ai_thinking_mode_chat=False))
    _stub_routing(service)
    product = _make_product()
    service.set_product_context(product, _make_score())
    service._schedule_history_summarization = lambda: None  # type: ignore[method-assign]

    captured_tools: dict[str, list[str]] = {}
    service._history.append(ChatMessage(role="assistant", content="Meta title icin net bir final onerim hazir."))

    async def fake_chat_completion(messages, tools):
        captured_tools["names"] = [tool["function"]["name"] for tool in (tools or [])]
        _, suggestion_saved = await service._save_suggestion_from_tool_args(
            {"suggested_meta_title": "Yeni Meta Title"}
        )
        return (
            "",
            "",
            [],
            {"model": "qwen-test"},
            suggestion_saved,
        )

    monkeypatch.setattr(service, "_chat_completion", fake_chat_completion)

    response = await service.send_message("uygula")

    assert SAVE_SEO_SUGGESTION_TOOL_NAME in captured_tools["names"]
    assert "Ne yapmak istersiniz" in response.content
    assert "single_apply_all" in response.content
    assert response.tool_results == []
    assert response.pending_suggestion is not None
    assert response.pending_suggestion.suggested_meta_title == "Yeni Meta Title"


@pytest.mark.anyio
async def test_save_intent_uses_deterministic_history_extraction_and_populates_panel(monkeypatch):
    service = ChatService(_make_config(ai_thinking_mode_chat=False))
    _stub_routing(service)
    product = _make_product(name="60X Mikroskop", meta_title="60X Mikroskop")
    service.set_product_context(product, _make_score())
    service._schedule_history_summarization = lambda: None  # type: ignore[method-assign]
    service._history.append(
        ChatMessage(
            role="assistant",
            content=(
                "1. Urun Adi\n"
                "Mevcut: 60X Mikroskop\n"
                "Oneri: Airontek 60X Mini-Mikroskop - Tasinabilir ve Mavi Isikli\n\n"
                "2. Meta Title\n"
                "Mevcut: 60X Mikroskop\n"
                "Oneri: Airontek 60X Mini-Mikroskop | Tasinabilir Inceleme\n\n"
                "3. Meta Description\n"
                "Mevcut: 320 karakter\n"
                "Oneri: Airontek 60X mini mikroskop, tasinabilir govdesi ve mavi isik destegiyle detayli inceleme sunar."
            ),
        )
    )

    async def fail_chat_completion(messages, tools):
        raise AssertionError("Deterministic history extraction should avoid LLM fallback")

    monkeypatch.setattr(service, "_chat_completion", fail_chat_completion)

    response = await service.send_message("kaydet")

    assert response.error is False
    assert response.suggestion_saved is not None
    assert "Bekleyen SEO degisiklikleri kaydedildi." in response.content
    assert "single_apply_all" in response.content or "Uygula" in response.content
    assert response.suggestion_saved["fields"]["suggested_name"].startswith("Airontek 60X Mini-Mikroskop")
    assert response.pending_suggestion is not None
    assert response.pending_suggestion.suggested_meta_title == "Airontek 60X Mini-Mikroskop | Tasinabilir Inceleme"


@pytest.mark.anyio
async def test_explicit_ikas_apply_uses_deterministic_parser_when_llm_extractor_fails(monkeypatch):
    service = ChatService(_make_config(ai_thinking_mode_chat=False))
    _stub_routing(service)
    product = _make_product(name="60X Mikroskop", meta_title="60X Mikroskop")
    service.set_product_context(product, _make_score())
    service._schedule_history_summarization = lambda: None  # type: ignore[method-assign]
    service._history.append(
        ChatMessage(
            role="assistant",
            content=(
                "2. Meta Title\n"
                "Mevcut: 60X Mikroskop\n"
                "Oneri: Airontek 60X Mini-Mikroskop | Tasinabilir Inceleme"
            ),
        )
    )

    async def fail_chat_completion(messages, tools):
        raise AssertionError("Deterministic parser should avoid LLM extractor fallback")

    monkeypatch.setattr(service, "_chat_completion", fail_chat_completion)

    response = await service.send_message("uygula")

    assert response.error is False
    assert "Ne yapmak istersiniz" in response.content
    assert "single_apply_all" in response.content
    assert response.pending_suggestion is not None
    assert response.pending_suggestion.suggested_meta_title == "Airontek 60X Mini-Mikroskop | Tasinabilir Inceleme"


@pytest.mark.anyio
async def test_chat_apply_logs_score_change_for_reports(monkeypatch):
    service = ChatService(_make_config(ai_thinking_mode_chat=False, dry_run=False))
    _stub_routing(service)
    product = _make_product(description_translations={"tr": "Bir test aciklamasi"})
    old_score = _make_score(total_score=60, english_description_score=0)
    new_score = _make_score(total_score=65, english_description_score=5)
    service.set_product_context(product, old_score)

    await service._save_suggestion_from_tool_args(
        {"suggested_description_en": "<p>English description</p>"}
    )
    suggestion = service._get_session_pending_suggestion(product.id)
    assert suggestion is not None
    available_fields = service._collect_applicable_suggestion_fields(suggestion)

    async def fake_tool_invoke(tool_name, args, agent_type=None):
        class _Execution:
            ok = True
            content = '{"ok": true}'
            error = None

        assert tool_name == "apply_seo_to_ikas"
        assert args["product_id"] == product.id
        assert args["description_en"] == "<p>English description</p>"
        return _Execution()

    class _FakeIkasClient:
        async def get_product_by_id(self, product_id):
            assert product_id == product.id
            return product.model_copy(update={
                "description_translations": {
                    **product.description_translations,
                    "en": "<p>English description</p>",
                },
            })

        async def close(self):
            return None

    logged: dict[str, object] = {}

    async def fake_save_product(updated_product):
        return None

    async def fake_save_score(score):
        return None

    async def fake_insert_score_change_log(**kwargs):
        logged.update(kwargs)

    monkeypatch.setattr(service._tool_registry, "invoke", fake_tool_invoke)
    monkeypatch.setattr("core.chat.suggestions.IkasClient", _FakeIkasClient)
    monkeypatch.setattr("core.chat.suggestions.analyze_product", lambda _product, _keywords=None: new_score)
    monkeypatch.setattr("core.chat.suggestions.db_save_product", fake_save_product)
    monkeypatch.setattr("core.chat.suggestions.db_save_score", fake_save_score)
    monkeypatch.setattr("core.chat.suggestions.db_insert_score_change_log", fake_insert_score_change_log)

    response_text, tool_results, pending = await service._execute_apply(
        suggestion,
        available_fields,
        selected_fields=["suggested_description_en"],
    )

    assert "SEO Skor Degisimi" in response_text
    assert tool_results[0]["tool"] == "chat_single_product_apply"
    assert pending is None
    assert logged == {
        "product_id": product.id,
        "product_name": product.name,
        "operation": "apply",
        "score_before": 60,
        "score_after": 65,
    }


@pytest.mark.anyio
async def test_chat_apply_keeps_pending_when_live_en_description_is_missing(monkeypatch):
    service = ChatService(_make_config(ai_thinking_mode_chat=False, dry_run=False))
    _stub_routing(service)
    product = _make_product(description_translations={"tr": "Bir test aciklamasi"})
    old_score = _make_score(total_score=60, english_description_score=0)
    service.set_product_context(product, old_score)

    await service._save_suggestion_from_tool_args(
        {"suggested_description_en": "<p>English description</p>"}
    )
    suggestion = service._get_session_pending_suggestion(product.id)
    assert suggestion is not None
    available_fields = service._collect_applicable_suggestion_fields(suggestion)

    async def fake_tool_invoke(tool_name, args, agent_type=None):
        class _Execution:
            ok = True
            content = '{"ok": true}'
            error = None

        assert tool_name == "apply_seo_to_ikas"
        assert args["description_en"] == "<p>English description</p>"
        return _Execution()

    class _FakeIkasClient:
        async def get_product_by_id(self, product_id):
            assert product_id == product.id
            return product

        async def close(self):
            return None

    monkeypatch.setattr(service._tool_registry, "invoke", fake_tool_invoke)
    monkeypatch.setattr("core.chat.suggestions.IkasClient", _FakeIkasClient)

    response_text, tool_results, pending = await service._execute_apply(
        suggestion,
        available_fields,
        selected_fields=["suggested_description_en"],
    )

    assert "canli veride dogrulanamadi" in response_text
    assert "Aciklama (EN)" in response_text
    assert tool_results == []
    assert pending is not None
    assert pending.suggested_description_en == "<p>English description</p>"
