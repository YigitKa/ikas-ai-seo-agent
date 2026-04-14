"""Product endpoints — fetch, list, detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_manager
from api.permissions import raise_http_for_permission
from api.schemas import (
    FetchProductsRequest,
    LocalDataResetResponse,
    ProductListResponse,
    ProductSyncResponse,
    ProductWithScore,
)
from core.models import Product, SeoScore
from core.permissions import PermissionDecisionError, build_runtime_allow_rule
from core.product_manager import ProductManager
from core.seo.analyzer import analyze_product
from core.utils.html import html_to_plain_text
from core.utils.presentation import get_en_description_value
from data import db

router = APIRouter()

FIELD_SCORE_FILTERS: dict[str, tuple[int, str]] = {
    "title_score_threshold": (15, "title_score"),
    "description_score_threshold": (20, "description_score"),
    "english_description_score_threshold": (5, "english_description_score"),
    "meta_score_threshold": (15, "meta_score"),
    "meta_desc_score_threshold": (10, "meta_desc_score"),
    "seo_score_threshold": (100, "seo_score"),
    "geo_score_threshold": (100, "geo_score"),
    "aeo_score_threshold": (100, "aeo_score"),
}

SORTABLE_FIELDS = {
    "name",
    "category",
    "sku",
    "has_english_description",
    "total_score",
    "seo_score",
    "geo_score",
    "aeo_score",
    "title_score",
    "description_score",
    "english_description_score",
    "meta_score",
    "meta_desc_score",
}


def _normalize_score(raw_value: int, max_score: int) -> int:
    if max_score <= 0:
        return 0
    normalized = round((max(0, raw_value) / max_score) * 100)
    return max(0, min(100, normalized))


def _normalized_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _has_english_description(description_translations: dict[str, str] | None) -> bool:
    return bool(
        html_to_plain_text(
            get_en_description_value(description_translations),
            preserve_breaks=False,
        )
    )


def _get_sort_value(item: tuple[Product, SeoScore], sort_by: str) -> str | int:
    product, score = item
    if sort_by == "name":
        return _normalized_text(product.name)
    if sort_by == "category":
        return _normalized_text(product.category)
    if sort_by == "sku":
        return _normalized_text(product.sku)
    if sort_by == "has_english_description":
        return 1 if _has_english_description(product.description_translations) else 0
    return int(getattr(score, sort_by, 0))


def _sort_scored_products(
    items: list[tuple[Product, SeoScore]],
    sort_by: str,
    sort_dir: str,
) -> list[tuple[Product, SeoScore]]:
    if sort_by not in SORTABLE_FIELDS:
        return items

    sorted_items = sorted(items, key=lambda item: _normalized_text(item[0].name))
    sorted_items = sorted(
        sorted_items,
        key=lambda item: _get_sort_value(item, sort_by),
        reverse=sort_dir == "desc",
    )

    if sort_by in {"category", "sku"}:
        sorted_items = sorted(sorted_items, key=lambda item: _get_sort_value(item, sort_by) == "")

    return sorted_items


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    filter: str = Query("all", pattern="^(all|low_score|missing_english|pending|approved)$"),
    search: str = Query(""),
    category: str = Query(""),
    score_threshold: int = Query(100, ge=0, le=100),
    seo_score_threshold: int = Query(100, ge=0, le=100),
    geo_score_threshold: int = Query(100, ge=0, le=100),
    aeo_score_threshold: int = Query(100, ge=0, le=100),
    title_score_threshold: int = Query(100, ge=0, le=100),
    description_score_threshold: int = Query(100, ge=0, le=100),
    english_description_score_threshold: int = Query(100, ge=0, le=100),
    meta_score_threshold: int = Query(100, ge=0, le=100),
    meta_desc_score_threshold: int = Query(100, ge=0, le=100),
    sort_by: str = Query(
        "name",
        pattern="^(name|category|sku|has_english_description|total_score|seo_score|geo_score|aeo_score|title_score|description_score|english_description_score|meta_score|meta_desc_score)$",
    ),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    manager: ProductManager = Depends(get_manager),
) -> ProductListResponse:
    """Return cached products with their latest scores."""
    products = await manager.get_cached_products()
    if not products:
        scored: list[tuple[Product, SeoScore]] = []
    else:
        product_ids = [p.id for p in products]
        cached_scores = await db.get_latest_scores_for_products(product_ids)

        scored = []
        unscored: list[Product] = []
        for p in products:
            existing = cached_scores.get(p.id)
            if existing:
                scored.append((p, existing))
            else:
                unscored.append(p)

        if unscored:
            newly_scored = await manager.score_products(unscored)
            scored.extend(newly_scored)

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

    search_query = search.strip().lower()
    if search_query:
        scored = [(p, s) for p, s in scored if search_query in p.name.lower()]

    category_query = category.strip().lower()
    if category_query:
        scored = [(p, s) for p, s in scored if category_query in (p.category or "").lower()]

    if score_threshold < 100:
        scored = [(p, s) for p, s in scored if s.total_score < score_threshold]

    field_thresholds = {
        "seo_score_threshold": seo_score_threshold,
        "geo_score_threshold": geo_score_threshold,
        "aeo_score_threshold": aeo_score_threshold,
        "title_score_threshold": title_score_threshold,
        "description_score_threshold": description_score_threshold,
        "english_description_score_threshold": english_description_score_threshold,
        "meta_score_threshold": meta_score_threshold,
        "meta_desc_score_threshold": meta_desc_score_threshold,
    }
    for threshold_key, threshold_value in field_thresholds.items():
        if threshold_value >= 100:
            continue

        max_score, score_attr = FIELD_SCORE_FILTERS[threshold_key]
        scored = [
            (product, score)
            for product, score in scored
            if _normalize_score(getattr(score, score_attr, 0), max_score) < threshold_value
        ]

    scored = _sort_scored_products(scored, sort_by, sort_dir)

    total = len(scored)
    start = (page - 1) * limit
    page_items = scored[start : start + limit]

    return ProductListResponse(
        items=[ProductWithScore(product=p, score=s) for p, s in page_items],
        total_count=total,
        page=page,
        limit=limit,
    )


@router.get("/categories")
async def list_categories() -> list[str]:
    """Return distinct category names from cached products."""
    products = await db.get_all_products()
    cats = sorted({p.category for p in products if p.category})
    return cats


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
    try:
        counts = await manager.clear_local_data(
            permission_rules=[
                build_runtime_allow_rule(
                    "db_reset",
                    description="The reset endpoint was invoked explicitly by the user.",
                )
            ]
        )
    except PermissionDecisionError as exc:
        raise_http_for_permission(exc)
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
