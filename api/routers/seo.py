"""SEO analysis endpoints."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from api.dependencies import get_manager
from api.schemas import MessageResponse, ProductWithScore, ScoreResponse
from config.settings import get_config
from core.html_utils import html_to_plain_text
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


@router.get("/generate-llms-txt", response_class=PlainTextResponse)
async def generate_llms_txt() -> str:
    """Generate a llms.txt file for the store, grouped by category."""
    config = get_config()
    store_name = config.ikas_store_name or "Magaza"

    products = await db.get_all_products()

    by_category: dict[str, list] = defaultdict(list)
    for product in products:
        category = product.category or "Genel"
        by_category[category].append(product)

    lines: list[str] = [
        f"# {store_name}",
        "> Bu dosya yapay zeka asistanlari icin optimize edilmistir.",
        "",
        "## Kategoriler ve Urunler",
    ]

    for category in sorted(by_category.keys()):
        lines.append(f"\n### {category}")
        for product in by_category[category]:
            plain_desc = html_to_plain_text(product.description).strip()
            short_desc = plain_desc[:100] if plain_desc else ""
            price_str = f"{product.price:.2f} TL" if product.price is not None else ""
            entry = f"- {product.name}"
            if short_desc:
                entry += f": {short_desc}"
            if price_str:
                entry += f" - {price_str}"
            lines.append(entry)

    return "\n".join(lines) + "\n"
