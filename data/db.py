import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.models import Product, SeoScore, SeoSuggestion

DB_PATH = Path(__file__).parent.parent / "seo_optimizer.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    data JSON,
    fetched_at TIMESTAMP,
    last_analyzed TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seo_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT,
    score_data JSON,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT,
    suggestion_data JSON,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP,
    applied_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT,
    product_id TEXT,
    details JSON,
    success BOOLEAN,
    created_at TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def save_product(product: Product) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO products (id, data, fetched_at) VALUES (?, ?, ?)",
        (product.id, product.model_dump_json(), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_product(product_id: str) -> Optional[Product]:
    conn = get_connection()
    row = conn.execute("SELECT data FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if row:
        return Product.model_validate_json(row["data"])
    return None


def get_all_products() -> List[Product]:
    conn = get_connection()
    rows = conn.execute("SELECT data FROM products").fetchall()
    conn.close()
    return [Product.model_validate_json(row["data"]) for row in rows]


def save_score(score: SeoScore) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO seo_scores (product_id, score_data, created_at) VALUES (?, ?, ?)",
        (score.product_id, score.model_dump_json(), datetime.now().isoformat()),
    )
    conn.execute(
        "UPDATE products SET last_analyzed = ? WHERE id = ?",
        (datetime.now().isoformat(), score.product_id),
    )
    conn.commit()
    conn.close()


def get_latest_score(product_id: str) -> Optional[SeoScore]:
    conn = get_connection()
    row = conn.execute(
        "SELECT score_data FROM seo_scores WHERE product_id = ? ORDER BY created_at DESC LIMIT 1",
        (product_id,),
    ).fetchone()
    conn.close()
    if row:
        return SeoScore.model_validate_json(row["score_data"])
    return None


def save_suggestion(suggestion: SeoSuggestion) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO suggestions (product_id, suggestion_data, status, created_at) VALUES (?, ?, ?, ?)",
        (
            suggestion.product_id,
            suggestion.model_dump_json(),
            suggestion.status,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_pending_suggestions() -> List[SeoSuggestion]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT suggestion_data FROM suggestions WHERE status = 'pending'"
    ).fetchall()
    conn.close()
    return [SeoSuggestion.model_validate_json(row["suggestion_data"]) for row in rows]


def get_suggestions_by_product(product_id: str) -> List[SeoSuggestion]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT suggestion_data FROM suggestions WHERE product_id = ? ORDER BY created_at DESC",
        (product_id,),
    ).fetchall()
    conn.close()
    return [SeoSuggestion.model_validate_json(row["suggestion_data"]) for row in rows]


def update_suggestion_status(product_id: str, status: str) -> None:
    conn = get_connection()
    applied_at = datetime.now().isoformat() if status == "applied" else None
    conn.execute(
        "UPDATE suggestions SET status = ?, applied_at = ? WHERE product_id = ? AND status = 'pending'",
        (status, applied_at, product_id),
    )
    conn.commit()
    conn.close()


def log_operation(operation: str, product_id: str, details: dict, success: bool) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO operation_log (operation, product_id, details, success, created_at) VALUES (?, ?, ?, ?, ?)",
        (operation, product_id, json.dumps(details), success, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_operation_history(limit: int = 50) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM operation_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# Initialize database on import
init_db()
