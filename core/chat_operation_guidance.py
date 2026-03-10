"""Operation guidance helpers extracted from chat_service.

Keeps suggestion footer and false-action safety logic isolated so ChatService
focuses on orchestration.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_SAVE_SEO_SUGGESTION_TOOL_NAME = "save_seo_suggestion"

MATCH_NORMALIZATION_TABLE = str.maketrans({
    "Ç": "c",
    "ç": "c",
    "Ğ": "g",
    "ğ": "g",
    "İ": "i",
    "ı": "i",
    "Ö": "o",
    "ö": "o",
    "Ş": "s",
    "ş": "s",
    "Ü": "u",
    "ü": "u",
})

SEO_OPERATION_HINT_PATTERN = re.compile(
    r"\bseo\b|\bskor\b|\bissue\b|\bsorun\b|\boneri\b|\bsuggestion\b|\bmeta\b|\bbaslik\b|\btitle\b|\baciklama\b|\bdescription\b|\bicerik\b|\bcontent\b|\bkeyword\b|\betiket\b|\btag\b|\bkategori\b|\bsku\b|\bokunabilirlik\b|\breadability\b|\bteknik seo\b|\btechnical seo\b|\bisim\b|\bname\b",
    re.IGNORECASE,
)

APPLY_INTENT_PATTERN = re.compile(
    r"\b(uygula|uygulansin|onayla|ikas'a uygula|ikas a uygula|mcp ile uygula|kaydet)\b",
    re.IGNORECASE,
)

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

FALSE_ACTION_DISCLAIMER_TR = (
    "\n\n---\n"
    "⚠️ **Not:** Yukarıdaki öneriler henüz uygulanmadı. "
    "Degisiklikleri chat uzerinden secili urunde uygulamak icin:\n"
    "- `@ikas uygula` yazarak onay akisina girin,\n"
    "- Sohbetteki **Öneriler** kartlarindan birini onaylayin."
)


def normalize_matching_text(text: str) -> str:
    return (text or "").translate(MATCH_NORMALIZATION_TABLE).lower()


def operation_footer_already_present(text: str) -> bool:
    return "ikas mcp operasyon onerisi" in normalize_matching_text(text)


def select_product_operation_suggestion(
    user_message: str,
    response_text: str,
    product_name: str | None,
    agent_type: str,
    *,
    save_suggestion_tool_name: str = DEFAULT_SAVE_SEO_SUGGESTION_TOOL_NAME,
) -> tuple[str, str, bool]:
    normalized_text = normalize_matching_text(f"{user_message}\n{response_text}")
    subject = (product_name or "").strip() or "secili urun"

    if agent_type == "operator" and APPLY_INTENT_PATTERN.search(normalized_text):
        return (
            "updateProduct",
            f"{subject} icin onaylanan SEO alanlarini ikas tarafinda guncellemek icin uygun mutation",
            True,
        )

    if SEO_OPERATION_HINT_PATTERN.search(normalized_text):
        if agent_type == "operator":
            return (
                "listProduct",
                f"{subject} kaydini canli veride dogrulayip degisiklik oncesi alanlari netlestirmek icin uygun query",
                False,
            )
        return (
            save_suggestion_tool_name,
            f"{subject} icin onaylanan SEO degisikliklerini pending suggestion olarak kaydetmek icin uygun chat araci",
            False,
        )

    return (
        "listProduct",
        f"{subject} kaydini dogrulamak ve eldeki urun alanlarini netlestirmek icin uygun query",
        False,
    )


def append_operation_suggestion(
    response_text: str,
    *,
    user_message: str,
    product_name: str | None,
    agent_type: str,
    save_suggestion_tool_name: str = DEFAULT_SAVE_SEO_SUGGESTION_TOOL_NAME,
) -> str:
    content = (response_text or "").strip()
    if not content or operation_footer_already_present(content):
        return response_text

    operation_name, reason, requires_confirmation = select_product_operation_suggestion(
        user_message,
        content,
        product_name,
        agent_type,
        save_suggestion_tool_name=save_suggestion_tool_name,
    )

    lines = [
        content,
        "",
        "**ikas MCP Operasyon Onerisi**",
        f"- `{operation_name}`: {reason}.",
    ]
    if requires_confirmation:
        lines.append("- Not: Bu bir mutation adimidir; uygulamadan once onayini alirim.")
    elif operation_name == save_suggestion_tool_name:
        lines.append("- Not: Bu adim ikas'ta anlik guncelleme yapmaz; sadece onayli oneriyi pending olarak kaydeder.")
    lines.append("- Istersen bir sonraki adimda bunu secili urun icin netlestireyim.")
    return "\n".join(lines)


def has_mutation_tool_result(tool_results: list[dict[str, Any]]) -> bool:
    mutation_prefixes = ("update", "create", "delete", "save", "add", "remove", "fulfill", "cancel", "refund", "approve")
    for result in tool_results:
        tool_name = str(result.get("tool", "")).strip()
        if any(tool_name.startswith(prefix) for prefix in mutation_prefixes):
            result_text = str(result.get("result", ""))
            if '"error"' not in result_text:
                return True
    return False


def append_false_action_disclaimer(response_text: str, tool_results: list[dict[str, Any]]) -> str:
    if not response_text:
        return response_text
    if has_mutation_tool_result(tool_results):
        return response_text

    normalized_response = normalize_matching_text(response_text)
    has_false_claim = (
        FALSE_ACTION_CLAIM_NORMALIZED_PATTERN.search(normalized_response)
        or FALSE_ACTION_CONFIRMATION_NORMALIZED_PATTERN.search(normalized_response)
    )
    if not has_false_claim:
        return response_text
    if "henuz uygulanmadi" in normalized_response:
        return response_text
    return response_text + FALSE_ACTION_DISCLAIMER_TR
