from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from core.chat.support import (
    GENERATE_SUGGESTION_PATTERN,
    MAX_HISTORY_MESSAGES,
    SUGGESTION_SAVE_SUCCESS_MESSAGE,
    _append_false_action_disclaimer,
    _append_operation_suggestion,
    _extract_suggestion_fields_from_text,
    _format_chat_error,
    _is_en_description_translation_request,
    _looks_like_option_selection,
    _message_has_apply_intent,
    _message_has_save_intent,
    _resolve_typed_option_selection,
)
from core.models import ChatMessage, ChatResponse
from core.permissions import build_runtime_allow_rule

logger = logging.getLogger(__name__)


class ChatServiceStreamingFlowMixin:
        async def _run_message_flow(
            self,
            user_message: str,
            chunk_handler: Callable[[str], Awaitable[None]] | None = None,
            event_handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        ) -> ChatResponse:
            """Run the full chat flow, optionally streaming assistant chunks."""
            # Detect [[GENERATE_SUGGESTION]] marker â€” this means the user selected
            # an option button and the AI should generate concrete values first.
            # Strip the marker and skip save/apply flow interception.
            is_generate_request = bool(GENERATE_SUGGESTION_PATTERN.search(user_message or ""))
            logger.debug("[MSG_FLOW] is_generate_request=%s message=%s...", is_generate_request, (user_message or "")[:60])
            if is_generate_request:
                user_message = GENERATE_SUGGESTION_PATTERN.sub("", user_message).strip()

            skill_command_response = await self._maybe_handle_skill_command(
                user_message,
                chunk_handler=chunk_handler,
            )
            if skill_command_response is not None:
                self._schedule_history_summarization()
                return skill_command_response

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

            if not is_generate_request and self._product and _is_en_description_translation_request(cleaned_message):
                is_generate_request = True

            # Force SEO agent for generate requests â€” always an SEO content task
            if is_generate_request and agent_type != "seo":
                agent_type = "seo"

            # Ensure tool calling is allowed when we need to save/apply or generate suggestions
            if is_generate_request or has_apply_intent or has_save_intent:
                allow_tools = True

            runtime_skill_selection = self.resolve_message_skill_selection(
                cleaned_message,
                agent_type=agent_type,
                allow_tools=allow_tools,
            )
            self.set_runtime_skill_selection(runtime_skill_selection)
            store_memory_context = await self._build_store_memory_context(
                agent_type=agent_type,
                applies_to="chat",
            )
            store_memory_prompt = store_memory_context.prompt
            store_memory_log = store_memory_context.usage_log.model_dump(mode="json")

            # Add user message to history and trim if needed
            user_msg = ChatMessage(role="user", content=cleaned_message)
            self._history.append(user_msg)
            if len(self._history) > MAX_HISTORY_MESSAGES:
                self._history = self._history[-MAX_HISTORY_MESSAGES:]

            # Skip save/apply flow interception when the message is a generate
            # request â€” the AI needs to produce concrete values first.
            if not is_generate_request:
                single_save_response = await self._maybe_handle_single_product_save_flow(
                    cleaned_message,
                    chunk_handler=chunk_handler,
                )
                if single_save_response is not None:
                    self.set_runtime_skill_selection(None)
                    return single_save_response

                single_apply_response = await self._maybe_handle_single_product_apply_flow(
                    cleaned_message,
                    chunk_handler=chunk_handler,
                )
                if single_apply_response is not None:
                    self.set_runtime_skill_selection(None)
                    return single_apply_response

            # Optionally prefetch guided MCP data for live-data questions
            # Skip guided MCP for generate requests â€” the AI needs to produce
            # concrete SEO values via save_seo_suggestion, not summarise MCP data.
            guided_context = ""
            guided_tool_results: list[dict[str, Any]] = []
            guided_fallback = ""
            mcp_available = bool(self._mcp_initialized and self._mcp)
            if allow_tools and mcp_available and not is_generate_request:
                try:
                    guided_result = await self._maybe_run_guided_mcp_request(cleaned_message)
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
                        meta={
                            "model": "ikas MCP",
                            "finish_reason": "guided_mcp",
                            "source": "ikas_mcp",
                            "active_skill": self.get_effective_skill_payload(),
                            "store_memory": store_memory_log,
                        },
                        pending_suggestion=self._get_session_pending_suggestion(),
                    )
                    if chunk_handler and response.content:
                        await chunk_handler(response.content)
                    self._schedule_history_summarization()
                    self.set_runtime_skill_selection(None)
                    return response

            messages, tools = self._build_completion_messages(
                cleaned_message,
                routing_instruction,
                agent_type,
                allow_tools,
                guided_context,
                store_memory_prompt,
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
            previous_permission_rules = list(self._permission_runtime_rules)
            if has_apply_intent:
                self._permission_runtime_rules = [
                    *previous_permission_rules,
                    build_runtime_allow_rule(
                        "apply",
                        description="The user explicitly requested an apply action in this chat turn.",
                    ),
                ]

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
                        meta={
                            "model": "ikas MCP",
                            "finish_reason": "guided_mcp_fallback",
                            "source": "ikas_mcp",
                            "active_skill": self.get_effective_skill_payload(),
                            "store_memory": store_memory_log,
                        },
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
                        meta={
                            "active_skill": self.get_effective_skill_payload(),
                            "store_memory": store_memory_log,
                        },
                        pending_suggestion=pending_suggestion,
                    )
                if chunk_handler and response.content:
                    await chunk_handler(response.content)
                self._schedule_history_summarization()
                return response
            finally:
                self._permission_runtime_rules = previous_permission_rules
                self.set_runtime_skill_selection(None)

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

            meta = dict(meta)
            meta["active_skill"] = runtime_skill_selection.to_payload() or self.get_effective_skill_payload()
            meta["store_memory"] = store_memory_log

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
                "active_skill": response.meta.get("active_skill"),
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


        async def close(self) -> None:
            """Close MCP connection."""
            self.cancel_active_request()
            if self._mcp:
                await self._mcp.close()
                self._mcp = None
                self._mcp_initialized = False
