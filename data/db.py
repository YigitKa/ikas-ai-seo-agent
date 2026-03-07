import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence

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

CREATE INDEX IF NOT EXISTS idx_seo_scores_product_created_at
ON seo_scores(product_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_suggestions_status_created_at
ON suggestions(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_suggestions_product_created_at
ON suggestions(product_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_operation_log_created_at
ON operation_log(created_at DESC);
"""


def _configure_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    return _configure_connection(conn)


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now().isoformat()


def _serialize_products(products: Iterable[Product], fetched_at: str) -> list[tuple[str, str, str]]:
    return [
        (product.id, product.model_dump_json(), fetched_at)
        for product in products
    ]


def _serialize_scores(scores: Iterable[SeoScore], created_at: str) -> list[tuple[str, str, str]]:
    return [
        (score.product_id, score.model_dump_json(), created_at)
        for score in scores
    ]


def _load_suggestions(query: str, params: Sequence[object] = ()) -> List[SeoSuggestion]:
    with connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [SeoSuggestion.model_validate_json(row["suggestion_data"]) for row in rows]


def init_db() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def save_product(product: Product) -> None:
    save_products([product])


def save_products(products: Sequence[Product]) -> None:
    if not products:
        return

    fetched_at = _now_iso()
    rows = _serialize_products(products, fetched_at)
    with connection() as conn:
        conn.executemany(
            """
            INSERT INTO products (id, data, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data = excluded.data,
                fetched_at = excluded.fetched_at
            """,
            rows,
        )
        conn.commit()


def get_product(product_id: str) -> Optional[Product]:
    with connection() as conn:
        row = conn.execute(
            "SELECT data FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
    if row:
        return Product.model_validate_json(row["data"])
    return None


def get_all_products() -> List[Product]:
    with connection() as conn:
        rows = conn.execute("SELECT data FROM products").fetchall()
    return [Product.model_validate_json(row["data"]) for row in rows]


def save_score(score: SeoScore) -> None:
    save_scores([score])


def save_scores(scores: Sequence[SeoScore]) -> None:
    if not scores:
        return

    created_at = _now_iso()
    score_rows = _serialize_scores(scores, created_at)
    product_rows = [(created_at, score.product_id) for score in scores]

    with connection() as conn:
        conn.executemany(
            "INSERT INTO seo_scores (product_id, score_data, created_at) VALUES (?, ?, ?)",
            score_rows,
        )
        conn.executemany(
            "UPDATE products SET last_analyzed = ? WHERE id = ?",
            product_rows,
        )
        conn.commit()


def get_latest_score(product_id: str) -> Optional[SeoScore]:
    with connection() as conn:
        row = conn.execute(
            "SELECT score_data FROM seo_scores WHERE product_id = ? ORDER BY created_at DESC LIMIT 1",
            (product_id,),
        ).fetchone()
    if row:
        return SeoScore.model_validate_json(row["score_data"])
    return None


def save_suggestion(suggestion: SeoSuggestion) -> None:
    created_at = _now_iso()
    with connection() as conn:
        conn.execute(
            "INSERT INTO suggestions (product_id, suggestion_data, status, created_at) VALUES (?, ?, ?, ?)",
            (
                suggestion.product_id,
                suggestion.model_dump_json(),
                suggestion.status,
                created_at,
            ),
        )
        conn.commit()


def get_pending_suggestions() -> List[SeoSuggestion]:
    return get_suggestions_by_status("pending")


def get_approved_suggestions() -> List[SeoSuggestion]:
    return get_suggestions_by_status("approved")


def get_suggestions_by_status(status: str) -> List[SeoSuggestion]:
    return _load_suggestions(
        "SELECT suggestion_data FROM suggestions WHERE status = ? ORDER BY created_at DESC",
        (status,),
    )


def get_suggestions_by_product(product_id: str) -> List[SeoSuggestion]:
    return _load_suggestions(
        "SELECT suggestion_data FROM suggestions WHERE product_id = ? ORDER BY created_at DESC",
        (product_id,),
    )


def get_latest_suggestion_by_product(
    product_id: str,
    statuses: Sequence[str] | None = None,
) -> Optional[SeoSuggestion]:
    query = "SELECT suggestion_data FROM suggestions WHERE product_id = ?"
    params: list[object] = [product_id]

    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        query += f" AND status IN ({placeholders})"
        params.extend(statuses)

    query += " ORDER BY created_at DESC LIMIT 1"

    with connection() as conn:
        row = conn.execute(query, params).fetchone()

    if row:
        return SeoSuggestion.model_validate_json(row["suggestion_data"])
    return None


def count_suggestions(status: str) -> int:
    with connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM suggestions WHERE status = ?",
            (status,),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_suggestion_product_ids(status: str) -> set[str]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT product_id FROM suggestions WHERE status = ?",
            (status,),
        ).fetchall()
    return {row["product_id"] for row in rows}


def update_suggestion_status(product_id: str, status: str) -> None:
    applied_at = _now_iso() if status == "applied" else None
    with connection() as conn:
        conn.execute(
            "UPDATE suggestions SET status = ?, applied_at = ? WHERE product_id = ? AND status = 'pending'",
            (status, applied_at, product_id),
        )
        conn.commit()


def log_operation(operation: str, product_id: str, details: dict, success: bool) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO operation_log (operation, product_id, details, success, created_at) VALUES (?, ?, ?, ?, ?)",
            (operation, product_id, json.dumps(details, ensure_ascii=False), success, _now_iso()),
        )
        conn.commit()


def get_operation_history(limit: int = 50) -> list:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM operation_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


# Initialize database on import
init_db()
