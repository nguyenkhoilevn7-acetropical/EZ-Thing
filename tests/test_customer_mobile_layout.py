"""Regression checks for the mobile cafe catalog shown in the 14 Nov screenshot.

These are source/wiring tests; visual behavior still needs a browser viewport check.
"""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_mobile_css_is_loaded_after_all_existing_styles():
    page = source("customer.html")
    styles = ["customer.css", "premium.css", "storefront-showcase.css", "i18n.css", "customer-mobile-fixes.css"]
    positions = [page.index(f"/assets/{name}") for name in styles]
    assert positions == sorted(positions)
    assert "customer-mobile-fixes.css?v=" in page


def test_catalog_chips_do_not_clip_start_and_are_scrollable():
    css = source("customer-mobile-fixes.css")
    assert "justify-content: flex-start;" in css
    assert "overflow-x: auto;" in css
    assert "flex: 0 0 auto;" in css
    assert "scroll-snap-align: start;" in css


def test_search_icon_is_vector_centered():
    css = source("customer-mobile-fixes.css")
    assert ".search-wrap::before" in css
    assert "translateY(-50%)" in css
    assert "data:image/svg+xml" in css


def test_products_keep_footer_alignment():
    css = source("customer-mobile-fixes.css")
    assert ".customer-product" in css
    assert "flex-direction: column;" in css
    assert ".item-foot" in css
    assert "margin-top: auto;" in css


def test_mobile_customer_language_switch_is_in_menu():
    lang = source("i18n.js")
    assert "const mobileCustomerNav=compact?" in lang
    assert ".customer-primary-nav" in lang
    assert "const target=mobileCustomerNav||" in lang
    css = source("customer-mobile-fixes.css")
    assert ".customer-primary-nav .ez-language-switch" in css


def test_category_scroll_is_preserved_across_search_and_filter():
    js = source("customer.js")
    assert "const categoryScroll=content?.querySelector('.category-bar')?.scrollLeft||0;" in js
    assert "nextBar.scrollLeft=categoryScroll" in js
    assert "scrollIntoView({block:'nearest',inline:'nearest'})" in js


def test_customer_fix_is_scoped_to_customer_root():
    css = source("customer-mobile-fixes.css")
    assert "body:has(#customer-root)" in css
    assert ".site-home" not in css
    assert "body:has(#admin-root)" not in css
