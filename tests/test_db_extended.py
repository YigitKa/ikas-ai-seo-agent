"""Extended tests for data/db.py — product CRUD, score persistence, operation logging."""

import asyncio
from datetime import datetime, timezone

import pytest

import data.db as db
from core.models import Product, SeoScore, SeoSuggestion


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _setup_db(monkeypatch, tmp_path, name="test.db"):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / name)
    asyncio.run(db.init_db())


def _product(pid: str, **kwargs) -> Product:
    return Product(id=pid, name=f"Product {pid}", **kwargs)


def _score(pid: str, total: int = 72) -> SeoScore:
    return SeoScore(
        product_id=pid,
        total_score=total,
        title_score=10,
        description_score=12,
        english_description_score=2,
        meta_score=9,
        meta_desc_score=7,
        keyword_score=7,
        content_quality_score=8,
        technical_seo_score=8,
        readability_score=4,
        ai_citability_score=5,
    )


# ── Product CRUD ──────────────────────────────────────────────────────────────

def test_save_and_get_product(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "prod_crud.db")

    p = _product("abc", category="Elektronik", price=199.99)
    asyncio.run(db.save_product(p))

    fetched = asyncio.run(db.get_product("abc"))
    assert fetched is not None
    assert fetched.id == "abc"
    assert fetched.category == "Elektronik"
    assert fetched.price == 199.99


def test_get_product_missing(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "prod_miss.db")
    result = asyncio.run(db.get_product("does-not-exist"))
    assert result is None


def test_save_product_overwrites_existing(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "prod_overwrite.db")

    p = _product("dup", category="Kitap")
    asyncio.run(db.save_product(p))

    p2 = _product("dup", category="Oyuncak")
    asyncio.run(db.save_product(p2))

    fetched = asyncio.run(db.get_product("dup"))
    assert fetched is not None
    assert fetched.category == "Oyuncak"


def test_get_all_products_returns_all(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "prod_all.db")

    for i in range(5):
        asyncio.run(db.save_product(_product(f"p{i}")))

    all_products = asyncio.run(db.get_all_products())
    assert len(all_products) == 5
    ids = {p.id for p in all_products}
    assert ids == {"p0", "p1", "p2", "p3", "p4"}


def test_get_all_products_empty(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "prod_empty.db")
    assert asyncio.run(db.get_all_products()) == []


def test_get_products_by_ids(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "prod_by_ids.db")

    for i in range(4):
        asyncio.run(db.save_product(_product(f"x{i}")))

    result = asyncio.run(db.get_products_by_ids(["x0", "x2"]))
    assert set(result.keys()) == {"x0", "x2"}


def test_get_products_by_ids_empty_list(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "prod_by_ids_empty.db")
    result = asyncio.run(db.get_products_by_ids([]))
    assert result == {}


# ── SEO Score persistence ──────────────────────────────────────────────────────

def test_save_and_get_latest_score(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "score.db")

    asyncio.run(db.save_product(_product("sp1")))
    s = _score("sp1", total=65)
    asyncio.run(db.save_score(s))

    latest = asyncio.run(db.get_latest_score("sp1"))
    assert latest is not None
    assert latest.total_score == 65
    assert latest.product_id == "sp1"


def test_get_latest_score_returns_most_recent(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "score_recent.db")

    asyncio.run(db.save_product(_product("sp2")))
    asyncio.run(db.save_score(_score("sp2", total=50)))
    asyncio.run(db.save_score(_score("sp2", total=80)))

    latest = asyncio.run(db.get_latest_score("sp2"))
    assert latest is not None
    assert latest.total_score == 80


def test_get_latest_score_missing_product(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "score_miss.db")
    result = asyncio.run(db.get_latest_score("nonexistent"))
    assert result is None


def test_get_latest_scores_for_products(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "scores_multi.db")

    for i in range(3):
        asyncio.run(db.save_product(_product(f"mp{i}")))
        asyncio.run(db.save_score(_score(f"mp{i}", total=60 + i * 10)))

    scores = asyncio.run(db.get_latest_scores_for_products(["mp0", "mp1", "mp2"]))
    assert scores["mp0"].total_score == 60
    assert scores["mp1"].total_score == 70
    assert scores["mp2"].total_score == 80


# ── Operation log ─────────────────────────────────────────────────────────────

def test_log_and_get_operation_history(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "oplog.db")

    asyncio.run(db.log_operation("fetch", "prod-1", {"count": 5}, True))
    asyncio.run(db.log_operation("apply", "prod-2", {"field": "title"}, False))

    history = asyncio.run(db.get_operation_history())
    assert len(history) >= 2
    ops = [h["operation"] for h in history]
    assert "fetch" in ops
    assert "apply" in ops


def test_log_operation_with_failure(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "oplog_fail.db")

    asyncio.run(db.log_operation("apply", "prod-err", {"error": "timeout"}, False))

    history = asyncio.run(db.get_operation_history())
    assert len(history) == 1
    assert not history[0]["success"]


# ── Suggestion persistence ─────────────────────────────────────────────────────

def test_save_and_get_pending_suggestions(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "sugg.db")

    sugg = SeoSuggestion(
        product_id="s-prod",
        original_name="Original",
        original_description="Old desc",
        suggested_name="Optimized Name",
    )
    asyncio.run(db.save_suggestion(sugg))

    pending = asyncio.run(db.get_pending_suggestions())
    assert len(pending) == 1
    assert pending[0].product_id == "s-prod"
    assert pending[0].suggested_name == "Optimized Name"


def test_get_approved_suggestions_empty(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "sugg_empty.db")
    assert asyncio.run(db.get_approved_suggestions()) == []


def test_update_suggestion_status(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "sugg_status.db")

    sugg = SeoSuggestion(
        product_id="s2",
        original_name="Prod",
        original_description="desc",
    )
    asyncio.run(db.save_suggestion(sugg))
    asyncio.run(db.update_suggestion_status("s2", "approved"))

    approved = asyncio.run(db.get_approved_suggestions())
    assert len(approved) == 1
    assert approved[0].status == "approved"


def test_count_suggestions_by_status(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "sugg_count.db")

    for i in range(3):
        asyncio.run(db.save_suggestion(
            SeoSuggestion(product_id=f"cp{i}", original_name="N", original_description="D")
        ))

    asyncio.run(db.update_suggestion_status("cp0", "approved"))

    assert asyncio.run(db.count_suggestions("pending")) == 2
    assert asyncio.run(db.count_suggestions("approved")) == 1


# ── Batch job operations ───────────────────────────────────────────────────────

def test_create_and_get_batch_job(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "batch.db")

    import json
    config = json.dumps({"target_fields": ["name", "meta_title"]})
    asyncio.run(db.create_batch_job(
        "job-001",
        config,
        task_payload={"config": {}, "product_ids": ["p1", "p2"], "stage": "analysis"},
    ))

    job = asyncio.run(db.get_batch_job("job-001"))
    assert job is not None
    assert job["id"] == "job-001"


def test_update_batch_job_status(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "batch_update.db")

    import json
    asyncio.run(db.create_batch_job(
        "job-002",
        json.dumps({}),
        task_payload={"config": {}, "product_ids": ["p1"], "stage": "analysis"},
    ))
    asyncio.run(db.update_batch_job("job-002", status="completed", total_count=1, processed_count=1))

    job = asyncio.run(db.get_batch_job("job-002"))
    assert job is not None
    assert job["status"] == "completed"


def test_list_batch_jobs(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "batch_list.db")

    import json
    for i in range(3):
        asyncio.run(db.create_batch_job(
            f"list-job-{i}",
            json.dumps({}),
            task_payload={"config": {}, "product_ids": [], "stage": "analysis"},
        ))

    jobs = asyncio.run(db.list_batch_jobs())
    ids = [j["id"] for j in jobs]
    assert "list-job-0" in ids
    assert "list-job-1" in ids


def test_get_batch_stats_empty(monkeypatch, tmp_path):
    _setup_db(monkeypatch, tmp_path, "batch_stats.db")
    stats = asyncio.run(db.get_batch_stats())
    assert "total_jobs" in stats
    assert stats["total_jobs"] == 0
