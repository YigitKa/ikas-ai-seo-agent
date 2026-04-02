from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from core.agent.tools import (
    AgentToolkit,
    ToolDefinition,
    build_apply_seo_to_ikas_tool,
    build_save_seo_suggestion_tool,
    create_batch_toolkit,
    create_chat_toolkit,
    create_seo_rewrite_toolkit,
)
from core.permissions import PermissionEngine, PermissionRequest, PermissionRule
from core.prompt_store import compose_prompt_with_skill_layer
from core.skills.store import (
    SkillDefinition,
    build_skill_prompt,
    get_skill_definition,
    list_skill_definitions,
    resolve_skill_tool_scope,
    validate_skill_definition,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CHAT_AGENT_SCOPE_PREFIX = "chat"


@dataclass
class SkillRuntimeSelection:
    applies_to: str
    selection_mode: str = "none"
    skills: list[SkillDefinition] = field(default_factory=list)
    explicit_skill_slug: str | None = None
    routed_skill_slug: str | None = None
    default_skill_slug: str | None = None
    merged_skill_slugs: list[str] = field(default_factory=list)
    prompt: str = ""
    allowed_tool_names: set[str] | None = None
    requested_tool_names: list[str] = field(default_factory=list)
    denied_tool_names: list[str] = field(default_factory=list)
    prompt_layer_sources: list[str] = field(default_factory=list)

    @property
    def primary_skill(self) -> SkillDefinition | None:
        if not self.skills:
            return None
        return self.skills[-1]

    def to_payload(self) -> dict[str, Any] | None:
        primary = self.primary_skill
        if primary is None:
            return None
        return {
            "slug": primary.slug,
            "name": primary.name,
            "description": primary.description,
            "applies_to": list(primary.applies_to),
            "allowed_tools": list(primary.allowed_tools),
            "resolved_tools": sorted(self.allowed_tool_names or []),
            "status": primary.status,
            "source": primary.source,
            "selection_mode": self.selection_mode,
            "merged_skill_slugs": list(self.merged_skill_slugs),
            "explicit_skill_slug": self.explicit_skill_slug,
            "prompt_layer_sources": list(self.prompt_layer_sources),
        }


def parse_skill_slug_list(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = value.split(",")
    else:
        raw_values = []
        for item in value:
            raw_values.extend(str(item).split(","))

    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        slug = str(raw or "").strip().lower()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        result.append(slug)
    return result


def _tokenize(text: str) -> set[str]:
    normalized = (text or "").lower()
    return {token for token in _TOKEN_RE.findall(normalized) if len(token) > 2}


def _build_skill_matching_text(skill: SkillDefinition) -> str:
    preview = skill.instructions_markdown[:800]
    return "\n".join([
        skill.slug,
        skill.name,
        skill.description,
        skill.when_to_use,
        " ".join(skill.tags),
        preview,
    ])


def _score_skill_match(skill: SkillDefinition, routing_text: str) -> int:
    routing_tokens = _tokenize(routing_text)
    if not routing_tokens:
        return 0

    skill_text = _build_skill_matching_text(skill)
    skill_tokens = _tokenize(skill_text)
    overlap = routing_tokens.intersection(skill_tokens)
    if not overlap:
        return 0

    score = len(overlap)
    lowered_text = routing_text.lower()
    slug_parts = [part for part in skill.slug.split("-") if part]
    if any(part in lowered_text for part in slug_parts):
        score += 3
    if any(tag.lower() in lowered_text for tag in skill.tags):
        score += 2
    if skill.name.lower() in lowered_text:
        score += 3
    return score


def _pick_routed_skill(
    skills: list[SkillDefinition],
    *,
    routing_text: str,
) -> SkillDefinition | None:
    ranked: list[tuple[int, int, str, SkillDefinition]] = []
    for skill in skills:
        score = _score_skill_match(skill, routing_text)
        if score <= 0:
            continue
        ranked.append((score, -skill.priority, skill.slug, skill))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][3]


def _pick_default_skill(skills: list[SkillDefinition]) -> SkillDefinition | None:
    tagged_defaults = [skill for skill in skills if any(tag.lower() == "default" for tag in skill.tags)]
    pool = tagged_defaults or [skill for skill in skills if skill.is_default]
    if not pool:
        return None
    return sorted(pool, key=lambda skill: (skill.priority, skill.name.lower(), skill.slug))[0]


def _iter_toolkit_definitions(toolkit: AgentToolkit) -> list[ToolDefinition]:
    definitions: list[ToolDefinition] = []
    for name in toolkit.tool_names:
        tool = toolkit.get(name)
        if tool is not None:
            definitions.append(tool)
    return definitions


def _flow_tool_definitions(applies_to: str, *, agent_scope: str | None = None) -> dict[str, ToolDefinition]:
    target = (applies_to or "").strip().lower()
    definitions: list[ToolDefinition] = []
    if target == "chat":
        definitions.extend(_iter_toolkit_definitions(create_chat_toolkit()))
        definitions.append(build_save_seo_suggestion_tool())
        definitions.append(build_apply_seo_to_ikas_tool())
    elif target == "rewrite":
        definitions.extend(_iter_toolkit_definitions(create_seo_rewrite_toolkit()))
    elif target == "batch":
        definitions.extend(_iter_toolkit_definitions(create_batch_toolkit()))

    result: dict[str, ToolDefinition] = {}
    for definition in definitions:
        if agent_scope and not definition.is_available_to(agent_scope):
            continue
        result[definition.name] = definition
    return result


def _compose_skill_prompts(skills: list[SkillDefinition], *, applies_to: str) -> tuple[str, list[str]]:
    sections: list[str] = []
    layer_sources: list[str] = []
    for skill in skills:
        prompt = build_skill_prompt(skill, applies_to=applies_to)
        if prompt:
            sections.append(prompt)
        validation = validate_skill_definition(skill)
        layer_sources.extend(layer.source for layer in validation.resolved_prompt_layers)
    return "\n\n".join(section for section in sections if section.strip()).strip(), layer_sources


def _merge_requested_tool_scope(skills: list[SkillDefinition], *, applies_to: str) -> tuple[set[str] | None, list[str]]:
    restrictive_scopes: list[set[str]] = []
    requested_names: list[str] = []
    for skill in skills:
        requested_names.extend(skill.allowed_tools)
        scope = resolve_skill_tool_scope(skill, applies_to=applies_to)
        if scope is not None:
            restrictive_scopes.append(set(scope))

    if not restrictive_scopes:
        return None, requested_names

    merged_scope = set(restrictive_scopes[0])
    for scope in restrictive_scopes[1:]:
        merged_scope &= scope
    return merged_scope, requested_names


def _filter_tools_by_permissions(
    tool_definitions: dict[str, ToolDefinition],
    *,
    tool_names: set[str] | None,
    permission_engine: PermissionEngine | None,
    permission_target: str,
    permission_source: str,
    permission_runtime_rules: Iterable[PermissionRule] | None = None,
    agent_scope: str | None = None,
) -> tuple[set[str] | None, list[str]]:
    if tool_names is None:
        candidate_names = set(tool_definitions.keys())
        unrestricted = True
        baseline_names = set(candidate_names)
    else:
        candidate_names = set(tool_names).intersection(tool_definitions.keys())
        unrestricted = False
        baseline_names = set(candidate_names)

    if permission_engine is None:
        return (None if unrestricted else candidate_names), []

    denied_names: list[str] = []
    for name in sorted(candidate_names):
        definition = tool_definitions.get(name)
        if definition is None:
            continue
        operation = str(definition.ui_meta.get("permission_operation") or "").strip()
        if not operation:
            continue
        decision = permission_engine.preview(
            PermissionRequest(
                operation=operation,  # type: ignore[arg-type]
                target=permission_target,
                tool_name=name,
                source=permission_source,
                agent_type=agent_scope,
            ),
            runtime_rules=list(permission_runtime_rules or ()),
        )
        if decision.behavior == "deny":
            candidate_names.discard(name)
            denied_names.append(name)

    if unrestricted and candidate_names == baseline_names:
        return None, denied_names
    return candidate_names, denied_names


def resolve_runtime_skill_selection(
    *,
    applies_to: str,
    explicit_skill_slugs: str | Iterable[str] | None = None,
    routing_text: str = "",
    enable_routing: bool = False,
    enable_default_fallback: bool = False,
    agent_scope: str | None = None,
    permission_engine: PermissionEngine | None = None,
    permission_target: str = "",
    permission_source: str = "skill_runtime.resolve",
    permission_runtime_rules: Iterable[PermissionRule] | None = None,
) -> SkillRuntimeSelection:
    target = (applies_to or "").strip().lower()
    available_skills = [
        skill
        for skill in list_skill_definitions()
        if skill.status == "active" and target in skill.applies_to
    ]
    explicit_slugs = parse_skill_slug_list(explicit_skill_slugs)
    explicit_skills: list[SkillDefinition] = []
    seen_slugs: set[str] = set()
    for slug in explicit_slugs:
        skill = get_skill_definition(slug)
        if skill.status != "active":
            raise ValueError(f"Skill aktif degil: {skill.slug}")
        if target not in skill.applies_to:
            raise ValueError(f"Skill {target} akisi icin uygun degil: {skill.slug}")
        if skill.slug in seen_slugs:
            continue
        explicit_skills.append(skill)
        seen_slugs.add(skill.slug)

    routed_skill: SkillDefinition | None = None
    if enable_routing and routing_text.strip():
        routed_skill = _pick_routed_skill(
            [skill for skill in available_skills if skill.slug not in seen_slugs],
            routing_text=routing_text,
        )
        if routed_skill is not None:
            seen_slugs.add(routed_skill.slug)

    default_skill: SkillDefinition | None = None
    if enable_default_fallback:
        default_skill = _pick_default_skill([skill for skill in available_skills if skill.slug not in seen_slugs])
        if default_skill is not None:
            seen_slugs.add(default_skill.slug)

    selected_skills: list[SkillDefinition] = []
    if default_skill is not None:
        selected_skills.append(default_skill)
    if routed_skill is not None:
        selected_skills.append(routed_skill)
    selected_skills.extend(explicit_skills)

    if not selected_skills:
        return SkillRuntimeSelection(applies_to=target)

    merged_prompt, prompt_layer_sources = _compose_skill_prompts(selected_skills, applies_to=target)
    requested_tool_scope, requested_tool_names = _merge_requested_tool_scope(selected_skills, applies_to=target)
    tool_definitions = _flow_tool_definitions(target, agent_scope=agent_scope)
    allowed_tool_names, denied_tool_names = _filter_tools_by_permissions(
        tool_definitions,
        tool_names=requested_tool_scope,
        permission_engine=permission_engine,
        permission_target=permission_target,
        permission_source=permission_source,
        permission_runtime_rules=permission_runtime_rules,
        agent_scope=agent_scope,
    )

    if len(selected_skills) > 1:
        selection_mode = "merged"
    elif explicit_skills:
        selection_mode = "explicit"
    elif routed_skill is not None:
        selection_mode = "routed"
    else:
        selection_mode = "default"

    return SkillRuntimeSelection(
        applies_to=target,
        selection_mode=selection_mode,
        skills=selected_skills,
        explicit_skill_slug=explicit_skills[-1].slug if explicit_skills else None,
        routed_skill_slug=routed_skill.slug if routed_skill is not None else None,
        default_skill_slug=default_skill.slug if default_skill is not None else None,
        merged_skill_slugs=[skill.slug for skill in selected_skills],
        prompt=compose_prompt_with_skill_layer("", merged_prompt, "chat") if not merged_prompt else merged_prompt,
        allowed_tool_names=allowed_tool_names,
        requested_tool_names=requested_tool_names,
        denied_tool_names=denied_tool_names,
        prompt_layer_sources=prompt_layer_sources,
    )


def resolve_chat_agent_scope(agent_type: str | None) -> str:
    normalized = (agent_type or "").strip().lower()
    if not normalized:
        return _CHAT_AGENT_SCOPE_PREFIX
    return f"{_CHAT_AGENT_SCOPE_PREFIX}:{normalized}"
