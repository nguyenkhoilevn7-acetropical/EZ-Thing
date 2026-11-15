"""Lightweight regression checks for approved 2026-11-14 storefront mockups.

These are static contract tests, not a substitute for device/browser acceptance.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
STATIC = BASE / "app" / "static"


def test_all_preview_templates_share_showcase_visuals():
    html = (STATIC / "customer.html").read_text(encoding="utf-8")
    css = (STATIC / "storefront-showcase.css").read_text(encoding="utf-8")
    js = (STATIC / "customer.js").read_text(encoding="utf-8")
    assert "/assets/storefront-showcase.css" in html
    assert "/assets/customer.js" in html
    for label in ("EZ THING CAFE", "EZ THING MART", "EZ THING SPA & WELLNESS"):
        assert label in js
    for template in ("kind-fnb", "kind-retail", "kind-online", "kind-services"):
        assert template in css
    for feature in ("customer-primary-nav", "shop-benefits", "showcase-grid", "hero-actions-shop"):
        assert feature in js and feature in css
    for action in ("open-cart", "shop-scroll", "book-scroll", "category", "open-booking"):
        assert action in js


def test_storefront_does_not_swap_out_server_authoritative_demo_flow():
    js = (STATIC / "customer.js").read_text(encoding="utf-8")
    assert "'/preview/'+channel+'/checkout'" in js
    assert "'/preview/wellness/appointments'" in js
    assert "const data=await api('/preview/'+channel)" in js
    assert "st.csrf=me.csrf_token" in js
    assert "st.pendingId" in js
    assert "price_vnd" in js


def test_only_dedicated_photo_host_is_csp_allowed():
    api = (BASE / "app" / "main.py").read_text(encoding="utf-8")
    assert "img-src 'self' data: blob: https://images.unsplash.com;" in api
    assert "script-src 'self'" in api
    assert "frame-ancestors 'none'" in api


def test_mocks_are_labeled_and_do_not_claim_real_orders():
    js = (STATIC / "customer.js").read_text(encoding="utf-8")
    assert "KHÔNG THANH TOÁN HOẶC GIAO HÀNG THẬT" in js
    assert "Chỉ sử dụng dữ liệu DEMO" in js
    assert "Giá do máy chủ cung cấp" in js
