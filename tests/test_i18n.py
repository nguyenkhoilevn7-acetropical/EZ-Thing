"""Contract coverage for the shared language preference and localized API."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.i18n import selected_language, translate_error
from app.main import app

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_catalog_supports_english_and_preserves_machine_keys():
    with TestClient(app) as cli:
        vi = cli.get("/api/catalog")
        en = cli.get("/api/catalog", headers={"Accept-Language": "en-US,en;q=0.8"})
        assert vi.status_code == en.status_code == 200
        assert vi.json()["industries"]["retail"] == "Bán lẻ"
        assert en.json()["industries"]["retail"] == "Retail"
        assert en.json()["features"]["products"][0] == "Products"
        assert vi.json()["plans"] == en.json()["plans"]
        assert en.json()["roadmap"] == vi.json()["roadmap"]
        assert en.json()["language"] == "en"
        assert en.headers["content-language"] == "en"
        assert en.headers["vary"] == "Accept-Language, Cookie"


def test_en_error_response_and_vi_fallback():
    with TestClient(app) as cli:
        en = cli.get("/api/auth/me", headers={"Accept-Language": "en"})
        vi = cli.get("/api/auth/me", headers={"Accept-Language": "vi"})
        assert en.status_code == vi.status_code == 401
        assert en.json()["detail"] == "Please sign in"
        assert vi.json()["detail"] == "Vui lòng đăng nhập"
        assert translate_error("Không đủ tồn kho: Áo thun", "en") == "Insufficient stock: Áo thun"
        assert translate_error("Unknown error", "en") == "Unknown error"


def test_languages_endpoint_with_cookie_and_explicit_header():
    with TestClient(app) as cli:
        cli.cookies.set("ez_lang", "en")
        res = cli.get("/api/languages", headers={"Accept-Language": "en"})
        assert res.status_code == 200
        assert res.json()["current"] == "en"
        assert res.json()["supported"] == ["vi", "en"]
        override = cli.get("/api/languages", headers={"Accept-Language": "vi"})
        assert override.json()["current"] == "vi"


def test_i18n_assets_are_shared_by_all_four_portals():
    for path in ("public.html", "customer.html", "index.html", "admin.html"):
        html = (STATIC / path).read_text(encoding="utf-8")
        assert "/assets/i18n.js" in html
        assert "/assets/i18n.css" in html
        assert html.index("i18n.js") < html.index(
            ("premium.js" if path == "public.html" else
             "customer.js" if path == "customer.html" else
             "admin.js" if path == "admin.html" else "app.js")
        )
    js = (STATIC / "i18n.js").read_text(encoding="utf-8")
    assert "ezthing_language" in js
    assert "ezthing:language-changed" in js
    assert "aria-pressed" in js
    assert "MutationObserver" in js


def test_all_api_clients_forward_language_preference():
    for path in ("app.js", "customer.js", "admin.js"):
        js = (STATIC / path).read_text(encoding="utf-8")
        assert "'Accept-Language':window.EZI18N?.language()||'vi'" in js


def test_broken_online_living_photo_and_fallback_handled():
    js = (STATIC / "customer.js").read_text(encoding="utf-8")
    assert "photo-1493663284031-b7e3aefcae8e" in js
    assert "photo-1493663284031-b7e3aefcae8c" not in js
    assert "storefront-fallback.svg" in js
    assert (STATIC / "storefront-fallback.svg").is_file()


def test_language_selector_escapes_sticky_headers_on_mobile():
    js = (STATIC / "i18n.js").read_text(encoding="utf-8")
    css = (STATIC / "i18n.css").read_text(encoding="utf-8")
    assert "compact?document.body" in js
    assert "addEventListener('resize',schedule)" in js
    assert "bottom:calc(86px + env(safe-area-inset-bottom))" in css
