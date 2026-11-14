"""Real storefront never leaks unpublished tenants, cost data or demo records."""
import os
from pathlib import Path
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Business


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    monkeypatch.delenv("EZ_THING_DEMO_MODE", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def owner(cli,email):
    res=cli.post("/api/auth/signup",json={"name":"Merchant owner", "email":email,
        "password":"SafePassword!123"})
    assert res.status_code==201,res.text
    return res.json()["csrf_token"]


def create(cli,csrf,industry="online"):
    result=cli.post("/api/businesses",headers={"x-csrf-token":csrf},
        json={"name":"Cửa Hàng Của Tôi", "industry":industry,
              "selected_plan":"PRO","need_inventory":True})
    assert result.status_code==201,result.text
    return result.json()["id"]


def publish(cli,csrf,bid,slug,enabled=True):
    return cli.put(f"/api/businesses/{bid}/publishing",
        headers={"x-csrf-token":csrf},
        json={"slug":slug,"published":enabled})


def test_private_by_default_then_owner_publishes_real_catalog():
    with TestClient(app) as merchant, TestClient(app) as stranger:
        csrf=owner(merchant,"published-owner@example.com")
        bid=create(merchant,csrf)
        product=merchant.post(f"/api/businesses/{bid}/products",
            headers={"x-csrf-token":csrf},
            json={"name":"Sản phẩm riêng","sku":"PROD-1","category":"Đồ dùng",
                  "price_vnd":249000,"cost_vnd":150000,"stock":10})
        assert product.status_code==201,product.text
        route="/api/public/shops/shop-test"
        assert stranger.get(route).status_code==404
        assert stranger.get("/api/businesses/"+bid+"/products").status_code==401
        page=stranger.get("/shop/shop-test")
        assert page.status_code==200
        assert "/assets/public-shop.js" in page.text
        assert "/assets/app.js" not in page.text

        result=publish(merchant,csrf,bid,"shop-test")
        assert result.status_code==200,result.text
        assert result.json()["published"] is True
        assert result.json()["public_url"]=="/shop/shop-test"
        data=stranger.get(route)
        assert data.status_code==200,data.text
        catalog=data.json()
        assert catalog["online_payment"] is False
        assert catalog["contact_only"] is True
        assert catalog["products"][0]["price_vnd"]==249000
        assert "cost_vnd" not in str(catalog)
        assert "stock" not in str(catalog)
        assert "password" not in str(catalog)
        assert "PRIVATE" not in str(catalog)

        payload={"request_id":"public-lead-000001","name":"Khách hàng","phone":"0901234567",
                 "message":"Xin báo giá sản phẩm","product_id":product.json()["id"]}
        result=stranger.post(route+"/inquiries",json=payload)
        assert result.status_code==201,result.text
        repeated=stranger.post(route+"/inquiries",json=payload)
        assert repeated.status_code==201
        assert repeated.json()["id"]==result.json()["id"]
        assert stranger.post(route+"/inquiries",json={
            **payload,"message":"Nội dung thay đổi"}).status_code==409
        leads=merchant.get(f"/api/businesses/{bid}/public-leads")
        assert len(leads.json())==1
        assert leads.json()[0]["name"]=="Khách hàng"
        assert leads.json()[0]["status"]=="new"
        first=merchant.post(f"/api/businesses/{bid}/public-leads/{result.json()['id']}/status",
            headers={"x-csrf-token":csrf},json={"status":"contacted"})
        assert first.status_code==200,first.text
        second=merchant.post(f"/api/businesses/{bid}/public-leads/{result.json()['id']}/status",
            headers={"x-csrf-token":csrf},json={"status":"closed"})
        assert second.status_code==200,second.text
        assert stranger.post(route+"/inquiries",json={
            **payload, "request_id":"public-lead-invalid","product_id":"bad-product",
        }).status_code==404

        result=publish(merchant,csrf,bid,"shop-test",False)
        assert result.status_code==200
        assert stranger.get(route).status_code==404


def test_slug_unique_and_cross_tenant_guards():
    with TestClient(app) as a, TestClient(app) as b:
        token_a=owner(a,"a-publisher@example.com")
        token_b=owner(b,"b-publisher@example.com")
        a_id=create(a,token_a,"fnb")
        b_id=create(b,token_b,"retail")
        assert publish(a,token_a,a_id,"the-cafe").status_code==200
        assert publish(b,token_b,b_id,"the-cafe").status_code==409
        assert publish(b,token_b,b_id,"admin").status_code==422
        assert publish(b,token_b,a_id,"hijack").status_code==404
        assert a.get(f"/api/businesses/{b_id}/publishing").status_code==404


def test_expired_tenant_is_not_public(monkeypatch):
    with TestClient(app) as client:
        token=owner(client,"expire-publisher@example.com")
        bid=create(client,token)
        assert publish(client,token,bid,"expire-public").status_code==200
        assert client.get("/api/public/shops/expire-public").status_code==200
        with SessionLocal() as db:
            business=db.get(Business,bid)
            business.subscription_status="demo"
            db.commit()
        assert client.get("/api/public/shops/expire-public").status_code==404


def test_frontend_responsive_dark_and_separate_assets():
    static=Path(__file__).resolve().parents[1] / "app" / "static"
    html=(static/"public-shop.html").read_text()
    css=(static/"public-shop.css").read_text()
    js=(static/"public-shop.js").read_text()
    assert "public-shop.js" in html and "app.js" not in html
    assert "@media(prefers-color-scheme:dark)" in css
    assert "@media(max-width:670px)" in css
    assert "state.data=await fetchJSON" in js
    assert "contact_only" in (Path(__file__).resolve().parents[1]/"app/published_storefront.py").read_text()
