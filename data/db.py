import json
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Iterable, List, Optional, Sequence

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

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP
);
"""


async def _configure_connection(conn: aiosqlite.Connection) -> aiosqlite.Connection:
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA temp_store=MEMORY")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


@asynccontextmanager
async def connection() -> AsyncIterator[aiosqlite.Connection]:
    async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
        await _configure_connection(conn)
        yield conn


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


async def _load_suggestions(query: str, params: Sequence[object] = ()) -> List[SeoSuggestion]:
    async with connection() as conn:
        async with conn.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
    return [SeoSuggestion.model_validate_json(row["suggestion_data"]) for row in rows]


async def init_db() -> None:
    async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()


async def save_product(product: Product) -> None:
    await save_products([product])


async def save_products(products: Sequence[Product]) -> None:
    if not products:
        return

    fetched_at = _now_iso()
    rows = _serialize_products(products, fetched_at)
    async with connection() as conn:
        await conn.executemany(
            """
            INSERT INTO products (id, data, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                data = excluded.data,
                fetched_at = excluded.fetched_at
            """,
            rows,
        )
        await conn.commit()


async def get_product(product_id: str) -> Optional[Product]:
    async with connection() as conn:
        async with conn.execute(
            "SELECT data FROM products WHERE id = ?",
            (product_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return Product.model_validate_json(row["data"])
    return None


async def get_all_products() -> List[Product]:
    async with connection() as conn:
        async with conn.execute("SELECT data FROM products") as cursor:
            rows = await cursor.fetchall()
    return [Product.model_validate_json(row["data"]) for row in rows]


async def clear_all_data() -> dict[str, int]:
    async with connection() as conn:
        async with conn.execute("SELECT COUNT(*) AS count FROM products") as cur:
            row = await cur.fetchone()
            products_count = int(row["count"]) if row else 0
        async with conn.execute("SELECT COUNT(*) AS count FROM seo_scores") as cur:
            row = await cur.fetchone()
            scores_count = int(row["count"]) if row else 0
        async with conn.execute("SELECT COUNT(*) AS count FROM suggestions") as cur:
            row = await cur.fetchone()
            suggestions_count = int(row["count"]) if row else 0
        async with conn.execute("SELECT COUNT(*) AS count FROM operation_log") as cur:
            row = await cur.fetchone()
            logs_count = int(row["count"]) if row else 0

        await conn.execute("DELETE FROM products")
        await conn.execute("DELETE FROM seo_scores")
        await conn.execute("DELETE FROM suggestions")
        await conn.execute("DELETE FROM operation_log")
        await conn.commit()

    return {
        "products": products_count,
        "seo_scores": scores_count,
        "suggestions": suggestions_count,
        "operation_log": logs_count,
    }


async def save_score(score: SeoScore) -> None:
    await save_scores([score])


async def save_scores(scores: Sequence[SeoScore]) -> None:
    if not scores:
        return

    created_at = _now_iso()
    score_rows = _serialize_scores(scores, created_at)
    product_rows = [(created_at, score.product_id) for score in scores]

    async with connection() as conn:
        await conn.executemany(
            "INSERT INTO seo_scores (product_id, score_data, created_at) VALUES (?, ?, ?)",
            score_rows,
        )
        await conn.executemany(
            "UPDATE products SET last_analyzed = ? WHERE id = ?",
            product_rows,
        )
        await conn.commit()


async def get_latest_score(product_id: str) -> Optional[SeoScore]:
    async with connection() as conn:
        async with conn.execute(
            "SELECT score_data FROM seo_scores WHERE product_id = ? ORDER BY created_at DESC LIMIT 1",
            (product_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return SeoScore.model_validate_json(row["score_data"])
    return None


async def save_suggestion(suggestion: SeoSuggestion) -> None:
    created_at = _now_iso()
    async with connection() as conn:
        await conn.execute(
            "INSERT INTO suggestions (product_id, suggestion_data, status, created_at) VALUES (?, ?, ?, ?)",
            (
                suggestion.product_id,
                suggestion.model_dump_json(),
                suggestion.status,
                created_at,
            ),
        )
        await conn.commit()


async def update_latest_pending_suggestion(suggestion: SeoSuggestion) -> None:
    async with connection() as conn:
        await conn.execute(
            """
            UPDATE suggestions
            SET suggestion_data = ?, status = ?
            WHERE id = (
                SELECT id
                FROM suggestions
                WHERE product_id = ? AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
            )
            """,
            (
                suggestion.model_dump_json(),
                suggestion.status,
                suggestion.product_id,
            ),
        )
        await conn.commit()


async def save_or_update_pending_suggestion(suggestion: SeoSuggestion) -> None:
    created_at = _now_iso()
    async with connection() as conn:
        async with conn.execute(
            """
            UPDATE suggestions
            SET suggestion_data = ?, status = ?
            WHERE id = (
                SELECT id
                FROM suggestions
                WHERE product_id = ? AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
            )
            """,
            (
                suggestion.model_dump_json(),
                suggestion.status,
                suggestion.product_id,
            ),
        ) as cursor:
            rowcount = cursor.rowcount

        if rowcount == 0:
            await conn.execute(
                "INSERT INTO suggestions (product_id, suggestion_data, status, created_at) VALUES (?, ?, ?, ?)",
                (
                    suggestion.product_id,
                    suggestion.model_dump_json(),
                    suggestion.status,
                    created_at,
                ),
            )
        await conn.commit()


async def get_pending_suggestions() -> List[SeoSuggestion]:
    return await get_suggestions_by_status("pending")


async def get_approved_suggestions() -> List[SeoSuggestion]:
    return await get_suggestions_by_status("approved")


async def get_suggestions_by_status(status: str) -> List[SeoSuggestion]:
    return await _load_suggestions(
        "SELECT suggestion_data FROM suggestions WHERE status = ? ORDER BY created_at DESC",
        (status,),
    )


async def get_suggestions_by_product(product_id: str) -> List[SeoSuggestion]:
    return await _load_suggestions(
        "SELECT suggestion_data FROM suggestions WHERE product_id = ? ORDER BY created_at DESC",
        (product_id,),
    )


async def get_latest_suggestion_by_product(
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

    async with connection() as conn:
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()

    if row:
        return SeoSuggestion.model_validate_json(row["suggestion_data"])
    return None


async def count_suggestions(status: str) -> int:
    async with connection() as conn:
        async with conn.execute(
            "SELECT COUNT(*) AS count FROM suggestions WHERE status = ?",
            (status,),
        ) as cursor:
            row = await cursor.fetchone()
    return int(row["count"]) if row else 0


async def get_suggestion_product_ids(status: str) -> set[str]:
    async with connection() as conn:
        async with conn.execute(
            "SELECT DISTINCT product_id FROM suggestions WHERE status = ?",
            (status,),
        ) as cursor:
            rows = await cursor.fetchall()
    return {row["product_id"] for row in rows}


async def update_suggestion_status(product_id: str, status: str) -> None:
    applied_at = _now_iso() if status == "applied" else None
    async with connection() as conn:
        await conn.execute(
            "UPDATE suggestions SET status = ?, applied_at = ? WHERE product_id = ? AND status = 'pending'",
            (status, applied_at, product_id),
        )
        await conn.commit()


async def log_operation(operation: str, product_id: str, details: dict, success: bool) -> None:
    async with connection() as conn:
        await conn.execute(
            "INSERT INTO operation_log (operation, product_id, details, success, created_at) VALUES (?, ?, ?, ?, ?)",
            (operation, product_id, json.dumps(details, ensure_ascii=False), success, _now_iso()),
        )
        await conn.commit()


async def get_operation_history(limit: int = 50) -> list:
    async with connection() as conn:
        async with conn.execute(
            "SELECT * FROM operation_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Settings — synchronous helpers (sqlite3) so they can be called from
# synchronous config loading code without requiring a running event loop.
# ---------------------------------------------------------------------------

def _sync_db_connection() -> sqlite3.Connection:
    """Open a synchronous SQLite connection for settings operations."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _ensure_settings_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP
        )
        """
    )
    conn.commit()


def get_all_settings_sync() -> dict[str, str]:
    """Return all persisted settings as a key→value dict (sync)."""
    try:
        conn = _sync_db_connection()
        _ensure_settings_table(conn)
        cursor = conn.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        conn.close()
        return {row["key"]: row["value"] for row in rows}
    except Exception:
        return {}


def set_settings_sync(values: dict[str, str]) -> None:
    """Upsert multiple key→value pairs into the settings table (sync)."""
    if not values:
        return
    now = datetime.now().isoformat()
    conn = _sync_db_connection()
    _ensure_settings_table(conn)
    conn.executemany(
        """
        INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        [(k, v, now) for k, v in values.items()],
    )
    conn.commit()
    conn.close()
