"""Guard merchant resiliency and staging infrastructure configuration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
BILLING = (ROOT / "app/static/billing-ui.js").read_text(encoding="utf-8")
DOCKER = (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_merchant_requests_timeout_and_trial_lock_transitions():
    assert "AbortController" in APP
    assert "setTimeout(()=>controller.abort()" in APP
    assert "finally{clearTimeout(timer)}" in APP
    assert "response.status===402" in APP
    assert "s.business.billing_required=true" in APP
    assert "history.replaceState(null,'','/app?tab=billing')" in APP


def test_dark_theme_inline_business_cards_are_theme_aware():
    assert "background:#fff" not in APP
    assert "background:var(--merchant-panel,var(--paper,#fff))" in APP


def test_async_gateway_payment_has_readback_not_browser_success():
    assert 'data-action="billing-refresh"' in BILLING
    assert "if(act==='billing-refresh')" in APP
    assert "checkout" in APP


def test_container_liveness_and_database_health_separated():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert '@app.get("/api/ready")' in main
    assert 'db.execute(text("SELECT 1")).scalar_one()' in main
    assert 'HEALTHCHECK' in DOCKER
    assert "/api/ready" in DOCKER
    assert "exec uvicorn" in DOCKER


def test_composite_indices_in_schema():
    from app.models import SaleOrder, SaleOrderItem, StockMovement
    def names(model):
        return {index.name for index in model.__table__.indexes}
    assert "ix_orders_biz_status_paid_at" in names(SaleOrder)
    assert "ix_order_items_biz_order" in names(SaleOrderItem)
    assert "ix_stock_movements_biz_ref" in names(StockMovement)
