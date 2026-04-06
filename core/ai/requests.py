"""Request builder functions for AI provider calls."""

import re
from typing import List, Optional

from core.utils.html import html_to_plain_text, sanitize_html_for_prompt
from core.models import AppConfig, Product, SeoScore, SeoSuggestion
from core.prompt_store import compose_prompt_with_skill_layer, load_prompt_template, render_prompt_template
from core.ai.constants import USER_PROMPT_TEMPLATE
from core.ai.helpers import _get_system_prompt, _cap_field_max_tokens


def _build_description_summary(value: str, limit: int = 320) -> str:
    """Extract a compact, product-focused plain-text summary from description HTML."""
    plain_text = html_to_plain_text(value, preserve_breaks=True)
    if not plain_text:
        return ""

    blocks = [re.sub(r"\s+", " ", block).strip(" -•\t") for block in plain_text.splitlines()]
    blocks = [block for block in blocks if block]
    if not blocks:
        return ""

    summary_parts: list[str] = []
    current_length = 0
    for block in blocks:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", block) if part.strip()]
        if not sentences:
            sentences = [block]

        for sentence in sentences:
            if sentence in summary_parts:
                continue
            summary_parts.append(sentence)
            current_length = len(" ".join(summary_parts))
            if current_length >= limit or len(summary_parts) >= 3:
                break

        if current_length >= limit or len(summary_parts) >= 3:
            break

    summary = " ".join(summary_parts).strip()
    if len(summary) <= limit:
        return summary

    truncated = summary[:limit].rsplit(" ", 1)[0].strip()
    return truncated or summary[:limit].strip()


FIELD_TEMPLATE_KEYS = {
    "name": "field_name_user",
    "meta_title": "field_meta_title_user",
    "meta_desc": "field_meta_desc_user",
    "desc_en": "field_desc_en_user",
    "desc_tr": "description_user",
}


def _build_field_prompt(field: str, product: Product, keywords: List[str], desc_limit: int = 800) -> str:
    """Build a small prompt for a single field rewrite using file-based templates."""
    template_key = FIELD_TEMPLATE_KEYS.get(field)
    if not template_key:
        raise ValueError(f"Unknown field: {field}")

    raw_desc = sanitize_html_for_prompt(product.description, limit=desc_limit)
    raw_desc_en = sanitize_html_for_prompt(product.description_translations.get("en", ""), limit=desc_limit)
    description_summary = _build_description_summary(product.description, limit=min(400, desc_limit)) or (
        raw_desc[:400] if raw_desc else "Belirtilmemis"
    )

    kw_str = ", ".join(keywords) if keywords else "Belirtilmemis"

    template = load_prompt_template(template_key)
    context = {
        "name": product.name,
        "description": raw_desc or "Belirtilmemis",
        "description_summary": description_summary,
        "description_en": raw_desc_en or "Belirtilmemis",
        "category": product.category or "Belirtilmemis",
        "keywords": kw_str,
    }
    return render_prompt_template(template, context)


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


def _prepare_full_translation_description(value: str) -> str:
    text = html_to_plain_text(value, preserve_breaks=True)
    text = re.sub(r"[ \t\f\v]+", " ", text).strip()
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# Providers whose models commonly produce <think> blocks
_THINK_TAG_PROVIDERS = frozenset({"ollama", "lm-studio", "openrouter", "custom"})


def _merge_system_prompt(system_prompt: str, extra_system_prompt: str = "") -> str:
    return compose_prompt_with_skill_layer(system_prompt, extra_system_prompt, "product_rewrite")


def build_product_rewrite_request(
    config: AppConfig,
    provider: str,
    product: Product,
    score: SeoScore,
    target_keywords: Optional[List[str]] = None,
    extra_system_prompt: str = "",
) -> dict:
    keywords = target_keywords or config.seo_target_keywords
    is_local = provider in ("ollama", "lm-studio")
    desc_limit = 800 if is_local else 2000
    raw_desc, raw_desc_en = _prepare_prompt_descriptions(product, desc_limit)

    system_content = _get_system_prompt(config)
    if provider in _THINK_TAG_PROVIDERS and not config.ai_thinking_mode:
        system_content += (
            "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
            "baska hicbir sey yazma. /no_think"
        )
    system_content = _merge_system_prompt(system_content, extra_system_prompt)

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


def build_geo_rewrite_request(
    config: AppConfig,
    provider: str,
    product: Product,
    score: SeoScore,
    target_keywords: Optional[List[str]] = None,
) -> dict:
    keywords = target_keywords or config.seo_target_keywords
    is_local = provider in ("ollama", "lm-studio")
    desc_limit = 800 if is_local else 2000
    raw_desc, _ = _prepare_prompt_descriptions(product, desc_limit)

    system_content = load_prompt_template("geo_rewrite_system")
    if provider in _THINK_TAG_PROVIDERS and not config.ai_thinking_mode:
        system_content += (
            "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
            "baska hicbir sey yazma. /no_think"
        )

    user_template = load_prompt_template("geo_rewrite_user")
    user_prompt = render_prompt_template(
        user_template,
        {
            "name": product.name,
            "description": raw_desc or "Belirtilmemis",
            "category": product.category or "Belirtilmemis",
            "issues": "; ".join(score.issues[:5]) if score.issues else "Yok",
            "keywords": ", ".join(keywords) if keywords else "Belirtilmemis",
        },
    )

    return {
        "system_prompt": system_content,
        "user_prompt": user_prompt,
        "max_tokens": config.ai_max_tokens,
    }


def build_llms_summary_request(
    config: AppConfig,
    provider: str,
    product: Product,
) -> dict:
    """Build prompt for llms.txt product summary."""
    is_local = provider in ("ollama", "lm-studio")
    desc_limit = 1200 if is_local else 1800
    raw_desc, _ = _prepare_prompt_descriptions(product, desc_limit)

    system_content = load_prompt_template("llms_summary_system")
    if provider in _THINK_TAG_PROVIDERS and not config.ai_thinking_mode:
        system_content += (
            "\n\nONEMLI: Dusunme surecini YAZMA. SADECE JSON ver. /no_think"
        )

    user_prompt = render_prompt_template(
        load_prompt_template("llms_summary_user"),
        {
            "store_name": config.ikas_store_name or "Magaza",
            "name": product.name,
            "description": raw_desc or "Belirtilmemis",
            "category": product.category or "Belirtilmemis",
            "price": f"{product.price:.2f} TL" if product.price is not None else "Belirsiz",
            "tags": ", ".join(product.tags) if getattr(product, "tags", None) else "Etiket yok",
        },
    )

    max_tokens = min(512, max(128, config.ai_max_tokens))
    return {
        "system_prompt": system_content,
        "user_prompt": user_prompt,
        "max_tokens": max_tokens,
    }


def build_field_rewrite_request(
    config: AppConfig,
    provider: str,
    field: str,
    product: Product,
    target_keywords: Optional[List[str]] = None,
    extra_system_prompt: str = "",
) -> dict:
    keywords = target_keywords or config.seo_target_keywords
    is_local = provider in ("ollama", "lm-studio")
    desc_limit = 800 if is_local else 2000
    thinking_mode = config.ai_thinking_mode
    max_tokens = _cap_field_max_tokens(field, config.ai_max_tokens, thinking_mode=thinking_mode)

    system_content = load_prompt_template("description_system") if field == "desc_tr" else _get_system_prompt(config)
    if provider in _THINK_TAG_PROVIDERS and not thinking_mode:
        system_content += (
            "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
            "baska hicbir sey yazma. /no_think"
        )
    system_content = _merge_system_prompt(system_content, extra_system_prompt)

    return {
        "system_prompt": system_content,
        "user_prompt": _build_field_prompt(field, product, keywords, desc_limit),
        "max_tokens": max_tokens,
    }


def build_en_translation_request(
    config: AppConfig,
    provider: str,
    product: Product,
    extra_system_prompt: str = "",
) -> dict:
    is_local = provider in ("ollama", "lm-studio")
    raw_desc = _prepare_full_translation_description(product.description)

    system_content = load_prompt_template("translation_system")
    if provider in _THINK_TAG_PROVIDERS and not config.ai_thinking_mode:
        system_content += (
            "\n\nONEMLI: Dusunme surecini YAZMA. Dogrudan JSON ciktisi ver, "
            "baska hicbir sey yazma. /no_think"
        )
    system_content = _merge_system_prompt(system_content, extra_system_prompt)

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
