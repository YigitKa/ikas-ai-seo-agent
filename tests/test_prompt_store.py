"""Tests for core/prompt_store.py — template loading, rendering, and caching."""

import pytest
from pathlib import Path
from unittest.mock import patch


import core.prompt_store as ps


# ── load_prompt_template ──────────────────────────────────────────────────────

def test_load_prompt_template_returns_string(tmp_path, monkeypatch):
    """Loading a known key returns a non-empty string."""
    # Patch the prompts dir to our temp dir and write a file
    fake_prompts = tmp_path / "prompts"
    fake_prompts.mkdir()
    (fake_prompts / "description_rewrite.system.txt").write_text("System prompt content")

    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    # Clear cache so our monkeypatched dir is used
    ps._prompt_cache.clear()

    result = ps.load_prompt_template("description_system")
    assert isinstance(result, str)
    assert len(result) > 0


def test_load_prompt_template_falls_back_to_default(tmp_path, monkeypatch):
    """When file doesn't exist, falls back to PROMPT_DEFAULTS."""
    fake_prompts = tmp_path / "prompts_missing"
    fake_prompts.mkdir()

    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    # description_system has a default
    result = ps.load_prompt_template("description_system")
    assert isinstance(result, str)
    assert len(result) > 0


def test_load_prompt_template_cached(tmp_path, monkeypatch):
    """Second call returns cached value without re-reading file."""
    fake_prompts = tmp_path / "prompts_cache"
    fake_prompts.mkdir()
    f = fake_prompts / "description_rewrite.system.txt"
    f.write_text("First content")

    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    first = ps.load_prompt_template("description_system")
    # Modify file — should not affect cached result
    f.write_text("Modified content")
    second = ps.load_prompt_template("description_system")

    assert first == second


def test_load_prompt_template_unknown_key_raises(tmp_path, monkeypatch):
    """Unknown key raises KeyError."""
    fake_prompts = tmp_path / "prompts_unk"
    fake_prompts.mkdir()
    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    with pytest.raises(KeyError):
        ps.load_prompt_template("totally_unknown_key_xyz")


# ── save_prompt_template / reset_prompt_template ─────────────────────────────

def test_save_prompt_template_writes_file(tmp_path, monkeypatch):
    fake_prompts = tmp_path / "prompts_save"
    fake_prompts.mkdir()
    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    ps.save_prompt_template("description_system", "Custom system prompt")

    saved_file = fake_prompts / "description_rewrite.system.txt"
    assert saved_file.exists()
    assert saved_file.read_text() == "Custom system prompt"


def test_save_prompt_template_updates_cache(tmp_path, monkeypatch):
    fake_prompts = tmp_path / "prompts_inv"
    fake_prompts.mkdir()
    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    # Prime the cache
    _ = ps.load_prompt_template("description_system")
    assert "description_system" in ps._prompt_cache

    # Save updates the cache with the new content
    ps.save_prompt_template("description_system", "New content")
    assert ps._prompt_cache.get("description_system") == "New content"


def test_reset_prompt_template_restores_default(tmp_path, monkeypatch):
    fake_prompts = tmp_path / "prompts_reset"
    fake_prompts.mkdir()
    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    # Save a custom version
    ps.save_prompt_template("description_system", "Custom content")
    # Reset it
    ps.reset_prompt_template("description_system")

    # Should now load from PROMPT_DEFAULTS (no file)
    ps._prompt_cache.clear()
    result = ps.load_prompt_template("description_system")
    assert "Custom content" not in result
    # The default should be loaded
    assert len(result) > 0


# ── PROMPT_FILES coverage ─────────────────────────────────────────────────────

def test_load_all_prompt_files_return_strings(tmp_path, monkeypatch):
    """All PROMPT_FILES keys can be loaded and return strings."""
    fake_prompts = tmp_path / "prompts_all"
    fake_prompts.mkdir()
    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    for key in ps.PROMPT_FILES:
        result = ps.load_prompt_template(key)
        assert isinstance(result, str), f"Key {key!r} returned non-string"

def test_prompt_files_keys_have_defaults(tmp_path, monkeypatch):
    """All PROMPT_FILES keys have corresponding PROMPT_DEFAULTS entries."""
    for key in ps.PROMPT_FILES:
        assert key in ps.PROMPT_DEFAULTS, f"Key {key!r} missing from PROMPT_DEFAULTS"


# ── get_agent_system_prompts_tr ───────────────────────────────────────────────

def test_get_agent_system_prompts_tr_has_required_keys(tmp_path, monkeypatch):
    fake_prompts = tmp_path / "prompts_agent"
    fake_prompts.mkdir()
    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    prompts = ps.get_agent_system_prompts_tr()
    assert isinstance(prompts, dict)
    assert "seo" in prompts
    assert "operator" in prompts
    assert "general" in prompts


def test_get_agent_system_prompts_tr_contain_placeholders_formatted(tmp_path, monkeypatch):
    """After format(), no unformatted {placeholder} should remain (except nested braces)."""
    fake_prompts = tmp_path / "prompts_fmt"
    fake_prompts.mkdir()
    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    ps._prompt_cache.clear()

    prompts = ps.get_agent_system_prompts_tr()
    # These templates have {product_context} and {score_context} — format with empty strings
    for key, template in prompts.items():
        try:
            formatted = template.format(product_context="", score_context="")
            assert isinstance(formatted, str)
        except KeyError as e:
            pytest.fail(f"Template {key!r} has unexpected placeholder: {e}")


# ── ensure_prompt_files ───────────────────────────────────────────────────────

def test_ensure_prompt_files_creates_missing_files(tmp_path, monkeypatch):
    fake_prompts = tmp_path / "prompts_ensure"
    fake_prompts.mkdir()
    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    # Reset initialized guard
    monkeypatch.setattr(ps, "_prompts_initialized", False)
    ps._prompt_cache.clear()

    ps.ensure_prompt_files()

    # Some standard files should now exist
    assert (fake_prompts / "description_rewrite.system.txt").exists()
    assert (fake_prompts / "description_rewrite.user.txt").exists()


def test_ensure_prompt_files_does_not_overwrite_existing(tmp_path, monkeypatch):
    fake_prompts = tmp_path / "prompts_no_overwrite"
    fake_prompts.mkdir()
    existing = fake_prompts / "description_rewrite.system.txt"
    existing.write_text("My custom content")

    monkeypatch.setattr(ps, "PROMPTS_DIR", fake_prompts)
    monkeypatch.setattr(ps, "_prompts_initialized", False)
    ps._prompt_cache.clear()

    ps.ensure_prompt_files()

    assert existing.read_text() == "My custom content"


# ── PROMPT_EDITOR_GROUPS ──────────────────────────────────────────────────────

def test_prompt_editor_groups_structure():
    for group_name, keys in ps.PROMPT_EDITOR_GROUPS:
        assert isinstance(group_name, str)
        assert isinstance(keys, tuple)
        for key in keys:
            assert key in ps.PROMPT_FILES, f"Key {key!r} in group {group_name!r} not in PROMPT_FILES"
