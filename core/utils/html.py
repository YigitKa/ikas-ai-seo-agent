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
_BULLET_LINE_RE = re.compile(r"^[-*•]\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


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


def plain_text_to_basic_html(value: str) -> str:
    if not value:
        return ""

    normalized = html.unescape(value).replace("\r", "\n").strip()
    if not normalized or has_html_markup(normalized):
        return normalized

    raw_lines = [line.strip() for line in normalized.split("\n")]
    non_empty_lines = [line for line in raw_lines if line]

    if len(non_empty_lines) <= 1:
        sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(normalized) if part.strip()]
        if len(sentences) >= 3:
            non_empty_lines = [
                " ".join(sentences[index:index + 2]).strip()
                for index in range(0, len(sentences), 2)
            ]

    blocks: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        nonlocal list_items
        if not list_items:
            return
        items_html = "".join(f"<li>{html.escape(item)}</li>" for item in list_items)
        blocks.append(f"<ul>{items_html}</ul>")
        list_items = []

    for line in non_empty_lines:
        if _BULLET_LINE_RE.match(line):
            list_items.append(_BULLET_LINE_RE.sub("", line).strip())
            continue
        flush_list()
        blocks.append(f"<p>{html.escape(line)}</p>")

    flush_list()
    return "\n".join(blocks).strip()
