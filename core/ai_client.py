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
from typing import Callable, List, Optional

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

    "desc_tr": """Urun Adi: {name}
Mevcut Turkce Aciklama: {description}
Kategori: {category}
Hedef Keywordler: {keywords}

Bu urunun Turkce aciklamasini SEO icin optimize et. 200-400 kelime, dogal satis dili.
SADECE JSON dondur:
{{"suggested_description": "..."}}""",

    "desc_en": """Urun Adi: {name}
Mevcut Ingilizce Aciklama: {description_en}
Kategori: {category}
Hedef Keywordler: {keywords}

Rewrite the English product description for SEO. 200-400 words, natural sales language.
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


def _build_field_prompt(field: str, product: Product, keywords: List[str], desc_limit: int = 800) -> str:
    """Build a small prompt for a single field rewrite."""
    import re as _re

    template = FIELD_PROMPT_TEMPLATES.get(field)
    if not template:
        raise ValueError(f"Unknown field: {field}")

    raw_desc = product.description[:desc_limit]
    raw_desc = _re.sub(r"<[^>]+>", " ", raw_desc)
    raw_desc = _re.sub(r"\s+", " ", raw_desc).strip()

    raw_desc_en = product.description_translations.get("en", "")[:desc_limit]
    raw_desc_en = _re.sub(r"<[^>]+>", " ", raw_desc_en)
    raw_desc_en = _re.sub(r"\s+", " ", raw_desc_en).strip()

    kw_str = ", ".join(keywords) if keywords else "Belirtilmemis"

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


class BaseAIClient:
    """Shared batch logic for all providers."""

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
        on_chunk: Optional[Callable[[str, bool], None]] = None,
    ) -> SeoSuggestion:
        raise NotImplementedError

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
        on_chunk: Optional[Callable[[str, bool], None]] = None,
    ) -> str | tuple[str, str]:
        """Rewrite a single field and return the new value as plain text,
        or (value, thinking_text) tuple when thinking mode is on."""
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

    def rewrite_field(self, field, product, score, target_keywords=None):
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
        result, thinking_text = _parse_response_text(response.content[0].text)
        return _build_suggestion(product, result, thinking_text)

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
    ) -> str | tuple[str, str]:
        keywords = target_keywords or self._config.seo_target_keywords
        user_prompt = _build_field_prompt(field, product, keywords, desc_limit=2000)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=_get_system_prompt(self._config),
            messages=[{"role": "user", "content": user_prompt}],
        )
        self._total_input_tokens += response.usage.input_tokens
        self._total_output_tokens += response.usage.output_tokens
        result, thinking_text = _parse_response_text(response.content[0].text)
        result_key = FIELD_RESULT_KEYS.get(field, field)
        value = result.get(result_key, "")
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
        # Token tracking
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._last_input_tokens = 0
        self._last_output_tokens = 0

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

    def _track_usage(self, response) -> None:
        """Extract and accumulate token usage from an API response."""
        usage = response.usage
        if usage:
            inp = getattr(usage, 'prompt_tokens', 0) or 0
            out = getattr(usage, 'completion_tokens', 0) or 0
            total = getattr(usage, 'total_tokens', 0) or 0
            self._last_input_tokens = inp
            self._last_output_tokens = out
            self._total_input_tokens += inp
            self._total_output_tokens += out
            logger.info(
                f"Token kullanimi: {inp} input + {out} output = {total} "
                f"(toplam: {self._total_input_tokens}+{self._total_output_tokens})"
            )
        else:
            self._last_input_tokens = 0
            self._last_output_tokens = 0
            logger.warning(f"{self._provider}: response.usage is None — token tracking unavailable")

    def _stream_completion(
        self,
        create_kwargs: dict,
        on_chunk: Callable[[str, bool], None],
    ) -> str:
        """Stream completion and call on_chunk(text, is_thinking) per token.

        Parses <think>...</think> tags in real-time so callers can
        distinguish thinking tokens from final output tokens.
        Returns the full raw text.
        """
        stream = self._client.chat.completions.create(**create_kwargs, stream=True)

        full_text = ""
        buf = ""            # unprocessed lookahead buffer for tag detection
        in_think = False    # currently inside <think>...</think>

        OPEN_TAG  = "<think>"
        CLOSE_TAG = "</think>"

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = (delta.content or "") if delta else ""
            if not piece:
                continue

            buf += piece
            full_text += piece

            # Emit what we can safely (everything except the last len(OPEN_TAG)-1
            # chars, which might be an incomplete tag boundary)
            while True:
                if not in_think:
                    tag_pos = buf.find(OPEN_TAG)
                    if tag_pos == -1:
                        # No open tag found — safe to emit all but tail
                        safe_len = max(0, len(buf) - len(OPEN_TAG) + 1)
                        if safe_len > 0:
                            on_chunk(buf[:safe_len], False)
                            buf = buf[safe_len:]
                        break
                    else:
                        # Emit text before tag
                        if tag_pos > 0:
                            on_chunk(buf[:tag_pos], False)
                        buf = buf[tag_pos + len(OPEN_TAG):]
                        in_think = True
                else:
                    end_pos = buf.find(CLOSE_TAG)
                    if end_pos == -1:
                        safe_len = max(0, len(buf) - len(CLOSE_TAG) + 1)
                        if safe_len > 0:
                            on_chunk(buf[:safe_len], True)
                            buf = buf[safe_len:]
                        break
                    else:
                        if end_pos > 0:
                            on_chunk(buf[:end_pos], True)
                        buf = buf[end_pos + len(CLOSE_TAG):]
                        in_think = False

        # Flush remaining buffer
        if buf:
            on_chunk(buf, in_think)

        # Token tracking: streaming responses may include usage in the last chunk
        try:
            # Drain stream for usage info (some providers send it at the end)
            for chunk in stream:
                if hasattr(chunk, 'usage') and chunk.usage:
                    inp = getattr(chunk.usage, 'prompt_tokens', 0) or 0
                    out = getattr(chunk.usage, 'completion_tokens', 0) or 0
                    self._last_input_tokens = inp
                    self._last_output_tokens = out
                    self._total_input_tokens += inp
                    self._total_output_tokens += out
        except Exception:
            pass

        return full_text

    def rewrite_product(
        self,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
        on_chunk: Optional[Callable[[str, bool], None]] = None,
    ) -> SeoSuggestion:
        keywords = target_keywords or self._config.seo_target_keywords

        # Local providers have smaller context windows – truncate more aggressively
        is_local = self._provider in ("ollama", "lm-studio")
        desc_limit = 800 if is_local else 2000
        thinking_mode = self._config.ai_thinking_mode
        max_tokens = self._max_tokens

        # Strip HTML tags from descriptions to save tokens
        import re as _re
        raw_desc = product.description[:desc_limit]
        raw_desc = _re.sub(r"<[^>]+>", " ", raw_desc)
        raw_desc = _re.sub(r"\s+", " ", raw_desc).strip()

        raw_desc_en = product.description_translations.get("en", "")[:desc_limit]
        raw_desc_en = _re.sub(r"<[^>]+>", " ", raw_desc_en)
        raw_desc_en = _re.sub(r"\s+", " ", raw_desc_en).strip()

        user_prompt = USER_PROMPT_TEMPLATE.format(
            name=product.name,
            description=raw_desc,
            description_en=raw_desc_en,
            category=product.category or "Belirtilmemis",
            issues="; ".join(score.issues[:5]) if score.issues else "Yok",
            keywords=", ".join(keywords) if keywords else "Belirtilmemis",
        )
        system_content = _get_system_prompt(self._config)
        if is_local and not thinking_mode:
            system_content += (
                "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
                "baska hicbir sey yazma. /no_think"
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

        # Use streaming when callback provided (shows live thinking)
        if on_chunk is not None:
            try:
                raw_text = self._stream_completion(create_kwargs, on_chunk)
            except Exception as api_err:
                logger.error(f"{self._provider} streaming failed: {api_err}")
                raise
        else:
            try:
                response = self._client.chat.completions.create(**create_kwargs)
            except Exception as api_err:
                logger.error(f"{self._provider} API request failed: {api_err}")
                raise

            self._track_usage(response)

            finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
            if finish_reason == "length":
                logger.warning(
                    f"{self._provider}: Response truncated (max_tokens={max_tokens} reached). "
                    "Consider increasing Max Tokens or disabling Thinking Mode."
                )

            if not response.choices:
                logger.error(f"{self._provider} returned no choices. Full response: {response}")
                raise ValueError(f"{self._provider} yanit dondurmedi (choices bos)")

            message = response.choices[0].message
            if message is None:
                raise ValueError(f"{self._provider} yanit mesaji bos")

            raw_text = message.content or ""
            if not raw_text.strip():
                raise ValueError(f"{self._provider} bos icerik dondu")

        logger.info(
            f"{self._provider} API call: "
            f"{self._last_input_tokens} in, {self._last_output_tokens} out tokens"
        )
        logger.debug(f"{self._provider} raw response: {raw_text[:500]}")
        result, thinking_text = _parse_response_text(raw_text)
        return _build_suggestion(product, result, thinking_text)

    def rewrite_field(
        self,
        field: str,
        product: Product,
        score: SeoScore,
        target_keywords: Optional[List[str]] = None,
        on_chunk: Optional[Callable[[str, bool], None]] = None,
    ) -> str | tuple[str, str]:
        keywords = target_keywords or self._config.seo_target_keywords
        is_local = self._provider in ("ollama", "lm-studio")
        desc_limit = 800 if is_local else 2000
        thinking_mode = self._config.ai_thinking_mode
        max_tokens = self._max_tokens

        user_prompt = _build_field_prompt(field, product, keywords, desc_limit)

        system_content = _get_system_prompt(self._config)
        if is_local and not thinking_mode:
            system_content += (
                "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
                "baska hicbir sey yazma. /no_think"
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

        if on_chunk is not None:
            try:
                raw_text = self._stream_completion(create_kwargs, on_chunk)
            except Exception as api_err:
                logger.error(f"{self._provider} field streaming failed: {api_err}")
                raise
        else:
            try:
                response = self._client.chat.completions.create(**create_kwargs)
            except Exception as api_err:
                logger.error(f"{self._provider} field rewrite failed: {api_err}")
                raise

            self._track_usage(response)

            finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
            if finish_reason == "length":
                logger.warning(
                    f"{self._provider}: Field '{field}' response truncated (max_tokens={max_tokens})."
                )

            if not response.choices:
                raise ValueError(f"{self._provider} yanit dondurmedi (choices bos)")

            message = response.choices[0].message
            raw_text = (message.content or "") if message else ""
            if not raw_text.strip():
                raise ValueError(f"{self._provider} bos icerik dondu")

        logger.info(
            f"{self._provider} field '{field}': "
            f"{self._last_input_tokens} in, {self._last_output_tokens} out tokens"
        )
        logger.debug(f"{self._provider} field '{field}' response: {raw_text[:300]}")
        result, thinking_text = _parse_response_text(raw_text)
        result_key = FIELD_RESULT_KEYS.get(field, field)
        value = result.get(result_key, "")
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
