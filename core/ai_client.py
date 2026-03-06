"""Unified AI client supporting multiple providers.

Providers:
  - anthropic  : Anthropic Claude (direct SDK)
  - openai     : OpenAI GPT models
  - gemini     : Google Gemini via OpenAI-compatible endpoint
  - openrouter : OpenRouter (any model)
  - ollama     : Local Ollama (OpenAI-compatible)
  - custom     : Any OpenAI-compatible endpoint
  - none       : Analysis only, raises error if rewrite is attempted
"""

import json
import logging
from typing import List, Optional

from core.models import AppConfig, Product, SeoScore, SeoSuggestion

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
Mevcut Turkce Aciklama: {description}
Mevcut Ingilizce Aciklama: {description_en}
Kategori: {category}
Mevcut SEO Sorunlari: {issues}
Hedef Keywordler: {keywords}

Su alanlari optimize et ve JSON olarak dondur:
{{
    "suggested_name": "...",
    "suggested_description": "...",
    "suggested_description_en": "...",
    "suggested_meta_title": "...",
    "suggested_meta_description": "..."
}}"""

# Default models per provider
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.2",
    "custom": "gpt-3.5-turbo",
}

# OpenAI-compatible base URLs
PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
}


def _get_system_prompt(config: AppConfig) -> str:
    languages = {lang.lower() for lang in config.store_languages}
    if "tr" in languages:
        return SYSTEM_PROMPT_TR
    return SYSTEM_PROMPT_EN


def _parse_response_text(raw_text: str) -> dict:
    """Strip markdown fences and parse JSON from AI response."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse AI response as JSON: {text[:200]}")
        raise ValueError("AI response was not valid JSON")


def _build_suggestion(product: Product, result: dict) -> SeoSuggestion:
    return SeoSuggestion(
        product_id=product.id,
        original_name=product.name,
        suggested_name=result.get("suggested_name"),
        original_description=product.description,
        suggested_description=result.get("suggested_description", ""),
        original_description_en=product.description_translations.get("en", ""),
        suggested_description_en=result.get("suggested_description_en", ""),
        original_meta_title=product.meta_title,
        suggested_meta_title=result.get("suggested_meta_title", ""),
        original_meta_description=product.meta_description,
        suggested_meta_description=result.get("suggested_meta_description", ""),
        status="pending",
    )


class BaseAIClient:
    """Shared batch logic for all providers."""

    def rewrite_product(
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


class NoneAIClient(BaseAIClient):
    """Placeholder when provider is 'none'. Only analysis is available."""

    def rewrite_product(self, product, score, target_keywords=None):
        raise RuntimeError(
            "AI provider 'none' secildi. Yeniden yazma icin Ayarlar'dan bir provider secin."
        )


class AnthropicAIClient(BaseAIClient):
    def __init__(self, config: AppConfig) -> None:
        import anthropic as _anthropic

        api_key = config.ai_api_key or config.anthropic_api_key
        self._client = _anthropic.Anthropic(api_key=api_key)
        self._model = config.ai_model_name or DEFAULT_MODELS["anthropic"]
        self._max_tokens = config.ai_max_tokens
        self._config = config
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
        model = self._model.lower()
        if "opus" in model:
            return round(
                self._total_input_tokens * 15.0 / 1_000_000
                + self._total_output_tokens * 75.0 / 1_000_000,
                4,
            )
        elif "sonnet" in model:
            return round(
                self._total_input_tokens * 3.0 / 1_000_000
                + self._total_output_tokens * 15.0 / 1_000_000,
                4,
            )
        else:  # haiku
            return round(
                self._total_input_tokens * 0.80 / 1_000_000
                + self._total_output_tokens * 4.0 / 1_000_000,
                4,
            )

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        keywords = target_keywords or self._config.seo_target_keywords
        user_prompt = USER_PROMPT_TEMPLATE.format(
            name=product.name,
            description=product.description[:2000],
            description_en=product.description_translations.get("en", "")[:2000],
            category=product.category or "Belirtilmemis",
            issues="; ".join(score.issues) if score.issues else "Yok",
            keywords=", ".join(keywords) if keywords else "Belirtilmemis",
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_get_system_prompt(self._config),
            messages=[{"role": "user", "content": user_prompt}],
        )
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        logger.info(
            f"Anthropic API call: {response.usage.input_tokens} input, "
            f"{response.usage.output_tokens} output tokens"
        )
        result = _parse_response_text(response.content[0].text)
        return _build_suggestion(product, result)


class OpenAICompatibleClient(BaseAIClient):
    """Handles OpenAI, Gemini (OpenAI-compat), OpenRouter, Ollama, and Custom endpoints."""

    def __init__(self, config: AppConfig, provider: str) -> None:
        from openai import OpenAI

        self._provider = provider
        self._config = config

        # Resolve base URL
        if provider == "custom":
            base_url = config.ai_base_url or None
        elif config.ai_base_url:
            base_url = config.ai_base_url
        else:
            base_url = PROVIDER_BASE_URLS.get(provider)

        # Ollama doesn't need a real API key
        api_key = config.ai_api_key or ("ollama" if provider == "ollama" else "no-key")

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = config.ai_model_name or DEFAULT_MODELS.get(provider, "gpt-4o-mini")
        self._temperature = config.ai_temperature
        self._max_tokens = config.ai_max_tokens

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        keywords = target_keywords or self._config.seo_target_keywords
        user_prompt = USER_PROMPT_TEMPLATE.format(
            name=product.name,
            description=product.description[:2000],
            description_en=product.description_translations.get("en", "")[:2000],
            category=product.category or "Belirtilmemis",
            issues="; ".join(score.issues) if score.issues else "Yok",
            keywords=", ".join(keywords) if keywords else "Belirtilmemis",
        )
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": _get_system_prompt(self._config)},
                {"role": "user", "content": user_prompt},
            ],
        )
        logger.info(
            f"{self._provider} API call: "
            f"{response.usage.prompt_tokens if response.usage else '?'} input tokens"
        )
        raw_text = response.choices[0].message.content or ""
        result = _parse_response_text(raw_text)
        return _build_suggestion(product, result)


def create_ai_client(config: AppConfig) -> BaseAIClient:
    """Factory: return the right AI client based on config.ai_provider."""
    provider = config.ai_provider.lower()

    if provider == "none":
        return NoneAIClient()
    elif provider == "anthropic":
        return AnthropicAIClient(config)
    elif provider in ("openai", "gemini", "openrouter", "ollama", "custom"):
        return OpenAICompatibleClient(config, provider)
    else:
        logger.warning(f"Unknown AI provider '{provider}', defaulting to NoneAIClient")
        return NoneAIClient()
