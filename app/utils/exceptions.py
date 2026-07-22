"""Birdman domain exceptions — map cleanly to HTTP in the API layer."""
from __future__ import annotations


class BirdmanError(Exception):
    """Base application error."""

    def __init__(self, message: str, *, code: str = "birdman_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ValidationAppError(BirdmanError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="validation_error")


class NotFoundError(BirdmanError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, code="not_found")
