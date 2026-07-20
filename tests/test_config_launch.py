"""Phase 5 — production config / CORS validation."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_config_launch.db")
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("SCHEMA_BOOTSTRAP", None)
os.environ["ENVIRONMENT"] = "development"

from app.config import settings, validate_launch_config


def teardown_function(_fn=None):
    settings.environment = "development"
    settings.allowed_origins = ["*"]
    settings.site_url = ""
    settings.public_base_url = "http://127.0.0.1:8000"
    settings.stripe_secret_key = ""
    settings.stripe_publishable_key = ""
    settings.stripe_webhook_secret = ""
    settings.payments_live = False
    settings.resend_api_key = ""
    settings.seed_demo = False
    os.environ.pop("SCHEMA_BOOTSTRAP", None)
    os.environ["ENVIRONMENT"] = "development"


def test_cors_never_star_in_production_mode():
    settings.environment = "production"
    settings.allowed_origins = ["*"]
    settings.site_url = "https://ragnarips.com"
    settings.public_base_url = "https://ragnarips.com"
    origins = settings.cors_allow_origins
    assert "*" not in origins
    assert "https://ragnarips.com" in origins


def test_validate_flags_wildcard_cors_in_production():
    settings.environment = "production"
    settings.allowed_origins = ["*"]
    settings.site_url = "https://ragnarips.com"
    settings.public_base_url = "https://ragnarips.com"
    settings.stripe_secret_key = "sk_live_x"
    settings.stripe_publishable_key = "pk_live_x"
    settings.stripe_webhook_secret = "whsec_x"
    settings.payments_live = True
    settings.resend_api_key = "re_x"
    settings.email_from = "RAGNAR <notifications@ragnarips.com>"
    settings.seed_demo = False
    os.environ["SCHEMA_BOOTSTRAP"] = "alembic"
    report = validate_launch_config()
    assert any("ALLOWED_ORIGINS" in e for e in report["errors"])


def test_dev_create_all_default():
    settings.environment = "development"
    os.environ.pop("SCHEMA_BOOTSTRAP", None)
    assert settings.use_create_all is True
    assert settings.is_production is False
