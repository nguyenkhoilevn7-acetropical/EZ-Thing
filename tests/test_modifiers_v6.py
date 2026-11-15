"""V6 add-on regression: tenant isolation, server pricing, product choices and stock."""
import os
import sys
from pathlib import Path
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def post(c, path, body, csrf):
    return c.post("/api" + path, json=body, headers={"x-csrf-token": csrf})


def put(c, path, body, csrf):
    return c.put("/api" + path, json=body, headers={"x-csrf-token": csrf})


def create_business(c, email):
    r = c.post("/api/auth/signup", json={
        "name":"Owner Cafe","email":email,"password":"SafePassword!123"})
    assert r.status_code == 201, r.text
    csrf = r.json()["csrf_token"]
    r = post(c, "/businesses", {
        "name":"Cafe V6","industry":"fnb","selected_plan":"PRO",
        "need_tables":True,"need_inventory":True,"need_insights":True,
        "need_branches":True}, csrf)
    assert r.status_code == 201, r.text
    return csrf, r.json()["id"]


def add_product(c, bid, csrf, name, sku, price=35000, stock=0, tracked=False):
    r = post(c, f"/businesses/{bid}/products", {
        "name":name,"sku":sku,"price_vnd":price,
        "stock":stock,"track_stock":tracked},csrf)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def path(bid, product):
    return f"/businesses/{bid}/products/{product}/modifiers"


def groups(ingredient=None):
    return [
        {"id":"size-group","name":"Size","min_select":1,"max_select":1,
         "options":[{"id":"size-m","name":"M","price_vnd":0},
                    {"id":"size-l","name":"L","price_vnd":7000}]},
        {"id":"topping-group","name":"Topping","min_select":0,"max_select":2,
         "options":[{"id":"pearl","name":"Trân châu","price_vnd":5000,
                     "inventory_product_id":ingredient,"inventory_quantity":2},
                    {"id":"jelly","name":"Thạch","price_vnd":3000}]},
    ]


def test_server_pricing_stock_and_receipt_snapshot(client):
    csrf,bid=create_business(client,"modifier-owner@example.com")
    ingredient=add_product(client,bid,csrf,"Trân châu nguyên liệu","PEARLS",1000,20,True)
    milk_tea=add_product(client,bid,csrf,"Trà sữa","TEA",35000)
    saved=put(client,path(bid,milk_tea),{"expected_revision":0,"groups":groups(ingredient)},csrf)
    assert saved.status_code==200,saved.text
    assert saved.json()["revision"]==1
    assert put(client,path(bid,milk_tea),{"expected_revision":0,"groups":[]},csrf).status_code==409
    assert put(client,path(bid,milk_tea),{"expected_revision":1,
        "groups":[{**groups()[0],"options":[groups()[0]["options"][0],
                    groups()[0]["options"][0]]}]},csrf).status_code==422

    # A required size cannot be skipped and a foreign option must be rejected.
    base={"idempotency_key":"mod-order-00001",
          "lines":[{"product_id":milk_tea,"quantity":1,
                    "selected_options":["pearl"]}]}
    assert post(client,f"/businesses/{bid}/orders",base,csrf).status_code==422
    assert post(client,f"/businesses/{bid}/orders",{
        **base,"lines":[{"product_id":milk_tea,"quantity":1,
                        "selected_options":["size-m","unlisted"]}]},csrf).status_code==422

    valid={"idempotency_key":"mod-order-00002",
           "lines":[
               {"product_id":milk_tea,"quantity":2,
                "selected_options":["size-m","pearl"]},
               {"product_id":milk_tea,"quantity":1,
                "selected_options":["size-l","jelly"]},
           ]}
    order=post(client,f"/businesses/{bid}/orders",valid,csrf)
    assert order.status_code==201,order.text
    result=order.json()
    assert result["total_vnd"]==2*40000+45000
    assert len(result["items"])==2
    assert result["items"][0]["modifiers"][1]["name"]=="Trân châu"
    assert result["items"][1]["modifiers"][1]["name"]=="Thạch"
    products=client.get(f"/api/businesses/{bid}/products").json()
    assert next(x for x in products if x["id"]==ingredient)["stock"]==16
    second=post(client,f"/businesses/{bid}/orders",valid,csrf)
    assert second.status_code==200,second.text
    assert second.json()["id"]==result["id"]
    assert len(client.get(f"/api/businesses/{bid}/order-dashboard").json()["orders"][0]["items"])==2

    # Price edits affect new orders only, not the immutable historical receipt.
    changed=groups(ingredient);changed[1]["options"][0]["price_vnd"]=8000
    assert put(client,path(bid,milk_tea),{"expected_revision":1,"groups":changed},csrf).status_code==200
    old=client.get(f"/api/businesses/{bid}/orders").json()[0]
    assert old["total_vnd"]==125000
    assert old["items"][0]["modifiers"][1]["price_vnd"]==5000
    cancel=post(client,f"/businesses/{bid}/orders/{result['id']}/cancel",
                {"confirmed":True,"reason":"Duplicate test"},csrf)
    assert cancel.status_code==200,cancel.text
    products=client.get(f"/api/businesses/{bid}/products").json()
    assert next(x for x in products if x["id"]==ingredient)["stock"]==20


def test_tenant_separation_and_invalid_stock_reference(client):
    csrf_a,a=create_business(client,"modifier-a@example.com")
    ingredient=add_product(client,a,csrf_a,"Topping","TOP-A",1000,10,True)
    milk=add_product(client,a,csrf_a,"Tea","TEA-A")
    assert put(client,path(a,milk),{"expected_revision":0,"groups":groups(ingredient)},csrf_a).status_code==200
    with TestClient(app) as another:
        csrf_b,b=create_business(another,"modifier-b@example.com")
        other=add_product(another,b,csrf_b,"Milk tea","TEA-B")
        assert another.get("/api"+path(a,milk)).status_code==404
        assert put(another,path(b,other),{"expected_revision":0,
            "groups":groups(ingredient)},csrf_b).status_code==422
        assert post(another,f"/businesses/{b}/orders",{
            "idempotency_key":"cross-tenant-0001",
            "lines":[{"product_id":other,"quantity":1,
                      "selected_options":["pearl"]}]},csrf_b).status_code==422


def test_public_site_modifiers_guest_requests_and_review_reprice(client):
    csrf,bid=create_business(client,"modifier-public@example.com")
    ingredient=add_product(client,bid,csrf,"Pearl stock","STOCK-P",1000,20,True)
    tea=add_product(client,bid,csrf,"Milk Tea","MILK-TEA")
    assert put(client,path(bid,tea),{"expected_revision":0,
        "groups":groups(ingredient)},csrf).status_code==200
    publishing=put(client,f"/businesses/{bid}/publishing",{
        "slug":"milk-tea-addon-test","published":True},csrf)
    assert publishing.status_code==200,publishing.text
    catalog=client.get("/api/public/shops/milk-tea-addon-test")
    assert catalog.status_code==200,catalog.text
    p=next(x for x in catalog.json()["products"] if x["id"]==tea)
    assert len(p["modifier_groups"])==2
    assert "inventory_product_id" not in str(p["modifier_groups"])

    payload={"request_id":"milk-tea-request-12345",
             "customer_name":"Guest Tester","phone":"0912345678",
             "lines":[{"product_id":tea,"quantity":2,
                       "selected_options":["size-l","pearl"]}]}
    request=client.post("/api/public/shops/milk-tea-addon-test/order-requests",json=payload)
    assert request.status_code==201,request.text
    assert request.json()["total_vnd"]==94000
    assert client.post("/api/public/shops/milk-tea-addon-test/order-requests",
                       json=payload).json()["id"]==request.json()["id"]
    assert next(x for x in client.get(f"/api/businesses/{bid}/products").json()
                if x["id"]==ingredient)["stock"]==20
    review=post(client,f"/businesses/{bid}/order-requests/{request.json()['id']}/review",
                {"action":"accept"},csrf)
    assert review.status_code==200,review.text
    accepted=client.get(f"/api/businesses/{bid}/orders").json()[0]
    assert accepted["total_vnd"]==94000
    assert accepted["items"][0]["modifiers"][1]["name"]=="Trân châu"
    assert next(x for x in client.get(f"/api/businesses/{bid}/products").json()
                if x["id"]==ingredient)["stock"]==16


def test_modifier_group_limits_and_strict_options(client):
    csrf,bid=create_business(client,"modifier-bounds@example.com")
    tea=add_product(client,bid,csrf,"Trà Sữa","TEA-BND")
    assert put(client,path(bid,tea),{"expected_revision":0,"groups":[{
        "id":"invalid","name":"Empty","min_select":2,"max_select":1,
        "options":[{"id":"only-one","name":"One"}]}]},csrf).status_code==422
    assert put(client,path(bid,tea),{"expected_revision":0,"groups":[
        {**groups()[0],"options":groups()[0]["options"][:1],
         "max_select":1}
    ]},csrf).status_code==200
    assert post(client,f"/businesses/{bid}/orders",{
        "idempotency_key":"duplicate-opt-001",
        "lines":[{"product_id":tea,"quantity":1,
                  "selected_options":["size-m","size-m"]}]},csrf).status_code==422
