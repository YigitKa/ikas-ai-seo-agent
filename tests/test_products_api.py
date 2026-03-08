from fastapi.testclient import TestClient

from api.dependencies import get_manager
from api.main import app


class _StubManager:
    async def sync_all_products(self, batch_size: int = 50) -> tuple[int, int]:
        return 512, 512

    def clear_local_data(self) -> dict[str, int]:
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
