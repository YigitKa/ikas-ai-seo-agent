import asyncio
import json
import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, List, Optional, Sequence
from uuid import uuid4

from core.models import LlmsEntry, LlmsJob, Product, SeoScore, SeoSuggestion

DB_PATH = Path(__file__).parent.parent / "seo_optimizer.db"

# ── Connection pool ─────────────────────────────────────────────────────────
_POOL_SIZE = 5
_pool: asyncio.Queue[aiosqlite.Connection] | None = None
_pool_initialized = False

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

CREATE TABLE IF NOT EXISTS llms_jobs (
    id TEXT PRIMARY KEY,
    status TEXT,
    total_count INTEGER,
    processed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_error TEXT,
    options JSON
);

CREATE TABLE IF NOT EXISTS llms_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    product_id TEXT,
    summary TEXT,
    status TEXT,
    error TEXT,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES llms_jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_seo_scores_product_created_at
ON seo_scores(product_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_suggestions_status_created_at
ON suggestions(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_suggestions_product_created_at
ON suggestions(product_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_operation_log_created_at
ON operation_log(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llms_entries_status
ON llms_entries(status);

CREATE INDEX IF NOT EXISTS idx_llms_entries_product
ON llms_entries(product_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_llms_entries_job_product
ON llms_entries(job_id, product_id);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batch_jobs (
    id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'idle',
    config_json JSON,
    total_count INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    avg_score_before REAL DEFAULT 0,
    avg_score_after REAL DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT
);

CREATE TABLE IF NOT EXISTS batch_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    product_id TEXT,
    product_name TEXT,
    status TEXT DEFAULT 'pending',
    score_before INTEGER,
    score_after INTEGER,
    rollback_data JSON,
    suggestion_data JSON,
    skip_reason TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES batch_jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_batch_items_job ON batch_items(job_id);
CREATE INDEX IF NOT EXISTS idx_batch_items_product ON batch_items(product_id);

CREATE TABLE IF NOT EXISTS daily_score_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT,
    total_score INTEGER,
    seo_score INTEGER,
    geo_score INTEGER,
    aeo_score INTEGER,
    title_score INTEGER,
    description_score INTEGER,
    english_description_score INTEGER,
    meta_score INTEGER,
    meta_desc_score INTEGER,
    keyword_score INTEGER,
    content_quality_score INTEGER,
    technical_seo_score INTEGER,
    readability_score INTEGER,
    ai_citability_score INTEGER,
    issues_count INTEGER DEFAULT 0,
    created_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_snapshots_date_product
ON daily_score_snapshots(snapshot_date, product_id);

CREATE INDEX IF NOT EXISTS idx_daily_snapshots_date
ON daily_score_snapshots(snapshot_date);

CREATE TABLE IF NOT EXISTS score_change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    score_before INTEGER,
    score_after INTEGER,
    delta INTEGER,
    job_id TEXT,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_score_change_log_created_at
ON score_change_log(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_score_change_log_product
ON score_change_log(product_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_score_change_log_job
ON score_change_log(job_id);
"""


async def _configure_connection(conn: aiosqlite.Connection) -> aiosqlite.Connection:
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA temp_store=MEMORY")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def _create_connection() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(str(DB_PATH), timeout=30)
    await _configure_connection(conn)
    return conn


async def _init_pool() -> None:
    global _pool, _pool_initialized
    if _pool_initialized:
        await close_pool()
    _pool = asyncio.Queue(maxsize=_POOL_SIZE)
    for _ in range(_POOL_SIZE):
        conn = await _create_connection()
        await _pool.put(conn)
    _pool_initialized = True


async def close_pool() -> None:
    """Close all pooled connections (call at shutdown)."""
    global _pool, _pool_initialized
    if _pool is None:
        return
    while not _pool.empty():
        conn = _pool.get_nowait()
        await conn.close()
    _pool_initialized = False
    _pool = None


@asynccontextmanager
async def connection() -> AsyncIterator[aiosqlite.Connection]:
    if not _pool_initialized or _pool is None:
        # Fallback for tests or before pool init
        async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
            await _configure_connection(conn)
            yield conn
        return

    conn = await _pool.get()
    try:
        yield conn
    finally:
        await _pool.put(conn)


@asynccontextmanager
async def get_connection() -> AsyncIterator[aiosqlite.Connection]:
    """Backward-compatible async connection helper."""
    async with connection() as conn:
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
    suggestions: list[SeoSuggestion] = []
    for row in rows:
        suggestion = SeoSuggestion.model_validate_json(row["suggestion_data"])
        status = row["status"] if "status" in row.keys() else None
        if isinstance(status, str) and status:
            suggestion = suggestion.model_copy(update={"status": status})
        suggestions.append(suggestion)
    return suggestions


async def init_db() -> None:
    async with aiosqlite.connect(str(DB_PATH), timeout=30) as conn:
        await conn.executescript(SCHEMA)
        # Migrations for existing databases
        try:
            await conn.execute("ALTER TABLE batch_items ADD COLUMN suggestion_data JSON")
        except Exception:
            pass  # Column already exists
        await conn.commit()
    await _init_pool()


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


async def get_products_by_ids(product_ids: Sequence[str]) -> dict[str, Product]:
    """Return products keyed by ID in a single query."""
    if not product_ids:
        return {}
    placeholders = ",".join("?" for _ in product_ids)
    result: dict[str, Product] = {}
    async with connection() as conn:
        async with conn.execute(
            f"SELECT id, data FROM products WHERE id IN ({placeholders})",
            list(product_ids),
        ) as cursor:
            async for row in cursor:
                result[row["id"]] = Product.model_validate_json(row["data"])
    return result


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


async def get_latest_scores_for_products(product_ids: Sequence[str]) -> dict[str, SeoScore]:
    """Return the latest SeoScore for each product_id in a single query."""
    if not product_ids:
        return {}

    placeholders = ",".join("?" for _ in product_ids)
    query = f"""
        SELECT s.product_id, s.score_data
        FROM seo_scores s
        INNER JOIN (
            SELECT product_id, MAX(created_at) AS max_created
            FROM seo_scores
            WHERE product_id IN ({placeholders})
            GROUP BY product_id
        ) latest ON s.product_id = latest.product_id AND s.created_at = latest.max_created
    """
    result: dict[str, SeoScore] = {}
    async with connection() as conn:
        async with conn.execute(query, list(product_ids)) as cursor:
            async for row in cursor:
                result[row["product_id"]] = SeoScore.model_validate_json(row["score_data"])
    return result


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
        "SELECT suggestion_data, status FROM suggestions WHERE status = ? ORDER BY created_at DESC",
        (status,),
    )


async def get_suggestions_by_product(product_id: str) -> List[SeoSuggestion]:
    return await _load_suggestions(
        "SELECT suggestion_data, status FROM suggestions WHERE product_id = ? ORDER BY created_at DESC",
        (product_id,),
    )


async def get_latest_suggestion_by_product(
    product_id: str,
    statuses: Sequence[str] | None = None,
) -> Optional[SeoSuggestion]:
    query = "SELECT suggestion_data, status FROM suggestions WHERE product_id = ?"
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
        suggestion = SeoSuggestion.model_validate_json(row["suggestion_data"])
        status = row["status"] if "status" in row.keys() else None
        if isinstance(status, str) and status:
            suggestion = suggestion.model_copy(update={"status": status})
        return suggestion
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


async def get_all_settings() -> dict[str, str]:
    """Return all persisted settings as a key→value dict."""
    try:
        async with connection() as conn:
            async with conn.execute("SELECT key, value FROM settings") as cursor:
                rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}
    except Exception:
        return {}


async def set_settings(values: dict[str, str]) -> None:
    """Upsert multiple key→value pairs into the settings table."""
    if not values:
        return

    now = datetime.now().isoformat()
    async with connection() as conn:
        await conn.executemany(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            [(k, v, now) for k, v in values.items()],
        )
        await conn.commit()


# ── llms.txt storage helpers ───────────────────────────────────────────────────


def _row_to_llms_job(row) -> LlmsJob:
    return LlmsJob(
        id=row["id"],
        status=row["status"],
        total_count=int(row["total_count"] or 0),
        processed_count=int(row["processed_count"] or 0),
        failed_count=int(row["failed_count"] or 0),
        skipped_count=int(row["skipped_count"] or 0),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        last_error=row["last_error"],
        options=json.loads(row["options"] or "{}"),
    )


def _row_to_llms_entry(row) -> LlmsEntry:
    return LlmsEntry(
        id=int(row["id"]),
        job_id=row["job_id"],
        product_id=row["product_id"],
        summary=row["summary"] or "",
        status=row["status"],
        error=row["error"] or "",
        tokens_input=int(row["tokens_input"] or 0),
        tokens_output=int(row["tokens_output"] or 0),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


async def get_llms_processed_product_ids() -> set[str]:
    async with connection() as conn:
        async with conn.execute(
            "SELECT DISTINCT product_id FROM llms_entries WHERE status = 'done'"
        ) as cursor:
            rows = await cursor.fetchall()
    return {row["product_id"] for row in rows}


async def get_llms_latest_job(statuses: Sequence[str] | None = None) -> Optional[LlmsJob]:
    query = "SELECT * FROM llms_jobs"
    params: list[Any] = []
    if statuses:
        placeholders = ", ".join("?" for _ in statuses)
        query += f" WHERE status IN ({placeholders})"
        params.extend(statuses)
    query += " ORDER BY created_at DESC LIMIT 1"

    async with connection() as conn:
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
    return _row_to_llms_job(row) if row else None


async def get_llms_job(job_id: str) -> Optional[LlmsJob]:
    async with connection() as conn:
        async with conn.execute("SELECT * FROM llms_jobs WHERE id = ?", (job_id,)) as cursor:
            row = await cursor.fetchone()
    return _row_to_llms_job(row) if row else None


async def create_llms_job(product_ids: Sequence[str], options: dict[str, Any] | None = None) -> LlmsJob:
    if not product_ids:
        raise ValueError("No products to process for llms.txt")

    now = _now_iso()
    job_id = str(uuid4())
    options_json = json.dumps(options or {})

    entry_rows = [
        (job_id, pid, "", "pending", "", 0, 0, now, now)
        for pid in product_ids
    ]

    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO llms_jobs (
                id, status, total_count, processed_count, failed_count, skipped_count,
                created_at, updated_at, last_error, options
            ) VALUES (?, 'queued', ?, 0, 0, 0, ?, ?, NULL, ?)
            """,
            (job_id, len(product_ids), now, now, options_json),
        )
        await conn.executemany(
            """
            INSERT INTO llms_entries (
                job_id, product_id, summary, status, error,
                tokens_input, tokens_output, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            entry_rows,
        )
        await conn.commit()

    return LlmsJob(
        id=job_id,
        status="queued",
        total_count=len(product_ids),
        processed_count=0,
        failed_count=0,
        skipped_count=0,
        created_at=datetime.fromisoformat(now),
        updated_at=datetime.fromisoformat(now),
        last_error=None,
        options=options or {},
    )


async def update_llms_job_status(job_id: str, status: str, last_error: str | None = None) -> None:
    async with connection() as conn:
        await conn.execute(
            "UPDATE llms_jobs SET status = ?, last_error = ?, updated_at = ? WHERE id = ?",
            (status, last_error, _now_iso(), job_id),
        )
        await conn.commit()


async def refresh_llms_job_counters(job_id: str) -> Optional[LlmsJob]:
    async with connection() as conn:
        async with conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS processed_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) AS processing_count,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending_count
            FROM llms_entries
            WHERE job_id = ?
            """,
            (job_id,),
            ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        processed = int(row["processed_count"] or 0)
        failed = int(row["failed_count"] or 0)
        skipped = 0
        await conn.execute(
            """
            UPDATE llms_jobs
            SET processed_count = ?, failed_count = ?, skipped_count = ?, updated_at = ?
            WHERE id = ?
            """,
            (processed, failed, skipped, _now_iso(), job_id),
        )
        await conn.commit()

    return await get_llms_job(job_id)


async def claim_next_llms_entry(job_id: str) -> Optional[LlmsEntry]:
    async with connection() as conn:
        async with conn.execute(
            """
            SELECT * FROM llms_entries
            WHERE job_id = ? AND status = 'pending'
            ORDER BY id ASC
            LIMIT 1
            """,
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        now = _now_iso()
        await conn.execute(
            "UPDATE llms_entries SET status = 'processing', updated_at = ? WHERE id = ?",
            (now, row["id"]),
        )
        await conn.commit()

    entry = _row_to_llms_entry(row)
    return entry.model_copy(update={"status": "processing"})


async def reset_llms_processing_entries(job_id: str) -> None:
    """Reset entries stuck in 'processing' back to 'pending' (e.g., after pause/stop)."""
    async with connection() as conn:
        await conn.execute(
            "UPDATE llms_entries SET status = 'pending', updated_at = ? WHERE job_id = ? AND status = 'processing'",
            (_now_iso(), job_id),
        )
        await conn.commit()


async def save_llms_entry_success(entry_id: int, summary: str, tokens_input: int = 0, tokens_output: int = 0) -> None:
    async with connection() as conn:
        await conn.execute(
            """
            UPDATE llms_entries
            SET summary = ?, status = 'done', error = '', tokens_input = ?, tokens_output = ?, updated_at = ?
            WHERE id = ?
            """,
            (summary, tokens_input, tokens_output, _now_iso(), entry_id),
        )
        await conn.commit()


async def save_llms_entry_failure(entry_id: int, error: str) -> None:
    async with connection() as conn:
        await conn.execute(
            """
            UPDATE llms_entries
            SET status = 'failed', error = ?, updated_at = ?
            WHERE id = ?
            """,
            (error[:400], _now_iso(), entry_id),
        )
        await conn.commit()


async def get_llms_recent_entries(status: str, limit: int = 10) -> list[LlmsEntry]:
    async with connection() as conn:
        async with conn.execute(
            """
            SELECT * FROM llms_entries
            WHERE status = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (status, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [_row_to_llms_entry(row) for row in rows]


async def ensure_manual_llms_job() -> str:
    """Ensure a reusable 'manual' llms job exists (used for single re-generations)."""
    job_id = "manual"
    now = _now_iso()
    async with connection() as conn:
        async with conn.execute("SELECT id FROM llms_jobs WHERE id = ?", (job_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            return job_id
        await conn.execute(
            """
            INSERT INTO llms_jobs (
                id, status, total_count, processed_count, failed_count, skipped_count,
                created_at, updated_at, last_error, options
            ) VALUES (?, 'completed', 0, 0, 0, 0, ?, ?, NULL, ?)
            """,
            (job_id, now, now, json.dumps({"source": "manual"})),
        )
        await conn.commit()
    return job_id


async def upsert_llms_entry_summary(
    product_id: str,
    summary: str,
    job_id: str = "manual",
    tokens_input: int = 0,
    tokens_output: int = 0,
) -> LlmsEntry:
    """Insert or update a summary for a single product (manual regen)."""
    now = _now_iso()
    async with connection() as conn:
        async with conn.execute(
            """
            SELECT * FROM llms_entries
            WHERE product_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (product_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            await conn.execute(
                """
                UPDATE llms_entries
                SET summary = ?, status = 'done', error = '', tokens_input = ?, tokens_output = ?, updated_at = ?, job_id = ?
                WHERE id = ?
                """,
                (summary, tokens_input, tokens_output, now, job_id, row["id"]),
            )
            entry_id = int(row["id"])
        else:
            await conn.execute(
                """
                INSERT INTO llms_entries (
                    job_id, product_id, summary, status, error,
                    tokens_input, tokens_output, created_at, updated_at
                ) VALUES (?, ?, ?, 'done', '', ?, ?, ?, ?)
                """,
                (job_id, product_id, summary, tokens_input, tokens_output, now, now),
            )
            async with conn.execute("SELECT last_insert_rowid() AS id") as cur:
                entry_id = int((await cur.fetchone())["id"])

        await conn.commit()

    # return latest stored row
    async with connection() as conn:
        async with conn.execute("SELECT * FROM llms_entries WHERE id = ?", (entry_id,)) as cursor:
            stored = await cursor.fetchone()
    return _row_to_llms_entry(stored)


async def get_llms_entries(status: str, limit: int | None = None) -> list[LlmsEntry]:
    query = """
        SELECT * FROM llms_entries
        WHERE status = ?
        ORDER BY updated_at DESC
    """
    params: list[Any] = [status]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    async with connection() as conn:
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
    return [_row_to_llms_entry(row) for row in rows]


async def get_llms_latest_summaries_map() -> dict[str, LlmsEntry]:
    """Return latest completed summary per product."""
    async with connection() as conn:
        async with conn.execute(
            "SELECT * FROM llms_entries WHERE status = 'done' ORDER BY updated_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
    latest: dict[str, LlmsEntry] = {}
    for row in rows:
        product_id = row["product_id"]
        if product_id not in latest:
            latest[product_id] = _row_to_llms_entry(row)
    return latest


async def get_llms_unprocessed_products(limit: int = 20) -> list[Product]:
    processed_ids = await get_llms_processed_product_ids()
    placeholders = ", ".join("?" for _ in processed_ids) if processed_ids else ""
    query = "SELECT data FROM products"
    params: list[Any] = []
    if processed_ids:
        query += f" WHERE id NOT IN ({placeholders})"
        params.extend(processed_ids)
    query += " ORDER BY fetched_at DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    async with connection() as conn:
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
    return [Product.model_validate_json(row["data"]) for row in rows]


async def get_llms_dashboard_counts() -> dict[str, int]:
    async with connection() as conn:
        async with conn.execute("SELECT COUNT(*) AS count FROM products") as cursor:
            total_row = await cursor.fetchone()
        async with conn.execute(
            "SELECT COUNT(DISTINCT product_id) AS count FROM llms_entries WHERE status = 'done'"
        ) as cursor:
            processed_row = await cursor.fetchone()
        async with conn.execute(
            "SELECT COUNT(*) AS count FROM llms_entries WHERE status IN ('pending','processing')"
        ) as cursor:
            pending_row = await cursor.fetchone()
        async with conn.execute(
            "SELECT COUNT(*) AS count FROM llms_entries WHERE status = 'failed'"
        ) as cursor:
            failed_row = await cursor.fetchone()

    total = int(total_row["count"] or 0) if total_row else 0
    processed = int(processed_row["count"] or 0) if processed_row else 0
    pending = int(pending_row["count"] or 0) if pending_row else 0
    failed = int(failed_row["count"] or 0) if failed_row else 0
    unprocessed = max(total - processed, 0)
    return {
        "total_products": total,
        "processed": processed,
        "pending": pending,
        "failed": failed,
        "unprocessed": unprocessed,
    }


# ── Batch job storage helpers ──────────────────────────────────────────────────


def _row_to_batch_job(row) -> dict:
    return {
        "id": row["id"],
        "status": row["status"],
        "config": json.loads(row["config_json"] or "{}"),
        "total_count": int(row["total_count"] or 0),
        "processed_count": int(row["processed_count"] or 0),
        "skipped_count": int(row["skipped_count"] or 0),
        "failed_count": int(row["failed_count"] or 0),
        "avg_score_before": float(row["avg_score_before"] or 0),
        "avg_score_after": float(row["avg_score_after"] or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
        "error": row["error"],
    }


def _row_to_batch_item(row) -> dict:
    sd = None
    try:
        if row["suggestion_data"]:
            sd = json.loads(row["suggestion_data"])
    except (KeyError, json.JSONDecodeError):
        pass
    return {
        "id": int(row["id"]),
        "job_id": row["job_id"],
        "product_id": row["product_id"],
        "product_name": row["product_name"] or "",
        "status": row["status"],
        "score_before": int(row["score_before"]) if row["score_before"] is not None else None,
        "score_after": int(row["score_after"]) if row["score_after"] is not None else None,
        "has_rollback": bool(row["rollback_data"]),
        "skip_reason": row["skip_reason"],
        "suggestion_data": sd,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def create_batch_job(job_id: str, config_json: str) -> None:
    now = _now_iso()
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO batch_jobs (id, status, config_json, created_at, updated_at)
            VALUES (?, 'idle', ?, ?, ?)
            """,
            (job_id, config_json, now, now),
        )
        await conn.commit()


async def get_batch_job(job_id: str) -> dict | None:
    async with connection() as conn:
        async with conn.execute("SELECT * FROM batch_jobs WHERE id = ?", (job_id,)) as cursor:
            row = await cursor.fetchone()
    return _row_to_batch_job(row) if row else None


async def list_batch_jobs() -> list[dict]:
    async with connection() as conn:
        async with conn.execute("SELECT * FROM batch_jobs ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
    return [_row_to_batch_job(row) for row in rows]


async def update_batch_job(job_id: str, **kwargs) -> None:
    if not kwargs:
        return
    now = _now_iso()
    kwargs["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    async with connection() as conn:
        await conn.execute(f"UPDATE batch_jobs SET {set_clause} WHERE id = ?", values)
        await conn.commit()


async def create_batch_item(
    job_id: str,
    product_id: str,
    product_name: str,
    status: str,
    score_before: int | None = None,
) -> int:
    now = _now_iso()
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO batch_items (job_id, product_id, product_name, status, score_before, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, product_id, product_name, status, score_before, now, now),
        )
        async with conn.execute("SELECT last_insert_rowid() AS id") as cur:
            item_id = int((await cur.fetchone())["id"])
        await conn.commit()
    return item_id


async def update_batch_item(item_id: int, **kwargs) -> None:
    if not kwargs:
        return
    now = _now_iso()
    kwargs["updated_at"] = now
    # rollback_data dict → JSON string
    if "rollback_data" in kwargs and isinstance(kwargs["rollback_data"], dict):
        kwargs["rollback_data"] = json.dumps(kwargs["rollback_data"], ensure_ascii=False)
    # suggestion_data dict → JSON string
    if "suggestion_data" in kwargs and isinstance(kwargs["suggestion_data"], dict):
        kwargs["suggestion_data"] = json.dumps(kwargs["suggestion_data"], ensure_ascii=False)
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [item_id]
    async with connection() as conn:
        await conn.execute(f"UPDATE batch_items SET {set_clause} WHERE id = ?", values)
        await conn.commit()


async def bulk_update_batch_item_status(item_ids: list[int], status: str) -> int:
    """Update status for multiple batch items in a single transaction."""
    if not item_ids:
        return 0
    now = _now_iso()
    placeholders = ",".join("?" for _ in item_ids)
    async with connection() as conn:
        cursor = await conn.execute(
            f"UPDATE batch_items SET status = ?, updated_at = ? WHERE id IN ({placeholders})",
            [status, now, *item_ids],
        )
        await conn.commit()
        return cursor.rowcount


async def get_batch_items(job_id: str) -> list[dict]:
    async with connection() as conn:
        async with conn.execute(
            "SELECT * FROM batch_items WHERE job_id = ? ORDER BY id ASC", (job_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [_row_to_batch_item(row) for row in rows]


async def get_batch_item(item_id: int) -> dict | None:
    async with connection() as conn:
        async with conn.execute("SELECT * FROM batch_items WHERE id = ?", (item_id,)) as cursor:
            row = await cursor.fetchone()
    return _row_to_batch_item(row) if row else None


async def get_batch_item_rollback_data(item_id: int) -> dict | None:
    async with connection() as conn:
        async with conn.execute(
            "SELECT rollback_data, product_id FROM batch_items WHERE id = ?", (item_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row and row["rollback_data"]:
        return {"product_id": row["product_id"], **json.loads(row["rollback_data"])}
    return None


async def get_batch_item_by_product(job_id: str, product_id: str) -> dict | None:
    async with connection() as conn:
        async with conn.execute(
            "SELECT * FROM batch_items WHERE job_id = ? AND product_id = ?",
            (job_id, product_id),
        ) as cursor:
            row = await cursor.fetchone()
    return _row_to_batch_item(row) if row else None


async def delete_batch_job(job_id: str) -> bool:
    async with connection() as conn:
        async with conn.execute("SELECT status FROM batch_jobs WHERE id = ?", (job_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            if row["status"] in ("running",):
                return False
        await conn.execute("DELETE FROM batch_items WHERE job_id = ?", (job_id,))
        await conn.execute("DELETE FROM batch_jobs WHERE id = ?", (job_id,))
        await conn.commit()
    return True


async def get_batch_stats() -> dict:
    async with connection() as conn:
        async with conn.execute("SELECT COUNT(*) AS c FROM batch_jobs") as cur:
            total_jobs = int((await cur.fetchone())["c"] or 0)
        async with conn.execute(
            "SELECT SUM(processed_count) AS s FROM batch_jobs WHERE status = 'completed'"
        ) as cur:
            total_processed = int((await cur.fetchone())["s"] or 0)
        async with conn.execute(
            """
            SELECT AVG(avg_score_after - avg_score_before) AS delta
            FROM batch_jobs
            WHERE status = 'completed' AND avg_score_before > 0
            """
        ) as cur:
            row = await cur.fetchone()
            avg_improvement = float(row["delta"] or 0)
        async with conn.execute(
            "SELECT * FROM batch_jobs WHERE status IN ('analyzing','running') ORDER BY created_at DESC LIMIT 1"
        ) as cur:
            active_row = await cur.fetchone()

    return {
        "total_jobs": total_jobs,
        "total_processed": total_processed,
        "avg_score_improvement": avg_improvement,
        "active_job": _row_to_batch_job(active_row) if active_row else None,
    }


# ── Daily score snapshot helpers ─────────────────────────────────────────────


async def has_daily_snapshot(snapshot_date: str) -> bool:
    """Check if a daily snapshot already exists for the given date (YYYY-MM-DD)."""
    async with connection() as conn:
        async with conn.execute(
            "SELECT COUNT(*) AS count FROM daily_score_snapshots WHERE snapshot_date = ?",
            (snapshot_date,),
        ) as cursor:
            row = await cursor.fetchone()
    return int(row["count"]) > 0 if row else False


async def save_daily_snapshots(
    snapshot_date: str,
    results: list[tuple["Product", "SeoScore"]],
) -> None:
    """Bulk-insert daily score snapshots. Uses INSERT OR IGNORE for idempotency."""
    if not results:
        return

    now = _now_iso()
    rows = [
        (
            snapshot_date,
            product.id,
            product.name,
            score.total_score,
            score.seo_score,
            score.geo_score,
            score.aeo_score,
            score.title_score,
            score.description_score,
            score.english_description_score,
            score.meta_score,
            score.meta_desc_score,
            score.keyword_score,
            score.content_quality_score,
            score.technical_seo_score,
            score.readability_score,
            score.ai_citability_score,
            len(score.issues),
            now,
        )
        for product, score in results
    ]

    async with connection() as conn:
        await conn.executemany(
            """
            INSERT OR IGNORE INTO daily_score_snapshots (
                snapshot_date, product_id, product_name,
                total_score, seo_score, geo_score, aeo_score,
                title_score, description_score, english_description_score,
                meta_score, meta_desc_score, keyword_score,
                content_quality_score, technical_seo_score,
                readability_score, ai_citability_score,
                issues_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await conn.commit()


async def get_store_daily_trends(days: int = 90) -> list[dict]:
    """Return store-wide daily averages for the last N days."""
    async with connection() as conn:
        async with conn.execute(
            """
            SELECT
                snapshot_date,
                COUNT(*) AS product_count,
                ROUND(AVG(total_score), 1) AS avg_total,
                ROUND(AVG(seo_score), 1) AS avg_seo,
                ROUND(AVG(geo_score), 1) AS avg_geo,
                ROUND(AVG(aeo_score), 1) AS avg_aeo,
                ROUND(AVG(title_score), 1) AS avg_title,
                ROUND(AVG(description_score), 1) AS avg_description,
                ROUND(AVG(english_description_score), 1) AS avg_english_description,
                ROUND(AVG(meta_score), 1) AS avg_meta,
                ROUND(AVG(meta_desc_score), 1) AS avg_meta_desc,
                ROUND(AVG(keyword_score), 1) AS avg_keyword,
                ROUND(AVG(content_quality_score), 1) AS avg_content_quality,
                ROUND(AVG(technical_seo_score), 1) AS avg_technical_seo,
                ROUND(AVG(readability_score), 1) AS avg_readability,
                ROUND(AVG(ai_citability_score), 1) AS avg_ai_citability,
                ROUND(AVG(issues_count), 1) AS avg_issues
            FROM daily_score_snapshots
            WHERE snapshot_date >= DATE('now', ? || ' days')
            GROUP BY snapshot_date
            ORDER BY snapshot_date ASC
            """,
            (f"-{days}",),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_product_daily_trends(product_id: str, days: int = 90) -> list[dict]:
    """Return daily score history for a single product."""
    async with connection() as conn:
        async with conn.execute(
            """
            SELECT
                snapshot_date,
                total_score, seo_score, geo_score, aeo_score,
                title_score, description_score, english_description_score,
                meta_score, meta_desc_score, keyword_score,
                content_quality_score, technical_seo_score,
                readability_score, ai_citability_score,
                issues_count
            FROM daily_score_snapshots
            WHERE product_id = ? AND snapshot_date >= DATE('now', ? || ' days')
            ORDER BY snapshot_date ASC
            """,
            (product_id, f"-{days}"),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_daily_summary() -> dict:
    """Compare first snapshot date averages vs latest snapshot date averages."""
    async with connection() as conn:
        # Get first and latest snapshot dates
        async with conn.execute(
            "SELECT MIN(snapshot_date) AS first_date, MAX(snapshot_date) AS latest_date FROM daily_score_snapshots"
        ) as cursor:
            dates_row = await cursor.fetchone()

        if not dates_row or not dates_row["first_date"]:
            return {
                "first_date": None, "latest_date": None, "days_tracked": 0,
                "total_products": 0, "snapshot_count": 0,
                "first_avg": {}, "latest_avg": {}, "improvement": {},
            }

        first_date = dates_row["first_date"]
        latest_date = dates_row["latest_date"]

        # Count distinct snapshot dates
        async with conn.execute(
            "SELECT COUNT(DISTINCT snapshot_date) AS cnt FROM daily_score_snapshots"
        ) as cursor:
            snap_row = await cursor.fetchone()
            snapshot_count = int(snap_row["cnt"]) if snap_row else 0

        # Count products in latest snapshot
        async with conn.execute(
            "SELECT COUNT(*) AS cnt FROM daily_score_snapshots WHERE snapshot_date = ?",
            (latest_date,),
        ) as cursor:
            cnt_row = await cursor.fetchone()
            total_products = int(cnt_row["cnt"]) if cnt_row else 0

        # Get averages for first date
        async with conn.execute(
            """
            SELECT
                ROUND(AVG(total_score), 1) AS total,
                ROUND(AVG(seo_score), 1) AS seo,
                ROUND(AVG(geo_score), 1) AS geo,
                ROUND(AVG(aeo_score), 1) AS aeo,
                ROUND(AVG(title_score), 1) AS title,
                ROUND(AVG(description_score), 1) AS description,
                ROUND(AVG(english_description_score), 1) AS english_description,
                ROUND(AVG(meta_score), 1) AS meta,
                ROUND(AVG(meta_desc_score), 1) AS meta_desc,
                ROUND(AVG(keyword_score), 1) AS keyword,
                ROUND(AVG(content_quality_score), 1) AS content_quality,
                ROUND(AVG(technical_seo_score), 1) AS technical_seo,
                ROUND(AVG(readability_score), 1) AS readability,
                ROUND(AVG(ai_citability_score), 1) AS ai_citability,
                ROUND(AVG(issues_count), 1) AS issues
            FROM daily_score_snapshots WHERE snapshot_date = ?
            """,
            (first_date,),
        ) as cursor:
            first_row = await cursor.fetchone()

        # Get averages for latest date
        async with conn.execute(
            """
            SELECT
                ROUND(AVG(total_score), 1) AS total,
                ROUND(AVG(seo_score), 1) AS seo,
                ROUND(AVG(geo_score), 1) AS geo,
                ROUND(AVG(aeo_score), 1) AS aeo,
                ROUND(AVG(title_score), 1) AS title,
                ROUND(AVG(description_score), 1) AS description,
                ROUND(AVG(english_description_score), 1) AS english_description,
                ROUND(AVG(meta_score), 1) AS meta,
                ROUND(AVG(meta_desc_score), 1) AS meta_desc,
                ROUND(AVG(keyword_score), 1) AS keyword,
                ROUND(AVG(content_quality_score), 1) AS content_quality,
                ROUND(AVG(technical_seo_score), 1) AS technical_seo,
                ROUND(AVG(readability_score), 1) AS readability,
                ROUND(AVG(ai_citability_score), 1) AS ai_citability,
                ROUND(AVG(issues_count), 1) AS issues
            FROM daily_score_snapshots WHERE snapshot_date = ?
            """,
            (latest_date,),
        ) as cursor:
            latest_row = await cursor.fetchone()

    first_avg = dict(first_row) if first_row else {}
    latest_avg = dict(latest_row) if latest_row else {}

    improvement = {}
    for key in first_avg:
        f_val = float(first_avg.get(key) or 0)
        l_val = float(latest_avg.get(key) or 0)
        improvement[key] = round(l_val - f_val, 1)

    return {
        "first_date": first_date,
        "latest_date": latest_date,
        "days_tracked": snapshot_count,
        "total_products": total_products,
        "snapshot_count": snapshot_count,
        "first_avg": first_avg,
        "latest_avg": latest_avg,
        "improvement": improvement,
    }


async def get_top_improvers(limit: int = 10) -> list[dict]:
    """Return products with the biggest total_score improvement (first vs latest snapshot)."""
    async with connection() as conn:
        async with conn.execute(
            "SELECT MIN(snapshot_date) AS first_date, MAX(snapshot_date) AS latest_date FROM daily_score_snapshots"
        ) as cursor:
            dates_row = await cursor.fetchone()

        if not dates_row or not dates_row["first_date"] or dates_row["first_date"] == dates_row["latest_date"]:
            return []

        first_date = dates_row["first_date"]
        latest_date = dates_row["latest_date"]

        async with conn.execute(
            """
            SELECT
                f.product_id,
                f.product_name,
                f.total_score AS first_score,
                l.total_score AS latest_score,
                (l.total_score - f.total_score) AS delta
            FROM daily_score_snapshots f
            JOIN daily_score_snapshots l
                ON f.product_id = l.product_id
            WHERE f.snapshot_date = ? AND l.snapshot_date = ?
            ORDER BY delta DESC
            LIMIT ?
            """,
            (first_date, latest_date, limit),
        ) as cursor:
            rows = await cursor.fetchall()

    return [dict(row) for row in rows]


async def get_snapshot_dates() -> list[str]:
    """Return all distinct snapshot dates."""
    async with connection() as conn:
        async with conn.execute(
            "SELECT DISTINCT snapshot_date FROM daily_score_snapshots ORDER BY snapshot_date ASC"
        ) as cursor:
            rows = await cursor.fetchall()
    return [row["snapshot_date"] for row in rows]


async def get_snapshot_products(snapshot_date: str) -> list[dict]:
    """Return all product scores for a specific snapshot date."""
    async with connection() as conn:
        async with conn.execute(
            """
            SELECT product_id, product_name, total_score, seo_score, geo_score, aeo_score,
                   title_score, description_score, english_description_score,
                   meta_score, meta_desc_score, keyword_score,
                   content_quality_score, technical_seo_score,
                   readability_score, ai_citability_score, issues_count
            FROM daily_score_snapshots
            WHERE snapshot_date = ?
            ORDER BY total_score DESC
            """,
            (snapshot_date,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# ── Score change log ─────────────────────────────────────────────────────────


async def insert_score_change_log(
    product_id: str,
    product_name: str,
    operation: str,
    score_before: Optional[int],
    score_after: Optional[int],
    job_id: Optional[str] = None,
) -> None:
    """Insert a score change event (called after every product update + re-score)."""
    delta = None
    if score_before is not None and score_after is not None:
        delta = score_after - score_before
    async with connection() as conn:
        await conn.execute(
            """INSERT INTO score_change_log
               (product_id, product_name, operation, score_before, score_after, delta, job_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (product_id, product_name, operation, score_before, score_after, delta, job_id, _now_iso()),
        )
        await conn.commit()


async def get_score_change_log(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    product_id: Optional[str] = None,
    operation: Optional[str] = None,
    job_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Query score change events with optional filters and date range."""
    conditions: list[str] = []
    params: list[Any] = []
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date + "T23:59:59")
    if product_id:
        conditions.append("product_id = ?")
        params.append(product_id)
    if operation:
        conditions.append("operation = ?")
        params.append(operation)
    if job_id:
        conditions.append("job_id = ?")
        params.append(job_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])
    async with connection() as conn:
        async with conn.execute(
            f"SELECT * FROM score_change_log {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_score_change_summary(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Aggregate stats for score change events in a date range."""
    conditions: list[str] = []
    params: list[Any] = []
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date + "T23:59:59")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with connection() as conn:
        async with conn.execute(
            f"""SELECT
                COUNT(*) AS total_events,
                COUNT(DISTINCT product_id) AS unique_products,
                ROUND(AVG(delta), 1) AS avg_delta,
                SUM(CASE WHEN delta > 0 THEN 1 ELSE 0 END) AS improved_count,
                SUM(CASE WHEN delta < 0 THEN 1 ELSE 0 END) AS degraded_count,
                SUM(CASE WHEN delta = 0 OR delta IS NULL THEN 1 ELSE 0 END) AS unchanged_count,
                MAX(delta) AS best_delta,
                MIN(delta) AS worst_delta,
                COALESCE(SUM(CASE WHEN delta > 0 THEN delta ELSE 0 END), 0) AS total_gain,
                COALESCE(SUM(delta), 0) AS net_change,
                ROUND(AVG(score_after), 1) AS avg_score_after
            FROM score_change_log {where}""",
            params,
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else {}


async def get_hourly_activity(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    """Score change events grouped by hour-of-day (0-23)."""
    conditions: list[str] = []
    params: list[Any] = []
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date + "T23:59:59")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with connection() as conn:
        async with conn.execute(
            f"""SELECT
                strftime('%H', created_at) AS hour,
                COUNT(*) AS event_count,
                ROUND(AVG(delta), 1) AS avg_delta,
                SUM(CASE WHEN delta > 0 THEN 1 ELSE 0 END) AS improved,
                SUM(CASE WHEN delta < 0 THEN 1 ELSE 0 END) AS degraded
            FROM score_change_log {where}
            GROUP BY hour
            ORDER BY hour""",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_daily_activity(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    """Score change events grouped by calendar date."""
    conditions: list[str] = []
    params: list[Any] = []
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date + "T23:59:59")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with connection() as conn:
        async with conn.execute(
            f"""SELECT
                DATE(created_at) AS day,
                COUNT(*) AS event_count,
                ROUND(AVG(delta), 1) AS avg_delta,
                SUM(CASE WHEN delta > 0 THEN 1 ELSE 0 END) AS improved,
                SUM(CASE WHEN delta < 0 THEN 1 ELSE 0 END) AS degraded,
                COUNT(DISTINCT product_id) AS unique_products
            FROM score_change_log {where}
            GROUP BY day
            ORDER BY day""",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_score_distribution() -> list[dict]:
    """Current product score distribution in buckets."""
    async with connection() as conn:
        async with conn.execute(
            """WITH latest AS (
                SELECT product_id,
                       json_extract(score_data, '$.total_score') AS total_score,
                       ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY created_at DESC) AS rn
                FROM seo_scores
            )
            SELECT
                CASE
                    WHEN total_score >= 90 THEN '90-100'
                    WHEN total_score >= 80 THEN '80-89'
                    WHEN total_score >= 70 THEN '70-79'
                    WHEN total_score >= 60 THEN '60-69'
                    WHEN total_score >= 50 THEN '50-59'
                    ELSE '0-49'
                END AS bucket,
                COUNT(*) AS count
            FROM latest WHERE rn = 1
            GROUP BY bucket
            ORDER BY bucket DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_operation_metrics(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict]:
    """Per-operation-type success rate and avg delta."""
    conditions: list[str] = []
    params: list[Any] = []
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date + "T23:59:59")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    async with connection() as conn:
        async with conn.execute(
            f"""SELECT
                operation,
                COUNT(*) AS total,
                ROUND(AVG(delta), 1) AS avg_delta,
                ROUND(100.0 * SUM(CASE WHEN delta > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS success_rate,
                MAX(delta) AS best_delta,
                MIN(delta) AS worst_delta,
                ROUND(AVG(score_after), 1) AS avg_score_after
            FROM score_change_log {where}
            GROUP BY operation""",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]
