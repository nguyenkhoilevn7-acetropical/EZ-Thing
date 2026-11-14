"""Regressions for Fold popup clipping, dark surfaces and stale homepage slider."""
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]
STATIC = BASE / "app" / "static"


def get(name):
    return (STATIC / name).read_text(encoding="utf-8")


def test_palette_is_viewport_fixed_and_repositioned():
    css = get("merchant-theme.css")
    js = get("merchant-theme.js")
    assert "position:fixed;left:12px;right:auto" in css
    assert "max-height:min(350px,calc(100dvh - 24px))" in css
    assert "positionPicker(menu, toggle)" in js
    assert "document.documentElement.clientWidth" in js
    assert "Math.max(12, Math.min(" in js
    assert "window.visualViewport?.addEventListener('resize'" in js
    assert "closePicker(true)" in js


def test_refinement_is_loaded_after_responsive_and_contains_no_public_bundle_leak():
    index = get("index.html")
    assert index.index("merchant-theme.css") < index.index("merchant-responsive.css")
    assert index.index("merchant-responsive.css") < index.index("merchant-palette-refinement.css")
    for name in ("public.html", "customer.html", "admin.html"):
        assert "merchant-palette-refinement.css" not in get(name)


def test_dark_neutral_cards_and_popup_are_dark_not_white():
    css = get("merchant-palette-refinement.css")
    for selector in (
        ".surface", ".kpi", ".task-item", ".table-tile",
        ".orders-table tbody tr", ".dialog", ".setup-card",
        ".merchant-theme-menu", ".merchant-theme-trigger",
        ".orders-table tbody td:nth-child(2)"
    ):
        assert selector in css
    assert "--merchant-panel:#1d1f25" in css
    assert "--merchant-page:#111216" in css
    assert "--merchant-muted:#b7b9c3" in css
    assert "background:var(--merchant-panel)!important" in css
    assert "background:var(--merchant-panel-alt)!important" in css
    assert ".pill.green" in css and ".pill.yellow" in css and ".pill.red" in css


def test_light_theme_accents_are_blue_and_do_not_leave_default_green():
    css = get("merchant-palette-refinement.css")
    assert "--merchant-accent:#0066cc" in css
    assert ".kpi .kpi-icon:not(.orange):not(.red):not(.blue)" in css
    assert ".task-item .task-icon" in css
    assert ".b-avatar" in css
    assert ".filter-btn.active" in css
    assert ".switch.on" in css


def test_missing_merchant_translations_were_added():
    translations = get("i18n.js")
    for token in ("Doanh thu hôm nay", "Từ đơn đã xác nhận nhận tiền",
                  "Cảnh báo tồn kho", "Sản phẩm trong danh mục",
                  "Còn tối đa 5 sản phẩm"):
        assert token in translations
    assert "^(" in translations and "đơn đang xử lý" in translations


def test_public_homepage_versioned_and_no_store():
    main = (BASE / "app" / "main.py").read_text(encoding="utf-8")
    public = get("public.html")
    sw = get("sw.js")
    assert 'FileResponse(ASSETS / "public.html", headers={"Cache-Control": "no-store, max-age=0"})' in main
    assert 'premium.js?v=20261114-ui-21' in public
    assert "data-ez-preview" in public and "data-preview-src" in public
    assert "const SHELL='ezthing-shell-v6'" in sw
