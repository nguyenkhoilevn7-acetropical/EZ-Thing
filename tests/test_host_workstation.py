"""Host workstation: branch scoping, concurrency, audited table sessions, booking edits."""
import os, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

os.environ["DATABASE_URL"]="sqlite:///"+str(Path(__file__).parent/"pilot-tests.db")
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AuditEvent, Membership, SaleOrder
from app.workflows import IndustryWorkItem

@pytest.fixture(autouse=True)
def db_reset(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED",raising=False)
    Base.metadata.drop_all(bind=engine);Base.metadata.create_all(bind=engine)

def req(c,method,path,body=None,csrf=None):
    return c.request(method,"/api"+path,json=body,
                     headers={"x-csrf-token":csrf} if csrf else {})

def signup(c,tag):
    r=req(c,"POST","/auth/signup",{
        "name":"Host "+tag,"email":f"host-tester-{tag}@example.com",
        "password":"SafePassword!123"})
    assert r.status_code==201,r.text
    return r.json()["csrf_token"],r.json()["id"]

def shop(c,tag):
    csrf,uid=signup(c,tag)
    b=req(c,"POST","/businesses",{
        "name":"Dining "+tag,"industry":"fnb","need_tables":True,
        "need_inventory":True,"need_branches":True,"selected_plan":"PRO"},csrf)
    assert b.status_code==201,b.text
    bid=b.json()["id"]
    branch=c.get(f"/api/businesses/{bid}/branches").json()[0]["id"]
    t=req(c,"POST",f"/businesses/{bid}/tables",{
        "label":"T02","seats":4,"branch_id":branch},csrf)
    assert t.status_code==201,t.text
    extra=req(c,"POST",f"/businesses/{bid}/tables",{
        "label":"T03","seats":6,"branch_id":branch},csrf)
    assert extra.status_code==201,extra.text
    return csrf,bid,branch

def table_ids(c,bid):
    r=c.get(f"/api/businesses/{bid}/host/board")
    assert r.status_code==200,r.text
    return r.json()["tables"]

def host_action(c,csrf,bid,tid,action,revision=0,**kw):
    return req(c,"POST",f"/businesses/{bid}/host/tables/{tid}/action",
               {"action":action,"expected_revision":revision,**kw},csrf)

def assigned_staff(owner,owner_csrf,bid,branch,c,tag,mode):
    csrf,uid=signup(c,tag)
    with SessionLocal() as db:
        db.add(Membership(id=str(uuid.uuid4()),business_id=bid,user_id=uid,role="staff"))
        db.commit()
    a=req(owner,"PUT",f"/businesses/{bid}/team/members/{uid}/duty",{
        "mode":mode,"branch_id":branch,"station":"all"},owner_csrf)
    assert a.status_code==200,a.text
    return csrf,uid

def test_host_seat_update_transfer_join_release_and_audit():
    with TestClient(app) as owner:
        csrf,bid,branch=shop(owner,"table-owner")
        tables=table_ids(owner,bid)
        first=tables[0]["id"];second=tables[1]["id"]
        seated=host_action(owner,csrf,bid,first,"seat",guest_count=3,note="VIP")
        assert seated.status_code==200,seated.text
        row=next(t for t in seated.json()["tables"] if t["id"]==first)
        assert row["status"]=="occupied" and row["guest_count"]==3
        assert row["revision"]==1 and row["note"]=="VIP"
        assert host_action(owner,csrf,bid,first,"seat",revision=1).status_code==409
        assert host_action(owner,csrf,bid,first,"update",revision=0,guest_count=2).status_code==409
        changed=host_action(owner,csrf,bid,first,"update",revision=1,guest_count=4,note="Bàn gia đình")
        assert changed.status_code==200
        merged=host_action(owner,csrf,bid,first,"join",revision=2,target_table_id=second)
        assert merged.status_code==200,merged.text
        rows={t["id"]:t for t in merged.json()["tables"]}
        assert rows[first]["group_id"] and rows[second]["group_id"]==rows[first]["group_id"]
        assert host_action(owner,csrf,bid,first,"transfer",revision=3,
                           target_table_id=second).status_code==409
        unlinked=host_action(owner,csrf,bid,second,"unjoin",revision=1)
        assert unlinked.status_code==200,unlinked.text
        moved=host_action(owner,csrf,bid,first,"transfer",revision=4,target_table_id=second)
        assert moved.status_code==200,moved.text
        rows={t["id"]:t for t in moved.json()["tables"]}
        assert rows[first]["status"]=="available" and rows[second]["guest_count"]==4
        released=host_action(owner,csrf,bid,second,"release",revision=3)
        assert released.status_code==200,released.text
        assert next(t for t in released.json()["tables"] if t["id"]==second)["status"]=="cleaning"
        ready=host_action(owner,csrf,bid,second,"ready",revision=4)
        assert ready.status_code==200,ready.text
        locked=host_action(owner,csrf,bid,second,"block",revision=5,note="Bàn sửa chữa")
        assert locked.status_code==200
        assert host_action(owner,csrf,bid,second,"seat",revision=6,guest_count=2).status_code==409
        assert host_action(owner,csrf,bid,second,"unblock",revision=6).status_code==200
        with SessionLocal() as db:
            audits=db.scalars(select(AuditEvent).where(AuditEvent.business_id==bid,
                AuditEvent.action.like("host.table_%"))).all()
            assert len(audits)>=7

def test_joined_table_release_cleans_all_tables_and_preserves_audit():
    with TestClient(app) as owner:
        csrf,bid,branch=shop(owner,"join-release")
        first,second=[x["id"] for x in table_ids(owner,bid)][:2]
        seated=host_action(owner,csrf,bid,first,"seat",guest_count=3)
        assert seated.status_code==200,seated.text
        joined=host_action(owner,csrf,bid,first,"join",revision=1,target_table_id=second)
        assert joined.status_code==200,joined.text
        released=host_action(owner,csrf,bid,first,"release",revision=2)
        assert released.status_code==200,released.text
        states={x["id"]:x for x in released.json()["tables"]}
        assert states[first]["status"]=="cleaning"
        assert states[second]["status"]=="cleaning"
        assert not states[first]["group_id"] and not states[second]["group_id"]
        assert states[second]["revision"]==2


def test_host_branch_employee_and_cross_tenant_rejections():
    with TestClient(app) as owner,TestClient(app) as employee,TestClient(app) as foreign:
        csrf,bid,branch=shop(owner,"tenant-owner")
        _,otherbid,_=shop(foreign,"tenant-foreign")
        host_csrf,_=assigned_staff(owner,csrf,bid,branch,employee,"staff-host","host")
        tid=table_ids(owner,bid)[0]["id"]
        assert employee.get(f"/api/businesses/{bid}/host/board").status_code==200
        assert employee.get(f"/api/businesses/{otherbid}/host/board").status_code==404
        assert foreign.get(f"/api/businesses/{bid}/host/board").status_code==404
        assert host_action(employee,host_csrf,bid,tid,"seat",guest_count=2).status_code==200
        assert employee.get(f"/api/businesses/{bid}/floorplan").status_code==200
        other=owner.post(f"/api/businesses/{bid}/branches",
                         headers={"x-csrf-token":csrf},json={"name":"Second Branch"})
        assert other.status_code==201,other.text
        otherbranch=other.json()["id"]
        assert employee.get(f"/api/businesses/{bid}/host/board?branch_id={otherbranch}").status_code==403
        assert employee.get(f"/api/businesses/{bid}/floorplan?branch_id={otherbranch}").status_code==403
        assert employee.put(f"/api/businesses/{bid}/floorplan",
                            headers={"x-csrf-token":host_csrf},
                            json={"branch_id":branch,"revision":0,"zones":[{"id":"inside","name":"Trong nhà"}],
                                  "placements":[]}).status_code==403

def test_open_check_prevents_host_release_and_transfer():
    with TestClient(app) as owner:
        csrf,bid,branch=shop(owner,"livecheck-owner")
        first=table_ids(owner,bid)[0]["id"]
        pr=req(owner,"POST",f"/businesses/{bid}/products",{
            "name":"Cà phê","sku":"CAFE-HOST","category":"Đồ uống",
            "price_vnd":35000,"track_stock":False},csrf)
        assert pr.status_code==201
        order=req(owner,"POST",f"/businesses/{bid}/orders",{
            "idempotency_key":"host-order-"+uuid.uuid4().hex,
            "branch_id":branch,"table_id":first,
            "lines":[{"product_id":pr.json()["id"],"quantity":1}]},csrf)
        assert order.status_code==201,order.text
        t=table_ids(owner,bid)[0]
        assert t["status"]=="occupied" and t["has_open_check"]
        assert host_action(owner,csrf,bid,first,"release",revision=0).status_code==409
        assert host_action(owner,csrf,bid,first,"transfer",revision=0,
                           target_table_id=table_ids(owner,bid)[1]["id"]).status_code==409
        with SessionLocal() as db:
            assert db.get(SaleOrder,order.json()["id"]).table_id==first

def test_future_reservation_edit_cancel_and_overlapping_booking():
    with TestClient(app) as owner,TestClient(app) as worker:
        csrf,bid,branch=shop(owner,"book-owner")
        staff_csrf,_=assigned_staff(owner,csrf,bid,branch,worker,"staff-book","host")
        tid=table_ids(owner,bid)[0]["id"]
        d=(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))+timedelta(days=2)).replace(
            hour=12,minute=0,second=0,microsecond=0)
        payload={"request_id":"book-host-"+uuid.uuid4().hex,"customer_name":"Lê Hoa",
                 "phone":"0901234567","party_size":2,"start_at":d.isoformat(),
                 "duration_minutes":90,"table_id":tid,"branch_id":branch,"note":"Gần cửa"}
        booked=req(worker,"POST",f"/businesses/{bid}/reservations",payload,staff_csrf)
        assert booked.status_code==201,booked.text
        rid=booked.json()["id"]
        assert worker.get(f"/api/businesses/{bid}/reservations").status_code==200
        edit={k:v for k,v in payload.items() if k!="request_id" and k!="branch_id"}
        edit["party_size"]=3;edit["note"]="Thêm ghế";edit["customer_name"]="Lê Hoa 2"
        result=req(worker,"POST",f"/businesses/{bid}/reservations/{rid}/edit",edit,staff_csrf)
        assert result.status_code==200,result.text
        assert result.json()["party_size"]==3
        assert result.json()["branch_id"]==branch
        duplicate=req(owner,"POST",f"/businesses/{bid}/reservations",
                      {**payload,"request_id":"other-"+uuid.uuid4().hex},csrf)
        assert duplicate.status_code==409,duplicate.text
        cancelled=req(worker,"POST",f"/businesses/{bid}/reservations/{rid}/status",
                      {"status":"cancelled"},staff_csrf)
        assert cancelled.status_code==200,cancelled.text
        assert cancelled.json()["status"]=="cancelled"
        assert req(worker,"POST",f"/businesses/{bid}/reservations/{rid}/edit",
                   edit,staff_csrf).status_code==409


def test_checkin_links_confirmed_reservation_and_prevents_double_seating():
    with TestClient(app) as owner:
        csrf,bid,branch=shop(owner,"linked-checkin")
        first=table_ids(owner,bid)[0]
        rid=str(uuid.uuid4())
        arrival=datetime.now(timezone.utc)+timedelta(minutes=10)
        with SessionLocal() as db:
            db.add(IndustryWorkItem(id=rid,business_id=bid,kind="reservations",
                reference_id="checkin-"+rid[:8],title="Lịch đặt bàn",
                status="confirmed",scheduled_at=arrival,
                ends_at=arrival+timedelta(minutes=90),
                details={"branch_id":branch,"table_id":first["id"],
                         "customer_name":"Nguyễn An","phone":"0912345678",
                         "party_size":2,"note":"Gần cửa"}))
            db.commit()

        # A walk-in cannot silently occupy a confirmed reservation window.
        occupied=host_action(owner,csrf,bid,first["id"],"seat",guest_count=1)
        assert occupied.status_code==409,occupied.text
        # Identity, tenant, table, and capacity are checked on the server.
        invalid=host_action(owner,csrf,bid,first["id"],"seat",
            guest_count=2,reservation_id=str(uuid.uuid4()))
        assert invalid.status_code==409,invalid.text
        oversized=host_action(owner,csrf,bid,first["id"],"seat",
            guest_count=first["seats"]+1,reservation_id=rid)
        assert oversized.status_code==409,oversized.text

        checked=host_action(owner,csrf,bid,first["id"],"seat",guest_count=2,
            reservation_id=rid,guest_name="Nguyễn An",guest_phone="0912345678",
            note="Đã đến đủ")
        assert checked.status_code==200,checked.text
        row=next(t for t in checked.json()["tables"] if t["id"]==first["id"])
        assert row["status"]=="occupied" and row["guest_count"]==2
        assert row["guest_name"]=="Nguyễn An" and row["guest_phone"]=="0912345678"
        assert row["reservation_id"]==rid and row["seated_at"]
        assert row["revision"]==1
        with SessionLocal() as db:
            booking=db.get(IndustryWorkItem,rid)
            assert booking.status=="seated"
            audit_rows=db.scalars(select(AuditEvent).where(
                AuditEvent.business_id==bid,
                AuditEvent.action=="host.table_seat")).all()
            assert len(audit_rows)==1
        assert host_action(owner,csrf,bid,first["id"],"seat",
            revision=1,guest_count=2,reservation_id=rid).status_code==409
        released=host_action(owner,csrf,bid,first["id"],"release",revision=1)
        assert released.status_code==200
        r=next(t for t in released.json()["tables"] if t["id"]==first["id"])
        assert r["status"]=="cleaning" and r["guest_name"]==""
        assert r["guest_phone"]=="" and r["reservation_id"] is None


def test_checkin_walkin_guest_details_and_conflicting_table_revision():
    with TestClient(app) as owner:
        csrf,bid,branch=shop(owner,"walkin-checkin")
        t=table_ids(owner,bid)[0]
        bad=host_action(owner,csrf,bid,t["id"],"seat",guest_count=t["seats"]+1)
        assert bad.status_code==409
        done=host_action(owner,csrf,bid,t["id"],"seat",guest_count=1,
            guest_name="Khách A",guest_phone="0900000000",note="Ít đá")
        assert done.status_code==200,done.text
        row=next(x for x in done.json()["tables"] if x["id"]==t["id"])
        assert row["guest_count"]==1 and row["guest_name"]=="Khách A"
        assert row["reservation_id"] is None
        assert host_action(owner,csrf,bid,t["id"],"seat",revision=1,
            guest_count=1).status_code==409
        # Staff may update the seated group's details without creating an order.
        updated=host_action(owner,csrf,bid,t["id"],"update",revision=1,
            guest_count=2,guest_name="Khách B",guest_phone="0900000001")
        assert updated.status_code==200
        current=next(x for x in updated.json()["tables"] if x["id"]==t["id"])
        assert current["guest_count"]==2
