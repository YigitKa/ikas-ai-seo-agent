"""Request builder functions for AI provider calls."""

from typing import List, Optional

from core.utils.html import sanitize_html_for_prompt
from core.models import AppConfig, Product, SeoScore, SeoSuggestion
from core.prompt_store import load_prompt_template, render_prompt_template
from core.ai.constants import FIELD_PROMPT_TEMPLATES, USER_PROMPT_TEMPLATE
from core.ai.helpers import _get_system_prompt, _cap_field_max_tokens


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
    if is_local and not config.ai_thinking_mode:
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
