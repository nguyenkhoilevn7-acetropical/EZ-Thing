"""A truthful end-of-day summary based on paid_at, not guessed cash in drawer."""
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def setup(c, name):
    response = c.post("/api/auth/signup", json={
        "name":"Cashier Owner", "email":name, "password":"SafePassword!123"})
    assert response.status_code==201, response.text
    csrf=response.json()["csrf_token"]
    business=c.post("/api/businesses",headers={"x-csrf-token":csrf},json={
        "name":"Cashier shop", "industry":"fnb", "selected_plan":"PRO",
        "need_tables":True, "need_inventory":True, "need_insights":True})
    assert business.status_code==201, business.text
    bid=business.json()["id"]
    branch=c.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
    product=c.post(f"/api/businesses/{bid}/products",
                   headers={"x-csrf-token":csrf},json={
        "name":"Test Tea","sku":"TEST-TEA", "category":"Tea",
        "price_vnd":35000, "track_stock":False})
    assert product.status_code==201, product.text
    return csrf,bid,branch,product.json()["id"]


def test_cashier_preview_uses_vietnam_paid_day_and_no_fabricated_cash(c=None):
    with TestClient(app) as owner:
        csrf,bid,branch,pid=setup(owner,"cashier-one@example.com")
        order=owner.post(f"/api/businesses/{bid}/orders",
                         headers={"x-csrf-token":csrf},json={
            "idempotency_key":"cashier-shift-order-00001",
            "branch_id":branch,
            "lines":[{"product_id":pid,"quantity":2}]})
        assert order.status_code==201, order.text
        oid=order.json()["id"]
        day=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date().isoformat()
        url=f"/api/businesses/{bid}/cashier/close-preview?day={day}&branch_id={branch}"
        initial=owner.get(url)
        assert initial.status_code==200, initial.text
        assert initial.json()["paid_at_day"]["amount_vnd"]==0
        assert initial.json()["created_at_day"]["open_now"]==1

        paid=owner.post(f"/api/businesses/{bid}/orders/{oid}/paid",
                        headers={"x-csrf-token":csrf},json={"confirmed":True})
        assert paid.status_code==200, paid.text
        report=owner.get(url)
        assert report.status_code==200, report.text
        data=report.json()
        assert data["mode"]=="read_only_preview"
        assert data["can_close_shift"] is False
        assert data["bank_verified"] is False
        assert data["cash_counted_vnd"] is None
        assert data["cash_variance_vnd"] is None
        assert data["paid_at_day"]=={"count":1,"amount_vnd":70000}
        assert data["unknown_payment_method_vnd"]==70000
        assert data["created_at_day"]["open_now"]==0
        assert data["entries"][0]["order_id"]==oid

        future=(date.today()+timedelta(days=365)).isoformat()
        assert owner.get(f"/api/businesses/{bid}/cashier/close-preview?day={future}").status_code==422
        assert owner.get(f"/api/businesses/{bid}/cashier/close-preview?branch_id=not-a-branch").status_code==404
        with TestClient(app) as outsider:
            setup(outsider,"cashier-two@example.com")
            assert outsider.get(url).status_code==404


def test_cashier_ui_and_print_document_assets_exist():
    static=Path(__file__).resolve().parents[1]/"app/static"
    html=(static/"index.html").read_text()
    app_js=(static/"app.js").read_text()
    operations=(static/"operations-v5.js").read_text()
    docs=(static/"merchant-print-documents.js").read_text()
    for asset in ("merchant-print-documents.js","merchant-print-documents.css"):
        assert asset in html
    assert "print-doc-open" in app_js
    assert "close-preview" in operations
    assert "ez-document-print-content" in docs
    assert "print-doc-browser" not in docs  # Dedicated scoped click handlers.
