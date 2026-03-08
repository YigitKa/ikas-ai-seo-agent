from core.models import Product
from core.suggestion_service import (
    apply_suggestion_field,
    create_pending_suggestion,
    sync_suggestion_fields,
)


def _build_product() -> Product:
    return Product(
        id="p1",
        name="Orijinal Ad",
        description="<p>TR</p>",
        description_translations={"en": "<p>EN</p>"},
        meta_title="Meta",
        meta_description="Meta desc",
    )


def test_create_pending_suggestion_uses_product_source_fields():
    suggestion = create_pending_suggestion(_build_product())

    assert suggestion.product_id == "p1"
    assert suggestion.original_name == "Orijinal Ad"
    assert suggestion.original_description == "<p>TR</p>"
    assert suggestion.original_description_en == "<p>EN</p>"
    assert suggestion.original_meta_title == "Meta"
    assert suggestion.original_meta_description == "Meta desc"
    assert suggestion.status == "pending"


def test_sync_suggestion_fields_normalizes_placeholder_values():
    suggestion = create_pending_suggestion(_build_product())
    apply_suggestion_field(suggestion, "name", "Yeni Ad")
    sync_suggestion_fields(
        suggestion,
        {
            "meta_title": "Yeni Meta",
            "meta_desc": "AI ile yeniden yazma icin butonu kullanin",
            "desc_tr": "<p>Yeni TR</p>",
            "desc_en": "<p>New EN</p>",
        },
    )

    assert suggestion.suggested_name == "Yeni Ad"
    assert suggestion.suggested_meta_title == "Yeni Meta"
    assert suggestion.suggested_meta_description == ""
    assert suggestion.suggested_description == "<p>Yeni TR</p>"
    assert suggestion.suggested_description_en == "<p>New EN</p>"
