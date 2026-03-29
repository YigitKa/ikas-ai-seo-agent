from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.chat.support import (
    MAX_TOOL_ROUNDS,
    SUGGESTION_SAVE_SUCCESS_MESSAGE,
    _LM_STUDIO_NON_CONTENT_EVENTS,
    _LMStudioNativeUnavailable,
    _StreamingVisibleTextFilter,
    _apply_choice_delta,
    _build_completion_meta,
    _merge_stream_meta_payload,
)

logger = logging.getLogger(__name__)


class ChatServiceStreamingProviderMixin:
        async def async_stream_chat(
            self,
            messages: list[dict],
            tools: list[dict] | None,
        ) -> AsyncIterator[dict[str, Any]]:
            """Stream chat completion chunks and resolve tool calls when needed."""
            # LM Studio: the compat /v1/chat/completions endpoint buffers the full response
            # before sending any SSE data (server-side buffering), so no chunks arrive until
            # generation is 100% complete.  The native /api/v1/chat endpoint flushes every
            # token immediately â€” use it instead for real-time streaming.
            # However, the native endpoint does NOT support tool calling, so when tools
            # are present we fall through to the compat endpoint which handles tool calls.
            if self._config.ai_provider == "lm-studio" and not tools:
                model_name = self._config.ai_model_name or self._get_default_model()
                try:
                    async for event in self._stream_lm_studio_native(messages, tools, model_name):
                        yield event
                    return
                except _LMStudioNativeUnavailable as exc:
                    logger.error("LM Studio native streaming unavailable: %s", exc)
                    raise RuntimeError(
                        "LM Studio native streaming endpoint (/api/v1/chat) kullanilamiyor. "
                        "Gercek zamanli streaming icin LM Studio 0.4+ surumu ve "
                        "AI_BASE_URL=http://localhost:1234/v1 kullanin."
                    ) from exc

            base_url = self._get_base_url()
            model = self._config.ai_model_name or self._get_default_model()
            all_tool_results: list[dict[str, Any]] = []
            last_message_content = ""
            last_meta: dict[str, Any] = {}
            last_suggestion_saved: dict[str, Any] | None = None

            for _round in range(MAX_TOOL_ROUNDS):
                request_body: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": self._config.ai_temperature,
                    "max_tokens": self._config.ai_max_tokens,
                    "stream": True,
                }

                if tools and self._config.ai_provider in ("ollama", "lm-studio", "openai", "openrouter", "custom", "anthropic", "gemini"):
                    request_body["tools"] = tools

                timeout = (
                    httpx.Timeout(600.0, connect=10.0)
                    if self._config.ai_provider in ("ollama", "lm-studio")
                    else httpx.Timeout(120.0, connect=10.0)
                )
                headers = self._build_auth_headers()

                message_content = ""
                thinking_content = ""
                finish_reason = "stop"
                meta_payload: dict[str, Any] = {"model": model}
                tool_calls: list[dict[str, Any]] = []
                streamed_chunk_emitted = False
                tool_calls_by_index: dict[int, dict[str, Any]] = {}
                visible_text_filter = _StreamingVisibleTextFilter()

                async with httpx.AsyncClient(timeout=timeout) as client:
                    with self._active_request_lock:
                        self._active_http_client = client
                    try:
                        async with client.stream(
                            "POST",
                            f"{base_url}/chat/completions",
                            json=request_body,
                            headers=headers,
                        ) as resp:
                            resp.raise_for_status()
                            content_type = resp.headers.get("content-type", "").lower()

                            if "text/event-stream" not in content_type:
                                data = json.loads((await resp.aread()).decode("utf-8"))
                                meta_payload = _merge_stream_meta_payload(meta_payload, data)
                                choice = data.get("choices", [{}])[0]
                                message = choice.get("message", {}) if isinstance(choice, dict) else {}
                                finish_reason = choice.get("finish_reason", "stop") if isinstance(choice, dict) else "stop"
                                message_content = str(message.get("content") or "")
                                raw_tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
                                if isinstance(raw_tool_calls, list):
                                    tool_calls = raw_tool_calls
                            else:
                                pending_data_lines: list[str] = []
                                sse_event_name = ""
                                async for line in resp.aiter_lines():
                                    if not line:
                                        if not pending_data_lines:
                                            sse_event_name = ""
                                            continue
                                        event_data = "\n".join(pending_data_lines)
                                        pending_data_lines.clear()
                                        current_sse_event = sse_event_name
                                        sse_event_name = ""
                                        if event_data == "[DONE]":
                                            break
                                        try:
                                            data = json.loads(event_data)
                                        except json.JSONDecodeError:
                                            logger.debug("Skipping invalid SSE payload: %s", event_data[:200])
                                            continue

                                        meta_payload = _merge_stream_meta_payload(meta_payload, data)
                                        choices = data.get("choices", [])
                                        if not isinstance(choices, list) or not choices:
                                            # Fallback: handle LM Studio native streaming format where
                                            # the compat endpoint returns {"content": "..."} payloads
                                            # (event: message.delta) instead of OpenAI choices structure.
                                            if current_sse_event not in _LM_STUDIO_NON_CONTENT_EVENTS:
                                                native_content = data.get("content")
                                                if isinstance(native_content, str) and native_content:
                                                    message_content += native_content
                                                    visible_chunk = visible_text_filter.consume(native_content)
                                                    thinking_delta = visible_text_filter.drain_thinking()
                                                    if thinking_delta and self._config.ai_thinking_mode_chat:
                                                        yield {"type": "thinking_chunk", "content": thinking_delta}
                                                    if visible_chunk and not tool_calls_by_index:
                                                        streamed_chunk_emitted = True
                                                        yield {"type": "chunk", "content": visible_chunk}
                                            continue

                                        choice = choices[0]
                                        if not isinstance(choice, dict):
                                            continue

                                        content_delta, finish_reason_update, visible_chunk, reasoning_delta = _apply_choice_delta(
                                            choice, visible_text_filter, tool_calls_by_index,
                                        )
                                        if content_delta:
                                            message_content += content_delta
                                        if finish_reason_update:
                                            finish_reason = finish_reason_update
                                        # Emit reasoning_content from providers (LM Studio/Qwen/DeepSeek)
                                        if reasoning_delta and self._config.ai_thinking_mode_chat:
                                            thinking_content += reasoning_delta
                                            yield {"type": "thinking_chunk", "content": reasoning_delta}
                                        thinking_delta = visible_text_filter.drain_thinking()
                                        if thinking_delta and self._config.ai_thinking_mode_chat:
                                            yield {"type": "thinking_chunk", "content": thinking_delta}
                                        if visible_chunk:
                                            streamed_chunk_emitted = True
                                            yield {"type": "chunk", "content": visible_chunk}
                                        continue

                                    if line.startswith(":"):
                                        continue
                                    if line.startswith("event:"):
                                        sse_event_name = line[6:].strip()
                                        continue
                                    if line.startswith("data:"):
                                        pending_data_lines.append(line[5:].lstrip())

                                if pending_data_lines:
                                    event_data = "\n".join(pending_data_lines)
                                    if event_data != "[DONE]":
                                        try:
                                            data = json.loads(event_data)
                                        except json.JSONDecodeError:
                                            logger.debug("Skipping trailing SSE payload: %s", event_data[:200])
                                        else:
                                            meta_payload = _merge_stream_meta_payload(meta_payload, data)
                                            choices = data.get("choices", [])
                                            if isinstance(choices, list) and choices:
                                                choice = choices[0]
                                                if isinstance(choice, dict):
                                                    content_delta, finish_reason_update, visible_chunk, reasoning_delta = _apply_choice_delta(
                                                        choice, visible_text_filter, tool_calls_by_index,
                                                    )
                                                    if content_delta:
                                                        message_content += content_delta
                                                    if finish_reason_update:
                                                        finish_reason = finish_reason_update
                                                    if reasoning_delta and self._config.ai_thinking_mode_chat:
                                                        thinking_content += reasoning_delta
                                                        yield {"type": "thinking_chunk", "content": reasoning_delta}
                                                    thinking_delta = visible_text_filter.drain_thinking()
                                                    if thinking_delta and self._config.ai_thinking_mode_chat:
                                                        yield {"type": "thinking_chunk", "content": thinking_delta}
                                                    if visible_chunk:
                                                        streamed_chunk_emitted = True
                                                        yield {"type": "chunk", "content": visible_chunk}
                    finally:
                        with self._active_request_lock:
                            if self._active_http_client is client:
                                self._active_http_client = None

                if not tool_calls and tool_calls_by_index:
                    tool_calls = [tool_calls_by_index[index] for index in sorted(tool_calls_by_index)]

                trailing_visible_chunk = visible_text_filter.finalize()
                if trailing_visible_chunk and not tool_calls and not tool_calls_by_index:
                    streamed_chunk_emitted = True
                    yield {
                        "type": "chunk",
                        "content": trailing_visible_chunk,
                    }

                meta = _build_completion_meta(meta_payload, model, finish_reason)
                self._total_tokens["input"] += int(meta.get("input_tokens", 0) or 0)
                self._total_tokens["output"] += int(meta.get("output_tokens", 0) or 0)
                self._total_tokens["estimated_cost"] = round(
                    float(self._total_tokens.get("estimated_cost", 0.0))
                    + float(meta.get("estimated_cost", 0.0)),
                    6,
                )

                last_message_content = message_content
                last_meta = meta

                logger.debug(
                    "[CHAT_STREAM] round=%d finish=%s tool_calls=%d content_len=%d",
                    _round, finish_reason, len(tool_calls), len(message_content),
                )

                if tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": message_content,
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

                        result_text, suggestion_saved = await self._execute_chat_tool(tool_name, args)
                        if suggestion_saved:
                            last_suggestion_saved = suggestion_saved

                        tool_result = {
                            "tool": tool_name,
                            "arguments": args,
                            "result": result_text[:2000],
                        }
                        all_tool_results.append(tool_result)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", "") if isinstance(tc, dict) else "",
                            "name": tool_name,
                            "content": result_text,
                        })

                    if last_suggestion_saved:
                        confirmation_message = SUGGESTION_SAVE_SUCCESS_MESSAGE
                        yield {
                            "type": "chunk",
                            "content": confirmation_message,
                        }
                        yield {
                            "type": "completion_result",
                            "content": confirmation_message,
                            "thinking": "",
                            "tool_results": list(all_tool_results),
                            "meta": {
                                **meta,
                                "source": "suggestion_saved",
                            },
                            "suggestion_saved": last_suggestion_saved,
                        }
                        return

                    continue

                embedded_thinking = self._extract_thinking(message_content) if self._config.ai_thinking_mode_chat else ""
                response_text = self._remove_thinking(message_content) if embedded_thinking else message_content

                # Merge reasoning_content (from delta.reasoning_content) with <think> blocks
                if self._config.ai_thinking_mode_chat:
                    parts = [p for p in (thinking_content.strip(), embedded_thinking) if p]
                    thinking_text = "\n\n".join(parts)
                else:
                    thinking_text = ""

                if response_text and not streamed_chunk_emitted:
                    yield {
                        "type": "chunk",
                        "content": response_text,
                    }

                if meta:
                    meta["session_total_cost"] = round(float(self._total_tokens.get("estimated_cost", 0.0)), 6)
                yield {
                    "type": "completion_result",
                    "content": response_text,
                    "thinking": thinking_text,
                    "tool_results": list(all_tool_results),
                    "meta": meta,
                    "suggestion_saved": last_suggestion_saved,
                }
                return

            if last_meta:
                last_meta["session_total_cost"] = round(float(self._total_tokens.get("estimated_cost", 0.0)), 6)
            yield {
                "type": "completion_result",
                "content": last_message_content or "Maksimum arac cagrisi sayisina ulasildi.",
                "thinking": "",
                "tool_results": list(all_tool_results),
                "meta": last_meta,
                "suggestion_saved": last_suggestion_saved,
            }


        def _get_base_url(self) -> str:
            """Get the base URL for the AI provider."""
            if self._config.ai_base_url:
                url = self._config.ai_base_url.rstrip("/")
                if not url.endswith("/v1"):
                    url += "/v1" if "/v1" not in url else ""
                return url

            provider = self._config.ai_provider
            defaults = {
                "ollama": "http://localhost:11434/v1",
                "lm-studio": "http://localhost:1234/v1",
                "openai": "https://api.openai.com/v1",
                "openrouter": "https://openrouter.ai/api/v1",
                "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
                "anthropic": "https://api.anthropic.com/v1",
            }
            return defaults.get(provider, "http://localhost:11434/v1")

        def _get_default_model(self) -> str:
            """Get the default model for the provider."""
            defaults = {
                "ollama": "llama3.2",
                "lm-studio": "default",
                "openai": "gpt-4o-mini",
                "openrouter": "openai/gpt-4o-mini",
                "gemini": "gemini-1.5-flash",
                "anthropic": "claude-haiku-4-5-20251001",
            }
            return defaults.get(self._config.ai_provider, "llama3.2")

        @staticmethod
        def _extract_thinking(text: str) -> str:
            """Extract <think>...</think> blocks from response."""
            match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            open_match = re.search(r"<think>(.*)$", text, re.DOTALL)
            return open_match.group(1).strip() if open_match else ""

        @staticmethod
        def _remove_thinking(text: str) -> str:
            """Remove <think>...</think> blocks from response."""
            cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
            if "<think>" in cleaned:
                cleaned = cleaned.split("<think>", 1)[0]
            return cleaned.strip()

