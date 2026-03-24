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
from core.agent.tools import create_seo_rewrite_toolkit
from core.utils.html import html_to_plain_text
from core.chat import ChatService
from core.clients.ikas import IkasClient
from core.models import AgentEvent, AppConfig, ChatResponse, Product, SeoScore, SeoSuggestion
from core.utils.presentation import format_prompt_display, get_en_description_value, get_tr_description_value
from core.prompt_store import REWRITE_AGENT_SYSTEM_PROMPT, BATCH_AGENT_SYSTEM_PROMPT, ensure_prompt_files
from core.services.provider import (
    discover_provider_models,
    get_lm_studio_live_status,
    get_provider_health,
    test_settings_connection,
)
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

TScore = TypeVar("TScore")


class ProductManager:
    def __init__(self) -> None:
        ensure_prompt_files()
        self._ikas = IkasClient()
        self._config = get_config()
        self._ai: BaseAIClient = create_ai_client(self._config)
        self._chat: ChatService = ChatService(self._config)

    def reload_ai_client(self) -> None:
        """Recreate AI client after config change."""
        from config.settings import get_config as _get
        self._config = _get()
        self._ai = create_ai_client(self._config)
        self._chat = ChatService(self._config)

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

    async def clear_local_data(self) -> dict[str, int]:
        counts = await db.clear_all_data()
        logger.info("Cleared local cache: %s", counts)
        return counts

    async def score_products(self, products: List[Product]) -> List[tuple[Product, SeoScore]]:
        scored_products: List[tuple[Product, SeoScore]] = []
        scores: List[SeoScore] = []

        for product in products:
            score = analyze_product(product, self._config.seo_target_keywords)
            scored_products.append((product, score))
            scores.append(score)

        await db.save_scores(scores)
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

    async def rewrite_product(self, product: Product, score: SeoScore) -> SeoSuggestion:
        if supports_tool_calling(self._config) and self._config.ai_provider != "none":
            return await self._agentic_rewrite_product(product, score)
        # Fallback: single-shot rewrite
        suggestion = self._ai.rewrite_product(product, score)
        await db.save_suggestion(suggestion)
        return suggestion

    async def _agentic_rewrite_product(self, product: Product, score: SeoScore) -> SeoSuggestion:
        """Run the agentic rewrite pipeline with tool calling."""
        toolkit = create_seo_rewrite_toolkit()
        orchestrator = AgentOrchestrator(
            config=self._config,
            toolkit=toolkit,
            system_prompt=REWRITE_AGENT_SYSTEM_PROMPT,
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
            suggestion = self._ai.rewrite_product(product, score)
            await db.save_suggestion(suggestion)
        return suggestion

    async def stream_rewrite_product(self, product_id: str) -> AsyncIterator[AgentEvent]:
        """Stream the agentic rewrite pipeline for a product."""
        product = await db.get_product(product_id)
        if product is None:
            yield AgentEvent(type="error", content=f"Product '{product_id}' not found.")
            return
        score = analyze_product(product, self._config.seo_target_keywords)

        toolkit = create_seo_rewrite_toolkit()
        orchestrator = AgentOrchestrator(
            config=self._config,
            toolkit=toolkit,
            system_prompt=REWRITE_AGENT_SYSTEM_PROMPT,
            max_iterations=8,
        )
        async for event in orchestrator.stream(
            user_message=f"Bu urunun SEO'sunu optimize et: {product.name} (ID: {product.id})",
            context={"product_id": product.id, "current_score": score.model_dump()},
        ):
            yield event

    def rewrite_field(self, field: str, product: Product, score: SeoScore) -> tuple[str, str]:
        result = self._ai.rewrite_field(field, product, score)
        if isinstance(result, tuple):
            return result
        return result, ""

    def translate_description_to_en(self, product: Product) -> tuple[str, str]:
        result = self._ai.translate_description_to_en(product)
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

    async def apply_suggestions(self, suggestions: List[SeoSuggestion]) -> int:
        applied = 0
        for suggestion in suggestions:
            if suggestion.status != "approved":
                continue
            updates = {}
            if suggestion.suggested_name:
                updates["name"] = suggestion.suggested_name
            if suggestion.suggested_description:
                updates["description"] = suggestion.suggested_description

            description_translations = {}
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
                success = await self._ikas.update_product(suggestion.product_id, updates)
                if success:
                    await db.update_suggestion_status(suggestion.product_id, "applied")
                    await db.log_operation("apply", suggestion.product_id, updates, True)
                    applied += 1
            except Exception as e:
                logger.error(f"Failed to apply suggestion for {suggestion.product_id}: {e}")
                await db.log_operation("apply", suggestion.product_id, {"error": str(e)}, False)

        logger.info(f"Applied {applied}/{len(suggestions)} suggestions")
        return applied

    async def apply_approved_suggestions(self) -> tuple[int, bool]:
        approved = await self.get_approved_suggestions()
        if not approved:
            return 0, False
        return await self.apply_suggestions(approved), True

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

    def _build_batch_system_prompt(self, config: Any) -> str:
        """Build BATCH_AGENT_SYSTEM_PROMPT augmented with user-defined constraints."""
        rules: list[str] = []
        if getattr(config, "preserve_specs", True):
            rules.append(
                "Teknik özellikleri (materyal, boyut, ağırlık) DEĞİŞTİRME, "
                "sadece biçimlendir ve SEO açısından zenginleştir."
            )
        if getattr(config, "prevent_cannibalization", True):
            rules.append(
                "Benzer ürün gruplarında LSI (Latent Semantic Indexing) varyasyonları "
                "kullan; anahtar kelime çakışmasını önle."
            )
        pct = getattr(config, "max_title_change_pct", 20)
        if pct < 100:
            rules.append(
                f"Başlık (title) etiketinde maksimum %{pct} değişiklik yap; "
                "mevcut ana anahtar kelimeyi koru."
            )
        target_fields = getattr(config, "target_fields", None)
        if target_fields:
            field_labels = [TARGET_FIELD_LABELS.get(f, f) for f in target_fields]
            rules.append(
                "SADECE şu alanları güncelle: " + ", ".join(field_labels) + ". "
                "Diğer alanlara dokunma, save_suggestion çağrısında diğer alanlara boş string ver."
            )
        if not rules:
            return BATCH_AGENT_SYSTEM_PROMPT
        constraints_block = "\n\nKISITLAMALAR (Bu kurallara kesinlikle uy):\n" + "\n".join(
            f"- {r}" for r in rules
        )
        return BATCH_AGENT_SYSTEM_PROMPT + constraints_block

    async def _run_agent_for_product(
        self, product: Product, score: SeoScore, system_prompt: str,
    ) -> SeoSuggestion | None:
        """Run the agentic rewrite and return the saved suggestion, or None."""
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
            "description": (product.description or "")[:1000],
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
        return await db.get_latest_suggestion_by_product(product.id)

    async def _fallback_rewrite(
        self, product: Product, score: SeoScore, config: Any,
    ) -> SeoSuggestion | None:
        """Direct AI rewrite as fallback when the agent loop fails to save."""
        try:
            suggestion = self._ai.rewrite_product(product, score)
        except Exception as exc:
            logger.warning("Fallback rewrite failed for %s: %s", product.id, exc)
            return None

        # Filter by target_fields: blank out non-target suggested fields
        target_fields = getattr(config, "target_fields", None)
        if target_fields:
            field_to_attr = {
                "name": "suggested_name",
                "description": "suggested_description",
                "description_en": "suggested_description_en",
                "meta_title": "suggested_meta_title",
                "meta_description": "suggested_meta_description",
            }
            blanks = {}
            for field_key, attr in field_to_attr.items():
                if field_key not in target_fields:
                    blanks[attr] = ""
            if blanks:
                suggestion = suggestion.model_copy(update=blanks)

        await db.save_or_update_pending_suggestion(suggestion)
        return suggestion

    async def run_analysis(self, job_id: str, product_ids: list[str], config: Any) -> None:
        """
        Generate AI suggestions for each selected product.
        Creates batch_items with suggestion_data and scores.
        Transitions job to 'analyzed' when done.
        """
        all_products = await db.get_all_products()
        product_map = {p.id: p for p in all_products}

        system_prompt = self._build_batch_system_prompt(config)
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
                suggestion = await self._run_agent_for_product(product, score, system_prompt)

                # Fallback: if agent didn't save, use direct AI rewrite
                if suggestion is None:
                    logger.warning(
                        "Agent did not save suggestion for %s; falling back to direct rewrite",
                        product.id,
                    )
                    suggestion = await self._fallback_rewrite(product, score, config)

                if suggestion is None:
                    target_fields = getattr(config, "target_fields", None)
                    if target_fields:
                        field_labels = [TARGET_FIELD_LABELS.get(f, f) for f in target_fields]
                        skip_reason = f"Öneri oluşturulamadı (hedef alanlar: {', '.join(field_labels)})"
                    else:
                        skip_reason = "Öneri oluşturulamadı"
                    await db.update_batch_item(item_id, status="skipped", skip_reason=skip_reason)
                    skipped += 1
                else:
                    updated = product.model_copy(update={
                        "name": suggestion.suggested_name or product.name,
                        "description": suggestion.suggested_description or product.description,
                        "meta_title": suggestion.suggested_meta_title or product.meta_title,
                        "meta_description": suggestion.suggested_meta_description or product.meta_description,
                    })
                    after_score = analyze_product(updated, self._config.seo_target_keywords).total_score
                    suggestion_data = {
                        "original_name": product.name,
                        "suggested_name": suggestion.suggested_name or "",
                        "original_meta_title": product.meta_title or "",
                        "suggested_meta_title": suggestion.suggested_meta_title or "",
                        "original_meta_description": product.meta_description or "",
                        "suggested_meta_description": suggestion.suggested_meta_description or "",
                        "original_description": (product.description or "")[:500],
                        "suggested_description": (suggestion.suggested_description or "")[:500],
                    }
                    await db.update_batch_item(
                        item_id,
                        status="analyzed",
                        score_after=after_score,
                        suggestion_data=suggestion_data,
                    )
                    score_befores.append(score.total_score)
                    score_afters.append(after_score)
                    processed += 1
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
        logger.info("Analysis job %s done: %d analyzed, %d skipped", job_id, processed, skipped)

    async def apply_batch_job(self, job_id: str, config: Any) -> None:
        """Apply approved suggestions to ikas for items with status='approved'."""
        items = await db.get_batch_items(job_id)
        approved = [i for i in items if i["status"] == "approved"]
        target_fields = set(getattr(config, "target_fields", []) or [])

        all_products = await db.get_all_products()
        product_map = {p.id: p for p in all_products}

        applied = 0
        for item in approved:
            current_job = await db.get_batch_job(job_id)
            if not current_job or current_job["status"] == "cancelled":
                break

            product_id = item["product_id"]
            suggestion = await db.get_latest_suggestion_by_product(product_id)
            if not suggestion:
                await db.update_batch_item(item["id"], status="skipped", skip_reason="Öneri bulunamadı")
                continue

            product = product_map.get(product_id)
            if not product:
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

            await db.update_batch_item(
                item["id"],
                status="applied" if not self._config.dry_run else "approved",
                rollback_data=rollback_data,
            )
            applied += 1

        await db.update_batch_job(job_id, status="completed")
        logger.info("Batch apply %s done: %d applied", job_id, applied)

    async def rollback_product(self, product_id: str, rollback_data: dict) -> bool:
        """Restore original product fields to ikas."""
        try:
            return await self._ikas.update_product(product_id, rollback_data)
        except Exception as exc:
            logger.error("Rollback failed for %s: %s", product_id, exc)
            return False
