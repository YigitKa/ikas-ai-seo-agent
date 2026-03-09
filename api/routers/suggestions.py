"""AI suggestion endpoints — generate, approve, reject, apply."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_manager
from api.schemas import (
    ApplyResponse,
    FieldRewriteRequest,
    MessageResponse,
    RewriteResponse,
    SuggestionActionRequest,
    SuggestionUpdateRequest,
)
from core.models import SeoSuggestion
from core.product_manager import ProductManager
from core.suggestion_service import apply_suggestion_field
from data import db

router = APIRouter()


@router.post("/generate/{product_id}", response_model=RewriteResponse)
async def generate_suggestion(
    product_id: str,
    manager: ProductManager = Depends(get_manager),
) -> RewriteResponse:
    """Generate a full AI rewrite for a product."""
    product = await db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    score = await db.get_latest_score(product_id)
    if not score:
        score = await manager.analyze_product(product)

    suggestion = await manager.rewrite_product(product, score)
    return RewriteResponse(
        suggestion=suggestion,
        thinking_text=suggestion.thinking_text,
    )


@router.post("/generate-field/{product_id}", response_model=RewriteResponse)
async def generate_field_rewrite(
    product_id: str,
    body: FieldRewriteRequest,
    manager: ProductManager = Depends(get_manager),
) -> RewriteResponse:
    """Rewrite a single field (name, desc_tr, meta_title, meta_desc, desc_en)."""
    product = await db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    score = await db.get_latest_score(product_id)
    if not score:
        score = await manager.analyze_product(product)

    if body.field == "desc_en":
        value, thinking = manager.translate_description_to_en(product)
    else:
        value, thinking = manager.rewrite_field(body.field, product, score)

    return RewriteResponse(field_value=value, thinking_text=thinking)


@router.get("/{product_id}", response_model=list[SeoSuggestion])
async def get_suggestions(product_id: str) -> list[SeoSuggestion]:
    """Get all suggestions for a product."""
    return await db.get_suggestions_by_product(product_id)


@router.patch("/{product_id}/approve", response_model=MessageResponse)
async def approve_suggestion(
    product_id: str,
    manager: ProductManager = Depends(get_manager),
) -> MessageResponse:
    """Approve the pending suggestion for a product."""
    await manager.approve_suggestion(product_id)
    return MessageResponse(message=f"Suggestion for {product_id} approved")


@router.patch("/{product_id}/reject", response_model=MessageResponse)
async def reject_suggestion(
    product_id: str,
    manager: ProductManager = Depends(get_manager),
) -> MessageResponse:
    """Reject the pending suggestion for a product."""
    await manager.reject_suggestion(product_id)
    return MessageResponse(message=f"Suggestion for {product_id} rejected")


@router.patch("/{product_id}/update", response_model=MessageResponse)
async def update_suggestion_fields(
    product_id: str,
    body: SuggestionUpdateRequest,
    manager: ProductManager = Depends(get_manager),
) -> MessageResponse:
    """Update individual fields on the latest pending suggestion."""
    suggestion = await manager.get_latest_suggestion(product_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="No pending suggestion found")

    for field_update in body.fields:
        apply_suggestion_field(suggestion, field_update.field, field_update.value)

    await manager.save_or_update_pending_suggestion(suggestion)
    return MessageResponse(message="Suggestion fields updated")


@router.post("/apply", response_model=ApplyResponse)
async def apply_approved(
    manager: ProductManager = Depends(get_manager),
) -> ApplyResponse:
    """Apply all approved suggestions to ikas."""
    approved = await manager.get_approved_suggestions()
    if not approved:
        return ApplyResponse(applied=0, total=0)

    applied = await manager.apply_suggestions(approved)
    return ApplyResponse(applied=applied, total=len(approved))
