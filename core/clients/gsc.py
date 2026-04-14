"""Google Search Console OAuth2 istemcisi.

OAuth2 akışı:
1. get_auth_url() → Kullanıcıyı Google OAuth ekranına yönlendir
2. exchange_code() → authorization_code → access + refresh token
3. fetch_analytics() → Refresh token ile verileri çek

Kimlik bilgileri config/settings.py üzerinden AppConfig'den okunur.
Refresh token .cache/user_settings.json'a save_config_to_db() ile kaydedilir.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_WEBMASTERS_BASE = "https://www.googleapis.com/webmasters/v3"


class GscAuthError(Exception):
    """GSC kimlik doğrulama hatası."""


class GscApiError(Exception):
    """GSC API çağrı hatası."""


class GoogleSearchConsoleClient:
    """Google Search Console Search Analytics verilerini çeken istemci."""

    def get_auth_url(self, client_id: str, redirect_uri: str) -> str:
        """Kullanıcıyı yönlendirmek için Google OAuth2 URL'i oluştur."""
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": _SCOPE,
            "access_type": "offline",   # refresh_token almak için zorunlu
            "prompt": "consent",        # Her seferinde refresh_token al
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict[str, str]:
        """Authorization code'u access + refresh token ile değiştir.

        Returns:
            {"access_token": ..., "refresh_token": ..., "expires_in": ...}
        """
        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_TOKEN_URL, data=payload)
        if resp.status_code != 200:
            raise GscAuthError(
                f"Token takas hatası ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    async def _get_access_token(
        self, client_id: str, client_secret: str, refresh_token: str
    ) -> str:
        """Refresh token kullanarak geçerli bir access token al."""
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_TOKEN_URL, data=payload)
        if resp.status_code != 200:
            raise GscAuthError(
                f"Token yenileme hatası ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise GscAuthError("Access token alınamadı.")
        return token

    async def list_properties(
        self, client_id: str, client_secret: str, refresh_token: str
    ) -> list[str]:
        """Kullanıcının GSC hesabındaki doğrulanmış property URL'lerini döndür."""
        token = await self._get_access_token(client_id, client_secret, refresh_token)
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{_WEBMASTERS_BASE}/sites", headers=headers
            )
        if resp.status_code != 200:
            raise GscApiError(
                f"Property listesi alınamadı ({resp.status_code}): {resp.text}"
            )
        sites = resp.json().get("siteEntry", [])
        return [s["siteUrl"] for s in sites]

    async def fetch_analytics(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        property_url: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Site geneli search analytics verilerini çek.

        Hem sayfa (page) bazlı hem de sorgu (query) bazlı veri döner.

        Returns:
            {
                "totals": {"clicks": int, "impressions": int, "ctr": float, "position": float},
                "pages": [{"url": str, "clicks": int, "impressions": int, "ctr": float, "position": float}, ...],
                "queries": [{"query": str, "clicks": int, "impressions": int, "ctr": float, "position": float}, ...],
                "synced_at": ISO8601 str,
            }
        """
        token = await self._get_access_token(client_id, client_secret, refresh_token)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        # GSC maks. 16 aya kadar veri sağlar; biz son `days` günü alıyoruz
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        from datetime import timedelta
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        encoded_url = property_url.rstrip("/")
        api_url = f"{_WEBMASTERS_BASE}/sites/{httpx.URL(encoded_url)}/searchAnalytics/query"

        pages = await self._query_dimension(
            api_url, headers, start_date, end_date, dimension="page", row_limit=500
        )
        queries = await self._query_dimension(
            api_url, headers, start_date, end_date, dimension="query", row_limit=500
        )

        # Site geneli toplamlar
        totals = self._aggregate_totals(pages)

        synced_at = datetime.now(timezone.utc).isoformat()
        return {
            "totals": totals,
            "pages": pages,
            "queries": queries,
            "synced_at": synced_at,
        }

    async def _query_dimension(
        self,
        api_url: str,
        headers: dict[str, str],
        start_date: str,
        end_date: str,
        dimension: str,
        row_limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Belirli bir boyut için GSC Search Analytics sorgusu yap."""
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": [dimension],
            "rowLimit": row_limit,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(api_url, headers=headers, json=body)

        if resp.status_code == 403:
            raise GscAuthError(
                "GSC API erişimi reddedildi. Property URL'inin doğru ve "
                "hesabın erişim izni olduğundan emin olun."
            )
        if resp.status_code != 200:
            raise GscApiError(
                f"GSC sorgu hatası ({resp.status_code}): {resp.text}"
            )

        rows = resp.json().get("rows", [])
        result: list[dict[str, Any]] = []
        for row in rows:
            keys = row.get("keys", [""])
            entry: dict[str, Any] = {
                "clicks": int(row.get("clicks", 0)),
                "impressions": int(row.get("impressions", 0)),
                "ctr": round(float(row.get("ctr", 0.0)) * 100, 2),  # 0.061 → 6.1
                "position": round(float(row.get("position", 0.0)), 1),
            }
            if dimension == "page":
                entry["url"] = keys[0]
            else:
                entry["query"] = keys[0]
            result.append(entry)
        return result

    def _aggregate_totals(self, pages: list[dict[str, Any]]) -> dict[str, Any]:
        """Sayfa listesinden site geneli toplamları hesapla."""
        if not pages:
            return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
        total_clicks = sum(p["clicks"] for p in pages)
        total_impressions = sum(p["impressions"] for p in pages)
        ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions else 0.0
        # Ağırlıklı ortalama pozisyon (gösterime göre)
        if total_impressions:
            weighted_pos = sum(p["position"] * p["impressions"] for p in pages)
            avg_position = round(weighted_pos / total_impressions, 1)
        else:
            avg_position = 0.0
        return {
            "clicks": total_clicks,
            "impressions": total_impressions,
            "ctr": ctr,
            "position": avg_position,
        }

    def filter_pages_for_product(
        self, pages: list[dict[str, Any]], slug: str
    ) -> list[dict[str, Any]]:
        """Verilen ürün slug'ını içeren sayfaları filtrele."""
        if not slug:
            return []
        return [p for p in pages if slug in p.get("url", "")]

    def aggregate_product_metrics(
        self, matched_pages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Eşleşen sayfalardaki metrikleri topla."""
        return self._aggregate_totals(matched_pages)
