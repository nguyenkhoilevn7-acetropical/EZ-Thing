"""Merchant appearance defaults to frontend light theme and supports 3 local choices."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/"app"/"static"


def test_theme_assets_are_only_in_backoffice():
    backoffice=(ASSETS/"index.html").read_text(encoding="utf-8")
    for asset in ("merchant-theme.css", "merchant-theme.js"):
        assert "/assets/"+asset in backoffice
    assert backoffice.index("merchant-theme.js") < backoffice.index("app.js")
    for other in ("public.html", "customer.html", "admin.html"):
        html=(ASSETS/other).read_text(encoding="utf-8")
        assert "/assets/merchant-theme." not in html


def test_three_themes_have_safe_defaults_and_business_scoping():
    script=(ASSETS/"merchant-theme.js").read_text(encoding="utf-8")
    for name in ("apple", "tropical", "graphite"):
        assert name in script
    assert "ezthing_merchant_theme:" in script
    assert "THEMES.includes(saved) ? saved : 'apple'" in script
    assert "THEMES.includes(next)" in script
    assert "setBusiness(id)" in script
    assert "aria-pressed" in script
    assert "ezthing:language-changed" in script
    assert "data-merchant-theme-toggle" in script


def test_merchant_picker_is_in_topbar_and_palette_changes_are_ui_only():
    app=(ASSETS/"app.js").read_text(encoding="utf-8")
    assert "window.EZMerchantTheme?.setBusiness(b.id)" in app
    assert "window.EZMerchantTheme?.pickerMarkup()" in app
    css=(ASSETS/"merchant-theme.css").read_text(encoding="utf-8")
    for name in ("apple", "graphite"):
        assert 'data-ez-merchant-theme="'+name+'"' in css
    assert ".merchant-theme-menu[hidden]" in css
    assert ".dashboard-welcome" in css
    assert ".mobile-nav" in css
    assert "prefers-reduced-motion" in css
