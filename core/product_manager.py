import logging
from typing import List, Optional

from config.settings import get_config
from core.ai_client import BaseAIClient, create_ai_client
from core.ikas_client import IkasClient
from core.models import Product, SeoScore, SeoSuggestion
from core.seo_analyzer import analyze_product
from data import db

logger = logging.getLogger(__name__)


class ProductManager:
    def __init__(self) -> None:
        self._ikas = IkasClient()
        self._config = get_config()
        self._ai: BaseAIClient = create_ai_client(self._config)

    def reload_ai_client(self) -> None:
        """Recreate AI client after config change."""
        from config.settings import get_config as _get
        self._config = _get()
        self._ai = create_ai_client(self._config)

    async def fetch_products(self, limit: int = 50, page: int = 1) -> List[Product]:
        products = await self._ikas.get_products(limit=limit, page=page)
        db.save_products(products)
        logger.info(f"Fetched and cached {len(products)} products (page {page})")
        return products

    async def fetch_product(self, product_id: str) -> Optional[Product]:
        product = await self._ikas.get_product_by_id(product_id)
        if product:
            db.save_product(product)
        return product

    def get_cached_products(self) -> List[Product]:
        return db.get_all_products()

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

    def approve_suggestion(self, product_id: str) -> None:
        db.update_suggestion_status(product_id, "approved")

    def reject_suggestion(self, product_id: str) -> None:
        db.update_suggestion_status(product_id, "rejected")

    def get_token_usage(self) -> dict:
        return self._ai.total_tokens

    def get_last_token_usage(self) -> dict:
        """Token usage of the most recent API call."""
        return getattr(self._ai, 'last_usage', {"input": 0, "output": 0})

    async def test_connection(self) -> bool:
        return await self._ikas.test_connection()

    async def close(self) -> None:
        await self._ikas.close()
