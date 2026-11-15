"""Public order requests for real tenant shops, merchant-approved only.

Guest submissions NEVER charge customers, create paid orders or reserve stock.
An owner/manager must accept after reconfirming the original server price and
available stock. Acceptance is one DB transaction that creates the ordinary
SaleOrder, customer and stock ledger, plus an optional kitchen/delivery ticket.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import Customer, LoginFailure, Product, SaleOrder, SaleOrderItem, StockMovement, now
from .main import audit, branch_for, current_user, feature, tenant
from .published_storefront import valid_public
from .team import allow, MANAGE_ROLES
from .workflows import IndustryWorkItem

router=APIRouter(tags=["Public order requests"])


class PublicOrderRequest(Base):
    __tablename__="public_order_requests"
    __table_args__=(
        UniqueConstraint("business_id","request_hash",name="uq_public_order_tenant_request"),
        Index("ix_public_orders_business_status", "business_id","status","created_at"),
    )
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    business_id: Mapped[str]=mapped_column(
        ForeignKey("businesses.id",ondelete="CASCADE"),index=True)
    request_hash: Mapped[str]=mapped_column(String(64))
    fingerprint: Mapped[str]=mapped_column(String(64))
    customer_name: Mapped[str]=mapped_column(String(100))
    phone: Mapped[str]=mapped_column(String(30))
    address: Mapped[str]=mapped_column(String(300),default="")
    note: Mapped[str]=mapped_column(String(180),default="")
    lines: Mapped[list]=mapped_column(JSON,default=list)
    total_vnd: Mapped[int]=mapped_column(BigInteger)
    status: Mapped[str]=mapped_column(String(20),default="pending")
    sale_order_id: Mapped[str | None]=mapped_column(
        ForeignKey("sale_orders.id"),nullable=True)
    review_reason: Mapped[str]=mapped_column(String(180),default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)


class PublicLine(BaseModel):
    product_id: str=Field(min_length=1,max_length=36)
    quantity: int=Field(ge=1,le=15)
    selected_options: list[str]=Field(default_factory=list,max_length=30)


class GuestOrder(BaseModel):
    request_id: str=Field(min_length=12,max_length=80)
    customer_name: str=Field(min_length=2,max_length=100)
    phone: str=Field(min_length=7,max_length=30)
    address: str=Field(default="",max_length=300)
    note: str=Field(default="",max_length=180)
    lines: list[PublicLine]=Field(min_length=1,max_length=15)


class ReviewOrder(BaseModel):
    action: Literal["accept","reject"]
    reason: str=Field(default="",max_length=180)


def reject(status: int, message: str):
    raise HTTPException(status, message)


def stored(row: PublicOrderRequest, private: bool = False):
    out={"id":row.id,"status":row.status,"total_vnd":row.total_vnd,
         "items":[{"product_id":x["product_id"],"name":x["name"],"quantity":x["quantity"],
                   "unit_price_vnd":x["unit_price_vnd"],
                   "modifiers":x.get("modifiers",[])} for x in row.lines],
         "created_at":row.created_at.isoformat()}
    if private:
        out.update({"customer_name":row.customer_name,"phone":row.phone,"address":row.address,
                    "note":row.note,"sale_order_id":row.sale_order_id,
                    "review_reason":row.review_reason})
    return out


def valid_origin(request: Request):
    origin=request.headers.get("origin")
    if not origin:
        return
    allowed={str(request.base_url).rstrip("/")}
    canonical=os.getenv("EZ_THING_PUBLIC_BASE_URL","").strip().rstrip("/")
    if canonical.startswith("https://") and "/" not in canonical[8:]:
        allowed.add(canonical)
    if origin not in allowed:
        reject(403,"Yêu cầu từ nguồn không hợp lệ")


def limit_public_request(db: Session, bid: str, phone: str, request: Request):
    """Database-shared throttling: 5 new requests/phone/day; 80/peer/day."""
    salt=os.getenv("EZ_THING_RATE_LIMIT_SALT","ezthing-pilot-v1")
    peer=request.client.host if request.client else "unknown"
    checks=(("phone",phone,5),("peer",peer,80))
    date=now()
    for category, identity, max_count in checks:
        key=hashlib.sha256((salt+"|guest-order|"+bid+"|"+category+"|"+identity).encode()).hexdigest()
        row=db.scalar(select(LoginFailure).where(
            LoginFailure.identity_hash==key).with_for_update())
        if row is None:
            row=LoginFailure(identity_hash=key,failures=0,window_started_at=date)
            db.add(row)
        start=row.window_started_at
        if start.tzinfo is None:
            start=start.replace(tzinfo=timezone.utc)
        if start < date-timedelta(days=1):
            row.failures=0
            row.window_started_at=date
        if row.failures>=max_count:
            reject(429,"Đã đạt giới hạn yêu cầu đặt hàng, vui lòng liên hệ cửa hàng")
        row.failures+=1


@router.post("/api/public/shops/{slug}/order-requests",status_code=201)
def create_guest_order(slug: str, body: GuestOrder, request: Request,
                       db: Session=Depends(db_session)):
    business=valid_public(db,slug)
    if business.industry not in ("online","retail","fnb"):
        reject(404,"Ngành dịch vụ sử dụng chức năng đặt lịch")
    valid_origin(request)
    if business.industry=="online" and len(body.address.strip())<8:
        reject(422,"Đơn hàng online cần địa chỉ nhận hàng")
    quantities=defaultdict(int)
    for line in body.lines:
        quantities[line.product_id]+=line.quantity
        if quantities[line.product_id]>15:
            reject(422,"Số lượng một mặt hàng vượt giới hạn")
    fingerprint=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    request_hash=hashlib.sha256((business.id+"|public-order|"+body.request_id).encode()).hexdigest()
    old=db.scalar(select(PublicOrderRequest).where(
        PublicOrderRequest.business_id==business.id,
        PublicOrderRequest.request_hash==request_hash))
    if old:
        if old.fingerprint!=fingerprint:
            reject(409,"Mã yêu cầu đã dùng cho giỏ hàng khác")
        return stored(old)
    # Do not retain rejected requests as stock reservations.
    product_rows=db.scalars(select(Product).where(
        Product.business_id==business.id,
        Product.id.in_(list(quantities)),Product.active.is_(True))).all()
    products={p.id:p for p in product_rows}
    if len(products)!=len(quantities):
        reject(404,"Một sản phẩm không tồn tại hoặc đã ngừng kinh doanh")
    for pid,qty in quantities.items():
        p=products[pid]
        if p.track_stock and p.stock<qty:
            reject(409,"Một sản phẩm đã tạm hết hàng")
    from .modifiers import price_line
    lines = []
    extra_stock = defaultdict(int)
    for entry in body.lines:
        p = products[entry.product_id]
        unit, selections, extras = price_line(db, business.id, p, entry.selected_options)
        lines.append({"product_id":p.id, "name":p.name, "quantity":entry.quantity,
                      "unit_price_vnd":unit, "selected_options":entry.selected_options,
                      "modifiers":selections})
        for stock_id, amount in extras.items():
            extra_stock[stock_id] += amount * entry.quantity
    for stock_id, amount in extra_stock.items():
        stock = db.scalar(select(Product).where(
            Product.business_id==business.id, Product.id==stock_id))
        if not stock or stock.stock < amount:
            reject(409, "Topping đã tạm hết hàng")
    total=sum(x["unit_price_vnd"]*x["quantity"] for x in lines)
    if total>50_000_000:
        reject(422,"Giá trị yêu cầu vượt giới hạn của website")
    outstanding=db.scalar(select(func.count(PublicOrderRequest.id)).where(
        PublicOrderRequest.business_id==business.id,
        PublicOrderRequest.phone==body.phone.strip(),
        PublicOrderRequest.status=="pending"))
    if outstanding>=2:
        reject(429,"Bạn đang có yêu cầu chưa được cửa hàng xác nhận")
    limit_public_request(db,business.id,body.phone.strip(),request)
    item=PublicOrderRequest(
        id=str(uuid.uuid4()),business_id=business.id,request_hash=request_hash,
        fingerprint=fingerprint,customer_name=body.customer_name.strip(),
        phone=body.phone.strip(),address=body.address.strip(),note=body.note.strip(),
        lines=lines,total_vnd=total,status="pending",
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent idempotency keys never create a second order or stock write.
        previous=db.scalar(select(PublicOrderRequest).where(
            PublicOrderRequest.business_id==business.id,
            PublicOrderRequest.request_hash==request_hash))
        if previous and previous.fingerprint==fingerprint:
            return stored(previous)
        reject(409,"Yêu cầu trùng hoặc gửi quá nhanh, vui lòng thử lại")
    return stored(item)


@router.get("/api/businesses/{bid}/order-requests")
def merchant_order_requests(bid: str, user=Depends(current_user), db: Session=Depends(db_session)):
    tenant(bid,user,db)
    allow(db,bid,user,MANAGE_ROLES)
    rows=db.scalars(select(PublicOrderRequest).where(
        PublicOrderRequest.business_id==bid)
        .order_by(PublicOrderRequest.created_at.desc()).limit(100)).all()
    return [stored(x,private=True) for x in rows]


@router.post("/api/businesses/{bid}/order-requests/{rid}/review")
def review_request(bid: str,rid: str,body: ReviewOrder,
                   user=Depends(current_user),db: Session=Depends(db_session)):
    b=tenant(bid,user,db)
    feature(b,"orders")
    allow(db,bid,user,MANAGE_ROLES)
    item=db.scalar(select(PublicOrderRequest).where(
        PublicOrderRequest.id==rid,
        PublicOrderRequest.business_id==bid).with_for_update())
    if not item:
        reject(404,"Không tìm thấy yêu cầu")
    if item.status=="accepted" and body.action=="accept":
        return stored(item,private=True)
    if item.status!="pending":
        reject(409,"Yêu cầu đã được xử lý")
    if body.action=="reject":
        item.status="rejected"
        item.review_reason=body.reason.strip()
        audit(db,bid,user[0].id,"public_order.rejected",{"request_id":rid})
        db.commit()
        return stored(item,private=True)
    # Accepted requests must use the same price originally displayed to guest.
    # Price changes require rejection and guest re-submission; no silent repricing.
    quantities=defaultdict(int)
    for line in item.lines:
        quantities[line["product_id"]] += line["quantity"]
    products={}
    for pid in sorted(quantities):
        p=db.scalar(select(Product).where(
            Product.business_id==bid,Product.id==pid,
            Product.active.is_(True)).with_for_update())
        if p is None or p.price_vnd!=next(x["unit_price_vnd"] for x in item.lines if x["product_id"]==pid):
            reject(409,"Giá hoặc sản phẩm đã thay đổi, cần từ chối và báo khách đặt lại")
        products[pid]=p
    from .modifiers import price_line, write_item_selection
    stock_quantities = defaultdict(int, quantities)
    for line in item.lines:
        unit, snapshots, extras = price_line(
            db, bid, products[line["product_id"]], line.get("selected_options", []))
        if unit != line["unit_price_vnd"] or snapshots != line.get("modifiers", []):
            reject(409, "Topping hoặc giá đã đổi, hãy từ chối để khách đặt lại")
        for stock_id, amount in extras.items():
            stock_quantities[stock_id] += amount * line["quantity"]
    branch=branch_for(db,bid,None)
    customer=Customer(id=str(uuid.uuid4()),business_id=bid,
                      name=item.customer_name,phone=item.phone,address=item.address)
    db.add(customer)
    db.flush()
    sale=SaleOrder(
        id=str(uuid.uuid4()),business_id=bid,branch_id=branch.id,
        customer_id=customer.id,table_id=None,
        idempotency_key="website-"+item.id,
        request_fingerprint=item.fingerprint,
        total_vnd=item.total_vnd,note=("Website #"+item.id[:8]+" "+item.note)[:300],
    )
    db.add(sale)
    db.flush()
    from .operations_v5 import consume_stock_for_sale
    consume_stock_for_sale(db,bid,sale.id,stock_quantities,branch.id)
    for line in item.lines:
        pid=line["product_id"]
        qty=line["quantity"]
        p=products[pid]
        entry_id=str(uuid.uuid4())
        db.add(SaleOrderItem(
            id=entry_id,business_id=bid,order_id=sale.id,
            product_id=pid,product_name=p.name,quantity=qty,
            unit_price_vnd=line["unit_price_vnd"],total_vnd=line["unit_price_vnd"]*qty,
        ))
        write_item_selection(db,bid,entry_id,line.get("modifiers",[]))
    kind={"online":"delivery","fnb":"kitchen"}.get(b.industry)
    if kind:
        db.add(IndustryWorkItem(
            id=str(uuid.uuid4()),business_id=bid,kind=kind,
            reference_id=sale.id,customer_id=customer.id,
            title=("Đơn giao • " if kind=="delivery" else "Phiếu bếp • ")+sale.id[:8].upper(),
            status="pending",details={"source":"published_storefront","note":item.note},
        ))
    item.status="accepted"
    item.sale_order_id=sale.id
    audit(db,bid,user[0].id,"public_order.accepted",{
        "request_id":rid,"sale_order_id":sale.id,"total_vnd":sale.total_vnd})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        reject(409,"Yêu cầu đã được xử lý ở phiên khác")
    return stored(item,private=True)
