from __future__ import annotations

import json

from core.skills.store import (
    SKILLS_DIR,
    SkillDefinition,
    ensure_skill_files,
    get_skill_definition,
    list_skill_definitions,
    preview_skill_definition,
    resolve_skill_tool_scope,
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
    assert saved.source == "custom"
    meta_path = (tmp_path / "skills" / "custom" / "custom-audit" / "meta.json")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert payload["slug"] == "custom-audit"
    assert payload["tags"] == ["custom", "audit"]


def test_get_skill_definition_prefers_custom_source_over_system(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()
    ensure_skill_files()

    custom_dir = tmp_path / "skills" / "custom" / "launch-readiness"
    custom_dir.mkdir(parents=True, exist_ok=True)
    (custom_dir / "meta.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "launch-readiness",
                "name": "Launch Readiness Override",
                "description": "Custom override",
                "when_to_use": "custom",
                "applies_to": ["chat"],
                "allowed_tools": [],
                "prompt_layers": [],
                "tags": ["default"],
                "priority": 5,
                "status": "active",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (custom_dir / "SKILL.md").write_text("# Custom override", encoding="utf-8")

    skill = get_skill_definition("launch-readiness")

    assert skill.source == "custom"
    assert skill.name == "Launch Readiness Override"


def test_resolve_skill_tool_scope_intersects_flow_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()
    ensure_skill_files()

    skill = skill_store.get_skill_definition("launch-readiness")

    resolved = resolve_skill_tool_scope(skill, applies_to="chat")

    assert resolved is not None
    assert "apply_seo_to_ikas" in resolved
    assert "save_suggestion" not in resolved


def test_preview_skill_definition_returns_runtime_debug(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()
    ensure_skill_files()

    skill = skill_store.get_skill_definition("brand-voice-rewrite")

    preview = preview_skill_definition(skill, applies_to="batch")

    assert preview["debug"]["applies_to"] == "batch"
    assert preview["debug"]["tool_scope_mode"] == "prompt_only"
    assert "Batch akisi" in preview["debug"]["tool_scope_note"]
    assert preview["debug"]["requested_tools"]
