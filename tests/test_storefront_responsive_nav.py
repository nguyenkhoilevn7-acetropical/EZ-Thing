"""Regression contracts for the responsive customer storefront header.

Browser visual verification remains necessary for final acceptance.
"""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_cafe_nav_removes_duplicate_order_destination():
    js = (STATIC / "customer.js").read_text(encoding="utf-8")
    cafe_line = next(line for line in js.splitlines() if "cafe:[['Trang chủ'" in line)
    assert "['Thực đơn','#section-main']" in cafe_line
    assert "['Đặt hàng','#section-main']" not in cafe_line
    assert "['Đặt bàn','/reserve/cafe']" in cafe_line
    assert 'aria-controls="customer-primary-nav"' in js


def test_tablet_navigation_collapses_before_labels_overlap():
    css = (STATIC / "storefront-showcase.css").read_text(encoding="utf-8")
    assert "@media (min-width:721px) and (max-width:1280px)" in css
    assert ".customer-header.mobile-open .customer-primary-nav{display:flex}" in css
    assert ".menu-toggle{display:inline-flex!important}" in css
    assert ".customer-primary-nav a[href=\"/reserve/cafe\"]{display:block}" in css
    assert "@media (max-width:420px)" in css


def test_mobile_menu_state_and_hero_are_accessible():
    js = (STATIC / "customer.js").read_text(encoding="utf-8")
    css = (STATIC / "storefront-showcase.css").read_text(encoding="utf-8")
    assert "function setMobileMenuOpen(open)" in js
    assert "setMobileMenuOpen(false)" in js
    assert "aria-expanded" in js
    assert "max-width:570px" in css
    assert "body:has(#customer-root) .merchant-copy p{max-width:100%" in css
