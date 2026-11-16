"""Auto-dispatch KDS regression: POS/website, category/item priority, print isolation."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

os.environ["DATABASE_URL"]="sqlite:///"+str(Path(__file__).parent/"pilot-tests.db")

from app.database import Base, engine, SessionLocal
from app.main import app
from app.workflows import IndustryWorkItem
from app.printing import PrintJob


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED",raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def request(c,method,path,body=None,csrf=None):
    headers={"x-csrf-token":csrf} if csrf else {}
    return c.request(method,"/api"+path,headers=headers,json=body)


def owner(c,key):
    r=request(c,"POST","/auth/signup",{
        "name":"Restaurant Owner","email":f"auto-kds-{key}@example.com",
        "password":"SafePassword!123"})
    assert r.status_code==201,r.text
    csrf=r.json()["csrf_token"]
    b=request(c,"POST","/businesses",{"name":"Split Kitchen "+key,"industry":"fnb",
        "selected_plan":"PRO","need_tables":True,"need_inventory":True},csrf)
    assert b.status_code==201,b.text
    return csrf,b.json()["id"]


def product(c,bid,csrf,name,sku,category):
    r=request(c,"POST",f"/businesses/{bid}/products",{
        "name":name,"sku":sku,"category":category,"price_vnd":39000,
        "track_stock":False},csrf)
    assert r.status_code==201,r.text
    return r.json()["id"]


def new_order(c,bid,csrf,ids,key=None):
    body={"idempotency_key":key or "auto-"+uuid.uuid4().hex,
          "lines":[{"product_id":pid,"quantity":1} for pid in ids]}
    r=request(c,"POST",f"/businesses/{bid}/orders",body,csrf)
    assert r.status_code==201,r.text
    return body,r.json()


def route(c,bid,csrf,kind,body):
    return request(c,"PUT",f"/businesses/{bid}/kds/{kind}",body,csrf)


def job_count(bid):
    with SessionLocal() as db:
        return db.scalar(select(func.count(IndustryWorkItem.id)).where(
            IndustryWorkItem.business_id==bid,
            IndustryWorkItem.kind=="kitchen"))


def print_count(bid):
    with SessionLocal() as db:
        return db.scalar(select(func.count(PrintJob.id)).where(PrintJob.business_id==bid))


def test_pos_auto_sends_food_to_kitchen_drinks_to_bar_and_print_only_once():
    with TestClient(app) as c:
        csrf,bid=owner(c,"mixed")
        drink=product(c,bid,csrf,"Nước ép cam","CAM","Đồ uống")
        food=product(c,bid,csrf,"Cơm chiên","RICE","Đồ ăn")
        branch=c.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
        for station in ("bar","hot"):
            r=request(c,"POST",f"/businesses/{bid}/printers",{
                "name":station,"branch_id":branch,"protocol":"connector_lan",
                "station":station,"auto_print":True},csrf)
            assert r.status_code==201,r.text

        # Configuration is explicit; category mapping takes precedence over guess.
        assert route(c,bid,csrf,"category-routes",{
            "category":"Đồ uống","station":"bar"}).status_code==200
        assert route(c,bid,csrf,"category-routes",{
            "category":"Đồ ăn","station":"hot"}).status_code==200
        body,created=new_order(c,bid,csrf,[drink,food],"auto-kds-mixed-order-01")
        oid=created["id"]
        assert created["kds_dispatch"]["status"]=="sent"
        queue=c.get(f"/api/businesses/{bid}/kds/queue").json()
        ticket=next(x for x in queue["tickets"] if x["order_id"]==oid)
        assert {x["product_id"]:x["station"] for x in ticket["lines"]}=={
            drink:"bar",food:"hot"}
        assert print_count(bid)==2
        with SessionLocal() as db:
            jobs=db.scalars(select(PrintJob).where(PrintJob.business_id==bid)).all()
            assert all("CAM" not in job.content for job in jobs)  # SKU is not printed
            bar=next(j for j in jobs if "KITCHEN / Pha" in j.content)
            hot=next(j for j in jobs if "KITCHEN / Bếp nóng" in j.content)
            assert "Nước ép cam" in bar.content and "Cơm chiên" not in bar.content
            assert "Cơm chiên" in hot.content and "Nước ép cam" not in hot.content
        replay=request(c,"POST",f"/businesses/{bid}/orders",body,csrf)
        assert replay.status_code==201
        assert replay.json()["id"]==oid
        manual=request(c,"POST",f"/businesses/{bid}/kds/fire",{"order_id":oid},csrf)
        assert manual.status_code==201,manual.text
        assert job_count(bid)==1 and print_count(bid)==2
        paid=request(c,"POST",f"/businesses/{bid}/orders/{oid}/paid",{"confirmed":True},csrf)
        assert paid.status_code==200,paid.text
        assert job_count(bid)==1 and print_count(bid)==2


def test_category_override_product_priority_and_no_prep():
    with TestClient(app) as c:
        csrf,bid=owner(c,"priority")
        tea=product(c,bid,csrf,"Trà đào","TEA","Đồ uống")
        juice=product(c,bid,csrf,"Nước ép","JUICE","Đồ uống")
        bottle=product(c,bid,csrf,"Nước suối chai","BOTTLE","Đồ uống")
        assert route(c,bid,csrf,"category-routes",{
            "category":"Đồ uống","station":"bar"}).status_code==200
        assert route(c,bid,csrf,"routes",{
            "product_id":juice,"station":"cold"}).status_code==200
        assert route(c,bid,csrf,"routes",{
            "product_id":bottle,"station":"skip"}).status_code==200
        _,one=new_order(c,bid,csrf,[tea,juice,bottle])
        queue=c.get(f"/api/businesses/{bid}/kds/queue").json()
        ticket=next(x for x in queue["tickets"] if x["order_id"]==one["id"])
        assert {x["product_id"]:x["station"] for x in ticket["lines"]}=={
            tea:"bar",juice:"cold"}
        assert len(ticket["lines"])==2
        assert request(c,"DELETE",f"/businesses/{bid}/kds/routes/{juice}",csrf=csrf).status_code==200
        assert request(c,"DELETE",f"/businesses/{bid}/kds/category-routes",
                       {"category":"Đồ uống"},csrf).status_code==200
        _,two=new_order(c,bid,csrf,[juice])
        new=c.get(f"/api/businesses/{bid}/kds/queue").json()["tickets"]
        later=next(x for x in new if x["order_id"]==two["id"])
        assert later["lines"][0]["station"]=="bar"  # inferred beverage fallback
        former=next(x for x in new if x["order_id"]==one["id"])
        assert former["lines"]==ticket["lines"],"Existing tickets must not be rerouted"
        _,skip_order=new_order(c,bid,csrf,[bottle])
        assert skip_order["kds_dispatch"]["status"]=="no_prep"
        assert job_count(bid)==2
        assert request(c,"POST",f"/businesses/{bid}/kds/fire",
                       {"order_id":skip_order["id"]},csrf).status_code==409


def test_disabled_auto_requires_explicit_manual_send_and_preserves_editing():
    with TestClient(app) as c:
        csrf,bid=owner(c,"manual")
        tea=product(c,bid,csrf,"Trà sữa","MILK","Đồ uống")
        assert route(c,bid,csrf,"settings",{"auto_dispatch":False}).status_code==200
        _,order=new_order(c,bid,csrf,[tea])
        assert order["kds_dispatch"]["status"]=="manual"
        assert job_count(bid)==0
        assert request(c,"POST",f"/businesses/{bid}/kds/fire",
                       {"order_id":order["id"]},csrf).status_code==201
        assert job_count(bid)==1
        assert request(c,"POST",f"/businesses/{bid}/kds/fire",
                       {"order_id":order["id"]},csrf).status_code==201
        assert job_count(bid)==1
        assert route(c,bid,csrf,"settings",{"auto_dispatch":True}).status_code==200
        _,next_order=new_order(c,bid,csrf,[tea])
        assert next_order["kds_dispatch"]["status"]=="sent"
        assert job_count(bid)==2


def test_kds_cross_tenant_config_guard_and_staff_forbidden():
    with TestClient(app) as one, TestClient(app) as two:
        csrf,bid=owner(one,"tenant-a")
        csrf2,bid2=owner(two,"tenant-b")
        tea=product(one,bid,csrf,"Tea","TEA","Đồ uống")
        product(two,bid2,csrf2,"Rice","RICE","Đồ ăn")
        assert two.get(f"/api/businesses/{bid}/kds/routes").status_code==404
        assert route(two,bid,csrf2,"category-routes",{
            "category":"Đồ uống","station":"hot"}).status_code==404
        assert route(two,bid,csrf2,"settings",{"auto_dispatch":False}).status_code==404
        assert route(one,bid,csrf,"category-routes",{
            "category":"Đồ uống","station":"bar"}).status_code==200
        result=one.get(f"/api/businesses/{bid}/kds/routes").json()
        assert result["settings"]["auto_dispatch"] is True
        assert result["category_routes"]["đồ uống"]=="bar"
        assert "skip" in result["route_stations"]
        assert route(one,bid,csrf,"routes",{"product_id":tea,"station":"skip"}).status_code==200


def test_fnb_website_approved_respects_no_prep_and_auto_settings():
    with TestClient(app) as owner_cli,TestClient(app) as guest:
        csrf,bid=owner(owner_cli,"website")
        bottle=product(owner_cli,bid,csrf,"Bottled water","BOTTLE","Nước đóng chai")
        assert route(owner_cli,bid,csrf,"category-routes",{
            "category":"Nước đóng chai","station":"skip"}).status_code==200
        published=request(owner_cli,"PUT",f"/businesses/{bid}/publishing",{
            "slug":"kds-skip-website","published":True},csrf)
        assert published.status_code==200,published.text
        sent=guest.post("/api/public/shops/kds-skip-website/order-requests",json={
            "request_id":"website-no-prep-test-01","customer_name":"Guest",
            "phone":"0901234567","address":"123 Test Street",
            "lines":[{"product_id":bottle,"quantity":2}]})
        assert sent.status_code==201,sent.text
        approved=request(owner_cli,"POST",f"/businesses/{bid}/order-requests/{sent.json()['id']}/review",
                         {"action":"accept"},csrf)
        assert approved.status_code==200,approved.text
        assert job_count(bid)==0
        assert owner_cli.get(f"/api/businesses/{bid}/kds/queue").json()["tickets"]==[]
