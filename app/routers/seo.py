"""SEO endpoints: robots.txt and a dynamic sitemap.xml."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import Seller

router = APIRouter(tags=["seo"])


def base_url() -> str:
    return (settings.site_url or settings.public_base_url).rstrip("/")


@router.get("/robots.txt", include_in_schema=False)
def robots() -> Response:
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin",
        "Disallow: /api/",
        f"Sitemap: {base_url()}/sitemap.xml",
        "",
    ])
    return Response(content=body, media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(session: Session = Depends(get_session)) -> Response:
    base = base_url()
    urls = [f"{base}/", f"{base}/marketplace", f"{base}/stores"]
    stores = session.exec(select(Seller).where(Seller.store_public == True)).all()  # noqa: E712
    urls += [f"{base}/store/{s.handle}" for s in stores]

    items = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
