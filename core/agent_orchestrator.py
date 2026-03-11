"""Generic agent orchestrator with tool-calling loop.

Provides ``AgentOrchestrator`` — a provider-agnostic agent loop that
sends messages to an OpenAI-compatible chat-completion endpoint,
detects tool calls, executes them via an ``AgentToolkit``, appends the
results, and iterates until the model stops or ``max_iterations`` is
reached.

Both a blocking ``run()`` and an async-streaming ``stream()`` interface
are provided.
"""

from __future__ import annotations

import json
import logging
import re
import time
import threading
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.agent_tools import AgentToolkit
from core.models import AgentEvent, AgentResult, AgentToolCall, AppConfig

logger = logging.getLogger(__name__)

# Defaults
DEFAULT_MAX_ITERATIONS = 10
TOOL_CALLING_PROVIDERS = frozenset({
    "anthropic", "openai", "gemini", "openrouter", "ollama", "lm-studio", "custom",
})

_PROVIDER_BASE_URLS: dict[str, str] = {
    "ollama": "http://localhost:11434/v1",
    "lm-studio": "http://localhost:1234/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "ollama": "llama3.2",
    "lm-studio": "default",
    "openai": "gpt-4o-mini",
    "openrouter": "openai/gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "anthropic": "claude-haiku-4-5-20251001",
}


def supports_tool_calling(config: AppConfig) -> bool:
    """Return True if the configured provider supports tool calling."""
    return config.ai_provider in TOOL_CALLING_PROVIDERS


# ── Helpers ──────────────────────────────────────────────────────────────


def _resolve_base_url(config: AppConfig) -> str:
    if config.ai_base_url:
        url = config.ai_base_url.rstrip("/")
        if not url.endswith("/v1") and "/v1" not in url:
            url += "/v1"
        return url
    return _PROVIDER_BASE_URLS.get(config.ai_provider, "http://localhost:11434/v1")


def _resolve_model(config: AppConfig) -> str:
    return config.ai_model_name or _PROVIDER_DEFAULT_MODELS.get(config.ai_provider, "llama3.2")


def _build_headers(config: AppConfig) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = config.ai_api_key
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif config.ai_provider in ("ollama", "lm-studio"):
        headers["Authorization"] = "Bearer ollama"
    return headers


def _build_timeout(config: AppConfig) -> httpx.Timeout:
    if config.ai_provider in ("ollama", "lm-studio"):
        return httpx.Timeout(600.0, connect=10.0)
    return httpx.Timeout(120.0, connect=10.0)


def _extract_thinking(text: str) -> str:
    match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    open_match = re.search(r"<think>(.*)$", text, re.DOTALL)
    return open_match.group(1).strip() if open_match else ""


def _remove_thinking(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "<think>" in cleaned:
        cleaned = cleaned.split("<think>", 1)[0]
    return cleaned.strip()


# ── AgentOrchestrator ────────────────────────────────────────────────────


class AgentOrchestrator:
    """Provider-agnostic agent loop with tool calling.

    Parameters
    ----------
    config:
        Application config with AI provider settings.
    toolkit:
        The set of tools exposed to the LLM.
    system_prompt:
        The system prompt that instructs the agent.
    max_iterations:
        Maximum number of LLM call rounds (including tool-call rounds).
    """

    def __init__(
        self,
        config: AppConfig,
        toolkit: AgentToolkit,
        system_prompt: str,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._config = config
        self._toolkit = toolkit
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations
        self._cancel_lock = threading.Lock()
        self._active_client: httpx.AsyncClient | None = None

    # ── Public API ───────────────────────────────────────────────────

    async def run(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Execute the agent loop to completion and return the final result."""
        result = AgentResult(content="")
        async for event in self.stream(user_message, context):
            if event.type == "completed":
                result.content = event.content
                result.meta = event.meta
            elif event.type == "tool_call":
                result.tool_calls_made.append(
                    AgentToolCall(name=event.tool_name, args=event.tool_args)
                )
            elif event.type == "tool_result":
                # Update last tool call with its result
                if result.tool_calls_made:
                    result.tool_calls_made[-1].result = event.tool_result
            elif event.type == "thinking":
                result.thinking += event.content
            elif event.type == "error":
                result.content = event.content
                result.meta["error"] = True
        result.iterations = result.meta.get("iterations", 0)
        result.suggestion_saved = result.meta.get("suggestion_saved")
        return result

    async def stream(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Execute the agent loop, yielding events as they occur."""
        messages = self._build_initial_messages(user_message, context)
        tools = self._toolkit.get_openai_functions() if len(self._toolkit) > 0 else None
        all_tool_calls: list[dict[str, Any]] = []

        for iteration in range(1, self._max_iterations + 1):
            content, thinking_text, tool_calls, meta = await self._call_llm(messages, tools)

            if thinking_text:
                yield AgentEvent(type="thinking", content=thinking_text)

            if not tool_calls:
                # Final response — no more tool calls
                response_text = _remove_thinking(content) if thinking_text else content
                yield AgentEvent(
                    type="completed",
                    content=response_text,
                    meta={**meta, "iterations": iteration},
                )
                return

            # Process tool calls
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                func = tc.get("function", {}) if isinstance(tc, dict) else {}
                tool_name = func.get("name", "") if isinstance(func, dict) else ""
                try:
                    args = json.loads(func.get("arguments", "{}")) if isinstance(func, dict) else {}
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}

                yield AgentEvent(type="tool_call", tool_name=tool_name, tool_args=args)

                result_text = await self._toolkit.execute(tool_name, args)
                all_tool_calls.append({
                    "tool": tool_name,
                    "arguments": args,
                    "result": result_text[:2000],
                })

                yield AgentEvent(type="tool_result", tool_name=tool_name, tool_result=result_text[:2000])

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", "") if isinstance(tc, dict) else "",
                    "name": tool_name,
                    "content": result_text,
                })

        # Max iterations reached
        yield AgentEvent(
            type="completed",
            content=content if content else "Maksimum iterasyon sayisina ulasildi.",
            meta={"iterations": self._max_iterations, "max_iterations_reached": True},
        )

    def cancel(self) -> bool:
        """Cancel the active LLM request if one is in flight."""
        with self._cancel_lock:
            client = self._active_client
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
                self._active_client = None
                return True
        return False

    # ── Private helpers ──────────────────────────────────────────────

    def _build_initial_messages(
        self,
        user_message: str,
        context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        if context:
            messages.append({
                "role": "system",
                "content": f"Context:\n```json\n{json.dumps(context, ensure_ascii=False, default=str)}\n```",
            })
        messages.append({"role": "user", "content": user_message})
        return messages

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[str, str, list[dict[str, Any]], dict[str, Any]]:
        """Make a single LLM call and return (content, thinking, tool_calls, meta)."""
        base_url = _resolve_base_url(self._config)
        model = _resolve_model(self._config)

        request_body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self._config.ai_temperature,
            "max_tokens": self._config.ai_max_tokens,
            "stream": False,
        }

        if tools and self._config.ai_provider in TOOL_CALLING_PROVIDERS:
            request_body["tools"] = tools

        timeout = _build_timeout(self._config)
        headers = _build_headers(self._config)

        async with httpx.AsyncClient(timeout=timeout) as client:
            with self._cancel_lock:
                self._active_client = client
            try:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    json=request_body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
            finally:
                with self._cancel_lock:
                    if self._active_client is client:
                        self._active_client = None

        choice = data.get("choices", [{}])[0] if isinstance(data.get("choices"), list) else {}
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        finish_reason = choice.get("finish_reason", "stop") if isinstance(choice, dict) else "stop"

        content = str(message.get("content") or "")
        tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not isinstance(tool_calls, list):
            tool_calls = []

        thinking_text = _extract_thinking(content)

        # Build meta from usage
        usage = data.get("usage", {})
        meta: dict[str, Any] = {
            "model": data.get("model", model),
            "finish_reason": finish_reason,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }

        return content, thinking_text, tool_calls, meta
