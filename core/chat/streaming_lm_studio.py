from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.chat.support import (
    _LMStudioNativeUnavailable,
    _StreamingVisibleTextFilter,
    _lm_studio_native_base,
)

logger = logging.getLogger(__name__)


class ChatServiceStreamingLMStudioMixin:
        def _build_lm_studio_native_payload(
            self,
            messages: list[dict],
            tools: list[dict] | None,
            model: str,
        ) -> dict[str, Any]:
            """Convert an OpenAI-style messages list to LM Studio native /api/v1/chat payload."""
            system_parts: list[str] = []
            conv_parts: list[str] = []
            last_user_input = ""

            for m in messages:
                role = m.get("role", "")
                content = m.get("content") or ""
                if not isinstance(content, str):
                    try:
                        content = str(content)
                    except Exception:
                        content = ""
                if role == "system":
                    system_parts.append(content)
                elif role == "user":
                    last_user_input = content
                    conv_parts.append(f"User: {content}")
                elif role == "assistant":
                    text = content or ""
                    conv_parts.append(f"Assistant: {text}")
                elif role == "tool":
                    conv_parts.append(f"[Tool result: {content[:500]}]")

            system_prompt = "\n\n".join(p for p in system_parts if p)

            # If there are prior conversation turns, append them to the system prompt
            # so the model has full context (stateless multi-turn).
            if len(conv_parts) > 1:
                prior_history = "\n".join(conv_parts[:-1])
                system_prompt = (
                    f"{system_prompt}\n\n## Conversation History\n{prior_history}"
                    if system_prompt
                    else f"## Conversation History\n{prior_history}"
                )

            payload: dict[str, Any] = {
                "model": model,
                "system_prompt": system_prompt,
                "input": last_user_input,
                "temperature": self._config.ai_temperature,
                "max_output_tokens": self._config.ai_max_tokens,
                "stream": True,
            }

            # Include tool names as informational context (model can't call them via native API,
            # but the system prompt already contains product data so most queries work without tools).
            if tools:
                tool_names = [
                    t.get("function", {}).get("name", "")
                    for t in tools
                    if isinstance(t, dict)
                ]
                tool_names = [n for n in tool_names if n]
                if tool_names:
                    payload["system_prompt"] = (
                        (payload.get("system_prompt") or "")
                        + f"\n\n[Available analysis tools: {', '.join(tool_names)}]"
                    )

            return payload

        async def _stream_lm_studio_native(
            self,
            messages: list[dict],
            tools: list[dict] | None,
            model: str,
        ) -> AsyncIterator[dict[str, Any]]:
            """Use LM Studio's native /api/v1/chat endpoint which streams tokens in real-time.

            Unlike the compat /v1/chat/completions endpoint (which buffers the full response),
            the native endpoint flushes each token immediately via SSE message.delta events.
            """
            native_base = _lm_studio_native_base(self._config.ai_base_url or "")
            url = f"{native_base}/api/v1/chat"
            payload = self._build_lm_studio_native_payload(messages, tools, model)

            headers: dict[str, str] = {"Content-Type": "application/json"}
            api_key = (self._config.ai_api_key or "").strip()
            if api_key and api_key not in {"lm-studio", "ollama"}:
                headers["Authorization"] = f"Bearer {api_key}"

            timeout = httpx.Timeout(600.0, connect=10.0)
            message_content = ""
            thinking_content = ""
            finish_reason = "stop"
            meta: dict[str, Any] = {"model": model}
            visible_text_filter = _StreamingVisibleTextFilter()
            streamed_chunk_emitted = False

            async with httpx.AsyncClient(timeout=timeout) as client:
                with self._active_request_lock:
                    self._active_http_client = client
                try:
                    async with client.stream("POST", url, json=payload, headers=headers) as resp:
                        if resp.status_code in (404, 405, 501):
                            raise _LMStudioNativeUnavailable(
                                f"LM Studio native endpoint returned {resp.status_code}"
                            )
                        resp.raise_for_status()
                        content_type = resp.headers.get("content-type", "").lower()
                        if "text/event-stream" not in content_type:
                            raise _LMStudioNativeUnavailable(
                                "LM Studio native endpoint did not return SSE "
                                f"(content-type={content_type or 'unknown'})"
                            )

                        sse_event = ""
                        pending_lines: list[str] = []

                        async for line in resp.aiter_lines():
                            if not line:
                                if not pending_lines:
                                    sse_event = ""
                                    continue
                                data_str = "\n".join(pending_lines)
                                event_name = sse_event
                                sse_event = ""
                                pending_lines = []

                                if event_name == "message.delta":
                                    try:
                                        data = json.loads(data_str)
                                        chunk = data.get("content", "")
                                        if isinstance(chunk, str) and chunk:
                                            message_content += chunk
                                            visible = visible_text_filter.consume(chunk)
                                            if visible:
                                                streamed_chunk_emitted = True
                                                yield {"type": "chunk", "content": visible}
                                    except json.JSONDecodeError:
                                        pass

                                elif event_name == "reasoning.delta":
                                    try:
                                        data = json.loads(data_str)
                                        chunk = data.get("content", "")
                                        if isinstance(chunk, str) and chunk:
                                            thinking_content += chunk
                                            if self._config.ai_thinking_mode_chat:
                                                yield {
                                                    "type": "thinking_chunk",
                                                    "content": chunk,
                                                }
                                    except json.JSONDecodeError:
                                        pass

                                elif event_name == "chat.end":
                                    try:
                                        data = json.loads(data_str)
                                        result = data.get("result") or {}
                                        stats = result.get("stats") or {}
                                        usage = result.get("usage") or {}
                                        output_items = result.get("output")
                                        if isinstance(output_items, list):
                                            for item in output_items:
                                                if not isinstance(item, dict):
                                                    continue
                                                output_type = str(item.get("type") or "")
                                                output_raw = item.get("content")
                                                output_text = ""
                                                if isinstance(output_raw, str):
                                                    output_text = output_raw
                                                elif isinstance(output_raw, list):
                                                    parts: list[str] = []
                                                    for part in output_raw:
                                                        if isinstance(part, str):
                                                            parts.append(part)
                                                            continue
                                                        if not isinstance(part, dict):
                                                            continue
                                                        text_part = part.get("text")
                                                        if isinstance(text_part, str):
                                                            parts.append(text_part)
                                                    output_text = "".join(parts)

                                                if not output_text:
                                                    continue
                                                if output_type == "message" and not message_content:
                                                    message_content = output_text
                                                elif output_type == "reasoning" and not thinking_content:
                                                    thinking_content = output_text

                                        meta = {
                                            "model": result.get("model", model),
                                            "finish_reason": (
                                                result.get("stopReason")
                                                or stats.get("stop_reason")
                                                or "stop"
                                            ),
                                            "input_tokens": int(
                                                usage.get("promptTokens")
                                                or stats.get("input_tokens", 0)
                                                or 0
                                            ),
                                            "output_tokens": int(
                                                usage.get("completionTokens")
                                                or stats.get("total_output_tokens", 0)
                                                or 0
                                            ),
                                        }
                                        for stat_key, meta_key in (
                                            ("tokens_per_second", "tokens_per_second"),
                                            ("time_to_first_token_seconds", "time_to_first_token_seconds"),
                                        ):
                                            val = stats.get(stat_key)
                                            if val is not None:
                                                try:
                                                    meta[meta_key] = float(val)
                                                except (TypeError, ValueError):
                                                    pass
                                        total = (
                                            meta["input_tokens"] + meta["output_tokens"]
                                        )
                                        if total:
                                            meta["total_tokens"] = total
                                        finish_reason = str(meta.get("finish_reason") or "stop")
                                    except (json.JSONDecodeError, KeyError, TypeError):
                                        pass
                                continue  # blank line handled â€” skip to next line

                            if line.startswith("event:"):
                                sse_event = line[6:].strip()
                            elif line.startswith("data:"):
                                pending_lines.append(line[5:].lstrip())
                finally:
                    with self._active_request_lock:
                        if self._active_http_client is client:
                            self._active_http_client = None

            trailing = visible_text_filter.finalize()
            if trailing:
                streamed_chunk_emitted = True
                yield {"type": "chunk", "content": trailing}

            embedded_thinking = self._extract_thinking(message_content) if self._config.ai_thinking_mode_chat else ""
            response_text = (
                self._remove_thinking(message_content) if embedded_thinking else message_content
            )
            if self._config.ai_thinking_mode_chat:
                if embedded_thinking and thinking_content:
                    thinking_text = f"{thinking_content}\n\n{embedded_thinking}".strip()
                elif embedded_thinking:
                    thinking_text = embedded_thinking
                else:
                    thinking_text = thinking_content.strip()
            else:
                thinking_text = ""

            if response_text and not streamed_chunk_emitted:
                yield {"type": "chunk", "content": response_text}

            yield {
                "type": "completion_result",
                "content": response_text,
                "thinking": thinking_text,
                "tool_results": [],
                "meta": {**meta, "finish_reason": finish_reason},
                "suggestion_saved": None,
            }

