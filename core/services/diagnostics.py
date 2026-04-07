from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import AppConfig, TaskRecord
from core.product_manager import ProductManager
from core.prompt_store import PROMPT_FILES, PROMPTS_DIR, _prompt_cache
from core.services.provider import resolve_provider_base_url
from data import db

HEALTHY = "healthy"
DEGRADED = "degraded"
DOWN = "down"
UNKNOWN = "unknown"

_STATUS_RANK = {
    DOWN: 3,
    DEGRADED: 2,
    UNKNOWN: 1,
    HEALTHY: 0,
}

_TERMINAL_TASK_STATUSES = {"completed", "completed_with_errors", "failed", "cancelled", "stopped"}
_PASSIVE_TASK_STATUSES = {"idle", "queued", "paused", "analyzed"}
_WAITING_STAGES = {"awaiting_review", "awaiting_approval", "awaiting_user_action"}
_STUCK_SIGNAL_SECONDS = 180
_STUCK_HEARTBEAT_SECONDS = 120
_ACTIVE_JOB_LIMIT = 8

_STAGE_LABELS = {
    "queued": "Hazirlaniyor",
    "preparing": "Hazirlaniyor",
    "analyzing": "Analiz",
    "awaiting_review": "Inceleme Bekleniyor",
    "awaiting_approval": "Onay Bekleniyor",
    "awaiting_user_action": "Kullanici Bekleniyor",
    "applying": "Uygulama",
    "running": "Calisiyor",
    "rolling_back": "Geri Alma",
    "completed": "Tamamlandi",
    "completed_with_errors": "Hata ile Tamamlandi",
    "failed": "Hata",
    "cancelled": "Durduruldu",
    "paused": "Duraklatildi",
    "stopped": "Durduruldu",
}


def _now() -> datetime:
    return datetime.now()


def _elapsed_ms(started_at: float) -> int:
    return max(0, int(round((time.perf_counter() - started_at) * 1000)))


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _dedupe_strs(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _pick_status(*statuses: str) -> str:
    chosen = HEALTHY
    for status in statuses:
        if _STATUS_RANK.get(status, -1) > _STATUS_RANK.get(chosen, -1):
            chosen = status
    return chosen


def _check_payload(
    name: str,
    *,
    status: str,
    checked_at: str,
    latency_ms: int | None = None,
    error_code: str | None = None,
    error_summary: str | None = None,
    retryable: bool | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "checked_at": checked_at,
        "latency_ms": latency_ms,
        "error_code": error_code,
        "error_summary": error_summary,
        "retryable": retryable,
    }


def _issue_payload(
    *,
    scope: str,
    component: str,
    reason_code: str,
    summary: str,
    target_id: str | None = None,
    target_label: str | None = None,
    recommended_action: str | None = None,
) -> dict[str, Any]:
    return {
        "scope": scope,
        "component": component,
        "reason_code": reason_code,
        "summary": summary,
        "target_id": target_id,
        "target_label": target_label,
        "recommended_action": recommended_action,
    }


def _task_feedback(task: TaskRecord) -> dict[str, Any]:
    feedback = task.payload.get("feedback")
    return feedback if isinstance(feedback, dict) else {}


def _task_stage(task: TaskRecord) -> str:
    feedback = _task_feedback(task)
    stage = feedback.get("stage") or task.payload.get("stage") or task.status
    return str(stage or task.status)


def _task_stage_label(task: TaskRecord) -> str:
    feedback = _task_feedback(task)
    label = feedback.get("stage_label")
    if isinstance(label, str) and label.strip():
        return label
    return _STAGE_LABELS.get(_task_stage(task), _task_stage(task).replace("_", " ").title())


def _task_status_message(task: TaskRecord) -> str:
    feedback = _task_feedback(task)
    message = feedback.get("status_message") or task.payload.get("status_message")
    if isinstance(message, str) and message.strip():
        return message
    if task.error and task.error.message:
        return task.error.message
    return _task_stage_label(task)


def _task_counts(task: TaskRecord) -> dict[str, int]:
    feedback = _task_feedback(task)
    raw_counts = feedback.get("summary_counts")
    counts = raw_counts if isinstance(raw_counts, dict) else {}
    result_counts = task.result if isinstance(task.result, dict) else {}
    total = int(counts.get("total") or result_counts.get("total_count") or 0)
    processed = int(counts.get("processed") or result_counts.get("processed_count") or 0)
    skipped = int(counts.get("skipped") or result_counts.get("skipped_count") or 0)
    failed = int(counts.get("failed") or result_counts.get("failed_count") or 0)
    succeeded = int(counts.get("succeeded") or max(processed - skipped - failed, 0))
    retried = int(counts.get("retried") or 0)
    remaining = int(counts.get("remaining") or max(total - processed - skipped - failed, 0))
    return {
        "total": total,
        "processed": processed,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "retried": retried,
        "remaining": remaining,
    }


def _task_current_item(task: TaskRecord) -> str | None:
    feedback = _task_feedback(task)
    current_item = feedback.get("current_item")
    if isinstance(current_item, dict):
        product_name = str(current_item.get("product_name") or "").strip()
        product_id = str(current_item.get("product_id") or "").strip()
        if product_name:
            return product_name
        if product_id:
            return product_id
    current_product_name = task.payload.get("current_product_name")
    if isinstance(current_product_name, str) and current_product_name.strip():
        return current_product_name
    return None


def _task_last_signal(task: TaskRecord) -> datetime:
    feedback = _task_feedback(task)
    candidates = [
        _parse_datetime(feedback.get("last_event_at")),
        task.heartbeat_at,
        task.updated_at,
    ]
    valid = [candidate for candidate in candidates if candidate is not None]
    return max(valid) if valid else task.updated_at


def _is_task_waiting(task: TaskRecord) -> bool:
    stage = _task_stage(task)
    return task.status in {"paused", "analyzed"} or stage in _WAITING_STAGES


def _is_task_running(task: TaskRecord) -> bool:
    if task.status in _TERMINAL_TASK_STATUSES | _PASSIVE_TASK_STATUSES:
        return False
    return not _is_task_waiting(task)


def _is_task_stuck(task: TaskRecord, now: datetime) -> bool:
    if not _is_task_running(task):
        return False
    last_signal = _task_last_signal(task)
    signal_age = (now - last_signal).total_seconds()
    heartbeat_age = None
    if task.heartbeat_at is not None:
        heartbeat_age = (now - task.heartbeat_at).total_seconds()
    if signal_age >= _STUCK_SIGNAL_SECONDS:
        return True
    if heartbeat_age is not None and heartbeat_age >= _STUCK_HEARTBEAT_SECONDS and signal_age >= _STUCK_HEARTBEAT_SECONDS:
        return True
    return False


def _task_summary_payload(task: TaskRecord, *, stuck: bool) -> dict[str, Any]:
    return {
        "id": task.id,
        "type": task.type,
        "status": task.status,
        "progress": task.progress,
        "stage": _task_stage(task),
        "stage_label": _task_stage_label(task),
        "status_message": _task_status_message(task),
        "heartbeat_at": _iso(task.heartbeat_at),
        "updated_at": _iso(task.updated_at),
        "current_item": _task_current_item(task),
        "stuck": stuck,
        "reason_code": "worker_stuck" if stuck else None,
        "counts": _task_counts(task),
    }


async def _build_provider_block(manager: ProductManager, config: AppConfig, checked_at: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.perf_counter()
    reason_codes: list[str] = []
    recommended_actions: list[str] = []
    issues: list[dict[str, Any]] = []

    provider = (config.ai_provider or "none").strip().lower()
    configured_model = (config.ai_model_name or "").strip()
    has_api_key = bool((config.ai_api_key or config.anthropic_api_key).strip())
    resolved_base_url = resolve_provider_base_url(provider, config.ai_base_url)

    if provider == "none":
        reason_codes.append("provider_not_configured")
        recommended_actions.append("Ayarlar ekranindan bir AI provider secin.")
        latency_ms = _elapsed_ms(started)
        issues.append(_issue_payload(
            scope="global",
            component="providers",
            reason_code="provider_not_configured",
            summary="AI provider secilmemis.",
            recommended_action="Ayarlar ekranindan bir AI provider secin.",
        ))
        return ({
            "status": UNKNOWN,
            "summary": "AI provider secilmemis.",
            "checked_at": checked_at,
            "latency_ms": latency_ms,
            "error_code": "provider_not_configured",
            "error_summary": "AI provider secilmemis.",
            "retryable": False,
            "reason_codes": reason_codes,
            "recommended_actions": recommended_actions,
            "checks": [
                _check_payload(
                    "provider_config",
                    status=UNKNOWN,
                    checked_at=checked_at,
                    latency_ms=latency_ms,
                    error_code="provider_not_configured",
                    error_summary="AI provider secilmemis.",
                    retryable=False,
                )
            ],
            "provider": provider,
            "configured_model": configured_model,
            "message": "Provider secimi bekleniyor.",
        }, issues)

    config_checks: list[dict[str, Any]] = []
    config_status = HEALTHY
    if provider not in {"ollama", "lm-studio", "none"} and not has_api_key:
        config_status = DEGRADED
        reason_codes.append("provider_api_key_missing")
        recommended_actions.append("Provider API anahtarini girin.")
        issues.append(_issue_payload(
            scope="global",
            component="providers",
            reason_code="provider_api_key_missing",
            summary=f"{provider} icin API anahtari eksik.",
            recommended_action="Provider API anahtarini girin.",
        ))
    if provider in {"openai", "openrouter", "ollama", "lm-studio", "custom"} and not resolved_base_url:
        config_status = _pick_status(config_status, DEGRADED)
        reason_codes.append("provider_base_url_missing")
        recommended_actions.append("Provider base URL bilgisini doldurun.")
        issues.append(_issue_payload(
            scope="global",
            component="providers",
            reason_code="provider_base_url_missing",
            summary=f"{provider} icin base URL eksik.",
            recommended_action="Provider base URL bilgisini doldurun.",
        ))
    config_checks.append(_check_payload(
        "provider_config",
        status=config_status,
        checked_at=checked_at,
        error_code=reason_codes[-1] if config_status != HEALTHY and reason_codes else None,
        error_summary=None if config_status == HEALTHY else "Provider konfigurasyonunda eksik alanlar var.",
        retryable=False if config_status != HEALTHY else None,
    ))

    health_started = time.perf_counter()
    health = manager.get_provider_health()
    health_latency = _elapsed_ms(health_started)
    raw_status = str(health.get("status") or "")
    raw_message = str(health.get("message") or "")

    mapped_status = {
        "ok": HEALTHY,
        "error": DOWN,
        "offline": DOWN,
        "missing_url": DEGRADED,
        "disabled": UNKNOWN,
    }.get(raw_status, UNKNOWN)

    error_code = None
    retryable = None
    if mapped_status != HEALTHY:
        if raw_status == "missing_url":
            error_code = "provider_base_url_missing"
            retryable = False
        elif raw_status == "offline":
            error_code = "provider_connection_failed"
            retryable = True
        elif raw_status == "error":
            error_code = "provider_http_error"
            retryable = True
        else:
            error_code = "provider_unavailable"
            retryable = True
        reason_codes.append(error_code)
        issues.append(_issue_payload(
            scope="global",
            component="providers",
            reason_code=error_code,
            summary=raw_message or "Provider baglantisi dogrulanamadi.",
            recommended_action="Provider baglantisini ve model ayarlarini kontrol edin.",
        ))
        recommended_actions.append("Provider baglantisini ve model ayarlarini kontrol edin.")

    checks = config_checks + [
        _check_payload(
            "provider_connectivity",
            status=mapped_status,
            checked_at=checked_at,
            latency_ms=health_latency,
            error_code=error_code,
            error_summary=raw_message if mapped_status != HEALTHY else None,
            retryable=retryable,
        )
    ]

    component_status = _pick_status(config_status, mapped_status)
    latency_ms = _elapsed_ms(started)
    return ({
        "status": component_status,
        "summary": raw_message or "Provider durumu okunamadi.",
        "checked_at": checked_at,
        "latency_ms": latency_ms,
        "error_code": error_code,
        "error_summary": raw_message if component_status != HEALTHY else None,
        "retryable": retryable,
        "reason_codes": _dedupe_strs(reason_codes),
        "recommended_actions": _dedupe_strs(recommended_actions),
        "checks": checks,
        "provider": provider,
        "configured_model": configured_model,
        "message": raw_message,
    }, issues)


def _build_mcp_block(manager: ProductManager, checked_at: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.perf_counter()
    reason_codes: list[str] = []
    recommended_actions: list[str] = []
    issues: list[dict[str, Any]] = []

    has_token = bool(manager.chat_has_mcp)
    initialized = bool(manager.chat_mcp_initialized)
    tools = manager.chat_mcp_tools if isinstance(manager.chat_mcp_tools, list) else []
    tool_names = [str(tool.get("name") or "") for tool in tools if isinstance(tool, dict) and tool.get("name")]
    tool_count = int(manager.chat_mcp_tool_count or len(tool_names))

    checks: list[dict[str, Any]] = []
    if not has_token:
        reason_codes.append("mcp_token_missing")
        recommended_actions.append("Ayarlar ekranindan MCP token girin.")
        issues.append(_issue_payload(
            scope="store",
            component="mcp",
            reason_code="mcp_token_missing",
            summary="MCP token tanimli degil.",
            recommended_action="Ayarlar ekranindan MCP token girin.",
        ))
        checks.append(_check_payload(
            "mcp_config",
            status=UNKNOWN,
            checked_at=checked_at,
            error_code="mcp_token_missing",
            error_summary="MCP token tanimli degil.",
            retryable=False,
        ))
        status = UNKNOWN
        summary = "MCP token bekleniyor."
        error_code = "mcp_token_missing"
        retryable = False
    elif initialized and tool_count > 0:
        checks.append(_check_payload("mcp_config", status=HEALTHY, checked_at=checked_at))
        checks.append(_check_payload("mcp_tools", status=HEALTHY, checked_at=checked_at))
        status = HEALTHY
        summary = f"MCP hazir, {tool_count} arac bulundu."
        error_code = None
        retryable = None
    elif initialized and tool_count == 0:
        reason_codes.append("mcp_tool_list_empty")
        recommended_actions.append("MCP baglantisini yeniden baslatip arac listesini kontrol edin.")
        issues.append(_issue_payload(
            scope="global",
            component="mcp",
            reason_code="mcp_tool_list_empty",
            summary="MCP baslatildi ama arac listesi bos geldi.",
            recommended_action="MCP baglantisini yeniden baslatip arac listesini kontrol edin.",
        ))
        checks.append(_check_payload("mcp_config", status=HEALTHY, checked_at=checked_at))
        checks.append(_check_payload(
            "mcp_tools",
            status=DEGRADED,
            checked_at=checked_at,
            error_code="mcp_tool_list_empty",
            error_summary="MCP baglandi fakat arac listesi bos.",
            retryable=True,
        ))
        status = DEGRADED
        summary = "MCP baglandi fakat arac listesi bos."
        error_code = "mcp_tool_list_empty"
        retryable = True
    else:
        reason_codes.append("mcp_not_initialized")
        recommended_actions.append("MCP baglantisini baslatin ve arac listesini yukleyin.")
        issues.append(_issue_payload(
            scope="global",
            component="mcp",
            reason_code="mcp_not_initialized",
            summary="MCP token var ancak baglanti henuz baslatilmamis.",
            recommended_action="MCP baglantisini baslatin ve arac listesini yukleyin.",
        ))
        checks.append(_check_payload("mcp_config", status=HEALTHY, checked_at=checked_at))
        checks.append(_check_payload(
            "mcp_initialize",
            status=DEGRADED,
            checked_at=checked_at,
            error_code="mcp_not_initialized",
            error_summary="Token var fakat baglanti baslatilmamis.",
            retryable=True,
        ))
        status = DEGRADED
        summary = "MCP token var fakat baglanti baslatilmamis."
        error_code = "mcp_not_initialized"
        retryable = True

    return ({
        "status": status,
        "summary": summary,
        "checked_at": checked_at,
        "latency_ms": _elapsed_ms(started),
        "error_code": error_code,
        "error_summary": summary if status != HEALTHY else None,
        "retryable": retryable,
        "reason_codes": _dedupe_strs(reason_codes),
        "recommended_actions": _dedupe_strs(recommended_actions),
        "checks": checks,
        "has_token": has_token,
        "initialized": initialized,
        "tool_count": tool_count,
        "tool_names": tool_names,
    }, issues)


async def _build_database_block(checked_at: str) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    started = time.perf_counter()
    reason_codes: list[str] = []
    recommended_actions: list[str] = []
    issues: list[dict[str, Any]] = []
    counts = {
        "product_count": 0,
        "suggestion_count": 0,
        "task_count": 0,
        "pending_suggestions": 0,
    }
    checks: list[dict[str, Any]] = []
    journal_mode = ""
    error_code = None
    error_summary = None
    retryable = None
    status = HEALTHY
    write_test_ok = False

    try:
        async with db.connection() as conn:
            read_started = time.perf_counter()
            async with conn.execute("SELECT COUNT(*) AS count FROM products") as cursor:
                counts["product_count"] = int((await cursor.fetchone())["count"] or 0)
            async with conn.execute("SELECT COUNT(*) AS count FROM suggestions") as cursor:
                counts["suggestion_count"] = int((await cursor.fetchone())["count"] or 0)
            async with conn.execute("SELECT COUNT(*) AS count FROM suggestions WHERE status = 'pending'") as cursor:
                counts["pending_suggestions"] = int((await cursor.fetchone())["count"] or 0)
            async with conn.execute("SELECT COUNT(*) AS count FROM tasks") as cursor:
                counts["task_count"] = int((await cursor.fetchone())["count"] or 0)
            async with conn.execute("PRAGMA journal_mode") as cursor:
                row = await cursor.fetchone()
                journal_mode = str(row[0] or "") if row else ""
            checks.append(_check_payload(
                "db_read",
                status=HEALTHY,
                checked_at=checked_at,
                latency_ms=_elapsed_ms(read_started),
            ))

            write_started = time.perf_counter()
            try:
                await conn.execute("BEGIN IMMEDIATE")
                await conn.execute(
                    """
                    INSERT INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    ("diagnostics.write_test", checked_at, checked_at),
                )
                await conn.rollback()
                write_test_ok = True
                checks.append(_check_payload(
                    "db_write",
                    status=HEALTHY,
                    checked_at=checked_at,
                    latency_ms=_elapsed_ms(write_started),
                ))
            except Exception as exc:  # noqa: BLE001
                await conn.rollback()
                write_error = str(exc)
                write_error_lower = write_error.lower()
                write_test_ok = False
                status = DOWN if "locked" in write_error_lower else DEGRADED
                error_code = "db_write_locked" if "locked" in write_error_lower else "db_write_failed"
                error_summary = write_error
                retryable = True
                reason_codes.append(error_code)
                recommended_actions.append("Veritabani yazma yolunu ve kilitlenen islemleri kontrol edin.")
                issues.append(_issue_payload(
                    scope="global",
                    component="database",
                    reason_code=error_code,
                    summary=write_error,
                    recommended_action="Veritabani yazma yolunu ve kilitlenen islemleri kontrol edin.",
                ))
                checks.append(_check_payload(
                    "db_write",
                    status=status,
                    checked_at=checked_at,
                    latency_ms=_elapsed_ms(write_started),
                    error_code=error_code,
                    error_summary=write_error,
                    retryable=True,
                ))
    except Exception as exc:  # noqa: BLE001
        status = DOWN
        error_code = "db_connection_failed"
        error_summary = str(exc)
        retryable = True
        reason_codes.append(error_code)
        recommended_actions.append("Veritabani dosyasina erisim ve izinleri kontrol edin.")
        issues.append(_issue_payload(
            scope="global",
            component="database",
            reason_code=error_code,
            summary=str(exc),
            recommended_action="Veritabani dosyasina erisim ve izinleri kontrol edin.",
        ))
        checks.append(_check_payload(
            "db_connectivity",
            status=DOWN,
            checked_at=checked_at,
            latency_ms=_elapsed_ms(started),
            error_code=error_code,
            error_summary=str(exc),
            retryable=True,
        ))

    summary = (
        f"DB hazir, {counts['product_count']} urun ve {counts['task_count']} task kaydi var."
        if status == HEALTHY
        else (error_summary or "DB kontrolu basarisiz.")
    )

    return ({
        "status": status,
        "summary": summary,
        "checked_at": checked_at,
        "latency_ms": _elapsed_ms(started),
        "error_code": error_code,
        "error_summary": error_summary,
        "retryable": retryable,
        "reason_codes": _dedupe_strs(reason_codes),
        "recommended_actions": _dedupe_strs(recommended_actions),
        "checks": checks,
        "path": str(Path(db.DB_PATH).resolve()),
        "journal_mode": journal_mode,
        "product_count": counts["product_count"],
        "suggestion_count": counts["suggestion_count"],
        "task_count": counts["task_count"],
        "write_test_ok": write_test_ok,
    }, issues, counts)


def _build_prompt_cache_block(checked_at: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reason_codes: list[str] = []
    recommended_actions: list[str] = []
    issues: list[dict[str, Any]] = []
    missing_templates = [
        key for key, filename in PROMPT_FILES.items()
        if not (PROMPTS_DIR / filename).exists()
    ]
    loaded_templates = len(_prompt_cache)
    total_templates = len(PROMPT_FILES)

    if missing_templates:
        reason_codes.append("prompt_template_missing")
        recommended_actions.append("Eksik prompt dosyalarini resetleyin veya yeniden olusturun.")
        issues.append(_issue_payload(
            scope="global",
            component="prompt_cache",
            reason_code="prompt_template_missing",
            summary=f"Eksik prompt dosyalari: {', '.join(missing_templates[:4])}",
            recommended_action="Eksik prompt dosyalarini resetleyin veya yeniden olusturun.",
        ))

    status = HEALTHY if not missing_templates else DEGRADED
    checks = [
        _check_payload(
            "prompt_files",
            status=status,
            checked_at=checked_at,
            error_code="prompt_template_missing" if missing_templates else None,
            error_summary="Bazi prompt dosyalari eksik." if missing_templates else None,
            retryable=False if missing_templates else None,
        )
    ]

    summary = (
        f"{loaded_templates}/{total_templates} prompt cache'te hazir."
        if not missing_templates
        else f"{len(missing_templates)} prompt dosyasi eksik."
    )

    return ({
        "status": status,
        "summary": summary,
        "checked_at": checked_at,
        "latency_ms": None,
        "error_code": "prompt_template_missing" if missing_templates else None,
        "error_summary": "Bazi prompt dosyalari eksik." if missing_templates else None,
        "retryable": False if missing_templates else None,
        "reason_codes": _dedupe_strs(reason_codes),
        "recommended_actions": _dedupe_strs(recommended_actions),
        "checks": checks,
        "prompt_dir": str(PROMPTS_DIR.resolve()),
        "total_templates": total_templates,
        "loaded_templates": loaded_templates,
        "missing_templates": missing_templates,
    }, issues)


def _build_store_context_block(config: AppConfig, db_counts: dict[str, int], checked_at: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reason_codes: list[str] = []
    recommended_actions: list[str] = []
    issues: list[dict[str, Any]] = []

    missing_keys: list[str] = []
    if not (config.ikas_store_name or "").strip():
        missing_keys.append("store_name")
    if not (config.ikas_client_id or "").strip():
        missing_keys.append("client_id")
    if not (config.ikas_client_secret or "").strip():
        missing_keys.append("client_secret")

    if missing_keys:
        reason_codes.append("store_config_incomplete")
        recommended_actions.append("ikas store bilgilerini tamamlayin.")
        issues.append(_issue_payload(
            scope="store",
            component="store_context",
            reason_code="store_config_incomplete",
            summary=f"Eksik store alanlari: {', '.join(missing_keys)}",
            target_label=(config.ikas_store_name or "").strip() or None,
            recommended_action="ikas store bilgilerini tamamlayin.",
        ))

    status = HEALTHY if not missing_keys else DEGRADED
    return ({
        "status": status,
        "summary": (
            f"{config.ikas_store_name or 'Store secilmedi'} icin {db_counts.get('product_count', 0)} cached urun var."
            if status == HEALTHY
            else "Store konfigurasyonu eksik."
        ),
        "checked_at": checked_at,
        "latency_ms": None,
        "error_code": "store_config_incomplete" if missing_keys else None,
        "error_summary": "Store konfigurasyonu eksik." if missing_keys else None,
        "retryable": False if missing_keys else None,
        "reason_codes": _dedupe_strs(reason_codes),
        "recommended_actions": _dedupe_strs(recommended_actions),
        "checks": [
            _check_payload(
                "store_config",
                status=status,
                checked_at=checked_at,
                error_code="store_config_incomplete" if missing_keys else None,
                error_summary=f"Eksik alanlar: {', '.join(missing_keys)}" if missing_keys else None,
                retryable=False if missing_keys else None,
            )
        ],
        "store_name": (config.ikas_store_name or "").strip(),
        "languages": list(config.store_languages or []),
        "dry_run": bool(config.dry_run),
        "product_count": int(db_counts.get("product_count") or 0),
        "pending_suggestions": int(db_counts.get("pending_suggestions") or 0),
    }, issues)


def _build_task_blocks(tasks: list[TaskRecord], checked_at: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    now = _now()
    reason_codes: list[str] = []
    recommended_actions: list[str] = []
    issues: list[dict[str, Any]] = []

    queued_tasks = [task for task in tasks if task.status in {"idle", "queued"}]
    waiting_tasks = [task for task in tasks if _is_task_waiting(task)]
    running_tasks = [task for task in tasks if _is_task_running(task)]
    terminal_tasks = [task for task in tasks if task.status in _TERMINAL_TASK_STATUSES]
    failed_tasks = [task for task in terminal_tasks if task.status in {"failed", "completed_with_errors"}]

    stuck_tasks = [task for task in running_tasks if _is_task_stuck(task, now)]
    latest_heartbeat = max((task.heartbeat_at for task in tasks if task.heartbeat_at is not None), default=None)
    last_crash = max(
        failed_tasks,
        key=lambda task: task.updated_at,
        default=None,
    )

    if stuck_tasks:
        reason_codes.append("worker_stuck")
        recommended_actions.append("Stuck gorunen job'lari durdurup yeniden baslatin.")
        for task in stuck_tasks:
            issues.append(_issue_payload(
                scope="job",
                component="workers",
                reason_code="worker_stuck",
                summary=f"{task.id} task'i {_task_last_signal(task).isoformat()} zamanindan beri sessiz.",
                target_id=task.id,
                target_label=_task_stage_label(task),
                recommended_action="Task'i durdurup tekrar calistirin veya debug report alin.",
            ))

    worker_status = HEALTHY if not stuck_tasks else DEGRADED
    worker_summary = (
        f"{len(running_tasks)} aktif is, {len(waiting_tasks)} bekleyen is var."
        if not stuck_tasks
        else f"{len(stuck_tasks)} task stuck adayi gorunuyor."
    )
    workers_block = {
        "status": worker_status,
        "summary": worker_summary,
        "checked_at": checked_at,
        "latency_ms": None,
        "error_code": "worker_stuck" if stuck_tasks else None,
        "error_summary": "Bazi task heartbeat uretmiyor." if stuck_tasks else None,
        "retryable": True if stuck_tasks else None,
        "reason_codes": _dedupe_strs(reason_codes),
        "recommended_actions": _dedupe_strs(recommended_actions),
        "checks": [
            _check_payload(
                "worker_heartbeat",
                status=worker_status,
                checked_at=checked_at,
                error_code="worker_stuck" if stuck_tasks else None,
                error_summary="Bazi task heartbeat uretmiyor." if stuck_tasks else None,
                retryable=True if stuck_tasks else None,
            )
        ],
        "active_count": len(running_tasks),
        "waiting_count": len(waiting_tasks),
        "stuck_count": len(stuck_tasks),
        "latest_heartbeat_at": _iso(latest_heartbeat),
        "last_crash_summary": (
            f"{last_crash.type}: {last_crash.error.message if last_crash and last_crash.error else last_crash.status}"
            if last_crash is not None
            else ""
        ),
    }

    longest_running = max(
        running_tasks,
        key=lambda task: (now - (task.started_at or task.updated_at)).total_seconds(),
        default=None,
    )
    task_runtime_status = _pick_status(DEGRADED if stuck_tasks else HEALTHY, DEGRADED if failed_tasks else HEALTHY)
    task_runtime_block = {
        "status": task_runtime_status,
        "summary": (
            f"{len(running_tasks)} aktif, {len(queued_tasks)} kuyrukta, {len(failed_tasks)} hatali task var."
            if tasks
            else "Task runtime bos."
        ),
        "checked_at": checked_at,
        "latency_ms": None,
        "error_code": "worker_stuck" if stuck_tasks else ("task_failed" if failed_tasks else None),
        "error_summary": "Aktif task'larin bir kismi stuck gorunuyor." if stuck_tasks else None,
        "retryable": True if (stuck_tasks or failed_tasks) else None,
        "reason_codes": _dedupe_strs(reason_codes + (["task_failed"] if failed_tasks else [])),
        "recommended_actions": _dedupe_strs(recommended_actions + (["Hatali task kayitlarini inceleyin."] if failed_tasks else [])),
        "checks": [
            _check_payload(
                "task_runtime",
                status=task_runtime_status,
                checked_at=checked_at,
                error_code="worker_stuck" if stuck_tasks else ("task_failed" if failed_tasks else None),
                error_summary="Task runtime'da hata veya sessiz kalan isler var." if (stuck_tasks or failed_tasks) else None,
                retryable=True if (stuck_tasks or failed_tasks) else None,
            )
        ],
        "queued_count": len(queued_tasks),
        "active_count": len(running_tasks),
        "waiting_count": len(waiting_tasks),
        "terminal_count": len(terminal_tasks),
        "failed_count": len(failed_tasks),
        "stuck_count": len(stuck_tasks),
        "longest_running_task": _task_summary_payload(longest_running, stuck=_is_task_stuck(longest_running, now)) if longest_running else None,
        "stuck_tasks": [_task_summary_payload(task, stuck=True) for task in stuck_tasks[:3]],
    }

    active_jobs = [
        _task_summary_payload(task, stuck=_is_task_stuck(task, now))
        for task in sorted(
            [task for task in tasks if task.status not in _TERMINAL_TASK_STATUSES and task.status not in {"idle"}],
            key=lambda task: task.updated_at,
            reverse=True,
        )[:_ACTIVE_JOB_LIMIT]
    ]
    active_jobs_block = {
        "status": HEALTHY if active_jobs else UNKNOWN,
        "summary": f"{len(active_jobs)} aktif veya bekleyen is listelendi." if active_jobs else "Aktif is yok.",
        "checked_at": checked_at,
        "latency_ms": None,
        "error_code": None,
        "error_summary": None,
        "retryable": None,
        "reason_codes": [],
        "recommended_actions": [],
        "checks": [],
        "total": len(active_jobs),
        "items": active_jobs,
    }

    return workers_block, task_runtime_block, active_jobs_block, issues


def _build_debug_report(
    *,
    generated_at: str,
    overall_status: str,
    blocks: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    active_jobs: dict[str, Any],
) -> str:
    lines = [
        f"generated_at: {generated_at}",
        f"overall_status: {overall_status}",
        "",
        "[components]",
    ]
    for key in ("providers", "mcp", "database", "workers", "prompt_cache", "task_runtime", "store_context"):
        block = blocks[key]
        lines.append(f"- {key}: {block.get('status')} | {block.get('summary')}")
        reason_codes = block.get("reason_codes") or []
        if reason_codes:
            lines.append(f"  reason_codes: {', '.join(reason_codes)}")
        actions = block.get("recommended_actions") or []
        if actions:
            lines.append(f"  actions: {' | '.join(actions[:3])}")

    lines.extend(["", "[active_jobs]"])
    items = active_jobs.get("items") or []
    if not items:
        lines.append("- none")
    else:
        for item in items:
            lines.append(
                f"- {item.get('id')} | {item.get('type')} | {item.get('status')} | "
                f"{item.get('stage_label')} | progress={item.get('progress')}"
            )

    lines.extend(["", "[issues]"])
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            target = f" ({issue['target_id']})" if issue.get("target_id") else ""
            lines.append(
                f"- {issue.get('scope')}:{issue.get('component')}:{issue.get('reason_code')}{target} | {issue.get('summary')}"
            )

    return "\n".join(lines)


async def build_diagnostics_summary(manager: ProductManager) -> dict[str, Any]:
    generated_at = _now().isoformat()
    config = manager.get_config()

    providers_block, provider_issues = await _build_provider_block(manager, config, generated_at)
    mcp_block, mcp_issues = _build_mcp_block(manager, generated_at)
    database_block, database_issues, db_counts = await _build_database_block(generated_at)
    prompt_cache_block, prompt_issues = _build_prompt_cache_block(generated_at)
    store_context_block, store_issues = _build_store_context_block(config, db_counts, generated_at)
    tasks = await db.list_tasks(limit=200)
    workers_block, task_runtime_block, active_jobs_block, worker_issues = _build_task_blocks(tasks, generated_at)

    issues = provider_issues + mcp_issues + database_issues + prompt_issues + store_issues + worker_issues
    reason_codes = _dedupe_strs([issue["reason_code"] for issue in issues])
    recommended_actions = _dedupe_strs(
        [str(issue.get("recommended_action") or "") for issue in issues]
        + providers_block.get("recommended_actions", [])
        + mcp_block.get("recommended_actions", [])
        + database_block.get("recommended_actions", [])
        + prompt_cache_block.get("recommended_actions", [])
        + store_context_block.get("recommended_actions", [])
        + workers_block.get("recommended_actions", [])
        + task_runtime_block.get("recommended_actions", [])
    )

    overall_status = HEALTHY
    for block in (
        providers_block,
        mcp_block,
        database_block,
        workers_block,
        prompt_cache_block,
        task_runtime_block,
        store_context_block,
    ):
        overall_status = _pick_status(overall_status, str(block.get("status") or UNKNOWN))
    if overall_status == HEALTHY and issues:
        overall_status = DEGRADED

    blocks = {
        "providers": providers_block,
        "mcp": mcp_block,
        "database": database_block,
        "workers": workers_block,
        "prompt_cache": prompt_cache_block,
        "task_runtime": task_runtime_block,
        "store_context": store_context_block,
    }
    debug_report = _build_debug_report(
        generated_at=generated_at,
        overall_status=overall_status,
        blocks=blocks,
        issues=issues,
        active_jobs=active_jobs_block,
    )

    return {
        "overall_status": overall_status,
        "generated_at": generated_at,
        "reason_codes": reason_codes,
        "recommended_actions": recommended_actions,
        "issues": issues,
        "debug_report": debug_report,
        "providers": providers_block,
        "mcp": mcp_block,
        "database": database_block,
        "workers": workers_block,
        "prompt_cache": prompt_cache_block,
        "task_runtime": task_runtime_block,
        "store_context": store_context_block,
        "active_jobs": active_jobs_block,
    }
