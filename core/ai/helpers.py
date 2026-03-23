"""Stateless helper/utility functions for AI response parsing and processing."""

import json
import logging
import re

from core.models import AppConfig
from core.ai.constants import (
    SYSTEM_PROMPT_TR,
    SYSTEM_PROMPT_EN,
    FIELD_MAX_OUTPUT_TOKENS,
    PROVIDER_BASE_URLS,
)

logger = logging.getLogger(__name__)


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
    text = raw_text.strip()
    thinking_parts: list[str] = []

    # 1) Extract <think>...</think> XML blocks
    think_xml_matches = list(re.finditer(r"<think>([\s\S]*?)</think>", text))
    for m in think_xml_matches:
        thinking_parts.append(m.group(1).strip())
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # 2) If text starts with JSON or markdown fence, no thinking preamble
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("[") or stripped.startswith("```"):
        return "\n\n".join(thinking_parts), text

    # 3) Text has non-JSON preamble (model is thinking/reasoning).
    #    Find the last valid non-placeholder JSON object and treat
    #    everything before it as thinking text.
    json_obj_pattern = re.compile(r"\{[^{}]*\}")  # non-nested JSON objects
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
    # First extract thinking content
    thinking_text, text = _extract_thinking(raw_text)

    if not text.strip():
        logger.error(f"No JSON content after stripping thinking (thinking length: {len(thinking_text)})")
        raise ValueError(
            "AI yaniti JSON icerik uretmeden tamamlandi (muhtemelen token limiti). "
            "Max Tokens degerini artirin veya Thinking Mode'u kapatin."
        )

    # 1) Strip markdown code fences (```json ... ``` or ``` ... ```)
    fence_match = re.search(r"```(?:json)?\s*\n([\s\S]*?)```", text)
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
    json_obj_matches = list(re.finditer(r"\{[^{}]*\}", text))
    for m in reversed(json_obj_matches):
        candidate = m.group(0)
        try:
            parsed = json.loads(candidate)
            if not _is_placeholder_json(parsed):
                return parsed, thinking_text
        except json.JSONDecodeError:
            continue

    # 4) Fallback: greedy { ... } for nested JSON
    brace_match = re.search(r"\{[\s\S]*\}", text)
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
