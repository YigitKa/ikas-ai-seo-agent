from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import logging
import re
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx

from core.agent.tools import AgentToolkit, create_chat_toolkit
from core.chat.support import (
    APPLY_INTENT_EXTRACTION_SYSTEM_PROMPT,
    APPLY_SEO_TO_IKAS_TOOL_NAME,
    CHAT_ACTION_PATTERN,
    GENERATE_SUGGESTION_PATTERN,
    HISTORY_SUMMARY_KEEP_RECENT_MESSAGES,
    HISTORY_SUMMARY_SYSTEM_PREFIX,
    HISTORY_SUMMARY_TRIGGER_MESSAGES,
    IKAS_OPERATION_GUIDE_TR,
    MAX_HISTORY_MESSAGES,
    MAX_TOOL_ROUNDS,
    MEMORY_SUMMARIZATION_PROMPT,
    SAVE_INTENT_PATTERN,
    SAVE_SEO_SUGGESTION_FIELD_MAP,
    SAVE_SEO_SUGGESTION_TOOL_INSTRUCTION,
    SAVE_SEO_SUGGESTION_TOOL_NAME,
    SEMANTIC_ROUTING_JSON_PATTERN,
    SEMANTIC_ROUTING_SYSTEM_PROMPT,
    STRUCTURED_SUGGESTION_OPTIONS_INSTRUCTION,
    SINGLE_PRODUCT_APPLY_ACTIONS,
    SUGGESTION_APPLY_FIELD_CONFIG,
    SUGGESTION_SAVE_SUCCESS_MESSAGE,
    SUGGESTION_REQUEST_HINT_PATTERN,
    ToolRegistry,
    _LMStudioNativeUnavailable,
    _StreamingVisibleTextFilter,
    _append_false_action_disclaimer,
    _append_operation_suggestion,
    _apply_choice_delta,
    _build_apply_seo_to_ikas_tool,
    _build_completion_meta,
    _build_local_no_think_instruction,
    _build_product_context,
    _build_save_seo_suggestion_tool,
    _build_tool_catalog_instruction,
    _compact_preview_text,
    _decode_json_string_fragment,
    _detect_manual_apply_action,
    _detect_suggestion_field_heading,
    _extract_chat_action,
    _extract_chat_action_payload,
    _extract_chat_completion_content,
    _extract_mcp_json_payload,
    _extract_mcp_text,
    _extract_suggestion_fields_from_text,
    _first_number,
    _format_chat_error,
    _format_decimal,
    _format_money,
    _has_mutation_tool_result,
    _lm_studio_native_base,
    _looks_like_final_suggestion_value,
    _looks_like_option_selection,
    _resolve_typed_option_selection,
    _message_has_apply_intent,
    _message_has_save_intent,
    _merge_stream_meta_payload,
    _normalize_matching_text,
    _operation_footer_already_present,
    _parse_agent_type,
    _should_request_structured_suggestion_options,
    _LM_STUDIO_NON_CONTENT_EVENTS,
)
from core.clients.ikas import IkasClient
from core.models import AppConfig, ChatMessage, ChatResponse, Product, SeoScore, SeoSuggestion
from core.clients.mcp import IkasMCPClient, MCPError

logger = logging.getLogger(__name__)


class ChatServiceStreamingMixin:
        async def send_message(self, user_message: str) -> ChatResponse:
            """Send a user message and get an AI response."""
            return await self._run_message_flow(user_message)

        async def stream_message(self, user_message: str) -> AsyncIterator[dict[str, Any]]:
            """Stream chat chunks followed by a final response payload."""
            queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

            async def emit_chunk(chunk: str) -> None:
                if not chunk:
                    return
                await queue.put({
                    "type": "chunk",
                    "content": chunk,
                })

            async def emit_stream_event(event: dict[str, Any]) -> None:
                event_type = str(event.get("type") or "")
                if event_type not in {"chunk", "thinking_chunk"}:
                    return
                content = str(event.get("content") or "")
                if not content:
                    return
                await queue.put({
                    "type": event_type,
                    "content": content,
                })

            async def runner() -> ChatResponse:
                try:
                    return await self._run_message_flow(
                        user_message,
                        chunk_handler=emit_chunk,
                        event_handler=emit_stream_event,
                    )
                finally:
                    await queue.put(None)

            task = asyncio.create_task(runner())

            try:
                while True:
                    event = await queue.get()
                    if event is None:
                        break
                    yield event

                response = await task
            except asyncio.CancelledError:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
                raise
            except Exception:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
                raise

            yield self._build_response_done_event(response)

        def _build_completion_messages(
            self,
            cleaned_message: str,
            routing_instruction: str | None,
            agent_type: str,
            allow_tools: bool,
            guided_context: str,
            mcp_available: bool,
            include_save_seo_tool: bool,
            *,
            is_generate_request: bool = False,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
            """Build the messages list and tools for the AI completion call.

            All system-level instructions are consolidated into a single system
            message so that models with strict jinja chat templates (e.g. qwen)
            can locate the user message without confusion.

            When *is_generate_request* is True a minimal system prompt and only
            the ``save_seo_suggestion`` tool are sent to stay within small
            context windows (e.g. 4 096 tokens).
            """

            if is_generate_request:
                return self._build_generate_messages(cleaned_message)

            # --- Collect all system-level parts into one block ---
            compact = self._config.ai_provider in ("lm-studio", "ollama")
            system_parts: list[str] = [
                _build_product_context(self._product, self._score, agent_type, compact=compact),
            ]
            if _should_request_structured_suggestion_options(cleaned_message):
                system_parts.append(STRUCTURED_SUGGESTION_OPTIONS_INSTRUCTION)

            # Skip verbose routing / MCP instructions for compact (local) models
            if not compact:
                if routing_instruction:
                    system_parts.append(routing_instruction)

            local_no_think_instruction = _build_local_no_think_instruction(self._config)
            if local_no_think_instruction:
                system_parts.append(local_no_think_instruction)

            if allow_tools and mcp_available and guided_context:
                system_parts.append(
                    "Asagidaki ikas MCP sonucu dogrulanmis canli veridir. "
                    "Bu veriyi esas al, veri uydurma ve degistirme:\n"
                    f"{guided_context}"
                )
            elif allow_tools and not mcp_available and not compact:
                system_parts.append(
                    "ikas MCP su anda hazir degil. Canli veri cekemedigini acikca belirt "
                    "ve magaza verisi uydurma."
                )

            tools, tool_instructions = self._build_chat_tools(
                allow_mcp_tools=allow_tools,
                guided_context=guided_context,
                agent_type=agent_type,
                include_save_seo_tool=include_save_seo_tool,
            )
            if not compact:
                system_parts.extend(tool_instructions)

            # Single consolidated system message
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": "\n\n".join(p for p in system_parts if p)},
            ]

            for msg in self._history:
                m: dict[str, Any] = {"role": msg.role, "content": msg.content}
                if msg.tool_calls:
                    m["tool_calls"] = msg.tool_calls
                if msg.tool_call_id:
                    m["tool_call_id"] = msg.tool_call_id
                if msg.role == "tool" and msg.name:
                    m["name"] = msg.name
                messages.append(m)

            return messages, tools

        def _build_generate_messages(
            self,
            cleaned_message: str,
        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
            """Build a minimal messages + tools payload for generate-suggestion requests.

            Only sends the product fields the model needs and the
            ``save_seo_suggestion`` tool — keeps the total under ~1 500 tokens
            so even 4 096-context models can handle it.
            """
            product_lines: list[str] = []
            if self._product:
                p = self._product
                product_lines = [
                    f"Urun: {p.name}",
                    f"Kategori: {p.category or '-'}",
                    f"Meta Title: {p.meta_title or '-'}",
                    f"Meta Description: {p.meta_description or '-'}",
                    f"Aciklama (ozet): {(p.description or '')[:150]}",
                ]

            system_prompt = (
                "Sen SEO uzmansin. Kullanicinin sectigi secenek dogrultusunda "
                "urun icin somut SEO degerlerini olustur ve save_seo_suggestion "
                "aracini cagirarak kaydet. Dusunme, dogrudan araci cagir. /no_think\n\n"
                + "\n".join(product_lines)
            )

            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": cleaned_message},
            ]

            tools: list[dict[str, Any]] = [_build_save_seo_suggestion_tool()]

            return messages, tools

        async def _run_message_flow(
            self,
            user_message: str,
            chunk_handler: Callable[[str], Awaitable[None]] | None = None,
            event_handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        ) -> ChatResponse:
            """Run the full chat flow, optionally streaming assistant chunks."""
            # Detect [[GENERATE_SUGGESTION]] marker — this means the user selected
            # an option button and the AI should generate concrete values first.
            # Strip the marker and skip save/apply flow interception.
            is_generate_request = bool(GENERATE_SUGGESTION_PATTERN.search(user_message or ""))
            logger.debug("[MSG_FLOW] is_generate_request=%s message=%s...", is_generate_request, (user_message or "")[:60])
            if is_generate_request:
                user_message = GENERATE_SUGGESTION_PATTERN.sub("", user_message).strip()

            cleaned_message, routing_instruction, agent_type, allow_tools = await self._extract_message_directives(user_message)
            has_apply_intent = _message_has_apply_intent(cleaned_message)
            has_save_intent = _message_has_save_intent(cleaned_message)

            # If the user typed "1. secenegi sec" instead of clicking, resolve the
            # option value from the last assistant message and enrich the message
            # to match what the frontend would have sent.
            if not is_generate_request and _looks_like_option_selection(cleaned_message):
                is_generate_request = True
                resolved = _resolve_typed_option_selection(cleaned_message, self._history)
                if resolved:
                    cleaned_message = resolved

            # Force SEO agent for generate requests — always an SEO content task
            if is_generate_request and agent_type != "seo":
                agent_type = "seo"

            # Ensure tool calling is allowed when we need to save/apply or generate suggestions
            if is_generate_request or has_apply_intent or has_save_intent:
                allow_tools = True

            # Add user message to history and trim if needed
            user_msg = ChatMessage(role="user", content=cleaned_message)
            self._history.append(user_msg)
            if len(self._history) > MAX_HISTORY_MESSAGES:
                self._history = self._history[-MAX_HISTORY_MESSAGES:]

            # Skip save/apply flow interception when the message is a generate
            # request — the AI needs to produce concrete values first.
            if not is_generate_request:
                single_save_response = await self._maybe_handle_single_product_save_flow(
                    cleaned_message,
                    chunk_handler=chunk_handler,
                )
                if single_save_response is not None:
                    return single_save_response

                single_apply_response = await self._maybe_handle_single_product_apply_flow(
                    cleaned_message,
                    chunk_handler=chunk_handler,
                )
                if single_apply_response is not None:
                    return single_apply_response

            # Optionally prefetch guided MCP data for live-data questions
            # Skip guided MCP for generate requests — the AI needs to produce
            # concrete SEO values via save_seo_suggestion, not summarise MCP data.
            guided_context = ""
            guided_tool_results: list[dict[str, Any]] = []
            guided_fallback = ""
            mcp_available = bool(self._mcp_initialized and self._mcp)
            if allow_tools and mcp_available and not is_generate_request:
                try:
                    guided_result = await self._maybe_run_guided_mcp_request()
                except Exception as exc:
                    logger.warning("Guided MCP request failed: %s", exc)
                    guided_result = None

                if guided_result:
                    guided_context, guided_tool_results, guided_fallback = guided_result
                    if not has_apply_intent and not is_generate_request:
                        # Return the MCP result directly without a secondary AI call
                        guided_content = _append_operation_suggestion(
                            guided_fallback,
                            user_message=cleaned_message,
                            product=self._product,
                            agent_type=agent_type,
                        )
                        self._history.append(ChatMessage(role="assistant", content=guided_content))
                        response = ChatResponse(
                            content=guided_content,
                            thinking="",
                            tool_results=guided_tool_results,
                            error=False,
                            meta={"model": "ikas MCP", "finish_reason": "guided_mcp", "source": "ikas_mcp"},
                            pending_suggestion=self._get_session_pending_suggestion(),
                        )
                        if chunk_handler and response.content:
                            await chunk_handler(response.content)
                        self._schedule_history_summarization()
                        return response

            messages, tools = self._build_completion_messages(
                cleaned_message,
                routing_instruction,
                agent_type,
                allow_tools,
                guided_context,
                mcp_available,
                include_save_seo_tool=(agent_type == "seo" or has_apply_intent or is_generate_request),
                is_generate_request=is_generate_request,
            )

            response_text = ""
            thinking_text = ""
            tool_results: list[dict[str, Any]] = list(guided_tool_results)
            meta: dict[str, Any] = {}
            suggestion_saved: dict[str, Any] | None = None
            pending_suggestion = self._get_session_pending_suggestion()

            try:
                logger.debug("[CHAT_FLOW] entering completion, chunk_handler=%s tools=%d is_gen=%s",
                    chunk_handler is not None, len(tools or []), is_generate_request)
                if chunk_handler is None:
                    completion_result = await self._chat_completion(messages, tools)
                else:
                    stream_signature = inspect.signature(self._chat_completion_stream)
                    if "event_handler" in stream_signature.parameters:
                        completion_result = await self._chat_completion_stream(
                            messages, tools, chunk_handler, event_handler=event_handler,
                        )
                    else:
                        completion_result = await self._chat_completion_stream(
                            messages, tools, chunk_handler,
                        )
                logger.debug("[CHAT_FLOW] completion done, result type=%s", type(completion_result).__name__)
                response_text, thinking_text, completion_tool_results, meta, suggestion_saved = (
                    self._normalize_completion_result(completion_result)
                )
                tool_results.extend(completion_tool_results)
            except asyncio.CancelledError:
                logger.info("Chat request cancelled by user")
                if user_msg in self._history:
                    self._history.remove(user_msg)
                raise
            except Exception as exc:
                logger.exception("Chat completion failed")
                if self._history and self._history[-1] is user_msg:
                    self._history.pop()
                if guided_fallback:
                    guided_content = _append_operation_suggestion(
                        guided_fallback, user_message=cleaned_message, product=self._product, agent_type=agent_type,
                    )
                    self._history.append(ChatMessage(role="assistant", content=guided_content))
                    response = ChatResponse(
                        content=guided_content,
                        thinking="",
                        tool_results=tool_results,
                        error=False,
                        meta={"model": "ikas MCP", "finish_reason": "guided_mcp_fallback", "source": "ikas_mcp"},
                        pending_suggestion=pending_suggestion,
                    )
                else:
                    response = ChatResponse(
                        content=_append_operation_suggestion(
                            _format_chat_error(exc), user_message=cleaned_message, product=self._product,
                            agent_type=agent_type,
                        ),
                        thinking="",
                        tool_results=tool_results,
                        error=True,
                        meta={},
                        pending_suggestion=pending_suggestion,
                    )
                if chunk_handler and response.content:
                    await chunk_handler(response.content)
                self._schedule_history_summarization()
                return response

            # Safety net: if the LLM output suggestion fields as JSON text instead
            # of calling save_seo_suggestion, parse and save programmatically.
            if not suggestion_saved and response_text and self._product:
                inline_fields = _extract_suggestion_fields_from_text(response_text)
                if inline_fields:
                    _, suggestion_saved = await self._save_suggestion_from_tool_args(inline_fields)
                    if suggestion_saved:
                        pending_suggestion = self._get_session_pending_suggestion()

            if suggestion_saved:
                pending_suggestion = self._get_session_pending_suggestion()
                response_text = self._build_suggestion_saved_response(suggestion_saved)
                if has_apply_intent and self._product:
                    if pending_suggestion:
                        pending_fields = self._collect_applicable_suggestion_fields(pending_suggestion)
                        if pending_fields:
                            response_text = (
                                f"{SUGGESTION_SAVE_SUCCESS_MESSAGE}\n\n"
                                + self._build_single_apply_confirmation_response(
                                    pending_suggestion,
                                    pending_fields,
                                )
                            )
            elif not response_text and guided_fallback:
                response_text = guided_fallback
            elif not response_text.strip() and thinking_text:
                response_text = (
                    "Model nihai cevap uretmedi. Yerel model dusunce modunda takilmis olabilir; "
                    "daha kisa bir istek deneyin veya Thinking Mode'u kapatin."
                )

            if not suggestion_saved:
                response_text = _append_operation_suggestion(
                    response_text, user_message=cleaned_message, product=self._product, agent_type=agent_type,
                )
                response_text = _append_false_action_disclaimer(response_text, tool_results)

            self._history.append(ChatMessage(role="assistant", content=response_text))
            self._schedule_history_summarization()

            return ChatResponse(
                content=response_text,
                thinking=thinking_text,
                tool_results=tool_results,
                error=False,
                meta=meta,
                suggestion_saved=suggestion_saved,
                pending_suggestion=pending_suggestion,
            )

        async def _chat_completion_stream(
            self,
            messages: list[dict],
            tools: list[dict] | None,
            chunk_handler: Callable[[str], Awaitable[None]],
            event_handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        ) -> tuple[str, str, list[dict], dict, dict[str, Any] | None]:
            """Consume the streaming completion generator and forward text chunks."""
            final_event: dict[str, Any] | None = None
            event_count = 0

            logger.debug("[CHAT_STREAM] Starting completion stream, tools=%d", len(tools or []))
            async for event in self.async_stream_chat(messages, tools):
                event_type = str(event.get("type") or "")
                event_count += 1
                if event_type in {"chunk", "thinking_chunk"}:
                    chunk = str(event.get("content") or "")
                    if chunk:
                        if event_handler is not None:
                            await event_handler({
                                "type": event_type,
                                "content": chunk,
                            })
                        elif event_type == "chunk":
                            await chunk_handler(chunk)
                    continue

                if event_type == "completion_result":
                    final_event = event

            logger.debug("[CHAT_STREAM] Stream done, events=%d final=%s", event_count, final_event is not None)
            if final_event is None:
                raise RuntimeError("Chat completion stream ended without a final result.")

            return (
                str(final_event.get("content") or ""),
                str(final_event.get("thinking") or ""),
                list(final_event.get("tool_results") or []),
                dict(final_event.get("meta") or {}),
                dict(final_event.get("suggestion_saved") or {}) or None,
            )

        @staticmethod
        def _build_response_done_event(response: ChatResponse) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "type": "response_done",
                "content": response.content,
                "thinking": response.thinking,
                "tool_results": response.tool_results,
                "error": response.error,
                "meta": response.meta,
                "pending_suggestion": (
                    response.pending_suggestion.model_dump(mode="json")
                    if response.pending_suggestion
                    else None
                ),
            }
            if response.suggestion_saved:
                payload["suggestion_saved"] = response.suggestion_saved

            # Signal frontend to refresh product data after a successful apply
            if response.tool_results:
                for tr in response.tool_results:
                    if tr.get("tool") == "chat_single_product_apply":
                        try:
                            result_data = json.loads(tr.get("result", "{}"))
                            if result_data.get("ok"):
                                payload["product_updated"] = True
                                break
                        except (json.JSONDecodeError, TypeError):
                            pass

            return payload

        @staticmethod
        def _normalize_completion_result(
            result: Any,
        ) -> tuple[str, str, list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
            if not isinstance(result, tuple):
                raise TypeError("Chat completion must return a tuple.")

            if len(result) == 4:
                response_text, thinking_text, tool_results, meta = result
                suggestion_saved = None
            elif len(result) == 5:
                response_text, thinking_text, tool_results, meta, suggestion_saved = result
            else:
                raise ValueError("Unexpected chat completion result shape.")

            return (
                str(response_text or ""),
                str(thinking_text or ""),
                list(tool_results or []),
                dict(meta or {}),
                dict(suggestion_saved or {}) or None,
            )

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
                                continue  # blank line handled — skip to next line

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

            embedded_thinking = self._extract_thinking(message_content)
            response_text = (
                self._remove_thinking(message_content) if embedded_thinking else message_content
            )
            if embedded_thinking and thinking_content:
                thinking_text = f"{thinking_content}\n\n{embedded_thinking}".strip()
            elif embedded_thinking:
                thinking_text = embedded_thinking
            else:
                thinking_text = thinking_content.strip()

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

        async def async_stream_chat(
            self,
            messages: list[dict],
            tools: list[dict] | None,
        ) -> AsyncIterator[dict[str, Any]]:
            """Stream chat completion chunks and resolve tool calls when needed."""
            # LM Studio: the compat /v1/chat/completions endpoint buffers the full response
            # before sending any SSE data (server-side buffering), so no chunks arrive until
            # generation is 100% complete.  The native /api/v1/chat endpoint flushes every
            # token immediately — use it instead for real-time streaming.
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
                                                    if visible_chunk and not tool_calls_by_index:
                                                        streamed_chunk_emitted = True
                                                        yield {"type": "chunk", "content": visible_chunk}
                                            continue

                                        choice = choices[0]
                                        if not isinstance(choice, dict):
                                            continue

                                        content_delta, finish_reason_update, visible_chunk = _apply_choice_delta(
                                            choice, visible_text_filter, tool_calls_by_index,
                                        )
                                        if content_delta:
                                            message_content += content_delta
                                        if finish_reason_update:
                                            finish_reason = finish_reason_update
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
                                                    content_delta, finish_reason_update, visible_chunk = _apply_choice_delta(
                                                        choice, visible_text_filter, tool_calls_by_index,
                                                    )
                                                    if content_delta:
                                                        message_content += content_delta
                                                    if finish_reason_update:
                                                        finish_reason = finish_reason_update
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

                thinking_text = self._extract_thinking(message_content)
                response_text = self._remove_thinking(message_content) if thinking_text else message_content

                if response_text and not streamed_chunk_emitted:
                    yield {
                        "type": "chunk",
                        "content": response_text,
                    }

                yield {
                    "type": "completion_result",
                    "content": response_text,
                    "thinking": thinking_text,
                    "tool_results": list(all_tool_results),
                    "meta": meta,
                    "suggestion_saved": last_suggestion_saved,
                }
                return

            yield {
                "type": "completion_result",
                "content": last_message_content or "Maksimum arac cagrisi sayisina ulasildi.",
                "thinking": "",
                "tool_results": list(all_tool_results),
                "meta": last_meta,
                "suggestion_saved": last_suggestion_saved,
            }

        async def _chat_completion(
            self,
            messages: list[dict],
            tools: list[dict] | None,
        ) -> tuple[str, str, list[dict], dict, dict[str, Any] | None]:
            """Run chat completion with automatic tool-call handling."""
            final_event: dict[str, Any] | None = None

            async for event in self.async_stream_chat(messages, tools):
                if event.get("type") == "completion_result":
                    final_event = event

            if final_event is None:
                return "", "", [], {}, None

            return (
                str(final_event.get("content") or ""),
                str(final_event.get("thinking") or ""),
                list(final_event.get("tool_results") or []),
                dict(final_event.get("meta") or {}),
                dict(final_event.get("suggestion_saved") or {}) or None,
            )

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

        async def close(self) -> None:
            """Close MCP connection."""
            self.cancel_active_request()
            if self._mcp:
                await self._mcp.close()
                self._mcp = None
                self._mcp_initialized = False
