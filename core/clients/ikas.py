import asyncio
import base64
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import get_config
from core.clients.mcp import IkasMCPClient
from core.models import Product

logger = logging.getLogger(__name__)


class IkasClient:
    PRODUCTS_QUERY = """
    query ListProducts($pagination: PaginationInput) {
        listProduct(pagination: $pagination) {
            data {
                id
                name
                description
                translations { locale name description }
                metaData { pageTitle description slug }
                tags { id name }
                categories { name }
                variants { prices { sellPrice } sku images { imageId order fileName isMain } }
            }
            count
            hasNext
        }
    }
    """

    PRODUCT_BY_ID_QUERY = """
    query GetProduct($id: StringFilterInput!) {
        listProduct(id: $id) {
            data {
                id
                name
                description
                translations { locale name description }
                metaData { pageTitle description slug }
                tags { id name }
                categories { name }
                variants { prices { sellPrice } sku images { imageId order fileName isMain } }
            }
        }
    }
    """

    SAVE_PRODUCT_MUTATION = """
    mutation SaveProduct($input: ProductInput!) {
        saveProduct(input: $input) {
            id
            name
            description
        }
    }
    """

    MCP_UPDATE_PRODUCT_MUTATION = """
    mutation UpdateProduct($input: UpdateProductInput!) {
        updateProduct(input: $input) {
            id
            name
            description
            updatedAt
        }
    }
    """

    _PREFETCH_FOR_UPDATE_QUERY = """
    query GetProductForUpdate($id: StringFilterInput!) {
        listProduct(id: $id) {
            data {
                id
                name
                description
                shortDescription
                type
                weight
                releaseDate
                salesChannelIds
                hiddenSalesChannelIds
                dynamicPriceListIds
                brandId
                categoryIds
                tagIds
                groupVariantsByVariantTypeId
                googleTaxonomyId
                productOptionSetId
                productVolumeDiscountId
                subscriptionPlanId
                vendorId
                maxQuantityPerCart
                baseUnit { baseAmount type unitId }
                productVariantTypes { order variantTypeId variantValueIds }
                attributes { imageIds productAttributeId productAttributeOptionId value }
                salesChannels {
                    id
                    maxQuantityPerCart
                    minQuantityPerCart
                    productVolumeDiscountId
                    quantitySettings
                    status
                }
                translations { locale name description }
                metaData {
                    id
                    slug
                    pageTitle
                    description
                    disableIndex
                    canonicals
                    targetId
                    targetType
                    metadataOverrides {
                        description
                        language
                        pageTitle
                        storefrontId
                        storefrontRegionId
                    }
                    translations {
                        locale
                        pageTitle
                        description
                        slug
                    }
                }
                variants {
                    id
                    sku
                    weight
                    isActive
                    sellIfOutOfStock
                    hsCode
                    fileId
                    subscriptionPlanId
                    barcodeList
                    bundleSettings {
                        maxBundleQuantity
                        minBundleQuantity
                        products {
                            addToBundleBasePrice
                            discountRatio
                            filteredVariantIds
                            id
                            maxQuantity
                            minQuantity
                            order
                            productId
                            quantity
                        }
                    }
                    unit { amount type }
                    attributes { imageIds productAttributeId productAttributeOptionId value }
                    variantValueIds { variantTypeId variantValueId }
                    prices { buyPrice sellPrice discountPrice currency priceListId }
                    images { imageId order fileName isMain isVideo }
                }
            }
        }
    }
    """

    CATEGORIES_QUERY = """
    query ListCategories {
        listCategory {
            data {
                id
                name
            }
        }
    }
    """

    def __init__(self) -> None:
        self._config = get_config()
        self._token: Optional[str] = None
        self._merchant_id: Optional[str] = None
        self._semaphore = asyncio.Semaphore(5)
        self._client: Optional[httpx.AsyncClient] = None
        self.total_count: int = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def authenticate(self) -> str:
        if self._token:
            return self._token

        client = await self._get_client()
        auth_url = f"https://{self._config.ikas_store_name}.myikas.com/api/admin/oauth/token"

        for attempt in range(3):
            try:
                response = await client.post(
                    auth_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._config.ikas_client_id,
                        "client_secret": self._config.ikas_client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                data = response.json()
                self._token = data["access_token"]
                self._merchant_id = data.get("merchantId") or data.get("merchant_id")
                if not self._merchant_id:
                    self._merchant_id = self._extract_merchant_id_from_jwt(self._token)
                logger.info("ikas authentication successful (merchant=%s)", self._merchant_id)
                return self._token
            except httpx.HTTPError as e:
                logger.warning(f"Auth attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        raise RuntimeError("Authentication failed after 3 attempts")

    @staticmethod
    def _extract_merchant_id_from_jwt(token: str) -> Optional[str]:
        """Decode JWT payload (without verification) to extract merchantId."""
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return None
            # Add padding for base64
            payload_b64 = parts[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            merchant_id = (
                payload.get("merchantId")
                or payload.get("merchant_id")
                or payload.get("mid")
                or payload.get("sub")
            )
            if merchant_id:
                logger.debug("Extracted merchantId from JWT: %s", merchant_id)
            else:
                logger.warning("Could not find merchantId in JWT payload: %s", list(payload.keys()))
            return merchant_id
        except Exception as e:
            logger.warning("Failed to decode JWT for merchantId: %s", e)
            return None

    async def _graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with self._semaphore:
            token = await self.authenticate()
            client = await self._get_client()

            for attempt in range(5):
                try:
                    response = await client.post(
                        self._config.ikas_api_url,
                        json={"query": query, "variables": variables or {}},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if response.status_code == 429:
                        try:
                            body = response.json()
                            retry_after = float(body.get("retryAfter", 5))
                        except Exception:
                            retry_after = 5.0
                        wait = retry_after + 0.5
                        logger.warning(
                            "GraphQL request failed: status=%s body=%s",
                            response.status_code,
                            response.text,
                        )
                        logger.warning("ikas rate limit hit, waiting %.1fs before retry (attempt %d/5)", wait, attempt + 1)
                        await asyncio.sleep(wait)
                        continue
                    if response.status_code >= 400:
                        logger.error(
                            "GraphQL request failed: status=%s body=%s",
                            response.status_code,
                            response.text,
                        )
                    response.raise_for_status()
                    result = response.json()

                    if "errors" in result:
                        raise RuntimeError(f"GraphQL errors: {result['errors']}")

                    return result["data"]
                except httpx.HTTPError as e:
                    logger.warning(f"GraphQL attempt {attempt + 1} failed: {e}")
                    if attempt < 4:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise

            raise RuntimeError("GraphQL request failed after 5 attempts")

    def _extract_translations(self, data: Dict[str, Any]) -> Dict[str, str]:
        # ikas API returns translations as list of {locale, name, description}
        raw = data.get("translations") or data.get("descriptionTranslations") or {}

        if isinstance(raw, dict):
            output: Dict[str, str] = {}
            for key, value in raw.items():
                if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
                    continue
                normalized_locale = self._normalize_translation_locale(key)
                output.setdefault(normalized_locale, value)
                output.setdefault(key.lower(), value)
            return output

        if isinstance(raw, list):
            output: Dict[str, str] = {}
            for item in raw:
                if not isinstance(item, dict):
                    continue
                locale = item.get("locale") or item.get("language")
                # ikas translations use "description" field (not "value")
                value = item.get("description") or item.get("value")
                if isinstance(locale, str) and isinstance(value, str) and value.strip():
                    normalized_locale = self._normalize_translation_locale(locale)
                    output.setdefault(normalized_locale, value)
                    output.setdefault(locale.lower(), value)
            return output

        return {}

    @staticmethod
    def _normalize_translation_locale(locale: str) -> str:
        normalized = locale.strip().lower().replace("_", "-")
        if not normalized:
            return normalized
        if normalized.startswith("en"):
            return "en"
        if normalized.startswith("tr"):
            return "tr"
        return normalized

    @classmethod
    def _normalize_translation_updates(cls, translations: Dict[str, Any]) -> Dict[str, str]:
        normalized_translations: Dict[str, str] = {}
        for locale, text in (translations or {}).items():
            if not isinstance(locale, str) or not isinstance(text, str) or not text.strip():
                continue
            normalized_translations[cls._normalize_translation_locale(locale)] = text
        return normalized_translations

    async def _seed_default_description_for_translation_update(
        self,
        product_id: str,
        input_data: Dict[str, Any],
    ) -> None:
        if "translations" not in input_data or "description" in input_data:
            return

        try:
            existing_product = await self.get_product_by_id(product_id)
        except Exception as exc:
            logger.warning(
                "Could not load existing product %s before translation update: %s",
                product_id,
                exc,
            )
            return

        if existing_product and isinstance(existing_product.description, str) and existing_product.description.strip():
            input_data["description"] = existing_product.description

    async def _get_product_for_update_data(self, product_id: str) -> Dict[str, Any]:
        data = await self._graphql(
            self._PREFETCH_FOR_UPDATE_QUERY,
            {"id": {"eq": product_id}},
        )
        products = data.get("listProduct", {}).get("data", [])
        if not products:
            raise RuntimeError(f"Product not found: {product_id}")
        return products[0]

    async def ensure_translations_persisted(
        self,
        product_id: str,
        translations: Dict[str, Any],
        *,
        attempts: int = 3,
        base_delay_seconds: float = 0.35,
    ) -> Product | None:
        expected_translations = self._normalize_translation_updates(translations)
        if not expected_translations:
            return await self.get_product_by_id(product_id)

        last_missing_locales = sorted(expected_translations.keys())
        last_product: Product | None = None

        for attempt in range(attempts):
            last_product = await self.get_product_by_id(product_id)
            if last_product:
                actual_translations = last_product.description_translations or {}
                missing_locales: list[str] = []
                for locale in expected_translations:
                    normalized_locale = self._normalize_translation_locale(locale)
                    actual_value = (
                        actual_translations.get(normalized_locale)
                        or actual_translations.get(locale.lower())
                        or actual_translations.get(locale)
                    )
                    if isinstance(actual_value, str) and actual_value.strip():
                        continue
                    missing_locales.append(normalized_locale)

                if not missing_locales:
                    return last_product
                last_missing_locales = sorted(set(missing_locales))

            if attempt + 1 < attempts:
                await asyncio.sleep(base_delay_seconds * (attempt + 1))

        raise RuntimeError(
            "Product update succeeded but translations were not persisted for locales: "
            + ", ".join(last_missing_locales)
        )

    @staticmethod
    def _copy_non_null_fields(source: Dict[str, Any], allowed_fields: tuple[str, ...]) -> Dict[str, Any]:
        return {
            field: source[field]
            for field in allowed_fields
            if field in source and source[field] is not None
        }

    @classmethod
    def _clean_product_attribute_for_input(cls, attribute: Dict[str, Any]) -> Dict[str, Any]:
        return cls._copy_non_null_fields(
            attribute,
            ("imageIds", "productAttributeId", "productAttributeOptionId", "value"),
        )

    @classmethod
    def _clean_product_variant_type_for_input(cls, variant_type: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = cls._copy_non_null_fields(
            variant_type,
            ("order", "variantTypeId", "variantValueIds"),
        )
        variant_value_ids = cleaned.get("variantValueIds")
        if isinstance(variant_value_ids, list):
            cleaned["variantValueIds"] = [value for value in variant_value_ids if value is not None]
        return cleaned

    @classmethod
    def _clean_product_sales_channel_for_input(cls, sales_channel: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = cls._copy_non_null_fields(
            sales_channel,
            ("id", "maxQuantityPerCart", "minQuantityPerCart", "productVolumeDiscountId", "quantitySettings", "status"),
        )
        quantity_settings = cleaned.get("quantitySettings")
        if isinstance(quantity_settings, list):
            cleaned["quantitySettings"] = [value for value in quantity_settings if value is not None]
        return cleaned

    @classmethod
    def _clean_translation_item_for_input(cls, translation: Dict[str, Any]) -> Dict[str, Any]:
        return cls._copy_non_null_fields(translation, ("locale", "name", "description"))

    @classmethod
    def _merge_translation_items(
        cls,
        existing_translations: Any,
        description_updates: Dict[str, str] | None = None,
    ) -> List[Dict[str, Any]]:
        merged: dict[str, Dict[str, Any]] = {}

        if isinstance(existing_translations, list):
            for item in existing_translations:
                if not isinstance(item, dict):
                    continue
                locale = item.get("locale")
                if not isinstance(locale, str) or not locale.strip():
                    continue
                cleaned = cls._clean_translation_item_for_input(item)
                if cleaned:
                    merged[cls._normalize_translation_locale(locale)] = cleaned

        for locale, text in cls._normalize_translation_updates(description_updates or {}).items():
            entry = dict(merged.get(locale, {"locale": locale}))
            entry["locale"] = locale
            entry["description"] = text
            merged[locale] = entry

        return [
            item for item in merged.values()
            if isinstance(item.get("locale"), str) and item["locale"].strip()
            and any(
                isinstance(item.get(field), str) and item[field].strip()
                for field in ("name", "description")
            )
        ]

    @classmethod
    def _clean_meta_override_for_input(cls, override: Dict[str, Any]) -> Dict[str, Any]:
        return cls._copy_non_null_fields(
            override,
            ("description", "language", "pageTitle", "storefrontId", "storefrontRegionId"),
        )

    @classmethod
    def _clean_meta_translation_for_input(cls, translation: Dict[str, Any]) -> Dict[str, Any]:
        return cls._copy_non_null_fields(
            translation,
            ("locale", "pageTitle", "description", "slug"),
        )

    @classmethod
    def _clean_meta_data_for_input(cls, meta_data: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = cls._copy_non_null_fields(
            meta_data,
            ("id", "slug", "pageTitle", "description", "disableIndex", "canonicals", "targetId", "targetType"),
        )
        overrides = meta_data.get("metadataOverrides")
        if isinstance(overrides, list):
            cleaned["metadataOverrides"] = [
                item
                for item in (cls._clean_meta_override_for_input(override) for override in overrides if isinstance(override, dict))
                if item
            ]
        translations = meta_data.get("translations")
        if isinstance(translations, list):
            cleaned["translations"] = [
                item
                for item in (cls._clean_meta_translation_for_input(translation) for translation in translations if isinstance(translation, dict))
                if item
            ]
        canonicals = cleaned.get("canonicals")
        if isinstance(canonicals, list):
            cleaned["canonicals"] = [value for value in canonicals if value is not None]
        return cleaned

    @classmethod
    def _clean_base_unit_for_input(cls, base_unit: Dict[str, Any]) -> Dict[str, Any]:
        return cls._copy_non_null_fields(base_unit, ("baseAmount", "type", "unitId"))

    @classmethod
    def _clean_bundle_product_for_input(cls, bundle_product: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = cls._copy_non_null_fields(
            bundle_product,
            ("addToBundleBasePrice", "discountRatio", "filteredVariantIds", "id", "maxQuantity", "minQuantity", "order", "productId", "quantity"),
        )
        filtered_variant_ids = cleaned.get("filteredVariantIds")
        if isinstance(filtered_variant_ids, list):
            cleaned["filteredVariantIds"] = [value for value in filtered_variant_ids if value is not None]
        return cleaned

    @classmethod
    def _clean_bundle_settings_for_input(cls, bundle_settings: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = cls._copy_non_null_fields(bundle_settings, ("maxBundleQuantity", "minBundleQuantity"))
        products = bundle_settings.get("products")
        if isinstance(products, list):
            cleaned["products"] = [
                item
                for item in (cls._clean_bundle_product_for_input(product) for product in products if isinstance(product, dict))
                if item
            ]
        return cleaned

    @classmethod
    def _clean_variant_unit_for_input(cls, unit: Dict[str, Any]) -> Dict[str, Any]:
        return cls._copy_non_null_fields(unit, ("amount", "type"))

    @staticmethod
    def _clean_variant_for_input(variant: Dict[str, Any]) -> Dict[str, Any]:
        """Whitelist variant fields for saveProduct mutation input.

        ikas GraphQL returns extra fields (_id, merchantId, deleted, isActive)
        that are NOT accepted by the mutation and cause validation errors.
        """
        cleaned: Dict[str, Any] = {}
        # Scalar fields accepted by VariantInput
        # ikas may return "_id" instead of "id" — map it
        variant_id = variant.get("id") or variant.get("_id")
        if variant_id is not None:
            cleaned["id"] = variant_id
        for key in ("sku", "weight", "sellIfOutOfStock", "isActive", "hsCode", "fileId", "subscriptionPlanId"):
            if variant.get(key) is not None:
                cleaned[key] = variant[key]

        barcode_list = variant.get("barcodeList")
        if isinstance(barcode_list, list):
            cleaned["barcodeList"] = [value for value in barcode_list if value is not None]

        unit = variant.get("unit")
        if isinstance(unit, dict):
            cleaned_unit = IkasClient._clean_variant_unit_for_input(unit)
            if cleaned_unit:
                cleaned["unit"] = cleaned_unit

        raw_attributes = variant.get("attributes")
        if isinstance(raw_attributes, list):
            cleaned["attributes"] = [
                item
                for item in (IkasClient._clean_product_attribute_for_input(attribute) for attribute in raw_attributes if isinstance(attribute, dict))
                if item
            ]

        bundle_settings = variant.get("bundleSettings")
        if isinstance(bundle_settings, dict):
            cleaned_bundle_settings = IkasClient._clean_bundle_settings_for_input(bundle_settings)
            if cleaned_bundle_settings:
                cleaned["bundleSettings"] = cleaned_bundle_settings

        # variantValueIds — array of {variantTypeId, variantValueId}
        raw_vvi = variant.get("variantValueIds")
        if isinstance(raw_vvi, list):
            cleaned["variantValueIds"] = [
                {"variantTypeId": v["variantTypeId"], "variantValueId": v["variantValueId"]}
                for v in raw_vvi
                if isinstance(v, dict) and v.get("variantTypeId") and v.get("variantValueId")
            ]

        # prices — strip merchantId and other server-side fields
        raw_prices = variant.get("prices")
        if isinstance(raw_prices, list):
            cleaned["prices"] = [
                {
                    k: v for k, v in p.items()
                    if k in ("buyPrice", "sellPrice", "discountPrice", "currency", "priceListId") and v is not None
                }
                for p in raw_prices if isinstance(p, dict)
            ]

        # images — strip merchantId and other server-side fields
        raw_images = variant.get("images")
        if isinstance(raw_images, list):
            cleaned["images"] = [
                {k: v for k, v in img.items() if k in ("imageId", "order", "fileName", "isMain", "isVideo") and v is not None}
                for img in raw_images if isinstance(img, dict)
            ]

        return cleaned

    def _build_image_url(self, image_data: Dict[str, Any]) -> Optional[str]:
        """Build a usable image URL from ikas ProductImage fields.
        
        Format: https://cdn.myikas.com/images/{merchantId}/{imageId}/3840/{fileName || 'image.webp'}
        """
        file_name = image_data.get("fileName") or "image.webp"
        image_id = image_data.get("imageId") or ""

        # fileName may already be a full URL
        if file_name.startswith("http"):
            return file_name

        if image_id and self._merchant_id:
            return f"https://cdn.myikas.com/images/{self._merchant_id}/{image_id}/3840/{file_name}"

        if image_id:
            return f"https://cdn.myikas.com/images/{image_id}/3840/{file_name}"

        return None

    @staticmethod
    def _extract_mcp_text_content(result: Any) -> str:
        if not isinstance(result, dict):
            return str(result or "")

        content = result.get("content")
        if not isinstance(content, list):
            return ""

        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()

    def _build_mcp_update_input(
        self,
        product_id: str,
        updates: Dict[str, Any],
        existing_product: Dict[str, Any],
    ) -> Dict[str, Any]:
        input_data: Dict[str, Any] = {"id": product_id}

        if "name" in updates:
            input_data["name"] = updates["name"]
        if "description" in updates:
            input_data["description"] = updates["description"]

        existing_meta = existing_product.get("metaData")
        if not isinstance(existing_meta, dict):
            existing_meta = {}

        if "meta_title" in updates or "meta_description" in updates:
            meta_data: Dict[str, Any] = {}
            if existing_meta.get("pageTitle") is not None:
                meta_data["pageTitle"] = existing_meta["pageTitle"]
            if existing_meta.get("description") is not None:
                meta_data["description"] = existing_meta["description"]
            meta_slug = existing_meta.get("slug")
            if isinstance(meta_slug, str) and meta_slug.strip():
                meta_data["slug"] = meta_slug
            if "meta_title" in updates:
                meta_data["pageTitle"] = updates["meta_title"]
            if "meta_description" in updates:
                meta_data["description"] = updates["meta_description"]
            if meta_data:
                input_data["metaData"] = meta_data

        requested_translations = self._normalize_translation_updates(updates.get("description_translations") or {})
        if requested_translations:
            input_data["translations"] = [
                {"locale": locale, "description": text}
                for locale, text in requested_translations.items()
            ]
            tr_description = requested_translations.get("tr")
            if tr_description and "description" not in input_data:
                input_data["description"] = tr_description
            elif (
                "description" not in input_data
                and isinstance(existing_product.get("description"), str)
                and existing_product["description"].strip()
            ):
                input_data["description"] = existing_product["description"]

        return input_data

    async def _update_product_via_mcp(
        self,
        product_id: str,
        updates: Dict[str, Any],
        existing_product: Dict[str, Any],
        *,
        mcp_token: str,
    ) -> None:
        input_data = self._build_mcp_update_input(product_id, updates, existing_product)
        mcp_client = IkasMCPClient(mcp_token)
        try:
            await mcp_client.initialize()
            result = await mcp_client.execute_mutation(
                "updateProduct",
                self.MCP_UPDATE_PRODUCT_MUTATION,
                {"input": input_data},
            )
        finally:
            await mcp_client.close()

        if isinstance(result, dict) and result.get("isError"):
            message = self._extract_mcp_text_content(result) or "MCP updateProduct returned an error"
            raise RuntimeError(message)

        logger.info("updateProduct MCP fallback succeeded for %s with keys: %s", product_id, list(input_data.keys()))

    def _parse_product(self, data: Dict[str, Any]) -> Product:
        variants = data.get("variants") or data.get("productVariants") or []
        first_variant = variants[0] if variants else {}
        categories = data.get("categories") or []
        meta = data.get("metaData") or {}
        description = data.get("description", "")
        translations = self._extract_translations(data)

        if isinstance(description, dict):
            for locale, value in description.items():
                if isinstance(locale, str) and isinstance(value, str) and value.strip():
                    translations.setdefault(locale.lower(), value)
            description = description.get("tr") or description.get("default") or ""

        if "tr" not in translations and isinstance(description, str) and description.strip():
            translations["tr"] = description

        # tags may be returned as objects {id, name} or plain strings
        raw_tags = data.get("tags") or []
        tags = [t["name"] if isinstance(t, dict) else t for t in raw_tags]

        # prices is a list of ProductPrice objects; take sellPrice from the first entry
        prices = first_variant.get("prices") or []
        price = prices[0].get("sellPrice") if prices else first_variant.get("price")

        # Extract image URLs from variants, sorted by order
        raw_images: list = []
        for v in variants:
            for img in (v.get("images") or []):
                if isinstance(img, dict):
                    raw_images.append(img)
        image_url: Optional[str] = None
        image_urls: list[str] = []
        if raw_images:
            sorted_images = sorted(raw_images, key=lambda x: x.get("order", 0))
            # Prefer isMain image if available
            main_images = [img for img in sorted_images if img.get("isMain")]
            chosen = main_images[0] if main_images else sorted_images[0]
            image_url = self._build_image_url(chosen)
            # Build all unique image URLs
            seen: set[str] = set()
            for img_data in sorted_images:
                url = self._build_image_url(img_data)
                if url and url not in seen:
                    seen.add(url)
                    image_urls.append(url)

        return Product(
            id=data["id"],
            name=data.get("name", ""),
            slug=meta.get("slug"),
            description=description if isinstance(description, str) else "",
            description_translations=translations,
            meta_title=meta.get("pageTitle") or meta.get("title"),
            meta_description=meta.get("description"),
            tags=tags,
            category=categories[0]["name"] if categories else None,
            price=price,
            sku=first_variant.get("sku"),
            status=data.get("status", "active"),
            image_url=image_url,
            image_urls=image_urls,
        )

    async def get_products(self, limit: int = 50, page: int = 1) -> List[Product]:
        all_products: List[Product] = []
        page_size = min(limit, 50)
        self.total_count = 0

        # Calculate API pages: UI page 1 with limit 50 => API page 1
        # UI page 2 with limit 50 => API page 2, etc.
        api_page = page
        remaining = limit

        while remaining > 0:
            fetch_size = min(remaining, page_size)
            data = await self._graphql(
                self.PRODUCTS_QUERY,
                {"pagination": {"page": api_page, "limit": fetch_size}},
            )
            result = data["listProduct"]
            product_list = result["data"]

            if api_page == page:
                self.total_count = result.get("count", 0)

            for item in product_list:
                all_products.append(self._parse_product(item))

            remaining -= len(product_list)
            if not result.get("hasNext") or not product_list:
                break
            api_page += 1

        return all_products

    async def get_all_products(self, batch_size: int = 50) -> List[Product]:
        all_products: List[Product] = []
        api_page = 1
        self.total_count = 0

        while True:
            data = await self._graphql(
                self.PRODUCTS_QUERY,
                {"pagination": {"page": api_page, "limit": min(batch_size, 50)}},
            )
            result = data["listProduct"]
            product_list = result["data"]

            if api_page == 1:
                self.total_count = result.get("count", 0)

            for item in product_list:
                all_products.append(self._parse_product(item))

            if not result.get("hasNext") or not product_list:
                break
            api_page += 1

        return all_products

    async def get_product_by_id(self, product_id: str) -> Optional[Product]:
        data = await self._graphql(
            self.PRODUCT_BY_ID_QUERY,
            {"id": {"eq": product_id}},
        )
        products = data["listProduct"]["data"]
        if products:
            return self._parse_product(products[0])
        return None

    async def update_product(self, product_id: str, updates: Dict[str, Any]) -> bool:
        config = get_config()
        if config.dry_run:
            logger.info(f"[DRY RUN] Would update product {product_id}: {updates}")
            return True

        existing_product = await self._get_product_for_update_data(product_id)
        input_data: Dict[str, Any] = {
            "id": product_id,
            "name": updates.get("name") or existing_product.get("name") or "",
            "type": existing_product.get("type"),
            "variants": [
                self._clean_variant_for_input(variant)
                for variant in (existing_product.get("variants") or [])
                if isinstance(variant, dict)
            ],
        }
        requested_translations: Dict[str, str] = {}

        for key in (
            "shortDescription",
            "weight",
            "releaseDate",
            "brandId",
            "categoryIds",
            "tagIds",
            "salesChannelIds",
            "hiddenSalesChannelIds",
            "dynamicPriceListIds",
            "groupVariantsByVariantTypeId",
            "googleTaxonomyId",
            "productOptionSetId",
            "productVolumeDiscountId",
            "subscriptionPlanId",
            "vendorId",
            "maxQuantityPerCart",
        ):
            if key in existing_product and existing_product.get(key) is not None:
                input_data[key] = existing_product.get(key)

        base_unit = existing_product.get("baseUnit")
        if isinstance(base_unit, dict):
            cleaned_base_unit = self._clean_base_unit_for_input(base_unit)
            if cleaned_base_unit:
                input_data["baseUnit"] = cleaned_base_unit

        product_variant_types = existing_product.get("productVariantTypes")
        if isinstance(product_variant_types, list):
            input_data["productVariantTypes"] = [
                item
                for item in (
                    self._clean_product_variant_type_for_input(variant_type)
                    for variant_type in product_variant_types
                    if isinstance(variant_type, dict)
                )
                if item
            ]

        attributes = existing_product.get("attributes")
        if isinstance(attributes, list):
            input_data["attributes"] = [
                item
                for item in (
                    self._clean_product_attribute_for_input(attribute)
                    for attribute in attributes
                    if isinstance(attribute, dict)
                )
                if item
            ]

        sales_channels = existing_product.get("salesChannels")
        if isinstance(sales_channels, list):
            input_data["salesChannels"] = [
                item
                for item in (
                    self._clean_product_sales_channel_for_input(sales_channel)
                    for sales_channel in sales_channels
                    if isinstance(sales_channel, dict)
                )
                if item
            ]

        if "description" in updates:
            input_data["description"] = updates["description"]
        elif isinstance(existing_product.get("description"), str) and existing_product["description"].strip():
            input_data["description"] = existing_product["description"]

        translation_updates = updates.get("description_translations") or {}
        translation_items = self._merge_translation_items(
            existing_product.get("translations"),
            translation_updates,
        )
        if translation_items:
            input_data["translations"] = translation_items
        if translation_updates:
            requested_translations = self._normalize_translation_updates(translation_updates)
            tr_description = requested_translations.get("tr")
            if tr_description and "description" not in input_data:
                input_data["description"] = tr_description

        existing_meta = existing_product.get("metaData") or {}
        cleaned_meta_data = self._clean_meta_data_for_input(existing_meta) if isinstance(existing_meta, dict) else {}
        if cleaned_meta_data:
            input_data["metaData"] = cleaned_meta_data
        if "meta_title" in updates or "meta_description" in updates:
            meta_slug = existing_meta.get("slug")
            if not isinstance(meta_slug, str) or not meta_slug.strip():
                raise RuntimeError("Product meta slug is required for saveProduct updates")
            meta_data: Dict[str, Any] = dict(input_data.get("metaData") or {})
            meta_data["slug"] = meta_slug
            if "meta_title" in updates:
                meta_data["pageTitle"] = updates["meta_title"]
            if "meta_description" in updates:
                meta_data["description"] = updates["meta_description"]
            if meta_data:
                input_data["metaData"] = meta_data

        if not input_data.get("name") or not input_data.get("type") or not input_data.get("variants"):
            raise RuntimeError("Existing product data is incomplete for saveProduct")

        if requested_translations and "description" not in input_data:
            await self._seed_default_description_for_translation_update(product_id, input_data)

        logger.info("Sending saveProduct input keys: %s", list(input_data.keys()))
        if "metaData" in input_data:
            logger.info("saveProduct metaData keys: %s", list(input_data["metaData"].keys()))

        try:
            await self._graphql(self.SAVE_PRODUCT_MUTATION, {"input": input_data})
        except RuntimeError as exc:
            error_text = str(exc).lower()
            translation_error = (
                "translation" in error_text
                and ("accept" in error_text or "unknown argument" in error_text or "unknown field" in error_text)
            )
            if translation_error and "translations" in input_data and "description" in input_data:
                logger.warning("translations not accepted by API, retrying with default description only")
                fallback_input = {k: v for k, v in input_data.items() if k != "translations"}
                try:
                    await self._graphql(self.SAVE_PRODUCT_MUTATION, {"input": fallback_input})
                except RuntimeError as fallback_exc:
                    if not config.ikas_mcp_token.strip():
                        raise
                    logger.warning(
                        "saveProduct retry failed for %s, falling back to MCP updateProduct: %s",
                        product_id,
                        fallback_exc,
                    )
                    await self._update_product_via_mcp(
                        product_id,
                        updates,
                        existing_product,
                        mcp_token=config.ikas_mcp_token,
                    )
            elif config.ikas_mcp_token.strip():
                logger.warning("saveProduct failed for %s, retrying with MCP updateProduct: %s", product_id, exc)
                await self._update_product_via_mcp(
                    product_id,
                    updates,
                    existing_product,
                    mcp_token=config.ikas_mcp_token,
                )
            else:
                raise

        if requested_translations:
            await self.ensure_translations_persisted(product_id, requested_translations)

        logger.info(f"Product {product_id} updated successfully")
        return True

    async def get_categories(self) -> List[Dict[str, str]]:
        data = await self._graphql(self.CATEGORIES_QUERY)
        return data.get("listCategory", {}).get("data", [])

    async def test_connection(self) -> bool:
        try:
            await self.authenticate()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
