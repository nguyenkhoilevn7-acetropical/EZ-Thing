"""Static wiring contract: no browser dependencies, catches stale frontend paths."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
STATIC = BASE / "app" / "static"


def test_customer_v04_assets_and_routes_are_connected():
    html = (STATIC / "customer.html").read_text(encoding="utf-8")
    css = (STATIC / "customer-v04.css").read_text(encoding="utf-8")
    js = (STATIC / "customer.js").read_text(encoding="utf-8")
    assert '/assets/customer.js' in html
    assert '/assets/customer-v04.css' in html
    assert 'data-channel=wellness' in css
    assert 'data-channel=mart' in css
    assert 'data-channel=online' in css
    assert 'customer-bottom-nav' in css
    assert 'customer-bottom-nav' in js
    assert 'async function slots()' in js
    assert 'slotRequestId' in js
    assert "'/quote'" in js
    assert "'/status'" in js
    assert 'function verifyCartQuote(' in js
    assert 'function statusHTML(' in js


def test_backend_quote_and_checkout_share_authoritative_rules():
    public = (BASE / "app" / "public.py").read_text(encoding="utf-8")
    assert 'def resolve_preview_lines(' in public
    assert 'def preview_quote(' in public
    assert 'quantities, products, total = resolve_preview_lines(db, business, body.lines)' in public
    assert 'quantities, products, total = resolve_preview_lines(db, b, body.lines)' in public
    assert 'def preview_order_status(' in public
    assert 'def preview_appointment_status(' in public
    assert 'FLOWS = {' in public
