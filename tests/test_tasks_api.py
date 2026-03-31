import asyncio
import json

import data.db as db
from api.main import app
from fastapi.testclient import TestClient


def test_tasks_api_lists_and_stops_batch_task(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_tasks_api.db")
    asyncio.run(db.init_db())
    asyncio.run(
        db.create_batch_job(
            "batch-task-1",
            json.dumps({"target_fields": ["name"]}),
            task_payload={
                "config": {"target_fields": ["name"]},
                "product_ids": ["prod-1", "prod-2"],
                "stage": "analysis",
            },
        )
    )
    asyncio.run(db.update_batch_job("batch-task-1", status="analyzing", total_count=2, processed_count=1))

    with TestClient(app) as client:
        list_response = client.get("/api/tasks")
        get_response = client.get("/api/tasks/batch-task-1")
        stop_response = client.post("/api/tasks/batch-task-1/stop")

    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert any(item["id"] == "batch-task-1" for item in items)

    assert get_response.status_code == 200
    assert get_response.json()["progress"] == 50

    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "cancelled"
