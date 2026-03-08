import data.db as db
from core.models import Product
from core.models import SeoSuggestion


def test_suggestion_status_helpers(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test.db")
    db.init_db()

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

    db.save_suggestion(pending)
    db.save_suggestion(approved)
    db.update_suggestion_status("prod_approved", "approved")

    assert db.count_suggestions("pending") == 1
    assert db.count_suggestions("approved") == 1
    assert db.get_suggestion_product_ids("pending") == {"prod_pending"}
    assert db.get_suggestion_product_ids("approved") == {"prod_approved"}
    assert db.get_latest_suggestion_by_product("prod_approved").product_id == "prod_approved"
    assert db.get_approved_suggestions()[0].product_id == "prod_approved"


def test_update_latest_pending_suggestion(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_update.db")
    db.init_db()

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

    db.save_suggestion(first)
    db.save_suggestion(second)

    edited = second.model_copy(update={"suggested_description": "<p>Kaydedilen yeni surum</p>"})
    db.update_latest_pending_suggestion(edited)

    latest = db.get_latest_suggestion_by_product("prod_edit")
    assert latest is not None
    assert latest.suggested_description == "<p>Kaydedilen yeni surum</p>"


def test_clear_all_data(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "seo_test_clear.db")
    db.init_db()

    db.save_product(Product(id="prod-1", name="Test Product"))
    db.log_operation("fetch", "prod-1", {"ok": True}, True)
    suggestion = SeoSuggestion(
        product_id="prod-1",
        original_name="Test Product",
        original_description="Original description",
    )
    db.save_suggestion(suggestion)

    counts = db.clear_all_data()

    assert counts["products"] == 1
    assert counts["suggestions"] == 1
    assert counts["operation_log"] == 1
    assert db.get_all_products() == []
    assert db.get_pending_suggestions() == []
    assert db.get_operation_history() == []
