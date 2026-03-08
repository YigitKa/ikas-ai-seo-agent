from typing import Optional

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
