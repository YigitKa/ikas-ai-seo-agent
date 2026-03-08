import logging
from typing import List, Optional

from config.settings import get_config, save_config_to_env
from core.ai_client import (
    BaseAIClient,
    build_en_translation_request,
    build_field_rewrite_request,
    build_product_rewrite_request,
    create_ai_client,
)
from core.chat_service import ChatService
from core.ikas_client import IkasClient
from core.models import AppConfig, ChatResponse, Product, SeoScore, SeoSuggestion
from core.presentation import format_prompt_display, get_tr_description_value
from core.provider_service import (
    discover_provider_models,
    get_lm_studio_live_status,
    get_provider_health,
    test_settings_connection,
)
from core.seo_analyzer import analyze_product
from data import db
from core.prompt_store import ensure_prompt_files

logger = logging.getLogger(__name__)


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
        db.save_products(products)
        logger.info(f"Fetched and cached {len(products)} products (page {page})")
        return products

    async def fetch_and_score_products(self, limit: int = 50, page: int = 1) -> tuple[list[tuple[Product, SeoScore]], int]:
        products = await self.fetch_products(limit=limit, page=page)
        return self.score_products(products), self._ikas.total_count

    async def sync_all_products(self, batch_size: int = 50) -> tuple[int, int]:
        products = await self._ikas.get_all_products(batch_size=batch_size)
        db.save_products(products)
        self.score_products(products)
        logger.info("Fetched and cached %s/%s products (full sync)", len(products), self._ikas.total_count)
        return len(products), self._ikas.total_count

    async def fetch_product(self, product_id: str) -> Optional[Product]:
        product = await self._ikas.get_product_by_id(product_id)
        if product:
            db.save_product(product)
        return product

    def get_cached_products(self) -> List[Product]:
        return db.get_all_products()

    def clear_local_data(self) -> dict[str, int]:
        counts = db.clear_all_data()
        logger.info("Cleared local cache: %s", counts)
        return counts

    def score_products(self, products: List[Product]) -> List[tuple[Product, SeoScore]]:
        scored_products: List[tuple[Product, SeoScore]] = []
        scores: List[SeoScore] = []

        for product in products:
            score = analyze_product(product, self._config.seo_target_keywords)
            scored_products.append((product, score))
            scores.append(score)

        db.save_scores(scores)
        logger.info("Analyzed %s products", len(products))
        return scored_products

    def analyze_product(self, product: Product) -> SeoScore:
        return self.score_products([product])[0][1]

    def filter_products_by_score(
        self,
        products_data: List[tuple[Product, SeoScore]],
        threshold: int | None = None,
    ) -> List[tuple[Product, SeoScore]]:
        cutoff = threshold if threshold is not None else self._config.seo_low_score_threshold
        return [(p, s) for p, s in products_data if s.total_score < cutoff]

    def analyze_products(
        self,
        products: List[Product],
        threshold: int = 100,
    ) -> List[tuple[Product, SeoScore]]:
        scored_products = self.score_products(products)
        results = [(product, score) for product, score in scored_products if score.total_score <= threshold]
        logger.info(f"Analyzed {len(products)} products, {len(results)} below threshold {threshold}")
        return results

    def rewrite_products(
        self,
        products_with_scores: List[tuple[Product, SeoScore]],
    ) -> List[SeoSuggestion]:
        suggestions = self._ai.rewrite_products_batch(products_with_scores)
        for s in suggestions:
            db.save_suggestion(s)
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

    def rewrite_product(self, product: Product, score: SeoScore) -> SeoSuggestion:
        suggestion = self._ai.rewrite_product(product, score)
        db.save_suggestion(suggestion)
        return suggestion

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

    def approve_pending_suggestion(self, suggestion: SeoSuggestion) -> None:
        self.save_or_update_pending_suggestion(suggestion)
        self.approve_suggestion(suggestion.product_id)

    def reject_pending_suggestion(self, product_id: str) -> None:
        self.reject_suggestion(product_id)

    def save_settings(self, values: dict) -> None:
        save_config_to_env(values)
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
                    db.update_suggestion_status(suggestion.product_id, "applied")
                    db.log_operation("apply", suggestion.product_id, updates, True)
                    applied += 1
            except Exception as e:
                logger.error(f"Failed to apply suggestion for {suggestion.product_id}: {e}")
                db.log_operation("apply", suggestion.product_id, {"error": str(e)}, False)

        logger.info(f"Applied {applied}/{len(suggestions)} suggestions")
        return applied

    async def apply_approved_suggestions(self) -> tuple[int, bool]:
        approved = self.get_approved_suggestions()
        if not approved:
            return 0, False
        return await self.apply_suggestions(approved), True

    def get_pending_suggestions(self) -> List[SeoSuggestion]:
        return db.get_pending_suggestions()

    def get_approved_suggestions(self) -> List[SeoSuggestion]:
        return db.get_approved_suggestions()

    def get_pending_suggestion_count(self) -> int:
        return db.count_suggestions("pending")

    def get_suggestion_product_ids(self, status: str) -> set[str]:
        return db.get_suggestion_product_ids(status)

    def get_latest_suggestion(self, product_id: str) -> Optional[SeoSuggestion]:
        return db.get_latest_suggestion_by_product(product_id)

    def update_latest_pending_suggestion(self, suggestion: SeoSuggestion) -> None:
        db.update_latest_pending_suggestion(suggestion)

    def save_or_update_pending_suggestion(self, suggestion: SeoSuggestion) -> None:
        db.save_or_update_pending_suggestion(suggestion)

    def approve_suggestion(self, product_id: str) -> None:
        db.update_suggestion_status(product_id, "approved")

    def reject_suggestion(self, product_id: str) -> None:
        db.update_suggestion_status(product_id, "rejected")

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
