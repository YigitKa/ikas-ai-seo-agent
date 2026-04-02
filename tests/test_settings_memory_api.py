import asyncio
from datetime import datetime

import data.db as db
from api.routers import settings
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_settings_memory_api_supports_crud(monkeypatch, tmp_path):
    asyncio.run(db.close_pool())
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_settings_memory.db")
    asyncio.run(db.init_db())

    try:
        app = FastAPI()
        app.include_router(settings.router, prefix="/api/settings")

        now = datetime.now().isoformat()
        payload = {
            "id": "memory-api-1",
            "memory_type": "forbidden_claim",
            "title": "Yasak claim",
            "content": "Doktor onayi olmadan tedavi eder gibi ifadeler kullanma.",
            "summary": "Tedavi eder gibi claim'ler yasak.",
            "category": "Takviye",
            "source": "manual",
            "enabled": True,
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }

        with TestClient(app) as client:
            save_response = client.put("/api/settings/memory/memory-api-1", json={"memory": payload})
            list_response = client.get("/api/settings/memory")
            get_response = client.get("/api/settings/memory/memory-api-1")
            delete_response = client.delete("/api/settings/memory/memory-api-1")
            missing_response = client.get("/api/settings/memory/memory-api-1")

        assert save_response.status_code == 200
        assert save_response.json()["memory_type"] == "forbidden_claim"

        assert list_response.status_code == 200
        assert any(item["id"] == "memory-api-1" for item in list_response.json()["items"])

        assert get_response.status_code == 200
        assert get_response.json()["title"] == "Yasak claim"

        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Store memory silindi"

        assert missing_response.status_code == 404
    finally:
        asyncio.run(db.close_pool())
