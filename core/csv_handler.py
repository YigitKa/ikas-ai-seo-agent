from pathlib import Path
from typing import List

import pandas as pd

from core.models import Product, SeoSuggestion


def import_products_from_csv(file_path: str) -> List[Product]:
    df = pd.read_csv(file_path)

    column_map = {
        "id": "id",
        "name": "name",
        "title": "name",
        "description": "description",
        "meta_title": "meta_title",
        "meta_description": "meta_description",
        "tags": "tags",
        "category": "category",
        "price": "price",
        "sku": "sku",
        "status": "status",
    }

    products = []
    for _, row in df.iterrows():
        data = {}
        for csv_col, model_field in column_map.items():
            if csv_col in df.columns:
                val = row[csv_col]
                if pd.isna(val):
                    val = None
                if model_field == "tags" and isinstance(val, str):
                    val = [t.strip() for t in val.split(",") if t.strip()]
                data[model_field] = val

        if "id" not in data or not data["id"]:
            data["id"] = f"csv_{_}"
        if "name" not in data:
            data["name"] = ""
        if "description" not in data:
            data["description"] = ""
        if "tags" not in data:
            data["tags"] = []

        products.append(Product(**data))

    return products


def export_suggestions_to_csv(suggestions: List[SeoSuggestion], output_path: str) -> str:
    rows = []
    for s in suggestions:
        rows.append({
            "product_id": s.product_id,
            "original_name": s.original_name,
            "suggested_name": s.suggested_name,
            "original_description": s.original_description[:200],
            "suggested_description": s.suggested_description[:200],
            "original_meta_title": s.original_meta_title,
            "suggested_meta_title": s.suggested_meta_title,
            "original_meta_description": s.original_meta_description,
            "suggested_meta_description": s.suggested_meta_description,
            "status": s.status,
        })

    df = pd.DataFrame(rows)
    path = Path(output_path)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path.resolve())
