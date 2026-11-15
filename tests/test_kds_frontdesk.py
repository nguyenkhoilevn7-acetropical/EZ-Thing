"""Kitchen/Bar KDS: order item snapshots, station routing, roles and lifecycle."""
import os
import sys
import uuid
from pathlib import Path
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Membership


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def cli():
    with TestClient(app) as c:
        yield c


def request(c, method, path, body=None, csrf=None):
    return c.request(method, "/api" + path, json=body, headers={
        "x-csrf-token": csrf} if csrf else {})


def signup(c, email):
    response=request(c,"POST","/auth/signup",{
        "name":"KDS Owner","email":email,"password":"SafePassword!123"})
    assert response.status_code==201,response.text
    return response.json()["csrf_token"]


def new_business(c,csrf,industry="fnb"):
    response=request(c,"POST","/businesses",{
        "name":"KDS Test","industry":industry,"selected_plan":"PRO",
        "need_tables":industry=="fnb","need_inventory":True,
        "need_insights":True,"need_branches":True},csrf)
    assert response.status_code==201,response.text
    return response.json()["id"]


def new_product(c,bid,csrf,name,sku,category="Đồ uống",stock=0,track_stock=False):
    response=request(c,"POST",f"/businesses/{bid}/products",{
        "name":name,"sku":sku,"category":category,"price_vnd":35000,
        "stock":stock,"track_stock":track_stock},csrf)
    assert response.status_code==201,response.text
    return response.json()["id"]


def new_order(c,bid,csrf,lines,branch_id=None):
    response=request(c,"POST",f"/businesses/{bid}/orders",{
        "idempotency_key":"kds-order-"+uuid.uuid4().hex,
        "branch_id":branch_id,"lines":lines,"note":"Ít đường · Không hành"},csrf)
    assert response.status_code==201,response.text
    return response.json()


def kds(bid,path=""):
    return f"/businesses/{bid}/kds"+path


def test_fnb_kds_fire_freezes_menu_modifiers_and_routes_by_product(cli):
    csrf=signup(cli,"kds-fire@example.com")
    bid=new_business(cli,csrf)
    milk=new_product(cli,bid,csrf,"Milk ingredient","MILK","Kho",20,True)
    tea=new_product(cli,bid,csrf,"Trà sữa","TEA")
    bread=new_product(cli,bid,csrf,"Bánh mì","BREAD","Đồ ăn")
    toppings=request(cli,"PUT",f"/businesses/{bid}/products/{tea}/modifiers",{
        "expected_revision":0,"groups":[
            {"id":"size","name":"Size","min_select":1,"max_select":1,
             "options":[{"id":"size-m","name":"M","price_vnd":0},
                        {"id":"size-l","name":"L","price_vnd":7000}]},
            {"id":"toppings","name":"Topping","min_select":0,"max_select":1,
             "options":[{"id":"pearl","name":"Trân châu","price_vnd":5000,
                         "inventory_product_id":milk,"inventory_quantity":1}]}
        ]},csrf)
    assert toppings.status_code==200,toppings.text
    route=request(cli,"PUT",kds(bid,"/routes"),{
        "product_id":bread,"station":"hot"},csrf)
    assert route.status_code==200,route.text
    o=new_order(cli,bid,csrf,[
        {"product_id":tea,"quantity":2,"selected_options":["size-l","pearl"]},
        {"product_id":bread,"quantity":1}
    ])
    fire=request(cli,"POST",kds(bid,"/fire"),{"order_id":o["id"]},csrf)
    assert fire.status_code==201,fire.text
    ticket_id=fire.json()["id"]
    assert request(cli,"POST",kds(bid,"/fire"),{"order_id":o["id"]},csrf).json()["id"]==ticket_id
    queue=cli.get("/api"+kds(bid,"/queue")).json()
    assert queue["transport"]=="foreground_polling"
    assert queue["notifications"]=="browser_tab_opt_in_only"
    assert queue["all_day"]=={"bar":2,"hot":1}
    assert len(queue["tickets"])==1
    ticket=queue["tickets"][0]
    assert ticket["revision"]==0 and ticket["status"]=="pending"
    assert "Ít đường" in ticket["note"]
    tea_line=next(x for x in ticket["lines"] if x["product_id"]==tea)
    bread_line=next(x for x in ticket["lines"] if x["product_id"]==bread)
    assert tea_line["station"]=="bar" and bread_line["station"]=="hot"
    assert [x["name"] for x in tea_line["modifiers"]]==["L","Trân châu"]
    assert tea_line["quantity"]==2
    assert tea_line["id"] in [x["id"] for x in o["items"]]


def test_kds_item_status_sla_and_optimistic_lock(cli):
    csrf=signup(cli,"kds-item@example.com")
    bid=new_business(cli,csrf)
    tea=new_product(cli,bid,csrf,"Trà sữa","TEA")
    rice=new_product(cli,bid,csrf,"Cơm gà","RICE","Đồ ăn")
    o=new_order(cli,bid,csrf,[{"product_id":tea,"quantity":1},
                               {"product_id":rice,"quantity":1}])
    job=request(cli,"POST",kds(bid,"/fire"),{"order_id":o["id"]},csrf).json()
    path=kds(bid,f"/tickets/{job['id']}/lines/")
    a,b=[x["id"] for x in cli.get("/api"+kds(bid,"/queue")).json()["tickets"][0]["lines"]]
    assert request(cli,"POST",path+a+"/status",{"status":"served","expected_revision":0},csrf).status_code==409
    x=request(cli,"POST",path+a+"/status",{"status":"preparing","expected_revision":0},csrf)
    assert x.status_code==200,x.text
    assert x.json()["revision"]==1 and x.json()["status"]=="preparing"
    assert request(cli,"POST",path+b+"/status",{"status":"preparing","expected_revision":0},csrf).status_code==409
    x=request(cli,"POST",path+b+"/status",{"status":"held","expected_revision":1},csrf)
    assert x.status_code==200 and x.json()["revision"]==2
    assert request(cli,"POST",path+b+"/status",{"status":"ready","expected_revision":2},csrf).status_code==409
    x=request(cli,"POST",path+b+"/status",{"status":"preparing","expected_revision":2},csrf)
    assert x.status_code==200
    x=request(cli,"POST",path+a+"/status",{"status":"ready","expected_revision":3},csrf)
    assert x.status_code==200 and x.json()["status"]=="preparing"
    x=request(cli,"POST",path+b+"/status",{"status":"ready","expected_revision":4},csrf)
    assert x.status_code==200 and x.json()["status"]=="ready"
    x=request(cli,"POST",path+a+"/status",{"status":"served","expected_revision":5},csrf)
    assert x.status_code==200 and x.json()["status"]=="ready"
    x=request(cli,"POST",path+b+"/status",{"status":"served","expected_revision":6},csrf)
    assert x.status_code==200 and x.json()["status"]=="served"
    assert cli.get("/api"+kds(bid,"/queue")).json()["all_day"]=={}
    assert request(cli,"POST",path+a+"/status",{"status":"ready","expected_revision":7},csrf).status_code==409
    recall=request(cli,"POST",path+a+"/status",{
        "status":"ready","expected_revision":7,
        "reason":"Đã giao nhầm món"},csrf)
    assert recall.status_code==200,recall.text
    assert recall.json()["status"]=="ready"
    assert cli.get("/api"+kds(bid,"/queue")).json()["all_day"]=={"bar":1}


def test_kds_manager_availability_branch_scope_and_tenant_isolation(cli):
    csrf=signup(cli,"kds-tenant@example.com")
    bid=new_business(cli,csrf)
    p=new_product(cli,bid,csrf,"Matcha","MATCHA")
    second=request(cli,"POST",f"/businesses/{bid}/branches",{
        "name":"Outlet 2"},csrf)
    assert second.status_code==201,second.text
    branch=second.json()["id"]
    o=new_order(cli,bid,csrf,[{"product_id":p,"quantity":1}],branch_id=branch)
    assert request(cli,"POST",kds(bid,"/fire"),{
        "order_id":o["id"]},csrf).status_code==201
    queue=cli.get("/api"+kds(bid,"/queue?branch_id="+branch)).json()
    assert len(queue["tickets"])==1
    assert cli.get("/api"+kds(bid,"/queue?branch_id=wrong")).status_code==404
    avail=request(cli,"POST",kds(bid,f"/products/{p}/availability"),{
        "available":False,"reason":"Tạm hết nguyên liệu"},csrf)
    assert avail.status_code==200,avail.text
    products=cli.get(f"/api/businesses/{bid}/products").json()
    assert next(x for x in products if x["id"]==p)["active"] is False
    assert request(cli,"POST",kds(bid,f"/products/{p}/availability"),{
        "available":True,"reason":"Đã nhập nguyên liệu"},csrf).status_code==200
    with TestClient(app) as other:
        other_csrf=signup(other,"kds-outsider@example.com")
        foreign=new_business(other,other_csrf,industry="retail")
        assert other.get("/api"+kds(bid,"/queue")).status_code==404
        assert request(other,"PUT",kds(bid,"/routes"),{
            "product_id":p,"station":"bar"},other_csrf).status_code==404
        assert other.get("/api"+kds(foreign,"/queue")).status_code==404
    assert request(cli,"PUT",kds(bid,"/routes"),{
        "product_id":"not-owned","station":"bar"},csrf).status_code==404


def test_kds_staff_can_bump_but_cannot_set_routes_recall_or_hide_menu(cli):
    csrf=signup(cli,"kds-manager@example.com")
    bid=new_business(cli,csrf)
    p=new_product(cli,bid,csrf,"Coffee","COFFEE")
    order=new_order(cli,bid,csrf,[{"product_id":p,"quantity":1}])
    job=request(cli,"POST",kds(bid,"/fire"),{
        "order_id":order["id"]},csrf).json()
    line=cli.get("/api"+kds(bid,"/queue")).json()["tickets"][0]["lines"][0]["id"]
    path=kds(bid,f"/tickets/{job['id']}/lines/{line}/status")
    with TestClient(app) as cashier:
        csrf_staff=signup(cashier,"kds-staff@example.com")
        user_id=cashier.get("/api/auth/me").json()["id"]
        with SessionLocal() as db:
            db.add(Membership(id=str(uuid.uuid4()),business_id=bid,
                              user_id=user_id,role="staff"))
            db.commit()
        assert cashier.get("/api"+kds(bid,"/queue")).status_code==200
        assert request(cashier,"PUT",kds(bid,"/routes"),{
            "product_id":p,"station":"cold"},csrf_staff).status_code==403
        assert request(cashier,"POST",kds(bid,f"/products/{p}/availability"),{
            "available":False,"reason":"Out of stock"},csrf_staff).status_code==403
        result=request(cashier,"POST",path,{"status":"preparing","expected_revision":0},csrf_staff)
        assert result.status_code==200,result.text
        result=request(cashier,"POST",path,{"status":"ready","expected_revision":1},csrf_staff)
        assert result.status_code==200,result.text
        assert request(cashier,"POST",path,{
            "status":"preparing","expected_revision":2,"reason":"Too late"},csrf_staff).status_code==409
    assert request(cli,"POST",path,{
        "status":"preparing","expected_revision":2,
        "reason":"Khách muốn làm lại"},csrf).status_code==200


def test_kds_legacy_bulk_and_csrf_guards(cli):
    csrf=signup(cli,"kds-legacy@example.com")
    bid=new_business(cli,csrf)
    p=new_product(cli,bid,csrf,"Bún bò","BUN","Món chính")
    o=new_order(cli,bid,csrf,[{"product_id":p,"quantity":2}])
    fire=request(cli,"POST",f"/businesses/{bid}/industry/kitchen",{
        "order_id":o["id"]},csrf)
    assert fire.status_code==201,fire.text
    job=fire.json()
    assert job["details"]["kds_lines"][0]["station"]=="hot"
    assert request(cli,"POST",kds(bid,"/fire"),{"order_id":o["id"]}).status_code==403
    assert request(cli,"PUT",kds(bid,"/routes"),{"product_id":p,"station":"cold"}).status_code==403
    assert cli.get("/api"+kds(bid,"/queue")).json()["tickets"][0]["status"]=="pending"
    for expected in ("preparing","ready","served"):
        bulk=request(cli,"POST",f"/businesses/{bid}/industry/kitchen/{job['id']}/status",{
            "status":expected},csrf)
        assert bulk.status_code==200,bulk.text
        snapshot=cli.get("/api"+kds(bid,"/queue")).json()["tickets"][0]
        assert snapshot["status"]==expected
        assert all(x["status"]==expected for x in snapshot["lines"])


def test_mobile_kds_assets_are_linked_without_page_reload(cli):
    with TestClient(app) as c:
        response=c.get("/app")
        assert response.status_code==200
        for asset in ("merchant-kds.js","merchant-kds.css"):
            assert "/assets/"+asset+"?h=" in response.text
            assert c.get("/assets/"+asset).status_code==200
    from pathlib import Path
    src=(Path(__file__).resolve().parents[1]/"app/static/app.js").read_text()
    assert "fnb:['overview','orders','reservations','kitchen']" in src
    assert "retail:['overview','orders','products','customers']" in src
    assert "services:['overview','appointments','products','customers']" in src
    assert "Lễ tân & xếp bàn" in src



def test_expeditor_runner_call_and_supervised_station_transfer(cli):
    csrf=signup(cli,"kds-expo@example.com")
    bid=new_business(cli,csrf)
    product=new_product(cli,bid,csrf,"House special","HOUSE-S","Món đặc biệt")
    order=new_order(cli,bid,csrf,[{"product_id":product,"quantity":2}])
    ticket=request(cli,"POST",kds(bid,"/fire"),{"order_id":order["id"]},csrf).json()
    tid=ticket["id"]
    line=cli.get("/api"+kds(bid,"/queue")).json()["tickets"][0]["lines"][0]
    assert line["station"]=="expo"  # Unclassified item, needs explicit route.
    path=kds(bid,f"/tickets/{tid}/lines/{line['id']}")
    moved=request(cli,"POST",path+"/move-station",{
        "station":"cold","reason":"Chuyển qua bếp lạnh",
        "expected_revision":0},csrf)
    assert moved.status_code==200,moved.text
    assert moved.json()["lines"][0]["station"]=="cold"
    assert moved.json()["revision"]==1
    assert cli.get("/api"+kds(bid,"/queue")).json()["all_day"]=={"cold":2}
    assert request(cli,"POST",path+"/call-runner",{"expected_revision":1},csrf).status_code==409
    assert request(cli,"POST",path+"/move-station",{
        "station":"bar","reason":"Đổi khu chế biến",
        "expected_revision":0},csrf).status_code==409
    assert request(cli,"POST",path+"/status",{
        "status":"preparing","expected_revision":1},csrf).status_code==200
    assert request(cli,"POST",path+"/status",{
        "status":"ready","expected_revision":2},csrf).status_code==200
    ready=cli.get("/api"+kds(bid,"/queue")).json()
    assert ready["ready_for_expo"]==2
    assert request(cli,"POST",path+"/move-station",{
        "station":"bar","reason":"Đổi trạm sau khi xong",
        "expected_revision":3},csrf).status_code==409
    alerted=request(cli,"POST",path+"/call-runner",{"expected_revision":3},csrf)
    assert alerted.status_code==200,alerted.text
    called=alerted.json()["lines"][0]["runner_called_at"]
    assert called and alerted.json()["revision"]==4
    retried=request(cli,"POST",path+"/call-runner",{"expected_revision":3},csrf)
    assert retried.status_code==200 and retried.json()["revision"]==4
    assert retried.json()["lines"][0]["runner_called_at"]==called
    assert request(cli,"POST",path+"/status",{
        "status":"served","expected_revision":4},csrf).status_code==200
    assert request(cli,"POST",path+"/call-runner",{"expected_revision":5},csrf).status_code==409
