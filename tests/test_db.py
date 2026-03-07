import data.db as db
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
