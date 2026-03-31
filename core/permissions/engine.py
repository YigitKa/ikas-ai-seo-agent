"""Central permission and approval engine for risky operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Literal

from core.models import AppConfig

PermissionBehavior = Literal["allow", "ask", "deny"]
PermissionScope = Literal["global", "project", "session", "runtime_override"]
PermissionOperation = Literal["apply", "rollback", "bulk_apply", "db_reset", "external_write"]
PermissionAuditLogger = Callable[["PermissionAuditRecord"], Awaitable[None]]

RULE_RESOLUTION_ORDER: tuple[PermissionScope, ...] = (
    "global",
    "project",
    "session",
    "runtime_override",
)
RISKY_PERMISSION_OPERATIONS = frozenset({
    "apply",
    "rollback",
    "bulk_apply",
    "db_reset",
    "external_write",
})


@dataclass
class PermissionRule:
    behavior: PermissionBehavior
    operation: PermissionOperation | None = None
    tool_name: str | None = None
    source: str | None = None
    scope: PermissionScope = "global"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, request: "PermissionRequest") -> bool:
        if self.operation is not None and self.operation != request.operation:
            return False
        if self.tool_name is not None and self.tool_name != request.tool_name:
            return False
        if self.source is not None and self.source != request.source:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "behavior": self.behavior,
            "operation": self.operation,
            "tool_name": self.tool_name,
            "source": self.source,
            "description": self.description,
            "metadata": dict(self.metadata),
        }


@dataclass
class PermissionRequest:
    operation: PermissionOperation
    target: str = ""
    tool_name: str | None = None
    source: str = ""
    agent_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "target": self.target,
            "tool_name": self.tool_name,
            "source": self.source,
            "agent_type": self.agent_type,
            "metadata": dict(self.metadata),
        }


@dataclass
class PermissionDecision:
    behavior: PermissionBehavior
    request: PermissionRequest
    matched_rule: PermissionRule | None = None
    resolution_trace: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.behavior == "allow"

    @property
    def requires_approval(self) -> bool:
        return self.request.operation in RISKY_PERMISSION_OPERATIONS

    @property
    def error_code(self) -> str:
        return "permission_approval_required" if self.behavior == "ask" else "permission_denied"

    @property
    def http_status_code(self) -> int:
        return 409 if self.behavior == "ask" else 403

    def to_dict(self) -> dict[str, Any]:
        return {
            "behavior": self.behavior,
            "reason": self.reason,
            "request": self.request.to_dict(),
            "matched_rule": self.matched_rule.to_dict() if self.matched_rule else None,
            "resolution_trace": list(self.resolution_trace),
            "requires_approval": self.requires_approval,
        }


@dataclass
class PermissionAuditRecord:
    operation: PermissionOperation
    target: str
    tool_name: str | None
    source: str
    agent_type: str | None
    decision: PermissionBehavior
    reason: str
    rule_scope: PermissionScope | None
    rule_behavior: PermissionBehavior | None
    audit_data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_decision(cls, decision: PermissionDecision) -> "PermissionAuditRecord":
        matched_rule = decision.matched_rule
        return cls(
            operation=decision.request.operation,
            target=decision.request.target,
            tool_name=decision.request.tool_name,
            source=decision.request.source,
            agent_type=decision.request.agent_type,
            decision=decision.behavior,
            reason=decision.reason,
            rule_scope=matched_rule.scope if matched_rule else None,
            rule_behavior=matched_rule.behavior if matched_rule else None,
            audit_data={
                "request": decision.request.to_dict(),
                "resolution_trace": list(decision.resolution_trace),
                "matched_rule": matched_rule.to_dict() if matched_rule else None,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "target": self.target,
            "tool_name": self.tool_name,
            "source": self.source,
            "agent_type": self.agent_type,
            "decision": self.decision,
            "reason": self.reason,
            "rule_scope": self.rule_scope,
            "rule_behavior": self.rule_behavior,
            "audit_data": dict(self.audit_data),
        }


class PermissionDecisionError(RuntimeError):
    def __init__(self, decision: PermissionDecision):
        self.decision = decision
        super().__init__(decision.reason)


def build_runtime_allow_rule(
    operation: PermissionOperation,
    *,
    description: str = "Explicit user approval provided.",
    tool_name: str | None = None,
    source: str | None = None,
) -> PermissionRule:
    return PermissionRule(
        scope="runtime_override",
        behavior="allow",
        operation=operation,
        tool_name=tool_name,
        source=source,
        description=description,
    )


def build_runtime_allow_rules(
    *operations: PermissionOperation,
    description: str = "Explicit user approval provided.",
) -> list[PermissionRule]:
    return [
        build_runtime_allow_rule(operation, description=description)
        for operation in operations
    ]


async def _default_audit_logger(record: PermissionAuditRecord) -> None:
    from data import db

    await db.log_permission_audit(record.to_dict())


def _default_global_rules() -> list[PermissionRule]:
    return [
        PermissionRule(
            scope="global",
            behavior="ask",
            operation=operation,
            description=f"The '{operation}' operation requires explicit approval.",
        )
        for operation in RISKY_PERMISSION_OPERATIONS
    ]


def _default_project_rules(config: AppConfig) -> list[PermissionRule]:
    return []


def _default_reason(
    behavior: PermissionBehavior,
    request: PermissionRequest,
    matched_rule: PermissionRule | None,
) -> str:
    if matched_rule and matched_rule.description:
        return matched_rule.description
    if behavior == "allow":
        return f"The '{request.operation}' operation is allowed."
    if behavior == "ask":
        return f"The '{request.operation}' operation requires explicit approval before execution."
    return f"The '{request.operation}' operation is denied by the active permission policy."


class PermissionEngine:
    """Evaluate risky operations across layered approval rules.

    Resolution order is applied as:
    global -> project -> session -> runtime_override

    The last matching rule wins. This lets more specific layers override more
    general defaults while keeping the precedence explicit and testable.
    """

    def __init__(
        self,
        *,
        global_rules: Iterable[PermissionRule] | None = None,
        project_rules: Iterable[PermissionRule] | None = None,
        session_rules: Iterable[PermissionRule] | None = None,
        audit_logger: PermissionAuditLogger | None = None,
    ) -> None:
        self._global_rules = tuple(global_rules or ())
        self._project_rules = tuple(project_rules or ())
        self._session_rules = tuple(session_rules or ())
        self._audit_logger = audit_logger or _default_audit_logger

    async def evaluate(
        self,
        request: PermissionRequest,
        *,
        session_rules: Iterable[PermissionRule] | None = None,
        runtime_rules: Iterable[PermissionRule] | None = None,
    ) -> PermissionDecision:
        layer_rules: dict[PermissionScope, tuple[PermissionRule, ...]] = {
            "global": self._global_rules,
            "project": self._project_rules,
            "session": tuple([*self._session_rules, *(session_rules or ())]),
            "runtime_override": tuple(runtime_rules or ()),
        }

        matched_rule: PermissionRule | None = None
        resolution_trace: list[dict[str, Any]] = []
        for scope in RULE_RESOLUTION_ORDER:
            for rule in layer_rules[scope]:
                if not rule.matches(request):
                    continue
                matched_rule = rule
                resolution_trace.append({
                    "scope": scope,
                    "behavior": rule.behavior,
                    "operation": rule.operation,
                    "tool_name": rule.tool_name,
                    "source": rule.source,
                })

        if matched_rule is None:
            matched_rule = PermissionRule(
                scope="global",
                behavior="deny",
                operation=request.operation,
                description="No permission rule matched the requested operation.",
            )

        decision = PermissionDecision(
            behavior=matched_rule.behavior,
            request=request,
            matched_rule=matched_rule,
            resolution_trace=resolution_trace,
            reason=_default_reason(matched_rule.behavior, request, matched_rule),
        )

        if decision.requires_approval:
            await self._audit_logger(PermissionAuditRecord.from_decision(decision))

        return decision

    async def ensure_allowed(
        self,
        request: PermissionRequest,
        *,
        session_rules: Iterable[PermissionRule] | None = None,
        runtime_rules: Iterable[PermissionRule] | None = None,
    ) -> PermissionDecision:
        decision = await self.evaluate(
            request,
            session_rules=session_rules,
            runtime_rules=runtime_rules,
        )
        if not decision.allowed:
            raise PermissionDecisionError(decision)
        return decision


def create_permission_engine(
    config: AppConfig | None = None,
    *,
    global_rules: Iterable[PermissionRule] | None = None,
    project_rules: Iterable[PermissionRule] | None = None,
    session_rules: Iterable[PermissionRule] | None = None,
    audit_logger: PermissionAuditLogger | None = None,
) -> PermissionEngine:
    app_config = config or AppConfig()
    return PermissionEngine(
        global_rules=global_rules or _default_global_rules(),
        project_rules=project_rules or _default_project_rules(app_config),
        session_rules=session_rules,
        audit_logger=audit_logger,
    )


__all__ = [
    "PermissionAuditRecord",
    "PermissionBehavior",
    "PermissionDecision",
    "PermissionDecisionError",
    "PermissionEngine",
    "PermissionOperation",
    "PermissionRequest",
    "PermissionRule",
    "PermissionScope",
    "RULE_RESOLUTION_ORDER",
    "RISKY_PERMISSION_OPERATIONS",
    "build_runtime_allow_rule",
    "build_runtime_allow_rules",
    "create_permission_engine",
]
