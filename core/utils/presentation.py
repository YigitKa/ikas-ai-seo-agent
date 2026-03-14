from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from core.models import Product, SeoSuggestion

_EMPTY_SUGGESTION_VALUES = {"", "-", "AI ile yeniden yazma icin butonu kullanin"}
_ISSUE_PATTERNS = {
    "Baslik": ("urun adi", "baslik", "url-dostu"),
    "Aciklama": (
        "aciklama",
        "paragraf",
        "html ogeleri",
        "cumle",
        "kelime cesitliligi",
        "tekrarlanan ifadeler",
        "gecis kelimeleri",
        "icerik kalite",
    ),
    "Meta Title": ("meta title",),
    "Meta Desc": ("meta description",),
    "Keyword": ("keyword", "kategori adi", "urun adi kelimeleri", "icerik uyumsuzlugu"),
}


def normalize_prompt_block(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    normalized: list[str] = []
    blank_pending = False

    for line in lines:
        if line.strip():
            if blank_pending and normalized:
                normalized.append("")
            normalized.append(line.strip())
            blank_pending = False
        else:
            blank_pending = True

    result = "\n".join(normalized).strip()
    return re.sub(r"\n{3,}", "\n\n", result)


def format_prompt_display(request: Mapping[str, Any]) -> str:
    system_prompt = normalize_prompt_block(str(request.get("system_prompt") or ""))
    user_prompt = normalize_prompt_block(str(request.get("user_prompt") or ""))
    parts: list[str] = []
    if system_prompt:
        parts.append("[system]\n" + system_prompt)
    if user_prompt:
        parts.append("[user]\n" + user_prompt)
    return "\n\n".join(parts).strip()


def clean_suggestion_value(value: str) -> str:
    normalized = (value or "").strip()
    return "" if normalized in _EMPTY_SUGGESTION_VALUES else normalized


def bucket_score_issue(issue: str) -> str | None:
    lowered = issue.lower()
    for bucket, patterns in _ISSUE_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            return bucket
    return None


def group_score_issues(issues: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    grouped = {name: [] for name in _ISSUE_PATTERNS}
    other: list[str] = []

    for issue in issues:
        bucket = bucket_score_issue(issue)
        if bucket is None:
            other.append(issue)
        else:
            grouped[bucket].append(issue)

    return grouped, other


def get_tr_description_value(
    description: str,
    translations: Mapping[str, str] | None = None,
) -> str:
    if translations:
        tr_desc = translations.get("tr", "")
        if tr_desc and tr_desc.strip():
            return tr_desc
    if description and description.strip():
        return description
    return ""


def get_en_description_value(translations: Mapping[str, str] | None = None) -> str:
    if translations:
        en_desc = translations.get("en", "")
        if en_desc and en_desc.strip():
            return en_desc
    return ""


def get_product_image_urls(product: Product) -> list[str]:
    if product.image_urls:
        return product.image_urls
    if product.image_url:
        return [product.image_url]
    return []


def summarize_suggestion_result(suggestion: SeoSuggestion) -> dict[str, str]:
    result = {
        "suggested_name": suggestion.suggested_name or "",
        "suggested_meta_title": suggestion.suggested_meta_title or "",
        "suggested_meta_description": suggestion.suggested_meta_description or "",
    }
    if suggestion.suggested_description:
        result["suggested_description"] = suggestion.suggested_description[:200] + "..."
    return result
