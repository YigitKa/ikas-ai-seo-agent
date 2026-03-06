import asyncio
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
                metaData { title description }
                tags
                categories { name }
                productVariants { price sku }
                status
            }
            pagination { totalCount page pageSize }
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
                metaData { title description }
                tags
                categories { name }
                productVariants { price sku }
                status
            }
        }
    }
    """

    UPDATE_PRODUCT_MUTATION = """
    mutation UpdateProduct($input: UpdateProductInput!) {
        updateProduct(input: $input) {
            id
            name
            description
            metaData { title description }
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
        self._semaphore = asyncio.Semaphore(5)
        self._client: Optional[httpx.AsyncClient] = None

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
                    json={
                        "grant_type": "client_credentials",
                        "client_id": self._config.ikas_client_id,
                        "client_secret": self._config.ikas_client_secret,
                    },
                )
                response.raise_for_status()
                data = response.json()
                self._token = data["access_token"]
                logger.info("ikas authentication successful")
                return self._token
            except httpx.HTTPError as e:
                logger.warning(f"Auth attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        raise RuntimeError("Authentication failed after 3 attempts")

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

    def _parse_product(self, data: Dict[str, Any]) -> Product:
        variants = data.get("productVariants") or []
        first_variant = variants[0] if variants else {}
        categories = data.get("categories") or []
        meta = data.get("metaData") or {}

        return Product(
            id=data["id"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            meta_title=meta.get("title"),
            meta_description=meta.get("description"),
            tags=data.get("tags") or [],
            category=categories[0]["name"] if categories else None,
            price=first_variant.get("price"),
            sku=first_variant.get("sku"),
            status=data.get("status", "active"),
        )

    async def get_products(self, limit: int = 50, offset: int = 0) -> List[Product]:
        all_products: List[Product] = []
        page = 1
        page_size = min(limit, 50)

        while True:
            data = await self._graphql(
                self.PRODUCTS_QUERY,
                {"pagination": {"page": page, "pageSize": page_size}},
            )
            product_list = data["listProduct"]["data"]
            pagination = data["listProduct"]["pagination"]

            for item in product_list:
                all_products.append(self._parse_product(item))

            total = pagination["totalCount"]
            if len(all_products) >= total or len(all_products) >= limit:
                break
            page += 1

        return all_products[:limit]

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
        if "name" in updates:
            input_data["name"] = updates["name"]
        if "meta_title" in updates or "meta_description" in updates:
            input_data["metaData"] = {}
            if "meta_title" in updates:
                input_data["metaData"]["title"] = updates["meta_title"]
            if "meta_description" in updates:
                input_data["metaData"]["description"] = updates["meta_description"]

        await self._graphql(self.UPDATE_PRODUCT_MUTATION, {"input": input_data})
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
