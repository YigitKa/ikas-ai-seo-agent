from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from core.agent.tools import (
    APPLY_SEO_TO_IKAS_TOOL_NAME,
    SAVE_SEO_SUGGESTION_TOOL_NAME,
    create_batch_toolkit,
    create_chat_toolkit,
    create_seo_rewrite_toolkit,
)
from core.prompt_store import get_prompt_editor_groups, get_prompt_editor_meta, load_prompt_template

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"
_README_NAME = "README.txt"
_META_FILE = "meta.json"
_MARKDOWN_FILE = "SKILL.md"
_VALID_APPLIES_TO = frozenset({"chat", "rewrite", "batch"})
_VALID_STATUSES = frozenset({"active", "draft", "disabled"})
_SKILL_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_FRONTMATTER_LINE_RE = re.compile(r"^(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(?P<value>.*)$")


class SkillPromptLayer(BaseModel):
    type: Literal["inline", "prompt_reference"] = "inline"
    label: str = ""
    prompt_key: str = ""
    content: str = ""

    @model_validator(mode="after")
    def _validate_layer(self) -> "SkillPromptLayer":
        self.label = self.label.strip()
        self.prompt_key = self.prompt_key.strip()
        self.content = self.content.strip()
        if self.type == "prompt_reference" and not self.prompt_key:
            raise ValueError("prompt_reference layer icin prompt_key zorunludur.")
        if self.type == "inline" and not self.content:
            raise ValueError("inline layer icin content zorunludur.")
        return self


class SkillResolvedPromptLayer(BaseModel):
    type: Literal["inline", "prompt_reference"]
    label: str = ""
    source: str = ""
    content: str = ""


class SkillValidationResult(BaseModel):
    ok: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    resolved_prompt_layers: list[SkillResolvedPromptLayer] = Field(default_factory=list)


class SkillDefinition(BaseModel):
    schema_version: int = 1
    slug: str
    name: str
    description: str = ""
    when_to_use: str = ""
    applies_to: list[str] = Field(default_factory=lambda: ["chat"])
    allowed_tools: list[str] = Field(default_factory=list)
    prompt_layers: list[SkillPromptLayer] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    priority: int = 100
    status: str = "active"
    instructions_markdown: str = ""
    source: str = "project"
    path: str = ""
    content_hash: str = ""
    is_default: bool = False

    @model_validator(mode="after")
    def _normalize_fields(self) -> "SkillDefinition":
        self.slug = self.slug.strip().lower()
        self.name = self.name.strip()
        self.description = self.description.strip()
        self.when_to_use = self.when_to_use.strip()
        self.status = self.status.strip().lower() or "active"
        self.instructions_markdown = self.instructions_markdown.strip()
        self.applies_to = _unique_preserve([value.strip().lower() for value in self.applies_to if value.strip()])
        self.allowed_tools = _unique_preserve([value.strip() for value in self.allowed_tools if value.strip()])
        self.tags = _unique_preserve([value.strip() for value in self.tags if value.strip()])
        if not _SKILL_SLUG_RE.fullmatch(self.slug):
            raise ValueError("Skill slug yalnizca kucuk harf, rakam ve tire icerebilir.")
        if not self.name:
            raise ValueError("Skill name bos olamaz.")
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"Gecersiz skill status: {self.status}")
        invalid_targets = sorted(value for value in self.applies_to if value not in _VALID_APPLIES_TO)
        if invalid_targets:
            invalid_text = ", ".join(invalid_targets)
            raise ValueError(f"Gecersiz applies_to degerleri: {invalid_text}")
        return self


class _CachedSkill(BaseModel):
    definition: SkillDefinition
    meta_mtime_ns: int = 0
    markdown_mtime_ns: int = 0


README_TEXT = """Bu klasordeki skill klasorleri uygulama tarafindan runtime'da diskten okunur.

Beklenen yapi:
- skills/<skill-slug>/meta.json
- skills/<skill-slug>/SKILL.md

Notlar:
- meta.json skill metadata'sini tutar.
- SKILL.md skill'in insan okunur talimatlarini ve orneklerini tutar.
- Varsayilan skill'ler silinirse API reset/uygulama bootstrap adiminda yeniden olusturulur.
"""


DEFAULT_SKILLS: dict[str, dict[str, str]] = {
    "category-audit": {
        "meta": json.dumps(
            {
                "schema_version": 1,
                "slug": "category-audit",
                "name": "Category Audit",
                "description": "Secili urunun kategori uyumunu, arama niyetini ve alan bazli eksiklerini inceler.",
                "when_to_use": "Kategori uyumu zayif oldugunda, urun farkli kategori niyetleriyle karisiyorsa veya SEO onceligi kategorik hizalama ise kullan.",
                "applies_to": ["chat", "rewrite"],
                "allowed_tools": [
                    "get_product_details",
                    "seo_score_product",
                    "validate_rewrite",
                    "get_seo_guidelines",
                    SAVE_SEO_SUGGESTION_TOOL_NAME,
                ],
                "prompt_layers": [
                    {
                        "type": "inline",
                        "label": "Category Audit Lens",
                        "content": (
                            "Kategori uyumuna odaklan. Urun basligi, meta alanlari ve aciklamada kategori niyetiyle uyumsuz "
                            "ifadelere dikkat et. Once mevcut kategoriyle uyumlu keyword bosluklarini belirle, sonra yalnizca "
                            "gercek urun verisine dayanan duzeltmeler oner."
                        ),
                    }
                ],
                "tags": ["seo", "category", "audit"],
                "priority": 20,
                "status": "active",
            },
            ensure_ascii=False,
            indent=2,
        ),
        "markdown": """# Category Audit

Bu skill, secili urunu mevcut kategorisi ve arama niyeti acisindan inceler.

## Calisma Sekli
- Once kategori ile urun adi ve meta alanlari arasindaki uyumu degerlendir.
- Kategoriye uymayan veya fazla genel kalan ifadeleri ayikla.
- Urunu farkli bir kategoriye tasimayi onermeden once metinsel hizalama adimlarini onceliklendir.
- Oneri verirken mevcut urun verisini koru; yeni ozellik uydurma.
""",
    },
    "brand-voice-rewrite": {
        "meta": json.dumps(
            {
                "schema_version": 1,
                "slug": "brand-voice-rewrite",
                "name": "Brand Voice Rewrite",
                "description": "Mevcut urun anlatimini daha tutarli, kontrollu ve marka tonuna uygun hale getirir.",
                "when_to_use": "Marka tonu daginik oldugunda, urun metni fazla teknik veya fazla genelse ve kontrollu bir rewrite isteniyorsa kullan.",
                "applies_to": ["chat", "rewrite", "batch"],
                "allowed_tools": [
                    "get_product_details",
                    "seo_score_product",
                    "validate_rewrite",
                    SAVE_SEO_SUGGESTION_TOOL_NAME,
                    "save_suggestion",
                ],
                "prompt_layers": [
                    {
                        "type": "inline",
                        "label": "Brand Voice Constraints",
                        "content": (
                            "Marka tonu net, kontrollu ve guven verici olsun. Abartili reklam dili, asiri iddia ve belirsiz superlative "
                            "ifadelerden kacın. Okunabilirligi artirirken ticari niyeti koru."
                        ),
                    }
                ],
                "tags": ["rewrite", "brand", "tone"],
                "priority": 30,
                "status": "active",
            },
            ensure_ascii=False,
            indent=2,
        ),
        "markdown": """# Brand Voice Rewrite

Bu skill, marka dilini duzene sokmak ve urun anlatimini daha tutarli hale getirmek icin kullanilir.

## Kurallar
- Marka tonu sakin, profesyonel ve guvenilir kalmali.
- Teknik detaylar varsa sadeleştir ama kaybetme.
- Meta ve aciklama alanlarinda ayni ton korunmali.
- Kullanici yeni bir ton tarif etmedikce fazla agresif metin yazma.
""",
    },
    "launch-readiness": {
        "meta": json.dumps(
            {
                "schema_version": 1,
                "slug": "launch-readiness",
                "name": "Launch Readiness",
                "description": "Yayina cikmadan once urunun SEO ve icerik eksiklerini kontrol eder.",
                "when_to_use": "Urun yayina alinmadan once son kontrol, alan eksigi taramasi veya yayina hazirlik checklist'i istendiginde kullan.",
                "applies_to": ["chat", "rewrite"],
                "allowed_tools": [
                    "get_product_details",
                    "seo_score_product",
                    "validate_rewrite",
                    "get_seo_guidelines",
                    SAVE_SEO_SUGGESTION_TOOL_NAME,
                    APPLY_SEO_TO_IKAS_TOOL_NAME,
                ],
                "prompt_layers": [
                    {
                        "type": "inline",
                        "label": "Launch Checklist",
                        "content": (
                            "Urunu yayin oncesi checklist mantigiyla kontrol et. Baslik, meta title, meta description, TR/EN aciklama, "
                            "kategori uyumu ve AI citability acisindan eksikleri net sirala. Onceligi eksik veya sifir puanli alanlara ver."
                        ),
                    }
                ],
                "tags": ["launch", "checklist", "seo"],
                "priority": 10,
                "status": "active",
            },
            ensure_ascii=False,
            indent=2,
        ),
        "markdown": """# Launch Readiness

Bu skill, urunun yayina cikmadan once asgari SEO ve icerik hijyenini kontrol eder.

## Kontrol Listesi
- Baslik ve meta alanlari dolu mu?
- Aciklama yeterince taranabilir ve bilgi yogun mu?
- EN aciklama gerekiyorsa mevcut mu?
- En dusuk skor alanlari net olarak listelendi mi?
- Kullanici isterse bir sonraki adim olarak duzeltme onerisi hazirla.
""",
    },
}

_skill_cache: dict[str, _CachedSkill] = {}


def _unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _skill_dir(slug: str) -> Path:
    normalized = normalize_skill_slug(slug)
    return get_skills_dir() / normalized


def _compute_content_hash(meta_text: str, markdown_text: str) -> str:
    digest = hashlib.sha256()
    digest.update(meta_text.encode("utf-8"))
    digest.update(b"\n--\n")
    digest.update(markdown_text.encode("utf-8"))
    return digest.hexdigest()


def normalize_skill_slug(slug: str) -> str:
    normalized = (slug or "").strip().lower()
    if not _SKILL_SLUG_RE.fullmatch(normalized):
        raise ValueError("Skill slug yalnizca kucuk harf, rakam ve tire icerebilir.")
    return normalized


def get_available_tool_names() -> list[str]:
    names = {
        APPLY_SEO_TO_IKAS_TOOL_NAME,
        SAVE_SEO_SUGGESTION_TOOL_NAME,
        *create_chat_toolkit().tool_names,
        *create_seo_rewrite_toolkit().tool_names,
        *create_batch_toolkit().tool_names,
    }
    return sorted(names)


def get_skills_dir() -> Path:
    ensure_skill_files()
    return SKILLS_DIR


def ensure_skill_files() -> Path:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    readme_path = SKILLS_DIR / _README_NAME
    if not readme_path.exists():
        readme_path.write_text(README_TEXT, encoding="utf-8")

    for slug, payload in DEFAULT_SKILLS.items():
        skill_dir = SKILLS_DIR / slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        meta_path = skill_dir / _META_FILE
        markdown_path = skill_dir / _MARKDOWN_FILE
        if not meta_path.exists():
            meta_path.write_text(payload["meta"], encoding="utf-8")
        if not markdown_path.exists():
            markdown_path.write_text(payload["markdown"], encoding="utf-8")

    return SKILLS_DIR


def _parse_frontmatter(markdown_text: str) -> tuple[dict[str, Any], str]:
    text = markdown_text.replace("\r\n", "\n")
    lines = text.split("\n")
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}, markdown_text.strip()

    metadata: dict[str, Any] = {}
    current_list_key: str | None = None
    body_start_idx = 0

    for idx in range(1, len(lines)):
        raw_line = lines[idx]
        stripped = raw_line.strip()
        if stripped == "---":
            body_start_idx = idx + 1
            break
        if not stripped:
            continue
        if stripped.startswith("- ") and current_list_key:
            metadata.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        current_list_key = None
        match = _FRONTMATTER_LINE_RE.match(stripped)
        if not match:
            continue
        key = match.group("key")
        value = match.group("value").strip()
        if not value:
            metadata[key] = []
            current_list_key = key
            continue
        if value.startswith("[") and value.endswith("]"):
            try:
                metadata[key] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        if value.lower() in {"true", "false"}:
            metadata[key] = value.lower() == "true"
            continue
        if re.fullmatch(r"-?\d+", value):
            metadata[key] = int(value)
            continue
        metadata[key] = value.strip("\"'")

    body = "\n".join(lines[body_start_idx:]).strip()
    return metadata, body


def _prompt_keys() -> set[str]:
    keys: set[str] = set()
    for _, prompt_keys in get_prompt_editor_groups():
        keys.update(prompt_keys)
    return keys


def _load_skill_from_disk(slug: str) -> SkillDefinition:
    skill_dir = _skill_dir(slug)
    meta_path = skill_dir / _META_FILE
    markdown_path = skill_dir / _MARKDOWN_FILE
    if not skill_dir.exists():
        raise KeyError(f"Skill bulunamadi: {slug}")
    if not markdown_path.exists() and not meta_path.exists():
        raise KeyError(f"Skill dosyalari eksik: {slug}")

    meta_mtime_ns = meta_path.stat().st_mtime_ns if meta_path.exists() else 0
    markdown_mtime_ns = markdown_path.stat().st_mtime_ns if markdown_path.exists() else 0

    cached = _skill_cache.get(slug)
    if cached and cached.meta_mtime_ns == meta_mtime_ns and cached.markdown_mtime_ns == markdown_mtime_ns:
        return cached.definition.model_copy(deep=True)

    markdown_text = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    metadata_from_frontmatter, markdown_body = _parse_frontmatter(markdown_text)

    metadata: dict[str, Any] = {}
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata = {
        **metadata_from_frontmatter,
        **metadata,
        "slug": slug,
        "instructions_markdown": markdown_body,
        "source": "system" if slug in DEFAULT_SKILLS else "project",
        "path": str(skill_dir),
        "is_default": slug in DEFAULT_SKILLS,
    }
    content_hash = _compute_content_hash(json.dumps(metadata, ensure_ascii=False, sort_keys=True), markdown_body)
    metadata["content_hash"] = content_hash
    definition = SkillDefinition.model_validate(metadata)
    _skill_cache[slug] = _CachedSkill(
        definition=definition,
        meta_mtime_ns=meta_mtime_ns,
        markdown_mtime_ns=markdown_mtime_ns,
    )
    return definition.model_copy(deep=True)


def list_skill_definitions() -> list[SkillDefinition]:
    ensure_skill_files()
    skills: list[SkillDefinition] = []
    for child in sorted(SKILLS_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir():
            continue
        if not _SKILL_SLUG_RE.fullmatch(child.name):
            logger.warning("Skill klasoru slug kurallarina uymuyor, atlandi: %s", child)
            continue
        try:
            skills.append(_load_skill_from_disk(child.name))
        except Exception as exc:
            logger.warning("Skill yuklenemedi: %s (%s)", child.name, exc)
    return sorted(skills, key=lambda skill: (skill.priority, skill.name.lower(), skill.slug))


def get_skill_definition(slug: str) -> SkillDefinition:
    ensure_skill_files()
    return _load_skill_from_disk(normalize_skill_slug(slug))


def _serialize_skill_metadata(skill: SkillDefinition) -> dict[str, Any]:
    payload = skill.model_dump(mode="json")
    payload.pop("instructions_markdown", None)
    payload.pop("source", None)
    payload.pop("path", None)
    payload.pop("content_hash", None)
    payload.pop("is_default", None)
    return payload


def validate_skill_definition(skill: SkillDefinition) -> SkillValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    resolved_layers: list[SkillResolvedPromptLayer] = []

    available_tools = set(get_available_tool_names())
    prompt_keys = _prompt_keys()

    for tool_name in skill.allowed_tools:
        if tool_name not in available_tools:
            errors.append(f"Bilinmeyen tool: {tool_name}")

    if not skill.instructions_markdown and not skill.prompt_layers:
        warnings.append("Skill talimati bos; yalnizca metadata ile kaydediliyor.")

    for layer in skill.prompt_layers:
        if layer.type == "inline":
            resolved_layers.append(
                SkillResolvedPromptLayer(
                    type="inline",
                    label=layer.label or "Inline Layer",
                    source="inline",
                    content=layer.content,
                )
            )
            continue

        prompt_key = layer.prompt_key
        if prompt_key not in prompt_keys:
            errors.append(f"Bilinmeyen prompt anahtari: {prompt_key}")
            continue
        try:
            prompt_content = load_prompt_template(prompt_key)
        except Exception as exc:
            errors.append(f"Prompt katmani okunamadi: {prompt_key} ({exc})")
            continue

        meta = get_prompt_editor_meta(prompt_key)
        runtime_variables = [str(item) for item in meta.get("runtime_variables", ())]
        if runtime_variables:
            warnings.append(
                f"{prompt_key} runtime degisken kullaniyor ({', '.join(runtime_variables)}); preview ham sablonu gosterir."
            )

        resolved_layers.append(
            SkillResolvedPromptLayer(
                type="prompt_reference",
                label=layer.label or str(meta.get("title") or prompt_key),
                source=prompt_key,
                content=prompt_content,
            )
        )

    return SkillValidationResult(ok=not errors, errors=errors, warnings=warnings, resolved_prompt_layers=resolved_layers)


def build_skill_prompt(
    skill: SkillDefinition,
    *,
    applies_to: str = "chat",
    include_warnings: bool = False,
) -> str:
    target = applies_to.strip().lower()
    if target and skill.applies_to and target not in skill.applies_to:
        return ""

    validation = validate_skill_definition(skill)
    parts: list[str] = [
        f"Aktif skill: {skill.name}",
        f"Aciklama: {skill.description}" if skill.description else "",
        f"Ne zaman kullan: {skill.when_to_use}" if skill.when_to_use else "",
    ]
    if skill.instructions_markdown:
        parts.append(skill.instructions_markdown)
    for layer in validation.resolved_prompt_layers:
        parts.append(f"[Skill Layer: {layer.label}]\n{layer.content}")
    if include_warnings and validation.warnings:
        parts.append(
            "Skill warnings:\n" + "\n".join(f"- {warning}" for warning in validation.warnings)
        )
    return "\n\n".join(part for part in parts if part).strip()


def preview_skill_definition(skill: SkillDefinition, *, applies_to: str = "chat") -> dict[str, Any]:
    validation = validate_skill_definition(skill)
    return {
        "validation": validation.model_dump(mode="json"),
        "composed_prompt": build_skill_prompt(skill, applies_to=applies_to, include_warnings=True),
    }


def save_skill_definition(skill: SkillDefinition) -> SkillDefinition:
    validation = validate_skill_definition(skill)
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))

    skill_dir = _skill_dir(skill.slug)
    skill_dir.mkdir(parents=True, exist_ok=True)
    meta_path = skill_dir / _META_FILE
    markdown_path = skill_dir / _MARKDOWN_FILE
    meta_path.write_text(
        json.dumps(_serialize_skill_metadata(skill), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(skill.instructions_markdown.strip() + ("\n" if skill.instructions_markdown.strip() else ""), encoding="utf-8")
    _skill_cache.pop(skill.slug, None)
    return get_skill_definition(skill.slug)


def delete_skill_definition(slug: str) -> None:
    normalized = normalize_skill_slug(slug)
    if normalized in DEFAULT_SKILLS:
        raise ValueError("Varsayilan skill silinemez; reset kullanin.")
    skill_dir = _skill_dir(normalized)
    if not skill_dir.exists():
        raise KeyError(f"Skill bulunamadi: {normalized}")
    shutil.rmtree(skill_dir)
    _skill_cache.pop(normalized, None)


def reset_skill_definition(slug: str) -> SkillDefinition:
    normalized = normalize_skill_slug(slug)
    skill_dir = _skill_dir(normalized)
    if normalized not in DEFAULT_SKILLS:
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        _skill_cache.pop(normalized, None)
        raise KeyError(f"Varsayilan olmayan skill reset edilemez: {normalized}")

    payload = DEFAULT_SKILLS[normalized]
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / _META_FILE).write_text(payload["meta"], encoding="utf-8")
    (skill_dir / _MARKDOWN_FILE).write_text(payload["markdown"], encoding="utf-8")
    _skill_cache.pop(normalized, None)
    return get_skill_definition(normalized)


def export_skill_definition(slug: str) -> dict[str, Any]:
    skill = get_skill_definition(slug)
    return skill.model_dump(mode="json")


def import_skill_definition(payload: dict[str, Any]) -> SkillDefinition:
    skill = SkillDefinition.model_validate(payload)
    return save_skill_definition(skill)
