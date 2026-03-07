"""Unified AI client supporting multiple providers.

Providers:
  - anthropic  : Anthropic Claude (direct SDK)
  - openai     : OpenAI GPT models
  - gemini     : Google Gemini via OpenAI-compatible endpoint
  - openrouter : OpenRouter (any model)
  - ollama     : Local Ollama (OpenAI-compatible)
  - lm-studio  : LM Studio local server (OpenAI-compatible)
  - custom     : Any OpenAI-compatible endpoint
  - none       : Analysis only, raises error if rewrite is attempted
"""

import json
import logging
import threading
from typing import List, Optional

import httpx

from core.html_utils import sanitize_html_for_prompt
from core.models import AppConfig, Product, SeoScore, SeoSuggestion
from core.prompt_store import load_prompt_template, render_prompt_template

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TR = """Sen bir e-ticaret SEO uzmanisin. Gorevin ikas magaza urunlerinin
 iceriklerini Turk kullanicilar ve Google TR icin optimize etmek.

Kurallar:
- Dogal, satis odakli Turkce kullan
- Aciklama 200-400 kelime arasi
- Ilk paragrafta ana keyword gecmeli
- Meta title max 60 karakter, marka adiyla bitir
- Meta description max 155 karakter, CTA icermeli
- Aciklama alanlarinda p, br, ul, ol, li, strong ve em gibi basit HTML tagleri kullanabilirsin
- Ad, meta title ve meta description alanlarinda HTML kullanma
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
- You may use simple HTML tags in description fields, such as <p>, <br>, <ul>, <ol>, <li>, <strong>, and <em>
- Do not use HTML in the name, meta title, or meta description fields
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

# Per-field prompt templates – smaller context, single field output
FIELD_PROMPT_TEMPLATES = {
    "name": """Urun Adi: {name}
Kategori: {category}
Hedef Keywordler: {keywords}

Bu urunun adini SEO icin optimize et. Dogal ve aranabilir bir isim olustur.
SADECE JSON dondur:
{{"suggested_name": "..."}}""",

    "meta_title": """Urun Adi: {name}
Kategori: {category}
Hedef Keywordler: {keywords}

Bu urun icin SEO uyumlu meta title yaz. Max 60 karakter, marka adiyla bitir.
SADECE JSON dondur:
{{"suggested_meta_title": "..."}}""",

    "meta_desc": """Urun Adi: {name}
Mevcut Aciklama: {description_short}
Hedef Keywordler: {keywords}

Bu urun icin SEO uyumlu meta description yaz. Max 155 karakter, CTA icermeli.
SADECE JSON dondur:
{{"suggested_meta_description": "..."}}""",

    "desc_en": """Urun Adi: {name}
Mevcut Ingilizce Aciklama: {description_en}
Kategori: {category}
Hedef Keywordler: {keywords}

Rewrite the English product description for SEO. 200-400 words, natural sales language.
Simple HTML is allowed in the description field when useful.
Return ONLY JSON:
{{"suggested_description_en": "..."}}""",
}

# Default models per provider
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.2",
    "lm-studio": "local-model",
    "custom": "gpt-3.5-turbo",
}

# OpenAI-compatible base URLs
PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "lm-studio": "http://localhost:1234/v1",
}


def _get_system_prompt(config: AppConfig) -> str:
    languages = {lang.lower() for lang in config.store_languages}
    if "tr" in languages:
        return SYSTEM_PROMPT_TR
    return SYSTEM_PROMPT_EN


def _is_placeholder_json(data: dict) -> bool:
    """Check if parsed JSON contains only placeholder values like '...' or empty strings."""
    if not isinstance(data, dict) or not data:
        return True
    str_values = [v for v in data.values() if isinstance(v, str)]
    if not str_values:
        return False
    return all(v.strip().strip('"').strip("'") in ("...", "\u2026", "") for v in str_values)


def _extract_thinking(raw_text: str) -> tuple[str, str]:
    """Extract thinking/reasoning content from AI response.

    Returns (thinking_text, remaining_text) where remaining_text
    should contain the JSON result.
    """
    import re as _re

    text = raw_text.strip()
    thinking_parts: list[str] = []

    # 1) Extract <think>...</think> XML blocks
    think_xml_matches = list(_re.finditer(r"<think>([\s\S]*?)</think>", text))
    for m in think_xml_matches:
        thinking_parts.append(m.group(1).strip())
    text = _re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # 2) If text starts with JSON or markdown fence, no thinking preamble
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("[") or stripped.startswith("```"):
        return "\n\n".join(thinking_parts), text

    # 3) Text has non-JSON preamble (model is thinking/reasoning).
    #    Find the last valid non-placeholder JSON object and treat
    #    everything before it as thinking text.
    json_obj_pattern = _re.compile(r"\{[^{}]*\}")  # non-nested JSON objects
    all_json_matches = list(json_obj_pattern.finditer(text))

    for m in reversed(all_json_matches):
        candidate = m.group(0)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and not _is_placeholder_json(parsed):
                before = text[:m.start()].strip()
                if before:
                    thinking_parts.append(before)
                return "\n\n".join(thinking_parts), text[m.start():]
        except (json.JSONDecodeError, ValueError):
            continue

    # 4) No valid non-placeholder JSON found.
    #    If text is clearly all reasoning (long and no usable JSON), mark as thinking.
    if len(text) > 200:
        thinking_parts.append(text)
        return "\n\n".join(thinking_parts), ""

    return "\n\n".join(thinking_parts), text


def _parse_response_text(raw_text: str) -> tuple[dict, str]:
    """Strip markdown fences / thinking blocks / stray text and extract JSON from AI response.

    Returns (parsed_dict, thinking_text).
    """
    import re as _re

    # First extract thinking content
    thinking_text, text = _extract_thinking(raw_text)

    if not text.strip():
        logger.error(f"No JSON content after stripping thinking (thinking length: {len(thinking_text)})")
        raise ValueError(
            "AI yaniti JSON icerik uretmeden tamamlandi (muhtemelen token limiti). "
            "Max Tokens degerini artirin veya Thinking Mode'u kapatin."
        )

    # 1) Strip markdown code fences (```json ... ``` or ``` ... ```)
    fence_match = _re.search(r"```(?:json)?\s*\n([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # 2) Try direct parse first
    try:
        parsed = json.loads(text)
        if _is_placeholder_json(parsed):
            raise json.JSONDecodeError("placeholder JSON", text, 0)
        return parsed, thinking_text
    except json.JSONDecodeError:
        pass

    # 3) Find individual non-nested { ... } blocks (last match first)
    json_obj_matches = list(_re.finditer(r"\{[^{}]*\}", text))
    for m in reversed(json_obj_matches):
        candidate = m.group(0)
        try:
            parsed = json.loads(candidate)
            if not _is_placeholder_json(parsed):
                return parsed, thinking_text
        except json.JSONDecodeError:
            continue

    # 4) Fallback: greedy { ... } for nested JSON
    brace_match = _re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        candidate = brace_match.group(0)
        try:
            parsed = json.loads(candidate)
            if not _is_placeholder_json(parsed):
                return parsed, thinking_text
        except json.JSONDecodeError:
            pass

    logger.error(f"Failed to parse AI response as JSON: {text[:300]}")
    raise ValueError("AI yaniti gecerli JSON degil. Model farkli formatta yanit dondu.")


# Mapping from field key to the JSON key in the response
FIELD_RESULT_KEYS = {
    "name": "suggested_name",
    "meta_title": "suggested_meta_title",
    "meta_desc": "suggested_meta_description",
    "desc_tr": "suggested_description",
    "desc_en": "suggested_description_en",
}

FIELD_MAX_OUTPUT_TOKENS = {
    "name": 96,
    "meta_title": 96,
    "meta_desc": 192,
    "desc_tr": 1024,
    "desc_en": 1024,
}


class _LMStudioNativeUnavailable(RuntimeError):
    """Raised when LM Studio's native REST API is not available."""


def _cap_field_max_tokens(field: str, requested: int, thinking_mode: bool = False) -> int:
    if thinking_mode:
        return max(requested, 1)
    cap = FIELD_MAX_OUTPUT_TOKENS.get(field)
    if cap is None:
        return max(requested, 1)
    return max(min(requested, cap), 1)


def _merge_thinking_text(*parts: str) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return "\n\n".join(cleaned)


def _lm_studio_native_base_url(base_url: str) -> str:
    base = (base_url or PROVIDER_BASE_URLS["lm-studio"]).rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


def _extract_lm_studio_output(data: dict) -> tuple[str, str]:
    outputs = data.get("output") or []
    message_parts: list[str] = []
    thinking_parts: list[str] = []

    for item in outputs:
        if not isinstance(item, dict):
            continue
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if item.get("type") == "reasoning":
            thinking_parts.append(content)
        else:
            message_parts.append(content)

    return "\n\n".join(message_parts).strip(), "\n\n".join(thinking_parts).strip()


def _build_field_prompt(field: str, product: Product, keywords: List[str], desc_limit: int = 800) -> str:
    """Build a small prompt for a single field rewrite."""
    raw_desc = sanitize_html_for_prompt(product.description, limit=desc_limit)
    raw_desc_en = sanitize_html_for_prompt(product.description_translations.get("en", ""), limit=desc_limit)

    kw_str = ", ".join(keywords) if keywords else "Belirtilmemis"

    if field == "desc_tr":
        template = load_prompt_template("description_user")
        return render_prompt_template(
            template,
            {
                "name": product.name,
                "description": raw_desc or "Belirtilmemis",
                "category": product.category or "Belirtilmemis",
                "keywords": kw_str,
            },
        )

    template = FIELD_PROMPT_TEMPLATES.get(field)
    if not template:
        raise ValueError(f"Unknown field: {field}")

    return template.format(
        name=product.name,
        description=raw_desc,
        description_short=raw_desc[:200],
        description_en=raw_desc_en,
        category=product.category or "Belirtilmemis",
        keywords=kw_str,
    )


def _build_suggestion(product: Product, result: dict, thinking_text: str = "") -> SeoSuggestion:
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
        thinking_text=thinking_text,
        status="pending",
    )


def _prepare_prompt_descriptions(product: Product, desc_limit: int) -> tuple[str, str]:
    raw_desc = sanitize_html_for_prompt(product.description, limit=desc_limit)
    raw_desc_en = sanitize_html_for_prompt(product.description_translations.get("en", ""), limit=desc_limit)
    return raw_desc, raw_desc_en


def build_product_rewrite_request(
    config: AppConfig,
    provider: str,
    product: Product,
    score: SeoScore,
    target_keywords: Optional[List[str]] = None,
) -> dict:
    keywords = target_keywords or config.seo_target_keywords
    is_local = provider in ("ollama", "lm-studio")
    desc_limit = 800 if is_local else 2000
    raw_desc, raw_desc_en = _prepare_prompt_descriptions(product, desc_limit)

    system_content = _get_system_prompt(config)
    if is_local and not config.ai_thinking_mode:
        system_content += (
            "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
            "baska hicbir sey yazma. /no_think"
        )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        name=product.name,
        description=raw_desc,
        description_en=raw_desc_en,
        category=product.category or "Belirtilmemis",
        issues="; ".join(score.issues[:5]) if score.issues else "Yok",
        keywords=", ".join(keywords) if keywords else "Belirtilmemis",
    )

    return {
        "system_prompt": system_content,
        "user_prompt": user_prompt,
        "max_tokens": config.ai_max_tokens,
    }


def build_field_rewrite_request(
    config: AppConfig,
    provider: str,
    field: str,
    product: Product,
    target_keywords: Optional[List[str]] = None,
) -> dict:
    keywords = target_keywords or config.seo_target_keywords
    is_local = provider in ("ollama", "lm-studio")
    desc_limit = 800 if is_local else 2000
    thinking_mode = config.ai_thinking_mode
    max_tokens = _cap_field_max_tokens(field, config.ai_max_tokens, thinking_mode=thinking_mode)

    system_content = load_prompt_template("description_system") if field == "desc_tr" else _get_system_prompt(config)
    if is_local and not thinking_mode:
        system_content += (
            "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
            "baska hicbir sey yazma. /no_think"
        )

    return {
        "system_prompt": system_content,
        "user_prompt": _build_field_prompt(field, product, keywords, desc_limit),
        "max_tokens": max_tokens,
    }


def build_en_translation_request(
    config: AppConfig,
    provider: str,
    product: Product,
) -> dict:
    is_local = provider in ("ollama", "lm-studio")
    desc_limit = 800 if is_local else 2000
    raw_desc, _ = _prepare_prompt_descriptions(product, desc_limit)

    system_content = load_prompt_template("translation_system")
    if is_local and not config.ai_thinking_mode:
        system_content += (
            "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
            "baska hicbir sey yazma. /no_think"
        )

    return {
        "system_prompt": system_content,
        "user_prompt": render_prompt_template(
            load_prompt_template("translation_user"),
            {
                "name": product.name,
                "description": raw_desc or "Belirtilmemis",
                "category": product.category or "Belirtilmemis",
            },
        ),
        "max_tokens": _cap_field_max_tokens("desc_en", config.ai_max_tokens, thinking_mode=config.ai_thinking_mode),
    }


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
        request = build_product_rewrite_request(
            self._config,
            "anthropic",
            product,
            score,
            target_keywords,
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=request["max_tokens"],
            system=request["system_prompt"],
            messages=[{"role": "user", "content": request["user_prompt"]}],
        )
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        logger.info(
            f"Anthropic API call: {response.usage.input_tokens} input, "
            f"{response.usage.output_tokens} output tokens"
        )
        result, thinking_text = _parse_response_text(response.content[0].text)
        return _build_suggestion(product, result, thinking_text)

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> str | tuple[str, str]:
        request = build_field_rewrite_request(
            self._config,
            "anthropic",
            field,
            product,
            target_keywords,
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=request["max_tokens"],
            system=request["system_prompt"],
            messages=[{"role": "user", "content": request["user_prompt"]}],
        )
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        result, thinking_text = _parse_response_text(response.content[0].text)
        result_key = FIELD_RESULT_KEYS.get(field, field)
        value = result.get(result_key, "")
        if thinking_text:
            return value, thinking_text
        return value

    def translate_description_to_en(self, product: Product) -> str | tuple[str, str]:
        request = build_en_translation_request(
            self._config,
            self._provider,
            product,
        )
        thinking_mode = self._config.ai_thinking_mode
        max_tokens = request["max_tokens"]
        user_prompt = request["user_prompt"]
        system_content = request["system_prompt"]

        if self._provider == "lm-studio":
            try:
                raw_text, native_thinking = self._lm_studio_chat(
                    system_prompt=system_content,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    thinking_mode=thinking_mode,
                )
                result, parsed_thinking = _parse_response_text(raw_text)
                value = result.get("suggested_description_en", "")
                thinking_text = _merge_thinking_text(native_thinking, parsed_thinking)
                if thinking_text:
                    return value, thinking_text
                return value
            except _LMStudioNativeUnavailable:
                logger.warning(
                    "LM Studio native REST API kullanilamadi; OpenAI-compatible /v1 yoluna geri dusuluyor"
                )

        create_kwargs = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ],
        )

        try:
            response = self._client.chat.completions.create(**create_kwargs)
        except Exception as api_err:
            logger.error(f"{self._provider} en translation failed: {api_err}")
            raise

        self._track_usage(response)
        finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
        self._last_response_meta["finish_reason"] = finish_reason or ""
        self._last_response_meta["model"] = self._model

        if not response.choices:
            raise ValueError(f"{self._provider} yanit dondurmedi (choices bos)")

        message = response.choices[0].message
        raw_text = (message.content or "") if message else ""
        if not raw_text.strip():
            raise ValueError(f"{self._provider} bos icerik dondu")

        result, thinking_text = _parse_response_text(raw_text)
        value = result.get("suggested_description_en", "")
        if thinking_text:
            return value, thinking_text
        return value

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

        # Ensure /v1 suffix for OpenAI-compatible providers
        if base_url and provider in ("ollama", "lm-studio", "openai") and not base_url.rstrip("/").endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"
            logger.info(f"Auto-appended /v1 to base URL: {base_url}")

        # Ollama and LM Studio don't need a real API key
        api_key = config.ai_api_key or ("ollama" if provider in ("ollama", "lm-studio") else "no-key")

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = config.ai_model_name or DEFAULT_MODELS.get(provider, "gpt-4o-mini")
        self._temperature = config.ai_temperature
        self._max_tokens = config.ai_max_tokens
        self._lm_studio_native_base = (
            _lm_studio_native_base_url(base_url or PROVIDER_BASE_URLS["lm-studio"])
            if provider == "lm-studio"
            else ""
        )
        # Token tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._last_input_tokens = 0
        self._last_output_tokens = 0
        self._last_response_meta: dict = {}
        self._active_request_lock = threading.Lock()
        self._active_lm_studio_client: httpx.Client | None = None
        self._active_lm_studio_response: httpx.Response | None = None
        self._cancel_lm_studio_request = False

    @property
    def total_tokens(self) -> dict:
        return {
            "input": self._total_input_tokens,
            "output": self._total_output_tokens,
            "estimated_cost": 0.0,
        }

    @property
    def last_usage(self) -> dict:
        """Token usage of the most recent API call."""
        return {
            "input": self._last_input_tokens,
            "output": self._last_output_tokens,
        }

    @property
    def last_response_meta(self) -> dict:
        return dict(self._last_response_meta)

    def _track_usage(self, response) -> None:
        """Extract and accumulate token usage from an API response."""
        usage = response.usage
        if usage:
            inp = getattr(usage, 'prompt_tokens', 0) or 0
            out = getattr(usage, 'completion_tokens', 0) or 0
            total = getattr(usage, 'total_tokens', 0) or 0
            self._last_input_tokens = inp
            self._last_output_tokens = out
            self._last_response_meta = {
                "input_tokens": inp,
                "output_tokens": out,
                "total_tokens": total,
            }
            self._total_input_tokens += inp
            self._total_output_tokens += out
            logger.info(
                f"Token kullanimi: {inp} input + {out} output = {total} "
                f"(toplam: {self._total_input_tokens}+{self._total_output_tokens})"
            )
        else:
            self._last_input_tokens = 0
            self._last_output_tokens = 0
            self._last_response_meta = {}
            logger.warning(f"{self._provider}: response.usage is None — token tracking unavailable")

    def _track_native_usage(self, data: dict) -> None:
        stats = data.get("stats") or {}
        inp = int(stats.get("input_tokens", 0) or 0)
        out = int(stats.get("total_output_tokens", 0) or 0)
        self._last_input_tokens = inp
        self._last_output_tokens = out
        self._last_response_meta = {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
            "reasoning_output_tokens": int(stats.get("reasoning_output_tokens", 0) or 0),
            "tokens_per_second": stats.get("tokens_per_second"),
            "time_to_first_token_seconds": stats.get("time_to_first_token_seconds"),
            "stop_reason": data.get("stop_reason") or stats.get("stop_reason") or "",
            "model_instance_id": data.get("model_instance_id", ""),
            "model": self._model,
        }
        self._total_input_tokens += inp
        self._total_output_tokens += out
        logger.info(
            f"LM Studio native token kullanimi: {inp} input + {out} output "
            f"(toplam: {self._total_input_tokens}+{self._total_output_tokens})"
        )

    def _lm_studio_headers(self) -> dict:
        api_key = (self._config.ai_api_key or "").strip()
        if api_key and api_key not in {"ollama", "lm-studio"}:
            return {"Authorization": f"Bearer {api_key}"}
        return {}

    def _post_lm_studio_native(self, payload: dict) -> dict:
        url = f"{self._lm_studio_native_base}/api/v1/chat"
        timeout = httpx.Timeout(120.0, connect=5.0)
        client = httpx.Client(timeout=timeout)
        with self._active_request_lock:
            self._active_lm_studio_client = client
            self._cancel_lm_studio_request = False

        try:
            stream_payload = dict(payload)
            stream_payload["stream"] = True

            try:
                with client.stream("POST", url, json=stream_payload, headers=self._lm_studio_headers()) as response:
                    with self._active_request_lock:
                        self._active_lm_studio_response = response
                        cancel_requested = self._cancel_lm_studio_request

                    if cancel_requested:
                        response.close()
                        raise RuntimeError("LM Studio istegi kullanici tarafindan iptal edildi")

                    if response.status_code in (404, 405, 501):
                        raise _LMStudioNativeUnavailable("LM Studio native /api/v1/chat endpoint'i mevcut degil")

                    if response.status_code >= 400 and "reasoning" in payload:
                        retry_payload = dict(payload)
                        retry_payload.pop("reasoning", None)
                        return self._post_lm_studio_native(retry_payload)

                    if response.status_code >= 400:
                        error_text = response.read().decode("utf-8", errors="replace")
                        raise RuntimeError(
                            f"LM Studio native API hatasi ({response.status_code}): {error_text[:300]}"
                        )

                    event_name = ""
                    data_lines: list[str] = []
                    for line in response.iter_lines():
                        if line == "":
                            if event_name == "chat.end" and data_lines:
                                try:
                                    payload_data = json.loads("\n".join(data_lines))
                                except json.JSONDecodeError as exc:
                                    raise RuntimeError("LM Studio stream sonu JSON degildi") from exc
                                return payload_data.get("result", payload_data)
                            event_name = ""
                            data_lines = []
                            continue

                        if line.startswith("event: "):
                            event_name = line[7:]
                        elif line.startswith("data: "):
                            data_lines.append(line[6:])
            except httpx.HTTPError as exc:
                raise RuntimeError(f"LM Studio native API istegi basarisiz: {exc}") from exc

            raise RuntimeError("LM Studio native stream chat.end olayi dondurmedi")
        finally:
            with self._active_request_lock:
                if self._active_lm_studio_response is not None:
                    self._active_lm_studio_response = None
                if self._active_lm_studio_client is client:
                    self._active_lm_studio_client = None
                self._cancel_lm_studio_request = False
            client.close()

    def cancel_active_request(self) -> bool:
        with self._active_request_lock:
            self._cancel_lm_studio_request = True
            response = self._active_lm_studio_response
            client = self._active_lm_studio_client
        if response is None and client is None:
            return False
        try:
            if response is not None:
                response.close()
            if client is not None:
                client.close()
            return True
        except Exception:
            logger.exception("Active LM Studio request could not be cancelled cleanly")
            return False

    def _lm_studio_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        thinking_mode: bool,
    ) -> tuple[str, str]:
        payload = {
            "model": self._model,
            "system_prompt": system_prompt,
            "input": user_prompt,
            "temperature": self._temperature,
            "max_output_tokens": max_tokens,
            "reasoning": "on" if thinking_mode else "off",
        }
        data = self._post_lm_studio_native(payload)
        self._track_native_usage(data)
        raw_text, native_thinking = _extract_lm_studio_output(data)
        if not raw_text.strip():
            stats = data.get("stats") or {}
            reasoning_tokens = int(stats.get("reasoning_output_tokens", 0) or 0)
            total_output = int(stats.get("total_output_tokens", 0) or 0)
            if thinking_mode and reasoning_tokens >= total_output > 0:
                raise ValueError(
                    "LM Studio thinking ciktilari token butcesini tuketti; model JSON yanitina gecemedi. "
                    "Max Tokens degerini artirin, context length'i buyutun veya Thinking Mode'u kapatin."
                )
            raise ValueError(
                "LM Studio yaniti JSON icerik uretmeden tamamlandi. "
                "Max Tokens degerini artirin veya Thinking Mode'u kapatin."
            )
        return raw_text, native_thinking

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> SeoSuggestion:
        request = build_product_rewrite_request(
            self._config,
            self._provider,
            product,
            score,
            target_keywords,
        )
        thinking_mode = self._config.ai_thinking_mode
        max_tokens = request["max_tokens"]
        user_prompt = request["user_prompt"]
        system_content = request["system_prompt"]

        if self._provider == "lm-studio":
            try:
                raw_text, native_thinking = self._lm_studio_chat(
                    system_prompt=system_content,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    thinking_mode=thinking_mode,
                )
                result, parsed_thinking = _parse_response_text(raw_text)
                return _build_suggestion(
                    product,
                    result,
                    _merge_thinking_text(native_thinking, parsed_thinking),
                )
            except _LMStudioNativeUnavailable:
                logger.warning(
                    "LM Studio native REST API kullanilamadi; OpenAI-compatible /v1 yoluna geri dusuluyor"
                )

        create_kwargs = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ],
        )

        # response_format is unreliable on local servers (LM Studio rejects json_object)
        # so we skip it entirely and rely on robust response parsing instead

        try:
            response = self._client.chat.completions.create(**create_kwargs)
        except Exception as api_err:
            logger.error(f"{self._provider} API request failed: {api_err}")
            raise

        self._track_usage(response)
        logger.info(
            f"{self._provider} API call: "
            f"{self._last_input_tokens} input, {self._last_output_tokens} output tokens "
            f"(total: {self._total_input_tokens}+{self._total_output_tokens})"
        )

        # Check for truncation — model ran out of tokens
        finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
        self._last_response_meta["finish_reason"] = finish_reason or ""
        self._last_response_meta["model"] = self._model
        if finish_reason == "length":
            logger.warning(
                f"{self._provider}: Response truncated (max_tokens={max_tokens} reached). "
                "Consider increasing Max Tokens or disabling Thinking Mode."
            )

        # Defensive checks for LM Studio / Ollama responses
        if not response.choices:
            logger.error(f"{self._provider} returned no choices. Full response: {response}")
            raise ValueError(f"{self._provider} yanit dondurmedi (choices bos)")

        message = response.choices[0].message
        if message is None:
            logger.error(f"{self._provider} returned None message")
            raise ValueError(f"{self._provider} yanit mesaji bos")

        raw_text = message.content or ""
        if not raw_text.strip():
            logger.error(f"{self._provider} returned empty content")
            raise ValueError(f"{self._provider} bos icerik dondu")

        logger.debug(f"{self._provider} raw response: {raw_text[:500]}")
        result, thinking_text = _parse_response_text(raw_text)
        return _build_suggestion(product, result, thinking_text)

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> str | tuple[str, str]:
        request = build_field_rewrite_request(
            self._config,
            self._provider,
            field,
            product,
            target_keywords,
        )
        thinking_mode = self._config.ai_thinking_mode
        max_tokens = request["max_tokens"]
        user_prompt = request["user_prompt"]
        system_content = request["system_prompt"]

        if self._provider == "lm-studio":
            try:
                raw_text, native_thinking = self._lm_studio_chat(
                    system_prompt=system_content,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    thinking_mode=thinking_mode,
                )
                result, parsed_thinking = _parse_response_text(raw_text)
                result_key = FIELD_RESULT_KEYS.get(field, field)
                value = result.get(result_key, "")
                thinking_text = _merge_thinking_text(native_thinking, parsed_thinking)
                if thinking_text:
                    return value, thinking_text
                return value
            except _LMStudioNativeUnavailable:
                logger.warning(
                    "LM Studio native REST API kullanilamadi; OpenAI-compatible /v1 yoluna geri dusuluyor"
                )

        create_kwargs = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ],
        )

        try:
            response = self._client.chat.completions.create(**create_kwargs)
        except Exception as api_err:
            logger.error(f"{self._provider} field rewrite failed: {api_err}")
            raise

        self._track_usage(response)
        logger.info(
            f"{self._provider} field '{field}': "
            f"{self._last_input_tokens} input, {self._last_output_tokens} output tokens "
            f"(total: {self._total_input_tokens}+{self._total_output_tokens})"
        )

        # Check for truncation
        finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
        self._last_response_meta["finish_reason"] = finish_reason or ""
        self._last_response_meta["model"] = self._model
        if finish_reason == "length":
            logger.warning(
                f"{self._provider}: Field '{field}' response truncated (max_tokens={max_tokens}). "
                "Consider increasing Max Tokens or disabling Thinking Mode."
            )

        if not response.choices:
            raise ValueError(f"{self._provider} yanit dondurmedi (choices bos)")

        message = response.choices[0].message
        raw_text = (message.content or "") if message else ""
        if not raw_text.strip():
            raise ValueError(f"{self._provider} bos icerik dondu")

        logger.debug(f"{self._provider} field '{field}' response: {raw_text[:300]}")
        result, thinking_text = _parse_response_text(raw_text)
        result_key = FIELD_RESULT_KEYS.get(field, field)
        value = result.get(result_key, "")
        if thinking_text:
            return value, thinking_text
        return value

    def translate_description_to_en(self, product: Product) -> str | tuple[str, str]:
        request = build_en_translation_request(
            self._config,
            self._provider,
            product,
        )
        thinking_mode = self._config.ai_thinking_mode
        max_tokens = request["max_tokens"]
        user_prompt = request["user_prompt"]
        system_content = request["system_prompt"]

        if self._provider == "lm-studio":
            try:
                raw_text, native_thinking = self._lm_studio_chat(
                    system_prompt=system_content,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    thinking_mode=thinking_mode,
                )
                result, parsed_thinking = _parse_response_text(raw_text)
                value = result.get("suggested_description_en", "")
                thinking_text = _merge_thinking_text(native_thinking, parsed_thinking)
                if thinking_text:
                    return value, thinking_text
                return value
            except _LMStudioNativeUnavailable:
                logger.warning(
                    "LM Studio native REST API kullanilamadi; OpenAI-compatible /v1 yoluna geri dusuluyor"
                )

        create_kwargs = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ],
        )

        try:
            response = self._client.chat.completions.create(**create_kwargs)
        except Exception as api_err:
            logger.error(f"{self._provider} en translation failed: {api_err}")
            raise

        self._track_usage(response)
        finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
        self._last_response_meta["finish_reason"] = finish_reason or ""
        self._last_response_meta["model"] = self._model

        if not response.choices:
            raise ValueError(f"{self._provider} yanit dondurmedi (choices bos)")

        message = response.choices[0].message
        raw_text = (message.content or "") if message else ""
        if not raw_text.strip():
            raise ValueError(f"{self._provider} bos icerik dondu")

        result, thinking_text = _parse_response_text(raw_text)
        value = result.get("suggested_description_en", "")
        if thinking_text:
            return value, thinking_text
        return value

def create_ai_client(config: AppConfig) -> BaseAIClient:
    """Factory: return the right AI client based on config.ai_provider."""
    provider = config.ai_provider.lower()

    if provider == "none":
        return NoneAIClient()
    elif provider == "anthropic":
        return AnthropicAIClient(config)
    elif provider in ("openai", "gemini", "openrouter", "ollama", "lm-studio", "custom"):
        return OpenAICompatibleClient(config, provider)
    else:
        logger.warning(f"Unknown AI provider '{provider}', defaulting to NoneAIClient")
        return NoneAIClient()
