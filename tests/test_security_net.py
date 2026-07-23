"""URL / SSRF guard unit tests."""
from __future__ import annotations

import pytest

from app.security_net import is_safe_public_https_url, require_safe_media_url


def test_https_public_ok():
    assert is_safe_public_https_url("https://res.cloudinary.com/demo/image/upload/sample.jpg")


def test_http_blocked_by_default():
    assert not is_safe_public_https_url("http://example.com/a.jpg")


def test_localhost_blocked():
    assert not is_safe_public_https_url("https://localhost/admin")
    assert not is_safe_public_https_url("https://127.0.0.1/x")


def test_metadata_blocked():
    assert not is_safe_public_https_url("https://169.254.169.254/latest/meta-data")


def test_relative_uploads_ok():
    assert require_safe_media_url("/uploads/scan-abc.jpg") == "/uploads/scan-abc.jpg"


def test_path_traversal_rejected():
    with pytest.raises(ValueError):
        require_safe_media_url("/uploads/../etc/passwd")
