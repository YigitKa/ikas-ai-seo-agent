from __future__ import annotations

import json

from core.skills.store import (
    SKILLS_DIR,
    SkillDefinition,
    ensure_skill_files,
    list_skill_definitions,
    save_skill_definition,
    validate_skill_definition,
)
import core.skills.store as skill_store


def test_ensure_skill_files_seeds_default_skills(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()

    ensure_skill_files()
    skills = list_skill_definitions()
    slugs = {skill.slug for skill in skills}

    assert {"category-audit", "brand-voice-rewrite", "launch-readiness"}.issubset(slugs)


def test_validate_skill_definition_rejects_unknown_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()
    ensure_skill_files()

    skill = SkillDefinition(
        slug="custom-audit",
        name="Custom Audit",
        instructions_markdown="Deneme",
        allowed_tools=["missing_tool"],
    )

    result = validate_skill_definition(skill)

    assert result.ok is False
    assert any("missing_tool" in error for error in result.errors)


def test_save_skill_definition_persists_custom_skill(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()
    ensure_skill_files()

    skill = SkillDefinition(
        slug="custom-audit",
        name="Custom Audit",
        description="Test skill",
        instructions_markdown="# Test\n\nCustom instructions",
        prompt_layers=[
            {
                "type": "inline",
                "label": "Inline",
                "content": "Inline prompt layer",
            }
        ],
        tags=["custom", "audit"],
    )

    saved = save_skill_definition(skill)

    assert saved.slug == "custom-audit"
    assert saved.name == "Custom Audit"
    assert saved.source == "project"
    meta_path = (tmp_path / "skills" / "custom-audit" / "meta.json")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert payload["slug"] == "custom-audit"
    assert payload["tags"] == ["custom", "audit"]
