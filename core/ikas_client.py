import asyncio
import base64
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from config.settings import get_config
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

    UPDATE_PRODUCT_MUTATION = """
    mutation SaveProduct($input: ProductInput!) {
        saveProduct(input: $input) {
            id
            name
            description
            metaData { pageTitle description }
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

            for attempt in range(3):
                try:
                    response = await client.post(
                        self._config.ikas_api_url,
                        json={"query": query, "variables": variables or {}},
                        headers={"Authorization": f"Bearer {token}"},
                    )
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
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise

            raise RuntimeError("GraphQL request failed after 3 attempts")

    def _extract_translations(self, data: Dict[str, Any]) -> Dict[str, str]:
        # ikas API returns translations as list of {locale, name, description}
        raw = data.get("translations") or data.get("descriptionTranslations") or {}

        if isinstance(raw, dict):
            return {k: v for k, v in raw.items() if isinstance(v, str) and v.strip()}

        if isinstance(raw, list):
            output: Dict[str, str] = {}
            for item in raw:
                if not isinstance(item, dict):
                    continue
                locale = item.get("locale") or item.get("language")
                # ikas translations use "description" field (not "value")
                value = item.get("description") or item.get("value")
                if isinstance(locale, str) and isinstance(value, str) and value.strip():
                    output[locale.lower()] = value
            return output

        return {}

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

        input_data: Dict[str, Any] = {"id": product_id}

        if "description" in updates:
            input_data["description"] = updates["description"]
        if "description_translations" in updates:
            translations = updates["description_translations"] or {}
            tr_description = translations.get("tr")
            if tr_description:
                input_data["description"] = tr_description
            # ikas API expects translations as {locale, name?, description}
            input_data["translations"] = [
                {"locale": locale, "description": text}
                for locale, text in translations.items()
                if isinstance(text, str) and text.strip()
            ]
        if "name" in updates:
            input_data["name"] = updates["name"]
        if "meta_title" in updates or "meta_description" in updates:
            input_data["metaData"] = {}
            if "meta_title" in updates:
                input_data["metaData"]["pageTitle"] = updates["meta_title"]
            if "meta_description" in updates:
                input_data["metaData"]["description"] = updates["meta_description"]

        try:
            await self._graphql(self.UPDATE_PRODUCT_MUTATION, {"input": input_data})
        except RuntimeError as exc:
            if "translations" in input_data:
                logger.warning("translations not accepted by API, retrying with default description only")
                fallback_input = {k: v for k, v in input_data.items() if k != "translations"}
                await self._graphql(self.UPDATE_PRODUCT_MUTATION, {"input": fallback_input})
            else:
                raise

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
