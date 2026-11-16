"""Regression: manual cashier tender, idempotency, tenant security, and close preview."""
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

os.environ["DATABASE_URL"]="sqlite:///"+str(Path(__file__).parent/"pilot-tests.db")

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Membership, AuditEvent, SaleOrder
from app.pos_payments import ManualTenderReceipt


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED",raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def post(c,path,body,csrf=None):
    return c.post("/api"+path,json=body,headers=({"x-csrf-token":csrf} if csrf else {}))


def signup(c,suffix):
    r=c.post("/api/auth/signup",json={"name":"Cashier User",
        "email":f"cashier-{suffix}@example.com","password":"SafePassword!123"})
    assert r.status_code==201,r.text
    return r.json()["csrf_token"],r.json()["id"]


def setup(c,name="first"):
    csrf,user_id=signup(c,name)
    r=post(c,"/businesses",{"name":"Checkout Studio","industry":"fnb",
        "selected_plan":"PRO","need_tables":True,"need_inventory":True},csrf)
    assert r.status_code==201,r.text
    bid=r.json()["id"]
    pr=post(c,f"/businesses/{bid}/products",{"name":"Trà vải",
        "sku":"TRA-VA-"+name,"price_vnd":39000,"stock":20,
        "track_stock":True,"category":"Đồ uống"},csrf)
    assert pr.status_code==201,pr.text
    return csrf,bid,pr.json()["id"]


def make_order(c,csrf,bid,pid,price=39000):
    r=post(c,f"/businesses/{bid}/orders",{
        "idempotency_key":"order-"+uuid.uuid4().hex,
        "lines":[{"product_id":pid,"quantity":1,"selected_options":[]}]
    },csrf)
    assert r.status_code==201,r.text
    assert r.json()["total_vnd"]==price
    return r.json()["id"]


def payload(request="0123456789abcdef",method="cash",expected=39000,cash=50000,ref=""):
    return {"request_id":request,"method":method,"confirmed":True,
            "expected_total_vnd":expected,"cash_received_vnd":cash,
            "transfer_reference":ref}


def test_cash_change_and_no_double_booking():
    with TestClient(app) as c:
        csrf,bid,pid=setup(c)
        oid=make_order(c,csrf,bid,pid)
        path=f"/businesses/{bid}/pos-payments/{oid}"
        assert post(c,path,{**payload(),"confirmed":False},csrf).status_code==422
        assert post(c,path,payload(expected=39001),csrf).status_code==409
        assert post(c,path,payload(cash=38000),csrf).status_code==422
        assert post(c,path,payload(method="card",cash=None),csrf).status_code==422
        assert c.get("/api"+path).json()["payment"] is None
        payment=post(c,path,payload(),csrf)
        assert payment.status_code==200,payment.text
        result=payment.json()
        assert result["order"]["status"]=="paid"
        assert result["payment"]["amount_vnd"]==39000
        assert result["payment"]["cash_received_vnd"]==50000
        assert result["payment"]["change_vnd"]==11000
        assert result["payment"]["method"]=="cash"
        assert result["payment"]["provider_verified"] is False
        assert post(c,path,payload(),csrf).status_code==200
        assert post(c,path,payload(request="another-attempt-123"),csrf).status_code==409
        assert post(c,path,payload(cash=55000),csrf).status_code==409
        assert c.get("/api"+path).json()["payment"]["change_vnd"]==11000
        with SessionLocal() as db:
            assert db.query(ManualTenderReceipt).filter(
                ManualTenderReceipt.business_id==bid).count()==1
            actions=db.scalars(select(AuditEvent).where(
                AuditEvent.business_id==bid,
                AuditEvent.action=="pos.tender_recorded_manual")).all()
            assert len(actions)==1


def test_transfer_requires_explicit_confirmation_and_is_never_bank_verified():
    with TestClient(app) as c:
        csrf,bid,pid=setup(c)
        oid=make_order(c,csrf,bid,pid)
        path=f"/businesses/{bid}/pos-payments/{oid}"
        body=payload(request="bank-payment-12345",method="bank_transfer",
                     cash=None,ref="MB123ABC")
        assert post(c,path,{**body,"cash_received_vnd":39000},csrf).status_code==422
        assert post(c,path,{**body,"confirmed":False},csrf).status_code==422
        settled=post(c,path,body,csrf)
        assert settled.status_code==200,settled.text
        pay=settled.json()["payment"]
        assert pay["method"]=="bank_transfer"
        assert pay["cash_received_vnd"] is None
        assert pay["change_vnd"]==0
        assert pay["transfer_reference"]=="MB123ABC"
        assert pay["provider_verified"] is False
        report=c.get(f"/api/businesses/{bid}/cashier/close-preview")
        assert report.status_code==200,report.text
        data=report.json()
        assert data["manual_bank_transfer_vnd"]==39000
        assert data["manual_cash_vnd"]==0
        assert data["unknown_payment_method_vnd"]==0
        assert data["bank_verified"] is False
        assert data["cash_counted_vnd"] is None
        assert data["can_close_shift"] is False


def test_legacy_payment_is_unclassified_not_falsely_cash():
    with TestClient(app) as c:
        csrf,bid,pid=setup(c)
        oid=make_order(c,csrf,bid,pid)
        old=post(c,f"/businesses/{bid}/orders/{oid}/paid",{"confirmed":True},csrf)
        assert old.status_code==200,old.text
        assert post(c,f"/businesses/{bid}/pos-payments/{oid}",payload(),csrf).status_code==409
        report=c.get(f"/api/businesses/{bid}/cashier/close-preview")
        assert report.status_code==200,report.text
        assert report.json()["unknown_payment_method_vnd"]==39000
        assert report.json()["manual_cash_vnd"]==0


def test_tenant_isolation_and_cashier_staff_is_audited():
    with TestClient(app) as owner, TestClient(app) as other, TestClient(app) as staff:
        csrf,bid,pid=setup(owner,"owner")
        another_csrf,another_bid,_=setup(other,"other")
        oid=make_order(owner,csrf,bid,pid)
        path=f"/businesses/{bid}/pos-payments/{oid}"
        assert other.get("/api"+path).status_code==404
        assert post(other,path,payload(),another_csrf).status_code==404
        assert staff.get("/api"+path).status_code==401
        staff_csrf,staff_id=signup(staff,"staff")
        with SessionLocal() as db:
            db.add(Membership(id=str(uuid.uuid4()),business_id=bid,
                              user_id=staff_id,role="staff"))
            db.commit()
        paid=post(staff,path,payload(request="staff-payment-12345"),staff_csrf)
        assert paid.status_code==200,paid.text
        assert paid.json()["order"]["status"]=="paid"
        with SessionLocal() as db:
            receipt=db.get(ManualTenderReceipt,oid)
            assert receipt.confirmed_by==staff_id
        assert staff.get(f"/api/businesses/{bid}/cashier/close-preview").status_code==403


def test_payment_attempt_cannot_resurrect_cancelled_order():
    with TestClient(app) as c:
        csrf,bid,pid=setup(c)
        oid=make_order(c,csrf,bid,pid)
        cancelled=post(c,f"/businesses/{bid}/orders/{oid}/cancel",
                       {"confirmed":True,"reason":"Customer cancelled"},csrf)
        assert cancelled.status_code==200,cancelled.text
        result=post(c,f"/businesses/{bid}/pos-payments/{oid}",payload(),csrf)
        assert result.status_code==409,result.text
        with SessionLocal() as db:
            assert db.get(SaleOrder,oid).status=="cancelled"
            assert db.get(ManualTenderReceipt,oid) is None
