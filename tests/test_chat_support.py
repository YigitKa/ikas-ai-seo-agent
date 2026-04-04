"""Tests for core/chat/support.py — extraction, normalization, and pattern-matching helpers."""

import json
import pytest

from core.chat.support import (
    _extract_chat_completion_content,
    _parse_agent_type,
    _normalize_matching_text,
    _should_request_structured_suggestion_options,
    _is_en_description_translation_request,
    _extract_chat_action,
    _extract_chat_action_payload,
    _message_has_apply_intent,
    _message_has_save_intent,
    _detect_manual_apply_action,
    _looks_like_final_suggestion_value,
    _looks_like_option_selection,
    _extract_option_index,
    _extract_options_from_assistant_message,
    _resolve_typed_option_selection,
    _build_field_priority_options,
    _build_tool_catalog_instruction,
    _build_local_no_think_instruction,
)
from core.models import AppConfig, SeoScore


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(**overrides) -> AppConfig:
    defaults = {
        "ikas_store_name": "test",
        "ikas_client_id": "cid",
        "ikas_client_secret": "csec",
        "ai_provider": "ollama",
        "ai_model_name": "llama3.2",
        "ai_base_url": "http://localhost:11434/v1",
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


def _make_score(**overrides) -> SeoScore:
    defaults = {
        "product_id": "p1",
        "total_score": 55,
        "title_score": 8,
        "description_score": 10,
        "english_description_score": 0,
        "meta_score": 7,
        "meta_desc_score": 5,
        "keyword_score": 6,
        "content_quality_score": 7,
        "technical_seo_score": 7,
        "readability_score": 3,
        "ai_citability_score": 2,
    }
    defaults.update(overrides)
    return SeoScore(**defaults)


# ── _extract_chat_completion_content ─────────────────────────────────────────

class TestExtractChatCompletionContent:
    def test_normal_string_content(self):
        data = {"choices": [{"message": {"content": "  hello world  "}}]}
        assert _extract_chat_completion_content(data) == "hello world"

    def test_list_content_blocks(self):
        data = {"choices": [{"message": {"content": [{"text": "part1"}, {"text": "part2"}]}}]}
        assert _extract_chat_completion_content(data) == "part1part2"

    def test_reasoning_content_fallback(self):
        data = {"choices": [{"message": {"content": "", "reasoning_content": "  deep thoughts  "}}]}
        assert _extract_chat_completion_content(data) == "deep thoughts"

    def test_empty_choices(self):
        assert _extract_chat_completion_content({"choices": []}) == ""

    def test_non_dict_input(self):
        assert _extract_chat_completion_content("string") == ""
        assert _extract_chat_completion_content(None) == ""

    def test_missing_content_key(self):
        data = {"choices": [{"message": {}}]}
        assert _extract_chat_completion_content(data) == ""

    def test_empty_string_content(self):
        data = {"choices": [{"message": {"content": "   "}}]}
        assert _extract_chat_completion_content(data) == ""


# ── _parse_agent_type ─────────────────────────────────────────────────────────

class TestParseAgentType:
    def test_bare_seo(self):
        assert _parse_agent_type("seo") == "seo"

    def test_bare_operator(self):
        assert _parse_agent_type("operator") == "operator"

    def test_bare_general(self):
        assert _parse_agent_type("general") == "general"

    def test_json_object(self):
        assert _parse_agent_type('{"agent_type": "seo"}') == "seo"

    def test_json_in_markdown_fence(self):
        content = "```json\n{\"agent_type\": \"operator\"}\n```"
        assert _parse_agent_type(content) == "operator"

    def test_think_block_stripped(self):
        content = "<think>Let me decide...</think>seo"
        assert _parse_agent_type(content) == "seo"

    def test_think_block_before_json(self):
        content = "<think>Analysis</think>{\"agent_type\": \"general\"}"
        assert _parse_agent_type(content) == "general"

    def test_empty_string(self):
        assert _parse_agent_type("") is None

    def test_only_think_block(self):
        assert _parse_agent_type("<think>thinking only</think>") is None

    def test_unknown_agent_type(self):
        # Falls back to keyword scan; if none found, returns None
        result = _parse_agent_type('{"agent_type": "unknown"}')
        assert result is None

    def test_keyword_fallback_in_text(self):
        # Valid JSON with unknown type, but "operator" keyword appears in the JSON text
        content = '{"agent_type": "xyz", "note": "use operator for this"}'
        assert _parse_agent_type(content) == "operator"


# ── _normalize_matching_text ──────────────────────────────────────────────────

class TestNormalizeMatchingText:
    def test_turkish_chars_normalized(self):
        assert _normalize_matching_text("Çiğdem Şahin Öğrenci") == "cigdem sahin ogrenci"

    def test_lowercase(self):
        assert _normalize_matching_text("SEO SKORU") == "seo skoru"

    def test_empty_string(self):
        assert _normalize_matching_text("") == ""

    def test_none_input(self):
        assert _normalize_matching_text(None) == ""  # type: ignore[arg-type]

    def test_latin_chars_unchanged(self):
        assert _normalize_matching_text("hello world") == "hello world"

    def test_i_with_dot_normalized(self):
        # İ (U+0130) → i
        assert _normalize_matching_text("İki") == "iki"


# ── _should_request_structured_suggestion_options ─────────────────────────────

class TestShouldRequestStructuredSuggestionOptions:
    def test_seo_rewrite_request(self):
        assert _should_request_structured_suggestion_options("meta title için öneri ver") is True

    def test_description_suggestion_request(self):
        assert _should_request_structured_suggestion_options("açıklama önerisi oluştur") is True

    def test_unrelated_message(self):
        assert _should_request_structured_suggestion_options("merhaba nasılsın") is False

    def test_only_seo_hint_no_suggestion_hint(self):
        # Has SEO hint but no suggestion/rewrite hint
        assert _should_request_structured_suggestion_options("seo skorum nedir") is False

    def test_empty_message(self):
        assert _should_request_structured_suggestion_options("") is False


# ── _is_en_description_translation_request ───────────────────────────────────

class TestIsEnDescriptionTranslationRequest:
    def test_turkish_translation_request(self):
        assert _is_en_description_translation_request("ingilizce açıklama oluştur") is True

    def test_english_translation_request(self):
        assert _is_en_description_translation_request("english description translate") is True

    def test_unrelated_message(self):
        assert _is_en_description_translation_request("fiyatı güncelle") is False

    def test_english_without_description(self):
        # Has English hint but not description context
        assert _is_en_description_translation_request("ingilizce yaz") is False

    def test_empty_message(self):
        assert _is_en_description_translation_request("") is False


# ── _extract_chat_action ──────────────────────────────────────────────────────

class TestExtractChatAction:
    def test_simple_action(self):
        assert _extract_chat_action("[[CHAT_ACTION:single_apply_all]]") == "single_apply_all"

    def test_action_with_payload(self):
        assert _extract_chat_action("[[CHAT_ACTION:single_apply_meta:{\"field\":\"meta\"}]]") == "single_apply_meta"

    def test_case_insensitive(self):
        assert _extract_chat_action("[[chat_action:single_apply_cancel]]") == "single_apply_cancel"

    def test_no_action(self):
        assert _extract_chat_action("regular message") is None

    def test_empty_string(self):
        assert _extract_chat_action("") is None

    def test_action_in_message_body(self):
        text = "User clicked [[CHAT_ACTION:single_apply_all]] to confirm"
        assert _extract_chat_action(text) == "single_apply_all"


# ── _extract_chat_action_payload ──────────────────────────────────────────────

class TestExtractChatActionPayload:
    def test_with_payload(self):
        payload = _extract_chat_action_payload('[[CHAT_ACTION:single_apply_meta:{"field":"meta_title"}]]')
        assert payload == '{"field":"meta_title"}'

    def test_without_payload(self):
        assert _extract_chat_action_payload("[[CHAT_ACTION:single_apply_all]]") is None

    def test_no_action(self):
        assert _extract_chat_action_payload("no action here") is None


# ── _message_has_apply_intent ─────────────────────────────────────────────────

class TestMessageHasApplyIntent:
    def test_apply_word(self):
        assert _message_has_apply_intent("uygula") is True

    def test_tamam_uygula(self):
        assert _message_has_apply_intent("tamam uygula") is True

    def test_unrelated(self):
        assert _message_has_apply_intent("hayır istemiyorum") is False

    def test_empty(self):
        assert _message_has_apply_intent("") is False


# ── _message_has_save_intent ──────────────────────────────────────────────────

class TestMessageHasSaveIntent:
    def test_kaydet(self):
        assert _message_has_save_intent("kaydet") is True

    def test_taslak_kaydet(self):
        assert _message_has_save_intent("taslak olarak kaydet") is True

    def test_unrelated(self):
        assert _message_has_save_intent("uygula lütfen") is False

    def test_empty(self):
        assert _message_has_save_intent("") is False


# ── _detect_manual_apply_action ───────────────────────────────────────────────

class TestDetectManualApplyAction:
    def test_cancel(self):
        assert _detect_manual_apply_action("vazgec") == "single_apply_cancel"

    def test_iptal(self):
        assert _detect_manual_apply_action("iptal") == "single_apply_cancel"

    def test_meta_only(self):
        assert _detect_manual_apply_action("sadece meta") == "single_apply_meta"

    def test_content_only(self):
        assert _detect_manual_apply_action("sadece icerik") == "single_apply_content"

    def test_all(self):
        assert _detect_manual_apply_action("hepsini") == "single_apply_all"

    def test_no_match(self):
        assert _detect_manual_apply_action("ne olacak bunlar") is None

    def test_empty(self):
        assert _detect_manual_apply_action("") is None


# ── _looks_like_final_suggestion_value ───────────────────────────────────────

class TestLooksLikeFinalSuggestionValue:
    def test_good_meta_title(self):
        assert _looks_like_final_suggestion_value("En İyi Ürün - Mağazamızda") is True

    def test_placeholder_value(self):
        assert _looks_like_final_suggestion_value("...") is False

    def test_instruction_value(self):
        # Contains "guncelle" (ASCII form matched by pattern) → not a final value
        assert _looks_like_final_suggestion_value("meta title guncelle") is False

    def test_too_short(self):
        assert _looks_like_final_suggestion_value("ab") is False

    def test_empty(self):
        assert _looks_like_final_suggestion_value("") is False


# ── _looks_like_option_selection ─────────────────────────────────────────────

class TestLooksLikeOptionSelection:
    def test_numbered_option(self):
        assert _looks_like_option_selection("1. seçeneği seç") is True

    def test_ilk_secenek(self):
        assert _looks_like_option_selection("ilk seçeneği seç") is True

    def test_unrelated(self):
        assert _looks_like_option_selection("bu ürünü güncelle") is False

    def test_empty(self):
        assert _looks_like_option_selection("") is False


# ── _extract_option_index ────────────────────────────────────────────────────

class TestExtractOptionIndex:
    def test_numbered(self):
        assert _extract_option_index("2. seçeneği seç") == 2

    def test_first_keyword(self):
        assert _extract_option_index("ilk seçeneği seç") == 1

    def test_no_match(self):
        assert _extract_option_index("meta title güncelle") is None

    def test_empty(self):
        assert _extract_option_index("") is None


# ── _extract_options_from_assistant_message ───────────────────────────────────

class TestExtractOptionsFromAssistantMessage:
    def test_json_fenced_options(self):
        content = 'Açıklama\n```json\n[{"tone":"Evet","value":"Evet uygula"}]\n```'
        opts = _extract_options_from_assistant_message(content)
        assert len(opts) == 1
        assert opts[0]["tone"] == "Evet"

    def test_trailing_array(self):
        content = 'Bir öneri:\n[{"tone":"A","value":"alpha"},{"tone":"B","value":"beta"}]'
        opts = _extract_options_from_assistant_message(content)
        assert len(opts) == 2

    def test_no_options(self):
        assert _extract_options_from_assistant_message("plain text no json") == []

    def test_invalid_json(self):
        assert _extract_options_from_assistant_message("```json\nnot valid json\n```") == []

    def test_json_without_tone_key(self):
        content = '```json\n[{"label":"A","val":"alpha"}]\n```'
        assert _extract_options_from_assistant_message(content) == []

    def test_empty(self):
        assert _extract_options_from_assistant_message("") == []


# ── _resolve_typed_option_selection ──────────────────────────────────────────

class TestResolveTypedOptionSelection:
    def _make_history(self, assistant_content: str) -> list:
        from core.models import ChatMessage
        return [ChatMessage(role="user", content="ne yapayım?"),
                ChatMessage(role="assistant", content=assistant_content)]

    def test_resolves_valid_index(self):
        history = self._make_history(
            'İşte seçenekler:\n```json\n[{"tone":"SEO","value":"SEO optimize et"},{"tone":"Meta","value":"Meta düzelt"}]\n```'
        )
        result = _resolve_typed_option_selection("2. seçeneği seç", history)
        assert result is not None
        assert "Meta" in result

    def test_first_option_keyword(self):
        history = self._make_history(
            '```json\n[{"tone":"Opt1","value":"opt1 value"}]\n```'
        )
        result = _resolve_typed_option_selection("ilk seçeneği seç", history)
        assert result is not None
        assert "Opt1" in result

    def test_out_of_range_index(self):
        history = self._make_history(
            '```json\n[{"tone":"A","value":"a val"}]\n```'
        )
        result = _resolve_typed_option_selection("5. seçeneği seç", history)
        assert result is None

    def test_no_options_in_history(self):
        from core.models import ChatMessage
        history = [ChatMessage(role="assistant", content="plain text")]
        result = _resolve_typed_option_selection("1. seçeneği seç", history)
        assert result is None

    def test_not_an_option_selection(self):
        from core.models import ChatMessage
        history = [ChatMessage(role="assistant", content='```json\n[{"tone":"X","value":"x"}]\n```')]
        result = _resolve_typed_option_selection("meta title güncelle", history)
        assert result is None


# ── _build_field_priority_options ─────────────────────────────────────────────

class TestBuildFieldPriorityOptions:
    def test_worst_field_first(self):
        score = _make_score(english_description_score=0, title_score=15)
        result = _build_field_priority_options(score)
        options = json.loads(result)
        # EN description (0/5 = 0%) should appear before Title (15/15 = 100%)
        tones = [o["tone"] for o in options]
        assert any("EN" in t for t in tones)
        # Perfect title shouldn't appear
        assert not any("Ürün Adı (15/15)" in t for t in tones)

    def test_all_perfect_scores(self):
        score = _make_score(
            english_description_score=5,
            title_score=15,
            description_score=20,
            meta_score=15,
            meta_desc_score=10,
            keyword_score=10,
            content_quality_score=10,
            technical_seo_score=10,
            readability_score=5,
            ai_citability_score=10,
        )
        result = _build_field_priority_options(score)
        options = json.loads(result)
        assert len(options) == 1
        assert options[0]["tone"] == "Tüm alanlar iyi"

    def test_returns_valid_json(self):
        score = _make_score()
        result = _build_field_priority_options(score)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert all("tone" in o and "value" in o for o in parsed)


# ── _build_tool_catalog_instruction ──────────────────────────────────────────

class TestBuildToolCatalogInstruction:
    def test_empty_list_returns_none(self):
        assert _build_tool_catalog_instruction([]) is None

    def test_returns_instruction_with_tool_names(self):
        tools = [{"name": "listProduct"}, {"name": "getOrder"}]
        result = _build_tool_catalog_instruction(tools)
        assert result is not None
        assert "listProduct" in result
        assert "getOrder" in result

    def test_mutation_warning_included(self):
        tools = [{"name": "updateProduct"}, {"name": "listOrders"}]
        result = _build_tool_catalog_instruction(tools)
        assert result is not None
        assert "mutation" in result.lower() or "degisiklik" in result.lower()

    def test_no_mutation_warning_for_query_only(self):
        tools = [{"name": "listProduct"}, {"name": "getCategory"}]
        result = _build_tool_catalog_instruction(tools)
        assert result is not None
        # No mutation names → no mutation warning expected
        assert "mutation" not in result.lower()


# ── _build_local_no_think_instruction ────────────────────────────────────────

class TestBuildLocalNoThinkInstruction:
    def test_ollama_returns_instruction_when_thinking_off(self):
        config = _make_config(ai_provider="ollama", ai_thinking_mode_chat=False)
        result = _build_local_no_think_instruction(config)
        assert result is not None
        assert "think" in result.lower() or "/no_think" in result

    def test_anthropic_returns_none(self):
        config = _make_config(ai_provider="anthropic", ai_thinking_mode_chat=False)
        result = _build_local_no_think_instruction(config)
        assert result is None

    def test_thinking_mode_on_returns_none(self):
        config = _make_config(ai_provider="ollama", ai_thinking_mode_chat=True)
        result = _build_local_no_think_instruction(config)
        assert result is None

    def test_lm_studio_returns_instruction(self):
        config = _make_config(ai_provider="lm-studio", ai_thinking_mode_chat=False)
        result = _build_local_no_think_instruction(config)
        assert result is not None
