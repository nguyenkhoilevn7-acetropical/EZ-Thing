"""Homepage phone must rotate among real, guarded customer storefronts."""
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
FRONTEND = (STATIC / "public.html").read_text(encoding="utf-8")
JS = (STATIC / "industry-phone.js").read_text(encoding="utf-8")
CSS = (STATIC / "industry-phone.css").read_text(encoding="utf-8")


def test_live_storefront_urls_are_used_and_not_external_mockups():
    assert 'data-industry-carousel' in FRONTEND
    assert '/assets/industry-phone.js' in FRONTEND
    assert '/assets/industry-phone.css' in FRONTEND
    assert JS.count("href: '/menu/cafe'") == 1
    for route in ('/menu/cafe', '/store/mart', '/store/online', '/booking/wellness'):
        assert "href: '" + route + "'" in JS
    assert "frame.src = slides[index].href" in JS
    assert 'data-industry-link' in FRONTEND


def test_carousel_is_accessible_and_respects_motion_preferences():
    for label in ('data-industry-action', 'data-industry-index', 'aria-pressed'):
        assert label in FRONTEND or label in JS
    for feature in ('touchstart', 'touchend', 'ArrowRight', 'ArrowLeft',
                    'visibilitychange', 'prefers-reduced-motion: reduce',
                    'ezthing:language-changed'):
        assert feature in JS
    assert '.industry-frame.is-active' in CSS
    assert 'pointer-events:none' in CSS


def test_same_origin_embedding_exception_is_only_for_public_demos():
    with TestClient(app) as client:
        homepage = client.get('/')
        assert homepage.status_code == 200
        assert homepage.headers['x-frame-options'] == 'DENY'
        assert "frame-src 'self'" in homepage.headers['content-security-policy']

        for route in ('/menu/cafe', '/store/mart', '/store/online', '/booking/wellness'):
            response = client.get(route)
            assert response.status_code == 200
            assert response.headers['x-frame-options'] == 'SAMEORIGIN'
            assert "frame-ancestors 'self'" in response.headers['content-security-policy']

        for route in ('/app', '/admin', '/api/catalog'):
            response = client.get(route)
            assert response.headers['x-frame-options'] == 'DENY'
            assert "frame-ancestors 'none'" in response.headers['content-security-policy']
