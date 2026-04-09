from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies import get_manager
from api.schemas import DiagnosticsSummaryResponse
from core.product_manager import ProductManager
from core.services.diagnostics import build_diagnostics_summary

router = APIRouter()


@router.get("/summary", response_model=DiagnosticsSummaryResponse)
async def get_diagnostics_summary(
    manager: ProductManager = Depends(get_manager),
) -> DiagnosticsSummaryResponse:
    payload = await build_diagnostics_summary(manager)
    return DiagnosticsSummaryResponse(**payload)
