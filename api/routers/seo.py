"""SEO analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_manager
from api.schemas import MessageResponse, ProductWithScore, ScoreResponse
from core.product_manager import ProductManager
from data import db

router = APIRouter()


@router.post("/analyze", response_model=MessageResponse)
async def analyze_all(
    manager: ProductManager = Depends(get_manager),
) -> MessageResponse:
    """Score all cached products."""
    products = await manager.get_cached_products()
    if not products:
        raise HTTPException(status_code=400, detail="No products cached. Fetch first.")

    scored = await manager.score_products(products)
    return MessageResponse(message=f"Analyzed {len(scored)} products")


@router.post("/analyze/{product_id}", response_model=ScoreResponse)
async def analyze_one(
    product_id: str,
    manager: ProductManager = Depends(get_manager),
) -> ScoreResponse:
    """Score a single product."""
    product = await db.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    score = await manager.analyze_product(product)
    return ScoreResponse(product_id=product_id, score=score)


@router.get("/scores/{product_id}", response_model=ScoreResponse)
async def get_score(
    product_id: str,
) -> ScoreResponse:
    """Get the latest SEO score for a product."""
    score = await db.get_latest_score(product_id)
    if not score:
        raise HTTPException(status_code=404, detail="No score found")
    return ScoreResponse(product_id=product_id, score=score)
