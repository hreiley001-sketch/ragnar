"""RAGNAR Dispatch — AI Shipping Agent.

AI owns quote → pack → label → ship → track → exception.
Sellers (and staff) talk to Dispatch; humans only for edge cases.
"""
from .brain import handle_message, start_conversation

__all__ = ["handle_message", "start_conversation"]
