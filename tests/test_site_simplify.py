"""Smoke checks for startup helpers and HTML page serving."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.main import serve_page
from app.models import SiteSetting
from app.site_config import DEFAULTS, retire_legacy_theme_values


def test_serve_page_returns_home():
    resp = serve_page("home.html")
    assert resp.status_code == 200
    assert Path(resp.path).name == "home.html"


def test_serve_page_missing_returns_json():
    resp = serve_page("does-not-exist.html", missing={"error": "gone"})
    assert resp.status_code == 200
    # JSONResponse body
    assert b"gone" in resp.body


def test_retire_legacy_theme_values_clears_old_palette(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(SiteSetting(key="theme_accent", value="#56c8f2"))
        session.add(SiteSetting(key="theme_gold", value="#d4a574"))  # current default — keep
        session.commit()
        cleared = retire_legacy_theme_values(session)
        assert cleared == 1
        assert session.get(SiteSetting, "theme_accent") is None
        assert session.get(SiteSetting, "theme_gold").value == "#d4a574"
        # Defaults still win for cleared keys
        assert DEFAULTS["theme_accent"] == "#8ecae6"


def test_html_routes_resolve():
    from app.main import app

    client = TestClient(app)
    for path in ("/", "/marketplace", "/login", "/cart", "/live", "/api.js"):
        # /api.js is under /static
        pass
    assert client.get("/").status_code == 200
    assert client.get("/marketplace").status_code == 200
    assert client.get("/static/api.js").status_code == 200
    assert client.get("/static/home.css").status_code == 200
    assert "home-polish" not in client.get("/").text
    assert "/static/api.js" in client.get("/marketplace").text
