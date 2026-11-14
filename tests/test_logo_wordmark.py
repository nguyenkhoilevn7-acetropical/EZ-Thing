"""Regression checks for EZ Thing branding across responsive entrypoints."""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_mark_does_not_overlap_the_thing_wordmark():
    css = (STATIC / "brand-logo.css").read_text(encoding="utf-8")
    assert ".site-brand.ez-site-brand{display:inline-flex;align-items:center;gap:4px" in css
    assert "margin-left:-" not in css
    assert "margin-right:-" not in css
    assert ".ez-site-brand .ez-brand-symbol{display:inline-flex;width:69px;height:49px;flex:0 0 69px" in css
    assert ".site-home .site-header .ez-site-brand .ez-brand-symbol{width:55px;height:39px;flex-basis:55px}" in css
    assert "@media(max-width:370px)" in css


def test_updated_stylesheet_is_loaded_for_every_platform_entrypoint():
    for name in ("public.html", "index.html", "admin.html", "customer.html"):
        html = (STATIC / name).read_text(encoding="utf-8")
        assert "brand-logo.css?v=20261114-ez-logo-02" in html, name
        assert "brand-logo.css?v=20261114-ez-logo-01" not in html, name


def test_mark_and_thing_are_not_duplicated_in_public_header():
    html = (STATIC / "public.html").read_text(encoding="utf-8")
    assert html.count('class="site-brand ez-site-brand"') == 2
    assert html.count('class="ez-logo-word">Thing</span>') == 2
    assert html.count('src="/assets/icons/ez-mark-light.svg"') == 2
