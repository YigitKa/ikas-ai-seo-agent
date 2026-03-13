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


class ChatServiceStateMixin:
        def __init__(self, config: AppConfig):
            self._config = config
            self._mcp: IkasMCPClient | None = None
            self._mcp_initialized = False
            self._history: list[ChatMessage] = []
            self._history_summary_lock = asyncio.Lock()
            self._product: Product | None = None
            self._score: SeoScore | None = None
            self._session_pending_suggestions: dict[str, SeoSuggestion] = {}
            self._total_tokens = {"input": 0, "output": 0}
            self._active_request_lock = threading.Lock()
            self._active_http_client: httpx.AsyncClient | None = None

            # Local tool registry — add new local tools here without touching _execute_chat_tool
            self._tool_registry = ToolRegistry()
            self._tool_registry.register(SAVE_SEO_SUGGESTION_TOOL_NAME, self._save_suggestion_from_tool_args)
            self._tool_registry.register("apply_seo_to_ikas", self._apply_seo_to_ikas_handler)

            # Agent toolkit — provides additional local tools (SEO scoring, validation, etc.)
            self._agent_toolkit: AgentToolkit = create_chat_toolkit()

        def _build_auth_headers(self) -> dict[str, str]:
            """Build auth headers for the current AI provider."""
            headers: dict[str, str] = {"Content-Type": "application/json"}
            api_key = self._config.ai_api_key
            if self._config.ai_provider == "anthropic" and api_key:
                headers["x-api-key"] = api_key
            elif api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            elif self._config.ai_provider in ("ollama", "lm-studio"):
                headers["Authorization"] = "Bearer ollama"
            return headers

        @property
        def has_mcp(self) -> bool:
            return bool(self._config.ikas_mcp_token)

        @property
        def mcp_initialized(self) -> bool:
            return self._mcp_initialized

        @property
        def history(self) -> list[ChatMessage]:
            return list(self._history)

        @property
        def total_tokens(self) -> dict[str, int]:
            return dict(self._total_tokens)

        @property
        def mcp_tool_count(self) -> int:
            return self._mcp.tool_count if self._mcp else 0

        @property
        def mcp_tools(self) -> list[dict[str, str]]:
            if not self._mcp:
                return []
            return self._mcp.get_tool_summaries()

        def set_product_context(self, product: Product | None, score: SeoScore | None = None) -> None:
            """Set the current product context for the conversation."""
            self._product = product
            self._score = score

        def clear_history(self) -> None:
            """Clear conversation history."""
            self._history.clear()
            self._session_pending_suggestions.clear()

        def _get_session_pending_suggestion(
            self,
            product_id: str | None = None,
        ) -> SeoSuggestion | None:
            product_key = product_id or (self._product.id if self._product else "")
            if not product_key:
                return None
            suggestion = self._session_pending_suggestions.get(product_key)
            return suggestion.model_copy(deep=True) if suggestion else None

        def _set_session_pending_suggestion(self, suggestion: SeoSuggestion) -> None:
            self._session_pending_suggestions[suggestion.product_id] = suggestion.model_copy(deep=True)

        def _clear_session_pending_suggestion(self, product_id: str | None = None) -> None:
            product_key = product_id or (self._product.id if self._product else "")
            if product_key:
                self._session_pending_suggestions.pop(product_key, None)

        async def _summarize_and_compress_history(self) -> None:
            async with self._history_summary_lock:
                if len(self._history) <= HISTORY_SUMMARY_TRIGGER_MESSAGES:
                    return

                messages_to_summarize = list(self._history[:-HISTORY_SUMMARY_KEEP_RECENT_MESSAGES])
                if not messages_to_summarize:
                    return

                history_block = "\n\n".join(
                    f"role: {msg.role}\ncontent: {msg.content}"
                    for msg in messages_to_summarize
                ).strip()
                if not history_block:
                    return

                base_url = self._get_base_url()
                model = self._config.ai_model_name or self._get_default_model()
                request_body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": MEMORY_SUMMARIZATION_PROMPT},
                        {"role": "user", "content": history_block},
                    ],
                    "temperature": 0.2,
                    "max_tokens": max(128, min(self._config.ai_max_tokens, 256)),
                    "stream": False,
                }
                timeout = (
                    httpx.Timeout(60.0, connect=10.0)
                    if self._config.ai_provider in ("ollama", "lm-studio")
                    else httpx.Timeout(30.0, connect=10.0)
                )
                headers = self._build_auth_headers()

                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            f"{base_url}/chat/completions",
                            json=request_body,
                            headers=headers,
                        )
                        response.raise_for_status()
                        payload = response.json()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.warning("History summarization failed", exc_info=True)
                    return

                summary = self._remove_thinking(_extract_chat_completion_content(payload)).strip()
                if not summary:
                    return

                current_history = list(self._history)
                summarized_count = len(messages_to_summarize)
                if len(current_history) < summarized_count:
                    return
                if current_history[:summarized_count] != messages_to_summarize:
                    return

                summary_message = ChatMessage(
                    role="system",
                    content=f"{HISTORY_SUMMARY_SYSTEM_PREFIX}{summary}",
                )
                self._history = [summary_message, *current_history[summarized_count:]]

        def _schedule_history_summarization(self) -> None:
            asyncio.create_task(self._summarize_and_compress_history())

        def cancel_active_request(self) -> bool:
            """Try to cancel the in-flight chat completion HTTP request."""
            with self._active_request_lock:
                client = self._active_http_client

            if client is None:
                return False

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return False

            loop.create_task(client.aclose())
            return True

        async def initialize_mcp(self) -> tuple[bool, str]:
            """Initialize MCP connection. Returns (success, message)."""
            if not self._config.ikas_mcp_token:
                return False, "MCP token ayarlanmamis. Ayarlar'dan ikas MCP token'i girin."

            try:
                self._mcp = IkasMCPClient(self._config.ikas_mcp_token)
                await self._mcp.initialize()
                await self._mcp.list_tools()
                self._mcp_initialized = True
                return True, f"MCP baglantisi basarili! {self._mcp.tool_count} operasyon hazir."
            except MCPError as exc:
                logger.error("MCP initialization failed: %s", exc)
                self._mcp_initialized = False
                return False, f"MCP hatasi: {exc}"
            except Exception as exc:
                logger.error("MCP connection failed: %s", exc)
                self._mcp_initialized = False
                return False, f"MCP baglanti hatasi: {exc}"

        async def _route_to_agent(self, user_message: str) -> str:
            cleaned_message = (user_message or "").strip()
            if not cleaned_message:
                return "general"

            base_url = self._get_base_url()
            model = self._config.ai_model_name or self._get_default_model()
            request_body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SEMANTIC_ROUTING_SYSTEM_PROMPT},
                    {"role": "user", "content": cleaned_message},
                ],
                "temperature": 0.0,
                "max_tokens": 20,
                "stream": False,
            }
            timeout = (
                httpx.Timeout(60.0, connect=10.0)
                if self._config.ai_provider in ("ollama", "lm-studio")
                else httpx.Timeout(30.0, connect=10.0)
            )
            headers = self._build_auth_headers()

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    with self._active_request_lock:
                        self._active_http_client = client
                    try:
                        response = await client.post(
                            f"{base_url}/chat/completions",
                            json=request_body,
                            headers=headers,
                        )
                        response.raise_for_status()
                        payload = response.json()
                    finally:
                        with self._active_request_lock:
                            if self._active_http_client is client:
                                self._active_http_client = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Semantic routing request failed, defaulting to general agent: %s", exc)
                return "general"

            completion_text = _extract_chat_completion_content(payload)
            agent_type = _parse_agent_type(completion_text)
            if agent_type is not None:
                return agent_type

            logger.warning("Semantic routing returned invalid payload, defaulting to general agent: %s", completion_text[:200])
            return "general"

        async def _extract_message_directives(
            self,
            user_message: str,
        ) -> tuple[str, str | None, str, bool]:
            """Route the message to the appropriate agent and build instructions."""
            cleaned_message = (user_message or "").strip()
            agent_type = await self._route_to_agent(user_message)
            allow_tools = agent_type == "operator"

            if allow_tools:
                return (
                    cleaned_message,
                    (
                        "Semantic routing bu mesaj icin canli magaza verisine "
                        "ihtiyac oldugunu tespit etti. "
                        "Mumkunse uygun araclarla canli veri cek. "
                        "Canli veri cekemiyorsan bunu acikca belirt. "
                        "Yanitta tavsiyeyi yine mevcut SEO problemi ve secili urun baglami etrafinda tut. "
                        "Kullanici sohbette onaylanmis SEO degisikliklerini 'uygula' veya 'kaydet' diyorsa "
                        "arka planda uygun araclari kullanarak taslak kaydet; sonra alan bazli onay sun. "
                        "ONEMLI: Yalnizca arac gercekten cagirilip basarili sonuc dondugunde islemi raporla. Arac cagirmadan 'guncelledim' deme. "
                        "Kullaniciya arac adi, MCP, GraphQL gibi teknik detaylari gosterme."
                    ),
                    agent_type,
                    True,
                )

            return (
                cleaned_message,
                (
                    "Semantic routing bu mesajin mevcut baglam ve SEO metin "
                    "yazarligi ile yanitlanabilecegini tespit etti. "
                    "Yalnizca mevcut SEO metrikleri, secili urunun promptta bulunan alanlari ve sohbet baglamina gore yanit ver. "
                    "Stok, fiyat, siparis, kampanya veya musteri verisi uydurma. "
                    "Kullanici urun aciklamasi, meta title veya meta description gibi mevcut alanlari yorumlamani isterse bunu local baglamla yap. "
                    "Kullanici sohbet sirasinda sunulan SEO onerilerini onaylarsa "
                    "arka planda uygun araclari kullanarak taslak kaydet. "
                    "Uygun oldugunda degisiklikleri once goster, onay al ve sadece secili urune uygula. "
                    "Kullaniciya arac adi, MCP, GraphQL gibi teknik detaylari gosterme."
                ),
                agent_type,
                False,
            )

        async def _maybe_run_guided_mcp_request(
            self,
        ) -> tuple[str, list[dict[str, Any]], str] | None:
            """Run a deterministic MCP query to fetch live product data (stock, price, variants).

            Called only when the Semantic Router has already determined that live MCP data is
            needed. Fetches a focused snapshot of the currently selected product from ikas.
            """
            if not self._product or not self._mcp or not self._mcp_initialized:
                return None

            result = await self._mcp.call_tool("listProduct", {
                "query": SELECTED_PRODUCT_LIVE_QUERY,
                "variables": {
                    "id": {"eq": self._product.id},
                    "pagination": {"limit": 1, "page": 1},
                },
            })

            payload = _extract_mcp_json_payload(result)
            list_product = payload.get("listProduct", {}) if isinstance(payload, dict) else {}
            items = list_product.get("data", []) if isinstance(list_product, dict) else []
            product_data = items[0] if isinstance(items, list) and items else None
            if not isinstance(product_data, dict):
                return None

            total_stock = product_data.get("totalStock")
            variants = product_data.get("variants", [])
            variant_lines: list[str] = []
            fallback_variant_lines: list[str] = []
            seen_prices: list[str] = []

            if isinstance(variants, list):
                for idx, variant in enumerate(variants[:8], start=1):
                    if not isinstance(variant, dict):
                        continue

                    sku = str(variant.get("sku") or "-")
                    stocks = variant.get("stocks", [])
                    prices = variant.get("prices", [])
                    stock_total = 0.0
                    has_stock = False

                    if isinstance(stocks, list):
                        for stock in stocks:
                            if isinstance(stock, dict) and isinstance(stock.get("stockCount"), (int, float)):
                                stock_total += float(stock["stockCount"])
                                has_stock = True

                    price_summary = "-"
                    if isinstance(prices, list) and prices:
                        formatted_prices = [
                            _format_money(price)
                            for price in prices
                            if isinstance(price, dict)
                        ]
                        formatted_prices = [price for price in formatted_prices if price and price != "-"]
                        if formatted_prices:
                            price_summary = ", ".join(formatted_prices[:2])
                            seen_prices.extend(formatted_prices[:2])

                    stock_summary = _format_decimal(stock_total) if has_stock else "-"
                    variant_lines.append(
                        f"- Varyant {idx}: sku={sku}, stok={stock_summary}, fiyat={price_summary}"
                    )
                    fallback_variant_lines.append(
                        f"Varyant {idx}: SKU {sku}, stok {stock_summary}, fiyat {price_summary}"
                    )

            price_summary = ", ".join(dict.fromkeys(seen_prices)) if seen_prices else "-"
            stock_summary = _format_decimal(total_stock)

            context_lines = [
                "ikas MCP ile dogrulanmis secili urun canli verisi:",
                f"- Urun: {product_data.get('name') or self._product.name}",
                f"- Urun ID: {product_data.get('id') or self._product.id}",
                f"- Toplam stok: {stock_summary}",
                f"- Varyant sayisi: {len(variants) if isinstance(variants, list) else 0}",
                f"- Fiyat ozeti: {price_summary}",
            ]
            if isinstance(total_stock, (int, float)) and float(total_stock) == -1:
                context_lines.append(
                    "- Not: MCP toplam stok degerini -1 dondurdu. Bu genelde stok takibinin kapali veya limitsiz satis anlamina gelebilir."
                )
            context_lines.extend(variant_lines)

            fallback_lines = [
                "**Durum**",
                f"- Urun: {product_data.get('name') or self._product.name}",
                f"- Toplam stok: {stock_summary}",
            ]
            if isinstance(total_stock, (int, float)) and float(total_stock) == -1:
                fallback_lines.append(
                    "- MCP `totalStock = -1` dondurdu. Bu deger genelde stok takibinin kapali veya varyantin limitsiz satisa acik olduguna isaret eder."
                )
            if price_summary != "-":
                fallback_lines.append(f"- Fiyat ozeti: {price_summary}")
            if fallback_variant_lines:
                fallback_lines.append(f"- Varyant ozeti: {' | '.join(fallback_variant_lines[:4])}")

            fallback_lines.append("")
            fallback_lines.append("**Not**")
            fallback_lines.append("- Bu cevap dogrudan ikas MCP canli verisine dayanir.")

            return (
                "\n".join(context_lines),
                [{
                    "tool": "listProduct",
                    "arguments": {
                        "id": self._product.id,
                        "mode": "selected_product_live_data",
                    },
                    "result": _extract_mcp_text(result)[:2000],
                }],
                "\n".join(fallback_lines),
            )

        def _build_chat_tools(
            self,
            *,
            allow_mcp_tools: bool,
            guided_context: str,
            agent_type: str,
            include_save_seo_tool: bool,
        ) -> tuple[list[dict[str, Any]] | None, list[str]]:
            tools: list[dict[str, Any]] = []
            instructions: list[str] = []

            if include_save_seo_tool:
                tools.append(_build_save_seo_suggestion_tool())
                instructions.append(SAVE_SEO_SUGGESTION_TOOL_INSTRUCTION)

            # Always include the apply_seo_to_ikas tool — it handles both
            # native ikas API and MCP routes internally so the LLM never
            # needs to write raw GraphQL mutations.
            tools.append(_build_apply_seo_to_ikas_tool())
            instructions.append(
                "Kullanici urun degisikliklerini onayladiginda, arka planda uygun araclari cagir. "
                "Kullaniciya arac adlarini gosterme; onay aldiktan sonra sessizce uygula."
            )

            # Add agent toolkit tools (SEO scoring, product details, validation, etc.)
            tools.extend(self._agent_toolkit.get_openai_functions())

            if allow_mcp_tools and self._mcp_initialized and self._mcp and not guided_context:
                tools.extend(self._mcp.get_tools_as_openai_functions())
                tool_catalog_instruction = _build_tool_catalog_instruction(self.mcp_tools)
                if tool_catalog_instruction:
                    instructions.append(tool_catalog_instruction)

            return (tools or None), instructions
