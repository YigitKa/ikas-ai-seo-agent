from __future__ import annotations

import core.skills.store as skill_store
from core.permissions import PermissionEngine, PermissionRule
from core.skills.runtime import resolve_chat_agent_scope, resolve_runtime_skill_selection


def _use_temp_skills(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()
    skill_store.ensure_skill_files()


def test_resolve_runtime_skill_selection_merges_default_and_explicit(monkeypatch, tmp_path):
    _use_temp_skills(monkeypatch, tmp_path)

    selection = resolve_runtime_skill_selection(
        applies_to="chat",
        explicit_skill_slugs="category-audit",
        routing_text="kategori uyumu ve publish kontrolu",
        enable_routing=False,
        enable_default_fallback=True,
        agent_scope=resolve_chat_agent_scope("seo"),
    )

    assert selection.selection_mode == "merged"
    assert selection.merged_skill_slugs == ["launch-readiness", "category-audit"]
    assert selection.primary_skill is not None
    assert selection.primary_skill.slug == "category-audit"
    assert selection.allowed_tool_names is not None
    assert "save_seo_suggestion" in selection.allowed_tool_names
    assert "apply_seo_to_ikas" not in selection.allowed_tool_names


def test_resolve_runtime_skill_selection_routes_brand_voice(monkeypatch, tmp_path):
    _use_temp_skills(monkeypatch, tmp_path)

    selection = resolve_runtime_skill_selection(
        applies_to="rewrite",
        routing_text="marka tonu daha kontrollu olsun, rewrite yap",
        enable_routing=True,
        enable_default_fallback=False,
        agent_scope="seo_rewrite",
    )

    assert selection.selection_mode == "routed"
    assert selection.primary_skill is not None
    assert selection.primary_skill.slug == "brand-voice-rewrite"


def test_resolve_runtime_skill_selection_intersects_permission_denies(monkeypatch, tmp_path):
    _use_temp_skills(monkeypatch, tmp_path)
    engine = PermissionEngine(
        global_rules=[
            PermissionRule(scope="global", behavior="allow", operation="rollback"),
            PermissionRule(scope="global", behavior="deny", operation="apply"),
        ],
        project_rules=[],
        session_rules=[],
    )

    selection = resolve_runtime_skill_selection(
        applies_to="chat",
        explicit_skill_slugs="launch-readiness",
        enable_routing=False,
        enable_default_fallback=False,
        agent_scope=resolve_chat_agent_scope("seo"),
        permission_engine=engine,
        permission_target="prod-1",
    )

    assert selection.allowed_tool_names is not None
    assert "apply_seo_to_ikas" not in selection.allowed_tool_names
    assert "apply_seo_to_ikas" in selection.denied_tool_names
