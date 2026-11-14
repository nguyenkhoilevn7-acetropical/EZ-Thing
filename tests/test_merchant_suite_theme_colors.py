"""Restaurant/Reservations accent follows the selected merchant palette.

The diagnostic browser test also checks computed CSS colors for all three themes.
"""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_merchant_suite_inherits_theme_tokens():
    css = (STATIC / "merchant-restaurant-suite.css").read_text(encoding="utf-8")
    scoped = css.split("Shared theme contract for the Restaurant Host Desk", 1)[1]
    assert "--suite-accent:var(--merchant-accent,var(--green))" in scoped
    assert "--suite-accent-hover:var(--merchant-accent-hover,var(--green2))" in scoped
    assert "--suite-panel:var(--merchant-panel,var(--paper))" in scoped
    assert "--suite-action-ink:#111820" in scoped
    assert ".suite-container .suite-primary" in scoped
    assert "background:var(--suite-accent)" in scoped
    assert ".suite-container .suite-save" in scoped
    assert ".suite-container .floor-zone-tabs button.active" in scoped
    assert ".suite-container .suite-booking-actions a" in scoped
    assert ".suite-container :is(input,select,textarea):focus" in scoped
    assert "color:var(--suite-accent)" in scoped


def test_apple_and_graphite_accents_stay_blue_while_tropical_is_green():
    palette = (STATIC / "merchant-palette-refinement.css").read_text(encoding="utf-8")
    theme = (STATIC / "merchant-theme.css").read_text(encoding="utf-8")
    assert "--merchant-accent:#0066cc" in palette
    assert "--merchant-accent:#a8cfff" in palette
    assert "--green:#0d936b" in (STATIC / "styles.css").read_text(encoding="utf-8")
    assert ':root[data-ez-merchant-theme="apple"]' in theme
    assert ':root[data-ez-merchant-theme="graphite"]' in theme
    assert 'data-ez-merchant-theme="graphite"] .suite-container' in (
        STATIC / "merchant-restaurant-suite.css"
    ).read_text(encoding="utf-8")


def test_business_status_colors_are_not_overridden_as_brand_accents():
    css = (STATIC / "merchant-restaurant-suite.css").read_text(encoding="utf-8")
    scoped = css.split("Shared theme contract for the Restaurant Host Desk", 1)[1]
    assert ".suite-tag.tag-pending" not in scoped
    assert ".suite-tag.tag-confirmed" not in scoped
    assert ".suite-table.state-reserved" not in scoped
    assert ".suite-table.state-serving" not in scoped
    assert "Table/booking semantic colors intentionally remain untouched" in scoped


def test_new_stylesheet_version_is_loaded():
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "merchant-restaurant-suite.css?v=20261114-ui-25" in index
    assert "merchant-restaurant-suite.css?v=20261114-ui-24" not in index
