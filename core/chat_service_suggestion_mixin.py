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

from core.agent_tools import AgentToolkit, create_chat_toolkit
from core.chat_service_support import (
    APPLY_INTENT_EXTRACTION_SYSTEM_PROMPT,
    APPLY_SEO_TO_IKAS_TOOL_NAME,
    CHAT_ACTION_PATTERN,
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
    _message_has_apply_intent,
    _message_has_save_intent,
    _merge_stream_meta_payload,
    _normalize_matching_text,
    _operation_footer_already_present,
    _parse_agent_type,
    _should_request_structured_suggestion_options,
)
from core.ikas_client import IkasClient
from core.models import AppConfig, ChatMessage, ChatResponse, Product, SeoScore, SeoSuggestion
from core.mcp_client import IkasMCPClient, MCPError

logger = logging.getLogger(__name__)


class ChatServiceSuggestionMixin:
        async def _save_suggestion_from_tool_args(
            self,
            args: dict[str, Any],
        ) -> tuple[str, dict[str, Any] | None]:
            from core.suggestion_service import apply_suggestion_field, create_pending_suggestion

            if not self._product:
                return json.dumps({
                    "ok": False,
                    "error": "Secili urun olmadan oneri kaydedilemez.",
                }, ensure_ascii=False), None

            suggestion = self._get_session_pending_suggestion(self._product.id) or create_pending_suggestion(self._product)
            saved_fields: dict[str, str] = {}

            for arg_key, (field_name, attr_name) in SAVE_SEO_SUGGESTION_FIELD_MAP.items():
                raw_value = args.get(arg_key)
                if not isinstance(raw_value, str) or not raw_value.strip():
                    continue

                apply_suggestion_field(suggestion, field_name, raw_value)
                cleaned_value = getattr(suggestion, attr_name, "") or ""
                if isinstance(cleaned_value, str) and cleaned_value.strip():
                    saved_fields[arg_key] = cleaned_value

            if not saved_fields:
                return json.dumps({
                    "ok": False,
                    "error": "Kaydedilecek gecerli bir SEO onerisi bulunamadi.",
                }, ensure_ascii=False), None

            self._set_session_pending_suggestion(suggestion)
            suggestion_saved = {
                "product_id": self._product.id,
                "product_name": self._product.name,
                "fields": saved_fields,
            }
            return json.dumps({
                "ok": True,
                "message": SUGGESTION_SAVE_SUCCESS_MESSAGE,
                "suggestion_saved": suggestion_saved,
            }, ensure_ascii=False), suggestion_saved

        async def _apply_seo_to_ikas_handler(
            self,
            args: dict[str, Any],
        ) -> tuple[str, dict[str, Any] | None]:
            """Apply SEO changes to ikas via IkasClient or MCP.

            This tool gives the LLM a structured way to update product fields
            without requiring raw GraphQL knowledge.  It tries the native
            IkasClient first (needs OAuth credentials) and falls back to MCP.
            """
            product_id = args.get("product_id", "")
            if not product_id:
                if self._product:
                    product_id = self._product.id
                else:
                    return json.dumps({
                        "ok": False,
                        "error": "product_id gerekli ama sağlanmadı ve seçili ürün yok.",
                    }, ensure_ascii=False), None

            # Build the update dict from provided fields
            updates: dict[str, Any] = {}
            description_translations: dict[str, str] = {}

            if args.get("name"):
                updates["name"] = args["name"]
            if args.get("meta_title"):
                updates["meta_title"] = args["meta_title"]
            if args.get("meta_description"):
                updates["meta_description"] = args["meta_description"]
            if args.get("description"):
                updates["description"] = args["description"]
                description_translations["tr"] = args["description"]
            if args.get("description_en"):
                description_translations["en"] = args["description_en"]
            if description_translations:
                updates["description_translations"] = description_translations

            if not updates:
                return json.dumps({
                    "ok": False,
                    "error": "Güncellenecek alan belirtilmedi.",
                }, ensure_ascii=False), None

            updated_fields = list(updates.keys())

            # Strategy 1: Try IkasClient (needs IKAS_CLIENT_ID + SECRET)
            ikas_client_available = bool(
                self._config.ikas_client_id and self._config.ikas_client_secret
            )
            if ikas_client_available:
                ikas_client = IkasClient()
                try:
                    await ikas_client.update_product(product_id, updates)
                    result = {
                        "ok": True,
                        "method": "ikas_api",
                        "product_id": product_id,
                        "updated_fields": updated_fields,
                        "dry_run": self._config.dry_run,
                        "message": (
                            f"Ürün başarıyla güncellendi (alanlar: {', '.join(updated_fields)})."
                            if not self._config.dry_run
                            else f"DRY_RUN: Güncelleme simüle edildi (alanlar: {', '.join(updated_fields)})."
                        ),
                    }
                    return json.dumps(result, ensure_ascii=False), None
                except Exception as exc:
                    logger.warning("IkasClient update failed, trying MCP: %s", exc)
                finally:
                    with contextlib.suppress(Exception):
                        await ikas_client.close()

            # Strategy 2: Use MCP updateProduct mutation
            if self._mcp and self._mcp_initialized:
                try:
                    input_data: dict[str, Any] = {"id": product_id}
                    if "name" in updates:
                        input_data["name"] = updates["name"]
                    if "description" in updates:
                        input_data["description"] = updates["description"]
                    if "meta_title" in updates or "meta_description" in updates:
                        meta_data: dict[str, Any] = {}
                        if "meta_title" in updates:
                            meta_data["pageTitle"] = updates["meta_title"]
                        if "meta_description" in updates:
                            meta_data["description"] = updates["meta_description"]
                        input_data["metaData"] = meta_data
                    if description_translations:
                        input_data["translations"] = [
                            {"locale": locale, "description": text}
                            for locale, text in description_translations.items()
                            if isinstance(text, str) and text.strip()
                        ]

                    result = await self._mcp.execute_mutation(
                        "saveProduct",
                        _MCP_SAVE_PRODUCT_MUTATION,
                        {"input": input_data},
                    )
                    return json.dumps({
                        "ok": True,
                        "method": "mcp",
                        "product_id": product_id,
                        "updated_fields": updated_fields,
                        "result": _extract_mcp_text(result)[:2000] if isinstance(result, dict) else str(result)[:2000],
                        "message": f"Ürün MCP üzerinden güncellendi (alanlar: {', '.join(updated_fields)}).",
                    }, ensure_ascii=False), None
                except Exception as exc:
                    logger.error("MCP update also failed: %s", exc)
                    return json.dumps({
                        "ok": False,
                        "error": f"Güncelleme başarısız. ikas API hatası: {exc}",
                        "tried": ["ikas_api", "mcp"] if ikas_client_available else ["mcp"],
                    }, ensure_ascii=False), None

            return json.dumps({
                "ok": False,
                "error": (
                    "Ürün güncellemesi yapılamadı. Ne ikas API kimlik bilgileri "
                    "(IKAS_CLIENT_ID/SECRET) ne de MCP bağlantısı mevcut."
                ),
            }, ensure_ascii=False), None

        async def _extract_pending_suggestion_from_history(
            self,
            cleaned_message: str,
        ) -> tuple[dict[str, Any] | None, str]:
            if not self._product:
                return None, ""

            recent_history = [
                msg for msg in self._history
                if msg.role in {"user", "assistant"} and msg.content.strip()
            ][-8:]
            if not recent_history:
                return None, ""

            deterministic_fields: dict[str, str] = {}
            for msg in reversed(recent_history):
                if msg.role != "assistant":
                    continue
                extracted_fields = _extract_suggestion_fields_from_text(msg.content)
                for field_name, value in extracted_fields.items():
                    deterministic_fields.setdefault(field_name, value)

            if deterministic_fields:
                _, suggestion_saved = await self._save_suggestion_from_tool_args(deterministic_fields)
                if suggestion_saved:
                    return suggestion_saved, ""

            messages: list[dict[str, Any]] = [{
                "role": "system",
                "content": APPLY_INTENT_EXTRACTION_SYSTEM_PROMPT,
            }]
            local_no_think_instruction = _build_local_no_think_instruction(self._config)
            if local_no_think_instruction:
                messages.append({"role": "system", "content": local_no_think_instruction})
            messages.append({
                "role": "system",
                "content": (
                    f"Secili urun: {self._product.name} (ID: {self._product.id}). "
                    f"Son kullanici mesaji: {cleaned_message}"
                ),
            })
            for msg in recent_history:
                messages.append({"role": msg.role, "content": msg.content})

            response_text, _, tool_results, _, suggestion_saved = self._normalize_completion_result(
                await self._chat_completion(messages, [_build_save_seo_suggestion_tool()])
            )

            if suggestion_saved:
                return suggestion_saved, ""

            # Safety net: if the LLM output JSON with suggestion fields as plain
            # text instead of calling the tool, parse and save programmatically.
            if response_text:
                fallback_fields = _extract_suggestion_fields_from_text(response_text)
                if fallback_fields:
                    _, fallback_saved = await self._save_suggestion_from_tool_args(fallback_fields)
                    if fallback_saved:
                        return fallback_saved, ""

            return None, (response_text or "").strip()

        @staticmethod
        def _collect_applicable_suggestion_fields(suggestion: SeoSuggestion) -> dict[str, str]:
            available_fields: dict[str, str] = {}
            for field_name in SUGGESTION_APPLY_FIELD_CONFIG:
                value = getattr(suggestion, field_name, None)
                if isinstance(value, str):
                    cleaned = value.strip()
                elif value is None:
                    cleaned = ""
                else:
                    cleaned = str(value).strip()
                if cleaned:
                    available_fields[field_name] = cleaned
            return available_fields

        @staticmethod
        def _resolve_apply_action_fields(action: str, available_fields: dict[str, str]) -> list[str]:
            all_fields = [field for field in SUGGESTION_APPLY_FIELD_CONFIG if field in available_fields]
            meta_fields = [field for field in ("suggested_meta_title", "suggested_meta_description") if field in available_fields]
            content_fields = [
                field for field in ("suggested_name", "suggested_description", "suggested_description_en")
                if field in available_fields
            ]

            if action == "single_apply_meta":
                return meta_fields
            if action == "single_apply_content":
                return content_fields
            if action == "single_apply_meta_content":
                return list(dict.fromkeys([*meta_fields, *content_fields]))
            if action == "single_apply_all":
                return all_fields
            return []

        def _build_single_apply_confirmation_response(
            self,
            suggestion: SeoSuggestion,
            available_fields: dict[str, str],
        ) -> str:
            product_label = (self._product.name if self._product else suggestion.product_id).strip()
            lines = [
                "**Uygulanacak Degisiklikler (Secili Urun)**",
                f"- Urun: {product_label}",
                "",
            ]

            for field_name in SUGGESTION_APPLY_FIELD_CONFIG:
                if field_name not in available_fields:
                    continue

                config = SUGGESTION_APPLY_FIELD_CONFIG[field_name]
                original_value = _compact_preview_text(str(getattr(suggestion, config["original_attr"], "") or ""))
                suggested_value = _compact_preview_text(available_fields[field_name])
                lines.extend([
                    f"- **{config['label']}**",
                    f"  - Mevcut: `{original_value}`",
                    f"  - Uygulanacak: `{suggested_value}`",
                ])

            lines.extend([
                "",
                "**Ne yapmak istersiniz?**",
            ])

            meta_fields = [field for field in ("suggested_meta_title", "suggested_meta_description") if field in available_fields]
            content_fields = [
                field for field in ("suggested_name", "suggested_description", "suggested_description_en")
                if field in available_fields
            ]
            options: list[dict[str, str]] = []
            if meta_fields:
                options.append({
                    "tone": "Meta",
                    "value": "Sadece Meta Title ve Meta Description'i guncelle.",
                    "action": "single_apply_meta",
                })
            if content_fields:
                options.append({
                    "tone": "Icerik",
                    "value": "Sadece icerik alanlarini (ad, aciklama, ceviri) guncelle.",
                    "action": "single_apply_content",
                })
            if meta_fields and content_fields:
                options.append({
                    "tone": "Hepsini Birlikte",
                    "value": "Meta ve icerik alanlarini birlikte guncelle.",
                    "action": "single_apply_meta_content",
                })
            options.append({
                "tone": "Tum Alanlar",
                "value": "Tum onerilen degisiklikleri uygula.",
                "action": "single_apply_all",
            })
            options.append({
                "tone": "Iptal",
                "value": "Simdilik bir sey yapma, vazgeciyorum.",
                "action": "single_apply_cancel",
            })

            lines.extend([
                "```json",
                json.dumps(options, ensure_ascii=False),
                "```",
            ])
            return "\n".join(lines)

        def _build_suggestion_saved_response(
            self,
            suggestion_saved: dict[str, Any],
        ) -> str:
            saved_fields = suggestion_saved.get("fields", {})
            field_labels = [
                SUGGESTION_APPLY_FIELD_CONFIG[field_name]["label"]
                for field_name in saved_fields
                if field_name in SUGGESTION_APPLY_FIELD_CONFIG
            ]
            lines = ["Bekleyen SEO degisiklikleri kaydedildi."]
            if field_labels:
                lines.append(f"- Kaydedilen alanlar: {', '.join(field_labels)}")
            lines.append("- Bu taslak sadece mevcut chat oturumunda tutulur.")

            options: list[dict[str, str]] = [
                {
                    "tone": "Uygula",
                    "value": "Bu degisiklikleri ikas'a uygula.",
                    "action": "single_apply_all",
                },
                {
                    "tone": "Detayli Sec",
                    "value": "Hangi alanlarin uygulanacagini secelim.",
                    "action": "single_apply_confirm",
                },
                {
                    "tone": "Iptal",
                    "value": "Simdilik bir sey yapma.",
                    "action": "single_apply_cancel",
                },
            ]
            lines.extend([
                "",
                "```json",
                json.dumps(options, ensure_ascii=False),
                "```",
            ])
            return "\n".join(lines)

        async def _maybe_handle_single_product_save_flow(
            self,
            cleaned_message: str,
            chunk_handler: Callable[[str], Awaitable[None]] | None = None,
        ) -> ChatResponse | None:
            if not self._product:
                return None

            has_save_intent = _message_has_save_intent(cleaned_message)
            has_apply_intent = _message_has_apply_intent(cleaned_message)
            if not has_save_intent or has_apply_intent:
                return None

            suggestion_saved, extraction_note = await self._extract_pending_suggestion_from_history(cleaned_message)
            if suggestion_saved:
                response_text = self._build_suggestion_saved_response(suggestion_saved)
                self._history.append(ChatMessage(role="assistant", content=response_text))
                self._schedule_history_summarization()
                response = ChatResponse(
                    content=response_text,
                    thinking="",
                    tool_results=[],
                    error=False,
                    meta={
                        "model": "ikas-chat-flow",
                        "finish_reason": "single_product_save_flow",
                    },
                    suggestion_saved=suggestion_saved,
                    pending_suggestion=self._get_session_pending_suggestion(),
                )
                if chunk_handler and response.content:
                    await chunk_handler(response.content)
                return response

            pending_suggestion = self._get_session_pending_suggestion()
            if pending_suggestion and self._collect_applicable_suggestion_fields(pending_suggestion):
                response_text = (
                    "Bu urun icin zaten bekleyen bir SEO taslagi var. "
                    "'Uygula' veya 'kaydet' diyerek onay adimindan devam edebilirsin."
                )
            else:
                response_text = (
                    extraction_note
                    or "Sohbet gecmisinde kaydedilecek net bir SEO taslagi bulamadim. "
                    "Once urun adi, meta title veya meta description icin net nihai oneriyi olusturalim."
                )

            self._history.append(ChatMessage(role="assistant", content=response_text))
            self._schedule_history_summarization()
            response = ChatResponse(
                content=response_text,
                thinking="",
                tool_results=[],
                error=False,
                meta={
                    "model": "ikas-chat-flow",
                    "finish_reason": "single_product_save_flow_no_suggestion",
                },
                pending_suggestion=pending_suggestion,
            )
            if chunk_handler and response.content:
                await chunk_handler(response.content)
            return response

        async def _apply_pending_suggestion_action(
            self,
            suggestion: SeoSuggestion,
            action: str,
            action_payload: str | None = None,
        ) -> tuple[str, list[dict[str, Any]], SeoSuggestion | None]:
            available_fields = self._collect_applicable_suggestion_fields(suggestion)
            if not available_fields:
                return (
                    "Secili urun icin uygulanabilir bekleyen taslak alani bulunamadi. "
                    "Once yeni bir SEO onerisi olusturalim.",
                    [],
                    None,
                )

            if action == "single_apply_cancel":
                self._clear_session_pending_suggestion(suggestion.product_id)
                return (
                    "Uygulama adimi iptal edildi. Hazir oldugunda tekrar onay verebilirsin.",
                    [],
                    None,
                )

            if action == "single_apply_confirm":
                return (
                    self._build_single_apply_confirmation_response(suggestion, available_fields),
                    [],
                    self._get_session_pending_suggestion(suggestion.product_id),
                )

            # Review step: return suggestion for user review in diff modal
            if action in ("single_apply_meta", "single_apply_content", "single_apply_meta_content", "single_apply_all"):
                selected_fields = self._resolve_apply_action_fields(action, available_fields)
                if not selected_fields:
                    return (
                        "Bu secenek icin uygun alan bulunamadi. Lutfen asagidaki guncel seceneklerden birini sec.\n\n"
                        + self._build_single_apply_confirmation_response(suggestion, available_fields),
                        [],
                        self._get_session_pending_suggestion(suggestion.product_id),
                    )

                suggestion.status = "pending_review"
                self._set_session_pending_suggestion(suggestion)

                selected_labels = [
                    SUGGESTION_APPLY_FIELD_CONFIG[f]["label"]
                    for f in selected_fields
                    if f in SUGGESTION_APPLY_FIELD_CONFIG
                ]
                response_text = (
                    f"Degisiklik onerisi hazirlandi. Incelemeniz icin {', '.join(selected_labels)} "
                    "alanlarinin eski ve yeni degerlerini gosteriyorum.\n\n"
                    "Onay verdiginizde ikas'a uygulanacak."
                )
                return (
                    response_text,
                    [],
                    suggestion,
                )

            # Execute step: apply with optional edits from the diff modal
            if action == "single_apply_execute":
                return await self._execute_apply(suggestion, available_fields, action_payload)

            selected_fields = self._resolve_apply_action_fields(action, available_fields)
            if not selected_fields:
                return (
                    "Bu secenek icin uygun alan bulunamadi. Lutfen asagidaki guncel seceneklerden birini sec.\n\n"
                    + self._build_single_apply_confirmation_response(suggestion, available_fields),
                    [],
                    self._get_session_pending_suggestion(suggestion.product_id),
                )

            return await self._execute_apply(suggestion, available_fields, action_payload, selected_fields)

        async def _execute_apply(
            self,
            suggestion: SeoSuggestion,
            available_fields: dict[str, str],
            action_payload: str | None = None,
            selected_fields: list[str] | None = None,
        ) -> tuple[str, list[dict[str, Any]], SeoSuggestion | None]:
            """Actually apply the suggestion to ikas, optionally applying user edits first."""
            # Apply edits from the diff modal if provided
            if action_payload:
                try:
                    payload_data = json.loads(action_payload)
                    edits = payload_data.get("edits", {})
                    real_action = payload_data.get("action", "single_apply_all")
                    for field_name, value in edits.items():
                        if field_name in SUGGESTION_APPLY_FIELD_CONFIG and value is not None:
                            setattr(suggestion, field_name, value)
                    # Re-collect available fields after edits
                    available_fields = self._collect_applicable_suggestion_fields(suggestion)
                    if selected_fields is None:
                        selected_fields = self._resolve_apply_action_fields(real_action, available_fields)
                except (json.JSONDecodeError, KeyError, AttributeError) as exc:
                    logger.warning("Failed to parse apply payload: %s", exc)

            if selected_fields is None:
                selected_fields = list(available_fields.keys())

            updates: dict[str, Any] = {}
            description_translations: dict[str, str] = {}
            selected_labels: list[str] = []

            for field_name in selected_fields:
                value = available_fields.get(field_name, "")
                if not value:
                    continue

                field_config = SUGGESTION_APPLY_FIELD_CONFIG[field_name]
                selected_labels.append(field_config["label"])
                update_key = field_config["update_key"]

                if update_key == "name":
                    updates["name"] = value
                elif update_key == "meta_title":
                    updates["meta_title"] = value
                elif update_key == "meta_description":
                    updates["meta_description"] = value
                elif update_key == "description":
                    updates["description"] = value
                    description_translations["tr"] = value
                elif update_key == "description_en":
                    description_translations["en"] = value

            if description_translations:
                updates["description_translations"] = description_translations

            if not updates:
                return (
                    "Secilen alanda gecerli bir icerik bulunamadi. "
                    "Lutfen once guncel bir oneriyi kaydedelim.",
                    [],
                    self._get_session_pending_suggestion(suggestion.product_id),
                )

            ikas_client = IkasClient()
            try:
                await ikas_client.update_product(suggestion.product_id, updates)
            except Exception as exc:
                logger.error("Chat single-product apply failed: %s", exc)
                return (
                    "ikas uygulama adimi basarisiz oldu. Hata: "
                    f"{exc}\n\nLutfen secenekleri gozden gecirip tekrar dene.\n\n"
                    + self._build_single_apply_confirmation_response(suggestion, available_fields),
                    [],
                    self._get_session_pending_suggestion(suggestion.product_id),
                )
            finally:
                with contextlib.suppress(Exception):
                    await ikas_client.close()

            # Verify by re-reading from ikas
            verification_note = ""
            try:
                ikas_verify = IkasClient()
                try:
                    products = await ikas_verify.fetch_products()
                    verified_product = next(
                        (p for p in products if p.id == suggestion.product_id), None
                    )
                    if verified_product:
                        verification_lines = ["", "**Dogrulama (ikas canli veri):**"]
                        if "meta_title" in updates and verified_product.meta_title:
                            verification_lines.append(f"- Meta Title: `{verified_product.meta_title}`")
                        if "meta_description" in updates and verified_product.meta_description:
                            verification_lines.append(f"- Meta Desc: `{verified_product.meta_description}`")
                        if "name" in updates:
                            verification_lines.append(f"- Urun Adi: `{verified_product.name}`")
                        if len(verification_lines) > 2:
                            verification_note = "\n".join(verification_lines)
                finally:
                    with contextlib.suppress(Exception):
                        await ikas_verify.close()
            except Exception as exc:
                logger.warning("Post-apply verification failed: %s", exc)
                verification_note = "\n\n⚠️ Dogrulama sirasinda hata olustu, ancak degisiklikler gonderildi."

            for field_name in selected_fields:
                if field_name == "suggested_name":
                    setattr(suggestion, field_name, None)
                else:
                    setattr(suggestion, field_name, "")

            remaining_fields = self._collect_applicable_suggestion_fields(suggestion)
            suggestion.status = "pending" if remaining_fields else "applied"
            if remaining_fields:
                self._set_session_pending_suggestion(suggestion)
            else:
                self._clear_session_pending_suggestion(suggestion.product_id)

            tool_result = {
                "tool": "chat_single_product_apply",
                "arguments": {
                    "action": "single_apply_execute",
                    "fields": selected_fields,
                },
                "result": json.dumps(
                    {"ok": True, "updates": updates, "remaining_fields": list(remaining_fields.keys())},
                    ensure_ascii=False,
                ),
            }

            response_lines = [
                "✅ Degisiklikler secili urun icin ikas'a gonderildi.",
                f"- Uygulanan alanlar: {', '.join(selected_labels)}",
            ]
            if self._config.dry_run:
                response_lines.append("- Not: DRY_RUN acik. Bu adim simule edildi, ikas'a yazilmadi.")

            if verification_note:
                response_lines.append(verification_note)

            if remaining_fields:
                response_lines.extend([
                    "",
                    f"Kalan taslak alanlar: {', '.join(SUGGESTION_APPLY_FIELD_CONFIG[field]['label'] for field in remaining_fields)}",
                    "Kalanlari da uygulamak istersen asagidaki seceneklerden birini sec.",
                    "",
                    self._build_single_apply_confirmation_response(suggestion, remaining_fields),
                ])
            else:
                response_lines.append("\n- Bu urun icin bekleyen taslak kalmadi.")

            return (
                "\n".join(response_lines),
                [tool_result],
                self._get_session_pending_suggestion(suggestion.product_id),
            )

        async def _maybe_handle_single_product_apply_flow(
            self,
            cleaned_message: str,
            chunk_handler: Callable[[str], Awaitable[None]] | None = None,
        ) -> ChatResponse | None:
            if not self._product:
                return None

            normalized_text = _normalize_matching_text(cleaned_message)
            action = _extract_chat_action(cleaned_message) or _detect_manual_apply_action(normalized_text)
            has_apply_intent = _message_has_apply_intent(cleaned_message)

            pending_suggestion = self._get_session_pending_suggestion()
            if not pending_suggestion and has_apply_intent:
                suggestion_saved, extraction_note = await self._extract_pending_suggestion_from_history(cleaned_message)
                if suggestion_saved:
                    pending_suggestion = self._get_session_pending_suggestion()
                else:
                    response_text = (
                        extraction_note
                        or "Sohbet gecmisinde uygulanacak net bir SEO taslagi bulamadim. "
                        "Once urun adi, meta title, meta description veya aciklama icin net oneriyi olusturalim."
                    )
                    self._history.append(ChatMessage(role="assistant", content=response_text))
                    self._schedule_history_summarization()
                    response = ChatResponse(
                        content=response_text,
                        thinking="",
                        tool_results=[],
                        error=False,
                        meta={
                            "model": "ikas-chat-flow",
                            "finish_reason": "apply_intent_missing_suggestion",
                        },
                        pending_suggestion=None,
                    )
                    if chunk_handler and response.content:
                        await chunk_handler(response.content)
                    return response
            if not pending_suggestion:
                return None

            available_fields = self._collect_applicable_suggestion_fields(pending_suggestion)
            if not available_fields:
                return None

            if action and action not in SINGLE_PRODUCT_APPLY_ACTIONS:
                return None
            if not action and not has_apply_intent:
                return None

            if action:
                action_payload = _extract_chat_action_payload(cleaned_message)
                response_text, tool_results, pending_suggestion = await self._apply_pending_suggestion_action(
                    pending_suggestion,
                    action,
                    action_payload=action_payload,
                )
            else:
                response_text = self._build_single_apply_confirmation_response(
                    pending_suggestion,
                    available_fields,
                )
                tool_results = []

            self._history.append(ChatMessage(role="assistant", content=response_text))
            self._schedule_history_summarization()

            response = ChatResponse(
                content=response_text,
                thinking="",
                tool_results=tool_results,
                error=False,
                meta={
                    "model": "ikas-chat-flow",
                    "finish_reason": "single_product_apply_flow",
                },
                pending_suggestion=pending_suggestion,
            )
            if chunk_handler and response.content:
                await chunk_handler(response.content)
            return response

        async def _execute_chat_tool(
            self,
            tool_name: str,
            args: dict[str, Any],
        ) -> tuple[str, dict[str, Any] | None]:
            # Check the local registry first (Open-Closed: new tools registered, not hardcoded)
            handler = self._tool_registry.get(tool_name)
            if handler:
                return await handler(args)

            # Check the agent toolkit (SEO scoring, validation, product details, etc.)
            if tool_name in self._agent_toolkit:
                result = await self._agent_toolkit.execute(tool_name, args)
                return result, None

            # Fall through to MCP for all dynamically-discovered ikas tools
            if self._mcp and self._mcp_initialized:
                try:
                    result = await self._mcp.call_tool(tool_name, args)
                    return json.dumps(result, ensure_ascii=False, indent=2), None
                except Exception as exc:
                    return json.dumps({
                        "error": str(exc),
                        "available_tools": self._mcp.get_tool_names(),
                    }, ensure_ascii=False), None

            available = self._tool_registry.local_tool_names + self._agent_toolkit.tool_names
            return json.dumps({
                "error": f"Tool '{tool_name}' is not available.",
                "available_tools": available,
            }, ensure_ascii=False), None
