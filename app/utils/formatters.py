"""Response shaping helpers."""
from __future__ import annotations

from typing import Any


def public_ok(data: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": True}
    if data:
        body["data"] = data
    body.update(extra)
    return body
