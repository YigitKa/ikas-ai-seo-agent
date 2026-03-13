"""Multi-turn conversational chat service with MCP tool integration."""

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


class ChatService:
    """Multi-turn chat service with optional MCP tool integration.

    Works with any OpenAI-compatible local model (Ollama, LM Studio)
    and can optionally use ikas MCP tools for real-time store data access.
    """

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
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        """Build the messages list and tools for the AI completion call."""
        system_prompt = _build_product_context(self._product, self._score, agent_type)
        if _should_request_structured_suggestion_options(cleaned_message):
            system_prompt = f"{system_prompt}\n\n{STRUCTURED_SUGGESTION_OPTIONS_INSTRUCTION}"

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if routing_instruction:
            messages.append({"role": "system", "content": routing_instruction})
        local_no_think_instruction = _build_local_no_think_instruction(self._config)
        if local_no_think_instruction:
            messages.append({"role": "system", "content": local_no_think_instruction})

        if allow_tools and mcp_available and guided_context:
            messages.append({
                "role": "system",
                "content": (
                    "Asagidaki ikas MCP sonucu dogrulanmis canli veridir. "
                    "Bu veriyi esas al, veri uydurma ve degistirme:\n"
                    f"{guided_context}"
                ),
            })
        elif allow_tools and not mcp_available:
            messages.append({
                "role": "system",
                "content": (
                    "ikas MCP su anda hazir degil. Canli veri cekemedigini acikca belirt "
                    "ve magaza verisi uydurma."
                ),
            })

        tools, tool_instructions = self._build_chat_tools(
            allow_mcp_tools=allow_tools,
            guided_context=guided_context,
            agent_type=agent_type,
            include_save_seo_tool=include_save_seo_tool,
        )
        for instruction in tool_instructions:
            messages.append({"role": "system", "content": instruction})

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

    async def _run_message_flow(
        self,
        user_message: str,
        chunk_handler: Callable[[str], Awaitable[None]] | None = None,
        event_handler: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> ChatResponse:
        """Run the full chat flow, optionally streaming assistant chunks."""
        cleaned_message, routing_instruction, agent_type, allow_tools = await self._extract_message_directives(user_message)
        has_apply_intent = _message_has_apply_intent(cleaned_message)

        # Add user message to history and trim if needed
        user_msg = ChatMessage(role="user", content=cleaned_message)
        self._history.append(user_msg)
        if len(self._history) > MAX_HISTORY_MESSAGES:
            self._history = self._history[-MAX_HISTORY_MESSAGES:]

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
        guided_context = ""
        guided_tool_results: list[dict[str, Any]] = []
        guided_fallback = ""
        mcp_available = bool(self._mcp_initialized and self._mcp)
        if allow_tools and mcp_available:
            try:
                guided_result = await self._maybe_run_guided_mcp_request()
            except Exception as exc:
                logger.warning("Guided MCP request failed: %s", exc)
                guided_result = None

            if guided_result:
                guided_context, guided_tool_results, guided_fallback = guided_result
                if not has_apply_intent:
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
            include_save_seo_tool=(agent_type == "seo" or has_apply_intent),
        )

        response_text = ""
        thinking_text = ""
        tool_results: list[dict[str, Any]] = list(guided_tool_results)
        meta: dict[str, Any] = {}
        suggestion_saved: dict[str, Any] | None = None
        pending_suggestion = self._get_session_pending_suggestion()

        try:
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

        async for event in self.async_stream_chat(messages, tools):
            event_type = str(event.get("type") or "")
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
        if self._config.ai_provider == "lm-studio":
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
