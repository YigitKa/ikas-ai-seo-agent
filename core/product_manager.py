import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, List, Optional, TypeVar

from config.settings import get_config, save_config_to_db
from core.ai.client import (
    BaseAIClient,
    build_en_translation_request,
    build_field_rewrite_request,
    build_product_rewrite_request,
    create_ai_client,
)
from core.agent.orchestrator import AgentOrchestrator, supports_tool_calling
from core.agent.tools import AgentToolkit, create_seo_rewrite_toolkit
from core.utils.html import html_to_plain_text, sanitize_html_for_prompt
from core.chat import ChatService
from core.clients.ikas import IkasClient
from core.models import AgentEvent, AppConfig, ChatResponse, Product, SeoScore, SeoSuggestion
from core.utils.presentation import format_prompt_display, get_en_description_value, get_tr_description_value
from core.prompt_store import compose_prompt_with_skill_layer, get_batch_agent_system_prompt, get_rewrite_agent_system_prompt
from core.skills import SkillDefinition, SkillRuntimeSelection, resolve_runtime_skill_selection
from core.permissions import (
    PermissionDecisionError,
    PermissionOperation,
    PermissionRequest,
    PermissionRule,
    create_permission_engine,
)
from core.services.provider import (
    discover_provider_models,
    get_lm_studio_live_status,
    get_provider_health,
    test_settings_connection,
)
from core.services.suggestion import apply_suggestion_field, create_pending_suggestion
from core.seo.analyzer import analyze_product
from data import db

logger = logging.getLogger(__name__)

TARGET_FIELD_LABELS = {
    "meta_title": "Meta Başlık",
    "meta_description": "Meta Açıklama",
    "name": "Ürün Başlığı",
    "description": "Açıklama (TR)",
    "description_en": "Açıklama (EN)",
}

BATCH_FIELD_TO_AI_FIELD = {
    "name": "name",
    "meta_title": "meta_title",
    "meta_description": "meta_desc",
    "description": "desc_tr",
    "description_en": "desc_en",
}

BATCH_FIELD_TO_SUGGESTION_ATTR = {
    "name": "suggested_name",
    "meta_title": "suggested_meta_title",
    "meta_description": "suggested_meta_description",
    "description": "suggested_description",
    "description_en": "suggested_description_en",
}

SUCCESSFUL_BATCH_ITEM_STATUSES = {"analyzed", "approved", "rejected", "applied", "rolled_back"}
SKIPPED_BATCH_ITEM_STATUSES = {"skipped", "failed"}

TScore = TypeVar("TScore")


class ProductManager:
    def __init__(self) -> None:
        self._ikas = IkasClient()
        self._config = get_config()
        self._ai: BaseAIClient = create_ai_client(self._config)
        self._chat: ChatService = ChatService(self._config)
        self._permission_engine = create_permission_engine(self._config)

    def reload_ai_client(self) -> None:
        """Recreate AI client after config change."""
        from config.settings import get_config as _get
        self._config = _get()
        self._ai = create_ai_client(self._config)
        self._chat = ChatService(self._config)
        self._permission_engine = create_permission_engine(self._config)

    def get_config(self) -> AppConfig:
        return self._config

    def is_setup_incomplete(self) -> bool:
        return not self._config.ikas_store_name or not self._config.ikas_client_id

    async def fetch_products(self, limit: int = 50, page: int = 1) -> List[Product]:
        products = await self._ikas.get_products(limit=limit, page=page)
        await db.save_products(products)
        logger.info(f"Fetched and cached {len(products)} products (page {page})")
        return products

    async def fetch_and_score_products(self, limit: int = 50, page: int = 1) -> tuple[list[tuple[Product, SeoScore]], int]:
        products = await self.fetch_products(limit=limit, page=page)
        return await self.score_products(products), self._ikas.total_count

    async def sync_all_products(self, batch_size: int = 50) -> tuple[int, int]:
        products = await self._ikas.get_all_products(batch_size=batch_size)
        await db.save_products(products)
        await self.score_products(products)
        logger.info("Fetched and cached %s/%s products (full sync)", len(products), self._ikas.total_count)
        return len(products), self._ikas.total_count

    async def fetch_product(self, product_id: str) -> Optional[Product]:
        product = await self._ikas.get_product_by_id(product_id)
        if product:
            await db.save_product(product)
        return product

    async def get_cached_products(self) -> List[Product]:
        return await db.get_all_products()

    async def clear_local_data(
        self,
        *,
        permission_rules: list[PermissionRule] | None = None,
    ) -> dict[str, int]:
        await self._require_permission(
            "db_reset",
            target="local_store",
            source="product_manager.clear_local_data",
            metadata={"dry_run": self._config.dry_run},
            runtime_rules=permission_rules,
        )
        counts = await db.clear_all_data()
        logger.info("Cleared local cache: %s", counts)
        return counts

    async def score_products(self, products: List[Product]) -> List[tuple[Product, SeoScore]]:
        keywords = self._config.seo_target_keywords
        scores = await asyncio.gather(
            *[asyncio.to_thread(analyze_product, p, keywords) for p in products]
        )
        scored_products = list(zip(products, scores))

        await db.save_scores(list(scores))
        logger.info("Analyzed %s products", len(products))
        return scored_products

    async def analyze_product(self, product: Product) -> SeoScore:
        return (await self.score_products([product]))[0][1]

    def filter_products_by_score(
        self,
        products_data: List[tuple[Product, SeoScore]],
        threshold: int | None = None,
    ) -> List[tuple[Product, SeoScore]]:
        cutoff = threshold if threshold is not None else self._config.seo_low_score_threshold
        return [(p, s) for p, s in products_data if s.total_score < cutoff]

    def filter_products_missing_english_translation(
        self,
        products_data: list[tuple[Product, TScore]],
    ) -> list[tuple[Product, TScore]]:
        return [
            (product, score)
            for product, score in products_data
            if not html_to_plain_text(
                get_en_description_value(product.description_translations),
                preserve_breaks=False,
            )
        ]

    async def analyze_products(
        self,
        products: List[Product],
        threshold: int = 100,
    ) -> List[tuple[Product, SeoScore]]:
        scored_products = await self.score_products(products)
        results = [(product, score) for product, score in scored_products if score.total_score <= threshold]
        logger.info(f"Analyzed {len(products)} products, {len(results)} below threshold {threshold}")
        return results

    async def rewrite_products(
        self,
        products_with_scores: List[tuple[Product, SeoScore]],
    ) -> List[SeoSuggestion]:
        suggestions = self._ai.rewrite_products_batch(products_with_scores)
        for s in suggestions:
            await db.save_suggestion(s)
        logger.info(f"Generated {len(suggestions)} suggestions")
        return suggestions

    def format_product_rewrite_prompt(self, product: Product, score: SeoScore) -> str:
        request = build_product_rewrite_request(self._config, self._config.ai_provider, product, score)
        return format_prompt_display(request)

    def format_field_rewrite_prompt(self, field: str, product: Product) -> str:
        request = build_field_rewrite_request(self._config, self._config.ai_provider, field, product)
        return format_prompt_display(request)

    def format_translation_prompt(self, product: Product) -> str:
        request = build_en_translation_request(self._config, self._config.ai_provider, product)
        return format_prompt_display(request)

    def get_active_model_name(self) -> str:
        return self._config.ai_model_name or self._config.ai_provider

    @staticmethod
    def _build_rewrite_skill_routing_text(
        product: Product,
        score: SeoScore | None = None,
        *,
        field: str = "",
    ) -> str:
        parts = [
            product.name,
            product.category or "",
            field,
            sanitize_html_for_prompt(product.description, limit=600),
        ]
        if score is not None and score.issues:
            parts.append("; ".join(score.issues[:8]))
        return "\n".join(part for part in parts if part).strip()

    def _build_batch_skill_routing_text(self, config: Any) -> str:
        parts = [
            self._get_batch_config_value(config, "category_filter", ""),
            " ".join(self._get_batch_config_value(config, "target_fields", []) or []),
        ]
        if self._get_batch_config_value(config, "preserve_specs", True):
            parts.append("preserve specs")
        if self._get_batch_config_value(config, "prevent_cannibalization", True):
            parts.append("prevent cannibalization")
        if self._get_batch_config_value(config, "in_stock_only", False):
            parts.append("in stock only")
        return "\n".join(str(part) for part in parts if str(part).strip()).strip()

    def _resolve_runtime_skill_selection(
        self,
        skill_slug: str | None,
        applies_to: str,
        *,
        routing_text: str = "",
        enable_routing: bool = True,
        enable_default_fallback: bool = True,
        permission_target: str = "",
    ) -> SkillRuntimeSelection:
        selection = resolve_runtime_skill_selection(
            applies_to=applies_to,
            explicit_skill_slugs=skill_slug,
            routing_text=routing_text,
            enable_routing=enable_routing,
            enable_default_fallback=enable_default_fallback,
            agent_scope="seo_rewrite" if applies_to == "rewrite" else "batch",
            permission_engine=self._permission_engine,
            permission_target=permission_target,
            permission_source=f"product_manager.skill_runtime.{applies_to}",
        )
        if selection.primary_skill is None:
            return selection

        logger.info(
            "Runtime skill resolved flow=%s mode=%s skills=%s resolved_tools=%s denied_tools=%s layers=%s",
            applies_to,
            selection.selection_mode,
            ",".join(selection.merged_skill_slugs),
            ",".join(sorted(selection.allowed_tool_names)) if selection.allowed_tool_names is not None else "*",
            ",".join(selection.denied_tool_names) if selection.denied_tool_names else "-",
            ",".join(selection.prompt_layer_sources) if selection.prompt_layer_sources else "-",
        )
        return selection

    def validate_skill_for_flow(
        self,
        skill_slug: str | None,
        applies_to: str,
    ) -> dict[str, Any] | None:
        selection = self._resolve_runtime_skill_selection(
            skill_slug,
            applies_to,
            enable_routing=False,
            enable_default_fallback=False,
        )
        skill = selection.primary_skill
        if skill is None:
            return None
        return {
            "slug": skill.slug,
            "name": skill.name,
            "applies_to": list(skill.applies_to),
            "allowed_tools": list(skill.allowed_tools),
            "selection_mode": selection.selection_mode,
            "merged_skill_slugs": list(selection.merged_skill_slugs),
        }

    @staticmethod
    def _filter_toolkit_to_allowed_names(
        toolkit: AgentToolkit,
        allowed_tool_names: set[str] | None,
        *,
        agent_type: str,
    ) -> AgentToolkit:
        if allowed_tool_names is None:
            return toolkit

        filtered_tools = []
        for name in toolkit.tool_names:
            if name not in allowed_tool_names:
                continue
            tool = toolkit.get(name)
            if tool is not None:
                filtered_tools.append(tool)
        return AgentToolkit(filtered_tools, agent_type=agent_type)

    async def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        *,
        skill_slug: str | None = None,
    ) -> SeoSuggestion:
        selection = self._resolve_runtime_skill_selection(
            skill_slug,
            "rewrite",
            routing_text=self._build_rewrite_skill_routing_text(product, score),
            permission_target=product.id,
        )
        extra_system_prompt = selection.prompt
        allowed_tool_names = selection.allowed_tool_names
        if supports_tool_calling(self._config) and self._config.ai_provider != "none":
            return await self._agentic_rewrite_product(
                product,
                score,
                extra_system_prompt=extra_system_prompt,
                allowed_tool_names=allowed_tool_names,
            )
        # Fallback: single-shot rewrite
        suggestion = self._ai.rewrite_product(product, score, extra_system_prompt=extra_system_prompt)
        await db.save_suggestion(suggestion)
        return suggestion

    async def _agentic_rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        *,
        extra_system_prompt: str = "",
        allowed_tool_names: set[str] | None = None,
    ) -> SeoSuggestion:
        """Run the agentic rewrite pipeline with tool calling."""
        toolkit = self._filter_toolkit_to_allowed_names(
            create_seo_rewrite_toolkit(),
            allowed_tool_names,
            agent_type="seo_rewrite",
        )
        system_prompt = get_rewrite_agent_system_prompt()
        if extra_system_prompt:
            system_prompt = compose_prompt_with_skill_layer(system_prompt, extra_system_prompt, "rewrite")
        orchestrator = AgentOrchestrator(
            config=self._config,
            toolkit=toolkit,
            system_prompt=system_prompt,
            max_iterations=8,
        )
        result = await orchestrator.run(
            user_message=f"Bu urunun SEO'sunu optimize et: {product.name} (ID: {product.id})",
            context={"product_id": product.id, "current_score": score.model_dump()},
        )
        # Agent should have called save_suggestion — fetch the latest
        suggestion = await db.get_latest_suggestion_by_product(product.id)
        if suggestion is None:
            # Agent didn't save; fall back to single-shot
            logger.warning("Agentic rewrite did not save a suggestion; falling back to single-shot")
            suggestion = self._ai.rewrite_product(product, score, extra_system_prompt=extra_system_prompt)
            await db.save_suggestion(suggestion)
        return suggestion

    async def stream_rewrite_product(
        self,
        product_id: str,
        *,
        skill_slug: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Stream the agentic rewrite pipeline for a product."""
        product = await db.get_product(product_id)
        if product is None:
            yield AgentEvent(type="error", content=f"Product '{product_id}' not found.")
            return
        score = analyze_product(product, self._config.seo_target_keywords)
        selection = self._resolve_runtime_skill_selection(
            skill_slug,
            "rewrite",
            routing_text=self._build_rewrite_skill_routing_text(product, score),
            permission_target=product.id,
        )
        extra_system_prompt = selection.prompt
        allowed_tool_names = selection.allowed_tool_names

        toolkit = self._filter_toolkit_to_allowed_names(
            create_seo_rewrite_toolkit(),
            allowed_tool_names,
            agent_type="seo_rewrite",
        )
        system_prompt = get_rewrite_agent_system_prompt()
        if extra_system_prompt:
            system_prompt = compose_prompt_with_skill_layer(system_prompt, extra_system_prompt, "rewrite")
        orchestrator = AgentOrchestrator(
            config=self._config,
            toolkit=toolkit,
            system_prompt=system_prompt,
            max_iterations=8,
        )
        async for event in orchestrator.stream(
            user_message=f"Bu urunun SEO'sunu optimize et: {product.name} (ID: {product.id})",
            context={"product_id": product.id, "current_score": score.model_dump()},
        ):
            yield event

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        *,
        skill_slug: str | None = None,
        extra_system_prompt: str = "",
    ) -> tuple[str, str]:
        selection = self._resolve_runtime_skill_selection(
            skill_slug,
            "rewrite",
            routing_text=self._build_rewrite_skill_routing_text(product, score, field=field),
            permission_target=product.id,
        )
        merged_prompt = compose_prompt_with_skill_layer(extra_system_prompt, selection.prompt, "product_rewrite")
        result = self._ai.rewrite_field(field, product, score, extra_system_prompt=merged_prompt)
        if isinstance(result, tuple):
            return result
        return result, ""

    def translate_description_to_en(
        self,
        product: Product,
        *,
        skill_slug: str | None = None,
        extra_system_prompt: str = "",
    ) -> tuple[str, str]:
        selection = self._resolve_runtime_skill_selection(
            skill_slug,
            "rewrite",
            routing_text=self._build_rewrite_skill_routing_text(product, field="description_en"),
            permission_target=product.id,
        )
        merged_prompt = compose_prompt_with_skill_layer(extra_system_prompt, selection.prompt, "product_rewrite")
        result = self._ai.translate_description_to_en(product, extra_system_prompt=merged_prompt)
        if isinstance(result, tuple):
            return result
        return result, ""

    def has_translatable_description(self, product: Product) -> bool:
        return bool(get_tr_description_value(product.description, product.description_translations))

    async def approve_pending_suggestion(self, suggestion: SeoSuggestion) -> None:
        await self.save_or_update_pending_suggestion(suggestion)
        await self.approve_suggestion(suggestion.product_id)

    async def reject_pending_suggestion(self, product_id: str) -> None:
        await self.reject_suggestion(product_id)

    async def save_settings(self, values: dict) -> None:
        await save_config_to_db(values)
        self.reload_ai_client()

    def get_provider_health(self) -> dict[str, str]:
        return get_provider_health(self._config)

    def discover_provider_models(self, provider: str, base_url: str = "") -> list[str]:
        return discover_provider_models(provider, base_url=base_url)

    def test_settings_connection(self, values: dict) -> dict:
        return test_settings_connection(values)

    def get_lm_studio_live_status(self, *, job_id: str = "") -> dict:
        return get_lm_studio_live_status(self._config, job_id=job_id)

    async def _require_permission(
        self,
        operation: PermissionOperation,
        *,
        target: str,
        source: str,
        metadata: dict[str, Any] | None = None,
        runtime_rules: list[PermissionRule] | None = None,
    ) -> None:
        await self._permission_engine.ensure_allowed(
            PermissionRequest(
                operation=operation,
                target=target,
                source=source,
                metadata=dict(metadata or {}),
            ),
            runtime_rules=runtime_rules,
        )

    async def apply_suggestions(
        self,
        suggestions: List[SeoSuggestion],
        *,
        permission_rules: list[PermissionRule] | None = None,
    ) -> int:
        sem = asyncio.Semaphore(3)
        approved = [s for s in suggestions if s.status == "approved"]
        if not approved:
            return 0

        permission_operation: PermissionOperation = "bulk_apply" if len(approved) > 1 else "apply"
        await self._require_permission(
            permission_operation,
            target="approved_suggestions",
            source="product_manager.apply_suggestions",
            metadata={
                "approved_count": len(approved),
                "product_ids": [suggestion.product_id for suggestion in approved],
            },
            runtime_rules=permission_rules,
        )

        async def _apply_one(suggestion: SeoSuggestion) -> bool:
            updates: dict[str, Any] = {}
            if suggestion.suggested_name:
                updates["name"] = suggestion.suggested_name
            if suggestion.suggested_description:
                updates["description"] = suggestion.suggested_description

            description_translations: dict[str, str] = {}
            if suggestion.suggested_description:
                description_translations["tr"] = suggestion.suggested_description
            if suggestion.suggested_description_en:
                description_translations["en"] = suggestion.suggested_description_en
            if description_translations:
                updates["description_translations"] = description_translations
            if suggestion.suggested_meta_title:
                updates["meta_title"] = suggestion.suggested_meta_title
            if suggestion.suggested_meta_description:
                updates["meta_description"] = suggestion.suggested_meta_description

            try:
                old_score_obj = await db.get_latest_score(suggestion.product_id)
                score_before = old_score_obj.total_score if old_score_obj else None

                async with sem:
                    success = await self._ikas.update_product(suggestion.product_id, updates)
                if not success:
                    return False

                await db.update_suggestion_status(suggestion.product_id, "applied")
                await db.log_operation("apply", suggestion.product_id, updates, True)

                score_after = None
                try:
                    async with sem:
                        updated_product = await self._ikas.get_product_by_id(suggestion.product_id)
                    if updated_product:
                        await db.save_product(updated_product)
                        new_score = analyze_product(updated_product, self._config.seo_target_keywords)
                        await db.save_scores([new_score])
                        score_after = new_score.total_score
                        logger.info("Post-apply verify %s: new score %s", suggestion.product_id, new_score.total_score)
                except Exception as verify_exc:
                    logger.warning("Post-apply verify failed for %s: %s", suggestion.product_id, verify_exc)

                await db.insert_score_change_log(
                    product_id=suggestion.product_id,
                    product_name=suggestion.original_name or "",
                    operation="apply",
                    score_before=score_before,
                    score_after=score_after,
                )
                return True
            except Exception as e:
                logger.error(f"Failed to apply suggestion for {suggestion.product_id}: {e}")
                await db.log_operation("apply", suggestion.product_id, {"error": str(e)}, False)
                return False

        results = await asyncio.gather(*[_apply_one(s) for s in approved])
        applied = sum(1 for r in results if r)
        logger.info(f"Applied {applied}/{len(suggestions)} suggestions")
        return applied

    async def apply_approved_suggestions(
        self,
        *,
        permission_rules: list[PermissionRule] | None = None,
    ) -> tuple[int, bool]:
        approved = await self.get_approved_suggestions()
        if not approved:
            return 0, False
        return await self.apply_suggestions(approved, permission_rules=permission_rules), True

    async def get_pending_suggestions(self) -> List[SeoSuggestion]:
        return await db.get_pending_suggestions()

    async def get_approved_suggestions(self) -> List[SeoSuggestion]:
        return await db.get_approved_suggestions()

    async def get_pending_suggestion_count(self) -> int:
        return await db.count_suggestions("pending")

    async def get_suggestion_product_ids(self, status: str) -> set[str]:
        return await db.get_suggestion_product_ids(status)

    async def get_latest_suggestion(self, product_id: str) -> Optional[SeoSuggestion]:
        return await db.get_latest_suggestion_by_product(product_id)

    async def update_latest_pending_suggestion(self, suggestion: SeoSuggestion) -> None:
        await db.update_latest_pending_suggestion(suggestion)

    async def save_or_update_pending_suggestion(self, suggestion: SeoSuggestion) -> None:
        await db.save_or_update_pending_suggestion(suggestion)

    async def approve_suggestion(self, product_id: str) -> None:
        await db.update_suggestion_status(product_id, "approved")

    async def reject_suggestion(self, product_id: str) -> None:
        await db.update_suggestion_status(product_id, "rejected")

    def get_token_usage(self) -> dict:
        return self._ai.total_tokens

    def get_last_token_usage(self) -> dict:
        """Token usage of the most recent API call."""
        return getattr(self._ai, 'last_usage', {"input": 0, "output": 0})

    def get_last_ai_meta(self) -> dict:
        return getattr(self._ai, "last_response_meta", {})

    def cancel_ai_request(self) -> bool:
        return self._ai.cancel_active_request()

    async def test_connection(self) -> bool:
        return await self._ikas.test_connection()

    # ── Chat / MCP ───────────────────────────────────────────────────────

    def set_chat_product_context(self, product: Product | None, score: SeoScore | None = None) -> None:
        """Set the current product context for the chat service."""
        self._chat.set_product_context(product, score)

    async def initialize_mcp(self) -> tuple[bool, str]:
        """Initialize the ikas MCP connection."""
        return await self._chat.initialize_mcp()

    async def send_chat_message(self, message: str) -> ChatResponse:
        """Send a chat message and get AI response with optional MCP tool calls."""
        return await self._chat.send_message(message)

    def stream_chat_message(self, message: str):
        """Return the chat stream iterator directly."""
        return self._chat.stream_message(message)

    def cancel_chat_request(self) -> bool:
        """Cancel the active chat request if one is in flight."""
        return self._chat.cancel_active_request()

    def clear_chat_history(self) -> None:
        """Clear the chat conversation history."""
        self._chat.clear_history()

    def set_chat_active_skill(self, slug: str) -> dict[str, Any] | None:
        self._chat.set_active_skill(slug)
        return self._chat.get_active_skill_payload()

    def clear_chat_active_skill(self) -> None:
        self._chat.clear_active_skill()

    def get_chat_active_skill(self) -> dict[str, Any] | None:
        return self._chat.get_active_skill_payload()

    @property
    def chat_has_mcp(self) -> bool:
        return self._chat.has_mcp

    @property
    def chat_mcp_initialized(self) -> bool:
        return self._chat.mcp_initialized

    @property
    def chat_mcp_tool_count(self) -> int:
        return self._chat.mcp_tool_count

    @property
    def chat_mcp_tools(self) -> list[dict[str, str]]:
        return self._chat.mcp_tools

    def get_chat_token_usage(self) -> dict[str, int]:
        return self._chat.total_tokens

    async def close(self) -> None:
        await self._ikas.close()
        await self._chat.close()

    # ── Batch operations ──────────────────────────────────────────────────

    def _get_batch_config_value(self, config: Any, key: str, default: Any) -> Any:
        if isinstance(config, dict):
            return config.get(key, default)
        return getattr(config, key, default)

    def _build_batch_runtime_prompt(self, config: Any) -> str:
        rules: list[str] = []
        if self._get_batch_config_value(config, "preserve_specs", True):
            rules.append(
                "Teknik ozellikleri (materyal, boyut, agirlik) DEGISTIRME, "
                "sadece bicimlendir ve SEO acisindan zenginlestir."
            )
        if self._get_batch_config_value(config, "prevent_cannibalization", True):
            rules.append(
                "Benzer urun gruplarinda LSI varyasyonlari kullan; "
                "anahtar kelime cakismasini onle."
            )
        pct = self._get_batch_config_value(config, "max_title_change_pct", 20)
        if pct < 100:
            rules.append(
                f"Baslik alaninda maksimum %{pct} degisiklik yap; "
                "mevcut ana anahtar kelimeyi koru."
            )
        target_fields = self._get_batch_config_value(config, "target_fields", None)
        if target_fields:
            field_labels = [TARGET_FIELD_LABELS.get(f, f) for f in target_fields]
            rules.append(
                "Sadece su alanlara odaklan: " + ", ".join(field_labels) + ". "
                "Diger alanlara yeni oneriler ekleme."
            )

        blocks: list[str] = []
        if rules:
            blocks.append(
                "BATCH KISITLARI (Bu kurallara kesinlikle uy):\n"
                + "\n".join(f"- {rule}" for rule in rules)
            )

        skill_slug = self._get_batch_config_value(config, "skill_slug", "")
        selection = self._resolve_runtime_skill_selection(
            skill_slug,
            "batch",
            routing_text=self._build_batch_skill_routing_text(config),
            permission_target=str(self._get_batch_config_value(config, "job_id", "")),
        )
        if selection.prompt:
            blocks.append(selection.prompt)

        return "\n\n".join(blocks).strip()

    def _build_batch_system_prompt(self, config: Any) -> str:
        """Build BATCH_AGENT_SYSTEM_PROMPT augmented with user-defined constraints."""
        runtime_prompt = self._build_batch_runtime_prompt(config)
        if not runtime_prompt:
            return get_batch_agent_system_prompt()
        return compose_prompt_with_skill_layer(get_batch_agent_system_prompt(), runtime_prompt, "batch")
        rules: list[str] = []
        if self._get_batch_config_value(config, "preserve_specs", True):
            rules.append(
                "Teknik özellikleri (materyal, boyut, ağırlık) DEĞİŞTİRME, "
                "sadece biçimlendir ve SEO açısından zenginleştir."
            )
        if self._get_batch_config_value(config, "prevent_cannibalization", True):
            rules.append(
                "Benzer ürün gruplarında LSI (Latent Semantic Indexing) varyasyonları "
                "kullan; anahtar kelime çakışmasını önle."
            )
        pct = self._get_batch_config_value(config, "max_title_change_pct", 20)
        if pct < 100:
            rules.append(
                f"Başlık (title) etiketinde maksimum %{pct} değişiklik yap; "
                "mevcut ana anahtar kelimeyi koru."
            )
        target_fields = self._get_batch_config_value(config, "target_fields", None)
        if target_fields:
            field_labels = [TARGET_FIELD_LABELS.get(f, f) for f in target_fields]
            rules.append(
                "SADECE şu alanları güncelle: " + ", ".join(field_labels) + ". "
                "Diğer alanlara dokunma, save_suggestion çağrısında diğer alanlara boş string ver."
            )
        base = get_batch_agent_system_prompt()
        if not rules:
            return base
        constraints_block = "\n\nKISITLAMALAR (Bu kurallara kesinlikle uy):\n" + "\n".join(
            f"- {r}" for r in rules
        )
        return base + constraints_block

    async def _run_agent_for_product(
        self, product: Product, score: SeoScore, system_prompt: str,
    ) -> SeoSuggestion | None:
        """Run the agentic rewrite and return the saved suggestion, or None."""
        previous_suggestion = await db.get_latest_suggestion_by_product(product.id)
        previous_created_at = previous_suggestion.created_at if previous_suggestion else None
        toolkit = create_seo_rewrite_toolkit()
        orchestrator = AgentOrchestrator(
            config=self._config,
            toolkit=toolkit,
            system_prompt=system_prompt,
            max_iterations=8,
        )
        product_context = {
            "product_id": product.id,
            "name": product.name,
            "description": sanitize_html_for_prompt(product.description, limit=1000),
            "meta_title": product.meta_title or "",
            "meta_description": product.meta_description or "",
            "category": product.category or "",
            "tags": product.tags or [],
            "current_score": score.total_score,
            "issues": score.issues[:10],
            "suggestions": score.suggestions[:10],
        }
        user_msg = (
            f"Bu ürünün SEO'sunu optimize et ve save_suggestion ile kaydet.\n"
            f"Ürün: {product.name} (ID: {product.id})\n"
            f"Mevcut skor: {score.total_score}/100\n"
            f"Sorunlar: {', '.join(score.issues[:5]) if score.issues else 'Yok'}"
        )
        result = await orchestrator.run(user_message=user_msg, context=product_context)
        logger.info(
            "Agent result for %s: iterations=%s, tool_calls=%s, content_len=%d",
            product.id,
            result.iterations,
            [tc.name for tc in result.tool_calls_made],
            len(result.content),
        )
        latest_suggestion = await db.get_latest_suggestion_by_product(product.id)
        if latest_suggestion is None:
            return None
        if previous_created_at and latest_suggestion.created_at == previous_created_at:
            return None
        return latest_suggestion

    def _filter_suggestion_to_target_fields(
        self,
        suggestion: SeoSuggestion,
        config: Any,
    ) -> SeoSuggestion:
        target_fields = set(self._get_batch_config_value(config, "target_fields", None) or [])
        if not target_fields:
            return suggestion

        blanks = {
            attr: ""
            for field_key, attr in BATCH_FIELD_TO_SUGGESTION_ATTR.items()
            if field_key not in target_fields
        }
        return suggestion.model_copy(update=blanks) if blanks else suggestion

    def _build_batch_skip_reason(self, config: Any) -> str:
        target_fields = self._get_batch_config_value(config, "target_fields", None)
        if target_fields:
            field_labels = [TARGET_FIELD_LABELS.get(f, f) for f in target_fields]
            return f"Öneri oluşturulamadı (hedef alanlar: {', '.join(field_labels)})"
        return "Öneri oluşturulamadı"

    def _get_batch_target_fields(
        self,
        config: Any,
        field_keys: list[str] | None = None,
    ) -> list[str]:
        configured_fields = self._get_batch_config_value(config, "target_fields", None) or list(TARGET_FIELD_LABELS)
        valid_fields = [field for field in configured_fields if field in TARGET_FIELD_LABELS]
        if field_keys is None:
            return valid_fields
        allowed = set(field_keys)
        return [field for field in valid_fields if field in allowed]

    def _get_batch_field_value(self, suggestion: SeoSuggestion, field: str) -> str:
        attr = BATCH_FIELD_TO_SUGGESTION_ATTR[field]
        value = getattr(suggestion, attr, "")
        return value or ""

    def _set_batch_field_value(self, suggestion: SeoSuggestion, field: str, value: str) -> None:
        apply_suggestion_field(suggestion, BATCH_FIELD_TO_AI_FIELD[field], value)

    def _build_suggestion_from_batch_item(self, product: Product, item: dict | None) -> SeoSuggestion:
        suggestion = create_pending_suggestion(product)
        suggestion_data = item.get("suggestion_data") if item else None
        if not isinstance(suggestion_data, dict):
            return suggestion

        for field in BATCH_FIELD_TO_SUGGESTION_ATTR:
            suggested_value = suggestion_data.get(f"suggested_{field}", "")
            if isinstance(suggested_value, str) and suggested_value.strip():
                self._set_batch_field_value(suggestion, field, suggested_value)
        return suggestion

    def _get_batch_item_field_errors(self, item: dict | None) -> dict[str, str]:
        suggestion_data = item.get("suggestion_data") if isinstance(item, dict) else None
        if not isinstance(suggestion_data, dict):
            return {}
        raw_field_errors = suggestion_data.get("field_errors")
        if not isinstance(raw_field_errors, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in raw_field_errors.items()
            if str(value).strip()
        }

    def _generate_batch_field_value(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        suggestion: SeoSuggestion | None = None,
        *,
        extra_system_prompt: str = "",
    ) -> tuple[str, str]:
        working_product = product

        if field == "description_en" and suggestion is not None:
            if suggestion.suggested_description.strip():
                working_product = working_product.model_copy(update={
                    "description": suggestion.suggested_description,
                })
            if suggestion.suggested_description_en.strip():
                updated_translations = dict(working_product.description_translations or {})
                updated_translations["en"] = suggestion.suggested_description_en
                working_product = working_product.model_copy(update={
                    "description_translations": updated_translations,
                })

        if field == "description_en" and not html_to_plain_text(
            get_en_description_value(working_product.description_translations),
            preserve_breaks=False,
        ):
            result = self.translate_description_to_en(
                working_product,
                extra_system_prompt=extra_system_prompt,
            )
        else:
            result = self.rewrite_field(
                BATCH_FIELD_TO_AI_FIELD[field],
                working_product,
                score,
                extra_system_prompt=extra_system_prompt,
            )

        if isinstance(result, tuple):
            return result
        return result, ""

    def _build_batch_item_result(
        self,
        product: Product,
        suggestion: SeoSuggestion,
        target_fields: list[str],
        field_errors: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any], bool]:
        original_en_description = get_en_description_value(product.description_translations)
        updated_translations = dict(product.description_translations or {})
        if suggestion.suggested_description:
            updated_translations["tr"] = suggestion.suggested_description
        if suggestion.suggested_description_en:
            updated_translations["en"] = suggestion.suggested_description_en

        updated = product.model_copy(update={
            "name": suggestion.suggested_name or product.name,
            "description": suggestion.suggested_description or product.description,
            "description_translations": updated_translations,
            "meta_title": suggestion.suggested_meta_title or product.meta_title,
            "meta_description": suggestion.suggested_meta_description or product.meta_description,
        })
        after_score = analyze_product(updated, self._config.seo_target_keywords).total_score
        original_values = {
            "name": product.name,
            "meta_title": product.meta_title or "",
            "meta_description": product.meta_description or "",
            "description": product.description or "",
            "description_en": original_en_description,
        }
        suggestion_data: dict[str, Any] = {
            "field_errors": field_errors or {},
            "active_fields": list(target_fields),
        }
        has_suggestions = False
        for field in target_fields:
            suggestion_data[f"original_{field}"] = original_values.get(field, "")
            suggested_value = self._get_batch_field_value(suggestion, field)
            suggestion_data[f"suggested_{field}"] = suggested_value
            if suggested_value.strip():
                has_suggestions = True
        return after_score, suggestion_data, has_suggestions

    async def _generate_batch_suggestion(
        self,
        product: Product,
        score: SeoScore,
        config: Any,
        extra_system_prompt: str,
        field_keys: list[str] | None = None,
        base_suggestion: SeoSuggestion | None = None,
    ) -> tuple[SeoSuggestion, dict[str, str]]:
        target_fields = self._get_batch_target_fields(config, field_keys)
        suggestion = base_suggestion.model_copy(deep=True) if base_suggestion else create_pending_suggestion(product)
        field_errors: dict[str, str] = {}
        thinking_parts: list[str] = []

        for field in target_fields:
            try:
                value, thinking = self._generate_batch_field_value(
                    field,
                    product,
                    score,
                    suggestion,
                    extra_system_prompt=extra_system_prompt,
                )
                if not value.strip():
                    field_errors[field] = "Öneri oluşturulamadı."
                    continue
                self._set_batch_field_value(suggestion, field, value)
                if thinking.strip():
                    thinking_parts.append(f"[{TARGET_FIELD_LABELS.get(field, field)}]\n{thinking.strip()}")
            except Exception as exc:
                logger.warning("Batch field generation failed for %s/%s: %s", product.id, field, exc)
                field_errors[field] = str(exc)[:200]

        suggestion.thinking_text = "\n\n".join(thinking_parts).strip()
        await db.save_or_update_pending_suggestion(self._filter_suggestion_to_target_fields(suggestion, config))
        return suggestion, field_errors

    async def _refresh_batch_job_metrics(self, job_id: str) -> None:
        items = await db.get_batch_items(job_id)
        successful_items = [item for item in items if item["status"] in SUCCESSFUL_BATCH_ITEM_STATUSES]
        scored_items = [
            item for item in successful_items
            if item["score_before"] is not None and item["score_after"] is not None
        ]

        def _avg(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0

        await db.update_batch_job(
            job_id,
            processed_count=len(successful_items),
            skipped_count=sum(1 for item in items if item["status"] in SKIPPED_BATCH_ITEM_STATUSES),
            failed_count=sum(1 for item in items if item["status"] == "failed"),
            avg_score_before=_avg([float(item["score_before"]) for item in scored_items]),
            avg_score_after=_avg([float(item["score_after"]) for item in scored_items]),
        )

    async def _fallback_rewrite(
        self, product: Product, score: SeoScore, config: Any,
    ) -> SeoSuggestion | None:
        """Direct AI rewrite as fallback when the agent loop fails to save."""
        try:
            suggestion = self._ai.rewrite_product(
                product,
                score,
                extra_system_prompt=self._build_batch_runtime_prompt(config),
            )
        except Exception as exc:
            logger.warning("Fallback rewrite failed for %s: %s", product.id, exc)
            return None

        suggestion = self._filter_suggestion_to_target_fields(suggestion, config)
        await db.save_or_update_pending_suggestion(suggestion)
        return suggestion

    async def regenerate_batch_item(self, item_id: int) -> dict:
        item = await db.get_batch_item(item_id)
        if item is None:
            raise ValueError("Item not found")

        job = await db.get_batch_job(item["job_id"])
        if job is None:
            raise ValueError("Job not found")
        if job["status"] != "analyzed":
            raise ValueError("Yeniden üretme sadece analiz tamamlandıktan sonra kullanılabilir.")

        product = await db.get_product(item["product_id"])
        if product is None:
            raise ValueError("Product not found")

        config = job["config"]
        score = analyze_product(product, self._config.seo_target_keywords)
        system_prompt = self._build_batch_runtime_prompt(config)
        base_suggestion = self._build_suggestion_from_batch_item(product, item)
        suggestion, field_errors = await self._generate_batch_suggestion(
            product,
            score,
            config,
            system_prompt,
            base_suggestion=base_suggestion,
        )
        target_fields = self._get_batch_target_fields(config)
        after_score, suggestion_data, has_suggestions = self._build_batch_item_result(
            product,
            suggestion,
            target_fields,
            field_errors,
        )
        await db.update_batch_item(
            item_id,
            status="analyzed" if has_suggestions else "skipped",
            score_before=score.total_score,
            score_after=after_score if has_suggestions else None,
            skip_reason=None if has_suggestions else self._build_batch_skip_reason(config),
            suggestion_data=suggestion_data,
        )
        await self._refresh_batch_job_metrics(job["id"])
        updated_item = await db.get_batch_item(item_id)
        if updated_item is None:
            raise ValueError("Item not found after update")
        return updated_item

    async def regenerate_batch_item_field(self, item_id: int, field_key: str) -> dict:
        item = await db.get_batch_item(item_id)
        if item is None:
            raise ValueError("Item not found")

        job = await db.get_batch_job(item["job_id"])
        if job is None:
            raise ValueError("Job not found")
        if job["status"] != "analyzed":
            raise ValueError("Yeniden üretme sadece analiz tamamlandıktan sonra kullanılabilir.")

        config = job["config"]
        target_fields = self._get_batch_target_fields(config)
        if field_key not in target_fields:
            raise ValueError("Bu alan bu iş için seçilmemiş.")
        if field_key not in BATCH_FIELD_TO_AI_FIELD:
            raise ValueError("Desteklenmeyen alan.")

        product = await db.get_product(item["product_id"])
        if product is None:
            raise ValueError("Product not found")

        score = analyze_product(product, self._config.seo_target_keywords)
        system_prompt = self._build_batch_runtime_prompt(config)
        base_suggestion = self._build_suggestion_from_batch_item(product, item)
        existing_field_errors = self._get_batch_item_field_errors(item)
        suggestion, field_errors = await self._generate_batch_suggestion(
            product,
            score,
            config,
            system_prompt,
            field_keys=[field_key],
            base_suggestion=base_suggestion,
        )
        merged_field_errors = {**existing_field_errors, **field_errors}
        if field_key not in field_errors:
            merged_field_errors.pop(field_key, None)
        after_score, suggestion_data, has_suggestions = self._build_batch_item_result(
            product,
            suggestion,
            target_fields,
            merged_field_errors,
        )
        await db.update_batch_item(
            item_id,
            status="analyzed" if has_suggestions else "skipped",
            score_before=score.total_score,
            score_after=after_score if has_suggestions else None,
            skip_reason=None if has_suggestions else self._build_batch_skip_reason(config),
            suggestion_data=suggestion_data,
        )
        await self._refresh_batch_job_metrics(job["id"])
        updated_item = await db.get_batch_item(item_id)
        if updated_item is None:
            raise ValueError("Item not found after update")
        return updated_item

    async def update_batch_item_decision(
        self,
        item_id: int,
        decision: str,
        revised_data: dict[str, Any] | None = None,
    ) -> dict:
        item = await db.get_batch_item(item_id)
        if item is None:
            raise ValueError("Item not found")

        if decision not in ("approved", "rejected", "revised"):
            raise ValueError("decision must be approved, rejected, or revised")

        status = "approved" if decision in ("approved", "revised") else "rejected"
        update_kwargs: dict[str, Any] = {"status": status}

        if revised_data:
            job = await db.get_batch_job(item["job_id"])
            if job is None:
                raise ValueError("Job not found")

            product = await db.get_product(item["product_id"])
            if product is None:
                raise ValueError("Product not found")

            target_fields = self._get_batch_target_fields(job["config"])
            base_data = item.get("suggestion_data") if isinstance(item, dict) else None
            merged_item = {
                "suggestion_data": dict(base_data) if isinstance(base_data, dict) else {},
            }
            field_errors = self._get_batch_item_field_errors(item)

            for field_key, raw_value in revised_data.items():
                if field_key not in target_fields or field_key not in BATCH_FIELD_TO_AI_FIELD:
                    continue
                merged_item["suggestion_data"][f"suggested_{field_key}"] = "" if raw_value is None else str(raw_value)
                field_errors.pop(field_key, None)

            score = analyze_product(product, self._config.seo_target_keywords)
            suggestion = self._build_suggestion_from_batch_item(product, merged_item)
            after_score, next_suggestion_data, has_suggestions = self._build_batch_item_result(
                product,
                suggestion,
                target_fields,
                field_errors,
            )
            update_kwargs["score_before"] = score.total_score
            update_kwargs["score_after"] = after_score if has_suggestions else None
            update_kwargs["suggestion_data"] = next_suggestion_data
            if has_suggestions:
                update_kwargs["skip_reason"] = None

        await db.update_batch_item(item_id, **update_kwargs)
        updated_item = await db.get_batch_item(item_id)
        if updated_item is None:
            raise ValueError("Item not found after update")
        return updated_item

    async def run_analysis(self, job_id: str, product_ids: list[str], config: Any) -> None:
        """
        Generate AI suggestions for each selected product.
        Creates batch_items with suggestion_data and scores.
        Transitions job to 'analyzed' when done.
        """
        all_products = await db.get_all_products()
        product_map = {p.id: p for p in all_products}

        system_prompt = self._build_batch_runtime_prompt(config)
        processed = 0
        skipped = 0
        score_befores: list[float] = []
        score_afters: list[float] = []

        def _avg(vals: list[float]) -> float:
            return sum(vals) / len(vals) if vals else 0

        for pid in product_ids:
            # Check cancellation
            current_job = await db.get_batch_job(job_id)
            if not current_job or current_job["status"] == "cancelled":
                logger.info("Analysis job %s cancelled at %d/%d", job_id, processed, len(product_ids))
                break

            product = product_map.get(pid)
            if not product:
                continue

            score = analyze_product(product, self._config.seo_target_keywords)

            item_id = await db.create_batch_item(
                job_id=job_id,
                product_id=product.id,
                product_name=product.name,
                status="pending",
                score_before=score.total_score,
            )

            try:
                suggestion, field_errors = await self._generate_batch_suggestion(product, score, config, system_prompt)
                target_fields = self._get_batch_target_fields(config)
                after_score, suggestion_data, has_suggestions = self._build_batch_item_result(
                    product,
                    suggestion,
                    target_fields,
                    field_errors,
                )

                if has_suggestions:
                    await db.update_batch_item(
                        item_id,
                        status="analyzed",
                        score_after=after_score,
                        suggestion_data=suggestion_data,
                    )
                    score_befores.append(score.total_score)
                    score_afters.append(after_score)
                    processed += 1
                else:
                    skip_reason = self._build_batch_skip_reason(config)
                    await db.update_batch_item(
                        item_id,
                        status="skipped",
                        score_after=None,
                        skip_reason=skip_reason,
                        suggestion_data=suggestion_data,
                    )
                    skipped += 1
            except Exception as exc:
                logger.warning("Analysis failed for %s: %s", product.id, exc)
                await db.update_batch_item(item_id, status="failed", skip_reason=str(exc)[:200])
                skipped += 1

            await db.update_batch_job(
                job_id,
                processed_count=processed,
                skipped_count=skipped,
                avg_score_before=_avg(score_befores),
                avg_score_after=_avg(score_afters),
            )

        await db.update_batch_job(
            job_id,
            status="analyzed",
            processed_count=processed,
            skipped_count=skipped,
            avg_score_before=_avg(score_befores),
            avg_score_after=_avg(score_afters),
        )
        await self._refresh_batch_job_metrics(job_id)
        logger.info("Analysis job %s done: %d analyzed, %d skipped", job_id, processed, skipped)

    async def apply_batch_job(
        self,
        job_id: str,
        config: Any,
        *,
        permission_rules: list[PermissionRule] | None = None,
    ) -> None:
        """Apply approved suggestions to ikas for items with status='approved'."""
        await self._require_permission(
            "bulk_apply",
            target=job_id,
            source="product_manager.apply_batch_job",
            metadata={"job_id": job_id, "dry_run": self._config.dry_run},
            runtime_rules=permission_rules,
        )
        items = await db.get_batch_items(job_id)
        approved = [i for i in items if i["status"] == "approved"]
        target_fields = set(self._get_batch_target_fields(config))

        all_products = await db.get_all_products()
        product_map = {p.id: p for p in all_products}

        # Reset progress counters so the UI tracks apply-phase progress
        await db.update_batch_job(
            job_id,
            processed_count=0,
            skipped_count=0,
            total_count=len(approved),
        )

        applied = 0
        failed = 0
        for item in approved:
            current_job = await db.get_batch_job(job_id)
            if not current_job or current_job["status"] == "cancelled":
                break

            product_id = item["product_id"]
            product = product_map.get(product_id)
            if not product:
                continue

            try:
                suggestion = self._build_suggestion_from_batch_item(product, item)
                if not any(self._get_batch_field_value(suggestion, field).strip() for field in target_fields):
                    suggestion = await db.get_latest_suggestion_by_product(product_id)
                if not suggestion:
                    await db.update_batch_item(item["id"], status="skipped", skip_reason="Öneri bulunamadı")
                    continue

                rollback_data = {
                    "name": product.name,
                    "description": product.description or "",
                    "description_translations": product.description_translations or {},
                    "meta_title": product.meta_title or "",
                    "meta_description": product.meta_description or "",
                }

                if not self._config.dry_run:
                    updates: dict[str, Any] = {}
                    if (not target_fields or "name" in target_fields) and suggestion.suggested_name:
                        updates["name"] = suggestion.suggested_name
                    if (not target_fields or "description" in target_fields) and suggestion.suggested_description:
                        updates["description"] = suggestion.suggested_description
                    desc_translations = {}
                    if (not target_fields or "description" in target_fields) and suggestion.suggested_description:
                        desc_translations["tr"] = suggestion.suggested_description
                    if (not target_fields or "description_en" in target_fields) and suggestion.suggested_description_en:
                        desc_translations["en"] = suggestion.suggested_description_en
                    if desc_translations:
                        updates["description_translations"] = desc_translations
                    if (not target_fields or "meta_title" in target_fields) and suggestion.suggested_meta_title:
                        updates["meta_title"] = suggestion.suggested_meta_title
                    if (not target_fields or "meta_description" in target_fields) and suggestion.suggested_meta_description:
                        updates["meta_description"] = suggestion.suggested_meta_description
                    if updates:
                        await self._ikas.update_product(product_id, updates)
                        await db.log_operation("batch_apply", product_id, updates, True)

                # Post-apply verification: re-fetch from ikas, re-score, update cache
                score_after_val = item.get("score_after")
                if not self._config.dry_run:
                    try:
                        updated_product = await self._ikas.get_product_by_id(product_id)
                        if updated_product:
                            await db.save_product(updated_product)
                            new_score = analyze_product(updated_product, self._config.seo_target_keywords)
                            await db.save_scores([new_score])
                            score_after_val = new_score.total_score
                            logger.info(
                                "Post-apply verify %s: score %s → %s",
                                product_id, item.get("score_before"), score_after_val,
                            )
                    except Exception as verify_exc:
                        logger.warning("Post-apply verify failed for %s: %s", product_id, verify_exc)

                await db.update_batch_item(
                    item["id"],
                    status="applied" if not self._config.dry_run else "approved",
                    rollback_data=rollback_data,
                    score_after=score_after_val,
                )
                # Log the score change event
                if not self._config.dry_run:
                    await db.insert_score_change_log(
                        product_id=product_id,
                        product_name=item.get("product_name", product.name),
                        operation="batch_apply",
                        score_before=item.get("score_before"),
                        score_after=score_after_val,
                        job_id=job_id,
                    )
                applied += 1
            except Exception as exc:
                failed += 1
                logger.error("Batch apply failed for product %s: %s", product_id, exc)
                await db.update_batch_item(
                    item["id"],
                    status="failed",
                    skip_reason=str(exc)[:500],
                    score_after=None,
                )

            await db.update_batch_job(job_id, processed_count=applied + failed)

        status = "completed" if failed == 0 else "completed_with_errors"
        await db.update_batch_job(job_id, status=status)
        await self._refresh_batch_job_metrics(job_id)
        logger.info("Batch apply %s done: %d applied, %d failed", job_id, applied, failed)

    async def rollback_product(
        self,
        product_id: str,
        rollback_data: dict,
        *,
        permission_rules: list[PermissionRule] | None = None,
    ) -> bool:
        """Restore original product fields to ikas."""
        try:
            await self._require_permission(
                "rollback",
                target=product_id,
                source="product_manager.rollback_product",
                metadata={"fields": sorted(rollback_data.keys())},
                runtime_rules=permission_rules,
            )
            return await self._ikas.update_product(product_id, rollback_data)
        except PermissionDecisionError:
            raise
        except Exception as exc:
            logger.error("Rollback failed for %s: %s", product_id, exc)
            return False
