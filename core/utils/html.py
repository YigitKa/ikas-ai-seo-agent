from __future__ import annotations

import html
import re

_BREAK_TAG_RE = re.compile(r"(?is)<\s*br\s*/?\s*>")
_OPEN_BLOCK_TAG_RE = re.compile(
    r"(?is)<\s*(?:p|div|section|article|header|footer|blockquote|table|thead|tbody|tfoot|tr|h[1-6])\b[^>]*>"
)
_CLOSE_BLOCK_TAG_RE = re.compile(
    r"(?is)<\s*/\s*(?:p|div|section|article|header|footer|blockquote|table|thead|tbody|tfoot|tr|h[1-6]|ul|ol)\s*>"
)
_LIST_ITEM_TAG_RE = re.compile(r"(?is)<\s*li\b[^>]*>")
_HTML_TAG_RE = re.compile(r"(?is)<[^>]+>")


def has_html_markup(value: str) -> bool:
    return bool(_HTML_TAG_RE.search(value or ""))


def html_to_plain_text(value: str, *, preserve_breaks: bool = True) -> str:
    if not value:
        return ""

    text = html.unescape(value).replace("\r", "\n")

    if preserve_breaks:
        text = _BREAK_TAG_RE.sub("\n", text)
        text = _OPEN_BLOCK_TAG_RE.sub("\n", text)
        text = _CLOSE_BLOCK_TAG_RE.sub("\n", text)
        text = _LIST_ITEM_TAG_RE.sub("\n- ", text)

    text = _HTML_TAG_RE.sub("", text).replace("\xa0", " ")

    if preserve_breaks:
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
    else:
        text = re.sub(r"\s+", " ", text)

    return text.strip()


def sanitize_html_for_prompt(value: str, limit: int | None = None) -> str:
    text = html_to_plain_text(value, preserve_breaks=True)
    text = re.sub(r"\s+", " ", text).strip()
    if limit is not None and limit >= 0:
        text = text[:limit]
    return text
