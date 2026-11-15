"""EZ Thing V5: cross-feature tenant, ledger and operational safety tests."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ["DATABASE_URL"]="sqlite:///"+str(Path(__file__).parent/"pilot-tests.db")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app

@pytest.fixture(autouse=True)
def reset_database(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def cli():
    with TestClient(app) as c:
        yield c

def post(cli,path,body,csrf):
    return cli.post("/api"+path,json=body,headers={"x-csrf-token":csrf} if csrf else {})

def put(cli,path,body,csrf):
    return cli.put("/api"+path,json=body,headers={"x-csrf-token":csrf})

def signup(c,email):
    r=c.post("/api/auth/signup",json={
        "name":"Owner Ops","email":email,"password":"SafePassword!123"})
    assert r.status_code==201,r.text
    return r.json()["csrf_token"]

def make_business(c,csrf,industry="fnb",plan="PRO"):
    r=post(c,"/businesses",{"name":"Ops "+industry,"industry":industry,
        "selected_plan":plan,"need_tables":industry=="fnb",
        "need_inventory":True,"need_insights":True,
        "need_branches":plan=="PRO"},csrf)
    assert r.status_code==201,r.text
    return r.json()["id"]

def create_product(c,bid,csrf,name,sku,stock=8,track_stock=True,price=50000,cost=11000):
    r=post(c,f"/businesses/{bid}/products",{
        "name":name,"sku":sku,"price_vnd":price,"cost_vnd":cost,
        "stock":stock,"track_stock":track_stock},csrf)
    assert r.status_code==201,r.text
    return r.json()["id"]

def op(bid,endpoint):
    return f"/businesses/{bid}/operations/{endpoint}"

def test_waitlist_host_queue_is_idempotent_scoped_and_holds_seated_capacity(cli):
    csrf=signup(cli,"host@example.com")
    bid=make_business(cli,csrf)
    br=cli.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
    table=post(cli,f"/businesses/{bid}/tables",{
        "branch_id":br,"label":"A1","seats":4},csrf)
    assert table.status_code==201,table.text
    body={"request_id":"wait-00000001","branch_id":br,"name":"Guest One",
          "phone":"0912345678","party_size":3}
    r=post(cli,op(bid,"waitlist"),body,csrf)
    assert r.status_code==201,r.text
    assert post(cli,op(bid,"waitlist"),body,csrf).json()["id"]==r.json()["id"]
    assert post(cli,op(bid,"waitlist"),{**body,"party_size":2},csrf).status_code==409
    id=r.json()["id"]
    assert post(cli,op(bid,f"waitlist/{id}/status"),{"status":"seated"},csrf).status_code==409
    assert post(cli,op(bid,f"waitlist/{id}/status"),{"status":"ready"},csrf).status_code==200
    done=post(cli,op(bid,f"waitlist/{id}/status"),{"status":"seated"},csrf)
    assert done.status_code==200,done.text
    assert done.json()["details"]["table_label"]=="A1"
    assert done.json()["scheduled_at"] is not None
    assert len(cli.get("/api"+op(bid,"waitlist")).json())==1
    with TestClient(app) as stranger:
        signup(stranger,"outsider-wait@example.com")
        assert stranger.get("/api"+op(bid,"waitlist")).status_code==404

def test_staff_shift_overlap_and_permissions(cli):
    csrf=signup(cli,"shifts@example.com")
    bid=make_business(cli,csrf,industry="retail")
    user_id=cli.get("/api/auth/me").json()["id"]
    branch=cli.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
    start=(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))+timedelta(days=2))
    start=start.replace(hour=9,minute=0,second=0,microsecond=0)
    template={"request_id":"staff-shift-00001","branch_id":branch,
              "employee_id":user_id,"start_at":start.isoformat(),
              "end_at":(start+timedelta(hours=8)).isoformat()}
    r=post(cli,op(bid,"shifts"),template,csrf)
    assert r.status_code==201,r.text
    assert post(cli,op(bid,"shifts"),template,csrf).json()["id"]==r.json()["id"]
    bad={**template,"request_id":"staff-shift-00002","start_at":(start+timedelta(hours=1)).isoformat()}
    assert post(cli,op(bid,"shifts"),bad,csrf).status_code==409
    assert post(cli,op(bid,f"shifts/{r.json()['id']}/cancel"),{},csrf).status_code==200
    assert post(cli,op(bid,"shifts"),bad,csrf).status_code==201
    assert cli.get("/api"+op(bid,"staff")).json()[0]["id"]==user_id

def test_recipe_exact_ingredient_deduction_and_cancel_restores(cli):
    csrf=signup(cli,"recipe@example.com")
    bid=make_business(cli,csrf)
    ingredient=create_product(cli,bid,csrf,"Milk","MILK",stock=10)
    finished=create_product(cli,bid,csrf,"Latte","LATTE",stock=0,track_stock=False)
    recipe=put(cli,op(bid,f"recipes/{finished}"),{"ingredients":[
        {"product_id":ingredient,"quantity":2}]},csrf)
    assert recipe.status_code==200,recipe.text
    order=post(cli,f"/businesses/{bid}/orders",{
        "idempotency_key":"recipe-order-0001",
        "lines":[{"product_id":finished,"quantity":3}]},csrf)
    assert order.status_code==201,order.text
    stocks={x["id"]:x["stock"] for x in cli.get(f"/api/businesses/{bid}/products").json()}
    assert stocks[ingredient]==4
    assert post(cli,f"/businesses/{bid}/orders",{
        "idempotency_key":"recipe-order-0002",
        "lines":[{"product_id":finished,"quantity":3}]},csrf).status_code==409
    assert post(cli,f"/businesses/{bid}/orders/{order.json()['id']}/cancel",
                {"confirmed":True,"reason":"Customer cancelled"},csrf).status_code==200
    stocks={x["id"]:x["stock"] for x in cli.get(f"/api/businesses/{bid}/products").json()}
    assert stocks[ingredient]==10
    assert put(cli,op(bid,f"recipes/{ingredient}"),
               {"ingredients":[{"product_id":finished,"quantity":1}]},csrf).status_code==422

def test_transfer_is_request_only_never_mutates_business_stock(cli):
    csrf=signup(cli,"transfer@example.com")
    bid=make_business(cli,csrf,industry="retail")
    br=cli.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
    second=post(cli,f"/businesses/{bid}/branches",{"name":"Outlet B"},csrf).json()["id"]
    pid=create_product(cli,bid,csrf,"Shirt","SHIRT",stock=15)
    req={"request_id":"transfer-00000001","product_id":pid,
         "from_branch_id":br,"to_branch_id":second,"quantity":5}
    r=post(cli,op(bid,"transfers"),req,csrf)
    assert r.status_code==201,r.text
    assert r.json()["details"]["inventory_applied"] is False
    ident=r.json()["id"]
    assert post(cli,op(bid,f"transfers/{ident}/status"),{"status":"received"},csrf).status_code==409
    assert post(cli,op(bid,f"transfers/{ident}/status"),{"status":"approved"},csrf).status_code==200
    assert post(cli,op(bid,f"transfers/{ident}/status"),{"status":"received"},csrf).status_code==200
    assert next(x for x in cli.get(f"/api/businesses/{bid}/products").json()
                if x["id"]==pid)["stock"]==15

def test_loyalty_earn_once_then_redeem_and_report_expense(cli):
    csrf=signup(cli,"loyalty@example.com")
    bid=make_business(cli,csrf,industry="retail")
    pid=create_product(cli,bid,csrf,"Book","BOOK",stock=30,price=60000,cost=20000)
    cid=post(cli,f"/businesses/{bid}/customers",{"name":"Reward guest","phone":"0909090909"},csrf).json()["id"]
    order=post(cli,f"/businesses/{bid}/orders",{
        "idempotency_key":"loyalty-order-001","customer_id":cid,
        "lines":[{"product_id":pid,"quantity":2}]},csrf).json()
    assert post(cli,f"/businesses/{bid}/orders/{order['id']}/paid",
                {"confirmed":True},csrf).status_code==200
    assert post(cli,f"/businesses/{bid}/orders/{order['id']}/paid",
                {"confirmed":True},csrf).status_code==200
    points=cli.get("/api"+op(bid,"loyalty")).json()
    assert points["balances"]==[{"customer_id":cid,"points":12}]
    redeem={"request_id":"points-redeem-0001","customer_id":cid,
            "points":4,"note":"Free sample"}
    assert post(cli,op(bid,"loyalty/redeem"),redeem,csrf).status_code==201
    assert post(cli,op(bid,"loyalty/redeem"),redeem,csrf).status_code==201
    assert post(cli,op(bid,"loyalty/redeem"),{**redeem,
           "request_id":"points-redeem-0002","points":50},csrf).status_code==409
    assert cli.get("/api"+op(bid,"loyalty")).json()["balances"][0]["points"]==8
    expense={"request_id":"expense-0000001","amount_vnd":15000,
             "category":"utilities","note":"Electricity"}
    assert post(cli,op(bid,"expenses"),expense,csrf).status_code==201
    assert post(cli,op(bid,"expenses"),expense,csrf).status_code==201
    report=cli.get("/api"+op(bid,"finance"))
    assert report.status_code==200,report.text
    assert report.json()["revenue_vnd"]==120000
    assert report.json()["estimated_cogs_vnd"]==40000
    assert report.json()["operating_expenses_vnd"]==15000
    assert report.json()["estimated_profit_vnd"]==65000

def test_notification_draft_and_deposit_are_explicitly_unpaid_unsent(cli):
    csrf=signup(cli,"draft@example.com")
    bid=make_business(cli,csrf)
    message={"request_id":"draft-00000001","channel":"zalo",
             "recipient":"0900123456","message":"Your table is ready"}
    r=post(cli,op(bid,"notifications"),message,csrf)
    assert r.status_code==201,r.text
    assert r.json()["status"]=="draft" and r.json()["details"]["sent"] is False
    branch=cli.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
    assert post(cli,f"/businesses/{bid}/tables",{
        "branch_id":branch,"label":"R1","seats":4},csrf).status_code==201
    start=(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))+timedelta(days=2)).replace(
        hour=11,minute=0,second=0,microsecond=0)
    reservation=post(cli,f"/businesses/{bid}/reservations",{
        "request_id":"reservation-deposit-001",
        "customer_name":"Deposit guest","phone":"0901234567",
        "party_size":2,"start_at":start.isoformat(),"duration_minutes":90,
        "branch_id":branch},csrf)
    assert reservation.status_code==201,reservation.text
    deposit=post(cli,op(bid,"deposits"),{
        "request_id":"deposit-00000001","reservation_id":reservation.json()["id"],
        "amount_vnd":200000},csrf)
    assert deposit.status_code==201,deposit.text
    assert deposit.json()["status"]=="pending_gateway"
    assert deposit.json()["details"]["paid"] is False
    assert deposit.json()["details"]["collection_enabled"] is False

def test_branch_policy_override_does_not_change_other_branch(cli):
    csrf=signup(cli,"branchhours@example.com")
    bid=make_business(cli,csrf)
    branch=cli.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
    other=post(cli,f"/businesses/{bid}/branches",{"name":"Outlet B"},csrf).json()["id"]
    p={"open_time":"12:00","last_seating_time":"14:00","close_time":"16:00",
       "closed_weekdays":[],"blocked_dates":[]}
    assert put(cli,f"/businesses/{bid}/reservations/policy?branch_id={branch}",p,csrf).status_code==200
    assert cli.get(f"/api/businesses/{bid}/reservations/policy?branch_id={branch}").json()==p
    assert cli.get(f"/api/businesses/{bid}/reservations/policy?branch_id={other}").json()["open_time"]=="08:00"
    day=(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))+timedelta(days=2)).date().isoformat()
    avail=cli.get(f"/api/businesses/{bid}/reservations/availability",
       params={"day":day,"party_size":2,"branch_id":branch})
    assert avail.status_code==200,avail.text
    assert all(int(x["start_at"][11:13])>=12 for x in avail.json()["slots"])
    assert put(cli,f"/businesses/{bid}/reservations/policy?branch_id=wrong",p,csrf).status_code==404

def test_operations_ui_and_csrf(cli):
    csrf=signup(cli,"ui-ops@example.com")
    bid=make_business(cli,csrf)
    assert cli.get("/assets/operations-v5.js").status_code==200
    assert cli.get("/assets/operations-v5.css").status_code==200
    html=cli.get("/app").text
    assert "operations-v5.js" in html and "operations-v5.css" in html
    assert post(cli,op(bid,"notifications"),{
        "request_id":"draft-00000003","channel":"email",
        "recipient":"x@example.com","message":"Hello world"},None).status_code==403
    assert cli.get("/api"+op(bid,"sync")).json()["transport"]=="polling"


def test_branch_inventory_opt_in_sale_transfer_return_stock_invariants(cli):
    """Stock must remain globally conserved and allocated across branches."""
    csrf=signup(cli,"branch-ledger@example.com")
    bid=make_business(cli,csrf,industry="retail")
    branches=cli.get(f"/api/businesses/{bid}/branches").json()
    primary=branches[0]["id"]
    second=post(cli,f"/businesses/{bid}/branches",{"name":"Second store"},csrf).json()["id"]
    pid=create_product(cli,bid,csrf,"Soap","SOAP-01",stock=15,price=30000)
    base=op(bid,"inventory")
    assert cli.get("/api"+base).json()["enabled"] is False
    assert post(cli,base+"/activate",{},csrf).status_code==422
    init=post(cli,base+"/activate",{"confirmation":"ALLOCATE_ALL_TO_PRIMARY_BRANCH"},csrf)
    assert init.status_code==200,init.text
    assert init.json()["initial_branch_id"]==primary
    assert post(cli,base+"/activate",{"confirmation":"ALLOCATE_ALL_TO_PRIMARY_BRANCH"},csrf).status_code==200
    def snap():
        x=cli.get("/api"+base).json()
        return {(v["branch_id"],v["product_id"]):v["quantity"] for v in x["balances"]}
    assert snap()=={(primary,pid):15}
    req={"request_id":"transfer-real-stock-001","product_id":pid,
         "from_branch_id":primary,"to_branch_id":second,"quantity":5}
    r=post(cli,op(bid,"transfers"),req,csrf)
    assert r.status_code==201,r.text
    ident=r.json()["id"]
    assert post(cli,op(bid,f"transfers/{ident}/status"),
                {"status":"approved"},csrf).status_code==200
    received=post(cli,op(bid,f"transfers/{ident}/status"),
                  {"status":"received"},csrf)
    assert received.status_code==200,received.text
    assert received.json()["details"]["inventory_applied"] is True
    assert post(cli,op(bid,f"transfers/{ident}/status"),
                {"status":"received"},csrf).status_code==200
    assert snap()=={(primary,pid):10,(second,pid):5}
    order=post(cli,f"/businesses/{bid}/orders",{
        "idempotency_key":"branch-order-00001","branch_id":second,
        "lines":[{"product_id":pid,"quantity":3}]},csrf)
    assert order.status_code==201,order.text
    assert snap()=={(primary,pid):10,(second,pid):2}
    assert post(cli,f"/businesses/{bid}/orders",{
        "idempotency_key":"branch-order-00002","branch_id":second,
        "lines":[{"product_id":pid,"quantity":3}]},csrf).status_code==409
    assert post(cli,f"/businesses/{bid}/orders/{order.json()['id']}/cancel",
                {"confirmed":True,"reason":"Return to shelf"},csrf).status_code==200
    assert snap()=={(primary,pid):10,(second,pid):5}
    adjustment=post(cli,f"/businesses/{bid}/products/{pid}/stock",
                    {"delta":-1,"reason":"Damaged","branch_id":second},csrf)
    assert adjustment.status_code==200,adjustment.text
    assert snap()=={(primary,pid):10,(second,pid):4}
    assert adjustment.json()["stock"]==14
    unauthorized=post(cli,op(bid,"inventory/activate"),
                      {"confirmation":"ALLOCATE_ALL_TO_PRIMARY_BRANCH"},None)
    assert unauthorized.status_code==403
    with TestClient(app) as outsider:
        signup(outsider,"branch-outsider@example.com")
        assert outsider.get("/api"+base).status_code==404
        assert post(outsider,op(bid,"transfers"),req,None).status_code==403


def test_recipe_sold_on_secondary_branch_updates_ingredient_location(cli):
    csrf=signup(cli,"branch-recipe@example.com")
    bid=make_business(cli,csrf)
    branches=cli.get(f"/api/businesses/{bid}/branches").json()
    primary=branches[0]["id"]
    second=post(cli,f"/businesses/{bid}/branches",{"name":"Second FNB"},csrf).json()["id"]
    milk=create_product(cli,bid,csrf,"Milk","MILK-SECOND",stock=20)
    latte=create_product(cli,bid,csrf,"Latte","LATTE-SECOND",stock=0,track_stock=False)
    assert put(cli,op(bid,f"recipes/{latte}"),{
        "ingredients":[{"product_id":milk,"quantity":2}]},csrf).status_code==200
    assert post(cli,op(bid,"inventory/activate"),
                {"confirmation":"ALLOCATE_ALL_TO_PRIMARY_BRANCH"},csrf).status_code==200
    transfer=post(cli,op(bid,"transfers"),{
        "request_id":"branch-recipe-transfer1","product_id":milk,
        "from_branch_id":primary,"to_branch_id":second,"quantity":8},csrf).json()
    assert post(cli,op(bid,f"transfers/{transfer['id']}/status"),
                {"status":"approved"},csrf).status_code==200
    assert post(cli,op(bid,f"transfers/{transfer['id']}/status"),
                {"status":"received"},csrf).status_code==200
    order=post(cli,f"/businesses/{bid}/orders",{
        "idempotency_key":"branch-recipe-order1","branch_id":second,
        "lines":[{"product_id":latte,"quantity":3}]},csrf)
    assert order.status_code==201,order.text
    balances=cli.get("/api"+op(bid,"inventory")).json()["balances"]
    assert next(x for x in balances if x["branch_id"]==second)["quantity"]==2
    assert post(cli,f"/businesses/{bid}/orders/{order.json()['id']}/cancel",{
        "confirmed":True,"reason":"Refund before kitchen"},csrf).status_code==200
    balances=cli.get("/api"+op(bid,"inventory")).json()["balances"]
    assert next(x for x in balances if x["branch_id"]==second)["quantity"]==8
