"""Multi-turn conversational chat service with MCP tool integration.

Allows users to chat about their products using local AI models (Ollama,
LM Studio, etc.) while the AI can autonomously call ikas MCP tools to
fetch real-time store data during the conversation.

Use cases:
  - Product Q&A: "Bu ürünün SEO skoru nasıl iyileştirilir?"
  - Store insights: "En çok satan 5 ürünü listele"
  - SEO coaching: "Başlık uzunluğu neden önemli?"
  - Bulk analysis: "Düşük skorlu ürünleri özetle"
  - Inventory: "Stokta azalan ürünler hangileri?"
"""

import asyncio
import contextlib
import inspect
import json
import logging
import re
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

# Type alias for local tool handlers registered in ToolRegistry
ToolHandler = Callable[[dict[str, Any]], Awaitable[tuple[str, "dict[str, Any] | None"]]]

import httpx

from core.agent.tools import (
    APPLY_SEO_TO_IKAS_TOOL_NAME,
    SAVE_SEO_SUGGESTION_TOOL_NAME,
    ToolRegistry as RuntimeToolRegistry,
    build_apply_seo_to_ikas_tool,
    build_save_seo_suggestion_tool,
)
from core.clients.ikas import IkasClient
from core.models import AppConfig, ChatMessage, ChatResponse, Product, SeoScore, SeoSuggestion
from core.clients.mcp import IkasMCPClient, MCPError
from core.prompt_store import get_agent_system_prompts_tr, load_prompt_template
from core.ai.constants import estimate_cost
from core.chat import guidance as op_guidance
from core.utils.html import sanitize_html_for_prompt

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5  # Max sequential tool-call rounds per message
MAX_HISTORY_MESSAGES = 40  # Keep conversation manageable for context window
HISTORY_SUMMARY_TRIGGER_MESSAGES = 12
HISTORY_SUMMARY_KEEP_RECENT_MESSAGES = 4


def _get_memory_summarization_prompt() -> str:
    return load_prompt_template("chat_memory_summarization_system")


def _get_history_summary_prefix() -> str:
    return load_prompt_template("chat_history_prefix_system")


def _get_product_context_template() -> str:
    return load_prompt_template("chat_product_context_system")


def _get_score_context_template() -> str:
    return load_prompt_template("chat_score_context_system")


def _get_semantic_routing_prompt() -> str:
    return load_prompt_template("chat_semantic_routing_system")


def _get_save_tool_instruction() -> str:
    return load_prompt_template("chat_save_tool_system")


def _get_apply_extraction_prompt() -> str:
    return load_prompt_template("chat_apply_extraction_system")


def _get_suggestion_options_instruction() -> str:
    return load_prompt_template("chat_suggestion_options_system")


def _get_false_action_disclaimer() -> str:
    return "\n\n" + load_prompt_template("chat_false_action_disclaimer_system")


def _get_compact_options_instruction() -> str:
    return load_prompt_template("chat_compact_options_system")


# Backward-compat module-level aliases (stale snapshots; prefer getter functions above)
MEMORY_SUMMARIZATION_PROMPT = _get_memory_summarization_prompt()
HISTORY_SUMMARY_SYSTEM_PREFIX = _get_history_summary_prefix()
CHAT_FLOW_PRODUCT_CONTEXT_TEMPLATE = _get_product_context_template()
CHAT_FLOW_SCORE_CONTEXT_TEMPLATE = _get_score_context_template()
SEMANTIC_ROUTING_SYSTEM_PROMPT = _get_semantic_routing_prompt()
SAVE_SEO_SUGGESTION_TOOL_INSTRUCTION = _get_save_tool_instruction()
APPLY_INTENT_EXTRACTION_SYSTEM_PROMPT = _get_apply_extraction_prompt()
STRUCTURED_SUGGESTION_OPTIONS_INSTRUCTION = _get_suggestion_options_instruction()
FALSE_ACTION_DISCLAIMER_TR = _get_false_action_disclaimer()

# Legacy aliases kept for backward compat — not currently used by runtime code.
IKAS_OPERATION_GUIDE_TR = ""  # loaded from file at runtime via load_prompt_template()
CHAT_OPTION_BUTTONS_INSTRUCTION = ""  # loaded from file at runtime

PRODUCT_CONTEXT_TEMPLATE = CHAT_FLOW_PRODUCT_CONTEXT_TEMPLATE  # backward-compat alias
SCORE_CONTEXT_TEMPLATE = CHAT_FLOW_SCORE_CONTEXT_TEMPLATE  # backward-compat alias

MATCH_NORMALIZATION_TABLE = str.maketrans({
    "\u00c7": "c",
    "\u00e7": "c",
    "\u011e": "g",
    "\u011f": "g",
    "\u0130": "i",
    "\u0131": "i",
    "\u00d6": "o",
    "\u00f6": "o",
    "\u015e": "s",
    "\u015f": "s",
    "\u00dc": "u",
    "\u00fc": "u",
})
SEO_OPERATION_HINT_PATTERN = re.compile(
    r"\bseo\b|\bskor\b|\bissue\b|\bsorun\b|\boneri\b|\bsuggestion\b|\bmeta\b|\bbaslik\b|\btitle\b|\baciklama\b|\bdescription\b|\bicerik\b|\bcontent\b|\bkeyword\b|\betiket\b|\btag\b|\bkategori\b|\bsku\b|\bokunabilirlik\b|\breadability\b|\bteknik seo\b|\btechnical seo\b|\bisim\b|\bname\b",
    re.IGNORECASE,
)
SUGGESTION_REQUEST_HINT_PATTERN = re.compile(
    r"\boneri\b|\bsuggestion\b|\balternatif\b|\bsecenek\b|\bopsiyon\b|\bvaryant\b|\bvariant\b|\byeniden yaz\b|\brewrite\b|\bolustur\b|\buret\b|\byaz\b|\bhazirla\b",
    re.IGNORECASE,
)
SEMANTIC_ROUTING_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

# Patterns that detect when the LLM falsely claims to have performed actions.
# These are matched against normalized (ASCII-like) text.
FALSE_ACTION_CLAIM_NORMALIZED_PATTERN = re.compile(
    r"\b(?:"
    r"uygula(?:n)?d(?:im|i)?|"
    r"guncelle(?:n)?d(?:im|i)?|"
    r"degistir(?:di|dim)?|"
    r"kaydet(?:ti|tim)?|"
    r"ekle(?:di|dim)?|"
    r"yaz(?:di|dim)?|"
    r"duzenle(?:di|dim)?|"
    r"applied|updated|saved|changed|modified"
    r")\b",
    re.IGNORECASE,
)
FALSE_ACTION_CONFIRMATION_NORMALIZED_PATTERN = re.compile(
    r"(?:"
    r"uygulama sonrasi|"
    r"basariyla (?:uygula|guncelle|kaydet)|"
    r"iyilestirilmis skor|"
    r"yeni seo (?:skoru|durumu)|"
    r"yapilan degisiklikler|"
    r"guncellemeler uygulandi|"
    r"successfully (?:applied|updated|saved)"
    r")",
    re.IGNORECASE,
)

SUGGESTION_SAVE_SUCCESS_MESSAGE = "\u00d6neri ba\u015far\u0131yla kaydedildi"
SAVE_SEO_SUGGESTION_FIELD_MAP = {
    "suggested_name": ("name", "suggested_name"),
    "suggested_meta_title": ("meta_title", "suggested_meta_title"),
    "suggested_meta_description": ("meta_desc", "suggested_meta_description"),
    "suggested_description": ("desc_tr", "suggested_description"),
    "suggested_description_en": ("desc_en", "suggested_description_en"),
}
SUGGESTION_APPLY_FIELD_CONFIG: dict[str, dict[str, str]] = {
    "suggested_name": {
        "label": "Urun Adi",
        "original_attr": "original_name",
        "update_key": "name",
    },
    "suggested_meta_title": {
        "label": "Meta Title",
        "original_attr": "original_meta_title",
        "update_key": "meta_title",
    },
    "suggested_meta_description": {
        "label": "Meta Description",
        "original_attr": "original_meta_description",
        "update_key": "meta_description",
    },
    "suggested_description": {
        "label": "Aciklama (TR)",
        "original_attr": "original_description",
        "update_key": "description",
    },
    "suggested_description_en": {
        "label": "Aciklama (EN)",
        "original_attr": "original_description_en",
        "update_key": "description_en",
    },
}
CHAT_ACTION_PATTERN = re.compile(r"\[\[CHAT_ACTION:([a-z0-9_-]+)(?::(.+?))?\]\]", re.IGNORECASE | re.DOTALL)
GENERATE_SUGGESTION_MARKER = "[[GENERATE_SUGGESTION]]"
GENERATE_SUGGESTION_PATTERN = re.compile(r"\[\[GENERATE_SUGGESTION\]\]\s*", re.IGNORECASE)
APPLY_INTENT_PATTERN = re.compile(
    r"\b(uygula|uygulansin|onayla|evet uygula|evet|tamam uygula)\b",
    re.IGNORECASE,
)
SAVE_INTENT_PATTERN = re.compile(
    r"\b(kaydet|taslak olarak kaydet|pending olarak kaydet|listeye kaydet)\b",
    re.IGNORECASE,
)
NON_FINAL_SUGGESTION_VALUE_PATTERN = re.compile(
    r"\b("
    r"gerekli|ekle|eklenmeli|ekleyin|yeniden yaz(?:im)?|"
    r"civari|karakter|ozet|özet|anahtar kelime odakli|"
    r"guncelle|duzelt|iyilestir|gelistir|geliştir"
    r")\b",
    re.IGNORECASE,
)
MANUAL_APPLY_ACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(vazgec|vazgeciyorum|iptal|hayir)\b", re.IGNORECASE), "single_apply_cancel"),
    (re.compile(r"\b(sadece meta|meta alan)\b", re.IGNORECASE), "single_apply_meta"),
    (re.compile(r"\b(sadece icerik|sadece aciklama|icerik alan)\b", re.IGNORECASE), "single_apply_content"),
    (re.compile(r"\b(hepsini|tumunu|tamamini|tum alanlari|evet|tamam)\b", re.IGNORECASE), "single_apply_all"),
]
SINGLE_PRODUCT_APPLY_ACTIONS = frozenset({
    "single_apply_meta",
    "single_apply_content",
    "single_apply_meta_content",
    "single_apply_all",
    "single_apply_cancel",
    "single_apply_confirm",
    "single_apply_execute",
})


def _build_save_seo_suggestion_tool() -> dict[str, Any]:
    return build_save_seo_suggestion_tool().to_openai_function()

# GraphQL mutation used by the apply_seo_to_ikas tool when routing through MCP
_MCP_SAVE_PRODUCT_MUTATION = """mutation SaveProduct($input: ProductInput!) {
  saveProduct(input: $input) {
    id
    name
    description
    metaData { pageTitle description }
  }
}"""


def _build_apply_seo_to_ikas_tool() -> dict[str, Any]:
    return build_apply_seo_to_ikas_tool().to_openai_function()


SELECTED_PRODUCT_LIVE_QUERY = """query listProduct($id: StringFilterInput, $pagination: PaginationInput) {
  listProduct(id: $id, pagination: $pagination) {
    count
    data {
      id
      name
      totalStock
      metaData {
        slug
      }
      categories {
        id
        name
      }
      variants {
        id
        sku
        sellIfOutOfStock
        stocks {
          stockCount
          stockLocationId
        }
        prices {
          sellPrice
          discountPrice
          currencyCode
        }
      }
    }
  }
}"""


def _extract_chat_completion_content(data: Any) -> str:
    if not isinstance(data, dict):
        return ""

    choices = data.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""

    choice = choices[0]
    if not isinstance(choice, dict):
        return ""

    message = choice.get("message", {})
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        joined = "".join(parts).strip()
        if joined:
            return joined

    # Thinking models (Qwen, DeepSeek) may place the answer in reasoning_content
    # when content is empty.
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return ""


def _parse_agent_type(content: str) -> str | None:
    candidate = (content or "").strip()
    if not candidate:
        return None

    # Strip <think>...</think> blocks from thinking models (Qwen, DeepSeek, etc.)
    candidate = re.sub(r"<think>.*?</think>", "", candidate, flags=re.DOTALL).strip()
    if not candidate:
        return None

    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)

    # Try direct match for bare agent type words (no JSON wrapper)
    bare = candidate.strip().strip('"').strip("'").lower()
    if bare in {"seo", "operator", "general"}:
        return bare

    if not candidate.startswith("{"):
        match = SEMANTIC_ROUTING_JSON_PATTERN.search(candidate)
        if not match:
            return None
        candidate = match.group(0)

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    agent_type = payload.get("agent_type")
    if not isinstance(agent_type, str):
        return None

    normalized = agent_type.strip().lower()
    if normalized in {"seo", "operator", "general"}:
        return normalized

    # Fallback: scan for agent type keywords anywhere in the response (for
    # smaller models that return explanatory text instead of pure JSON).
    lower_text = re.sub(r"<think>.*?</think>", "", (content or ""), flags=re.DOTALL).lower()
    for keyword in ("operator", "seo", "general"):
        if re.search(rf"\b{keyword}\b", lower_text):
            return keyword
    return None


_COMPACT_OPTION_BUTTONS_INSTRUCTION = _get_compact_options_instruction()  # backward-compat


# Field metadata: (score_attr, max_points, label for buttons, description)
_FIELD_PRIORITY_DEFS: list[tuple[str, int, str, str]] = [
    ("english_description_score", 5, "EN Açıklama", "İngilizce açıklamayı oluştur/iyileştir"),
    ("title_score", 15, "Ürün Adı", "Ürün adını SEO için optimize et"),
    ("meta_score", 15, "Meta Title", "Meta title'ı iyileştir"),
    ("meta_desc_score", 10, "Meta Description", "Meta description'ı iyileştir"),
    ("description_score", 20, "TR Açıklama", "Türkçe açıklamayı iyileştir"),
    ("keyword_score", 10, "Anahtar Kelime", "Anahtar kelime optimizasyonu yap"),
    ("content_quality_score", 10, "İçerik Kalitesi", "İçerik kalitesini artır"),
    ("technical_seo_score", 10, "Teknik SEO", "Teknik SEO sorunlarını düzelt"),
    ("readability_score", 5, "Okunabilirlik", "Okunabilirlik skorunu artır"),
    ("ai_citability_score", 10, "AI Alıntılama", "AI alıntılama skorunu artır"),
]


def _build_field_priority_options(score: "SeoScore") -> str:
    """Build a priority-sorted JSON option list from score breakdown.

    Returns a string like:
    [{"tone":"EN Açıklama (0/5)","value":"İngilizce açıklamayı oluştur/iyileştir"}, ...]
    sorted by score percentage ascending (worst fields first).
    """
    field_scores: list[tuple[float, str, int, int, str]] = []
    for attr, max_pts, label, desc in _FIELD_PRIORITY_DEFS:
        pts = getattr(score, attr, 0) or 0
        pct = (pts / max_pts * 100) if max_pts > 0 else 100
        field_scores.append((pct, label, pts, max_pts, desc))

    # Sort by percentage ascending (worst first)
    field_scores.sort(key=lambda x: x[0])

    options: list[dict[str, str]] = []
    for pct, label, pts, max_pts, desc in field_scores:
        if pct >= 100:
            continue  # Skip perfect-score fields
        tag = f"{label} ({pts}/{max_pts})"
        options.append({"tone": tag, "value": desc})

    if not options:
        return '[{"tone":"Tüm alanlar iyi","value":"Tüm SEO alanları yeterli seviyede."}]'

    return json.dumps(options, ensure_ascii=False)


def _build_product_context(
    product: Product | None,
    score: SeoScore | None,
    agent_type: str = "general",
    *,
    compact: bool = False,
) -> str:
    """Build product context string for the system prompt.

    When *compact* is True the verbose examples and operation guide are
    replaced with minimal one-liners to stay within tight context windows.
    """
    product_ctx = ""
    score_ctx = ""

    if product:
        desc_source = sanitize_html_for_prompt(product.description)
        desc_preview = desc_source[:2000]
        if len(desc_source) > 2000:
            desc_preview += "..."
        product_ctx = _get_product_context_template().format(
            name=product.name,
            category=product.category or "-",
            price=f"{product.price:.2f} TL" if product.price else "-",
            sku=product.sku or "-",
            status=product.status,
            meta_title=product.meta_title or "-",
            meta_description=product.meta_description or "-",
            tags=", ".join(product.tags) if product.tags else "-",
            description_preview=desc_preview or "-",
        )

    if score:
        field_priority_options = _build_field_priority_options(score)
        score_ctx = _get_score_context_template().format(
            total_score=score.total_score,
            seo_score=score.seo_score,
            geo_score=score.geo_score,
            aeo_score=score.aeo_score,
            title_score=score.title_score,
            description_score=score.description_score,
            english_description_score=score.english_description_score,
            meta_score=score.meta_score,
            meta_desc_score=score.meta_desc_score,
            keyword_score=score.keyword_score,
            content_quality_score=score.content_quality_score,
            technical_seo_score=score.technical_seo_score,
            readability_score=score.readability_score,
            ai_citability_score=score.ai_citability_score,
            issues="; ".join(score.issues[:8]) if score.issues else "Yok",
            field_priority_options=field_priority_options,
        )

    agent_prompts = get_agent_system_prompts_tr()
    template = agent_prompts.get(agent_type, agent_prompts["general"])
    base_prompt = template.format(
        product_context=product_ctx,
        score_context=score_ctx,
    )

    if compact:
        return base_prompt + "\n\n" + _get_compact_options_instruction()

    return (
        base_prompt
        + "\n\n"
        + load_prompt_template("chat_option_buttons_system")
        + "\n\n"
        + load_prompt_template("ikas_operation_guide_system")
    )


def _build_tool_catalog_instruction(
    tool_summaries: list[dict[str, str]],
) -> str | None:
    if not tool_summaries:
        return None

    tool_names = [tool["name"] for tool in tool_summaries if tool.get("name")]
    instructions = [
        "MCP araci kullanacaksan yalnizca asagidaki tam tool adlarini kullan.",
        "Tool adi uydurma; listede olmayan isim kullanma.",
    ]

    if any(name.startswith("update") or name.startswith("create") or name.startswith("delete") for name in tool_names):
        instructions.append(
            "Kullanici acikca degisiklik istemedikce mutation kullanma; once query araclari tercih et."
        )

    visible_names = ", ".join(tool_names[:40])
    instructions.append(f"Kullanilabilir toollar: {visible_names}")
    return " ".join(instructions)


def _build_local_no_think_instruction(config: AppConfig) -> str | None:
    if config.ai_thinking_mode_chat:
        return None
    # Providers whose models commonly produce <think> blocks
    if config.ai_provider in ("ollama", "lm-studio", "openrouter", "custom"):
        return (
            "Ic muhakemeyi, <think> bloklarini ve uzun dusunce metinlerini "
            "yazma; dogrudan nihai yaniti ver. /no_think"
        )
    return None


def _normalize_matching_text(text: str) -> str:
    return (text or "").translate(MATCH_NORMALIZATION_TABLE).lower()


def _should_request_structured_suggestion_options(user_message: str) -> bool:
    normalized_text = _normalize_matching_text(user_message)
    return bool(
        normalized_text
        and SEO_OPERATION_HINT_PATTERN.search(normalized_text)
        and SUGGESTION_REQUEST_HINT_PATTERN.search(normalized_text)
    )


def _extract_chat_action(text: str) -> str | None:
    match = CHAT_ACTION_PATTERN.search(text or "")
    if not match:
        return None
    action = (match.group(1) or "").strip().lower()
    return action or None


def _extract_chat_action_payload(text: str) -> str | None:
    """Extract the optional JSON payload from a CHAT_ACTION directive."""
    match = CHAT_ACTION_PATTERN.search(text or "")
    if not match:
        return None
    payload = (match.group(2) or "").strip()
    return payload or None


def _message_has_apply_intent(text: str) -> bool:
    normalized_text = _normalize_matching_text(text)
    return bool(normalized_text and APPLY_INTENT_PATTERN.search(normalized_text))


def _message_has_save_intent(text: str) -> bool:
    normalized_text = _normalize_matching_text(text)
    return bool(normalized_text and SAVE_INTENT_PATTERN.search(normalized_text))


def _detect_manual_apply_action(normalized_text: str) -> str | None:
    if not normalized_text:
        return None

    for pattern, action in MANUAL_APPLY_ACTION_PATTERNS:
        if pattern.search(normalized_text):
            return action
    return None


def _looks_like_final_suggestion_value(value: str) -> bool:
    cleaned = re.sub(r"\s+", " ", (value or "").strip(" `\"'"))
    if len(cleaned) < 4:
        return False
    if NON_FINAL_SUGGESTION_VALUE_PATTERN.search(cleaned):
        return False
    return True


def _looks_like_option_selection(text: str) -> bool:
    """
    Detect user phrases like "1. secenegi sec" that imply an option button click.
    Helpful when the user types instead of clicking the structured card.
    """
    normalized = _normalize_matching_text(text)
    if not normalized:
        return False

    patterns = [
        re.compile(r"\b\d+\s*\.?\s*seceneg[iı]\s*sec", re.IGNORECASE),
        re.compile(r"\bilk\s*seceneg[iı]\s*sec", re.IGNORECASE),
        re.compile(r"\bsecenek\s*\d+\s*sec", re.IGNORECASE),
    ]
    return any(p.search(normalized) for p in patterns)


_OPTION_INDEX_PATTERN = re.compile(r"\b(\d+)\s*\.?\s*seceneg", re.IGNORECASE)
_OPTION_FIRST_PATTERN = re.compile(r"\bilk\s*seceneg", re.IGNORECASE)


def _extract_option_index(text: str) -> int | None:
    """Extract the 1-based option index from a typed option selection phrase."""
    normalized = _normalize_matching_text(text)
    if not normalized:
        return None
    m = _OPTION_INDEX_PATTERN.search(normalized)
    if m:
        return int(m.group(1))
    if _OPTION_FIRST_PATTERN.search(normalized):
        return 1
    return None


def _extract_options_from_assistant_message(content: str) -> list[dict[str, str]]:
    """Parse structured option JSON from an assistant message."""
    # Try ```json ... ``` blocks first
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", content):
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict) and "tone" in parsed[0]:
                return parsed
        except (json.JSONDecodeError, TypeError):
            continue
    # Try trailing array
    trailing = re.search(r"(\[[\s\S]*\])\s*$", content)
    if trailing:
        try:
            parsed = json.loads(trailing.group(1))
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict) and "tone" in parsed[0]:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def _resolve_typed_option_selection(
    user_text: str,
    history: list,
) -> str | None:
    """Resolve a typed option selection to an enriched message like the frontend sends.

    Walks backward through *history* to find the last assistant message with
    structured option buttons, extracts the selected option by index, and
    returns a message identical to what the frontend would have sent (minus
    the ``[[GENERATE_SUGGESTION]]`` marker which the caller adds separately).

    Returns ``None`` if no matching option is found.
    """
    idx = _extract_option_index(user_text)
    if idx is None:
        return None

    # Walk history backwards to find the last assistant message with options
    for msg in reversed(history):
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        content = getattr(msg, "content", None) or (msg.get("content", "") if isinstance(msg, dict) else "")
        if role != "assistant" or not content:
            continue
        options = _extract_options_from_assistant_message(content)
        if not options:
            continue
        if 1 <= idx <= len(options):
            opt = options[idx - 1]
            tone = opt.get("tone", "")
            value = opt.get("value", "")
            return (
                f"{idx}. secenegi sectim.\n"
                f"Ton: {tone}\n"
                f"Icerik: {value}\n"
                f"Bu secenek dogrultusunda urun icin somut SEO degerleri olustur ve save_seo_suggestion araci ile kaydet."
            )
        break  # Found options but index out of range
    return None


def _decode_json_string_fragment(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return ""
    try:
        return json.loads(f'"{candidate}"')
    except Exception:
        return candidate.replace('\\"', '"').replace("\\n", "\n")


def _detect_suggestion_field_heading(line: str) -> str | None:
    normalized = _normalize_matching_text(re.sub(r"^\d+\.\s*", "", line or "").strip())
    if not normalized:
        return None
    if "meta title" in normalized:
        return "suggested_meta_title"
    if "meta description" in normalized:
        return "suggested_meta_description"
    if "ingilizce aciklama" in normalized or "english description" in normalized or "aciklama (en" in normalized:
        return "suggested_description_en"
    if "urun adi" in normalized or "urun adı" in normalized or normalized.startswith("baslik"):
        return "suggested_name"
    if "aciklama" in normalized and "meta" not in normalized:
        return "suggested_description"
    return None


def _extract_suggestion_fields_from_text(content: str) -> dict[str, str]:
    extracted: dict[str, str] = {}
    if not content.strip():
        return extracted

    json_field_patterns = {
        "suggested_name": [
            r'"suggested_name"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"product_name"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
        "suggested_meta_title": [
            r'"suggested_meta_title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"meta_title"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
        "suggested_meta_description": [
            r'"suggested_meta_description"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"meta_description"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
        "suggested_description": [
            r'"suggested_description"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"turkish"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
        "suggested_description_en": [
            r'"suggested_description_en"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r'"english"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ],
    }
    for field_name, patterns in json_field_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            candidate = _decode_json_string_fragment(match.group(1))
            if _looks_like_final_suggestion_value(candidate):
                extracted[field_name] = candidate.strip()
                break

    lines = [line.rstrip() for line in content.splitlines()]
    current_field: str | None = None

    direct_patterns: list[tuple[str, re.Pattern[str]]] = [
        ("suggested_name", re.compile(r"^(?:[-*]\s*)?(?:urun adi|urun adı|product name)\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
        ("suggested_meta_title", re.compile(r"^(?:[-*]\s*)?meta title\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
        ("suggested_meta_description", re.compile(r"^(?:[-*]\s*)?meta description\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
        ("suggested_description", re.compile(r"^(?:[-*]\s*)?(?:turkce aciklama|turkçe aciklama|aciklama \(tr\)|aciklama)\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
        ("suggested_description_en", re.compile(r"^(?:[-*]\s*)?(?:ingilizce aciklama|english description|aciklama \(en\))\s*(?:onerisi|önerisi)?\s*:\s*(.+)$", re.IGNORECASE)),
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        heading_field = _detect_suggestion_field_heading(stripped)
        if heading_field and ":" not in stripped:
            current_field = heading_field
            continue

        if stripped.lower().startswith("mevcut:"):
            continue

        value_match = re.match(r"^(?:oneri|öneri|uygulanacak)\s*:\s*(.+)$", stripped, re.IGNORECASE)
        if value_match and current_field:
            candidate = value_match.group(1).strip()
            if _looks_like_final_suggestion_value(candidate):
                extracted.setdefault(current_field, candidate)
            continue

        for field_name, pattern in direct_patterns:
            direct_match = pattern.match(stripped)
            if not direct_match:
                continue
            candidate = direct_match.group(1).strip()
            if _looks_like_final_suggestion_value(candidate):
                extracted.setdefault(field_name, candidate)
            break

    return extracted


def _compact_preview_text(value: str, *, limit: int = 180) -> str:
    collapsed = re.sub(r"\s+", " ", (value or "").strip())
    if not collapsed:
        return "-"
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit - 3]}..."


def _operation_footer_already_present(text: str) -> bool:
    return op_guidance.operation_footer_already_present(text)


def _select_product_operation_suggestion(
    user_message: str,
    response_text: str,
    product: Product | None,
    agent_type: str,
) -> tuple[str, str, bool]:
    return op_guidance.select_product_operation_suggestion(
        user_message,
        response_text,
        product.name if product else None,
        agent_type,
        save_suggestion_tool_name=SAVE_SEO_SUGGESTION_TOOL_NAME,
    )


def _append_operation_suggestion(
    response_text: str,
    *,
    user_message: str,
    product: Product | None,
    agent_type: str,
) -> str:
    return op_guidance.append_operation_suggestion(
        response_text,
        user_message=user_message,
        product_name=product.name if product else None,
        agent_type=agent_type,
        save_suggestion_tool_name=SAVE_SEO_SUGGESTION_TOOL_NAME,
    )


def _has_mutation_tool_result(tool_results: list[dict[str, Any]]) -> bool:
    """Check if any tool result is from a mutation (write) operation."""
    return op_guidance.has_mutation_tool_result(tool_results)


def _append_false_action_disclaimer(
    response_text: str,
    tool_results: list[dict[str, Any]],
) -> str:
    """Append a disclaimer if the LLM claims to have applied changes but no mutation was executed."""
    return op_guidance.append_false_action_disclaimer(response_text, tool_results)


def _format_chat_error(exc: Exception) -> str:
    if isinstance(exc, httpx.ReadTimeout):
        return (
            "AI istegi zaman asimina ugradi. Yerel model dusunce modunda takilmis olabilir; "
            "daha kisa bir istek deneyin veya Thinking Mode'u kapatin."
        )
    if isinstance(exc, httpx.ConnectError):
        return "AI endpoint'ine baglanilamadi. Base URL ve model server durumunu kontrol edin."
    if isinstance(exc, httpx.HTTPStatusError):
        return f"AI endpoint'i HTTP {exc.response.status_code} dondu."

    text = str(exc).strip()
    return f"AI hatasi: {text}" if text else "AI istegi basarisiz oldu."


def _extract_mcp_text(result: dict[str, Any]) -> str:
    content = result.get("content")
    if not isinstance(content, list):
        return json.dumps(result, ensure_ascii=False)

    text_parts = [
        str(item.get("text", ""))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    text = "\n".join(part for part in text_parts if part).strip()
    return text or json.dumps(result, ensure_ascii=False)


def _extract_mcp_json_payload(result: dict[str, Any]) -> dict[str, Any]:
    text = _extract_mcp_text(result)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _format_decimal(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _format_money(price: dict[str, Any]) -> str:
    sell_price = price.get("sellPrice")
    discount_price = price.get("discountPrice")
    currency = str(price.get("currencyCode") or "").strip()
    sell_text = _format_decimal(sell_price)
    discount_text = _format_decimal(discount_price)
    currency_text = f" {currency}" if currency else ""
    if isinstance(discount_price, (int, float)):
        return f"{sell_text}{currency_text} (indirimli: {discount_text}{currency_text})"
    return f"{sell_text}{currency_text}"


def _first_number(*values: Any) -> int | float | None:
    for value in values:
        if isinstance(value, (int, float)):
            return value
    return None


def _build_completion_meta(data: dict[str, Any], model: str, finish_reason: str) -> dict[str, Any]:
    usage = data.get("usage", {}) if isinstance(data, dict) else {}
    stats = data.get("stats", {}) if isinstance(data, dict) else {}
    model_info = data.get("model_info", {}) if isinstance(data, dict) else {}

    input_tokens = _first_number(
        usage.get("prompt_tokens") if isinstance(usage, dict) else None,
        stats.get("input_tokens") if isinstance(stats, dict) else None,
    )
    output_tokens = _first_number(
        usage.get("completion_tokens") if isinstance(usage, dict) else None,
        stats.get("total_output_tokens") if isinstance(stats, dict) else None,
        stats.get("output_tokens") if isinstance(stats, dict) else None,
    )
    total_tokens = _first_number(
        usage.get("total_tokens") if isinstance(usage, dict) else None,
        (
            (int(input_tokens) if isinstance(input_tokens, (int, float)) else 0)
            + (int(output_tokens) if isinstance(output_tokens, (int, float)) else 0)
        ),
    )

    meta: dict[str, Any] = {
        "model": data.get("model", model),
        "finish_reason": finish_reason,
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }

    extra_fields = {
        "tokens_per_second": _first_number(
            stats.get("tokens_per_second") if isinstance(stats, dict) else None,
        ),
        "time_to_first_token_seconds": _first_number(
            stats.get("time_to_first_token_seconds") if isinstance(stats, dict) else None,
        ),
        "reasoning_output_tokens": _first_number(
            stats.get("reasoning_output_tokens") if isinstance(stats, dict) else None,
        ),
        "context_length": _first_number(
            model_info.get("context_length") if isinstance(model_info, dict) else None,
            model_info.get("max_context_length") if isinstance(model_info, dict) else None,
            stats.get("context_length") if isinstance(stats, dict) else None,
        ),
        "stop_reason": str(data.get("stop_reason") or (stats.get("stop_reason") if isinstance(stats, dict) else "") or ""),
    }

    prompt_tokens = meta["input_tokens"]
    context_length = extra_fields["context_length"]
    if isinstance(context_length, (int, float)) and context_length > 0:
        meta["context_length"] = int(context_length)
        meta["context_used_percent"] = round((prompt_tokens / context_length) * 100, 1)
        meta["context_remaining_percent"] = round(max(0.0, 100 - meta["context_used_percent"]), 1)

    for key, value in extra_fields.items():
        if key in {"context_length"}:
            continue
        if isinstance(value, (int, float)):
            meta[key] = value
        elif isinstance(value, str) and value:
            meta[key] = value

    # Estimate cost from model name and token counts
    cost = estimate_cost(str(meta.get("model", "")), meta["input_tokens"], meta["output_tokens"])
    if cost > 0:
        meta["estimated_cost"] = cost

    return meta


def _extract_stream_delta_content(delta: dict[str, Any]) -> str:
    content = delta.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return ""


def _lm_studio_native_base(configured_base_url: str) -> str:
    """Return LM Studio's native API root by stripping the /v1 suffix if present."""
    base = (configured_base_url or "http://localhost:1234").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base


class _LMStudioNativeUnavailable(Exception):
    """Raised when the LM Studio native /api/v1/chat endpoint returns 404/405/501."""


class _StreamingVisibleTextFilter:
    """Hide <think> blocks while still streaming visible assistant text."""

    _OPEN_TAG = "<think>"
    _CLOSE_TAG = "</think>"

    def __init__(self) -> None:
        self._inside_think = False
        self._pending_tag = ""
        self._thinking_buffer: list[str] = []

    def consume(self, chunk: str) -> str:
        if not chunk:
            return ""

        text = f"{self._pending_tag}{chunk}"
        self._pending_tag = ""
        visible_parts: list[str] = []
        index = 0

        while index < len(text):
            remainder = text[index:]
            if remainder.startswith(self._OPEN_TAG):
                self._inside_think = True
                index += len(self._OPEN_TAG)
                continue
            if remainder.startswith(self._CLOSE_TAG):
                self._inside_think = False
                index += len(self._CLOSE_TAG)
                continue

            if text[index] == "<":
                partial_tag = self._match_partial_tag(remainder)
                if partial_tag is not None:
                    self._pending_tag = partial_tag
                    break

            if not self._inside_think:
                visible_parts.append(text[index])
            else:
                self._thinking_buffer.append(text[index])
            index += 1

        return "".join(visible_parts)

    def drain_thinking(self) -> str:
        """Return and clear any captured thinking content."""
        if not self._thinking_buffer:
            return ""
        text = "".join(self._thinking_buffer)
        self._thinking_buffer.clear()
        return text

    def finalize(self) -> str:
        if self._inside_think or not self._pending_tag:
            self._pending_tag = ""
            return ""

        trailing_text = self._pending_tag
        self._pending_tag = ""
        return trailing_text

    @classmethod
    def _match_partial_tag(cls, text: str) -> str | None:
        for tag in (cls._OPEN_TAG, cls._CLOSE_TAG):
            if tag.startswith(text) and text != tag:
                return text
        return None


def _merge_stream_tool_call(
    tool_calls_by_index: dict[int, dict[str, Any]],
    tool_call_delta: dict[str, Any],
) -> None:
    raw_index = tool_call_delta.get("index", 0)
    index = raw_index if isinstance(raw_index, int) else 0
    tool_call = tool_calls_by_index.setdefault(index, {
        "id": "",
        "type": "function",
        "function": {
            "name": "",
            "arguments": "",
        },
    })

    tool_call_id = tool_call_delta.get("id")
    if isinstance(tool_call_id, str) and tool_call_id:
        tool_call["id"] = tool_call_id

    tool_call_type = tool_call_delta.get("type")
    if isinstance(tool_call_type, str) and tool_call_type:
        tool_call["type"] = tool_call_type

    function_delta = tool_call_delta.get("function", {})
    if not isinstance(function_delta, dict):
        return

    function_payload = tool_call.setdefault("function", {"name": "", "arguments": ""})
    name = function_delta.get("name")
    if isinstance(name, str) and name:
        function_payload["name"] = f"{function_payload.get('name', '')}{name}"

    arguments = function_delta.get("arguments")
    if isinstance(arguments, str) and arguments:
        function_payload["arguments"] = f"{function_payload.get('arguments', '')}{arguments}"


# LM Studio native event names (compat endpoint) that carry no text content
_LM_STUDIO_NON_CONTENT_EVENTS: frozenset[str] = frozenset({
    "chat.start", "chat.end",
    "model_load.start", "model_load.progress", "model_load.end",
    "prompt_processing.start", "prompt_processing.progress",
    "prompt_processing.end",
    "reasoning.start", "reasoning.end",
    "tool_call.start", "tool_call.arguments",
    "tool_call.success", "tool_call.failure",
    "message.start", "message.end",
    "error",
})


def _apply_choice_delta(
    choice: dict[str, Any],
    visible_text_filter: "_StreamingVisibleTextFilter",
    tool_calls_by_index: dict[int, dict[str, Any]],
) -> tuple[str, str, str, str]:
    """Process one OpenAI-style choice delta. Mutates tool_calls_by_index.

    Returns (content_delta, finish_reason, visible_chunk, reasoning_delta).
    visible_chunk is empty when tool calls are already pending.
    reasoning_delta carries ``reasoning_content`` from providers like LM Studio / Qwen.
    """
    delta = choice.get("delta", {})
    if not isinstance(delta, dict):
        delta = {}

    raw_finish_reason = choice.get("finish_reason")
    finish_reason = raw_finish_reason if isinstance(raw_finish_reason, str) and raw_finish_reason else ""

    content_delta = _extract_stream_delta_content(delta)
    visible_chunk = ""
    if content_delta:
        visible = visible_text_filter.consume(content_delta)
        if visible and not tool_calls_by_index:
            visible_chunk = visible

    # Extract reasoning_content (used by LM Studio, Qwen, DeepSeek, etc.)
    reasoning_raw = delta.get("reasoning_content")
    reasoning_delta = reasoning_raw if isinstance(reasoning_raw, str) else ""

    delta_tool_calls = delta.get("tool_calls")
    if isinstance(delta_tool_calls, list):
        for tc_delta in delta_tool_calls:
            if isinstance(tc_delta, dict):
                _merge_stream_tool_call(tool_calls_by_index, tc_delta)

    return content_delta, finish_reason, visible_chunk, reasoning_delta


def _merge_stream_meta_payload(target: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(target)

    model_name = payload.get("model")
    if isinstance(model_name, str) and model_name:
        merged["model"] = model_name

    for key in ("usage", "stats", "model_info", "stop_reason"):
        value = payload.get(key)
        if value not in (None, "", {}, []):
            merged[key] = value

    return merged


class ToolRegistry(RuntimeToolRegistry):
    """Backward-compatible alias for the shared Tool Runtime v2 registry."""


