"""Tests for core/agent_orchestrator.py — AgentOrchestrator."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from core.agent.orchestrator import (
    AgentOrchestrator,
    supports_tool_calling,
    _resolve_base_url,
    _resolve_model,
    _extract_thinking,
    _remove_thinking,
)
from core.agent.tools import AgentTool, AgentToolkit
from core.models import AppConfig, AgentEvent, AgentResult


def _make_config(**overrides) -> AppConfig:
    defaults = {
        "ikas_store_name": "test",
        "ikas_client_id": "cid",
        "ikas_client_secret": "csec",
        "ai_provider": "ollama",
        "ai_model_name": "llama3.2",
        "ai_base_url": "http://localhost:11434/v1",
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


# ── supports_tool_calling ────────────────────────────────────────────────


def test_supports_tool_calling_ollama():
    assert supports_tool_calling(_make_config(ai_provider="ollama"))


def test_supports_tool_calling_openai():
    assert supports_tool_calling(_make_config(ai_provider="openai"))


def test_supports_tool_calling_anthropic():
    assert supports_tool_calling(_make_config(ai_provider="anthropic"))


def test_supports_tool_calling_lm_studio():
    assert supports_tool_calling(_make_config(ai_provider="lm-studio"))


def test_supports_tool_calling_gemini():
    assert supports_tool_calling(_make_config(ai_provider="gemini"))


def test_supports_tool_calling_openrouter():
    assert supports_tool_calling(_make_config(ai_provider="openrouter"))


def test_supports_tool_calling_custom():
    assert supports_tool_calling(_make_config(ai_provider="custom"))


def test_supports_tool_calling_none():
    assert not supports_tool_calling(_make_config(ai_provider="none"))


# ── URL/model resolution ────────────────────────────────────────────────


def test_resolve_base_url_from_config():
    config = _make_config(ai_base_url="http://myserver:8080")
    assert _resolve_base_url(config) == "http://myserver:8080/v1"


def test_resolve_base_url_already_has_v1():
    config = _make_config(ai_base_url="http://myserver:8080/v1")
    assert _resolve_base_url(config) == "http://myserver:8080/v1"


def test_resolve_base_url_default_ollama():
    config = _make_config(ai_base_url="", ai_provider="ollama")
    assert _resolve_base_url(config) == "http://localhost:11434/v1"


def test_resolve_model_from_config():
    config = _make_config(ai_model_name="qwen3")
    assert _resolve_model(config) == "qwen3"


def test_resolve_model_default():
    config = _make_config(ai_model_name="", ai_provider="openai")
    assert _resolve_model(config) == "gpt-4o-mini"


# ── Thinking extraction ─────────────────────────────────────────────────


def test_extract_thinking():
    text = "Before <think>my thoughts</think> After"
    assert _extract_thinking(text) == "my thoughts"


def test_extract_thinking_empty():
    assert _extract_thinking("no thinking here") == ""


def test_remove_thinking():
    text = "Before <think>my thoughts</think> After"
    assert _remove_thinking(text) == "Before  After"


# ── AgentOrchestrator._build_initial_messages ────────────────────────────


def test_build_initial_messages_without_context():
    config = _make_config()
    toolkit = AgentToolkit()
    orch = AgentOrchestrator(config, toolkit, "System prompt here")

    messages = orch._build_initial_messages("Hello", None)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "System prompt here"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hello"


def test_build_initial_messages_with_context():
    config = _make_config()
    toolkit = AgentToolkit()
    orch = AgentOrchestrator(config, toolkit, "System")

    messages = orch._build_initial_messages("Hi", {"product_id": "p1"})
    assert len(messages) == 3
    assert messages[1]["role"] == "system"
    assert "product_id" in messages[1]["content"]


# ── AgentOrchestrator.run ────────────────────────────────────────────────


def _mock_response(content: str, tool_calls=None, finish_reason="stop"):
    """Build a mock httpx response JSON."""
    message = {"content": content, "role": "assistant"}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "model": "test-model",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


@pytest.mark.anyio
async def test_orchestrator_run_simple_response():
    """Agent returns a direct response without tool calls."""
    config = _make_config()
    toolkit = AgentToolkit()
    orch = AgentOrchestrator(config, toolkit, "You are helpful.", max_iterations=3)

    mock_resp = _mock_response("Here is my answer.")

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_http_resp = MagicMock()
        mock_http_resp.json.return_value = mock_resp
        mock_http_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_http_resp)

        MockClient.return_value = mock_client

        result = await orch.run("What is SEO?")

    assert result.content == "Here is my answer."
    assert result.iterations == 1
    assert len(result.tool_calls_made) == 0


@pytest.mark.anyio
async def test_orchestrator_run_with_tool_calls():
    """Agent makes a tool call, gets result, then responds."""
    call_log = []

    async def mock_handler(args):
        call_log.append(args)
        return json.dumps({"score": 42})

    tool = AgentTool(
        name="score_tool",
        description="Score something",
        parameters={"type": "object", "properties": {}},
        handler=mock_handler,
    )
    config = _make_config()
    toolkit = AgentToolkit([tool])
    orch = AgentOrchestrator(config, toolkit, "Use tools.", max_iterations=5)

    # First call: model requests tool call
    tool_call_resp = _mock_response(
        "Let me check the score.",
        tool_calls=[{
            "id": "call_1",
            "type": "function",
            "function": {"name": "score_tool", "arguments": "{}"},
        }],
        finish_reason="tool_calls",
    )
    # Second call: model gives final answer
    final_resp = _mock_response("The score is 42.")

    call_count = 0

    async def mock_post(url, json=None, headers=None):
        nonlocal call_count
        call_count += 1
        mock_http_resp = MagicMock()
        mock_http_resp.raise_for_status = MagicMock()
        if call_count == 1:
            mock_http_resp.json.return_value = tool_call_resp
        else:
            mock_http_resp.json.return_value = final_resp
        return mock_http_resp

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        MockClient.return_value = mock_client

        result = await orch.run("Score this product")

    assert result.content == "The score is 42."
    assert result.iterations == 2
    assert len(result.tool_calls_made) == 1
    assert result.tool_calls_made[0].name == "score_tool"
    assert len(call_log) == 1


@pytest.mark.anyio
async def test_orchestrator_stream_yields_events():
    """Stream should yield tool_call, tool_result, and completed events."""
    async def mock_handler(args):
        return json.dumps({"ok": True})

    tool = AgentTool(name="my_tool", description="My tool", handler=mock_handler)
    config = _make_config()
    toolkit = AgentToolkit([tool])
    orch = AgentOrchestrator(config, toolkit, "System", max_iterations=3)

    tool_call_resp = _mock_response(
        "",
        tool_calls=[{
            "id": "c1",
            "type": "function",
            "function": {"name": "my_tool", "arguments": "{}"},
        }],
        finish_reason="tool_calls",
    )
    final_resp = _mock_response("Done!")

    call_count = 0

    async def mock_post(url, json=None, headers=None):
        nonlocal call_count
        call_count += 1
        mock_http_resp = MagicMock()
        mock_http_resp.raise_for_status = MagicMock()
        mock_http_resp.json.return_value = tool_call_resp if call_count == 1 else final_resp
        return mock_http_resp

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        MockClient.return_value = mock_client

        events = []
        async for event in orch.stream("Do it"):
            events.append(event)

    event_types = [e.type for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "completed" in event_types

    completed = [e for e in events if e.type == "completed"][0]
    assert completed.content == "Done!"


@pytest.mark.anyio
async def test_orchestrator_max_iterations():
    """Agent should stop after max_iterations even if model keeps calling tools."""
    async def mock_handler(args):
        return json.dumps({"ok": True})

    tool = AgentTool(name="loop_tool", description="Loop", handler=mock_handler)
    config = _make_config()
    toolkit = AgentToolkit([tool])
    orch = AgentOrchestrator(config, toolkit, "System", max_iterations=2)

    # Always return tool call
    tool_call_resp = _mock_response(
        "calling tool",
        tool_calls=[{
            "id": "c1",
            "type": "function",
            "function": {"name": "loop_tool", "arguments": "{}"},
        }],
        finish_reason="tool_calls",
    )

    async def mock_post(url, json=None, headers=None):
        mock_http_resp = MagicMock()
        mock_http_resp.raise_for_status = MagicMock()
        mock_http_resp.json.return_value = tool_call_resp
        return mock_http_resp

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        MockClient.return_value = mock_client

        result = await orch.run("Loop forever")

    assert result.meta.get("max_iterations_reached") is True


@pytest.mark.anyio
async def test_orchestrator_thinking_extraction():
    """Thinking blocks should be extracted and removed from content."""
    config = _make_config()
    toolkit = AgentToolkit()
    orch = AgentOrchestrator(config, toolkit, "System", max_iterations=1)

    resp = _mock_response("<think>I need to analyze this</think>Here is the answer.")

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_http_resp = MagicMock()
        mock_http_resp.json.return_value = resp
        mock_http_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_http_resp)
        MockClient.return_value = mock_client

        result = await orch.run("Analyze this")

    assert result.thinking == "I need to analyze this"
    assert result.content == "Here is the answer."
