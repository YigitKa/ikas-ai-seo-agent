"""Google Search Console API endpoint'leri.

OAuth2 Akışı:
  GET /api/gsc/auth/start        → Google OAuth yetkilendirme URL'ini döner
  GET /api/gsc/auth/callback     → authorization_code'u token ile değiştirir,
                                    refresh_token'ı kaydeder, /settings'e yönlendirir

Veri:
  GET /api/gsc/status            → Bağlantı durumu + son senkronizasyon bilgisi
  GET /api/gsc/properties        → Kullanıcının GSC hesabındaki property listesi
  GET /api/gsc/data?days=30      → Önbellekten site geneli analytics; 24 saatten eskiyse arka planda yeniler
  POST /api/gsc/sync             → Önbelleği yok say, GSC'den zorla veri çek
  DELETE /api/gsc/cache          → Önbelleği temizle
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

import data.db as db
from api.schemas import (
    GscAuthUrlResponse,
    GscDataResponse,
    GscPageMetric,
    GscQueryMetric,
    GscStatusResponse,
    GscSyncResponse,
    MessageResponse,
)
from config.settings import get_config, save_config_to_db
from core.clients.gsc import GscApiError, GscAuthError, GoogleSearchConsoleClient

logger = logging.getLogger(__name__)

router = APIRouter()

_gsc_client = GoogleSearchConsoleClient()

# OAuth2 callback URL — varsayılan port, başlatma sırasında override edilebilir
_DEFAULT_CALLBACK_PATH = "/api/gsc/auth/callback"


def _get_redirect_uri(request_base_url: str) -> str:
    """Redirect URI'yi base URL'den türet."""
    base = request_base_url.rstrip("/")
    return f"{base}{_DEFAULT_CALLBACK_PATH}"


def _is_stale(synced_at_iso: str | None, max_age_hours: int = 24) -> bool:
    """Son senkronizasyonun belirtilen saatten eski olup olmadığını kontrol et."""
    if not synced_at_iso:
        return True
    try:
        synced_at = datetime.fromisoformat(synced_at_iso.replace("Z", "+00:00"))
        if synced_at.tzinfo is None:
            synced_at = synced_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - synced_at > timedelta(hours=max_age_hours)
    except (ValueError, TypeError):
        return True


def _build_data_response(
    data: dict,
    property_url: str,
    days: int,
    stale: bool,
) -> GscDataResponse:
    """Ham GSC veri sözlüğünden GscDataResponse oluştur."""
    pages = [
        GscPageMetric(
            url=p.get("url", ""),
            clicks=p.get("clicks", 0),
            impressions=p.get("impressions", 0),
            ctr=p.get("ctr", 0.0),
            position=p.get("position", 0.0),
        )
        for p in data.get("pages", [])
    ]
    queries = [
        GscQueryMetric(
            query=q.get("query", ""),
            clicks=q.get("clicks", 0),
            impressions=q.get("impressions", 0),
            ctr=q.get("ctr", 0.0),
            position=q.get("position", 0.0),
        )
        for q in data.get("queries", [])
    ]
    return GscDataResponse(
        property_url=property_url,
        days=days,
        totals=data.get("totals", {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}),
        pages=pages,
        queries=queries,
        synced_at=data.get("synced_at", ""),
        is_stale=stale,
    )


async def _do_sync(config, days: int) -> dict:
    """GSC'den veri çek ve önbelleğe kaydet."""
    data = await _gsc_client.fetch_analytics(
        client_id=config.gsc_client_id,
        client_secret=config.gsc_client_secret,
        refresh_token=config.gsc_refresh_token,
        property_url=config.gsc_property_url,
        days=days,
    )
    await db.save_gsc_cache(config.gsc_property_url, days, data)
    return data


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/status", response_model=GscStatusResponse)
async def gsc_status() -> GscStatusResponse:
    """GSC bağlantı durumunu döndür."""
    cfg = get_config()
    connected = bool(cfg.gsc_refresh_token and cfg.gsc_property_url)
    last_synced = None
    stale = True

    if connected:
        cached = await db.get_gsc_cache(cfg.gsc_property_url, 30)
        if cached:
            last_synced = cached.get("synced_at")
            stale = _is_stale(last_synced)

    return GscStatusResponse(
        connected=connected,
        property_url=cfg.gsc_property_url,
        last_synced=last_synced,
        is_stale=stale,
    )


@router.get("/auth/start", response_model=GscAuthUrlResponse)
async def gsc_auth_start(
    redirect_uri: str = Query(
        default="",
        description="OAuth2 callback URL'i. Boş bırakılırsa localhost:8000 kullanılır.",
    ),
) -> GscAuthUrlResponse:
    """Google OAuth2 yetkilendirme URL'ini döndür."""
    cfg = get_config()
    if not cfg.gsc_client_id:
        raise HTTPException(
            status_code=400,
            detail="GSC Client ID ayarlanmamış. Lütfen Settings sayfasından girin.",
        )
    callback_uri = redirect_uri or f"http://localhost:8000{_DEFAULT_CALLBACK_PATH}"
    url = _gsc_client.get_auth_url(
        client_id=cfg.gsc_client_id,
        redirect_uri=callback_uri,
    )
    return GscAuthUrlResponse(url=url)


@router.get("/auth/callback")
async def gsc_auth_callback(
    code: str = Query(..., description="Google tarafından sağlanan authorization code"),
    redirect_uri: str = Query(
        default="",
        description="Token takas için kullanılan redirect_uri (auth/start ile aynı olmalı)",
    ),
) -> RedirectResponse:
    """Google OAuth2 callback — authorization code'u refresh_token ile değiştirir."""
    cfg = get_config()
    if not cfg.gsc_client_id or not cfg.gsc_client_secret:
        raise HTTPException(
            status_code=400,
            detail="GSC Client ID veya Secret ayarlanmamış.",
        )
    callback_uri = redirect_uri or f"http://localhost:8000{_DEFAULT_CALLBACK_PATH}"

    try:
        tokens = await _gsc_client.exchange_code(
            code=code,
            client_id=cfg.gsc_client_id,
            client_secret=cfg.gsc_client_secret,
            redirect_uri=callback_uri,
        )
    except GscAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    refresh_token = tokens.get("refresh_token", "")
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google refresh_token döndürmedi. OAuth akışını 'prompt=consent' ile yeniden deneyin.",
        )

    # Refresh token'ı kalıcı olarak kaydet
    await save_config_to_db({"gsc_refresh_token": refresh_token})
    logger.info("GSC refresh token başarıyla kaydedildi.")

    # Kullanıcıyı settings sayfasına yönlendir
    return RedirectResponse(url="/?page=settings&gsc=ok", status_code=302)


@router.get("/properties")
async def gsc_list_properties() -> dict:
    """Kullanıcının GSC hesabındaki doğrulanmış property URL'lerini listele."""
    cfg = get_config()
    if not cfg.gsc_refresh_token:
        raise HTTPException(status_code=401, detail="GSC hesabı bağlı değil.")
    try:
        properties = await _gsc_client.list_properties(
            client_id=cfg.gsc_client_id,
            client_secret=cfg.gsc_client_secret,
            refresh_token=cfg.gsc_refresh_token,
        )
        return {"properties": properties}
    except GscAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/data", response_model=GscDataResponse)
async def gsc_get_data(
    days: int = Query(default=30, ge=1, le=90, description="Son kaç günlük veri"),
) -> GscDataResponse:
    """Site geneli GSC analytics verisini döndür.

    - Önbellekte geçerli veri varsa (< 24 saat) anında döner.
    - Önbellekte eski veri varsa eski veriyi dönerken arka planda yenileme başlatır.
    - Önbellekte hiç veri yoksa senkron olarak çeker.
    """
    cfg = get_config()
    if not cfg.gsc_refresh_token or not cfg.gsc_property_url:
        raise HTTPException(
            status_code=401,
            detail="GSC bağlı değil veya property URL ayarlanmamış.",
        )

    cached = await db.get_gsc_cache(cfg.gsc_property_url, days)

    if cached:
        stale = _is_stale(cached.get("synced_at"))
        if stale:
            # Eski veriyi hemen döndür; arka planda yenile
            asyncio.create_task(_background_sync(cfg, days))
        return _build_data_response(cached, cfg.gsc_property_url, days, stale)

    # Önbellekte hiç veri yok — senkron çek
    try:
        data = await _do_sync(cfg, days)
    except GscAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return _build_data_response(data, cfg.gsc_property_url, days, False)


async def _background_sync(cfg, days: int) -> None:
    """Arka planda GSC verisi çekip önbelleğe yazar (hataları sessizce loglar)."""
    try:
        await _do_sync(cfg, days)
        logger.info("Arka plan GSC senkronizasyonu tamamlandı (%d gün).", days)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Arka plan GSC senkronizasyonu başarısız: %s", exc)


@router.post("/sync", response_model=GscSyncResponse)
async def gsc_sync(
    days: int = Query(default=30, ge=1, le=90, description="Son kaç günlük veri"),
) -> GscSyncResponse:
    """Önbelleği yok say; GSC'den taze veri çek ve kaydet."""
    cfg = get_config()
    if not cfg.gsc_refresh_token or not cfg.gsc_property_url:
        raise HTTPException(
            status_code=401,
            detail="GSC bağlı değil veya property URL ayarlanmamış.",
        )

    try:
        data = await _do_sync(cfg, days)
    except GscAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except GscApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return GscSyncResponse(
        message="GSC verisi başarıyla senkronize edildi.",
        property_url=cfg.gsc_property_url,
        pages_synced=len(data.get("pages", [])),
        queries_synced=len(data.get("queries", [])),
        synced_at=data.get("synced_at", ""),
    )


@router.delete("/cache", response_model=MessageResponse)
async def gsc_clear_cache() -> MessageResponse:
    """GSC önbelleğini temizle. Bir sonraki /data isteğinde yeniden çekilir."""
    cfg = get_config()
    property_url = cfg.gsc_property_url or None
    await db.clear_gsc_cache(property_url)
    return MessageResponse(message="GSC önbelleği temizlendi.")
