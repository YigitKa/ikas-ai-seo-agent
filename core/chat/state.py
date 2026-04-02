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

from core.agent.tools import AgentToolkit, create_chat_toolkit, create_local_chat_tool_registry
from core.chat.support import (
    APPLY_SEO_TO_IKAS_TOOL_NAME,
    CHAT_ACTION_PATTERN,
    HISTORY_SUMMARY_KEEP_RECENT_MESSAGES,
    HISTORY_SUMMARY_TRIGGER_MESSAGES,
    MAX_HISTORY_MESSAGES,
    MAX_TOOL_ROUNDS,
    SAVE_INTENT_PATTERN,
    SAVE_SEO_SUGGESTION_FIELD_MAP,
    SAVE_SEO_SUGGESTION_TOOL_NAME,
    SELECTED_PRODUCT_LIVE_QUERY,
    SEMANTIC_ROUTING_JSON_PATTERN,
    SINGLE_PRODUCT_APPLY_ACTIONS,
    SUGGESTION_APPLY_FIELD_CONFIG,
    SUGGESTION_SAVE_SUCCESS_MESSAGE,
    SUGGESTION_REQUEST_HINT_PATTERN,
    _LMStudioNativeUnavailable,
    _StreamingVisibleTextFilter,
    _append_false_action_disclaimer,
    _append_operation_suggestion,
    _apply_choice_delta,
    _build_completion_meta,
    _build_local_no_think_instruction,
    _build_product_context,
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
    _get_apply_extraction_prompt,
    _get_history_summary_prefix,
    _get_memory_summarization_prompt,
    _get_save_tool_instruction,
    _get_semantic_routing_prompt,
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
from core.clients.ikas import IkasClient
from core.models import AppConfig, ChatMessage, ChatResponse, Product, SeoScore, SeoSuggestion
from core.clients.mcp import IkasMCPClient, MCPError
from core.permissions import PermissionRule, create_permission_engine
from core.skills import (
    SkillDefinition,
    SkillRuntimeSelection,
    get_skill_definition,
    list_skill_definitions,
    resolve_chat_agent_scope,
    resolve_runtime_skill_selection,
)
from core.services.store_memory import StoreMemoryService

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
            self._total_tokens: dict[str, int | float] = {"input": 0, "output": 0, "estimated_cost": 0.0}
            self._active_request_lock = threading.Lock()
            self._active_http_client: httpx.AsyncClient | None = None
            self._permission_engine = create_permission_engine(config)
            self._permission_runtime_rules: list[PermissionRule] = []
            self._active_skill_slug: str | None = None
            self._runtime_skill_selection: SkillRuntimeSelection | None = None
            self._store_memory_service = StoreMemoryService()

            # Local tool registry — add new local tools here without touching _execute_chat_tool
            self._tool_registry = create_local_chat_tool_registry(
                self._save_suggestion_from_tool_args,
                self._apply_seo_to_ikas_handler,
                permission_engine=self._permission_engine,
                runtime_rule_provider=self._get_tool_permission_runtime_rules,
            )

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
        def total_tokens(self) -> dict[str, int | float]:
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
            self._permission_runtime_rules.clear()

        def get_active_skill(self) -> SkillDefinition | None:
            if not self._active_skill_slug:
                return None
            try:
                return get_skill_definition(self._active_skill_slug)
            except Exception:
                logger.warning("Active skill could not be reloaded: %s", self._active_skill_slug, exc_info=True)
                self._active_skill_slug = None
                return None

        def get_active_skill_payload(self) -> dict[str, Any] | None:
            skill = self.get_active_skill()
            if skill is None:
                return None
            selection = resolve_runtime_skill_selection(
                applies_to="chat",
                explicit_skill_slugs=skill.slug,
                agent_scope=resolve_chat_agent_scope("general"),
                permission_engine=self._permission_engine,
                permission_source="chat.state.explicit_skill_payload",
                permission_runtime_rules=self._permission_runtime_rules,
            )
            payload = selection.to_payload()
            if payload is not None:
                return payload
            return {
                "slug": skill.slug,
                "name": skill.name,
                "description": skill.description,
                "applies_to": list(skill.applies_to),
                "allowed_tools": list(skill.allowed_tools),
                "resolved_tools": [],
                "status": skill.status,
                "source": skill.source,
                "selection_mode": "explicit",
            }

        def set_active_skill(self, slug: str) -> SkillDefinition:
            skill = get_skill_definition(slug)
            if skill.status != "active":
                raise ValueError(f"Skill aktif degil: {skill.slug}")
            if "chat" not in skill.applies_to:
                raise ValueError(f"Skill chat akisi icin uygun degil: {skill.slug}")
            self._active_skill_slug = skill.slug
            selection = resolve_runtime_skill_selection(
                applies_to="chat",
                explicit_skill_slugs=skill.slug,
                agent_scope=resolve_chat_agent_scope("general"),
                permission_engine=self._permission_engine,
                permission_source="chat.state.set_active_skill",
                permission_runtime_rules=self._permission_runtime_rules,
            )
            resolved_tools = sorted(selection.allowed_tool_names or [])
            logger.info(
                "Chat skill activated slug=%s resolved_tools=%s",
                skill.slug,
                ",".join(resolved_tools) if resolved_tools else "*",
            )
            return skill

        def clear_active_skill(self) -> None:
            self._active_skill_slug = None

        def list_available_skills(self) -> list[SkillDefinition]:
            return list_skill_definitions()

        def set_runtime_skill_selection(self, selection: SkillRuntimeSelection | None) -> None:
            self._runtime_skill_selection = selection

        def get_effective_skill_payload(self) -> dict[str, Any] | None:
            if self._runtime_skill_selection is not None:
                payload = self._runtime_skill_selection.to_payload()
                if payload is not None:
                    return payload
            return self.get_active_skill_payload()

        def _build_active_skill_system_prompt(self) -> str:
            if self._runtime_skill_selection is not None:
                return self._runtime_skill_selection.prompt
            payload = self.get_active_skill_payload()
            if payload is None:
                return ""
            selection = resolve_runtime_skill_selection(
                applies_to="chat",
                explicit_skill_slugs=payload.get("slug"),
                agent_scope=resolve_chat_agent_scope("general"),
                permission_engine=self._permission_engine,
                permission_source="chat.state.build_prompt",
                permission_runtime_rules=self._permission_runtime_rules,
            )
            return selection.prompt

        def _get_active_skill_allowed_tools(self) -> set[str] | None:
            if self._runtime_skill_selection is not None:
                return self._runtime_skill_selection.allowed_tool_names
            selection = self.get_active_skill_payload()
            if selection is None:
                return None
            resolved_tools = selection.get("resolved_tools") or []
            return set(str(name) for name in resolved_tools)

        def resolve_message_skill_selection(
            self,
            user_message: str,
            *,
            agent_type: str,
            allow_tools: bool,
        ) -> SkillRuntimeSelection:
            product_parts = []
            if self._product is not None:
                product_parts.extend([
                    self._product.name,
                    self._product.category or "",
                ])
            if self._score is not None and self._score.issues:
                product_parts.append("; ".join(self._score.issues[:6]))

            routing_text = "\n".join(part for part in [user_message, *product_parts] if part).strip()
            selection = resolve_runtime_skill_selection(
                applies_to="chat",
                explicit_skill_slugs=self._active_skill_slug,
                routing_text=routing_text,
                enable_routing=bool(user_message.strip()) and agent_type != "operator",
                enable_default_fallback=bool(self._product) and agent_type != "operator",
                agent_scope=resolve_chat_agent_scope(agent_type),
                permission_engine=self._permission_engine,
                permission_target=self._product.id if self._product else "",
                permission_source="chat.state.runtime_selection",
                permission_runtime_rules=self._permission_runtime_rules,
            )
            logger.info(
                "Chat runtime skill resolved mode=%s skills=%s agent=%s allow_tools=%s resolved_tools=%s denied_tools=%s",
                selection.selection_mode,
                ",".join(selection.merged_skill_slugs) if selection.merged_skill_slugs else "-",
                agent_type,
                allow_tools,
                ",".join(sorted(selection.allowed_tool_names)) if selection.allowed_tool_names is not None else "*",
                ",".join(selection.denied_tool_names) if selection.denied_tool_names else "-",
            )
            return selection

        @staticmethod
        def _format_skill_status_message(
            *,
            title: str,
            active_skill: SkillDefinition | None,
            available_skills: list[SkillDefinition],
        ) -> str:
            lines = [f"**{title}**"]
            if active_skill is None:
                lines.append("- Aktif skill yok.")
            else:
                lines.append(f"- Aktif skill: `{active_skill.slug}`")
                if active_skill.description:
                    lines.append(f"- Aciklama: {active_skill.description}")
                if active_skill.allowed_tools:
                    lines.append(f"- Tool siniri: {', '.join(active_skill.allowed_tools)}")

            active_skills = [skill for skill in available_skills if skill.status == "active" and "chat" in skill.applies_to]
            if active_skills:
                lines.append("")
                lines.append("Kullanilabilir chat skill'leri:")
                for skill in active_skills[:12]:
                    summary = f"{skill.slug}: {skill.description}" if skill.description else skill.slug
                    lines.append(f"- {summary}")

            lines.append("")
            lines.append("Komutlar: `/skill`, `/skill set <slug>`, `/skill clear`")
            return "\n".join(lines)

        async def _maybe_handle_skill_command(
            self,
            user_message: str,
            *,
            chunk_handler: Callable[[str], Awaitable[None]] | None = None,
        ) -> ChatResponse | None:
            cleaned = (user_message or "").strip()
            if not cleaned.lower().startswith("/skill"):
                return None

            parts = cleaned.split()
            available_skills = self.list_available_skills()

            if len(parts) == 1 or (len(parts) == 2 and parts[1].lower() in {"list", "status"}):
                content = self._format_skill_status_message(
                    title="Skill Durumu",
                    active_skill=self.get_active_skill(),
                    available_skills=available_skills,
                )
            elif len(parts) >= 2 and parts[1].lower() in {"clear", "off", "none"}:
                self.clear_active_skill()
                content = self._format_skill_status_message(
                    title="Skill Temizlendi",
                    active_skill=None,
                    available_skills=available_skills,
                )
            else:
                slug = parts[-1].strip().lower()
                try:
                    skill = self.set_active_skill(slug)
                except Exception as exc:
                    content = self._format_skill_status_message(
                        title=f"Skill Secilemedi: {exc}",
                        active_skill=self.get_active_skill(),
                        available_skills=available_skills,
                    )
                else:
                    content = self._format_skill_status_message(
                        title="Skill Aktif Edildi",
                        active_skill=skill,
                        available_skills=available_skills,
                    )

            if chunk_handler and content:
                await chunk_handler(content)

            self._history.append(ChatMessage(role="assistant", content=content))
            return ChatResponse(
                content=content,
                thinking="",
                tool_results=[],
                error=False,
                meta={"active_skill": self.get_active_skill_payload()},
                pending_suggestion=self._get_session_pending_suggestion(),
            )

        def _get_tool_permission_runtime_rules(
            self,
            tool: Any,
            args: dict[str, Any],
            agent_type: str | None,
        ) -> list[PermissionRule]:
            return list(self._permission_runtime_rules)

        async def _build_store_memory_context(
            self,
            *,
            agent_type: str,
            applies_to: str = "chat",
        ):
            return await self._store_memory_service.build_prompt_context(
                product=self._product,
                applies_to=applies_to,
                agent_type=agent_type,
            )

        @contextlib.contextmanager
        def _temporary_permission_runtime_rules(
            self,
            rules: list[PermissionRule] | tuple[PermissionRule, ...],
        ):
            previous_rules = list(self._permission_runtime_rules)
            self._permission_runtime_rules = [*previous_rules, *list(rules)]
            try:
                yield
            finally:
                self._permission_runtime_rules = previous_rules

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
                        {"role": "system", "content": _get_memory_summarization_prompt()},
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
                    content=f"{_get_history_summary_prefix()}{summary}",
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
                    {"role": "system", "content": _get_semantic_routing_prompt()},
                    {"role": "user", "content": cleaned_message},
                ],
                "temperature": 0.0,
                "max_tokens": 256,
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
            allowed_tool_names: set[str] | None = None,
        ) -> tuple[list[dict[str, Any]] | None, list[str]]:
            tools: list[dict[str, Any]] = []
            instructions: list[str] = []
            local_tool_names = [APPLY_SEO_TO_IKAS_TOOL_NAME]

            if include_save_seo_tool:
                local_tool_names.insert(0, SAVE_SEO_SUGGESTION_TOOL_NAME)
                instructions.append(_get_save_tool_instruction())

            if allowed_tool_names is not None:
                local_tool_names = [name for name in local_tool_names if name in allowed_tool_names]

            # Always include the apply_seo_to_ikas tool — it handles both
            # native ikas API and MCP routes internally so the LLM never
            # needs to write raw GraphQL mutations.
            if local_tool_names:
                tools.extend(
                    self._tool_registry.get_openai_functions(
                        agent_type=f"chat:{agent_type}",
                        names=local_tool_names,
                    )
                )
            if local_tool_names:
                instructions.append(
                    "Kullanici urun degisikliklerini onayladiginda, arka planda uygun araclari cagir. "
                    "Kullaniciya arac adlarini gosterme; onay aldiktan sonra sessizce uygula."
                )

            # Add agent toolkit tools (SEO scoring, product details, validation, etc.)
            toolkit_tools = self._agent_toolkit.get_openai_functions()
            if allowed_tool_names is not None:
                toolkit_tools = [
                    tool for tool in toolkit_tools
                    if str(tool.get("function", {}).get("name") or "") in allowed_tool_names
                ]
            tools.extend(toolkit_tools)

            if allow_mcp_tools and self._mcp_initialized and self._mcp and not guided_context:
                mcp_tools = self._mcp.get_tools_as_openai_functions()
                mcp_tool_summaries = self.mcp_tools
                if allowed_tool_names is not None:
                    mcp_tools = [
                        tool for tool in mcp_tools
                        if str(tool.get("function", {}).get("name") or "") in allowed_tool_names
                    ]
                    mcp_tool_summaries = [
                        tool for tool in mcp_tool_summaries
                        if str(tool.get("name") or "") in allowed_tool_names
                    ]
                tools.extend(mcp_tools)
                tool_catalog_instruction = _build_tool_catalog_instruction(mcp_tool_summaries)
                if tool_catalog_instruction:
                    instructions.append(tool_catalog_instruction)

            return (tools or None), instructions
