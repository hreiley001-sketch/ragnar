"""Network / URL hardening helpers (SSRF and open-redirect guards)."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


_BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
}


def is_safe_public_https_url(url: str, *, allow_http: bool = False) -> bool:
    """Return True only for http(s) URLs that do not target private/link-local hosts."""
    raw = (url or "").strip()
    if not raw or len(raw) > 2000:
        return False
    try:
        parsed = urlparse(raw)
    except Exception:  # noqa: BLE001
        return False
    scheme = (parsed.scheme or "").lower()
    if scheme not in ({"https", "http"} if allow_http else {"https"}):
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return False
    # Block literal IPs in private ranges.
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
        return True
    except ValueError:
        pass
    # Resolve hostnames and reject private answers (best-effort).
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def require_safe_media_url(url: str) -> str:
    """Validate and return URL, or raise ValueError."""
    cleaned = (url or "").strip()
    # Allow same-origin relative upload paths used by scan-to-post.
    if cleaned.startswith("/uploads/") and ".." not in cleaned and "\\" not in cleaned:
        return cleaned
    if not is_safe_public_https_url(cleaned, allow_http=False):
        raise ValueError("URL must be a public https:// address")
    return cleaned
