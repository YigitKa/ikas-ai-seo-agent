"""Cross-cutting utility modules."""

from core.utils.html import has_html_markup, html_to_plain_text, sanitize_html_for_prompt
from core.utils.presentation import (
    clean_suggestion_value,
    format_prompt_display,
    get_en_description_value,
    get_tr_description_value,
)

__all__ = [
    "has_html_markup",
    "html_to_plain_text",
    "sanitize_html_for_prompt",
    "clean_suggestion_value",
    "format_prompt_display",
    "get_en_description_value",
    "get_tr_description_value",
]
