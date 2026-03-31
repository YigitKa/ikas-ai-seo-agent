"""Tool Runtime v2 definitions, registry, and built-in tool factories."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from core.models import Product, SeoSuggestion
from core.permissions import PermissionEngine, PermissionRequest, PermissionRule

logger = logging.getLogger(__name__)

ToolRiskLevel = Literal["low", "medium", "high", "critical"]
ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]

SAVE_SUGGESTION_TOOL_NAME = "save_suggestion"
SAVE_SEO_SUGGESTION_TOOL_NAME = "save_seo_suggestion"
APPLY_SEO_TO_IKAS_TOOL_NAME = "apply_seo_to_ikas"

_DEFAULT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
}

_SHARED_TOOL_ALLOWLIST = frozenset({"seo_rewrite", "chat", "batch"})


def tool_success(data: Any = None, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "meta": dict(meta or {}),
    }


def tool_error(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": dict(details or {}),
            "retryable": retryable,
        },
        "meta": dict(meta or {}),
    }


def _safe_json_content(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _try_parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _looks_like_runtime_payload(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("ok"), bool)
        and any(key in payload for key in ("data", "error", "meta"))
    )


def _coerce_error_payload(payload: Any) -> "ToolExecutionError":
    if isinstance(payload, ToolExecutionError):
        return payload
    if isinstance(payload, dict):
        return ToolExecutionError(
            code=str(payload.get("code") or "tool_error"),
            message=str(payload.get("message") or "Tool execution failed."),
            details=dict(payload.get("details") or {}),
            retryable=bool(payload.get("retryable", False)),
        )
    return ToolExecutionError(code="tool_error", message=str(payload or "Tool execution failed."))


def _normalize_agent_type(agent_type: str | None) -> str:
    return (agent_type or "").strip().lower()


def _expand_agent_scopes(agent_type: str | None) -> set[str]:
    normalized = _normalize_agent_type(agent_type)
    if not normalized:
        return set()

    scopes = {normalized}
    parts = normalized.split(":")
    for idx in range(1, len(parts)):
        scopes.add(":".join(parts[:idx]))
    return scopes


@dataclass
class ToolExecutionError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }


@dataclass
class ToolResponseEnvelope:
    ok: bool
    tool_name: str
    data: Any = None
    error: ToolExecutionError | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        tool_name: str,
        data: Any = None,
        *,
        meta: dict[str, Any] | None = None,
    ) -> "ToolResponseEnvelope":
        return cls(ok=True, tool_name=tool_name, data=data, error=None, meta=dict(meta or {}))

    @classmethod
    def failure(
        cls,
        tool_name: str,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        meta: dict[str, Any] | None = None,
        data: Any = None,
    ) -> "ToolResponseEnvelope":
        return cls(
            ok=False,
            tool_name=tool_name,
            data=data,
            error=ToolExecutionError(
                code=code,
                message=message,
                details=dict(details or {}),
                retryable=retryable,
            ),
            meta=dict(meta or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tool_name": self.tool_name,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
            "meta": self.meta,
        }

    def to_json(self) -> str:
        return _safe_json_content(self.to_dict())


@dataclass
class ToolExecutionResult:
    definition: "ToolDefinition"
    response: ToolResponseEnvelope
    duration_ms: int = 0
    internal_meta: dict[str, Any] = field(default_factory=dict)

    @property
    def content(self) -> str:
        return self.response.to_json()

    @property
    def ok(self) -> bool:
        return self.response.ok

    @property
    def data(self) -> Any:
        return self.response.data

    @property
    def error(self) -> ToolExecutionError | None:
        return self.response.error


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    risk_level: ToolRiskLevel = "low"
    read_only: bool = True
    destructive: bool = False
    concurrency_safe: bool = True
    ui_meta: dict[str, Any] = field(default_factory=dict)
    handler: ToolHandler | None = None
    allowlist: frozenset[str] | set[str] | list[str] = field(default_factory=frozenset)
    visible: bool = True

    def __post_init__(self) -> None:
        schema = self.input_schema or self.parameters or _DEFAULT_INPUT_SCHEMA
        copied_schema = deepcopy(schema)
        self.input_schema = copied_schema
        self.parameters = copied_schema
        self.allowlist = frozenset(_normalize_agent_type(value) for value in self.allowlist if _normalize_agent_type(value))
        self.ui_meta = dict(self.ui_meta)

    def with_handler(self, handler: ToolHandler | None) -> "ToolDefinition":
        return replace(self, handler=handler)

    def is_available_to(self, agent_type: str | None) -> bool:
        if not self.allowlist:
            return True
        scopes = _expand_agent_scopes(agent_type)
        return bool(scopes.intersection(self.allowlist))

    def to_openai_function(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


AgentTool = ToolDefinition


def _normalize_tool_response(
    tool: ToolDefinition,
    payload: Any,
    *,
    duration_ms: int,
) -> ToolResponseEnvelope:
    if isinstance(payload, ToolResponseEnvelope):
        response = payload
    elif _looks_like_runtime_payload(payload):
        response = (
            ToolResponseEnvelope.success(
                tool.name,
                data=payload.get("data"),
                meta=dict(payload.get("meta") or {}),
            )
            if payload.get("ok")
            else ToolResponseEnvelope(
                ok=False,
                tool_name=tool.name,
                data=payload.get("data"),
                error=_coerce_error_payload(payload.get("error")),
                meta=dict(payload.get("meta") or {}),
            )
        )
    elif isinstance(payload, dict) and payload.get("error"):
        response = ToolResponseEnvelope.failure(
            tool.name,
            code="tool_error",
            message=str(payload.get("error")),
            details={key: value for key, value in payload.items() if key != "error"},
        )
    else:
        response = ToolResponseEnvelope.success(tool.name, data=payload)

    response.meta.setdefault("duration_ms", duration_ms)
    response.meta.setdefault("risk_level", tool.risk_level)
    response.meta.setdefault("read_only", tool.read_only)
    response.meta.setdefault("destructive", tool.destructive)
    response.meta.setdefault("concurrency_safe", tool.concurrency_safe)
    return response


def unwrap_tool_response_data(result_text: str) -> Any:
    parsed = _try_parse_json(result_text)
    if isinstance(parsed, dict) and isinstance(parsed.get("ok"), bool) and "tool_name" in parsed:
        return parsed.get("data")
    return parsed if parsed is not None else result_text


class ToolRegistry:
    """Shared registry for Tool Runtime v2 definitions."""

    def __init__(
        self,
        tools: Iterable[ToolDefinition] | None = None,
        *,
        permission_engine: PermissionEngine | None = None,
        runtime_rule_provider: Callable[[ToolDefinition, dict[str, Any], str | None], Iterable[PermissionRule]] | None = None,
    ) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._permission_engine = permission_engine
        self._runtime_rule_provider = runtime_rule_provider
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: ToolDefinition) -> ToolDefinition:
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def list(
        self,
        *,
        agent_type: str | None = None,
        names: Iterable[str] | None = None,
        include_hidden: bool = False,
    ) -> list[ToolDefinition]:
        selected_names = set(names or [])
        tools: list[ToolDefinition] = []
        for tool in self._tools.values():
            if selected_names and tool.name not in selected_names:
                continue
            if not include_hidden and not tool.visible:
                continue
            if agent_type and not tool.is_available_to(agent_type):
                continue
            tools.append(tool)
        return tools

    def get_openai_functions(
        self,
        *,
        agent_type: str | None = None,
        names: Iterable[str] | None = None,
        include_hidden: bool = False,
    ) -> list[dict[str, Any]]:
        return [
            tool.to_openai_function()
            for tool in self.list(agent_type=agent_type, names=names, include_hidden=include_hidden)
        ]

    async def invoke(
        self,
        name: str,
        args: dict[str, Any],
        *,
        agent_type: str | None = None,
    ) -> ToolExecutionResult:
        tool = self._tools.get(name)
        if tool is None:
            response = ToolResponseEnvelope.failure(
                name,
                code="tool_not_found",
                message=f"Tool '{name}' is not available.",
                details={"available_tools": self.tool_names},
            )
            return ToolExecutionResult(
                definition=ToolDefinition(name=name, description="Unavailable tool"),
                response=response,
            )

        if agent_type and not tool.is_available_to(agent_type):
            response = ToolResponseEnvelope.failure(
                tool.name,
                code="tool_not_allowed",
                message=f"Tool '{tool.name}' is not allowed for agent '{agent_type}'.",
                details={"allowlist": sorted(tool.allowlist)},
            )
            return ToolExecutionResult(definition=tool, response=response)

        if tool.handler is None:
            response = ToolResponseEnvelope.failure(
                tool.name,
                code="tool_handler_missing",
                message=f"Tool '{tool.name}' does not have a handler.",
            )
            return ToolExecutionResult(definition=tool, response=response)

        permission_operation = str(tool.ui_meta.get("permission_operation") or "").strip()
        if self._permission_engine and permission_operation:
            runtime_rule_values = (
                self._runtime_rule_provider(tool, args, agent_type)
                if self._runtime_rule_provider is not None
                else []
            )
            runtime_rules = list(runtime_rule_values or [])
            decision = await self._permission_engine.evaluate(
                PermissionRequest(
                    operation=permission_operation,  # type: ignore[arg-type]
                    target=str(args.get("product_id") or args.get("job_id") or ""),
                    tool_name=tool.name,
                    source="tool_registry.invoke",
                    agent_type=agent_type,
                    metadata={
                        "arguments": dict(args),
                        "risk_level": tool.risk_level,
                        "read_only": tool.read_only,
                        "destructive": tool.destructive,
                    },
                ),
                runtime_rules=runtime_rules,
            )
            if not decision.allowed:
                response = ToolResponseEnvelope.failure(
                    tool.name,
                    code=decision.error_code,
                    message=decision.reason,
                    details={"permission": decision.to_dict()},
                    meta={"permission": decision.to_dict()},
                )
                return ToolExecutionResult(definition=tool, response=response)

        start = time.monotonic()
        internal_meta: dict[str, Any] = {}
        try:
            raw_result = await tool.handler(args)
        except Exception as exc:
            logger.exception("Tool '%s' raised an error", tool.name)
            duration_ms = int((time.monotonic() - start) * 1000)
            response = ToolResponseEnvelope.failure(
                tool.name,
                code="tool_execution_failed",
                message=str(exc) or "Tool execution failed.",
            )
            response.meta.setdefault("duration_ms", duration_ms)
            response.meta.setdefault("risk_level", tool.risk_level)
            response.meta.setdefault("read_only", tool.read_only)
            response.meta.setdefault("destructive", tool.destructive)
            response.meta.setdefault("concurrency_safe", tool.concurrency_safe)
            return ToolExecutionResult(definition=tool, response=response, duration_ms=duration_ms)

        duration_ms = int((time.monotonic() - start) * 1000)
        payload = raw_result
        if isinstance(raw_result, tuple) and len(raw_result) == 2:
            payload, raw_internal_meta = raw_result
            if isinstance(raw_internal_meta, dict):
                internal_meta = dict(raw_internal_meta)

        if isinstance(payload, str):
            parsed_payload = _try_parse_json(payload)
            payload = parsed_payload if parsed_payload is not None else payload

        response = _normalize_tool_response(tool, payload, duration_ms=duration_ms)
        logger.debug("Tool '%s' executed in %d ms", tool.name, duration_ms)
        return ToolExecutionResult(
            definition=tool,
            response=response,
            duration_ms=duration_ms,
            internal_meta=internal_meta,
        )

    async def execute(
        self,
        name: str,
        args: dict[str, Any],
        *,
        agent_type: str | None = None,
    ) -> str:
        return (await self.invoke(name, args, agent_type=agent_type)).content

    def __contains__(self, name: str) -> bool:
        return name in self._tools


class AgentToolkit:
    """Filtered toolkit view over Tool Runtime v2 registry."""

    def __init__(
        self,
        tools: Iterable[ToolDefinition] | None = None,
        *,
        agent_type: str | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self._registry = registry or ToolRegistry()
        self._agent_type = agent_type
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        self._registry.register(tool)

    def get(self, name: str) -> ToolDefinition | None:
        tool = self._registry.get(name)
        if tool is None:
            return None
        if self._agent_type and not tool.is_available_to(self._agent_type):
            return None
        return tool

    @property
    def tool_names(self) -> list[str]:
        return [tool.name for tool in self._registry.list(agent_type=self._agent_type)]

    def get_openai_functions(self) -> list[dict[str, Any]]:
        return self._registry.get_openai_functions(agent_type=self._agent_type)

    async def invoke(self, name: str, args: dict[str, Any]) -> ToolExecutionResult:
        return await self._registry.invoke(name, args, agent_type=self._agent_type)

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        return (await self.invoke(name, args)).content

    def __len__(self) -> int:
        return len(self.tool_names)

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None


def build_seo_score_product_tool() -> ToolDefinition:
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        from core.seo.analyzer import analyze_product
        from data import db

        product_id = str(args.get("product_id") or "")
        product = await db.get_product(product_id)
        if product is None:
            return tool_error(
                "product_not_found",
                f"Product '{product_id}' not found.",
                details={"product_id": product_id},
            )

        target_keywords = args.get("target_keywords")
        score = analyze_product(product, target_keywords)
        return tool_success(score.model_dump(mode="json"))

    return ToolDefinition(
        name="seo_score_product",
        description=(
            "Bir urunu kural tabanli SEO rubrigine gore skorlar. "
            "Issues ve suggestions listesini de dondurur."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Urun ID'si"},
                "target_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hedef anahtar kelimeler (opsiyonel)",
                },
            },
            "required": ["product_id"],
        },
        risk_level="low",
        read_only=True,
        destructive=False,
        concurrency_safe=True,
        ui_meta={"label": "SEO Puanlama", "variant": "score"},
        handler=handler,
        allowlist=_SHARED_TOOL_ALLOWLIST,
    )


def build_get_product_details_tool() -> ToolDefinition:
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        from data import db

        product_id = str(args.get("product_id") or "")
        product = await db.get_product(product_id)
        if product is None:
            return tool_error(
                "product_not_found",
                f"Product '{product_id}' not found.",
                details={"product_id": product_id},
            )
        return tool_success(product.model_dump(mode="json"))

    return ToolDefinition(
        name="get_product_details",
        description="Yerel veritabanindan urun detaylarini getirir.",
        input_schema={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Urun ID'si"},
            },
            "required": ["product_id"],
        },
        risk_level="low",
        read_only=True,
        destructive=False,
        concurrency_safe=True,
        ui_meta={"label": "Urun Detaylari", "variant": "details"},
        handler=handler,
        allowlist=_SHARED_TOOL_ALLOWLIST,
    )


def build_search_products_tool() -> ToolDefinition:
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        from data import db

        products = await db.get_all_products()
        max_score = args.get("max_score")
        limit = int(args.get("limit", 20) or 20)

        if max_score is not None:
            from core.seo.analyzer import analyze_product

            filtered: list[dict[str, Any]] = []
            for product in products:
                score = analyze_product(product)
                if score.total_score <= int(max_score):
                    filtered.append({
                        "id": product.id,
                        "name": product.name,
                        "score": score.total_score,
                    })
            filtered.sort(key=lambda item: item["score"])
            return tool_success(filtered[:limit])

        return tool_success([{"id": product.id, "name": product.name} for product in products[:limit]])

    return ToolDefinition(
        name="search_products",
        description=(
            "Yerel veritabanindaki urunleri listeler veya filtreler. "
            "max_score ile dusuk skorlu urunleri bulabilirsiniz."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "max_score": {
                    "type": "integer",
                    "description": "Bu skorun altindaki urunleri filtrele (opsiyonel)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maksimum sonuc sayisi (default 20)",
                },
            },
        },
        risk_level="low",
        read_only=True,
        destructive=False,
        concurrency_safe=True,
        ui_meta={"label": "Urun Arama", "variant": "search"},
        handler=handler,
        allowlist=_SHARED_TOOL_ALLOWLIST,
    )


def build_validate_rewrite_tool() -> ToolDefinition:
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        from core.seo.analyzer import analyze_product
        from data import db

        product_id = str(args.get("product_id") or "")
        product = await db.get_product(product_id)
        if product is None:
            return tool_error(
                "product_not_found",
                f"Product '{product_id}' not found.",
                details={"product_id": product_id},
            )

        original_score = analyze_product(product)
        updates = args.get("updates", {})
        modified_data = product.model_dump(mode="json")
        if isinstance(updates, dict):
            for field_name, value in updates.items():
                if field_name in modified_data:
                    modified_data[field_name] = value
        modified_product = Product.model_validate(modified_data)
        new_score = analyze_product(modified_product)
        score_delta = new_score.total_score - original_score.total_score

        return tool_success({
            "original_score": original_score.total_score,
            "new_score": new_score.total_score,
            "improvement": score_delta,
            "improved": score_delta > 0,
            "score_delta": score_delta,
            "original_summary_scores": {
                "seo": original_score.seo_score,
                "geo": original_score.geo_score,
                "aeo": original_score.aeo_score,
            },
            "new_summary_scores": {
                "seo": new_score.seo_score,
                "geo": new_score.geo_score,
                "aeo": new_score.aeo_score,
            },
            "original_breakdown": {
                "title": original_score.title_score,
                "description": original_score.description_score,
                "meta_title": original_score.meta_score,
                "meta_description": original_score.meta_desc_score,
                "keyword": original_score.keyword_score,
                "content_quality": original_score.content_quality_score,
                "technical": original_score.technical_seo_score,
                "readability": original_score.readability_score,
                "ai_citability": original_score.ai_citability_score,
            },
            "new_breakdown": {
                "title": new_score.title_score,
                "description": new_score.description_score,
                "meta_title": new_score.meta_score,
                "meta_description": new_score.meta_desc_score,
                "keyword": new_score.keyword_score,
                "content_quality": new_score.content_quality_score,
                "technical": new_score.technical_seo_score,
                "readability": new_score.readability_score,
                "ai_citability": new_score.ai_citability_score,
            },
            "remaining_issues": new_score.issues,
        })

    return ToolDefinition(
        name="validate_rewrite",
        description=(
            "Urun alanlarini degistirmeden, onerilen degisikliklerle skoru simule eder. "
            "Onceki/sonraki skor karsilastirmasi dondurur."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Urun ID'si"},
                "updates": {
                    "type": "object",
                    "description": (
                        "Simule edilecek alan degisiklikleri. "
                        'Ornek: {"name": "Yeni Baslik", "description": "<p>Yeni aciklama...</p>"}'
                    ),
                },
            },
            "required": ["product_id", "updates"],
        },
        risk_level="low",
        read_only=True,
        destructive=False,
        concurrency_safe=True,
        ui_meta={"label": "Yeniden Yasim Dogrulama", "variant": "validation"},
        handler=handler,
        allowlist=_SHARED_TOOL_ALLOWLIST,
    )


def build_save_suggestion_tool() -> ToolDefinition:
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        from data import db

        product_id = str(args.get("product_id") or "")
        product = await db.get_product(product_id)
        if product is None:
            return tool_error(
                "product_not_found",
                f"Product '{product_id}' not found.",
                details={"product_id": product_id},
            )

        from core.utils.presentation import get_en_description_value, get_tr_description_value

        suggestion = SeoSuggestion(
            product_id=product_id,
            original_name=product.name,
            suggested_name=str(args.get("suggested_name") or ""),
            original_description=get_tr_description_value(product.description, product.description_translations),
            suggested_description=str(args.get("suggested_description") or ""),
            original_description_en=get_en_description_value(product.description_translations),
            suggested_description_en=str(args.get("suggested_description_en") or ""),
            original_meta_title=product.meta_title or "",
            suggested_meta_title=str(args.get("suggested_meta_title") or ""),
            original_meta_description=product.meta_description or "",
            suggested_meta_description=str(args.get("suggested_meta_description") or ""),
            thinking_text=str(args.get("thinking_text") or ""),
            status="pending",
        )
        await db.save_or_update_pending_suggestion(suggestion)

        return tool_success({
            "success": True,
            "product_id": product_id,
            "status": "pending",
            "message": "Oneri basariyla kaydedildi.",
        })

    return ToolDefinition(
        name=SAVE_SUGGESTION_TOOL_NAME,
        description=(
            "Optimize edilmis SEO onerilerini veritabanina kaydeder. "
            "Status 'pending' olarak kaydedilir; kullanici onayi bekler."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Urun ID'si"},
                "suggested_name": {"type": "string", "description": "Onerilen urun adi (opsiyonel)"},
                "suggested_description": {"type": "string", "description": "Onerilen TR aciklama (HTML)"},
                "suggested_description_en": {"type": "string", "description": "Onerilen EN aciklama (opsiyonel)"},
                "suggested_meta_title": {"type": "string", "description": "Onerilen meta title"},
                "suggested_meta_description": {"type": "string", "description": "Onerilen meta description"},
                "thinking_text": {"type": "string", "description": "Dusunce sureci aciklamasi (opsiyonel)"},
            },
            "required": ["product_id"],
        },
        risk_level="medium",
        read_only=False,
        destructive=False,
        concurrency_safe=False,
        ui_meta={"label": "Oneri Kaydedildi", "variant": "save"},
        handler=handler,
        allowlist=_SHARED_TOOL_ALLOWLIST,
    )


def build_get_seo_guidelines_tool() -> ToolDefinition:
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        return tool_success({
            "rubric": {
                "title": {"max": 15, "ideal_length": "30-60 karakter", "tips": "Power words, keyword near front, no special chars"},
                "description_tr": {"max": 20, "ideal": "Min 150 kelime, paragraf yapisi, basliklar, listeler, bold"},
                "description_en": {"max": 5, "ideal": "Min 100 kelime, Turkce karakter olmamali"},
                "meta_title": {"max": 15, "ideal_length": "50-60 karakter", "tips": "Brand separator, farkli urun adindan"},
                "meta_description": {"max": 10, "ideal_length": "120-160 karakter", "tips": "CTA icermeli"},
                "keyword_optimization": {"max": 10, "tips": "Target keywords in description/meta"},
                "content_quality": {"max": 10, "tips": "No keyword stuffing (>5%), diverse vocabulary"},
                "technical_seo": {"max": 10, "tips": "3-5 images, 3-5 tags, category, slug"},
                "readability": {"max": 5, "tips": "15-25 words/sentence, transition words"},
                "ai_citability": {"max": 10, "tips": "Structured facts, clear attributes, AI-readable"},
            },
            "total_max": 100,
        })

    return ToolDefinition(
        name="get_seo_guidelines",
        description="SEO skorlama rubriginin kurallarini ve max puanlarini dondurur.",
        input_schema={"type": "object", "properties": {}},
        risk_level="low",
        read_only=True,
        destructive=False,
        concurrency_safe=True,
        ui_meta={"label": "SEO Kilavuzlari", "variant": "guidelines"},
        handler=handler,
        allowlist=_SHARED_TOOL_ALLOWLIST,
    )


def build_save_seo_suggestion_tool(handler: ToolHandler | None = None) -> ToolDefinition:
    return ToolDefinition(
        name=SAVE_SEO_SUGGESTION_TOOL_NAME,
        description=(
            "Kullanici sohbet sirasinda sunulan SEO degisikliklerini "
            "(baslik, aciklama vb.) begendiginde ve 'uygula', 'kaydet', "
            "'bunu sectim' dediginde bu araci cagir."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "suggested_name": {
                    "type": "string",
                    "description": "Kaydedilecek yeni urun adi onerisi.",
                },
                "suggested_meta_title": {
                    "type": "string",
                    "description": "Kaydedilecek yeni meta title onerisi.",
                },
                "suggested_meta_description": {
                    "type": "string",
                    "description": "Kaydedilecek yeni meta description onerisi.",
                },
                "suggested_description": {
                    "type": "string",
                    "description": "Kaydedilecek Turkce urun aciklamasi onerisi.",
                },
                "suggested_description_en": {
                    "type": "string",
                    "description": "Kaydedilecek Ingilizce urun aciklamasi onerisi.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        risk_level="medium",
        read_only=False,
        destructive=False,
        concurrency_safe=False,
        ui_meta={"label": "Taslak Kaydet", "variant": "save"},
        handler=handler,
        allowlist=frozenset({"chat"}),
    )


def build_apply_seo_to_ikas_tool(handler: ToolHandler | None = None) -> ToolDefinition:
    return ToolDefinition(
        name=APPLY_SEO_TO_IKAS_TOOL_NAME,
        description=(
            "Onaylanan SEO degisikliklerini ikas'a uygular. "
            "Kullanici urun uzerindeki degisiklikleri onayladiginda (orn: 'uygula', 'ikas'a kaydet', 'guncelle') "
            "bu araci cagir. Alan bos ise o alan guncellenmez."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "product_id": {
                    "type": "string",
                    "description": "Guncellenecek urunun ID'si.",
                },
                "name": {
                    "type": "string",
                    "description": "Yeni urun adi (bos birak = degistirme).",
                },
                "description": {
                    "type": "string",
                    "description": "Yeni TR aciklama HTML (bos birak = degistirme).",
                },
                "description_en": {
                    "type": "string",
                    "description": "Yeni EN aciklama (bos birak = degistirme).",
                },
                "meta_title": {
                    "type": "string",
                    "description": "Yeni meta title (bos birak = degistirme).",
                },
                "meta_description": {
                    "type": "string",
                    "description": "Yeni meta description (bos birak = degistirme).",
                },
            },
            "required": ["product_id"],
            "additionalProperties": False,
        },
        risk_level="high",
        read_only=False,
        destructive=False,
        concurrency_safe=False,
        ui_meta={
            "label": "ikas Uygulama",
            "variant": "apply",
            "permission_operation": "apply",
        },
        handler=handler,
        allowlist=frozenset({"chat"}),
    )


def create_local_chat_tool_registry(
    save_suggestion_handler: ToolHandler,
    apply_handler: ToolHandler,
    *,
    permission_engine: PermissionEngine | None = None,
    runtime_rule_provider: Callable[[ToolDefinition, dict[str, Any], str | None], Iterable[PermissionRule]] | None = None,
) -> ToolRegistry:
    return ToolRegistry(
        [
            build_save_seo_suggestion_tool(save_suggestion_handler),
            build_apply_seo_to_ikas_tool(apply_handler),
        ],
        permission_engine=permission_engine,
        runtime_rule_provider=runtime_rule_provider,
    )


def create_seo_rewrite_toolkit() -> AgentToolkit:
    return AgentToolkit(
        [
            build_seo_score_product_tool(),
            build_get_product_details_tool(),
            build_validate_rewrite_tool(),
            build_save_suggestion_tool(),
            build_get_seo_guidelines_tool(),
        ],
        agent_type="seo_rewrite",
    )


def create_chat_toolkit() -> AgentToolkit:
    return AgentToolkit(
        [
            build_seo_score_product_tool(),
            build_get_product_details_tool(),
            build_search_products_tool(),
            build_validate_rewrite_tool(),
            build_save_suggestion_tool(),
            build_get_seo_guidelines_tool(),
        ],
        agent_type="chat",
    )


def create_batch_toolkit() -> AgentToolkit:
    return AgentToolkit(
        [
            build_search_products_tool(),
            build_seo_score_product_tool(),
            build_get_product_details_tool(),
            build_validate_rewrite_tool(),
            build_save_suggestion_tool(),
        ],
        agent_type="batch",
    )


__all__ = [
    "APPLY_SEO_TO_IKAS_TOOL_NAME",
    "AgentTool",
    "AgentToolkit",
    "SAVE_SEO_SUGGESTION_TOOL_NAME",
    "SAVE_SUGGESTION_TOOL_NAME",
    "ToolDefinition",
    "ToolExecutionError",
    "ToolExecutionResult",
    "ToolRegistry",
    "ToolResponseEnvelope",
    "build_apply_seo_to_ikas_tool",
    "build_get_product_details_tool",
    "build_get_seo_guidelines_tool",
    "build_save_seo_suggestion_tool",
    "build_save_suggestion_tool",
    "build_search_products_tool",
    "build_seo_score_product_tool",
    "build_validate_rewrite_tool",
    "create_batch_toolkit",
    "create_chat_toolkit",
    "create_local_chat_tool_registry",
    "create_seo_rewrite_toolkit",
    "tool_error",
    "tool_success",
    "unwrap_tool_response_data",
]
