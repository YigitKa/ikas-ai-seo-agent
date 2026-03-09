from fastapi.testclient import TestClient

from api.dependencies import get_manager
from api.main import app
from core.models import Product, SeoScore


def _build_product(product_id: str, *, en_description: str = "") -> Product:
    translations = {"tr": "<p>Turkce aciklama</p>"}
    if en_description:
        translations["en"] = en_description
    return Product(
        id=product_id,
        name=f"Product {product_id}",
        description="<p>Turkce aciklama</p>",
        description_translations=translations,
    )


def _build_score(product_id: str, total_score: int = 80) -> SeoScore:
    return SeoScore(
        product_id=product_id,
        total_score=total_score,
        title_score=10,
        description_score=15,
        english_description_score=2,
        meta_score=10,
        meta_desc_score=8,
        keyword_score=8,
        content_quality_score=8,
        technical_seo_score=9,
        readability_score=4,
    )


class _StubManager:
    def __init__(self) -> None:
        self._products = [
            _build_product("p-missing"),
            _build_product("p-has-en", en_description="<p>English description</p>"),
        ]
        self._scores = {
            product.id: _build_score(product.id)
            for product in self._products
        }
        self.missing_english_calls = 0

    async def get_cached_products(self):
        return self._products

    async def score_products(self, products):
        return [(product, self._scores[product.id]) for product in products]

    def filter_products_by_score(self, scored):
        return scored

    def filter_products_missing_english_translation(self, scored):
        self.missing_english_calls += 1
        return [
            (product, score)
            for product, score in scored
            if not product.description_translations.get("en", "").strip()
        ]

    async def get_suggestion_product_ids(self, status: str):
        return set()

    async def sync_all_products(self, batch_size: int = 50) -> tuple[int, int]:
        return 512, 512

    async def clear_local_data(self) -> dict[str, int]:
        return {
            "products": 512,
            "seo_scores": 512,
            "suggestions": 9,
            "operation_log": 4,
        }


def test_sync_and_reset_routes_are_not_captured_by_product_id_route():
    app.dependency_overrides[get_manager] = lambda: _StubManager()
    client = TestClient(app)

    try:
        sync_response = client.post("/api/products/sync")
        reset_response = client.post("/api/products/reset")
    finally:
        app.dependency_overrides.clear()

    assert sync_response.status_code == 200
    assert sync_response.json() == {"fetched_count": 512, "total_count": 512}

    assert reset_response.status_code == 200
    assert reset_response.json() == {
        "message": "Local product data cleared",
        "products_deleted": 512,
        "scores_deleted": 512,
        "suggestions_deleted": 9,
        "logs_deleted": 4,
    }


def test_list_products_supports_missing_english_filter():
    stub = _StubManager()
    app.dependency_overrides[get_manager] = lambda: stub
    client = TestClient(app)

    try:
        response = client.get("/api/products?filter=missing_english")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert stub.missing_english_calls == 1
    assert response.json()["total_count"] == 1
    assert [item["product"]["id"] for item in response.json()["items"]] == ["p-missing"]
