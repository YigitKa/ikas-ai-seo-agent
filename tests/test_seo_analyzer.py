import json
from pathlib import Path

from core.models import Product
from core.seo_analyzer import analyze_product, strip_html, word_count

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_sample_products() -> list[Product]:
    data = json.loads((FIXTURES_DIR / "sample_products.json").read_text())
    products = []
    for item in data:
        meta = item.get("metaData") or {}
        variants = item.get("productVariants") or []
        categories = item.get("categories") or []
        products.append(Product(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            meta_title=meta.get("title"),
            meta_description=meta.get("description"),
            tags=item.get("tags", []),
            category=categories[0]["name"] if categories else None,
            price=variants[0]["price"] if variants else None,
            sku=variants[0]["sku"] if variants else None,
            status=item.get("status", "active"),
        ))
    return products


def test_strip_html():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert strip_html("no tags here") == "no tags here"
    assert strip_html("") == ""


def test_word_count():
    assert word_count("hello world test") == 3
    assert word_count("<p>hello world</p>") == 2
    assert word_count("") == 0


def test_analyze_product_low_score():
    """Product with minimal content should get a low score."""
    products = load_sample_products()
    laptop = next(p for p in products if p.id == "prod_003")
    score = analyze_product(laptop)

    assert score.total_score < 40
    assert len(score.issues) > 0
    assert "LAPTOP CANTASI" in laptop.name


def test_analyze_product_medium_score():
    """Product with some SEO data should get a medium score."""
    products = load_sample_products()
    kolye = next(p for p in products if p.id == "prod_004")
    score = analyze_product(kolye)

    assert 30 <= score.total_score <= 80
    assert score.meta_score > 0


def test_analyze_product_high_score():
    """Product with good SEO data should get a higher score."""
    products = load_sample_products()
    tshirt = next(p for p in products if p.id == "prod_002")
    score = analyze_product(tshirt)

    assert score.total_score > 40
    assert score.meta_score > 0
    assert score.meta_desc_score > 0


def test_analyze_empty_product():
    product = Product(id="empty", name="", description="")
    score = analyze_product(product)
    assert score.total_score <= 10
    assert score.title_score == 0
    assert score.description_score == 0
    assert score.meta_score == 0
    assert score.meta_desc_score == 0
    assert len(score.issues) > 0


def test_keyword_analysis():
    products = load_sample_products()
    kupa = next(p for p in products if p.id == "prod_001")
    score = analyze_product(kupa, target_keywords=["seramik", "kupa"])

    assert score.keyword_score >= 0
    assert score.product_id == "prod_001"


def test_needs_optimization():
    product = Product(id="low", name="x", description="y")
    score = analyze_product(product)
    assert score.needs_optimization is True
