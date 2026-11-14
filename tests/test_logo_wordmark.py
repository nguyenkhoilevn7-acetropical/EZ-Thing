"""Regression tests for the approved flat EZ Thing wordmark."""
from pathlib import Path
from xml.etree import ElementTree as ET

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
ICON_PATH = STATIC / "icons"
VERSION = "20261115-sidebar-01"
SVG_VERSION = "minimal-01"


def test_flat_vector_logo_is_embedded_font_free_and_accessible():
    ns = {"svg": "http://www.w3.org/2000/svg"}
    for variant, foreground in (("light", "#202124"), ("dark", "#f8fafc")):
        for prefix in ("ez-mark", "ez-thing-wordmark"):
            svg = ET.parse(ICON_PATH / f"{prefix}-{variant}.svg").getroot()
            assert svg.attrib["role"] == "img"
            assert svg.attrib["aria-label"] in ("EZ", "EZ Thing")
            assert svg.find("svg:title", ns) is not None
            fills = [p.attrib["fill"] for p in svg.findall("svg:path", ns)]
            assert fills == [foreground, "#49c91c"]
            assert not svg.findall(".//svg:image", ns)
            assert not svg.findall(".//svg:filter", ns)
            assert not svg.findall(".//svg:linearGradient", ns)
            assert not svg.findall(".//svg:text", ns)


def test_public_header_and_footer_use_one_approved_full_wordmark():
    html = (STATIC / "public.html").read_text(encoding="utf-8")
    assert html.count('class="site-brand ez-site-brand"') == 2
    assert html.count('/assets/icons/ez-thing-wordmark-light.svg?v=' + SVG_VERSION) == 2
    assert 'class="ez-logo-word">Thing</span>' not in html
    assert "ez-brand-symbol" not in html


def test_platform_entrypoints_are_cache_busted_and_use_new_logo():
    for name in ("public.html", "index.html", "admin.html", "customer.html"):
        html = (STATIC / name).read_text(encoding="utf-8")
        assert f"brand-logo.css?v={VERSION}" in html, name
        assert "black-e-04" not in html, name
        assert "ez-logo-02" not in html, name
        assert "ez-thing-wordmark-" in html, name


def test_mobile_sizes_and_dark_mode_are_explicit():
    css = (STATIC / "brand-logo.css").read_text(encoding="utf-8")
    assert ".site-home .site-header .site-brand.ez-site-brand .ez-full-logo{width:128px" in css
    assert "width:clamp(88px,23vw,112px)" in css
    assert "width:clamp(84px,23vw,96px)" in css
    assert '[data-ez-merchant-theme="graphite"] .ez-wordmark .ez-full-logo-dark{display:block}' in css
    assert ".admin-ez-logo .ez-full-logo-dark{display:block" in css
    assert "margin-left:-" not in css
    assert "margin-right:-" not in css


def test_business_custom_logo_remains_unmodified():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "brand?.logo_url" in js
    assert "merchant-brand-image" in js
    assert 'ez-tenant-wordmark' in js
    assert "/assets/icons/ez-thing-wordmark-light.svg?v=minimal-01" in js
    assert "/assets/icons/ez-thing-wordmark-dark.svg?v=minimal-01" in js

def test_site_favicons_and_pwa_icons_use_minimal_ez_artwork():
    import json

    for name in ("public.html", "index.html", "admin.html", "customer.html", "public-shop.html"):
        html = (STATIC / name).read_text(encoding="utf-8")
        assert 'href="/assets/icons/ez-mark-light.svg?v=minimal-01"' in html, name
        assert 'href="/assets/icons/icon-192.png"' not in html, name
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert len(manifest["icons"]) == 2
    assert manifest["icons"][0]["src"].endswith("ez-mark-light.svg?v=minimal-01")
    assert manifest["icons"][1]["src"].endswith("ez-mark-maskable.svg?v=minimal-01")
    assert manifest["icons"][1]["purpose"] == "maskable"
    ET.parse(ICON_PATH / "ez-mark-maskable.svg")
