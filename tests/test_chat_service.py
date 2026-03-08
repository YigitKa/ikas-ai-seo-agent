"""Tests for core/chat_service.py — multi-turn chat with MCP."""

import httpx
import pytest

from core.chat_service import (
    ChatService,
    SAVE_SEO_SUGGESTION_TOOL_NAME,
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
async def test_send_message_local_passes_only_save_suggestion_tool_even_if_mcp_ready():
    config = _make_config(ai_provider="lm-studio", ai_thinking_mode=False)
    service = ChatService(config)
    product = _make_product()
    service.set_product_context(product, _make_score())
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
    tools = captured["tools"]
    assert isinstance(tools, list)
    assert [tool["function"]["name"] for tool in tools] == [SAVE_SEO_SUGGESTION_TOOL_NAME]
    system_messages = [
        msg["content"]
        for msg in captured["messages"]  # type: ignore[index]
        if msg["role"] == "system"
    ]
    assert any("/no_think" in content for content in system_messages)
    assert any("save_seo_suggestion" in content for content in system_messages)


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


def test_save_suggestion_tool_name_is_stable():
    assert SAVE_SEO_SUGGESTION_TOOL_NAME == "save_seo_suggestion"


def test_local_routing_keeps_mcp_tools_disabled():
    cleaned, instruction, allow_tools = _extract_message_directives("@local bunu uygula")
    assert cleaned == "bunu uygula"
    assert instruction is not None
    assert "save_seo_suggestion" in instruction
    assert allow_tools is False


def test_default_routing_is_local_without_mentions():
    cleaned, instruction, allow_tools = _extract_message_directives("bunu kaydet")
    assert cleaned == "bunu kaydet"
    assert instruction is not None
    assert allow_tools is False


@pytest.mark.anyio
async def test_handle_apply_intent_no_history():
    """Apply intent with no conversation history returns error."""
    config = _make_config(ai_provider="openai", ai_base_url="https://example.com/v1")
    service = ChatService(config)
    product = _make_product()
    service.set_product_context(product, _make_score())

    saved_suggestions = []

    def fake_save(suggestion):
        saved_suggestions.append(suggestion)

    import data.db as _db
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(_db, "save_or_update_pending_suggestion", fake_save)

    lines = [
        'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"save_seo_suggestion","arguments":"{"}}]},"finish_reason":null}]}',
        "",
        'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"suggested_meta_title\\": \\"Yeni Meta Title\\"}"}}]},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":4,"completion_tokens":3,"total_tokens":7}}',
        "",
        "data: [DONE]",
        "",
    ]

    def fake_stream(self_client, method, url, **kwargs):
        return _FakeStreamContext(_FakeStreamResponse(lines))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)
    # No history → no assistant messages → should error

    try:
        response = await service.send_message("bunu uygula")
    finally:
        monkeypatch.undo()

    assert response.error is False
    assert response.content == "Öneri başarıyla kaydedildi"
    assert response.suggestion_saved is not None
    assert response.suggestion_saved["product_id"] == product.id
    assert response.suggestion_saved["fields"]["suggested_meta_title"] == "Yeni Meta Title"
    assert len(saved_suggestions) == 1


@pytest.mark.anyio
async def test_handle_apply_intent_creates_suggestion(monkeypatch):
    config = _make_config(ai_provider="openai", ai_base_url="https://example.com/v1")
    service = ChatService(config)
    product = _make_product(name="60X Mikroskop")
    service.set_product_context(product, _make_score())

    saved_suggestions = []

    def fake_save(suggestion):
        saved_suggestions.append(suggestion)

    import data.db as _db
    monkeypatch.setattr(_db, "save_or_update_pending_suggestion", fake_save)

    lines = [
        'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"save_seo_suggestion","arguments":"{"}}]},"finish_reason":null}]}',
        "",
        'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"suggested_meta_title\\": \\"Airontek 60X Tasinabilir Mikroskop | Mavi Isik\\""}}]},"finish_reason":null}]}',
        "",
        'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":", \\"suggested_description\\": \\"Yeni urun aciklamasi\\"}"}}]},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":4,"completion_tokens":3,"total_tokens":7}}',
        "",
        "data: [DONE]",
        "",
    ]

    def fake_stream(self_client, method, url, **kwargs):
        return _FakeStreamContext(_FakeStreamResponse(lines))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    response = await service.send_message("bunu uygula")

    assert response.error is False
    assert response.content == "Öneri başarıyla kaydedildi"
    assert response.suggestion_saved is not None
    assert response.suggestion_saved["product_id"] == product.id
    assert response.suggestion_saved["fields"]["suggested_meta_title"] == "Airontek 60X Tasinabilir Mikroskop | Mavi Isik"
    assert response.suggestion_saved["fields"]["suggested_description"] == "Yeni urun aciklamasi"
    assert response.tool_results[0]["tool"] == SAVE_SEO_SUGGESTION_TOOL_NAME
    assert len(saved_suggestions) == 1
    assert saved_suggestions[0].suggested_meta_title == "Airontek 60X Tasinabilir Mikroskop | Mavi Isik"
    assert saved_suggestions[0].suggested_description == "Yeni urun aciklamasi"
    return

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


class _FakeStreamResponse:
    def __init__(self, lines, content_type: str = "text/event-stream"):
        self._lines = lines
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b""


class _FakeStreamContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.anyio
async def test_async_stream_chat_yields_content_chunks_from_sse(monkeypatch):
    config = _make_config(ai_provider="openai", ai_base_url="https://example.com/v1")
    service = ChatService(config)

    lines = [
        'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"content":"Mer"},"finish_reason":null}]}',
        "",
        'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"content":"haba"},"finish_reason":null}]}',
        "",
        'data: {"model":"gpt-test","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5}}',
        "",
        "data: [DONE]",
        "",
    ]

    def fake_stream(self_client, method, url, **kwargs):
        assert method == "POST"
        assert url.endswith("/chat/completions")
        assert kwargs["json"]["stream"] is True
        return _FakeStreamContext(_FakeStreamResponse(lines))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    events = [event async for event in service.async_stream_chat(
        [{"role": "user", "content": "Merhaba de"}],
        None,
    )]

    assert [event["type"] for event in events] == ["chunk", "chunk", "completion_result"]
    assert [event["content"] for event in events[:2]] == ["Mer", "haba"]
    assert events[-1]["content"] == "Merhaba"
    assert events[-1]["meta"]["model"] == "gpt-test"
    assert service.total_tokens == {"input": 3, "output": 2}


@pytest.mark.anyio
async def test_async_stream_chat_buffers_tool_calls_until_final_response(monkeypatch):
    config = _make_config(ai_provider="openai", ai_base_url="https://example.com/v1")
    service = ChatService(config)
    tool_invocations = []

    class FakeMCP:
        async def call_tool(self, name, args):
            tool_invocations.append((name, args))
            return {"ok": True, "product_id": args.get("id")}

        def get_tool_names(self):
            return ["listProduct"]

    service._mcp = FakeMCP()
    service._mcp_initialized = True

    stream_rounds = [
        [
            'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"listProduct","arguments":"{"}}]},"finish_reason":null}]}',
            "",
            'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\\"id\\": \\"prod-1\\""}}]},"finish_reason":null}]}',
            "",
            'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"}"}}]},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":4,"completion_tokens":3,"total_tokens":7}}',
            "",
            "data: [DONE]",
            "",
        ],
        [
            'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"content":"Tamam"},"finish_reason":null}]}',
            "",
            'data: {"model":"gpt-test","choices":[{"index":0,"delta":{"content":"landi"},"finish_reason":null}]}',
            "",
            'data: {"model":"gpt-test","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":2,"total_tokens":7}}',
            "",
            "data: [DONE]",
            "",
        ],
    ]

    def fake_stream(self_client, method, url, **kwargs):
        return _FakeStreamContext(_FakeStreamResponse(stream_rounds.pop(0)))

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    events = [event async for event in service.async_stream_chat(
        [{"role": "user", "content": "@ikas urunu kontrol et"}],
        [{"type": "function", "function": {"name": "listProduct"}}],
    )]

    assert [event["type"] for event in events] == ["chunk", "chunk", "completion_result"]
    assert "".join(event["content"] for event in events[:-1]) == "Tamamlandi"
    assert tool_invocations == [("listProduct", {"id": "prod-1"})]
    assert events[-1]["tool_results"][0]["tool"] == "listProduct"
    assert events[-1]["content"] == "Tamamlandi"


@pytest.mark.anyio
async def test_stream_message_emits_response_done_after_chunks():
    config = _make_config(ai_provider="openai", ai_base_url="https://example.com/v1")
    service = ChatService(config)

    async def fake_chat_completion_stream(messages, tools, chunk_handler):
        await chunk_handler("Mer")
        await chunk_handler("haba")
        return "Merhaba", "", [], {"model": "stream-test"}

    service._chat_completion_stream = fake_chat_completion_stream  # type: ignore[method-assign]

    events = [event async for event in service.stream_message("selam")]

    assert [event["type"] for event in events] == ["chunk", "chunk", "response_done"]
    assert [event["content"] for event in events[:2]] == ["Mer", "haba"]
    assert events[-1]["content"].startswith("Merhaba")
    assert events[-1]["meta"]["model"] == "stream-test"
