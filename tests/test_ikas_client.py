import json
from pathlib import Path

from core.models import Product

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_product_from_fixture():
    """Test that fixture data can be parsed into Product models."""
    data = json.loads((FIXTURES_DIR / "sample_products.json").read_text())

    for item in data:
        meta = item.get("metaData") or {}
        variants = item.get("productVariants") or []
        categories = item.get("categories") or []

        product = Product(
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
        )

        assert product.id
        assert isinstance(product.tags, list)


def test_product_model_defaults():
    p = Product(id="test", name="Test Product")
    assert p.description == ""
    assert p.tags == []
    assert p.status == "active"
    assert p.meta_title is None


def test_product_model_full():
    p = Product(
        id="full",
        name="Full Product",
        description="A full product",
        meta_title="Full - Brand",
        meta_description="Buy Full Product now",
        tags=["tag1", "tag2"],
        category="Test Category",
        price=99.99,
        sku="FP-001",
        status="passive",
    )
    assert p.price == 99.99
    assert p.sku == "FP-001"
    assert len(p.tags) == 2
