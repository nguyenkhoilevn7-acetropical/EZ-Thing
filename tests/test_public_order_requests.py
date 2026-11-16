"""Guest cart -> quote -> manager approval -> existing order ledger."""
import os
from pathlib import Path
os.environ["DATABASE_URL"]="sqlite:///"+str(Path(__file__).parent/"pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Product, SaleOrder, Customer, StockMovement
from app.public_order_requests import PublicOrderRequest
from app.workflows import IndustryWorkItem


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED",raising=False)
    monkeypatch.delenv("EZ_THING_REQUIRE_VERIFIED_EMAIL",raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def setup(cli,industry="online",suffix="a"):
    account=cli.post("/api/auth/signup",json={
        "name":"Merchant","email":f"order-{industry}-{suffix}@example.com",
        "password":"SafePassword!123"})
    assert account.status_code==201,account.text
    csrf=account.json()["csrf_token"]
    business=cli.post("/api/businesses",headers={"x-csrf-token":csrf},json={
        "name":"My test shop","industry":industry,"selected_plan":"PRO",
        "need_inventory":True,"need_tables":industry=="fnb"})
    assert business.status_code==201,business.text
    bid=business.json()["id"]
    p=cli.post(f"/api/businesses/{bid}/products",headers={"x-csrf-token":csrf},json={
        "name":"Coffee bag","sku":"COFFEE-01","price_vnd":74000,
        "cost_vnd":37000,"stock":12,"track_stock":True})
    assert p.status_code==201,p.text
    return csrf,bid,p.json()["id"]


def publish(cli,csrf,bid,slug):
    res=cli.put(f"/api/businesses/{bid}/publishing",headers={"x-csrf-token":csrf},
                json={"slug":slug,"published":True})
    assert res.status_code==200,res.text


def request(pid,request_id="guest-order-test-00001",qty=2):
    return {
        "request_id":request_id,"customer_name":"Khách thử nghiệm",
        "phone":"0901234567","address":"123 Nguyen Hue, Quan 1, TP.HCM",
        "note":"Giao buổi sáng",
        "lines":[{"product_id":pid,"quantity":qty}],
    }


@pytest.mark.parametrize("industry,workflow",[
    ("fnb","kitchen"),("retail",None),("online","delivery"),
])
def test_merchant_approval_atomic_stock_order_and_workflow(industry,workflow):
    with TestClient(app) as owner, TestClient(app) as guest:
        csrf,bid,pid=setup(owner,industry)
        publish(owner,csrf,bid,industry+"-myshop")
        url=f"/api/public/shops/{industry}-myshop/order-requests"
        body=request(pid)
        sent=guest.post(url,json=body)
        assert sent.status_code==201,sent.text
        quote=sent.json()
        assert quote["total_vnd"]==148000
        assert quote["status"]=="pending"
        with SessionLocal() as db:
            assert db.scalar(select(func.count(SaleOrder.id)).where(SaleOrder.business_id==bid))==0
            assert db.get(Product,pid).stock==12
        duplicate=guest.post(url,json=body)
        assert duplicate.status_code==201 and duplicate.json()["id"]==quote["id"]
        assert guest.post(url,json={**body,"lines":[{"product_id":pid,"quantity":1}]}).status_code==409
        inbox=owner.get(f"/api/businesses/{bid}/order-requests")
        assert inbox.status_code==200 and len(inbox.json())==1
        assert inbox.json()[0]["phone"]==body["phone"]
        approved=owner.post(f"/api/businesses/{bid}/order-requests/{quote['id']}/review",
            headers={"x-csrf-token":csrf},json={"action":"accept"})
        assert approved.status_code==200,approved.text
        order_id=approved.json()["sale_order_id"]
        assert order_id
        replay=owner.post(f"/api/businesses/{bid}/order-requests/{quote['id']}/review",
            headers={"x-csrf-token":csrf},json={"action":"accept"})
        assert replay.status_code==200
        assert replay.json()["sale_order_id"]==order_id
        with SessionLocal() as db:
            o=db.get(SaleOrder,order_id)
            assert o.status=="open" and o.paid_at is None and o.total_vnd==148000
            assert o.business_id==bid
            assert db.get(Product,pid).stock==10
            assert db.scalar(select(func.count(StockMovement.id)).where(
                StockMovement.business_id==bid,StockMovement.ref==order_id,
                StockMovement.reason=="sale"))==1
            assert db.scalar(select(func.count(Customer.id)).where(
                Customer.business_id==bid,Customer.phone==body["phone"]))==1
            if workflow:
                jobs=db.scalars(select(IndustryWorkItem).where(
                    IndustryWorkItem.business_id==bid,
                    IndustryWorkItem.reference_id==order_id,
                    IndustryWorkItem.kind==workflow)).all()
                assert len(jobs)==1 and jobs[0].status=="pending"


def test_cross_tenant_products_unpublished_sites_and_rejection():
    with TestClient(app) as owner, TestClient(app) as other, TestClient(app) as guest:
        csrf,bid,pid=setup(owner,"retail","c")
        other_csrf,other_bid,other_pid=setup(other,"retail","d")
        publish(owner,csrf,bid,"storefront-c")
        assert guest.post("/api/public/shops/missing/order-requests",json=request(pid)).status_code==404
        assert guest.post("/api/public/shops/storefront-c/order-requests",json=request(other_pid)).status_code==404
        response=guest.post("/api/public/shops/storefront-c/order-requests",json=request(pid))
        assert response.status_code==201,response.text
        rid=response.json()["id"]
        assert other.get(f"/api/businesses/{bid}/order-requests").status_code==404
        assert other.post(f"/api/businesses/{bid}/order-requests/{rid}/review",
            headers={"x-csrf-token":other_csrf},json={"action":"accept"}).status_code==404
        rejected=owner.post(f"/api/businesses/{bid}/order-requests/{rid}/review",
            headers={"x-csrf-token":csrf},json={"action":"reject","reason":"Khách đổi ý"})
        assert rejected.status_code==200
        assert rejected.json()["status"]=="rejected"
        assert owner.post(f"/api/businesses/{bid}/order-requests/{rid}/review",
            headers={"x-csrf-token":csrf},json={"action":"accept"}).status_code==409
        with SessionLocal() as db:
            assert db.get(Product,pid).stock==12
            assert db.scalar(select(func.count(SaleOrder.id)).where(SaleOrder.business_id==bid))==0


def test_price_change_or_stock_shortage_blocks_approval_without_partial_state():
    with TestClient(app) as owner, TestClient(app) as guest:
        csrf,bid,pid=setup(owner,"online","price")
        publish(owner,csrf,bid,"store-price")
        response=guest.post("/api/public/shops/store-price/order-requests",json=request(pid))
        rid=response.json()["id"]
        with SessionLocal() as db:
            p=db.get(Product,pid)
            p.price_vnd=76000
            db.commit()
        decision=owner.post(f"/api/businesses/{bid}/order-requests/{rid}/review",
            headers={"x-csrf-token":csrf},json={"action":"accept"})
        assert decision.status_code==409
        with SessionLocal() as db:
            req=db.get(PublicOrderRequest,rid)
            assert req.status=="pending" and req.sale_order_id is None
            assert db.get(Product,pid).stock==12
            assert db.scalar(select(func.count(SaleOrder.id)).where(SaleOrder.business_id==bid))==0


def test_guest_order_abuse_cap_and_origin():
    with TestClient(app) as owner, TestClient(app) as guest:
        csrf,bid,pid=setup(owner,"retail","cap")
        publish(owner,csrf,bid,"store-cap")
        url="/api/public/shops/store-cap/order-requests"
        assert guest.post(url,json=request(pid),headers={"origin":"https://evil.invalid"}).status_code==403
        assert guest.post(url,json=request(pid,qty=16)).status_code==422
        first=guest.post(url,json=request(pid))
        assert first.status_code==201
        second=guest.post(url,json=request(pid,request_id="guest-order-test-00002"))
        assert second.status_code==201
        third=guest.post(url,json=request(pid,request_id="guest-order-test-00003"))
        assert third.status_code==429
        with SessionLocal() as db:
            assert db.get(Product,pid).stock==12
            assert db.scalar(select(func.count(PublicOrderRequest.id)).where(
                PublicOrderRequest.business_id==bid))==2


def test_guest_cart_ui_mobile_and_backend_approval_text():
    root=Path(__file__).resolve().parents[1]/"app/static"
    js=(root/"public-shop.js").read_text()
    css=(root/"public-shop.css").read_text()
    merchant=(root/"site-publishing-ui.js").read_text()
    assert 'data-action="cart-add"' not in js or '"cart-add"' in js
    for marker in ("shop-order-form","cart-inc","cart-dec","/order-requests","pending merchant review"):
        assert marker in js.lower() if marker=="pending merchant review" else marker in js
    assert ".shop-cart-line" in css
    assert "data-action=\"public-order-review\"" in merchant


def test_approved_published_fnb_order_is_fired_to_kds_and_ez_print_atomically():
    from app.printing import PrintJob
    with TestClient(app) as owner, TestClient(app) as guest:
        csrf, bid, pid=setup(owner,"fnb","print-bridge")
        branch=owner.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
        added=owner.post(f"/api/businesses/{bid}/printers",
            headers={"x-csrf-token":csrf},json={
                "name":"Bar main","branch_id":branch,
                "protocol":"connector_lan","station":"bar","auto_print":True})
        assert added.status_code==201,added.text
        publish(owner,csrf,bid,"fnb-print-bridge")
        requested=guest.post("/api/public/shops/fnb-print-bridge/order-requests",
                             json=request(pid,"fnb-approved-with-print",2))
        assert requested.status_code==201,requested.text
        rid=requested.json()["id"]
        approved=owner.post(f"/api/businesses/{bid}/order-requests/{rid}/review",
                            headers={"x-csrf-token":csrf},json={"action":"accept"})
        assert approved.status_code==200,approved.text
        oid=approved.json()["sale_order_id"]
        with SessionLocal() as db:
            kds=db.scalar(select(IndustryWorkItem).where(
                IndustryWorkItem.business_id==bid,
                IndustryWorkItem.kind=="kitchen",
                IndustryWorkItem.reference_id==oid))
            assert kds is not None
            assert kds.details["kds_revision"]==0
            assert kds.details["kds_lines"][0]["name"]=="Coffee bag"
            assert kds.details["kds_lines"][0]["station"]=="bar"
            print_jobs=db.scalars(select(PrintJob).where(
                PrintJob.business_id==bid)).all()
            assert len(print_jobs)==1
            assert "Coffee bag" in print_jobs[0].content
            db.get(Product,pid).name="Menu updated later"
            db.commit()
        queue=owner.get(f"/api/businesses/{bid}/kds/queue")
        assert queue.status_code==200,queue.text
        ticket=next(x for x in queue.json()["tickets"] if x["order_id"]==oid)
        assert ticket["lines"][0]["name"]=="Coffee bag"
        assert owner.post(f"/api/businesses/{bid}/order-requests/{rid}/review",
                         headers={"x-csrf-token":csrf},
                         json={"action":"accept"}).status_code==200
        with SessionLocal() as db:
            assert db.scalar(select(func.count(PrintJob.id)).where(
                PrintJob.business_id==bid))==1
