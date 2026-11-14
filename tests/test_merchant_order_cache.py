"""Regression: all filtered merchant orders must be actionable from the same data source."""
from pathlib import Path

def test_confirm_paid_uses_server_dashboard_order_list():
    js = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text(encoding="utf-8")
    assert "function confirmPaid(id){const o=(s.cache.orderDashboard?.orders||s.cache.orders||[]).find(x=>x.id===id);if(!o||o.status!=='open')return;" in js
    assert "function confirmPaid(id){const o=s.cache.orders?.find(x=>x.id===id)" not in js
    assert "function cancelOrder(id){" in js
