"""Regression guards for finite customer-demo boot and asset freshness."""
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "app" / "static"

def test_customer_demo_has_recovery_script_before_app():
    page = (ASSETS / "customer.html").read_text(encoding="utf-8")
    assert page.index("customer-watchdog.js") < page.index("customer.js?")
    assert "customer.js?v=20261114-demo-loading-01" in page
    assert "enfix-31" in page

def test_customer_api_uses_bounded_wait_and_retry():
    app = (ASSETS / "customer.js").read_text(encoding="utf-8")
    watchdog = (ASSETS / "customer-watchdog.js").read_text(encoding="utf-8")
    assert "controller.abort()" in app
    assert "clearTimeout(timer)" in app
    assert "retry-demo" in app
    assert "window.setTimeout(recover,55000)" in watchdog
    assert "customer-loading" in watchdog

def test_translations_yield_to_network_tasks():
    i18n=(ASSETS / "i18n.js").read_text(encoding="utf-8")
    assert "window.setTimeout(()=>{scheduled=false;apply();}, 32)" in i18n
    assert "queueMicrotask(()=>{scheduled=false;apply();});" not in i18n
