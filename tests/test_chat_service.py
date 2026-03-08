"""Tests for core/chat_service.py — multi-turn chat with MCP."""

import httpx
import pytest

from core.chat_service import (
    APPLY_INTENT_PATTERN,
    ChatService,
    _append_false_action_disclaimer,
    _build_completion_meta,
    _build_product_context,
    _extract_message_directives,
    _has_mutation_tool_result,
)
from core.models import AppConfig, ChatMessage, Product, SeoScore


def _make_config(**overrides) -> AppConfig:
    defaults = {
        "ikas_store_name": "test-store",
        "ikas_client_id": "cid",
        "ikas_client_secret": "csec",
        "ai_provider": "ollama",
        "ai_model_name": "llama3.2",
        "ai_base_url": "http://localhost:11434/v1",
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


def _make_product(**overrides) -> Product:
    defaults = {
        "id": "prod-1",
        "name": "Test Urun",
        "description": "Bir test aciklamasi",
        "category": "Elektronik",
        "price": 199.99,
        "meta_title": "Test Urun - En Iyi Fiyat",
        "meta_description": "Test urun aciklamasi burada",
        "tags": ["test", "urun"],
    }
    defaults.update(overrides)
    return Product(**defaults)


def _make_score(**overrides) -> SeoScore:
    defaults = {
        "product_id": "prod-1",
        "total_score": 65,
        "title_score": 10,
        "description_score": 12,
        "meta_score": 8,
        "meta_desc_score": 5,
        "keyword_score": 5,
        "content_quality_score": 7,
        "technical_seo_score": 8,
        "readability_score": 3,
        "issues": ["Baslik cok kisa", "Meta description eksik"],
    }
    defaults.update(overrides)
    return SeoScore(**defaults)


def test_chat_service_init():
    config = _make_config()
    service = ChatService(config)
    assert not service.has_mcp
    assert not service.mcp_initialized
    assert service.history == []
    assert service.total_tokens == {"input": 0, "output": 0}


def test_chat_service_has_mcp_with_token():
    config = _make_config(ikas_mcp_token="mcp_test_token")
    service = ChatService(config)
    assert service.has_mcp


def test_set_product_context():
    config = _make_config()
    service = ChatService(config)
    product = _make_product()
    score = _make_score()
    service.set_product_context(product, score)
    assert service._product is product
    assert service._score is score


def test_clear_history():
    config = _make_config()
    service = ChatService(config)
    service._history.append(ChatMessage(role="user", content="test"))
    assert len(service.history) == 1
    service.clear_history()
    assert service.history == []


def test_build_product_context_without_product():
    ctx = _build_product_context(None, None)
    assert "asistan" in ctx.lower() or "mağaza" in ctx.lower()


def test_build_product_context_mentions_chat_roles():
    ctx = _build_product_context(None, None)
    assert "local ai" in ctx.lower()
    assert "ikas mcp" in ctx.lower()


def test_build_product_context_mentions_supported_operations_and_next_step_behavior():
    ctx = _build_product_context(None, None)
    assert "listproduct" in ctx.lower()
    assert "updateproduct" in ctx.lower()
    assert "sonraki adim" in ctx.lower()


def test_build_product_context_limits_default_scope_to_current_seo_data():
    ctx = _build_product_context(None, None)
    assert "yalnizca mevcut seo metrikleri" in ctx.lower()
    assert "eldeki alanlariyla sinirla" in ctx.lower()


def test_extract_message_directives_ikas_forces_tools():
    cleaned, instruction, allow_tools = _extract_message_directives("@ikas stok durumunu kontrol et")
    assert cleaned == "stok durumunu kontrol et"
    assert instruction is not None and "@ikas" in instruction
    assert allow_tools is True


def test_extract_message_directives_local_disables_tools():
    cleaned, instruction, allow_tools = _extract_message_directives("@local seo skorunu yorumla")
    assert cleaned == "seo skorunu yorumla"
    assert instruction is not None and "@local" in instruction
    assert "mevcut seo metrikleri" in instruction.lower()
    assert "degisiklik uygulayamazsin" in instruction.lower() or "oneriler panel" in instruction.lower()
    assert allow_tools is False


def test_extract_message_directives_without_mentions_stays_local():
    cleaned, instruction, allow_tools = _extract_message_directives("seo skorunu yorumla")
    assert cleaned == "seo skorunu yorumla"
    assert instruction is not None
    assert allow_tools is False


def test_extract_message_directives_combined_mentions():
    cleaned, instruction, allow_tools = _extract_message_directives("@ikas @local varyantlari ozetle")
    assert cleaned == "varyantlari ozetle"
    assert instruction is not None
    assert allow_tools is True


def test_build_product_context_with_product():
    product = _make_product(name="Akilli Saat", price=599.99)
    ctx = _build_product_context(product, None)
    assert "Akilli Saat" in ctx
    assert "599.99" in ctx


def test_build_product_context_with_score():
    product = _make_product()
    score = _make_score(total_score=42)
    ctx = _build_product_context(product, score)
    assert "42/100" in ctx
    assert "Baslik cok kisa" in ctx


def test_extract_thinking():
    text = "Some text <think>This is my reasoning</think> Final answer"
    result = ChatService._extract_thinking(text)
    assert result == "This is my reasoning"


def test_extract_thinking_no_block():
    result = ChatService._extract_thinking("Just normal text")
    assert result == ""


def test_remove_thinking():
    text = "<think>reasoning here</think>Final answer"
    result = ChatService._remove_thinking(text)
    assert result == "Final answer"


def test_extract_thinking_with_unclosed_block():
    text = "<think>unfinished reasoning"
    result = ChatService._extract_thinking(text)
    assert result == "unfinished reasoning"


def test_remove_thinking_with_unclosed_block():
    text = "<think>unfinished reasoning"
    result = ChatService._remove_thinking(text)
    assert result == ""


def test_get_base_url_with_config():
    config = _make_config(ai_base_url="http://localhost:11434/v1")
    service = ChatService(config)
    assert "localhost:11434" in service._get_base_url()


def test_get_base_url_defaults():
    config = _make_config(ai_provider="ollama", ai_base_url="")
    service = ChatService(config)
    assert "11434" in service._get_base_url()

    config2 = _make_config(ai_provider="lm-studio", ai_base_url="")
    service2 = ChatService(config2)
    assert "1234" in service2._get_base_url()


def test_get_default_model():
    config = _make_config(ai_provider="ollama")
    service = ChatService(config)
    assert service._get_default_model() == "llama3.2"

    config2 = _make_config(ai_provider="openai")
    service2 = ChatService(config2)
    assert service2._get_default_model() == "gpt-4o-mini"


def test_build_completion_meta_uses_stats_and_context_length():
    meta = _build_completion_meta(
        {
            "model": "turkish-gemma-9b",
            "stats": {
                "input_tokens": 917,
                "total_output_tokens": 899,
                "tokens_per_second": 14.49,
                "time_to_first_token_seconds": 0.43,
                "reasoning_output_tokens": 120,
            },
            "model_info": {
                "context_length": 4096,
            },
        },
        "turkish-gemma-9b",
        "stop",
    )

    assert meta["input_tokens"] == 917
    assert meta["output_tokens"] == 899
    assert meta["total_tokens"] == 1816
    assert meta["context_length"] == 4096
    assert meta["tokens_per_second"] == 14.49
    assert meta["time_to_first_token_seconds"] == 0.43
    assert meta["context_used_percent"] == 22.4


@pytest.mark.anyio
async def test_send_message_local_does_not_pass_tools_even_if_mcp_ready():
    config = _make_config(ai_provider="lm-studio", ai_thinking_mode=False)
    service = ChatService(config)
    service.set_product_context(_make_product(), _make_score())
    service._mcp_initialized = True
    service._mcp = object()
    captured: dict[str, object] = {}

    async def fake_chat_completion(messages, tools):
        captured["messages"] = messages
        captured["tools"] = tools
        return "Kisa yanit", "", [], {"model": "lm-studio-test"}

    service._chat_completion = fake_chat_completion  # type: ignore[method-assign]

    response = await service.send_message("@local seo skorunu yorumla")

    assert response.error is False
    assert "ikas MCP Operasyon Onerisi" in response.content
    assert "`updateProduct`" in response.content
    assert captured["tools"] is None
    system_messages = [
        msg["content"]
        for msg in captured["messages"]  # type: ignore[index]
        if msg["role"] == "system"
    ]
    assert any("/no_think" in content for content in system_messages)


@pytest.mark.anyio
async def test_send_message_appends_seo_operation_suggestion_for_existing_product_fields():
    config = _make_config(ai_provider="lm-studio", ai_thinking_mode=False)
    service = ChatService(config)
    service.set_product_context(_make_product(name="Bud Candy 250 ML"), _make_score())

    async def fake_chat_completion(messages, tools):
        return "Aciklama girisi zayif, fayda dili daha belirgin olabilir.", "", [], {"model": "lm-studio-test"}

    service._chat_completion = fake_chat_completion  # type: ignore[method-assign]

    response = await service.send_message("@local urun aciklamasini yorumla")

    assert response.error is False
    assert "ikas MCP Operasyon Onerisi" in response.content
    assert "`updateProduct`" in response.content
    assert "mutation" in response.content.lower()


@pytest.mark.anyio
async def test_send_message_timeout_returns_clear_error_and_drops_failed_user():
    config = _make_config(ai_provider="lm-studio")
    service = ChatService(config)
    service.set_product_context(_make_product(), _make_score())

    async def fake_chat_completion(messages, tools):
        raise httpx.ReadTimeout("timed out")

    service._chat_completion = fake_chat_completion  # type: ignore[method-assign]

    response = await service.send_message("@local Bu urunun SEO skorunu hizlica acikla")

    assert response.error is True
    assert "zaman asimina" in response.content.lower()
    assert "ikas mcp operasyon onerisi" in response.content.lower()
    assert service.history == []


# ── False action disclaimer tests ────────────────────────────────────────


def test_false_action_disclaimer_appended_when_llm_claims_update():
    """LLM says 'güncelledim' but no MCP mutation was called."""
    response = "Meta title güncellendi. Yeni skor: 80/100."
    result = _append_false_action_disclaimer(response, [])
    assert "henüz uygulanmadı" in result
    assert "Öneriler" in result


def test_false_action_disclaimer_appended_for_uyguladim():
    response = "Değişiklikler uyguladım, artık skor daha yüksek olacak."
    result = _append_false_action_disclaimer(response, [])
    assert "henüz uygulanmadı" in result


def test_false_action_disclaimer_appended_for_confirmation_phrases():
    response = "Uygulama Sonrası Meta Title: Airontek 60X Taşınabilir Mikroskop"
    result = _append_false_action_disclaimer(response, [])
    assert "henüz uygulanmadı" in result


def test_false_action_disclaimer_not_appended_for_normal_suggestion():
    """Normal suggestions without action claims should not get disclaimer."""
    response = "Meta title'ı şu şekilde değiştirmenizi öneriyorum: 'Airontek 60X Mikroskop'"
    result = _append_false_action_disclaimer(response, [])
    assert "henüz uygulanmadı" not in result


def test_false_action_disclaimer_not_appended_when_mutation_succeeded():
    """If a mutation was actually called, the claim is legitimate."""
    response = "updateProduct ile meta title güncellendi."
    tool_results = [{"tool": "updateProduct", "arguments": {}, "result": '{"data": {"ok": true}}'}]
    result = _append_false_action_disclaimer(response, tool_results)
    assert "henüz uygulanmadı" not in result


def test_false_action_disclaimer_appended_when_mutation_had_error():
    """If mutation was called but returned error, disclaimer should appear."""
    response = "Meta title güncellendi."
    tool_results = [{"tool": "updateProduct", "arguments": {}, "result": '{"error": "unauthorized"}'}]
    result = _append_false_action_disclaimer(response, tool_results)
    assert "henüz uygulanmadı" in result


def test_false_action_disclaimer_not_duplicated():
    """Don't add disclaimer if already present."""
    response = "Güncellendi.\n\n---\n⚠️ **Not:** Yukarıdaki öneriler henüz uygulanmadı."
    result = _append_false_action_disclaimer(response, [])
    assert result.count("henüz uygulanmadı") == 1


def test_has_mutation_tool_result_detects_mutations():
    assert _has_mutation_tool_result([
        {"tool": "updateProduct", "arguments": {}, "result": '{"ok": true}'}
    ])
    assert _has_mutation_tool_result([
        {"tool": "createProduct", "arguments": {}, "result": '{"id": "123"}'}
    ])
    assert not _has_mutation_tool_result([
        {"tool": "listProduct", "arguments": {}, "result": '{"data": []}'}
    ])
    assert not _has_mutation_tool_result([])


@pytest.mark.anyio
async def test_send_message_adds_disclaimer_when_llm_hallucinates_action():
    """End-to-end: LLM claims it updated something in @local mode → disclaimer appended."""
    config = _make_config(ai_provider="lm-studio", ai_thinking_mode=False)
    service = ChatService(config)
    service.set_product_context(_make_product(), _make_score())

    async def fake_chat_completion(messages, tools):
        return "Meta title güncellendi! Yeni skor: 80/100.", "", [], {"model": "test"}

    service._chat_completion = fake_chat_completion  # type: ignore[method-assign]

    response = await service.send_message("@local meta title guncelle")

    assert response.error is False
    assert "henüz uygulanmadı" in response.content
    assert "Öneriler" in response.content


# ── Apply intent detection tests ─────────────────────────────────────────


def test_apply_intent_pattern_matches_turkish():
    assert APPLY_INTENT_PATTERN.search("bunu uygula")
    assert APPLY_INTENT_PATTERN.search("Seçenek B uygula")
    assert APPLY_INTENT_PATTERN.search("secenek A kaydet")
    assert APPLY_INTENT_PATTERN.search("bu öneriyi uygula")
    assert APPLY_INTENT_PATTERN.search("bu değişikliği kaydet")
    assert APPLY_INTENT_PATTERN.search("hepsini uygula")
    assert APPLY_INTENT_PATTERN.search("tümünü kaydet")


def test_apply_intent_pattern_matches_english():
    assert APPLY_INTENT_PATTERN.search("apply")
    assert APPLY_INTENT_PATTERN.search("save this suggestion")
    assert APPLY_INTENT_PATTERN.search("save these")


def test_apply_intent_pattern_does_not_match_questions():
    assert not APPLY_INTENT_PATTERN.search("meta title nasıl olmalı")
    assert not APPLY_INTENT_PATTERN.search("SEO skorunu yorumla")
    assert not APPLY_INTENT_PATTERN.search("açıklamayı analiz et")


@pytest.mark.anyio
async def test_handle_apply_intent_no_history():
    """Apply intent with no conversation history returns error."""
    config = _make_config(ai_provider="lm-studio")
    service = ChatService(config)
    service.set_product_context(_make_product(), _make_score())
    # No history → no assistant messages → should error

    response = await service.send_message("bunu uygula")

    assert "kaydedilecek bir öneri yok" in response.content.lower() or response.error


@pytest.mark.anyio
async def test_handle_apply_intent_creates_suggestion(monkeypatch):
    """Apply intent with conversation history extracts and saves suggestion."""
    import json as _json
    config = _make_config(ai_provider="lm-studio", ai_thinking_mode=False)
    service = ChatService(config)
    product = _make_product(name="60X Mikroskop")
    service.set_product_context(product, _make_score())

    # Simulate prior conversation
    service._history.append(ChatMessage(role="user", content="meta title oner"))
    service._history.append(ChatMessage(
        role="assistant",
        content="Meta title onerim: 'Airontek 60X Tasinabilir Mikroskop | Mavi Isik'",
    ))

    # Mock the extraction LLM call
    extraction_response = _json.dumps({
        "suggested_meta_title": "Airontek 60X Tasinabilir Mikroskop | Mavi Isik",
        "suggested_meta_description": "",
        "suggested_name": "",
        "suggested_description": "",
        "suggested_description_en": "",
    })

    async def fake_post(self_client, url, **kwargs):
        class FakeResponse:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {
                    "choices": [{"message": {"content": extraction_response}}],
                }
        return FakeResponse()

    import httpx as _httpx
    monkeypatch.setattr(_httpx.AsyncClient, "post", fake_post)

    # Mock DB save to track what was saved
    saved_suggestions = []

    def fake_save(suggestion):
        saved_suggestions.append(suggestion)

    import data.db as _db
    monkeypatch.setattr(_db, "save_or_update_pending_suggestion", fake_save)

    response = await service.send_message("bunu uygula")

    assert response.error is False
    assert response.suggestion_saved is not None
    assert response.suggestion_saved["product_id"] == product.id
    assert "suggested_meta_title" in response.suggestion_saved["fields"]
    assert "kaydedildi" in response.content.lower()
    assert len(saved_suggestions) == 1
    assert saved_suggestions[0].suggested_meta_title == "Airontek 60X Tasinabilir Mikroskop | Mavi Isik"
