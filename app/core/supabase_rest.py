"""Minimal Supabase REST client — PostgREST via service/anon key.

Used by marketplace services when Supabase is configured.
Degrades to None when keys/URL unset (local SQLite product path still works).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import settings
from .security import service_headers

logger = logging.getLogger("ragnar.core.supabase_rest")


def available() -> bool:
    return bool(settings.supabase_url and service_headers())


def _base() -> str:
    return f"{settings.supabase_url.rstrip('/')}/rest/v1"


def insert(table: str, row: dict[str, Any]) -> dict[str, Any] | None:
    headers = service_headers()
    if not headers:
        return None
    headers = {**headers, "Prefer": "return=representation"}
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(f"{_base()}/{table}", headers=headers, json=row)
        if resp.status_code >= 400:
            logger.warning("supabase insert %s → %s %s", table, resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("supabase insert failed %s: %s", table, exc)
        return None


def select(
    table: str,
    *,
    filters: dict[str, str] | None = None,
    order: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    headers = service_headers()
    if not headers:
        return []
    params: dict[str, str] = {"select": "*", "limit": str(limit)}
    if order:
        params["order"] = order
    if filters:
        params.update(filters)
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{_base()}/{table}", headers=headers, params=params)
        if resp.status_code >= 400:
            logger.warning("supabase select %s → %s", table, resp.status_code)
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("supabase select failed %s: %s", table, exc)
        return []


def patch(table: str, match: dict[str, str], values: dict[str, Any]) -> dict[str, Any] | None:
    headers = service_headers()
    if not headers:
        return None
    headers = {**headers, "Prefer": "return=representation"}
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.patch(
                f"{_base()}/{table}",
                headers=headers,
                params=match,
                json=values,
            )
        if resp.status_code >= 400:
            logger.warning("supabase patch %s → %s %s", table, resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("supabase patch failed %s: %s", table, exc)
        return None
