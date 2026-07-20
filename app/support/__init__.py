"""RAGNAR AI Support OS.

AI owns intake → reasoning → action → resolution. Humans are governors and
editors for edge cases (legal, high-value, fraud), not frontline agents.
"""
from .brain import handle_message, start_conversation

__all__ = ["handle_message", "start_conversation"]
