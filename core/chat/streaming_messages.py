from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from core.ai.requests import build_en_translation_request
from core.chat.support import (
    _build_local_no_think_instruction,
    _build_product_context,
    _build_save_seo_suggestion_tool,
    _is_en_description_translation_request,
    _should_request_structured_suggestion_options,
)
from core.models import ChatResponse
from core.prompt_store import compose_prompt_with_skill_layer, load_prompt_template


class ChatServiceStreamingMessagesMixin:
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
            active_skill_prompt = self._build_active_skill_system_prompt()
            system_parts: list[str] = [
                compose_prompt_with_skill_layer(
                    _build_product_context(self._product, self._score, agent_type, compact=compact),
                    active_skill_prompt,
                    "chat",
                ),
            ]
            if _should_request_structured_suggestion_options(cleaned_message):
                system_parts.append(load_prompt_template("chat_suggestion_options_system"))

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
                allowed_tool_names=self._get_active_skill_allowed_tools(),
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
            ``save_seo_suggestion`` tool â€” keeps the total under ~1 500 tokens
            so even 4 096-context models can handle it.

            When the user selected a specific field (e.g. "EN Aciklama"),
            the system prompt instructs the AI to fill ONLY that field.
            """
            if self._product and _is_en_description_translation_request(cleaned_message):
                translation_request = build_en_translation_request(
                    self._config,
                    self._config.ai_provider,
                    self._product,
                    extra_system_prompt=self._build_active_skill_system_prompt(),
                )
                return (
                    [
                        {"role": "system", "content": translation_request["system_prompt"]},
                        {
                            "role": "user",
                            "content": (
                                f"{translation_request['user_prompt']}\n\n"
                                f"Kullanici talebi: {cleaned_message}"
                            ),
                        },
                    ],
                    [_build_save_seo_suggestion_tool()],
                )

            product_lines: list[str] = []
            if self._product:
                p = self._product
                product_lines = [
                    f"Urun ID: {p.id}",
                    f"Urun: {p.name}",
                    f"Kategori: {p.category or '-'}",
                    f"Meta Title: {p.meta_title or '-'}",
                    f"Meta Description: {p.meta_description or '-'}",
                    f"Aciklama: {(p.description or '')[:2000]}",
                ]

            # Detect which field the user selected from the message content
            field_instruction = (
                "Kullanicinin sectigi ALAN icin somut SEO degeri olustur. "
                "YALNIZCA o alani save_seo_suggestion aracinda doldur, "
                "diger alanlari BOZ birak."
            )

            skill_prompt = self._build_active_skill_system_prompt()
            system_prompt = compose_prompt_with_skill_layer(
                (
                    "Sen SEO uzmansin. "
                    + field_instruction
                    + " Dusunme, dogrudan araci cagir. /no_think\n\n"
                    + "\n".join(product_lines)
                ),
                skill_prompt,
                "chat",
            )

            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": cleaned_message},
            ]

            tools: list[dict[str, Any]] = [_build_save_seo_suggestion_tool()]

            return messages, tools
