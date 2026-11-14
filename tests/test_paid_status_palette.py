"""Paid status badges use blue across merchant themes without changing payment data."""
from pathlib import Path
import re

STATIC=Path(__file__).resolve().parents[1]/"app"/"static"

def test_paid_status_uses_dedicated_class_not_green():
    js=(STATIC/"app.js").read_text(encoding="utf-8")
    status=js.split("function status(val){",1)[1].split("\n",1)[0]
    assert 'val===\'paid\'?' in status
    assert 'class="pill paid"' in status
    assert 'class="pill green"' not in status
    assert 'val===\'open\'?' in status
    assert 'class="pill yellow"' in status

def test_blue_paid_badge_is_legible_in_all_three_themes():
    css=(STATIC/"merchant-palette-refinement.css").read_text(encoding="utf-8")
    for name in ("apple","tropical","graphite"):
        rule=css.split(f':root[data-ez-merchant-theme="{name}"] .pill.paid{{',1)[1].split("}",1)[0]
        assert "color:" in rule and "background:" in rule and "border-color:" in rule
    assert "color:#0057b8;" in css
    assert "color:#c5deff;" in css
    assert "background:#203b61;" in css

def test_cache_bust_for_paid_status_assets():
    html=(STATIC/"index.html").read_text(encoding="utf-8")
    assert '/assets/merchant-palette-refinement.css?v=20261114-ui-23' in html
    match = re.search(r'/assets/app\\.js\\?v=20261114-ui-(\\d+)', html)
    assert match is not None and int(match.group(1)) >= 23
