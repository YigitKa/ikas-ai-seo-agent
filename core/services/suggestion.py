from __future__ import annotations

from collections.abc import Mapping

from core.models import Product, SeoSuggestion
from core.utils.presentation import clean_suggestion_value


def create_pending_suggestion(product: Product) -> SeoSuggestion:
    return SeoSuggestion(
        product_id=product.id,
        original_name=product.name,
        original_description=product.description,
        original_description_en=product.description_translations.get("en", ""),
        original_meta_title=product.meta_title,
        original_meta_description=product.meta_description,
        status="pending",
    )


def apply_suggestion_field(suggestion: SeoSuggestion, field: str, value: str) -> None:
    cleaned = clean_suggestion_value(value)
    if field == "name":
        suggestion.suggested_name = cleaned or None
    elif field == "meta_title":
        suggestion.suggested_meta_title = cleaned
    elif field == "meta_desc":
        suggestion.suggested_meta_description = cleaned
    elif field == "desc_tr":
        suggestion.suggested_description = cleaned
    elif field == "desc_en":
        suggestion.suggested_description_en = cleaned


def sync_suggestion_fields(suggestion: SeoSuggestion, field_values: Mapping[str, str]) -> SeoSuggestion:
    for field, value in field_values.items():
        apply_suggestion_field(suggestion, field, value)
    return suggestion
