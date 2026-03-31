"""Permission and approval engine exports."""

from core.permissions.engine import (
    PermissionAuditRecord,
    PermissionBehavior,
    PermissionDecision,
    PermissionDecisionError,
    PermissionEngine,
    PermissionOperation,
    PermissionRequest,
    PermissionRule,
    PermissionScope,
    RULE_RESOLUTION_ORDER,
    RISKY_PERMISSION_OPERATIONS,
    build_runtime_allow_rule,
    build_runtime_allow_rules,
    create_permission_engine,
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
