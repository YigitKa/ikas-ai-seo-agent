import json
from pathlib import Path

import pytest

from core.clients.ikas import IkasClient
from core.models import AppConfig, Product

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_product_from_fixture():
    """Test that fixture data can be parsed into Product models."""
    data = json.loads((FIXTURES_DIR / "sample_products.json").read_text())

    for item in data:
        meta = item.get("metaData") or {}
        variants = item.get("productVariants") or []
        categories = item.get("categories") or []

        product = Product(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            meta_title=meta.get("title"),
            meta_description=meta.get("description"),
            tags=item.get("tags", []),
            category=categories[0]["name"] if categories else None,
            price=variants[0]["price"] if variants else None,
            sku=variants[0]["sku"] if variants else None,
            status=item.get("status", "active"),
        )

        assert product.id
        assert isinstance(product.tags, list)


def test_product_model_defaults():
    p = Product(id="test", name="Test Product")
    assert p.description == ""
    assert p.tags == []
    assert p.status == "active"
    assert p.meta_title is None
    assert p.slug is None


def test_product_model_full():
    p = Product(
        id="full",
        name="Full Product",
        description="A full product",
        meta_title="Full - Brand",
        meta_description="Buy Full Product now",
        tags=["tag1", "tag2"],
        category="Test Category",
        price=99.99,
        sku="FP-001",
        status="passive",
    )
    assert p.price == 99.99
    assert p.sku == "FP-001"
    assert len(p.tags) == 2


def test_parse_product_translations(monkeypatch):
    monkeypatch.setenv("IKAS_STORE_NAME", "demo-store")
    monkeypatch.setenv("IKAS_CLIENT_ID", "demo-client")
    monkeypatch.setenv("IKAS_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-demo")
    client = IkasClient()
    parsed = client._parse_product({
        "id": "prod_tr_en",
        "name": "Test",
        "description": "Turkce aciklama",
        "descriptionTranslations": [
            {"locale": "tr", "value": "Turkce aciklama"},
            {"locale": "en", "value": "English description"},
        ],
        "metaData": {"title": None, "description": None},
        "tags": [],
        "categories": [],
        "productVariants": [],
        "status": "active",
    })

    assert parsed.description_translations.get("en") == "English description"
    assert parsed.description_translations.get("tr") == "Turkce aciklama"


def test_parse_product_translations_normalizes_regional_locales(monkeypatch):
    monkeypatch.setenv("IKAS_STORE_NAME", "demo-store")
    monkeypatch.setenv("IKAS_CLIENT_ID", "demo-client")
    monkeypatch.setenv("IKAS_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-demo")
    client = IkasClient()
    parsed = client._parse_product({
        "id": "prod_locale",
        "name": "Locale Product",
        "description": "Turkce aciklama",
        "translations": [
            {"locale": "tr-TR", "description": "Turkce aciklama"},
            {"locale": "en-US", "description": "English description"},
        ],
        "metaData": {"title": None, "description": None},
        "tags": [],
        "categories": [],
        "variants": [],
        "status": "active",
    })

    assert parsed.description_translations.get("en") == "English description"
    assert parsed.description_translations.get("tr") == "Turkce aciklama"


def test_parse_product_slug(monkeypatch):
    monkeypatch.setenv("IKAS_STORE_NAME", "demo-store")
    monkeypatch.setenv("IKAS_CLIENT_ID", "demo-client")
    monkeypatch.setenv("IKAS_CLIENT_SECRET", "demo-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-demo")
    client = IkasClient()
    parsed = client._parse_product({
        "id": "prod_slug",
        "name": "Sluglu Urun",
        "description": "Aciklama",
        "metaData": {"pageTitle": None, "description": None, "slug": "sluglu-urun"},
        "tags": [],
        "categories": [],
        "variants": [],
        "status": "active",
    })

    assert parsed.slug == "sluglu-urun"


@pytest.mark.anyio
async def test_update_product_uses_save_product_mutation_for_translations(monkeypatch):
    monkeypatch.setattr(
        "core.clients.ikas.get_config",
        lambda: AppConfig(
            ikas_store_name="demo-store",
            ikas_client_id="demo-client",
            ikas_client_secret="demo-secret",
            ikas_api_url="https://api.myikas.com/api/v1/admin/graphql",
            dry_run=False,
        ),
    )
    client = IkasClient()
    calls: list[tuple[str, dict]] = []
    existing_product_data = {
        "id": "prod-1",
        "name": "Test Product",
        "description": "Bir test aciklamasi",
        "type": "PHYSICAL",
        "translations": [{"locale": "tr", "description": "Bir test aciklamasi"}],
        "variants": [
            {
                "id": "var-1",
                "sku": "sku-1",
                "isActive": True,
                "sellIfOutOfStock": False,
                "prices": [{"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"}],
                "images": [],
            }
        ],
    }
    verified_product = Product(
        id="prod-1",
        name="Test Product",
        description="Bir test aciklamasi",
        description_translations={
            "tr": "Bir test aciklamasi",
            "en": "<p>English description</p>",
        },
    )

    async def fake_graphql(query, variables=None):
        calls.append((query, variables or {}))
        return {"saveProduct": {"id": "prod-1"}}

    async def fake_get_product_by_id(_product_id):
        return verified_product

    async def fake_get_product_for_update_data(_product_id):
        return existing_product_data

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    monkeypatch.setattr(client, "get_product_by_id", fake_get_product_by_id)
    monkeypatch.setattr(client, "_get_product_for_update_data", fake_get_product_for_update_data)

    ok = await client.update_product("prod-1", {
        "description_translations": {"en": "<p>English description</p>"},
    })

    assert ok is True
    assert len(calls) == 1
    query, variables = calls[0]
    assert "mutation SaveProduct($input: ProductInput!)" in query
    assert variables == {
        "input": {
            "id": "prod-1",
            "name": "Test Product",
            "type": "PHYSICAL",
            "variants": [
                {
                    "id": "var-1",
                    "sku": "sku-1",
                    "isActive": True,
                    "sellIfOutOfStock": False,
                    "prices": [{"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"}],
                    "images": [],
                }
            ],
            "description": "Bir test aciklamasi",
            "translations": [
                {"locale": "tr", "description": "Bir test aciklamasi"},
                {"locale": "en", "description": "<p>English description</p>"},
            ],
        }
    }


@pytest.mark.anyio
async def test_update_product_retries_without_translations_only_when_default_description_exists(monkeypatch):
    monkeypatch.setattr(
        "core.clients.ikas.get_config",
        lambda: AppConfig(
            ikas_store_name="demo-store",
            ikas_client_id="demo-client",
            ikas_client_secret="demo-secret",
            ikas_api_url="https://api.myikas.com/api/v1/admin/graphql",
            dry_run=False,
        ),
    )
    client = IkasClient()
    calls: list[tuple[str, dict]] = []
    existing_product_data = {
        "id": "prod-1",
        "name": "Test Product",
        "description": "<p>Turkce aciklama</p>",
        "type": "PHYSICAL",
        "translations": [{"locale": "tr", "description": "<p>Turkce aciklama</p>"}],
        "variants": [
            {
                "id": "var-1",
                "sku": "sku-1",
                "isActive": True,
                "sellIfOutOfStock": False,
                "prices": [
                    {"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"},
                    {"buyPrice": 55.0, "sellPrice": 90.0, "discountPrice": 80.0, "currency": "TRY", "priceListId": "pl-1"},
                ],
                "images": [],
            }
        ],
        "salesChannelIds": ["sc-1"],
    }
    verified_product = Product(
        id="prod-1",
        name="Test Product",
        description="<p>Turkce aciklama</p>",
        description_translations={
            "tr": "<p>Turkce aciklama</p>",
            "en": "<p>English description</p>",
        },
    )

    async def fake_graphql(query, variables=None):
        calls.append((query, variables or {}))
        if len(calls) == 1:
            raise RuntimeError("translations not accepted by API")
        return {"saveProduct": {"id": "prod-1"}}

    async def fake_get_product_by_id(_product_id):
        return verified_product

    async def fake_get_product_for_update_data(_product_id):
        return existing_product_data

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    monkeypatch.setattr(client, "get_product_by_id", fake_get_product_by_id)
    monkeypatch.setattr(client, "_get_product_for_update_data", fake_get_product_for_update_data)

    ok = await client.update_product("prod-1", {
        "description_translations": {"tr": "<p>Turkce aciklama</p>", "en": "<p>English description</p>"},
    })

    assert ok is True
    assert len(calls) == 2
    assert calls[0][1]["input"]["translations"] == [
        {"locale": "tr", "description": "<p>Turkce aciklama</p>"},
        {"locale": "en", "description": "<p>English description</p>"},
    ]
    assert calls[0][1]["input"]["salesChannelIds"] == ["sc-1"]
    assert calls[0][1]["input"]["variants"][0]["prices"] == [
        {"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"},
        {"buyPrice": 55.0, "sellPrice": 90.0, "discountPrice": 80.0, "currency": "TRY", "priceListId": "pl-1"},
    ]
    assert calls[1][1] == {
        "input": {
            "id": "prod-1",
            "name": "Test Product",
            "type": "PHYSICAL",
            "salesChannelIds": ["sc-1"],
            "variants": [
                    {
                        "id": "var-1",
                        "sku": "sku-1",
                        "isActive": True,
                        "sellIfOutOfStock": False,
                        "prices": [
                            {"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"},
                            {"buyPrice": 55.0, "sellPrice": 90.0, "discountPrice": 80.0, "currency": "TRY", "priceListId": "pl-1"},
                        ],
                        "images": [],
                    }
                ],
                "description": "<p>Turkce aciklama</p>",
            }
        }


@pytest.mark.anyio
async def test_update_product_does_not_silently_drop_en_only_translation(monkeypatch):
    monkeypatch.setattr(
        "core.clients.ikas.get_config",
        lambda: AppConfig(
            ikas_store_name="demo-store",
            ikas_client_id="demo-client",
            ikas_client_secret="demo-secret",
            ikas_api_url="https://api.myikas.com/api/v1/admin/graphql",
            dry_run=False,
        ),
    )
    client = IkasClient()
    calls: list[tuple[str, dict]] = []
    existing_product_data = {
        "id": "prod-1",
        "name": "Test Product",
        "description": "Bir test aciklamasi",
        "type": "PHYSICAL",
        "translations": [{"locale": "tr", "description": "Bir test aciklamasi"}],
        "variants": [
            {
                "id": "var-1",
                "sku": "sku-1",
                "isActive": True,
                "sellIfOutOfStock": False,
                "prices": [{"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"}],
                "images": [],
            }
        ],
    }
    existing_product = Product(
        id="prod-1",
        name="Test Product",
        description="Bir test aciklamasi",
        description_translations={"tr": "Bir test aciklamasi"},
    )

    async def fake_graphql(query, variables=None):
        calls.append((query, variables or {}))
        if len(calls) == 1:
            raise RuntimeError("translations not accepted by API")
        return {"saveProduct": {"id": "prod-1"}}

    async def fake_get_product_by_id(_product_id):
        return existing_product

    async def fake_get_product_for_update_data(_product_id):
        return existing_product_data

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    monkeypatch.setattr(client, "get_product_by_id", fake_get_product_by_id)
    monkeypatch.setattr(client, "_get_product_for_update_data", fake_get_product_for_update_data)

    with pytest.raises(RuntimeError, match="Product update succeeded but translations were not persisted for locales: en"):
        await client.update_product("prod-1", {
            "description_translations": {"en": "<p>English description</p>"},
        })

    assert len(calls) == 2
    assert calls[0][1] == {
        "input": {
            "id": "prod-1",
            "name": "Test Product",
            "type": "PHYSICAL",
            "variants": [
                {
                    "id": "var-1",
                    "sku": "sku-1",
                    "isActive": True,
                    "sellIfOutOfStock": False,
                    "prices": [{"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"}],
                    "images": [],
                }
            ],
            "description": "Bir test aciklamasi",
            "translations": [
                {"locale": "tr", "description": "Bir test aciklamasi"},
                {"locale": "en", "description": "<p>English description</p>"},
            ],
        }
    }
    assert calls[1][1] == {
        "input": {
            "id": "prod-1",
            "name": "Test Product",
            "type": "PHYSICAL",
            "variants": [
                {
                    "id": "var-1",
                    "sku": "sku-1",
                    "isActive": True,
                    "sellIfOutOfStock": False,
                    "prices": [{"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"}],
                    "images": [],
                }
            ],
            "description": "Bir test aciklamasi",
        }
    }


@pytest.mark.anyio
async def test_update_product_raises_when_translation_not_persisted_after_success(monkeypatch):
    monkeypatch.setattr(
        "core.clients.ikas.get_config",
        lambda: AppConfig(
            ikas_store_name="demo-store",
            ikas_client_id="demo-client",
            ikas_client_secret="demo-secret",
            ikas_api_url="https://api.myikas.com/api/v1/admin/graphql",
            dry_run=False,
        ),
    )
    client = IkasClient()
    existing_product_data = {
        "id": "prod-1",
        "name": "Test Product",
        "description": "Bir test aciklamasi",
        "type": "PHYSICAL",
        "translations": [{"locale": "tr", "description": "Bir test aciklamasi"}],
        "variants": [
            {
                "id": "var-1",
                "sku": "sku-1",
                "isActive": True,
                "sellIfOutOfStock": False,
                "prices": [{"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"}],
                "images": [],
            }
        ],
    }
    existing_product = Product(
        id="prod-1",
        name="Test Product",
        description="Bir test aciklamasi",
        description_translations={"tr": "Bir test aciklamasi"},
    )

    async def fake_graphql(query, variables=None):
        return {"updateProduct": {"id": "prod-1"}}

    async def fake_sleep(_seconds):
        return None

    async def fake_get_product_by_id(_product_id):
        return existing_product

    async def fake_get_product_for_update_data(_product_id):
        return existing_product_data

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    monkeypatch.setattr(client, "get_product_by_id", fake_get_product_by_id)
    monkeypatch.setattr(client, "_get_product_for_update_data", fake_get_product_for_update_data)
    monkeypatch.setattr("core.clients.ikas.asyncio.sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="Product update succeeded but translations were not persisted for locales: en"):
        await client.update_product("prod-1", {
            "description_translations": {"en": "<p>English description</p>"},
        })


@pytest.mark.anyio
async def test_update_product_does_not_retry_non_translation_errors(monkeypatch):
    monkeypatch.setattr(
        "core.clients.ikas.get_config",
        lambda: AppConfig(
            ikas_store_name="demo-store",
            ikas_client_id="demo-client",
            ikas_client_secret="demo-secret",
            ikas_api_url="https://api.myikas.com/api/v1/admin/graphql",
            dry_run=False,
        ),
    )
    client = IkasClient()
    calls: list[tuple[str, dict]] = []
    existing_product_data = {
        "id": "prod-1",
        "name": "Test Product",
        "description": "Bir test aciklamasi",
        "type": "PHYSICAL",
        "translations": [{"locale": "tr", "description": "Bir test aciklamasi"}],
        "variants": [
            {
                "id": "var-1",
                "sku": "sku-1",
                "isActive": True,
                "sellIfOutOfStock": False,
                "prices": [
                    {"buyPrice": 60.0, "sellPrice": 100.0},
                    {"buyPrice": 55.0, "sellPrice": 90.0, "priceListId": "pl-1"},
                ],
                "images": [],
            }
        ],
    }

    async def fake_graphql(query, variables=None):
        calls.append((query, variables or {}))
        raise RuntimeError("GraphQL errors: DUPLICATE_DEFAULT_PRICE")

    async def fake_get_product_for_update_data(_product_id):
        return existing_product_data

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    monkeypatch.setattr(client, "_get_product_for_update_data", fake_get_product_for_update_data)

    with pytest.raises(RuntimeError, match="DUPLICATE_DEFAULT_PRICE"):
        await client.update_product("prod-1", {
            "description_translations": {"en": "<p>English description</p>"},
        })

    assert len(calls) == 1


@pytest.mark.anyio
async def test_update_product_preserves_existing_product_fields(monkeypatch):
    monkeypatch.setattr(
        "core.clients.ikas.get_config",
        lambda: AppConfig(
            ikas_store_name="demo-store",
            ikas_client_id="demo-client",
            ikas_client_secret="demo-secret",
            ikas_api_url="https://api.myikas.com/api/v1/admin/graphql",
            dry_run=False,
        ),
    )
    client = IkasClient()
    calls: list[tuple[str, dict]] = []
    existing_product_data = {
        "id": "prod-1",
        "name": "Test Product",
        "description": "<p>Turkce aciklama</p>",
        "shortDescription": "Kisa aciklama",
        "type": "PHYSICAL",
        "weight": 1.25,
        "releaseDate": "2026-03-31T12:00:00.000Z",
        "brandId": "brand-1",
        "categoryIds": ["cat-1"],
        "tagIds": ["tag-1"],
        "salesChannelIds": ["sc-1"],
        "hiddenSalesChannelIds": ["hidden-1"],
        "dynamicPriceListIds": ["dpl-1"],
        "groupVariantsByVariantTypeId": "vt-1",
        "googleTaxonomyId": "113",
        "productOptionSetId": "pos-1",
        "productVolumeDiscountId": "pvd-1",
        "subscriptionPlanId": "sub-1",
        "vendorId": "vendor-1",
        "maxQuantityPerCart": 4,
        "baseUnit": {"baseAmount": 1.0, "type": "PIECE", "unitId": "unit-1"},
        "productVariantTypes": [{"order": 1, "variantTypeId": "vt-1", "variantValueIds": ["vv-1", "vv-2"]}],
        "attributes": [{"imageIds": ["img-attr"], "productAttributeId": "attr-1", "productAttributeOptionId": "opt-1", "value": "Green"}],
        "salesChannels": [{
            "id": "sc-1",
            "maxQuantityPerCart": 4,
            "minQuantityPerCart": 1,
            "productVolumeDiscountId": "pvd-1",
            "quantitySettings": [1, 2, 3],
            "status": "VISIBLE",
        }],
        "translations": [
            {"locale": "tr", "name": "Test Product", "description": "<p>Turkce aciklama</p>"},
            {"locale": "en", "name": "Test Product EN", "description": "<p>Old english</p>"},
        ],
        "metaData": {
            "id": "meta-1",
            "slug": "test-product",
            "pageTitle": "Eski Meta Title",
            "description": "Eski Meta Description",
            "disableIndex": False,
            "canonicals": ["https://example.com/test-product"],
            "targetId": "prod-1",
            "targetType": "PRODUCT",
            "metadataOverrides": [{
                "description": "Override desc",
                "language": "tr",
                "pageTitle": "Override title",
                "storefrontId": "sf-1",
                "storefrontRegionId": "sr-1",
            }],
            "translations": [{
                "locale": "en",
                "pageTitle": "English Meta",
                "description": "English Meta Desc",
                "slug": "test-product-en",
            }],
        },
        "variants": [
            {
                "id": "var-1",
                "sku": "sku-1",
                "weight": 1.25,
                "isActive": True,
                "sellIfOutOfStock": False,
                "hsCode": "1234",
                "fileId": "file-1",
                "subscriptionPlanId": "sub-1",
                "barcodeList": ["barcode-1"],
                "bundleSettings": {
                    "maxBundleQuantity": 3,
                    "minBundleQuantity": 1,
                    "products": [{
                        "addToBundleBasePrice": True,
                        "discountRatio": 10,
                        "filteredVariantIds": ["fvv-1"],
                        "id": "bundle-1",
                        "maxQuantity": 3,
                        "minQuantity": 1,
                        "order": 1,
                        "productId": "bundle-prod-1",
                        "quantity": 2,
                    }],
                },
                "unit": {"amount": 2.0, "type": "LITER"},
                "attributes": [{"productAttributeId": "attr-1", "value": "Variant Green"}],
                "variantValueIds": [{"variantTypeId": "vt-1", "variantValueId": "vv-1"}],
                "prices": [
                    {"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"},
                    {"buyPrice": 55.0, "sellPrice": 90.0, "discountPrice": 80.0, "currency": "TRY", "priceListId": "pl-1"},
                ],
                "images": [{"imageId": "img-1", "order": 1, "fileName": "test.webp", "isMain": True, "isVideo": False}],
            }
        ],
    }
    verified_product = Product(
        id="prod-1",
        name="Test Product",
        description="<p>Turkce aciklama</p>",
        description_translations={
            "tr": "<p>Turkce aciklama</p>",
            "en": "<p>English description</p>",
        },
    )

    async def fake_graphql(query, variables=None):
        calls.append((query, variables or {}))
        return {"saveProduct": {"id": "prod-1"}}

    async def fake_get_product_for_update_data(_product_id):
        return existing_product_data

    async def fake_get_product_by_id(_product_id):
        return verified_product

    monkeypatch.setattr(client, "_graphql", fake_graphql)
    monkeypatch.setattr(client, "_get_product_for_update_data", fake_get_product_for_update_data)
    monkeypatch.setattr(client, "get_product_by_id", fake_get_product_by_id)

    ok = await client.update_product("prod-1", {
        "description_translations": {"en": "<p>English description</p>"},
    })

    assert ok is True
    assert len(calls) == 1
    payload = calls[0][1]["input"]
    assert payload["shortDescription"] == "Kisa aciklama"
    assert payload["hiddenSalesChannelIds"] == ["hidden-1"]
    assert payload["dynamicPriceListIds"] == ["dpl-1"]
    assert payload["baseUnit"] == {"baseAmount": 1.0, "type": "PIECE", "unitId": "unit-1"}
    assert payload["productVariantTypes"] == [{"order": 1, "variantTypeId": "vt-1", "variantValueIds": ["vv-1", "vv-2"]}]
    assert payload["attributes"] == [{"imageIds": ["img-attr"], "productAttributeId": "attr-1", "productAttributeOptionId": "opt-1", "value": "Green"}]
    assert payload["salesChannels"] == [{
        "id": "sc-1",
        "maxQuantityPerCart": 4,
        "minQuantityPerCart": 1,
        "productVolumeDiscountId": "pvd-1",
        "quantitySettings": [1, 2, 3],
        "status": "VISIBLE",
    }]
    assert payload["metaData"] == {
        "id": "meta-1",
        "slug": "test-product",
        "pageTitle": "Eski Meta Title",
        "description": "Eski Meta Description",
        "disableIndex": False,
        "canonicals": ["https://example.com/test-product"],
        "targetId": "prod-1",
        "targetType": "PRODUCT",
        "metadataOverrides": [{
            "description": "Override desc",
            "language": "tr",
            "pageTitle": "Override title",
            "storefrontId": "sf-1",
            "storefrontRegionId": "sr-1",
        }],
        "translations": [{
            "locale": "en",
            "pageTitle": "English Meta",
            "description": "English Meta Desc",
            "slug": "test-product-en",
        }],
    }
    assert payload["translations"] == [
        {"locale": "tr", "name": "Test Product", "description": "<p>Turkce aciklama</p>"},
        {"locale": "en", "name": "Test Product EN", "description": "<p>English description</p>"},
    ]
    assert payload["variants"] == [{
        "id": "var-1",
        "sku": "sku-1",
        "weight": 1.25,
        "isActive": True,
        "sellIfOutOfStock": False,
        "hsCode": "1234",
        "fileId": "file-1",
        "subscriptionPlanId": "sub-1",
        "barcodeList": ["barcode-1"],
        "bundleSettings": {
            "maxBundleQuantity": 3,
            "minBundleQuantity": 1,
            "products": [{
                "addToBundleBasePrice": True,
                "discountRatio": 10,
                "filteredVariantIds": ["fvv-1"],
                "id": "bundle-1",
                "maxQuantity": 3,
                "minQuantity": 1,
                "order": 1,
                "productId": "bundle-prod-1",
                "quantity": 2,
            }],
        },
        "unit": {"amount": 2.0, "type": "LITER"},
        "attributes": [{"productAttributeId": "attr-1", "value": "Variant Green"}],
        "variantValueIds": [{"variantTypeId": "vt-1", "variantValueId": "vv-1"}],
        "prices": [
            {"buyPrice": 60.0, "sellPrice": 100.0, "currency": "TRY"},
            {"buyPrice": 55.0, "sellPrice": 90.0, "discountPrice": 80.0, "currency": "TRY", "priceListId": "pl-1"},
        ],
        "images": [{"imageId": "img-1", "order": 1, "fileName": "test.webp", "isMain": True, "isVideo": False}],
    }]
