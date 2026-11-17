"""Full-screen role preview and server-authenticated employee task segregation."""
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Membership


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def account(c, tag):
    r=c.post("/api/auth/signup",json={"name":"Worker "+tag,
        "email":f"employee-{tag}@example.com","password":"SafePassword!123"})
    assert r.status_code==201,r.text
    return r.json()["csrf_token"], r.json()["id"]


def shop(c, tag):
    csrf,uid=account(c,tag)
    r=c.post("/api/businesses",headers={"x-csrf-token":csrf},json={
        "name":"Controlled restaurant","industry":"fnb",
        "selected_plan":"PRO","need_tables":True,"need_inventory":True})
    assert r.status_code==201,r.text
    return csrf,uid,r.json()["id"]


def item(c,csrf,bid,name,sku,category):
    r=c.post(f"/api/businesses/{bid}/products",headers={"x-csrf-token":csrf},
       json={"name":name,"sku":sku,"category":category,"price_vnd":39000,
             "track_stock":False})
    assert r.status_code==201,r.text
    return r.json()["id"]


def assign(owner,csrf,bid,uid,mode,branch_id=None,station="all"):
    r=owner.put(f"/api/businesses/{bid}/team/members/{uid}/duty",
       headers={"x-csrf-token":csrf},
       json={"mode":mode,"branch_id":branch_id,"station":station})
    assert r.status_code==200,r.text
    return r.json()


def test_staff_order_is_default_and_rejected_at_kds_and_cashier():
    with TestClient(app) as owner, TestClient(app) as staff:
        csrf,_,bid=shop(owner,"owner-default")
        staff_csrf,uid=account(staff,"unassigned")
        with SessionLocal() as db:
            db.add(Membership(id=str(uuid.uuid4()),business_id=bid,user_id=uid,role="staff"))
            db.commit()
        d=staff.get(f"/api/businesses/{bid}/team/my-duty")
        assert d.status_code==200
        assert d.json()["mode"]=="order" and d.json()["assigned"] is False
        assert staff.get(f"/api/businesses/{bid}/kds/queue").status_code==403
        assert staff.get(f"/api/businesses/{bid}/order-dashboard").status_code==200
        assert staff.get(f"/api/businesses/{bid}/workstations").status_code==403
        assert staff.put(f"/api/businesses/{bid}/team/members/{uid}/duty",
            headers={"x-csrf-token":staff_csrf},
            json={"mode":"cashier","station":"all"}).status_code==403


def test_bar_can_see_only_bar_lines_and_cannot_pay_or_create_orders():
    with TestClient(app) as owner, TestClient(app) as bar:
        csrf,_,bid=shop(owner,"owner-bar")
        branch_id=owner.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
        tea=item(owner,csrf,bid,"Trà vải","TEA-ST","Đồ uống")
        food=item(owner,csrf,bid,"Cơm chiên","RICE-ST","Món ăn")
        assert owner.put(f"/api/businesses/{bid}/kds/category-routes",
            headers={"x-csrf-token":csrf},
            json={"category":"Đồ uống","station":"bar"}).status_code==200
        assert owner.put(f"/api/businesses/{bid}/kds/category-routes",
            headers={"x-csrf-token":csrf},
            json={"category":"Món ăn","station":"hot"}).status_code==200
        order=owner.post(f"/api/businesses/{bid}/orders",
            headers={"x-csrf-token":csrf},
            json={"idempotency_key":"security-kds-"+uuid.uuid4().hex,
                  "lines":[{"product_id":tea,"quantity":1},
                           {"product_id":food,"quantity":1}]})
        assert order.status_code==201,order.text
        csrf_worker,worker_id=account(bar,"bar1")
        with SessionLocal() as db:
            db.add(Membership(id=str(uuid.uuid4()),business_id=bid,user_id=worker_id,role="staff"))
            db.commit()
        assigned=assign(owner,csrf,bid,worker_id,"bar",branch_id,"bar")
        assert assigned["duty"]["station"]=="bar"
        current=bar.put(f"/api/businesses/{bid}/workstations/current",
            headers={"x-csrf-token":csrf_worker},
            json={"client_key":str(uuid.uuid4()),"name":"Bar tablet"})
        assert current.status_code==200,current.text
        assert current.json()["mode"]=="bar"
        queue=bar.get(f"/api/businesses/{bid}/kds/queue")
        assert queue.status_code==200,queue.text
        tickets=queue.json()["tickets"]
        assert len(tickets)==1
        assert {x["product_id"] for x in tickets[0]["lines"]}=={tea}
        assert {x["station"] for x in tickets[0]["lines"]}=={"bar"}
        assert bar.get(f"/api/businesses/{bid}/orders").status_code==403
        assert bar.get(f"/api/businesses/{bid}/order-dashboard").status_code==403
        assert bar.get(f"/api/businesses/{bid}/products").status_code==403
        assert bar.post(f"/api/businesses/{bid}/orders",
            headers={"x-csrf-token":csrf_worker},
            json={"idempotency_key":"no-accept-"+uuid.uuid4().hex,
                  "lines":[{"product_id":tea,"quantity":1}]}).status_code==403
        assert bar.post(
            f"/api/businesses/{bid}/pos-payments/{order.json()['id']}",
            headers={"x-csrf-token":csrf_worker},
            json={"request_id":"notallowed1234567","confirmed":True,
                  "method":"cash","expected_total_vnd":78000,
                  "cash_received_vnd":78000}).status_code==403
        ticket=tickets[0]
        cooked_id=next(x["id"] for x in owner.get(
            f"/api/businesses/{bid}/kds/queue").json()["tickets"][0]["lines"]
            if x["product_id"]==food)
        update=bar.post(
            f"/api/businesses/{bid}/kds/tickets/{ticket['id']}/lines/{cooked_id}/status",
            headers={"x-csrf-token":csrf_worker},
            json={"status":"preparing","expected_revision":0})
        assert update.status_code==403
        bar_id=ticket["lines"][0]["id"]
        update=bar.post(
            f"/api/businesses/{bid}/kds/tickets/{ticket['id']}/lines/{bar_id}/status",
            headers={"x-csrf-token":csrf_worker},
            json={"status":"preparing","expected_revision":0})
        assert update.status_code==200,update.text
        assert {x["product_id"] for x in update.json()["lines"]}=={tea}


def test_cashier_collects_payment_not_prepares_and_wrong_branch_denied():
    with TestClient(app) as owner, TestClient(app) as cashier:
        csrf,_,bid=shop(owner,"owner-cash")
        branch=owner.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
        product_id=item(owner,csrf,bid,"Trà sữa","MILK-CASH","Đồ uống")
        order=owner.post(f"/api/businesses/{bid}/orders",headers={"x-csrf-token":csrf},
           json={"idempotency_key":"cashier-"+uuid.uuid4().hex,
                 "lines":[{"product_id":product_id,"quantity":1}]})
        assert order.status_code==201
        staff_csrf,worker=account(cashier,"cash-staff")
        with SessionLocal() as db:
            db.add(Membership(id=str(uuid.uuid4()),business_id=bid,user_id=worker,role="staff"))
            db.commit()
        assign(owner,csrf,bid,worker,"cashier",branch)
        assert cashier.get(f"/api/businesses/{bid}/kds/queue").status_code==403
        assert cashier.get(f"/api/businesses/{bid}/orders").status_code==200
        assert cashier.get(f"/api/businesses/{bid}/customers").status_code==200
        response=cashier.post(f"/api/businesses/{bid}/pos-payments/{order.json()['id']}",
            headers={"x-csrf-token":staff_csrf},
            json={"request_id":"cashier-accepted-2026","confirmed":True,
                  "method":"cash","expected_total_vnd":39000,"cash_received_vnd":50000})
        assert response.status_code==200,response.text
        assert response.json()["payment"]["change_vnd"]==11000
        assert cashier.post(f"/api/businesses/{bid}/orders",
            headers={"x-csrf-token":staff_csrf},
            json={"idempotency_key":"cashier-no-create-123",
                  "lines":[{"product_id":product_id,"quantity":1}]}).status_code==403
        assert owner.put(f"/api/businesses/{bid}/team/members/{worker}/duty",
            headers={"x-csrf-token":csrf},
            json={"mode":"bar","station":"hot"}).status_code==422


def test_preview_uses_ephemeral_api_sandbox_and_allows_realistic_controls():
    static=Path(__file__).resolve().parents[1]/"app/static"
    js=(static/"workstation-ui.js").read_text()
    app_js=(static/"app.js").read_text()
    css=(static/"workstation-ui.css").read_text()
    team=(static/"team-ui.js").read_text()
    for feature in ("previewNav","openPreviewPicker","exitPreview","previewOnly",
                    "data-ezws=\"preview\"","stopImmediatePropagation","fullscreen"):
        assert feature in js
    assert "data-ezws=\"preview-picker\"" in team
    assert "data-team-duty" in team
    assert "cashierTaskTab()" in app_js
    assert "hostTaskTab()" in app_js
    assert "data-ez-workstation-preview" in css
    assert "ezws-preview-switcher" in js
    assert "ezws-preview-switcher:not([open])" in css
    assert "ezws-preview-bar" in css
    assert "INTERACTIVE SANDBOX" in js
    assert "previewResponse" in js and "previewRead" in js
    assert "throw Error(choose(" in js  # deny-by-default for every unmatched write
    assert "sandbox=null" in js
    assert "previewResponse?.(path,opt)" in app_js
    assert "previewRead?.(path,data)" in app_js
    assert "pointer-events:none!important" not in css
