"""Tests for core/chat_service.py — multi-turn chat with MCP."""

import pytest

from core.chat_service import ChatService, _build_product_context
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
