"""Base AI client class and NoneAIClient placeholder."""

import logging
from typing import List, Optional

from core.models import Product, SeoScore, SeoSuggestion

logger = logging.getLogger(__name__)


class BaseAIClient:
    """Shared batch logic for all providers."""

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        raise NotImplementedError

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> str | tuple[str, str]:
        """Rewrite a single field and return the new value as plain text,
        or (value, thinking_text) tuple when thinking mode is on."""
        raise NotImplementedError

    def translate_description_to_en(
        self,
        product: Product,
    ) -> str | tuple[str, str]:
        raise NotImplementedError

    def rewrite_product_for_geo(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        raise NotImplementedError

    def rewrite_products_batch(
        self,
        products: List[tuple[Product, SeoScore]],
        target_keywords: Optional[List[str]] = None,
    ) -> List[SeoSuggestion]:
        suggestions = []
        for product, score in products:
            try:
                suggestion = self.rewrite_product(product, score, target_keywords)
                suggestions.append(suggestion)
            except Exception as e:
                logger.error(f"Failed to rewrite product {product.id}: {e}")
        return suggestions

    @property
    def total_tokens(self) -> dict:
        return {"input": 0, "output": 0, "estimated_cost": 0.0}

    @property
    def last_response_meta(self) -> dict:
        return {}

    def cancel_active_request(self) -> bool:
        return False


class NoneAIClient(BaseAIClient):
    """Placeholder when provider is 'none'. Only analysis is available."""

    def rewrite_product(self, product, score, target_keywords=None):
        raise RuntimeError(
            "AI provider 'none' secildi. Yeniden yazma icin Ayarlar'dan bir provider secin."
        )

    def rewrite_field(self, field, product, score, target_keywords=None):
        raise RuntimeError(
            "AI provider 'none' secildi. Yeniden yazma icin Ayarlar'dan bir provider secin."
        )

    def translate_description_to_en(self, product):
        raise RuntimeError(
            "AI provider 'none' secildi. Ceviri icin Ayarlar'dan bir provider secin."
        )

    def rewrite_product_for_geo(self, product, score, target_keywords=None):
        raise RuntimeError(
            "AI provider 'none' secildi. GEO yeniden yazma icin Ayarlar'dan bir provider secin."
        )
