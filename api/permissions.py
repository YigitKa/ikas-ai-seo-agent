"""FastAPI helpers for permission-engine failures."""

from __future__ import annotations

from fastapi import HTTPException

from core.permissions import PermissionDecisionError


def raise_http_for_permission(error: PermissionDecisionError) -> None:
    raise HTTPException(
        status_code=error.decision.http_status_code,
        detail=error.decision.to_dict(),
    ) from error
