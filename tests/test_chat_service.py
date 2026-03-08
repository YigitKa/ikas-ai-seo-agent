"""Tests for core/chat_service.py — multi-turn chat with MCP."""

import httpx
import pytest

from core.chat_service import (
    ChatService,
    _build_completion_meta,
    _build_product_context,
    _extract_message_directives,
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
    assert "operasyon" in instruction.lower()
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
