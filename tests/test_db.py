import asyncio
import json

import data.db as db
from core.models import Product
from core.models import SeoSuggestion


def test_suggestion_status_helpers(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test.db")
    asyncio.run(db.init_db())

    pending = SeoSuggestion(
        product_id="prod_pending",
        original_name="Pending Product",
        original_description="Pending description",
    )
    approved = SeoSuggestion(
        product_id="prod_approved",
        original_name="Approved Product",
        original_description="Approved description",
    )

    asyncio.run(db.save_suggestion(pending))
    asyncio.run(db.save_suggestion(approved))
    asyncio.run(db.update_suggestion_status("prod_approved", "approved"))

    assert asyncio.run(db.count_suggestions("pending")) == 1
    assert asyncio.run(db.count_suggestions("approved")) == 1
    assert asyncio.run(db.get_suggestion_product_ids("pending")) == {"prod_pending"}
    assert asyncio.run(db.get_suggestion_product_ids("approved")) == {"prod_approved"}
    latest_approved = asyncio.run(db.get_latest_suggestion_by_product("prod_approved"))
    approved_items = asyncio.run(db.get_approved_suggestions())

    assert latest_approved is not None
    assert latest_approved.product_id == "prod_approved"
    assert latest_approved.status == "approved"
    assert approved_items[0].product_id == "prod_approved"
    assert approved_items[0].status == "approved"


def test_update_latest_pending_suggestion(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_update.db")
    asyncio.run(db.init_db())

    first = SeoSuggestion(
        product_id="prod_edit",
        original_name="Editable Product",
        original_description="Original description",
        suggested_description="<p>Ilk surum</p>",
    )
    second = SeoSuggestion(
        product_id="prod_edit",
        original_name="Editable Product",
        original_description="Original description",
        suggested_description="<p>Ikinci surum</p>",
    )

    asyncio.run(db.save_suggestion(first))
    asyncio.run(db.save_suggestion(second))

    edited = second.model_copy(update={"suggested_description": "<p>Kaydedilen yeni surum</p>"})
    asyncio.run(db.update_latest_pending_suggestion(edited))

    latest = asyncio.run(db.get_latest_suggestion_by_product("prod_edit"))
    assert latest is not None
    assert latest.suggested_description == "<p>Kaydedilen yeni surum</p>"


def test_clear_all_data(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_clear.db")
    asyncio.run(db.init_db())

    asyncio.run(db.save_product(Product(id="prod-1", name="Test Product")))
    asyncio.run(db.log_operation("fetch", "prod-1", {"ok": True}, True))
    suggestion = SeoSuggestion(
        product_id="prod-1",
        original_name="Test Product",
        original_description="Original description",
    )
    asyncio.run(db.save_suggestion(suggestion))

    counts = asyncio.run(db.clear_all_data())

    assert counts["products"] == 1
    assert counts["suggestions"] == 1
    assert counts["operation_log"] == 1
    assert asyncio.run(db.get_all_products()) == []
    assert asyncio.run(db.get_pending_suggestions()) == []
    assert asyncio.run(db.get_operation_history()) == []


def test_llms_jobs_sync_into_unified_tasks(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_tasks_llms.db")
    asyncio.run(db.init_db())

    job = asyncio.run(db.create_llms_job(["prod-1", "prod-2"], options={"reason": "test"}))
    task = asyncio.run(db.get_task(job.id))

    assert task is not None
    assert task.type == "llms_generation"
    assert task.status == "queued"
    assert task.payload["product_ids"] == ["prod-1", "prod-2"]
    assert task.payload["reason"] == "test"

    entry = asyncio.run(db.claim_next_llms_entry(job.id))
    assert entry is not None
    asyncio.run(db.save_llms_entry_success(entry.id, "Summary"))
    asyncio.run(db.refresh_llms_job_counters(job.id))

    task = asyncio.run(db.get_task(job.id))
    assert task is not None
    assert task.progress == 50
    assert task.result["processed_count"] == 1


def test_batch_jobs_sync_into_unified_tasks_without_losing_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_tasks_batch.db")
    asyncio.run(db.init_db())

    asyncio.run(
        db.create_batch_job(
            "batch-job-1",
            json.dumps({"target_fields": ["name"]}),
            task_payload={
                "config": {"target_fields": ["name"]},
                "product_ids": ["prod-1", "prod-2"],
                "stage": "analysis",
            },
        )
    )
    asyncio.run(db.update_batch_job("batch-job-1", status="analyzing", total_count=2, processed_count=1))

    task = asyncio.run(db.get_task("batch-job-1"))
    assert task is not None
    assert task.type == "batch_job"
    assert task.progress == 50
    assert task.payload["product_ids"] == ["prod-1", "prod-2"]
    assert task.payload["stage"] == "analysis"

    asyncio.run(db.patch_task_payload("batch-job-1", {"stage": "apply"}))
    asyncio.run(db.update_batch_job("batch-job-1", status="running", total_count=2, processed_count=1))

    task = asyncio.run(db.get_task("batch-job-1"))
    assert task is not None
    assert task.payload["stage"] == "apply"
    assert task.result["processed_count"] == 1
