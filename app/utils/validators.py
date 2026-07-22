"""Small validators used by services."""
from __future__ import annotations

from .exceptions import ValidationAppError


def require_non_empty(value: str | None, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationAppError(f"{field} is required")
    return text
