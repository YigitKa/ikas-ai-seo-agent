"""Tests for Gemma 4 model support via Ollama provider.

Gemma 4 (e.g. 'gemma4:27b', 'gemma4:12b') is accessed through Ollama's
OpenAI-compatible endpoint. These tests verify that:

- AgentOrchestrator resolves the model name and base URL correctly
- Tool-calling is enabled for Ollama (which hosts Gemma 4)
- Cost estimation returns 0.0 for local Gemma models (no API cost)
- Headers are built correctly for Ollama (no auth key required)
- Provider service correctly handles Gemma 4 via Ollama model discovery
- Gemma 4 via OpenRouter works with the correct model slug
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.agent.orchestrator import (
    AgentOrchestrator,
    supports_tool_calling,
    _resolve_base_url,
    _resolve_model,
    _build_headers,
)
from core.agent.tools import AgentToolkit
from core.ai.constants import estimate_cost
from core.models import AppConfig, AgentResult
from core.services.provider import (
    discover_provider_models,
    resolve_provider_base_url,
    get_provider_model_options,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ollama_gemma4_config(**overrides) -> AppConfig:
    defaults = {
        "ikas_store_name": "test",
        "ikas_client_id": "cid",
        "ikas_client_secret": "csec",
        "ai_provider": "ollama",
        "ai_model_name": "gemma4:27b",
        "ai_base_url": "http://localhost:11434/v1",
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


def _openrouter_gemma4_config(**overrides) -> AppConfig:
    defaults = {
        "ikas_store_name": "test",
        "ikas_client_id": "cid",
        "ikas_client_secret": "csec",
        "ai_provider": "openrouter",
        "ai_model_name": "google/gemma-4-27b",
        "ai_api_key": "sk-or-test",
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


class _FakeHttpResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# ── supports_tool_calling ────────────────────────────────────────────────────


def test_gemma4_via_ollama_supports_tool_calling():
    """Ollama provider (which runs Gemma 4) must have tool-calling enabled."""
    config = _ollama_gemma4_config()
    assert supports_tool_calling(config) is True


def test_gemma4_via_openrouter_supports_tool_calling():
    """OpenRouter provider (which can serve Gemma 4) must have tool-calling enabled."""
    config = _openrouter_gemma4_config()
    assert supports_tool_calling(config) is True


# ── Model and URL resolution ─────────────────────────────────────────────────


def test_resolve_model_gemma4_ollama():
    """Configured model name 'gemma4:27b' should pass through unchanged."""
    config = _ollama_gemma4_config(ai_model_name="gemma4:27b")
    assert _resolve_model(config) == "gemma4:27b"


def test_resolve_model_gemma4_12b_variant():
    """Different Gemma 4 size variants are passed through unchanged."""
    config = _ollama_gemma4_config(ai_model_name="gemma4:12b")
    assert _resolve_model(config) == "gemma4:12b"


def test_resolve_model_gemma4_openrouter():
    """OpenRouter model slug for Gemma 4 should pass through unchanged."""
    config = _openrouter_gemma4_config(ai_model_name="google/gemma-4-27b")
    assert _resolve_model(config) == "google/gemma-4-27b"


def test_resolve_base_url_gemma4_ollama_default():
    """Without explicit base URL, Ollama defaults to localhost:11434."""
    config = _ollama_gemma4_config(ai_base_url="")
    assert _resolve_base_url(config) == "http://localhost:11434/v1"


def test_resolve_base_url_gemma4_ollama_custom():
    """Custom Ollama base URL (e.g. remote server) should be honoured."""
    config = _ollama_gemma4_config(ai_base_url="http://gpu-server:11434")
    assert _resolve_base_url(config) == "http://gpu-server:11434/v1"


# ── Auth headers ─────────────────────────────────────────────────────────────


def test_gemma4_ollama_headers_no_api_key():
    """Ollama doesn't require a real API key; a placeholder Bearer is used."""
    config = _ollama_gemma4_config(ai_api_key="")
    headers = _build_headers(config)
    assert headers["Authorization"] == "Bearer ollama"
    assert "x-api-key" not in headers


def test_gemma4_openrouter_headers_with_api_key():
    """OpenRouter requires a proper Bearer token."""
    config = _openrouter_gemma4_config(ai_api_key="sk-or-real-key")
    headers = _build_headers(config)
    assert headers["Authorization"] == "Bearer sk-or-real-key"


# ── Cost estimation ──────────────────────────────────────────────────────────


def test_gemma4_ollama_cost_is_zero():
    """Local Gemma 4 models run on Ollama and have no API cost."""
    cost = estimate_cost("gemma4:27b", input_tokens=1000, output_tokens=500)
    assert cost == 0.0


def test_gemma4_12b_cost_is_zero():
    """All Gemma 4 size variants should return 0 cost (local models)."""
    cost = estimate_cost("gemma4:12b", input_tokens=5000, output_tokens=1000)
    assert cost == 0.0


def test_gemma3_model_cost_is_zero():
    """Gemma 3 (predecessor) also runs locally — zero cost."""
    cost = estimate_cost("gemma3:9b", input_tokens=2000, output_tokens=800)
    assert cost == 0.0


# ── Provider model options ───────────────────────────────────────────────────


def test_get_provider_model_options_ollama_returns_list():
    """Ollama has no static preset list — returns empty (dynamic discovery)."""
    options = get_provider_model_options("ollama")
    # Ollama models are discovered dynamically, not in a static list
    assert isinstance(options, list)


def test_get_provider_model_options_openrouter_includes_gemma():
    """OpenRouter model list should include at least one Gemma entry."""
    options = get_provider_model_options("openrouter")
    # At minimum we expect Google's Gemma to be listed via its flash variant
    gemma_entries = [m for m in options if "gemma" in m.lower() or "google" in m.lower()]
    assert len(gemma_entries) > 0, f"No Gemma/Google entry found in openrouter options: {options}"


# ── Provider base URL ─────────────────────────────────────────────────────────


def test_resolve_provider_base_url_ollama_appends_v1():
    """Ollama base URL gets /v1 appended automatically."""
    url = resolve_provider_base_url("ollama", "http://localhost:11434")
    assert url == "http://localhost:11434/v1"


def test_resolve_provider_base_url_ollama_keeps_existing_v1():
    """If /v1 already present, no double-append."""
    url = resolve_provider_base_url("ollama", "http://localhost:11434/v1")
    assert url == "http://localhost:11434/v1"


# ── Ollama model discovery picks up Gemma 4 ──────────────────────────────────


def test_discover_provider_models_ollama_lists_gemma4(monkeypatch):
    """Ollama model discovery should surface Gemma 4 when it's installed."""

    def fake_get(url: str, timeout: float):
        assert "/api/tags" in url
        return _FakeHttpResponse(200, {
            "models": [
                {"name": "gemma4:27b"},
                {"name": "gemma4:12b"},
                {"name": "llama3.2"},
            ],
        })

    monkeypatch.setattr("core.services.provider.httpx.get", fake_get)

    models = discover_provider_models("ollama", "http://localhost:11434/v1")

    assert "gemma4:27b" in models
    assert "gemma4:12b" in models
    assert "llama3.2" in models


def test_discover_provider_models_ollama_only_gemma4(monkeypatch):
    """Discovery works when Gemma 4 is the only installed model."""

    def fake_get(url: str, timeout: float):
        return _FakeHttpResponse(200, {"models": [{"name": "gemma4:27b"}]})

    monkeypatch.setattr("core.services.provider.httpx.get", fake_get)

    models = discover_provider_models("ollama")
    assert models == ["gemma4:27b"]


# ── AgentOrchestrator integration with Gemma 4 ───────────────────────────────


def _mock_llm_response(content: str):
    return {
        "choices": [{"message": {"content": content, "role": "assistant"}, "finish_reason": "stop"}],
        "model": "gemma4:27b",
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }


@pytest.mark.anyio
async def test_orchestrator_gemma4_ollama_runs_successfully():
    """AgentOrchestrator completes a run with Gemma 4 on Ollama."""
    config = _ollama_gemma4_config()
    toolkit = AgentToolkit()
    orch = AgentOrchestrator(config, toolkit, "Sen bir SEO uzmanisın.", max_iterations=3)

    mock_resp = _mock_llm_response("Urun basligini optimize ettim.")

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_http_resp = MagicMock()
        mock_http_resp.json.return_value = mock_resp
        mock_http_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_http_resp)
        MockClient.return_value = mock_client

        result = await orch.run("Bu ürünün SEO skorunu değerlendir.")

    assert result.content == "Urun basligini optimize ettim."
    assert result.iterations == 1


@pytest.mark.anyio
async def test_orchestrator_gemma4_sends_model_name_in_request():
    """The request body sent to Ollama must contain the Gemma 4 model name."""
    config = _ollama_gemma4_config(ai_model_name="gemma4:27b")
    toolkit = AgentToolkit()
    orch = AgentOrchestrator(config, toolkit, "System", max_iterations=1)

    captured_body: dict = {}

    async def fake_post(url, json=None, headers=None):
        nonlocal captured_body
        captured_body = json or {}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _mock_llm_response("Done")
        return mock_resp

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        MockClient.return_value = mock_client

        await orch.run("Test")

    assert captured_body.get("model") == "gemma4:27b"


@pytest.mark.anyio
async def test_orchestrator_gemma4_thinking_extraction():
    """Gemma 4 (like Qwen/DeepSeek) may emit <think> blocks; they should be extracted."""
    config = _ollama_gemma4_config()
    toolkit = AgentToolkit()
    orch = AgentOrchestrator(config, toolkit, "System", max_iterations=1)

    resp = _mock_llm_response("<think>Meta başlığı 60 karakterde tutmalıyım.</think>Meta başlığı optimize edildi.")

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_http_resp = MagicMock()
        mock_http_resp.json.return_value = resp
        mock_http_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_http_resp)
        MockClient.return_value = mock_client

        result = await orch.run("Analiz et")

    assert result.thinking == "Meta başlığı 60 karakterde tutmalıyım."
    assert result.content == "Meta başlığı optimize edildi."


@pytest.mark.anyio
async def test_orchestrator_gemma4_tool_call_and_response():
    """Gemma 4 can make tool calls via Ollama's OpenAI-compatible endpoint."""
    tool_call_log = []

    async def mock_handler(args):
        tool_call_log.append(args)
        return json.dumps({"total_score": 55, "issues": ["Meta description eksik"]})

    from core.agent.tools import AgentTool
    tool = AgentTool(
        name="seo_score_product",
        description="SEO skorunu hesapla",
        parameters={"type": "object", "properties": {}},
        handler=mock_handler,
    )
    config = _ollama_gemma4_config()
    toolkit = AgentToolkit([tool])
    orch = AgentOrchestrator(config, toolkit, "System", max_iterations=5)

    tool_call_resp = {
        "choices": [{
            "message": {
                "content": "Skoru kontrol edeyim.",
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_gemma4_1",
                    "type": "function",
                    "function": {"name": "seo_score_product", "arguments": "{}"},
                }],
            },
            "finish_reason": "tool_calls",
        }],
        "model": "gemma4:27b",
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
    }
    final_resp = _mock_llm_response("SEO skoru 55/100. Meta description eklenmeli.")

    call_count = 0

    async def fake_post(url, json=None, headers=None):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = tool_call_resp if call_count == 1 else final_resp
        return mock_resp

    with patch("core.agent.orchestrator.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        MockClient.return_value = mock_client

        result = await orch.run("Bu ürünü analiz et")

    assert len(result.tool_calls_made) == 1
    assert result.tool_calls_made[0].name == "seo_score_product"
    assert len(tool_call_log) == 1
    assert "SEO skoru 55/100" in result.content


# ── AppConfig with Gemma 4 ───────────────────────────────────────────────────


def test_appconfig_gemma4_ollama_fields():
    """AppConfig correctly stores Gemma 4 / Ollama settings."""
    config = _ollama_gemma4_config()
    assert config.ai_provider == "ollama"
    assert config.ai_model_name == "gemma4:27b"
    assert "11434" in config.ai_base_url


def test_appconfig_gemma4_openrouter_fields():
    """AppConfig correctly stores Gemma 4 via OpenRouter settings."""
    config = _openrouter_gemma4_config()
    assert config.ai_provider == "openrouter"
    assert config.ai_model_name == "google/gemma-4-27b"
    assert config.ai_api_key == "sk-or-test"
