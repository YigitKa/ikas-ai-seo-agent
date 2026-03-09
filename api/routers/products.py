"""Product endpoints — fetch, list, detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_manager
from api.schemas import (
    FetchProductsRequest,
    LocalDataResetResponse,
    ProductListResponse,
    ProductSyncResponse,
    ProductWithScore,
)
from core.product_manager import ProductManager
from data import db

router = APIRouter()


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    filter: str = Query("all", pattern="^(all|low_score|missing_english|pending|approved)$"),
    manager: ProductManager = Depends(get_manager),
) -> ProductListResponse:
    """Return cached products with their latest scores."""
    products = await manager.get_cached_products()
    scored = await manager.score_products(products) if products else []

    if filter == "low_score":
        scored = manager.filter_products_by_score(scored)
    elif filter == "missing_english":
        scored = manager.filter_products_missing_english_translation(scored)
    elif filter == "pending":
        pending_ids = await manager.get_suggestion_product_ids("pending")
        scored = [(p, s) for p, s in scored if p.id in pending_ids]
    elif filter == "approved":
        approved_ids = await manager.get_suggestion_product_ids("approved")
        scored = [(p, s) for p, s in scored if p.id in approved_ids]

    total = len(scored)
    start = (page - 1) * limit
    page_items = scored[start : start + limit]

    return ProductListResponse(
        items=[ProductWithScore(product=p, score=s) for p, s in page_items],
        total_count=total,
        page=page,
        limit=limit,
    )


@router.post("/fetch", response_model=ProductListResponse)
async def fetch_products(
    body: FetchProductsRequest,
    manager: ProductManager = Depends(get_manager),
) -> ProductListResponse:
    """Fetch products from ikas and score them."""
    scored, total_count = await manager.fetch_and_score_products(
        limit=body.limit, page=body.page,
    )

    return ProductListResponse(
        items=[ProductWithScore(product=p, score=s) for p, s in scored],
        total_count=total_count,
        page=body.page,
        limit=body.limit,
    )


@router.post("/sync", response_model=ProductSyncResponse)
async def sync_products(
    manager: ProductManager = Depends(get_manager),
) -> ProductSyncResponse:
    """Fetch the full catalog from ikas and refresh local cache."""
    fetched_count, total_count = await manager.sync_all_products()
    return ProductSyncResponse(fetched_count=fetched_count, total_count=total_count)


@router.post("/reset", response_model=LocalDataResetResponse)
async def reset_local_product_data(
    manager: ProductManager = Depends(get_manager),
) -> LocalDataResetResponse:
    """Clear local product cache, SEO scores, suggestions and logs."""
    counts = await manager.clear_local_data()
    return LocalDataResetResponse(
        message="Local product data cleared",
        products_deleted=counts["products"],
        scores_deleted=counts["seo_scores"],
        suggestions_deleted=counts["suggestions"],
        logs_deleted=counts["operation_log"],
    )


@router.get("/{product_id}", response_model=ProductWithScore)
async def get_product(
    product_id: str,
    manager: ProductManager = Depends(get_manager),
) -> ProductWithScore:
    """Get a single product with its score."""
    product = await db.get_product(product_id)
    if not product or not product.slug:
        fresh_product = await manager.fetch_product(product_id)
        if fresh_product:
            product = fresh_product
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    score = await db.get_latest_score(product_id)
    if not score:
        score = await manager.analyze_product(product)

    return ProductWithScore(product=product, score=score)
