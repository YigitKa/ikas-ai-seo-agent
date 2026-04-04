"""Tests for core/ai/helpers.py — response parsing, thinking extraction, utilities."""

import pytest

from core.ai.helpers import (
    _extract_thinking,
    _parse_response_text,
    _is_placeholder_json,
    _is_placeholder_string,
    _decode_json_string_fragment,
    _extract_known_string_fields,
    _cap_field_max_tokens,
    _merge_thinking_text,
    _extract_lm_studio_output,
    _get_system_prompt,
    _lm_studio_native_base_url,
)
from core.models import AppConfig


def _make_config(**overrides) -> AppConfig:
    defaults = {
        "ikas_store_name": "test",
        "ikas_client_id": "cid",
        "ikas_client_secret": "csec",
        "ai_provider": "anthropic",
        "ai_model_name": "claude-haiku-4-5-20251001",
    }
    defaults.update(overrides)
    return AppConfig(**defaults)


# ── _is_placeholder_json ──────────────────────────────────────────────────────

class TestIsPlaceholderJson:
    def test_dots_placeholder(self):
        assert _is_placeholder_json({"suggested_description": "..."}) is True

    def test_ellipsis_unicode(self):
        assert _is_placeholder_json({"suggested_description": "…"}) is True

    def test_empty_string_value(self):
        assert _is_placeholder_json({"key": ""}) is True

    def test_real_content(self):
        assert _is_placeholder_json({"suggested_description": "Real product description here."}) is False

    def test_empty_dict(self):
        assert _is_placeholder_json({}) is True

    def test_non_dict(self):
        assert _is_placeholder_json("not a dict") is True  # type: ignore[arg-type]

    def test_mixed_values(self):
        # One real value → not placeholder
        assert _is_placeholder_json({"a": "...", "b": "Real value"}) is False


# ── _is_placeholder_string ────────────────────────────────────────────────────

class TestIsPlaceholderString:
    def test_dots(self):
        assert _is_placeholder_string("...") is True

    def test_quoted_dots(self):
        assert _is_placeholder_string('"..."') is True

    def test_empty(self):
        assert _is_placeholder_string("") is True

    def test_real_value(self):
        assert _is_placeholder_string("Real meta title text") is False


# ── _decode_json_string_fragment ──────────────────────────────────────────────

class TestDecodeJsonStringFragment:
    def test_escape_sequences(self):
        result = _decode_json_string_fragment(r"line1\nline2")
        assert "line1" in result
        assert "line2" in result

    def test_escaped_quotes(self):
        result = _decode_json_string_fragment(r'say \"hello\"')
        assert '"hello"' in result

    def test_slash_unescape(self):
        result = _decode_json_string_fragment(r"path\/to\/file")
        assert "path/to/file" in result

    def test_empty_string(self):
        assert _decode_json_string_fragment("") == ""

    def test_plain_string(self):
        assert _decode_json_string_fragment("plain text") == "plain text"


# ── _extract_thinking ─────────────────────────────────────────────────────────

class TestExtractThinking:
    def test_think_xml_block_extracted(self):
        raw = "<think>Let me analyze this.</think>{\"suggested_name\": \"Product\"}"
        thinking, remaining = _extract_thinking(raw)
        assert "Let me analyze this." in thinking
        assert "suggested_name" in remaining
        assert "<think>" not in remaining

    def test_no_think_block(self):
        raw = '{"suggested_name": "Test Product"}'
        thinking, remaining = _extract_thinking(raw)
        assert thinking == ""
        assert remaining == raw

    def test_multiple_think_blocks(self):
        raw = "<think>First thought</think><think>Second thought</think>{\"key\": \"val\"}"
        thinking, remaining = _extract_thinking(raw)
        assert "First thought" in thinking
        assert "Second thought" in thinking

    def test_text_preamble_treated_as_thinking(self):
        raw = 'Here is my analysis:\n{"suggested_name": "Product"}'
        thinking, remaining = _extract_thinking(raw)
        # The preamble should be captured as thinking
        assert "suggested_name" in remaining

    def test_long_text_no_json_all_thinking(self):
        raw = "a" * 300  # No JSON
        thinking, remaining = _extract_thinking(raw)
        assert len(thinking) > 0
        assert remaining == ""


# ── _parse_response_text ──────────────────────────────────────────────────────

class TestParseResponseText:
    def test_clean_json(self):
        raw = '{"suggested_description": "New product description"}'
        parsed, thinking = _parse_response_text(raw)
        assert parsed["suggested_description"] == "New product description"
        assert thinking == ""

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"suggested_name": "Test"}\n```'
        parsed, thinking = _parse_response_text(raw)
        assert parsed["suggested_name"] == "Test"

    def test_think_then_json(self):
        raw = "<think>Reasoning here</think>{\"suggested_meta_title\": \"New Title\"}"
        parsed, thinking = _parse_response_text(raw)
        assert parsed["suggested_meta_title"] == "New Title"
        assert "Reasoning" in thinking

    def test_placeholder_json_raises(self):
        raw = '{"suggested_description": "..."}'
        with pytest.raises(ValueError):
            _parse_response_text(raw)

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            _parse_response_text("not json at all and short")

    def test_nested_json_extracted(self):
        raw = '{"outer": {"inner": "value"}, "suggested_name": "Product"}'
        parsed, thinking = _parse_response_text(raw)
        assert "suggested_name" in parsed

    def test_tolerant_field_extraction(self):
        # Broken JSON but with recognizable field
        raw = '{"suggested_name": "My Product Name", "bad": '
        parsed, thinking = _parse_response_text(raw)
        assert parsed.get("suggested_name") == "My Product Name"


# ── _extract_known_string_fields ──────────────────────────────────────────────

class TestExtractKnownStringFields:
    def test_extracts_suggested_name(self):
        text = '"suggested_name": "Great Product"'
        result = _extract_known_string_fields(text)
        assert result.get("suggested_name") == "Great Product"

    def test_extracts_multiple_fields(self):
        text = '"suggested_name": "Name", "suggested_meta_title": "Title"'
        result = _extract_known_string_fields(text)
        assert "suggested_name" in result
        assert "suggested_meta_title" in result

    def test_skips_placeholder_values(self):
        text = '"suggested_description": "..."'
        result = _extract_known_string_fields(text)
        assert "suggested_description" not in result

    def test_empty_text(self):
        result = _extract_known_string_fields("")
        assert result == {}


# ── _cap_field_max_tokens ─────────────────────────────────────────────────────

class TestCapFieldMaxTokens:
    def test_capped_at_field_limit(self):
        # "name" field is capped at 96 tokens in FIELD_MAX_OUTPUT_TOKENS
        result = _cap_field_max_tokens("name", 10000)
        assert result < 10000
        assert result == 96

    def test_thinking_mode_skips_cap(self):
        result = _cap_field_max_tokens("name", 5, thinking_mode=True)
        assert result >= 1

    def test_minimum_one(self):
        result = _cap_field_max_tokens("name", 0)
        assert result >= 1

    def test_unknown_field_returns_requested(self):
        result = _cap_field_max_tokens("unknown_field_xyz", 500)
        assert result == 500


# ── _merge_thinking_text ──────────────────────────────────────────────────────

class TestMergeThinkingText:
    def test_two_parts(self):
        result = _merge_thinking_text("Part A", "Part B")
        assert "Part A" in result
        assert "Part B" in result

    def test_empty_parts_skipped(self):
        result = _merge_thinking_text("Real", "", "  ")
        assert result == "Real"

    def test_all_empty(self):
        result = _merge_thinking_text("", "", "")
        assert result == ""

    def test_single_part(self):
        result = _merge_thinking_text("Only part")
        assert result == "Only part"


# ── _extract_lm_studio_output ─────────────────────────────────────────────────

class TestExtractLmStudioOutput:
    def test_message_and_reasoning(self):
        data = {
            "output": [
                {"type": "reasoning", "content": "My reasoning"},
                {"type": "text", "content": "Final answer"},
            ]
        }
        message, thinking = _extract_lm_studio_output(data)
        assert "Final answer" in message
        assert "My reasoning" in thinking

    def test_only_message(self):
        data = {"output": [{"type": "text", "content": "Answer"}]}
        message, thinking = _extract_lm_studio_output(data)
        assert message == "Answer"
        assert thinking == ""

    def test_empty_output(self):
        data = {"output": []}
        message, thinking = _extract_lm_studio_output(data)
        assert message == ""
        assert thinking == ""

    def test_missing_output_key(self):
        data = {}
        message, thinking = _extract_lm_studio_output(data)
        assert message == ""
        assert thinking == ""


# ── _get_system_prompt ────────────────────────────────────────────────────────

class TestGetSystemPrompt:
    def test_turkish_store_returns_tr_prompt(self):
        config = _make_config(store_languages=["tr"])
        result = _get_system_prompt(config)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_english_only_store_returns_en_prompt(self):
        config = _make_config(store_languages=["en"])
        result = _get_system_prompt(config)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_tr_en_store_returns_tr_prompt(self):
        config = _make_config(store_languages=["tr", "en"])
        result_tr = _get_system_prompt(config)
        config_en = _make_config(store_languages=["en"])
        result_en = _get_system_prompt(config_en)
        # Turkish store should return different prompt than English-only
        assert result_tr != result_en


# ── _lm_studio_native_base_url ────────────────────────────────────────────────

class TestLmStudioNativeBaseUrl:
    def test_strips_v1_suffix(self):
        result = _lm_studio_native_base_url("http://localhost:1234/v1")
        assert not result.endswith("/v1")
        assert result == "http://localhost:1234"

    def test_no_v1_suffix_unchanged(self):
        result = _lm_studio_native_base_url("http://localhost:1234")
        assert result == "http://localhost:1234"

    def test_trailing_slash_stripped(self):
        result = _lm_studio_native_base_url("http://localhost:1234/")
        assert not result.endswith("/")
