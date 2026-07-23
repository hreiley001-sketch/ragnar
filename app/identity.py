"""AI identity verification + ban enforcement for signup trust.

Uses OpenAI vision (same stack as card scan) to read a government ID photo,
extract a name + document fingerprint hash, and block banned re-registrations.
Full document numbers are never stored — only an HMAC hash.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
from typing import Optional

from sqlmodel import Session, select

from .config import settings
from .http_client import sync_client
from .models import BanRecord, IdentityStatus, IdentitySubmission, LEGAL_DOCS_VERSION, User, utcnow

logger = logging.getLogger("ragnar.identity")

_APPROVE_CONFIDENCE = 0.78
_ID_PROMPT = (
    "You are verifying a government photo ID for a trading-card marketplace. "
    "Look at the ID image (and selfie if provided). Return ONLY JSON with keys: "
    "doc_type (string|null — passport, drivers_license, national_id, other), "
    "full_name (string|null), "
    "doc_number (string|null — the primary ID number exactly as printed), "
    "dob (string|null YYYY-MM-DD), "
    "expiry (string|null YYYY-MM-DD), "
    "country (string|null), "
    "looks_authentic (bool — false if screenshot of screenshot, obvious fake, blank, or not an ID), "
    "selfie_match (bool|null — null if no selfie), "
    "confidence (0-1 float), "
    "notes (short string). "
    "If the image is not a readable government ID, set looks_authentic=false and confidence low."
)


def normalize_name(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _pepper() -> bytes:
    raw = (settings.identity_hash_pepper or settings.admin_token or "ragnar-dev-pepper").encode()
    return hashlib.sha256(raw).digest()


def hash_doc_number(doc_number: str | None, country: str | None = None) -> Optional[str]:
    num = re.sub(r"[^A-Za-z0-9]", "", (doc_number or "").upper())
    if len(num) < 4:
        return None
    material = f"{(country or '').upper()}|{num}".encode()
    return hmac.new(_pepper(), material, hashlib.sha256).hexdigest()


def names_match(a: str | None, b: str | None) -> bool:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Allow first+last reordering / partial containment for common ID formats.
    ta, tb = set(na.split()), set(nb.split())
    if len(ta) >= 2 and len(tb) >= 2 and len(ta & tb) >= 2:
        return True
    return na in nb or nb in na


def is_email_banned(session: Session, email: str) -> Optional[BanRecord]:
    e = normalize_email(email)
    if not e:
        return None
    return session.exec(select(BanRecord).where(BanRecord.email_normalized == e)).first()


def is_doc_banned(session: Session, doc_hash: str | None) -> Optional[BanRecord]:
    if not doc_hash:
        return None
    return session.exec(select(BanRecord).where(BanRecord.id_doc_hash == doc_hash)).first()


def assert_not_banned(session: Session, *, email: str | None = None, doc_hash: str | None = None) -> None:
    from fastapi import HTTPException, status

    if email and is_email_banned(session, email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email is banned from RAGNAR and cannot create a new account.",
        )
    if doc_hash and is_doc_banned(session, doc_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This identity document is banned from RAGNAR and cannot be used again.",
        )


def record_ban(
    session: Session,
    user: User,
    *,
    reason: str,
    banned_by: str | None,
) -> BanRecord:
    user.identity_status = IdentityStatus.banned.value
    user.banned_at = utcnow()
    user.ban_reason = (reason or "policy_violation")[:500]
    session.add(user)
    rec = BanRecord(
        email_normalized=normalize_email(user.email),
        id_doc_hash=user.id_doc_hash,
        legal_name_normalized=normalize_name(user.legal_name or user.name),
        reason=user.ban_reason,
        banned_by=banned_by,
        user_id_at_ban=user.id,
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)
    return rec


def accept_legal(user: User) -> None:
    now = utcnow()
    user.terms_accepted_at = now
    user.privacy_accepted_at = now
    user.terms_version = LEGAL_DOCS_VERSION
    user.legal_docs_version = LEGAL_DOCS_VERSION


def needs_legal_acceptance(user: User) -> bool:
    return not user.terms_accepted_at or user.legal_docs_version != LEGAL_DOCS_VERSION


def needs_identity(user: User) -> bool:
    if user.identity_status in {
        IdentityStatus.approved.value,
        IdentityStatus.pending.value,
        IdentityStatus.banned.value,
    }:
        return False
    return True


def _vision_extract(id_bytes: bytes, content_type: str, selfie_bytes: bytes | None = None) -> dict:
    if not settings.openai_api_key:
        return {
            "doc_type": None,
            "full_name": None,
            "doc_number": None,
            "looks_authentic": False,
            "confidence": 0.0,
            "notes": "OPENAI_API_KEY not configured — staff must review manually.",
            "provider": "manual",
        }

    def _part(data: bytes, ctype: str) -> dict:
        b64 = base64.b64encode(data).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{ctype or 'image/jpeg'};base64,{b64}"},
        }

    content = [{"type": "text", "text": _ID_PROMPT}, _part(id_bytes, content_type)]
    if selfie_bytes:
        content.append(_part(selfie_bytes, "image/jpeg"))

    try:
        resp = sync_client(timeout=50.0).post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_vision_model,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 500,
                "temperature": 0,
            },
            timeout=50.0,
        )
        if resp.status_code >= 400:
            logger.warning("ID vision failed %s: %s", resp.status_code, resp.text[:200])
            return {
                "looks_authentic": False,
                "confidence": 0.0,
                "notes": f"Vision provider error ({resp.status_code})",
                "provider": "openai",
            }
        text = resp.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", text, re.DOTALL)
        raw = json.loads(match.group(0) if match else text)
        raw["provider"] = f"openai:{settings.openai_vision_model}"
        return raw
    except Exception as exc:  # noqa: BLE001
        logger.warning("ID vision error: %s", exc)
        return {
            "looks_authentic": False,
            "confidence": 0.0,
            "notes": f"Vision error: {exc}",
            "provider": "openai",
        }


def run_id_check(
    session: Session,
    user: User,
    *,
    id_bytes: bytes,
    id_content_type: str,
    id_path: str,
    selfie_bytes: bytes | None = None,
    selfie_path: str | None = None,
) -> IdentitySubmission:
    assert_not_banned(session, email=user.email, doc_hash=user.id_doc_hash)

    raw = _vision_extract(id_bytes, id_content_type, selfie_bytes)
    confidence = float(raw.get("confidence") or 0)
    looks_ok = bool(raw.get("looks_authentic"))
    extracted_name = (raw.get("full_name") or "").strip() or None
    doc_hash = hash_doc_number(raw.get("doc_number"), raw.get("country"))
    if doc_hash:
        assert_not_banned(session, doc_hash=doc_hash)

    name_ok = names_match(extracted_name, user.name) or names_match(extracted_name, user.legal_name)
    selfie_ok = raw.get("selfie_match")
    if selfie_bytes is not None and selfie_ok is False:
        looks_ok = False

    if looks_ok and name_ok and confidence >= _APPROVE_CONFIDENCE and doc_hash:
        status = IdentityStatus.approved.value
        notes = raw.get("notes") or "Auto-approved by AI ID check."
    elif not looks_ok:
        status = IdentityStatus.rejected.value
        notes = raw.get("notes") or "Could not verify a genuine government ID."
    else:
        status = IdentityStatus.pending.value
        notes = raw.get("notes") or "Needs staff review (name match or confidence)."

    sub = IdentitySubmission(
        user_id=user.id,
        status=status,
        id_image_path=id_path,
        selfie_image_path=selfie_path,
        provider=raw.get("provider"),
        confidence=confidence,
        extracted_name=extracted_name,
        extracted_doc_type=(raw.get("doc_type") or None),
        id_doc_hash=doc_hash,
        notes=str(notes)[:1000],
    )
    session.add(sub)

    user.identity_status = status
    user.identity_checked_at = utcnow()
    user.identity_reject_reason = None if status == IdentityStatus.approved.value else str(notes)[:500]
    if extracted_name:
        user.legal_name = extracted_name[:160]
    if doc_hash:
        user.id_doc_hash = doc_hash
    session.add(user)
    session.commit()
    session.refresh(sub)
    return sub
