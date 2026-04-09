from typing import Optional
from datetime import datetime

import pytest

from core.permissions import create_permission_engine
import core.skills.store as skill_store
from core.models import Product
from core.product_manager import ProductManager


def _build_product(product_id: str, *, en_description: Optional[str] = None) -> Product:
    translations = {"tr": "<p>Turkce aciklama</p>"}
    if en_description is not None:
        translations["en"] = en_description
    return Product(
        id=product_id,
        name=f"Product {product_id}",
        description="<p>Turkce aciklama</p>",
        description_translations=translations,
    )


def test_filter_products_missing_english_translation_treats_empty_html_as_missing():
    manager = ProductManager.__new__(ProductManager)
    products = [
        (_build_product("missing"), "score-missing"),
        (_build_product("html-only", en_description="<p> </p>"), "score-html"),
        (_build_product("has-en", en_description="<p>English description</p>"), "score-en"),
    ]

    filtered = manager.filter_products_missing_english_translation(products)

    assert [product.id for product, _ in filtered] == ["missing", "html-only"]


def test_stream_chat_message_returns_chat_stream_directly():
    manager = ProductManager.__new__(ProductManager)

    class _FakeChat:
        def __init__(self):
            self.calls = []
            self.stream = object()

        def stream_message(self, message: str):
            self.calls.append(message)
            return self.stream

    manager._chat = _FakeChat()

    result = manager.stream_chat_message("merhaba")

    assert result is manager._chat.stream
    assert manager._chat.calls == ["merhaba"]


def test_estimate_batch_eta_seconds_handles_naive_started_at():
    manager = ProductManager.__new__(ProductManager)

    eta = manager._estimate_batch_eta_seconds(
        started_at=datetime.now(),
        summary_counts={"processed": 1, "remaining": 2},
        stage="analyzing",
    )

    assert isinstance(eta, int)
    assert eta >= 1


def _use_temp_skills(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(skill_store, "SKILLS_DIR", tmp_path / "skills")
    skill_store._skill_cache.clear()
    skill_store.ensure_skill_files()


def _make_manager() -> ProductManager:
    manager = ProductManager.__new__(ProductManager)
    manager._permission_engine = create_permission_engine()
    return manager


def test_validate_skill_for_flow_rejects_skill_without_batch_support(monkeypatch, tmp_path):
    _use_temp_skills(monkeypatch, tmp_path)
    manager = _make_manager()

    with pytest.raises(ValueError, match="batch akisi"):
        manager.validate_skill_for_flow("category-audit", "batch")


def test_build_batch_runtime_prompt_includes_selected_skill(monkeypatch, tmp_path):
    _use_temp_skills(monkeypatch, tmp_path)
    manager = _make_manager()

    prompt = manager._build_batch_runtime_prompt({
        "preserve_specs": True,
        "prevent_cannibalization": True,
        "max_title_change_pct": 25,
        "target_fields": ["name", "meta_title"],
        "skill_slug": "brand-voice-rewrite",
    })

    assert "BATCH KISITLARI" in prompt
    assert "Aktif skill: Brand Voice Rewrite" in prompt


def test_resolve_runtime_skill_selection_routes_brand_voice(monkeypatch, tmp_path):
    _use_temp_skills(monkeypatch, tmp_path)
    manager = _make_manager()

    selection = manager._resolve_runtime_skill_selection(
        "",
        "rewrite",
        routing_text="marka tonu daha kontrollu ve rewrite odakli olsun",
        enable_routing=True,
        enable_default_fallback=False,
    )

    assert selection.primary_skill is not None
    assert selection.primary_skill.slug == "brand-voice-rewrite"
    assert selection.selection_mode == "routed"
