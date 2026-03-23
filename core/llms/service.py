import asyncio
import logging
from typing import Optional

from config.settings import get_config
from core.ai.client import create_ai_client
from core.prompt_store import ensure_prompt_files
from core.models import LlmsJob, Product
from data import db

logger = logging.getLogger(__name__)


class LlmsService:
    """Orchestrates background llms.txt summary generation."""

    def __init__(self) -> None:
        ensure_prompt_files()
        self._ai = create_ai_client(get_config())
        self._task: asyncio.Task | None = None
        self._job_id: str | None = None
        self._stop_event = asyncio.Event()
        self._stop_reason: str = ""
        self._lock = asyncio.Lock()
        self._current_product: Product | None = None

    @property
    def current_product(self) -> Product | None:
        return self._current_product

    def reload_ai_client(self) -> None:
        """Recreate AI client after settings change."""
        self._ai = create_ai_client(get_config())

    async def bootstrap(self) -> None:
        """Resume any in-flight llms job on app startup."""
        job = await db.get_llms_latest_job(statuses=["running"])
        if job:
            await db.reset_llms_processing_entries(job.id)
            await self._start_worker(job.id, resume=True)

    async def start_new_job(self) -> LlmsJob:
        """Create a new job for unprocessed products and start worker."""
        async with self._lock:
            if self._task and not self._task.done():
                raise RuntimeError("Halihazirda calisan bir llms.txt isi var.")
            products = await db.get_all_products()
            processed_ids = await db.get_llms_processed_product_ids()
            targets = [p.id for p in products if p.id not in processed_ids]
            if not targets:
                raise RuntimeError("Islenecek yeni veya islenmemis urun bulunamadi.")

            job = await db.create_llms_job(targets, options={"reason": "auto"})
            await self._start_worker(job.id)
            return job

    async def resume_job(self, job_id: str | None = None) -> LlmsJob:
        async with self._lock:
            if self._task and not self._task.done():
                raise RuntimeError("Zaten calisan bir llms.txt isi var.")
            job = await db.get_llms_job(job_id) if job_id else await db.get_llms_latest_job(statuses=["paused", "queued"])
            if not job:
                raise RuntimeError("Devam ettirilecek bekleyen llms.txt isi yok.")
            await db.reset_llms_processing_entries(job.id)
            await self._start_worker(job.id, resume=True)
            return job

    async def pause_job(self) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                self._stop_reason = "paused"
                self._stop_event.set()
                try:
                    self._ai.cancel_active_request()
                except Exception:
                    logger.debug("AI request cancel during pause ignored", exc_info=True)

    async def stop_job(self) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                self._stop_reason = "stopped"
                self._stop_event.set()
                try:
                    self._ai.cancel_active_request()
                except Exception:
                    logger.debug("AI request cancel during stop ignored", exc_info=True)

    async def _start_worker(self, job_id: str, resume: bool = False) -> None:
        if self._task and not self._task.done():
            await self.stop_job()
        self._job_id = job_id
        self._stop_event = asyncio.Event()
        self._stop_reason = ""
        if not resume:
            await db.update_llms_job_status(job_id, "running")
        self._task = asyncio.create_task(self._run(job_id))

    async def _run(self, job_id: str) -> None:
        logger.info("llms.txt worker started (job=%s)", job_id)
        try:
            await db.update_llms_job_status(job_id, "running")
            while True:
                if self._stop_event.is_set():
                    break

                entry = await db.claim_next_llms_entry(job_id)
                if entry is None:
                    await db.refresh_llms_job_counters(job_id)
                    await db.update_llms_job_status(job_id, "completed")
                    self._current_product = None
                    return

                product = await db.get_product(entry.product_id)
                if not product:
                    await db.save_llms_entry_failure(entry.id, "Product not found in cache")
                    await db.refresh_llms_job_counters(job_id)
                    continue

                self._current_product = product
                try:
                    summary = self._ai.summarize_for_llms(product)
                    if isinstance(summary, tuple):
                        summary_text, _thinking = summary
                    else:
                        summary_text = summary
                    usage = getattr(self._ai, "last_usage", {"input": 0, "output": 0})  # type: ignore[attr-defined]
                    tokens_in = int(usage.get("input", 0) or 0)
                    tokens_out = int(usage.get("output", 0) or 0)
                    await db.save_llms_entry_success(entry.id, summary_text, tokens_in, tokens_out)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("llms.txt summary failed for %s: %s", entry.product_id, exc)
                    await db.save_llms_entry_failure(entry.id, str(exc))

                await db.refresh_llms_job_counters(job_id)

        finally:
            # reset any in-progress entries back to pending if we exited early
            await db.reset_llms_processing_entries(job_id)
            status = "completed"
            if self._stop_reason == "paused":
                status = "paused"
            elif self._stop_reason == "stopped":
                status = "stopped"
            await db.update_llms_job_status(job_id, status)
            self._current_product = None
            logger.info("llms.txt worker finished (job=%s, status=%s)", job_id, status)

    async def regenerate_product(self, product_id: str):
        """Synchronously regenerate summary for a single product (manual trigger)."""
        product = await db.get_product(product_id)
        if not product:
            raise RuntimeError("Product not found")
        summary = self._ai.summarize_for_llms(product)
        if isinstance(summary, tuple):
            summary_text, _thinking = summary
        else:
            summary_text = summary
        usage = getattr(self._ai, "last_usage", {"input": 0, "output": 0})  # type: ignore[attr-defined]
        tokens_in = int(usage.get("input", 0) or 0)
        tokens_out = int(usage.get("output", 0) or 0)
        job_id = await db.ensure_manual_llms_job()
        entry = await db.upsert_llms_entry_summary(product_id, summary_text, job_id=job_id, tokens_input=tokens_in, tokens_output=tokens_out)
        return {
            "product_id": product_id,
            "product_name": product.name,
            "category": product.category,
            "summary": entry.summary,
            "status": entry.status,
            "updated_at": entry.updated_at.isoformat(),
        }


# Singleton service used by API routes
llms_service = LlmsService()
