"""DATABASE_URL normalization for Supabase / Postgres."""
from __future__ import annotations

from app.config import normalize_database_url


def test_supabase_uri_gets_psycopg_and_ssl():
    raw = (
        "postgresql://postgres:secret@db.tmlwajtttnkhkmrsdnie.supabase.co:5432/postgres"
    )
    out = normalize_database_url(raw)
    assert out.startswith("postgresql+psycopg://")
    assert "sslmode=require" in out
    assert "db.tmlwajtttnkhkmrsdnie.supabase.co" in out
    assert "secret" in out


def test_postgres_scheme_alias():
    out = normalize_database_url("postgres://u:p@localhost:5432/ragnar")
    assert out.startswith("postgresql+psycopg://")
    assert "sslmode" not in out  # local Postgres left alone


def test_sqlite_unchanged():
    assert normalize_database_url("sqlite:///./ragnar.db") == "sqlite:///./ragnar.db"


def test_existing_sslmode_preserved():
    raw = "postgresql://u:p@db.x.supabase.co:5432/postgres?sslmode=verify-full"
    out = normalize_database_url(raw)
    assert "sslmode=verify-full" in out
    assert out.count("sslmode=") == 1


def test_pooler_helpers():
    from app.config import is_supabase_direct_db_url, is_supabase_pooler_url

    pooler = normalize_database_url(
        "postgresql://u:p@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    )
    direct = normalize_database_url(
        "postgresql://u:p@db.xyz.supabase.co:5432/postgres"
    )
    assert is_supabase_pooler_url(pooler)
    assert is_supabase_direct_db_url(direct)
    assert not is_supabase_pooler_url(direct)
