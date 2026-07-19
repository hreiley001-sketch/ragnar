"""Live video — LiveKit access tokens (key-gated), hand-rolled JWT (HS256) so
no SDK dependency is needed. The ride page joins the room when this is wired.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from .config import settings


def is_configured() -> bool:
    return bool(settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def access_token(room: str, identity: str, *, can_publish: bool = False, ttl_sec: int = 3600) -> str:
    """LiveKit-compatible JWT: viewers subscribe; hosts can publish."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "iss": settings.livekit_api_key,
        "sub": identity,
        "nbf": now - 10,
        "exp": now + ttl_sec,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": can_publish,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }
    signing_input = _b64url(json.dumps(header, separators=(",", ":")).encode()) + "." + \
        _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(settings.livekit_api_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + _b64url(sig)
