"""Card-imaging pipeline — Cloudinary (transform-CDN + AI background removal),
Remove.bg (dedicated background removal), and Replicate (AI upscale/restore).

Everything here is **key-gated with graceful fallback**: with no keys configured,
``cdn_url`` returns the original image untouched and the enhancement helpers
return ``None``, so the marketplace keeps working on plain ``/uploads`` files.

All outbound calls use ``httpx.AsyncClient`` (async) except ``cdn_url``, which is
pure URL string-building with no network I/O.
"""
from __future__ import annotations

import hashlib
import logging
import time
from urllib.parse import quote

import httpx

from .config import settings

logger = logging.getLogger("ragnar.media")

_CLOUDINARY_UPLOAD = "https://api.cloudinary.com/v1_1/{cloud}/image/upload"
_CLOUDINARY_DELIVER = "https://res.cloudinary.com/{cloud}/image"
_REMOVEBG = "https://api.remove.bg/v1.0/removebg"
_REPLICATE = "https://api.replicate.com/v1/models/{model}/predictions"


# --------------------------------------------------------------------------- #
# Configuration probes (surfaced at /api/meta.integrations)
# --------------------------------------------------------------------------- #
def cloudinary_configured() -> bool:
    return bool(
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    )


def removebg_configured() -> bool:
    return bool(settings.removebg_api_key)


def replicate_configured() -> bool:
    return bool(settings.replicate_api_token)


def background_removal_available() -> bool:
    """AI background removal works via either Cloudinary's add-on or Remove.bg."""
    return removebg_configured() or cloudinary_configured()


def _abs_url(source: str) -> str:
    """Make a site-relative path (``/uploads/x.jpg``) absolute so third-party
    APIs can fetch it. Absolute URLs pass through unchanged."""
    if not source:
        return source
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return f"{settings.public_base_url}/{source.lstrip('/')}"


# --------------------------------------------------------------------------- #
# Cloudinary — delivery/transform URLs (no network I/O)
# --------------------------------------------------------------------------- #
def cdn_url(
    source: str,
    *,
    public_id: str | None = None,
    width: int | None = None,
    height: int | None = None,
    crop: str = "fill",
    quality: str = "auto",
    fmt: str = "auto",
    remove_bg: bool = False,
) -> str:
    """Return a transformed delivery URL for ``source``.

    If Cloudinary isn't configured, returns ``source`` unchanged (graceful
    fallback). When ``public_id`` is known (asset previously uploaded) it's
    delivered directly; otherwise Cloudinary *fetches* and transforms the
    absolute source URL on the fly.
    """
    if not source and not public_id:
        return source
    if not cloudinary_configured():
        return source

    t: list[str] = [f"f_{fmt}", f"q_{quality}"]
    if width:
        t.append(f"w_{int(width)}")
    if height:
        t.append(f"h_{int(height)}")
    if width or height:
        t.append(f"c_{crop}")
    if remove_bg:
        t.append("e_background_removal")
    transform = ",".join(t)
    base = _CLOUDINARY_DELIVER.format(cloud=settings.cloudinary_cloud_name)

    if public_id:
        return f"{base}/upload/{transform}/{public_id}"
    return f"{base}/fetch/{transform}/{quote(_abs_url(source), safe='')}"


def thumb_url(source: str, public_id: str | None = None, *, w: int = 400, h: int = 560) -> str:
    """Grid thumbnail — card aspect (~5:7), fill-cropped, auto format/quality."""
    return cdn_url(source, public_id=public_id, width=w, height=h, crop="fill")


# --------------------------------------------------------------------------- #
# Cloudinary — signed upload (async)
# --------------------------------------------------------------------------- #
def _sign(params: dict) -> str:
    """Cloudinary signature: sha1 of sorted 'k=v' params + api_secret."""
    payload = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha1((payload + settings.cloudinary_api_secret).encode()).hexdigest()


async def cloudinary_upload(
    data: bytes, filename: str = "card", *, folder: str | None = None
) -> dict | None:
    """Upload bytes to Cloudinary. Returns ``{secure_url, public_id, format,
    width, height, bytes}`` or ``None`` if unconfigured / on failure."""
    if not cloudinary_configured() or not data:
        return None
    folder = folder or settings.cloudinary_folder
    ts = int(time.time())
    to_sign = {"timestamp": ts}
    if folder:
        to_sign["folder"] = folder
    signature = _sign(to_sign)
    form = {
        "api_key": settings.cloudinary_api_key,
        "timestamp": str(ts),
        "signature": signature,
    }
    if folder:
        form["folder"] = folder
    url = _CLOUDINARY_UPLOAD.format(cloud=settings.cloudinary_cloud_name)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url, data=form, files={"file": (filename, data)}
            )
        if resp.status_code >= 400:
            logger.warning("Cloudinary upload failed %s: %s", resp.status_code, resp.text[:200])
            return None
        j = resp.json()
        return {
            "secure_url": j.get("secure_url"),
            "public_id": j.get("public_id"),
            "format": j.get("format"),
            "width": j.get("width"),
            "height": j.get("height"),
            "bytes": j.get("bytes"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cloudinary upload error: %s", exc)
        return None


async def cloudinary_upload_url(image_url: str, *, folder: str | None = None) -> dict | None:
    """Upload a remote image by URL (Cloudinary fetches it server-side)."""
    if not cloudinary_configured() or not image_url:
        return None
    folder = folder or settings.cloudinary_folder
    ts = int(time.time())
    to_sign = {"timestamp": ts}
    if folder:
        to_sign["folder"] = folder
    form = {
        "api_key": settings.cloudinary_api_key,
        "timestamp": str(ts),
        "signature": _sign(to_sign),
        "file": _abs_url(image_url),
    }
    if folder:
        form["folder"] = folder
    url = _CLOUDINARY_UPLOAD.format(cloud=settings.cloudinary_cloud_name)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, data=form)
        if resp.status_code >= 400:
            logger.warning("Cloudinary url-upload failed %s: %s", resp.status_code, resp.text[:200])
            return None
        j = resp.json()
        return {"secure_url": j.get("secure_url"), "public_id": j.get("public_id"),
                "format": j.get("format"), "width": j.get("width"), "height": j.get("height")}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cloudinary url-upload error: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Remove.bg — dedicated background removal (async)
# --------------------------------------------------------------------------- #
async def remove_background(image_url: str) -> bytes | None:
    """Strip the background from ``image_url``; returns PNG bytes or ``None``."""
    if not removebg_configured() or not image_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                _REMOVEBG,
                headers={"X-Api-Key": settings.removebg_api_key},
                data={"image_url": _abs_url(image_url), "size": "auto"},
            )
        if resp.status_code >= 400:
            logger.warning("Remove.bg failed %s: %s", resp.status_code, resp.text[:200])
            return None
        return resp.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("Remove.bg error: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Replicate — AI upscale / restore (async, may take several seconds)
# --------------------------------------------------------------------------- #
def _first_url(output) -> str | None:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        return output[0] if isinstance(output[0], str) else None
    return None


async def replicate_upscale(image_url: str, *, scale: int | None = None) -> str | None:
    """Upscale/restore ``image_url`` via a Replicate model (default Real-ESRGAN).

    Uses the model-based predictions endpoint with ``Prefer: wait`` so most jobs
    return synchronously; falls back to short polling if still processing.
    Returns the enhanced image URL or ``None``.
    """
    if not replicate_configured() or not image_url:
        return None
    scale = scale or settings.replicate_upscale
    url = _REPLICATE.format(model=settings.replicate_upscale_model)
    headers = {
        "Authorization": f"Bearer {settings.replicate_api_token}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    body = {"input": {"image": _abs_url(image_url), "scale": scale}}
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code >= 400:
                logger.warning("Replicate failed %s: %s", resp.status_code, resp.text[:200])
                return None
            pred = resp.json()
            status = pred.get("status")
            get_url = (pred.get("urls") or {}).get("get")
            # Poll a few times if it didn't finish under Prefer: wait.
            tries = 0
            while status in ("starting", "processing") and get_url and tries < 20:
                tries += 1
                poll = await client.get(get_url, headers=headers)
                pred = poll.json()
                status = pred.get("status")
                if status in ("succeeded", "failed", "canceled"):
                    break
        if status == "succeeded":
            return _first_url(pred.get("output"))
        logger.warning("Replicate ended status=%s", status)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Replicate error: %s", exc)
        return None


async def fetch_bytes(url: str) -> bytes | None:
    """Download an image URL to bytes (used to re-upload enhanced output)."""
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(_abs_url(url))
        if resp.status_code >= 400:
            return None
        return resp.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_bytes error: %s", exc)
        return None
