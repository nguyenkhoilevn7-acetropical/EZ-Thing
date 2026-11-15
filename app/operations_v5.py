"""EZ Thing v5 operational workflows layered on the EXISTING tenant ledger.

No carrier, SMS, Zalo, bank, card or fiscal API is called here. Unpaid deposit
requests and notification drafts are deliberately not evidence of payment/delivery.
All mutable operations use the authenticated session and CSRF middleware.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func, text, update, String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Session, Mapped, mapped_column

from .database import Base, db_session
from .main import current_user, tenant, feature, fail, audit, new_id
from .models import Branch, Business, Customer, Membership, Product, SaleOrder, SaleOrderItem, StockMovement, User, now
from .team import allow, MANAGE_ROLES
from .workflows import IndustryWorkItem

router = APIRouter(prefix="/api/businesses/{bid}/operations", tags=["EZ Thing operations v5"])
UTC = timezone.utc


class BranchBalance(Base):
    """Optional physically allocated stock; global Product.stock stays authoritative."""
    __tablename__ = "branch_stock_balances"
    __table_args__ = (UniqueConstraint("business_id","branch_id","product_id"),)
    business_id:Mapped[str]=mapped_column(ForeignKey("businesses.id",ondelete="CASCADE"),primary_key=True)
    branch_id:Mapped[str]=mapped_column(ForeignKey("branches.id",ondelete="CASCADE"),primary_key=True)
    product_id:Mapped[str]=mapped_column(ForeignKey("products.id",ondelete="CASCADE"),primary_key=True)
    quantity:Mapped[int]=mapped_column(Integer,default=0,nullable=False)


def branch_inventory_enabled(db:Session,bid:str):
    business=db.get(Business,bid)
    return bool((business.setup or {}).get("branch_inventory_enabled")) if business else False


def primary_branch(db,bid):
    row=db.scalar(select(Branch).where(Branch.business_id==bid).order_by(
        Branch.created_at,Branch.id))
    if not row:fail(422,"Doanh nghiệp chưa có chi nhánh")
    return row


def branch_stock_change(db,bid,branch_id,pid,delta):
    """Atomic branch change inside the caller's wider Product.stock transaction."""
    if not branch_inventory_enabled(db,bid):return
    if not branch_id:fail(422,"Thiếu chi nhánh khi theo dõi kho riêng")
    lock_business(db,bid,"branch-inventory")
    in_branch(db,bid,branch_id)
    if delta>=0:
        row=db.get(BranchBalance,{"business_id":bid,"branch_id":branch_id,"product_id":pid})
        if row:
            row.quantity+=delta
        else:
            db.add(BranchBalance(business_id=bid,branch_id=branch_id,product_id=pid,quantity=delta))
    else:
        changed=db.execute(update(BranchBalance).where(
            BranchBalance.business_id==bid,BranchBalance.branch_id==branch_id,
            BranchBalance.product_id==pid,
            BranchBalance.quantity>=-delta).values(quantity=BranchBalance.quantity+delta))
        if changed.rowcount!=1:
            fail(409,"Tồn kho tại chi nhánh không đủ")


class ActivateBranchInventory(BaseModel):
    confirmation:Literal["ALLOCATE_ALL_TO_PRIMARY_BRANCH"]


@router.get("/inventory")
def inventory_balances(bid:str,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,permission="products")
    enabled=branch_inventory_enabled(db,bid)
    results=[]
    if enabled:
        balances=db.scalars(select(BranchBalance).where(BranchBalance.business_id==bid)).all()
        results=[{"branch_id":x.branch_id,"product_id":x.product_id,
                  "quantity":x.quantity} for x in balances]
    return {"enabled":enabled,"balances":results,
            "activation_policy":"All existing tracked Product.stock is initially allocated to primary branch; explicit owner consent required."}


@router.post("/inventory/activate")
def activate_branch_inventory(bid:str,body:ActivateBranchInventory,
                              user=Depends(current_user),db:Session=Depends(db_session)):
    b=scope(db,bid,user,permission="multi_branch")
    allow(db,bid,user,{"owner"})
    lock_business(db,bid,"branch-inventory")
    b=db.scalar(select(Business).where(Business.id==bid).with_for_update())
    if branch_inventory_enabled(db,bid):
        return {"enabled":True,"message":"Kho chi nhánh đã được kích hoạt"}
    main=primary_branch(db,bid)
    products=db.scalars(select(Product).where(
        Product.business_id==bid,Product.track_stock.is_(True)).with_for_update()).all()
    for p in products:
        db.add(BranchBalance(business_id=bid,branch_id=main.id,
                             product_id=p.id,quantity=p.stock))
    settings=dict(b.setup or {})
    settings["branch_inventory_enabled"]=True
    b.setup=settings
    audit(db,bid,user[0].id,"stock.branch_inventory_activated",
          {"initial_branch":main.id,"product_count":len(products)})
    db.commit()
    return {"enabled":True,"initial_branch_id":main.id,"product_count":len(products)}


def new_product_branch_balance(db:Session,bid:str,p:Product):
    if branch_inventory_enabled(db,bid) and p.track_stock:
        branch=primary_branch(db,bid)
        db.add(BranchBalance(business_id=bid,branch_id=branch.id,
                             product_id=p.id,quantity=p.stock))



def lock_business(db: Session, bid: str, subject: str = "operation"):
    """Serialize inventory/loyalty operations across workers on PostgreSQL."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        key = int.from_bytes(hashlib.sha256(f"v5:{bid}:{subject}".encode()).digest()[:8],
                             "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def can_manage(db, bid, user):
    return allow(db, bid, user, MANAGE_ROLES)


def scope(db, bid, user, industry=None, permission=None, manage=False):
    b = tenant(bid, user, db)
    if industry and b.industry != industry:
        fail(404, "Chức năng không áp dụng cho ngành này")
    if permission:
        feature(b, permission)
    if manage:
        can_manage(db, bid, user)
    return b


def in_branch(db, bid, branch_id):
    branch = db.scalar(select(Branch).where(Branch.business_id == bid, Branch.id == branch_id))
    if not branch:
        fail(404, "Chi nhánh không tồn tại trong doanh nghiệp")
    return branch


def item_out(row: IndustryWorkItem):
    return {"id": row.id, "kind": row.kind, "status": row.status,
            "title": row.title, "details": row.details or {},
            "customer_id": row.customer_id, "product_id": row.product_id,
            "reference_id": row.reference_id, "assignee": row.assignee,
            "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
            "ends_at": row.ends_at.isoformat() if row.ends_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None}


def rows(db, bid, kind, limit=100):
    return db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid, IndustryWorkItem.kind == kind)
        .order_by(IndustryWorkItem.created_at.desc(), IndustryWorkItem.id.desc())
        .limit(limit)).all()


def store(db, bid, user, row, action, payload=None):
    db.add(row)
    audit(db, bid, user[0].id, action, payload or {"id": row.id})
    db.commit()
    return item_out(row)


class WaitlistAdd(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=8, max_length=25)
    party_size: int = Field(ge=1, le=20)
    branch_id: str
    note: str = Field(default="", max_length=240)


class WaitlistStatus(BaseModel):
    status: Literal["ready", "seated", "cancelled"]


@router.get("/waitlist")
def waitlist(bid: str, user=Depends(current_user), db: Session=Depends(db_session)):
    scope(db, bid, user, "fnb", "tables")
    return [item_out(x) for x in rows(db, bid, "waitlist", 150)]


@router.post("/waitlist", status_code=201)
def join_waitlist(bid: str, body: WaitlistAdd, user=Depends(current_user),
                  db: Session=Depends(db_session)):
    scope(db, bid, user, "fnb", "tables")
    in_branch(db, bid, body.branch_id)
    lock_business(db, bid, "waitlist")
    ref = hashlib.sha256((bid + "|" + body.request_id).encode()).hexdigest()[:36]
    fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    existing = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid, IndustryWorkItem.kind == "waitlist",
        IndustryWorkItem.reference_id == ref))
    if existing:
        if (existing.details or {}).get("fingerprint") != fingerprint:
            fail(409, "Mã yêu cầu đã được sử dụng")
        return item_out(existing)
    count=db.scalar(select(func.count()).select_from(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="waitlist",
        IndustryWorkItem.status.in_(("waiting","ready")))) or 0
    if count>=200:fail(429,"Danh sách chờ đã đạt giới hạn")
    row = IndustryWorkItem(id=new_id(), business_id=bid, kind="waitlist",
        reference_id=ref, title="Chờ bàn • " + body.name.strip(), status="waiting",
        details={"name":body.name.strip(), "phone":body.phone.strip(),
                 "party_size":body.party_size, "branch_id":body.branch_id,
                 "note":body.note.strip(), "fingerprint":fingerprint})
    return store(db, bid, user, row, "waitlist.joined")


@router.post("/waitlist/{item_id}/status")
def progress_waitlist(bid: str, item_id: str, body: WaitlistStatus,
                      user=Depends(current_user), db: Session=Depends(db_session)):
    scope(db, bid, user, "fnb", "tables")
    lock_business(db, bid, "waitlist")
    row = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid, IndustryWorkItem.kind == "waitlist",
        IndustryWorkItem.id == item_id).with_for_update())
    if not row: fail(404, "Không tìm thấy yêu cầu chờ bàn")
    allowed = {"waiting": {"ready", "cancelled"},
               "ready": {"seated", "cancelled"}}
    if row.status == body.status:
        return item_out(row)
    if body.status not in allowed.get(row.status, set()):
        fail(409, "Trạng thái danh sách chờ không hợp lệ")
    # 'ready' is a host workflow, NOT an outbound notification or table hold.
    # Seating requires actual free capacity now for the requested branch.
    if body.status == "seated":
        from .reservations import free_tables, lock_capacity
        lock_capacity(db, bid)
        from .models import DiningTable
        candidates = db.scalars(select(DiningTable).where(
            DiningTable.business_id == bid,
            DiningTable.branch_id == row.details["branch_id"],
            DiningTable.seats >= row.details["party_size"])).all()
        at = now()
        free = free_tables(db, bid, at, at + timedelta(minutes=90),
                           row.details["party_size"], allowed_ids={x.id for x in candidates})
        if not free:
            fail(409, "Không có bàn trống phù hợp để nhận khách")
        # A seat is not a future reservation: allocate in the floorplan workflow
        # only after a host has confirmed the physical table.
        details = dict(row.details or {})
        details["table_id"] = free[0].id
        details["table_label"] = free[0].label
        row.details = details
        row.scheduled_at = at
        row.ends_at = at + timedelta(minutes=90)
    row.status = body.status
    audit(db, bid, user[0].id, "waitlist.status", {"id":item_id,"status":body.status})
    db.commit()
    return item_out(row)


class ShiftCreate(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    branch_id: str
    employee_id: str
    start_at: datetime
    end_at: datetime
    note: str = Field(default="", max_length=240)

    @field_validator("start_at", "end_at")
    @classmethod
    def tz_required(cls, v):
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("Ca làm cần múi giờ")
        return v


@router.get("/staff")
def staff_for_shift(bid:str,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,manage=True)
    return [{"id":u.id,"name":u.name,"role":m.role} for m,u in db.execute(
        select(Membership,User).join(User,Membership.user_id==User.id).where(
            Membership.business_id==bid).order_by(User.name))]


@router.get("/shifts")
def list_shifts(bid: str, user=Depends(current_user), db: Session=Depends(db_session)):
    scope(db, bid, user)
    can_manage(db, bid, user)
    return [item_out(x) for x in rows(db, bid, "staff_shift", 150)]


@router.post("/shifts", status_code=201)
def create_shift(bid: str, body: ShiftCreate, user=Depends(current_user),
                 db: Session=Depends(db_session)):
    scope(db, bid, user, manage=True)
    in_branch(db, bid, body.branch_id)
    member = db.scalar(select(Membership).where(
        Membership.business_id == bid, Membership.user_id == body.employee_id))
    worker = db.get(User, body.employee_id) if member else None
    if not worker:
        fail(404, "Nhân viên không thuộc doanh nghiệp")
    start, end = body.start_at.astimezone(UTC), body.end_at.astimezone(UTC)
    if not start < end or end - start > timedelta(hours=16):
        fail(422, "Ca làm phải từ 1 phút đến 16 giờ")
    if start < now() - timedelta(days=31) or start > now() + timedelta(days=90):
        fail(422, "Ngày ca làm không nằm trong phạm vi quản lý")
    lock_business(db, bid, "shift:"+body.employee_id)
    ref = hashlib.sha256((bid+"|shift|"+body.request_id).encode()).hexdigest()[:36]
    fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    old = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="staff_shift",
        IndustryWorkItem.reference_id==ref))
    if old:
        if old.details.get("fingerprint") != fingerprint: fail(409,"Mã ca đã sử dụng")
        return item_out(old)
    conflicts = db.scalar(select(IndustryWorkItem.id).where(
        IndustryWorkItem.business_id==bid, IndustryWorkItem.kind=="staff_shift",
        IndustryWorkItem.assignee==body.employee_id,
        IndustryWorkItem.status=="scheduled",
        IndustryWorkItem.scheduled_at<end, IndustryWorkItem.ends_at>start))
    if conflicts: fail(409, "Nhân viên đã có ca trùng giờ")
    row=IndustryWorkItem(id=new_id(),business_id=bid,kind="staff_shift",
        reference_id=ref,assignee=body.employee_id,title=worker.name,
        scheduled_at=start,ends_at=end,status="scheduled",
        details={"branch_id":body.branch_id,"note":body.note,
                 "fingerprint":fingerprint})
    return store(db,bid,user,row,"team.shift_created")


@router.post("/shifts/{item_id}/cancel")
def cancel_shift(bid:str,item_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,manage=True)
    row=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="staff_shift",
        IndustryWorkItem.id==item_id).with_for_update())
    if not row:fail(404,"Không tìm thấy ca làm")
    if row.status=="cancelled":return item_out(row)
    row.status="cancelled"
    audit(db,bid,user[0].id,"team.shift_cancelled",{"id":row.id})
    db.commit()
    return item_out(row)


class RecipeIngredient(BaseModel):
    product_id: str
    quantity: int=Field(ge=1,le=100000)


class RecipeUpdate(BaseModel):
    ingredients: list[RecipeIngredient] = Field(min_length=1,max_length=30)


@router.get("/recipes")
def list_recipes(bid:str,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,"fnb","products")
    return [item_out(x) for x in rows(db,bid,"recipe",200)]


@router.put("/recipes/{finished_id}")
def save_recipe(bid:str,finished_id:str,body:RecipeUpdate,
                user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,"fnb","products",True)
    main=db.scalar(select(Product).where(Product.business_id==bid,Product.id==finished_id))
    if not main:fail(404,"Sản phẩm bán không hợp lệ")
    if main.track_stock:
        fail(422,"Món có công thức phải tắt theo dõi tồn thành phẩm, tránh trừ kho hai lần")
    ids=[line.product_id for line in body.ingredients]
    if len(ids)!=len(set(ids)) or finished_id in ids:
        fail(422,"Không được lặp nguyên liệu hoặc dùng chính món làm nguyên liệu")
    products=db.scalars(select(Product).where(
        Product.business_id==bid,Product.id.in_(ids),Product.track_stock.is_(True))).all()
    if len(products)!=len(ids):
        fail(422,"Nguyên liệu phải là sản phẩm trong kho của doanh nghiệp")
    lock_business(db,bid,"recipe:"+finished_id)
    row=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="recipe",
        IndustryWorkItem.reference_id==finished_id).with_for_update())
    details={"ingredients":[x.model_dump() for x in body.ingredients]}
    if row:
        row.details=details
        row.status="active"
        audit(db,bid,user[0].id,"recipe.updated",{"product_id":finished_id})
        db.commit()
        return item_out(row)
    row=IndustryWorkItem(id=new_id(),business_id=bid,kind="recipe",
        reference_id=finished_id,product_id=finished_id,
        title="Định lượng • "+main.name,status="active",details=details)
    return store(db,bid,user,row,"recipe.created")


def consumption_for_sale(db:Session,bid:str,quantities:dict[str,int]):
    """Aggregate the exact inventory consumption for recipe + ordinary product.

    Call from ALL order acceptance paths before writing stock or movement rows.
    Snapshot as stock_movements makes later order cancellation reverse precisely.
    """
    used=defaultdict(int)
    for pid,qty in quantities.items():
        product=db.scalar(select(Product).where(Product.business_id==bid,Product.id==pid))
        recipe=db.scalar(select(IndustryWorkItem).where(
            IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="recipe",
            IndustryWorkItem.reference_id==pid,IndustryWorkItem.status=="active"))
        if recipe:
            if product.track_stock:
                fail(409,"Món có định lượng không được bật tồn thành phẩm")
            for line in recipe.details.get("ingredients",[]):
                used[line["product_id"]]+=int(line["quantity"])*qty
        elif product.track_stock:
            used[pid]+=qty
    return used


def consume_stock_for_sale(db:Session,bid:str,oid:str,quantities:dict[str,int],branch_id:str|None=None):
    used=consumption_for_sale(db,bid,quantities)
    for pid,qty in sorted(used.items()):
        changed=db.execute(update(Product).where(
            Product.id==pid,Product.business_id==bid,Product.track_stock.is_(True),
            Product.stock>=qty).values(stock=Product.stock-qty))
        if changed.rowcount!=1:
            fail(409,"Không đủ nguyên liệu hoặc tồn kho cho đơn hàng")
        branch_stock_change(db,bid,branch_id,pid,-qty)
        db.add(StockMovement(id=new_id(),business_id=bid,product_id=pid,
            delta=-qty,reason="sale",ref=oid))
    return used


class TransferCreate(BaseModel):
    request_id: str = Field(min_length=8,max_length=80,pattern=r"^[a-zA-Z0-9_-]+$")
    product_id: str
    from_branch_id: str
    to_branch_id: str
    quantity: int = Field(ge=1, le=1000000)
    note: str = Field(default="", max_length=240)


@router.get("/transfers")
def list_transfers(bid:str,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,permission="products")
    return [item_out(x) for x in rows(db,bid,"transfer_request",150)]


@router.post("/transfers",status_code=201)
def create_transfer(bid:str,body:TransferCreate,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,permission="products",manage=True)
    if body.from_branch_id==body.to_branch_id:fail(422,"Kho nguồn và kho đích phải khác nhau")
    in_branch(db,bid,body.from_branch_id)
    in_branch(db,bid,body.to_branch_id)
    product=db.scalar(select(Product).where(
        Product.id==body.product_id,Product.business_id==bid,
        Product.track_stock.is_(True)))
    if not product:fail(404,"Không tìm thấy hàng tồn kho")
    # Product.stock is business-wide; no false per-branch balances or global
    # movement are recorded until the independent location-ledger migration.
    lock_business(db,bid,"transfers")
    ref=hashlib.sha256((bid+"|transfer|"+body.request_id).encode()).hexdigest()[:36]
    fp=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    old=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="transfer_request",
        IndustryWorkItem.reference_id==ref))
    if old:
        if old.details.get("fingerprint")!=fp:fail(409,"Mã chuyển kho đã sử dụng")
        return item_out(old)
    row=IndustryWorkItem(id=new_id(),business_id=bid,kind="transfer_request",
        reference_id=ref,product_id=product.id,title="Chuyển kho • "+product.name,status="requested",
        details={**body.model_dump(), "fingerprint":fp,
                 "inventory_applied":False})
    return store(db,bid,user,row,"stock.transfer_requested")


class TransferStatus(BaseModel):
    status:Literal["approved","received","cancelled"]


@router.post("/transfers/{item_id}/status")
def transfer_status(bid:str,item_id:str,body:TransferStatus,
                    user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,permission="products",manage=True)
    row=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="transfer_request",
        IndustryWorkItem.id==item_id).with_for_update())
    if not row:fail(404,"Không tìm thấy yêu cầu chuyển kho")
    if row.status==body.status:return item_out(row)
    allowed={"requested":{"approved","cancelled"},"approved":{"received","cancelled"}}
    if body.status not in allowed.get(row.status,set()):
        fail(409,"Trạng thái yêu cầu không hợp lệ")
    if body.status=="received" and branch_inventory_enabled(db,bid):
        lock_business(db,bid,"branch-inventory")
        props=row.details or {}
        src=props["from_branch_id"]
        dst=props["to_branch_id"]
        qty=int(props["quantity"])
        branch_stock_change(db,bid,src,row.product_id,-qty)
        branch_stock_change(db,bid,dst,row.product_id,qty)
        details=dict(props)
        details["inventory_applied"]=True
        row.details=details
    row.status=body.status
    audit(db,bid,user[0].id,"stock.transfer_status",{"id":row.id,"status":body.status,
        "inventory_applied":(row.details or {}).get("inventory_applied",False)})
    db.commit()
    return item_out(row)


class DeliveryEvent(BaseModel):
    event: Literal["picked_up","in_transit","delayed","delivery_attempt","delivered","failed"]
    note: str = Field(default="", max_length=240)
    tracking_number: str = Field(default="", max_length=100)


@router.post("/deliveries/{item_id}/events")
def delivery_event(bid:str,item_id:str,body:DeliveryEvent,
                   user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,"online","fulfillment")
    can_manage(db,bid,user)
    row=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid, IndustryWorkItem.kind=="delivery",
        IndustryWorkItem.id==item_id).with_for_update())
    if not row:fail(404,"Không tìm thấy phiếu giao hàng")
    if row.status=="cancelled":fail(409,"Đơn đã hủy")
    if body.event=="delivered" and row.status!="delivered":
        fail(409,"Cần hoàn tất các bước vận hành giao hàng trước")
    details=dict(row.details or {})
    events=list(details.get("tracking_events",[]))
    events.append({"event":body.event,"note":body.note.strip(),
                   "at":now().isoformat(),"actor_id":user[0].id})
    details["tracking_events"]=events[-50:]
    if body.tracking_number:
        details["tracking_number"]=body.tracking_number.strip()
    row.details=details
    audit(db,bid,user[0].id,"delivery.tracking",{"id":row.id,"event":body.event})
    db.commit()
    return item_out(row)


def loyalty_earn_on_paid(db:Session,bid:str,order:SaleOrder):
    """Called inside the order-paid transaction; one award per paid order."""
    if not order.customer_id or not order.total_vnd: return
    ref=order.id
    old=db.scalar(select(IndustryWorkItem.id).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="loyalty",
        IndustryWorkItem.reference_id==ref))
    if old:return
    points=order.total_vnd//10000  # 1 point / 10,000 VND; no cash value.
    if points<=0:return
    db.add(IndustryWorkItem(id=new_id(),business_id=bid,kind="loyalty",
        reference_id=ref,customer_id=order.customer_id,status="earned",
        title="Tích điểm đơn "+order.id[:8],
        details={"points":points,"sale_order_id":order.id,
                 "cash_value_vnd":0}))


@router.get("/loyalty")
def loyalty(bid:str,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,permission="orders")
    can_manage(db,bid,user)
    ledger=db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="loyalty")
        .order_by(IndustryWorkItem.created_at.desc(),IndustryWorkItem.id.desc())).all()
    balances=defaultdict(int)
    for item in ledger:
        if item.customer_id:balances[item.customer_id]+=int(item.details.get("points",0))
    return {"balances":[{"customer_id":cid,"points":value} for cid,value in balances.items()],
            "transactions":[item_out(x) for x in ledger[:100]],
            "policy":"1 point per 10,000 VND paid; no cash value; manual rewards only"}


class RedeemPoints(BaseModel):
    request_id:str=Field(min_length=8,max_length=80,pattern=r"^[A-Za-z0-9_-]+$")
    customer_id:str
    points:int=Field(ge=1,le=100000)
    note:str=Field(min_length=4,max_length=200)


@router.post("/loyalty/redeem",status_code=201)
def redeem_points(bid:str,body:RedeemPoints,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,permission="orders",manage=True)
    customer=db.scalar(select(Customer).where(Customer.business_id==bid,Customer.id==body.customer_id))
    if not customer:fail(404,"Khách hàng không tồn tại")
    lock_business(db,bid,"loyalty:"+body.customer_id)
    ref=hashlib.sha256((bid+"|loyalty|"+body.request_id).encode()).hexdigest()[:36]
    fp=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    old=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="loyalty",
        IndustryWorkItem.reference_id==ref))
    if old:
        if old.details.get("fingerprint")!=fp:fail(409,"Mã đổi điểm đã sử dụng")
        return item_out(old)
    total=db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="loyalty",
        IndustryWorkItem.customer_id==body.customer_id)).all()
    balance=sum(int(x.details.get("points",0)) for x in total)
    if balance<body.points:fail(409,"Khách không đủ điểm để đổi thưởng")
    row=IndustryWorkItem(id=new_id(),business_id=bid,kind="loyalty",
        reference_id=ref,customer_id=body.customer_id,status="redeemed",
        title="Đổi thưởng • "+customer.name,
        details={"points":-body.points,"note":body.note.strip(),
                 "fingerprint":fp,"cash_value_vnd":0})
    return store(db,bid,user,row,"loyalty.redeemed")


class ExpenseAdd(BaseModel):
    request_id:str=Field(min_length=8,max_length=80,pattern=r"^[A-Za-z0-9_-]+$")
    amount_vnd:int=Field(gt=0,le=100000000000)
    category:Literal["rent","staff","utilities","ingredients","marketing","other"]
    note:str=Field(min_length=3,max_length=200)


@router.post("/expenses",status_code=201)
def add_expense(bid:str,body:ExpenseAdd,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,permission="insights",manage=True)
    lock_business(db,bid,"expenses")
    ref=hashlib.sha256((bid+"|expense|"+body.request_id).encode()).hexdigest()[:36]
    fp=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    old=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="expense",
        IndustryWorkItem.reference_id==ref))
    if old:
        if old.details.get("fingerprint")!=fp:fail(409,"Mã chi phí đã sử dụng")
        return item_out(old)
    row=IndustryWorkItem(id=new_id(),business_id=bid,kind="expense",
        reference_id=ref,status="posted",title=body.note.strip(),
        details={**body.model_dump(),"fingerprint":fp})
    return store(db,bid,user,row,"finance.expense_created")


@router.get("/finance")
def financial_report(bid:str,start:date|None=None,end:date|None=None,
                     user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,permission="insights",manage=True)
    begin=datetime.combine(start or (now().date()-timedelta(days=30)), datetime.min.time(), tzinfo=UTC)
    finish=datetime.combine((end or now().date())+timedelta(days=1),datetime.min.time(),tzinfo=UTC)
    if finish<=begin or finish-begin>timedelta(days=366):
        fail(422,"Khoảng báo cáo không hợp lệ (tối đa 366 ngày)")
    orders=db.scalars(select(SaleOrder).where(
        SaleOrder.business_id==bid,SaleOrder.status=="paid",
        SaleOrder.paid_at>=begin,SaleOrder.paid_at<finish)).all()
    ids=[x.id for x in orders]
    total_revenue=sum(x.total_vnd for x in orders)
    # Current-cost estimate from exact sale stock movements, including recipe
    # ingredients. Historic unit cost is not snapshotted by the pilot ledger.
    estimated_cogs=0
    if ids:
        for movement,product in db.execute(select(StockMovement,Product).join(
            Product,(Product.id==StockMovement.product_id)&(Product.business_id==bid))
            .where(StockMovement.business_id==bid,StockMovement.reason=="sale",
                   StockMovement.delta<0,StockMovement.ref.in_(ids))):
            estimated_cogs+=(-movement.delta)*product.cost_vnd
    expenses=[x for x in db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="expense",
        IndustryWorkItem.created_at>=begin,IndustryWorkItem.created_at<finish)).all()]
    expense_total=sum(int(x.details.get("amount_vnd",0)) for x in expenses)
    return {"period":{"start":begin.date().isoformat(),"end":(finish-timedelta(days=1)).date().isoformat()},
            "paid_order_count":len(orders),"revenue_vnd":total_revenue,
            "estimated_cogs_vnd":estimated_cogs,"operating_expenses_vnd":expense_total,
            "estimated_profit_vnd":total_revenue-estimated_cogs-expense_total,
            "expenses":[item_out(x) for x in expenses],
            "disclaimer":"COGS uses current product costs, not historical inventory valuation; do not use as statutory financial statements."}


class MessageDraft(BaseModel):
    request_id:str=Field(min_length=8,max_length=80,pattern=r"^[A-Za-z0-9_-]+$")
    channel:Literal["email","zalo"]
    recipient:str=Field(min_length=5,max_length=180)
    message:str=Field(min_length=5,max_length=600)


@router.get("/notifications")
def notification_drafts(bid:str,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,manage=True)
    return [item_out(x) for x in rows(db,bid,"message_draft",100)]


@router.post("/notifications",status_code=201)
def create_notification_draft(bid:str,body:MessageDraft,user=Depends(current_user),
                              db:Session=Depends(db_session)):
    scope(db,bid,user,manage=True)
    if body.channel=="email" and ("@" not in body.recipient or " " in body.recipient):
        fail(422,"Email người nhận không hợp lệ")
    lock_business(db,bid,"notifications")
    ref=hashlib.sha256((bid+"|message|"+body.request_id).encode()).hexdigest()[:36]
    fp=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    old=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="message_draft",
        IndustryWorkItem.reference_id==ref))
    if old:
        if old.details.get("fingerprint")!=fp:fail(409,"Mã thông báo đã sử dụng")
        return item_out(old)
    row=IndustryWorkItem(id=new_id(),business_id=bid,kind="message_draft",
        reference_id=ref,status="draft",title="Nháp "+body.channel.upper(),
        details={**body.model_dump(),"fingerprint":fp,"sent":False})
    return store(db,bid,user,row,"notification.drafted")


class DepositRequest(BaseModel):
    request_id:str=Field(min_length=8,max_length=80,pattern=r"^[A-Za-z0-9_-]+$")
    reservation_id:str
    amount_vnd:int=Field(gt=0,le=50000000)
    note:str=Field(default="",max_length=200)


@router.get("/deposits")
def deposit_requests(bid:str,user=Depends(current_user),db:Session=Depends(db_session)):
    scope(db,bid,user,"fnb","tables",True)
    return [item_out(x) for x in rows(db,bid,"booking_deposit",100)]


@router.post("/deposits",status_code=201)
def deposit_request(bid:str,body:DepositRequest,user=Depends(current_user),
                    db:Session=Depends(db_session)):
    scope(db,bid,user,"fnb","tables",True)
    reservation=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="reservations",
        IndustryWorkItem.id==body.reservation_id))
    if not reservation:fail(404,"Không tìm thấy lịch đặt bàn")
    if reservation.status in ("cancelled","no_show","completed"):
        fail(409,"Không nhận cọc cho lịch đã kết thúc")
    lock_business(db,bid,"deposit")
    ref=body.reservation_id
    existing=db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id==bid,IndustryWorkItem.kind=="booking_deposit",
        IndustryWorkItem.reference_id==ref))
    if existing:
        if existing.details.get("amount_vnd")!=body.amount_vnd:
            fail(409,"Lịch đã có yêu cầu cọc với số tiền khác")
        return item_out(existing)
    row=IndustryWorkItem(id=new_id(),business_id=bid,kind="booking_deposit",
        reference_id=ref,status="pending_gateway",title="Yêu cầu cọc • "+reservation.title,
        details={"amount_vnd":body.amount_vnd,"note":body.note,
                 "paid":False,"gateway_reference":None,"collection_enabled":False})
    return store(db,bid,user,row,"deposit.requested")


@router.get("/sync")
def operational_sync(bid:str,user=Depends(current_user),db:Session=Depends(db_session)):
    """Lightweight multi-device polling; never writes or exposes private detail."""
    scope(db,bid,user)
    counts={}
    for kind in ("reservations","waitlist","delivery","appointments","staff_shift"):
        counts[kind]=int(db.scalar(select(func.count()).select_from(IndustryWorkItem).where(
            IndustryWorkItem.business_id==bid,IndustryWorkItem.kind==kind,
            IndustryWorkItem.status.not_in(("cancelled","completed","delivered","no_show")))) or 0)
    revision,last_count=db.execute(select(
        func.max(IndustryWorkItem.updated_at),func.count(IndustryWorkItem.id)
    ).where(IndustryWorkItem.business_id==bid)).one()
    order_revision,paid_revision,order_count=db.execute(select(
        func.max(SaleOrder.created_at),func.max(SaleOrder.paid_at),func.count(SaleOrder.id)
    ).where(SaleOrder.business_id==bid)).one()
    stock_revision,stock_count=db.execute(select(
        func.max(StockMovement.created_at),func.count(StockMovement.id)
    ).where(StockMovement.business_id==bid)).one()
    version=hashlib.sha256(
        f"{revision or ''}:{last_count}:{order_revision}:{paid_revision}:{order_count}:{stock_revision}:{stock_count}".encode()
    ).hexdigest()[:16]
    return {"server_time":now().isoformat(),"active_counts":counts,
            "version":version,"poll_after_seconds":15,"transport":"polling"}
