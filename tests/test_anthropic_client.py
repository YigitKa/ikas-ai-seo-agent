"""Tests for AnthropicAIClient — Claude API integration.

Covers all methods, extended thinking, cancellation, streaming,
token tracking, and cost estimation.
"""

import json
import threading
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from core.ai.client import (
    AnthropicAIClient,
    create_ai_client,
    _parse_response_text,
    _extract_thinking,
    _merge_thinking_text,
    build_product_rewrite_request,
    build_field_rewrite_request,
    build_geo_rewrite_request,
    build_en_translation_request,
    DEFAULT_MODELS,
)
from core.models import AppConfig, Product, SeoScore, SeoSuggestion


# ── Helpers ──────────────────────────────────────────────────────────────


def _build_config(**overrides) -> AppConfig:
    values = {
        "ai_provider": "anthropic",
        "ai_api_key": "sk-ant-test-key-123",
        "ai_model_name": "",
        "ai_temperature": 0.7,
        "ai_max_tokens": 2000,
        "ai_thinking_mode": False,
        "store_languages": ["tr"],
    }
    values.update(overrides)
    return AppConfig(**values)


def _build_product(**overrides) -> Product:
    defaults = {
        "id": "p1",
        "name": "Nike Air Max 270 Kadin Spor Ayakkabi",
        "category": "Kadin Ayakkabi",
        "description": "<p>Konforlu spor ayakkabi</p>",
        "description_translations": {"en": "Comfortable sports shoe"},
        "meta_title": "Nike Air Max",
        "meta_description": "En iyi spor ayakkabi",
    }
    defaults.update(overrides)
    return Product(**defaults)


def _build_score(**overrides) -> SeoScore:
    defaults = {
        "product_id": "p1",
        "total_score": 45,
        "title_score": 10,
        "description_score": 10,
        "meta_score": 8,
        "meta_desc_score": 7,
        "keyword_score": 5,
        "issues": ["Baslik cok kisa", "Meta aciklama eksik"],
    }
    defaults.update(overrides)
    return SeoScore(**defaults)


def _mock_anthropic_response(
    text: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
    model: str = "claude-haiku-4-5-20251001",
    stop_reason: str = "end_turn",
    thinking_text: str | None = None,
):
    """Build a mock Anthropic Messages API response."""
    response = MagicMock()

    content_blocks = []
    if thinking_text:
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thinking = thinking_text
        content_blocks.append(thinking_block)

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text
    content_blocks.append(text_block)

    response.content = content_blocks

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    response.usage = usage

    response.model = model
    response.stop_reason = stop_reason
    response.id = "msg_test123"

    return response


# ── Factory ──────────────────────────────────────────────────────────────


def test_create_ai_client_returns_anthropic_client():
    config = _build_config()
    with patch("core.ai.client.AnthropicAIClient") as MockClass:
        MockClass.return_value = MagicMock()
        client = create_ai_client(config)
        MockClass.assert_called_once_with(config)


def test_create_ai_client_none_provider():
    config = _build_config(ai_provider="none", ai_api_key="")
    client = create_ai_client(config)
    assert client.__class__.__name__ == "NoneAIClient"


# ── Initialization ──────────────────────────────────────────────────────


def test_anthropic_client_uses_default_model():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_model_name=""))
        assert client._model == DEFAULT_MODELS["anthropic"]


def test_anthropic_client_uses_custom_model():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_model_name="claude-sonnet-4-20250514"))
        assert client._model == "claude-sonnet-4-20250514"


def test_anthropic_client_uses_legacy_api_key():
    with patch("anthropic.Anthropic") as MockAnthropic:
        config = _build_config(ai_api_key="", anthropic_api_key="sk-ant-legacy-key")
        client = AnthropicAIClient(config)
        MockAnthropic.assert_called_once_with(api_key="sk-ant-legacy-key")


def test_anthropic_client_prefers_ai_api_key_over_legacy():
    with patch("anthropic.Anthropic") as MockAnthropic:
        config = _build_config(ai_api_key="sk-ant-new", anthropic_api_key="sk-ant-old")
        client = AnthropicAIClient(config)
        MockAnthropic.assert_called_once_with(api_key="sk-ant-new")


def test_anthropic_client_thinking_mode_flag():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=True))
        assert client._thinking_mode is True

        client2 = AnthropicAIClient(_build_config(ai_thinking_mode=False))
        assert client2._thinking_mode is False


# ── _build_create_kwargs ─────────────────────────────────────────────────


def test_build_create_kwargs_normal_mode():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=False))
        kwargs = client._build_create_kwargs("System", "User msg", 2000)

    assert kwargs["model"] == DEFAULT_MODELS["anthropic"]
    assert kwargs["max_tokens"] == 2000
    assert kwargs["system"] == "System"
    assert kwargs["messages"] == [{"role": "user", "content": "User msg"}]
    assert "thinking" not in kwargs
    assert "temperature" not in kwargs


def test_build_create_kwargs_thinking_mode():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=True))
        kwargs = client._build_create_kwargs("System", "User", 2000)

    assert kwargs["temperature"] == 1  # Required for extended thinking
    assert kwargs["thinking"]["type"] == "enabled"
    assert kwargs["thinking"]["budget_tokens"] >= 2000
    assert kwargs["max_tokens"] >= 8000  # Increased for thinking + response


def test_build_create_kwargs_thinking_budget_minimum():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=True, ai_max_tokens=500))
        kwargs = client._build_create_kwargs("Sys", "User", 500)

    assert kwargs["thinking"]["budget_tokens"] == 1024  # Minimum 1024


# ── _extract_response ───────────────────────────────────────────────────


def test_extract_response_text_only():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config())

    response = _mock_anthropic_response('{"suggested_name": "Test"}')
    text, thinking = client._extract_response(response)
    assert '{"suggested_name": "Test"}' in text
    assert thinking == ""


def test_extract_response_with_native_thinking():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=True))

    response = _mock_anthropic_response(
        '{"suggested_name": "Optimized"}',
        thinking_text="I need to analyze the product title for SEO...",
    )
    text, thinking = client._extract_response(response)
    assert '{"suggested_name": "Optimized"}' in text
    assert "I need to analyze the product title" in thinking


def test_extract_response_with_think_tags_fallback():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config())

    response = _mock_anthropic_response(
        '<think>Reasoning here</think>{"suggested_name": "Result"}'
    )
    text, thinking = client._extract_response(response)
    assert "Reasoning here" in thinking


# ── Token tracking ───────────────────────────────────────────────────────


def test_token_tracking_accumulates():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config())

    resp1 = _mock_anthropic_response('{"suggested_name":"A"}', input_tokens=100, output_tokens=50)
    resp2 = _mock_anthropic_response('{"suggested_name":"B"}', input_tokens=200, output_tokens=80)

    client._track_response(resp1, "test1")
    client._track_response(resp2, "test2")

    tokens = client.total_tokens
    assert tokens["input"] == 300
    assert tokens["output"] == 130
    assert tokens["estimated_cost"] > 0


def test_last_response_meta_updated():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config())

    response = _mock_anthropic_response(
        '{"suggested_name":"X"}',
        model="claude-haiku-4-5-20251001",
        stop_reason="end_turn",
    )
    client._track_response(response, "test")

    meta = client.last_response_meta
    assert meta["model"] == "claude-haiku-4-5-20251001"
    assert meta["stop_reason"] == "end_turn"
    assert meta["input_tokens"] == 100
    assert meta["output_tokens"] == 50


# ── Cost estimation ──────────────────────────────────────────────────────


def test_cost_estimation_haiku():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_model_name="claude-haiku-4-5-20251001"))
    client._total_input_tokens = 1_000_000
    client._total_output_tokens = 1_000_000
    cost = client._estimate_cost()
    assert cost == round(0.80 + 4.0, 4)


def test_cost_estimation_sonnet():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_model_name="claude-sonnet-4-20250514"))
    client._total_input_tokens = 1_000_000
    client._total_output_tokens = 1_000_000
    cost = client._estimate_cost()
    assert cost == round(3.0 + 15.0, 4)


def test_cost_estimation_opus():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config(ai_model_name="claude-opus-4-20250514"))
    client._total_input_tokens = 1_000_000
    client._total_output_tokens = 1_000_000
    cost = client._estimate_cost()
    assert cost == round(15.0 + 75.0, 4)


# ── rewrite_product ──────────────────────────────────────────────────────


def test_rewrite_product_returns_suggestion():
    mock_client = MagicMock()
    response = _mock_anthropic_response(json.dumps({
        "suggested_name": "Nike Air Max 270 - Kadin Spor Ayakkabi",
        "suggested_description": "<p>Yeni optimized aciklama</p>",
        "suggested_description_en": "Optimized English description",
        "suggested_meta_title": "Nike Air Max 270 | Kadin Ayakkabi",
        "suggested_meta_description": "En konforlu spor ayakkabi. Hemen satin alin!",
    }))
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        suggestion = client.rewrite_product(_build_product(), _build_score())

    assert isinstance(suggestion, SeoSuggestion)
    assert suggestion.suggested_name == "Nike Air Max 270 - Kadin Spor Ayakkabi"
    assert suggestion.product_id == "p1"
    assert suggestion.status == "pending"
    mock_client.messages.create.assert_called_once()


def test_rewrite_product_with_thinking_mode():
    mock_client = MagicMock()
    response = _mock_anthropic_response(
        json.dumps({
            "suggested_name": "SEO Optimized Name",
            "suggested_description": "New desc",
            "suggested_meta_title": "Meta",
            "suggested_meta_description": "Meta desc",
        }),
        thinking_text="Analyzing the product for SEO improvements...",
    )
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=True))
        suggestion = client.rewrite_product(_build_product(), _build_score())

    assert suggestion.thinking_text != ""
    assert "Analyzing" in suggestion.thinking_text

    # Verify thinking params were sent
    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs.kwargs.get("temperature") == 1 or call_kwargs[1].get("temperature") == 1


def test_rewrite_product_tracks_tokens():
    mock_client = MagicMock()
    response = _mock_anthropic_response(
        json.dumps({"suggested_name": "Test"}),
        input_tokens=500,
        output_tokens=200,
    )
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        client.rewrite_product(_build_product(), _build_score())

    assert client.total_tokens["input"] == 500
    assert client.total_tokens["output"] == 200


# ── rewrite_field ────────────────────────────────────────────────────────


def test_rewrite_field_name():
    mock_client = MagicMock()
    response = _mock_anthropic_response(json.dumps({
        "suggested_name": "Optimized Product Name",
    }))
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        result = client.rewrite_field("name", _build_product(), _build_score())

    assert result == "Optimized Product Name"


def test_rewrite_field_meta_title():
    mock_client = MagicMock()
    response = _mock_anthropic_response(json.dumps({
        "suggested_meta_title": "Nike Air Max | Ayakkabi",
    }))
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        result = client.rewrite_field("meta_title", _build_product(), _build_score())

    assert result == "Nike Air Max | Ayakkabi"


def test_rewrite_field_with_thinking_returns_tuple():
    mock_client = MagicMock()
    response = _mock_anthropic_response(
        json.dumps({"suggested_name": "Better Name"}),
        thinking_text="Analyzing the title length and keywords...",
    )
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=True))
        result = client.rewrite_field("name", _build_product(), _build_score())

    assert isinstance(result, tuple)
    value, thinking = result
    assert value == "Better Name"
    assert "Analyzing" in thinking


# ── rewrite_product_for_geo ──────────────────────────────────────────────


def test_rewrite_product_for_geo():
    mock_client = MagicMock()
    response = _mock_anthropic_response(json.dumps({
        "suggested_name": "GEO Optimized Name",
        "suggested_description": "Encyclopedic description for AI bots",
        "suggested_meta_title": "GEO Meta Title",
        "suggested_meta_description": "AI-optimized meta description",
    }))
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        suggestion = client.rewrite_product_for_geo(_build_product(), _build_score())

    assert isinstance(suggestion, SeoSuggestion)
    assert suggestion.suggested_name == "GEO Optimized Name"


# ── translate_description_to_en ──────────────────────────────────────────


def test_translate_description_to_en():
    mock_client = MagicMock()
    response = _mock_anthropic_response(json.dumps({
        "suggested_description_en": "Nike Air Max 270 Women's Sports Shoe - comfortable and stylish",
    }))
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        result = client.translate_description_to_en(_build_product())

    assert "Nike Air Max" in result
    assert isinstance(result, str)


def test_translate_description_to_en_with_thinking():
    mock_client = MagicMock()
    response = _mock_anthropic_response(
        json.dumps({
            "suggested_description_en": "Translated description here",
        }),
        thinking_text="Translating the Turkish description...",
    )
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=True))
        result = client.translate_description_to_en(_build_product())

    assert isinstance(result, tuple)
    value, thinking = result
    assert value == "Translated description here"
    assert "Translating" in thinking


def test_translate_uses_anthropic_sdk_not_openai():
    """Regression test: translate_description_to_en must use
    self._client.messages.create(), not self._client.chat.completions.create()."""
    mock_client = MagicMock()
    response = _mock_anthropic_response(json.dumps({
        "suggested_description_en": "English text",
    }))
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        client.translate_description_to_en(_build_product())

    # messages.create should be called (Anthropic SDK)
    mock_client.messages.create.assert_called_once()
    # chat.completions.create should NOT be called (OpenAI SDK)
    assert not hasattr(mock_client, "chat") or not mock_client.chat.completions.create.called


# ── cancel_active_request ────────────────────────────────────────────────


def test_cancel_active_request_no_stream():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config())
    assert client.cancel_active_request() is False


def test_cancel_active_request_with_stream():
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config())

    mock_stream = MagicMock()
    client._active_stream = mock_stream

    assert client.cancel_active_request() is True
    mock_stream.close.assert_called_once()
    assert client._active_stream is None


def test_cancel_active_request_thread_safety():
    """Verify cancel uses a lock for thread safety."""
    with patch("anthropic.Anthropic"):
        client = AnthropicAIClient(_build_config())

    assert isinstance(client._cancel_lock, type(threading.Lock()))


# ── streaming ────────────────────────────────────────────────────────────


def test_stream_message_yields_text_events():
    mock_client = MagicMock()

    # Create mock events
    text_delta_event = MagicMock()
    text_delta_event.type = "content_block_delta"
    text_delta_event.delta.type = "text_delta"
    text_delta_event.delta.text = "Hello "

    text_delta_event2 = MagicMock()
    text_delta_event2.type = "content_block_delta"
    text_delta_event2.delta.type = "text_delta"
    text_delta_event2.delta.text = "world!"

    stop_event = MagicMock()
    stop_event.type = "message_stop"

    # Build the context manager for stream
    mock_stream = MagicMock()
    mock_stream.__iter__ = MagicMock(
        return_value=iter([text_delta_event, text_delta_event2, stop_event])
    )
    final_msg = _mock_anthropic_response("Hello world!")
    mock_stream.get_final_message.return_value = final_msg

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)

    mock_client.messages.stream.return_value = mock_stream_ctx

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        events = list(client.stream_message("System", "User msg"))

    text_events = [(t, c) for t, c in events if t == "text"]
    assert len(text_events) == 2
    assert text_events[0][1] == "Hello "
    assert text_events[1][1] == "world!"

    done_events = [(t, c) for t, c in events if t == "done"]
    assert len(done_events) == 1


def test_stream_message_with_thinking_events():
    mock_client = MagicMock()

    # Thinking block start
    thinking_start_event = MagicMock()
    thinking_start_event.type = "content_block_start"
    thinking_start_event.content_block.type = "thinking"

    # Thinking delta
    thinking_delta = MagicMock()
    thinking_delta.type = "content_block_delta"
    thinking_delta.delta.type = "thinking_delta"
    thinking_delta.delta.thinking = "Let me analyze..."

    # Text delta
    text_delta = MagicMock()
    text_delta.type = "content_block_delta"
    text_delta.delta.type = "text_delta"
    text_delta.delta.text = "Here is the result."

    stop_event = MagicMock()
    stop_event.type = "message_stop"

    mock_stream = MagicMock()
    mock_stream.__iter__ = MagicMock(
        return_value=iter([thinking_start_event, thinking_delta, text_delta, stop_event])
    )
    final_msg = _mock_anthropic_response("Here is the result.", thinking_text="Let me analyze...")
    mock_stream.get_final_message.return_value = final_msg

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)

    mock_client.messages.stream.return_value = mock_stream_ctx

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config(ai_thinking_mode=True))
        events = list(client.stream_message("System", "User"))

    thinking_events = [(t, c) for t, c in events if t in ("thinking", "thinking_start")]
    assert len(thinking_events) >= 1

    text_events = [(t, c) for t, c in events if t == "text"]
    assert len(text_events) == 1


# ── Request building for Anthropic ───────────────────────────────────────


def test_build_product_rewrite_request_for_anthropic():
    config = _build_config()
    product = _build_product()
    score = _build_score()

    request = build_product_rewrite_request(config, "anthropic", product, score)
    assert "system_prompt" in request
    assert "user_prompt" in request
    assert "max_tokens" in request
    # Should not have /no_think (that's for local providers)
    assert "/no_think" not in request["system_prompt"]


def test_build_field_rewrite_request_no_no_think_for_anthropic():
    config = _build_config(ai_thinking_mode=False)
    request = build_field_rewrite_request(config, "anthropic", "name", _build_product())
    assert "/no_think" not in request["system_prompt"]


def test_build_geo_rewrite_request_for_anthropic():
    config = _build_config()
    request = build_geo_rewrite_request(config, "anthropic", _build_product(), _build_score())
    assert "system_prompt" in request
    assert "user_prompt" in request


def test_build_en_translation_request_for_anthropic():
    config = _build_config()
    request = build_en_translation_request(config, "anthropic", _build_product())
    assert "system_prompt" in request
    assert "user_prompt" in request
    # No /no_think for cloud providers
    assert "/no_think" not in request["system_prompt"]


# ── Batch rewrite ────────────────────────────────────────────────────────


def test_rewrite_products_batch():
    mock_client = MagicMock()

    products = [
        (_build_product(id="p1", name="Product 1"), _build_score(product_id="p1")),
        (_build_product(id="p2", name="Product 2"), _build_score(product_id="p2")),
    ]

    def make_response(call_args):
        return _mock_anthropic_response(json.dumps({
            "suggested_name": "Optimized",
            "suggested_description": "Desc",
            "suggested_meta_title": "Meta",
            "suggested_meta_description": "Meta desc",
        }))

    mock_client.messages.create.side_effect = [
        make_response(None),
        make_response(None),
    ]

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        suggestions = client.rewrite_products_batch(products)

    assert len(suggestions) == 2
    assert all(isinstance(s, SeoSuggestion) for s in suggestions)


def test_rewrite_products_batch_handles_individual_failure():
    mock_client = MagicMock()

    products = [
        (_build_product(id="p1", name="Product 1"), _build_score(product_id="p1")),
        (_build_product(id="p2", name="Product 2"), _build_score(product_id="p2")),
    ]

    mock_client.messages.create.side_effect = [
        Exception("API error"),
        _mock_anthropic_response(json.dumps({
            "suggested_name": "OK",
            "suggested_description": "OK",
            "suggested_meta_title": "OK",
            "suggested_meta_description": "OK",
        })),
    ]

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        suggestions = client.rewrite_products_batch(products)

    # First fails, second succeeds
    assert len(suggestions) == 1


# ── Agent orchestrator integration ───────────────────────────────────────


def test_orchestrator_anthropic_header():
    """AgentOrchestrator should use x-api-key for Anthropic, not Bearer."""
    from core.agent.orchestrator import _build_headers

    config = _build_config()
    headers = _build_headers(config)
    assert "x-api-key" in headers
    assert headers["x-api-key"] == "sk-ant-test-key-123"
    assert "Authorization" not in headers


def test_orchestrator_anthropic_base_url():
    from core.agent.orchestrator import _resolve_base_url

    config = _build_config(ai_base_url="")
    url = _resolve_base_url(config)
    assert url == "https://api.anthropic.com/v1"


def test_orchestrator_anthropic_default_model():
    from core.agent.orchestrator import _resolve_model

    config = _build_config(ai_model_name="")
    model = _resolve_model(config)
    assert model == DEFAULT_MODELS["anthropic"]


# ── Edge cases ───────────────────────────────────────────────────────────


def test_anthropic_client_handles_empty_response():
    mock_client = MagicMock()
    response = _mock_anthropic_response("")
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        with pytest.raises(ValueError):
            client.rewrite_product(_build_product(), _build_score())


def test_anthropic_client_handles_non_json_response():
    mock_client = MagicMock()
    response = _mock_anthropic_response("This is not JSON at all, just text.")
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        with pytest.raises(ValueError, match="JSON"):
            client.rewrite_product(_build_product(), _build_score())


def test_anthropic_client_handles_markdown_fenced_json():
    mock_client = MagicMock()
    response = _mock_anthropic_response(
        '```json\n{"suggested_name": "Fenced Result"}\n```'
    )
    mock_client.messages.create.return_value = response

    with patch("anthropic.Anthropic", return_value=mock_client):
        client = AnthropicAIClient(_build_config())
        suggestion = client.rewrite_product(_build_product(), _build_score())

    assert suggestion.suggested_name == "Fenced Result"


def test_merge_thinking_text_combines_parts():
    result = _merge_thinking_text("Part 1", "", "Part 2", "")
    assert result == "Part 1\n\nPart 2"


def test_merge_thinking_text_empty():
    result = _merge_thinking_text("", "", "")
    assert result == ""
