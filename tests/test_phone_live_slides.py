"""Public phone preview uses real same-origin websites with secure iframe restrictions."""
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db"))

from fastapi.testclient import TestClient
from app.main import app

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
PREVIEW_PATHS = (
    "/menu/cafe",
    "/store/mart",
    "/store/online",
    "/booking/wellness",
    "/reserve/cafe",
)


def test_phone_slideshow_markup_and_accessible_controls():
    home = (STATIC / "public.html").read_text(encoding="utf-8")
    script = (STATIC / "premium.js").read_text(encoding="utf-8")
    css = (STATIC / "premium.css").read_text(encoding="utf-8")
    for path in PREVIEW_PATHS:
        assert f'data-preview-src="{path}"' in home
    assert home.count('class="live-preview-frame') == len(PREVIEW_PATHS)
    assert home.count('data-preview-index="') == len(PREVIEW_PATHS)
    assert "phone-banner" not in home  # old drawn fake interface was removed
    assert "live-preview-frame.is-active" in css
    for feature in ("6500", "IntersectionObserver", "visibilitychange",
                    "prefers-reduced-motion", "aria-pressed", "loadFrame"):
        assert feature in script


def test_only_public_customer_previews_allow_same_origin_embedding():
    with TestClient(app) as client:
        for path in PREVIEW_PATHS:
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["x-frame-options"] == "SAMEORIGIN"
            assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
        for path in ("/", "/admin", "/app", "/api/docs"):
            response = client.get(path)
            assert response.headers["x-frame-options"] == "DENY"
            assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
