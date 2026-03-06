import json
import logging
from typing import List, Optional

import anthropic

from config.settings import get_config
from core.models import Product, SeoScore, SeoSuggestion

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TR = """Sen bir e-ticaret SEO uzmanisin. Gorevin ikas magaza urunlerinin
iceriklerini Turk kullanicilar ve Google TR icin optimize etmek.

Kurallar:
- Dogal, satis odakli Turkce kullan
- Aciklama 200-400 kelime arasi
- Ilk paragrafta ana keyword gecmeli
- Meta title max 60 karakter, marka adiyla bitir
- Meta description max 155 karakter, CTA icermeli
- HTML tag kullanma, duz metin dondur
- Abartili reklam dili kullanma
- Urunun gercek ozelliklerine sadik kal

SADECE JSON dondur, baska hicbir sey yazma."""

SYSTEM_PROMPT_EN = """You are an e-commerce SEO specialist. Your task is to optimize
product content for search engines and users.

Rules:
- Use natural, sales-oriented language
- Description should be 200-400 words
- Main keyword should appear in the first paragraph
- Meta title max 60 characters, end with brand name
- Meta description max 155 characters, include CTA
- No HTML tags, return plain text
- No exaggerated advertising language
- Stay faithful to the product's real features

Return ONLY JSON, nothing else."""

USER_PROMPT_TEMPLATE = """Urun Adi: {name}
Mevcut Aciklama: {description}
Kategori: {category}
Mevcut SEO Sorunlari: {issues}
Hedef Keywordler: {keywords}

Su alanlari optimize et ve JSON olarak dondur:
{{
    "suggested_name": "...",
    "suggested_description": "...",
    "suggested_meta_title": "...",
    "suggested_meta_description": "..."
}}"""


class ClaudeClient:
    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        config = get_config()
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._model = model
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    @property
    def total_tokens(self) -> dict:
        return {
            "input": self._total_input_tokens,
            "output": self._total_output_tokens,
            "estimated_cost": self._estimate_cost(),
        }

    def _estimate_cost(self) -> float:
        if "opus" in self._model:
            input_cost = self._total_input_tokens * 15.0 / 1_000_000
            output_cost = self._total_output_tokens * 75.0 / 1_000_000
        elif "sonnet" in self._model:
            input_cost = self._total_input_tokens * 3.0 / 1_000_000
            output_cost = self._total_output_tokens * 15.0 / 1_000_000
        else:  # haiku
            input_cost = self._total_input_tokens * 0.80 / 1_000_000
            output_cost = self._total_output_tokens * 4.0 / 1_000_000
        return round(input_cost + output_cost, 4)

    def _get_system_prompt(self) -> str:
        config = get_config()
        if config.store_language == "tr":
            return SYSTEM_PROMPT_TR
        return SYSTEM_PROMPT_EN

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        config = get_config()
        keywords = target_keywords or config.seo_target_keywords

        user_prompt = USER_PROMPT_TEMPLATE.format(
            name=product.name,
            description=product.description[:2000],
            category=product.category or "Belirtilmemis",
            issues="; ".join(score.issues) if score.issues else "Yok",
            keywords=", ".join(keywords) if keywords else "Belirtilmemis",
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            system=self._get_system_prompt(),
            messages=[{"role": "user", "content": user_prompt}],
        )

        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens

        logger.info(
            f"Claude API call: {response.usage.input_tokens} input, "
            f"{response.usage.output_tokens} output tokens"
        )

        raw_text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            lines = lines[1:]  # remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw_text = "\n".join(lines)

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse Claude response as JSON: {raw_text[:200]}")
            raise ValueError("Claude response was not valid JSON")

        return SeoSuggestion(
            product_id=product.id,
            original_name=product.name,
            suggested_name=result.get("suggested_name"),
            original_description=product.description,
            suggested_description=result.get("suggested_description", ""),
            original_meta_title=product.meta_title,
            suggested_meta_title=result.get("suggested_meta_title", ""),
            original_meta_description=product.meta_description,
            suggested_meta_description=result.get("suggested_meta_description", ""),
            status="pending",
        )

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
