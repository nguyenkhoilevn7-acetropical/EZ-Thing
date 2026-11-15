"""V7 POS: stateful edit / table-move integration and stock/finance safety."""
import os
import sys
from pathlib import Path
os.environ["DATABASE_URL"]="sqlite:///"+str(Path(__file__).parent/"pilot-tests.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, engine
from app.main import app
from app.models import Business, Membership, Product, SaleOrder, StockMovement
from app.workflows import IndustryWorkItem


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as cli:
        yield cli


def post(c, suffix, body, csrf=None):
    return c.post("/api"+suffix,json=body,headers={"x-csrf-token":csrf} if csrf else {})


def put(c, suffix, body, csrf=None):
    return c.put("/api"+suffix,json=body,headers={"x-csrf-token":csrf} if csrf else {})


def owner(c, email, industry="fnb"):
    x=c.post("/api/auth/signup",json={"name":"POS Owner","email":email,
                                     "password":"SafePassword!123"})
    assert x.status_code==201,x.text
    csrf=x.json()["csrf_token"]
    x=post(c,"/businesses",{"name":"POS Test","industry":industry,
             "selected_plan":"PRO","need_tables":industry=="fnb",
             "need_inventory":True,"need_insights":True,"need_branches":True},csrf)
    assert x.status_code==201,x.text
    return csrf,x.json()["id"]


def item(c,bid,csrf,name,sku,price=35000,cost=0,stock=0,tracked=False):
    x=post(c,f"/businesses/{bid}/products",{
        "name":name,"sku":sku,"price_vnd":price,"cost_vnd":cost,
        "stock":stock,"track_stock":tracked},csrf)
    assert x.status_code==201,x.text
    return x.json()["id"]


def check(bid,oid):return f"/businesses/{bid}/pos/orders/{oid}"


def get_stock(c,bid,pid):
    return next(x["stock"] for x in c.get(f"/api/businesses/{bid}/products").json() if x["id"]==pid)


def modifier_set(ingredient):
    return [{"id":"sizes","name":"Size","min_select":1,"max_select":1,
             "options":[{"id":"size-m","name":"M","price_vnd":0},
                        {"id":"size-l","name":"L","price_vnd":7000}]},
            {"id":"toppings","name":"Topping","min_select":0,"max_select":1,
             "options":[{"id":"pearls","name":"Trân châu","price_vnd":5000,
                         "inventory_product_id":ingredient,"inventory_quantity":2}]}]


def test_edit_options_amount_tips_stock_and_cancel(client):
    csrf,bid=owner(client,"pos-v7-edit@example.com")
    pearl=item(client,bid,csrf,"Pearl ingredients","PEARL",price=1000,cost=800,stock=20,tracked=True)
    tea=item(client,bid,csrf,"Milk Tea","TEA",price=35000)
    options=put(client,f"/businesses/{bid}/products/{tea}/modifiers",{
        "expected_revision":0,"groups":modifier_set(pearl)},csrf)
    assert options.status_code==200,options.text
    source=post(client,f"/businesses/{bid}/orders",{
        "idempotency_key":"pos-edit-initial-0001",
        "lines":[{"product_id":tea,"quantity":2,
                  "selected_options":["size-m","pearls"]}]},csrf)
    assert source.status_code==201,source.text
    oid=source.json()["id"]
    assert get_stock(client,bid,pearl)==16
    initial=client.get("/api"+check(bid,oid)).json()
    assert initial["revision"]==0 and initial["total_vnd"]==80000
    assert initial["items"][0]["id"]
    change={"request_id":"pos-v7-edit-request-01","expected_revision":0,
            "lines":[{"product_id":tea,"quantity":1,
                      "selected_options":["size-l","pearls"]}],
            "discount_vnd":5000,"tip_vnd":2000,"note":"Ít đá"}
    saved=put(client,check(bid,oid),change,csrf)
    assert saved.status_code==200,saved.text
    result=saved.json()
    assert result["total_vnd"]==44000
    assert result["subtotal_vnd"]==47000
    assert result["discount_vnd"]==5000 and result["tip_vnd"]==2000
    assert result["revision"]==1
    assert result["items"][0]["modifiers"][0]["name"]=="L"
    assert get_stock(client,bid,pearl)==18
    assert put(client,check(bid,oid),change,csrf).json()==result
    assert get_stock(client,bid,pearl)==18
    assert put(client,check(bid,oid),{**change,"note":"New request"},csrf).status_code==409
    assert put(client,check(bid,oid),{**change,"request_id":"pos-v7-edit-request-02"},csrf).status_code==409
    assert client.get(f"/api/businesses/{bid}/orders").json()[0]["total_vnd"]==44000
    cancelled=post(client,f"/businesses/{bid}/orders/{oid}/cancel",{
        "confirmed":True,"reason":"Changed mind"},csrf)
    assert cancelled.status_code==200,cancelled.text
    assert get_stock(client,bid,pearl)==20
    assert put(client,check(bid,oid),{
        **change,"request_id":"pos-v7-edit-request-03","expected_revision":1},csrf).status_code==409


def test_edited_paid_order_finance_counts_net_consumption(client):
    csrf,bid=owner(client,"pos-v7-cost@example.com")
    tracked=item(client,bid,csrf,"Retail drink","DRINK",price=50000,cost=15000,stock=10,tracked=True)
    source=post(client,f"/businesses/{bid}/orders",{
        "idempotency_key":"pos-v7-cost-source-01",
        "lines":[{"product_id":tracked,"quantity":4}]},csrf).json()
    oid=source["id"]
    assert get_stock(client,bid,tracked)==6
    r=put(client,check(bid,oid),{
        "request_id":"pos-v7-cost-change-1","expected_revision":0,
        "lines":[{"product_id":tracked,"quantity":2}],
        "discount_vnd":10000,"tip_vnd":0,"note":""},csrf)
    assert r.status_code==200,r.text
    assert r.json()["total_vnd"]==90000
    assert get_stock(client,bid,tracked)==8
    assert post(client,f"/businesses/{bid}/orders/{oid}/paid",{
        "confirmed":True},csrf).status_code==200
    finance=client.get(f"/api/businesses/{bid}/operations/finance")
    assert finance.status_code==200,finance.text
    assert finance.json()["revenue_vnd"]==90000
    assert finance.json()["estimated_cogs_vnd"]==30000
    assert put(client,check(bid,oid),{
        "request_id":"pos-v7-after-paid-01","expected_revision":1,
        "lines":[{"product_id":tracked,"quantity":1}]},csrf).status_code==409
    assert get_stock(client,bid,tracked)==8


def test_move_table_same_branch_revision_idempotency_and_tenant_scope(client):
    csrf,bid=owner(client,"pos-v7-move@example.com")
    tea=item(client,bid,csrf,"Trà Sữa","TEA")
    branches=client.get(f"/api/businesses/{bid}/branches").json()
    a=branches[0]["id"]
    b=post(client,f"/businesses/{bid}/branches",{"name":"Outlet B"},csrf).json()["id"]
    t1=post(client,f"/businesses/{bid}/tables",{
        "branch_id":a,"label":"Table A","seats":4},csrf).json()["id"]
    t2=post(client,f"/businesses/{bid}/tables",{
        "branch_id":a,"label":"Table B","seats":4},csrf).json()["id"]
    foreign=post(client,f"/businesses/{bid}/tables",{
        "branch_id":b,"label":"Table X","seats":4},csrf).json()["id"]
    order=post(client,f"/businesses/{bid}/orders",{
        "idempotency_key":"pos-v7-table-0001",
        "table_id":t1,"branch_id":a,"lines":[{"product_id":tea,"quantity":1}]},csrf).json()
    oid=order["id"]
    body={"request_id":"pos-v7-move-0001","expected_revision":0,"table_id":t2}
    moved=post(client,check(bid,oid)+"/move-table",body,csrf)
    assert moved.status_code==200,moved.text
    assert moved.json()["table_id"]==t2 and moved.json()["revision"]==1
    assert post(client,check(bid,oid)+"/move-table",body,csrf).json()==moved.json()
    assert post(client,check(bid,oid)+"/move-table",{
        **body,"request_id":"pos-v7-move-0002",
        "table_id":foreign,"expected_revision":1},csrf).status_code==404
    assert post(client,check(bid,oid)+"/move-table",{
        **body,"request_id":"pos-v7-move-0003"},csrf).status_code==409
    with TestClient(app) as outsider:
        owner(outsider,"pos-v7-outsider@example.com")
        assert outsider.get("/api"+check(bid,oid)).status_code==404
        assert put(outsider,check(bid,oid),{
            "request_id":"pos-v7-cross-tenant-1","expected_revision":1,
            "lines":[{"product_id":tea,"quantity":1}]},
            outsider.get("/api/auth/me").json()["csrf_token"]).status_code==404


def test_kitchen_ticket_rejects_edit_and_move(client):
    csrf,bid=owner(client,"pos-v7-kitchen@example.com")
    p=item(client,bid,csrf,"Coffee","COFFEE")
    branch=client.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
    table=post(client,f"/businesses/{bid}/tables",{
        "branch_id":branch,"label":"A1"},csrf).json()["id"]
    source=post(client,f"/businesses/{bid}/orders",{
        "idempotency_key":"pos-v7-kitchen-order-1",
        "branch_id":branch,"lines":[{"product_id":p,"quantity":1}]},csrf).json()
    oid=source["id"]
    from app.database import SessionLocal
    with SessionLocal() as db:
        from uuid import uuid4
        db.add(IndustryWorkItem(
            id=str(uuid4()),business_id=bid,kind="kitchen",
            reference_id=oid,status="pending",title="Kitchen ticket",
            details={"source":"test"}))
        db.commit()
    replacement={"request_id":"pos-v7-kitchen-edit-01","expected_revision":0,
                 "lines":[{"product_id":p,"quantity":2}]}
    assert put(client,check(bid,oid),replacement,csrf).status_code==409
    assert post(client,check(bid,oid)+"/move-table",{
        "request_id":"pos-v7-kitchen-move-1",
        "expected_revision":0,"table_id":table},csrf).status_code==409


def test_pos_editor_is_accessible_and_uses_csrf(client):
    csrf,bid=owner(client,"pos-v7-ui@example.com")
    p=item(client,bid,csrf,"Coffee","COFFEE")
    order=post(client,f"/businesses/{bid}/orders",{
        "idempotency_key":"pos-v7-csrf-0001",
        "lines":[{"product_id":p,"quantity":1}]},csrf).json()
    oid=order["id"]
    body={"request_id":"pos-v7-csrf-check-01","expected_revision":0,
          "lines":[{"product_id":p,"quantity":2}]}
    assert client.put("/api"+check(bid,oid),json=body).status_code==403
    assert client.get("/assets/pos-v7.js").status_code==200
    assert client.get("/assets/pos-v7.css").status_code==200
    index=client.get("/app").text
    assert "pos-v7.js?v=20261115-v7-01" in index
    assert "pos-v7.css?v=20261115-v7-01" in index
