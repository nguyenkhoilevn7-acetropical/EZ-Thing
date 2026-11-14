"""Tenant-scoped, industry-specific operational workflows for EZ Thing pilot.

No payment, shipping-carrier, kitchen-device, or calendar integration is implied.
All state changes remain internal and audited. New table only: safe for existing pilot
schema created with SQLAlchemy create_all; formal migrations required before launch.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, select, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, Session
from .database import Base, db_session, engine
from .models import Customer, Product, SaleOrder, StockMovement, User, now
from .main import current_user, tenant, feature, audit, fail, new_id

router = APIRouter(prefix="/api/businesses/{bid}/industry", tags=["Industry workflows"])

KINDS = {"fnb": ("kitchen", "kitchen"), "retail": ("inventory", "stock_ledger"),
         "online": ("delivery", "fulfillment"), "services": ("appointments", "appointments")}
TRANSITIONS = {
 "kitchen": {"pending": "preparing", "preparing": "ready", "ready": "served"},
 "delivery": {"pending": "packed", "packed": "shipped", "shipped": "delivered"},
 "appointments": {"scheduled": "confirmed", "confirmed": "completed"},
}

class IndustryWorkItem(Base):
    __tablename__ = "industry_work_items"
    __table_args__ = (
      UniqueConstraint("business_id", "kind", "reference_id", name="uq_industry_work_reference"),
      Index("ix_industry_work_biz_kind", "business_id", "kind", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    assignee: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(20))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class CreateWorkItem(BaseModel):
    order_id: str | None = None
    customer_id: str | None = None
    product_id: str | None = None
    assignee: str = Field(default="", max_length=100)
    start_at: datetime | None = None
    duration_minutes: int = Field(default=60, ge=15, le=480)
    note: str = Field(default="", max_length=300)
    carrier: str = Field(default="", max_length=80)
    tracking_number: str = Field(default="", max_length=100)

    @field_validator("start_at")
    @classmethod
    def require_timezone(cls, dt):
        if dt is not None and (dt.tzinfo is None or dt.utcoffset() is None):
            raise ValueError("Thời gian đặt lịch cần có múi giờ")
        return dt

class NextStatus(BaseModel):
    status: str = Field(min_length=3, max_length=20)


def scope(bid, kind, user, db):
    b = tenant(bid, user, db)
    expected = KINDS.get(b.industry)
    if expected is None or kind != expected[0]:
        fail(404, "Không có quy trình này trong ngành kinh doanh")
    feature(b, expected[1])
    return b


def output(row):
    return {"id": row.id, "kind": row.kind, "reference_id": row.reference_id,
      "customer_id": row.customer_id, "product_id": row.product_id,
      "title": row.title, "assignee": row.assignee, "status": row.status,
      "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
      "ends_at": row.ends_at.isoformat() if row.ends_at else None,
      "details": row.details, "created_at": row.created_at.isoformat() if row.created_at else None}

@router.get("/{kind}")
def list_items(bid: str, kind: str, user=Depends(current_user), db: Session = Depends(db_session)):
    scope(bid, kind, user, db)
    if kind == "inventory":
        rows = db.execute(select(StockMovement, Product.name)
           .join(Product, (Product.id == StockMovement.product_id) & (Product.business_id == bid))
           .where(StockMovement.business_id == bid)
           .order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(100)).all()
        return [{"id": m.id, "product_id": m.product_id, "product_name": name,
                 "delta": m.delta, "reason": m.reason, "created_at": m.created_at.isoformat()}
                for m, name in rows]
    rows = db.scalars(select(IndustryWorkItem).where(IndustryWorkItem.business_id == bid,
                  IndustryWorkItem.kind == kind).order_by(IndustryWorkItem.created_at.desc()).limit(100)).all()
    return [output(row) for row in rows]

@router.post("/{kind}", status_code=201)
def create_item(bid: str, kind: str, body: CreateWorkItem,
                user=Depends(current_user), db: Session = Depends(db_session)):
    scope(bid, kind, user, db)
    if kind == "inventory":
        fail(405, "Dùng chức năng nhập/xuất kho có sẵn")
    if kind in ("kitchen", "delivery"):
        if not body.order_id:
            fail(422, "Vui lòng chọn đơn hàng")
        order = db.scalar(select(SaleOrder).where(SaleOrder.id == body.order_id, SaleOrder.business_id == bid))
        if not order:
            fail(404, "Không tìm thấy đơn hàng")
        old = db.scalar(select(IndustryWorkItem).where(IndustryWorkItem.business_id == bid,
                 IndustryWorkItem.kind == kind, IndustryWorkItem.reference_id == order.id))
        if old:
            return output(old)
        if kind == "delivery":
            customer = db.scalar(select(Customer).where(Customer.id == order.customer_id,
                Customer.business_id == bid)) if order.customer_id else None
            if not customer or not customer.address.strip():
                fail(422, "Đơn giao hàng cần có khách hàng và địa chỉ nhận hàng")
        row = IndustryWorkItem(id=new_id(), business_id=bid, kind=kind,
              reference_id=order.id, customer_id=order.customer_id,
              title=("Phiếu bếp • " if kind == "kitchen" else "Đơn giao • ") + order.id[:8].upper(),
              status="pending", details={"note":body.note,
                       **({"carrier":body.carrier,"tracking_number":body.tracking_number} if kind == "delivery" else {})})
    else:
        if not (body.customer_id and body.product_id and body.start_at and body.assignee.strip()):
            fail(422, "Cần chọn khách, dịch vụ, nhân viên và thời gian")
        customer = db.scalar(select(Customer).where(Customer.id == body.customer_id, Customer.business_id == bid))
        product = db.scalar(select(Product).where(Product.id == body.product_id,
                           Product.business_id == bid, Product.active.is_(True)))
        if not customer or not product:
            fail(404, "Khách hàng hoặc dịch vụ không thuộc doanh nghiệp")
        if product.track_stock:
            fail(422, "Dịch vụ đặt lịch phải tắt theo dõi tồn kho")
        start = body.start_at.astimezone(timezone.utc)
        end = start + timedelta(minutes=body.duration_minutes)
        if start < now() - timedelta(minutes=5):
            fail(422, "Không thể đặt lịch trong quá khứ")
        assignee = body.assignee.strip()
        # Serialize concurrent appointments per business + employee on PostgreSQL.
        if db.bind and db.bind.dialect.name == "postgresql":
            key = int.from_bytes(hashlib.sha256(f"{bid}|{assignee.casefold()}".encode()).digest()[:8], "big", signed=True)
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        conflict = db.scalar(select(IndustryWorkItem.id).where(
                 IndustryWorkItem.business_id == bid, IndustryWorkItem.kind == "appointments",
                 func.lower(IndustryWorkItem.assignee) == assignee.casefold(),
                 IndustryWorkItem.status.in_(["scheduled", "confirmed"]),
                 IndustryWorkItem.scheduled_at < end, IndustryWorkItem.ends_at > start))
        if conflict:
            fail(409, "Nhân viên đã có lịch trùng giờ")
        row = IndustryWorkItem(id=new_id(), business_id=bid, kind=kind,
              customer_id=customer.id, product_id=product.id,
              title=f"{product.name} • {customer.name}", assignee=assignee,
              scheduled_at=start, ends_at=end, status="scheduled", details={"note":body.note})
    db.add(row)
    audit(db, bid, user[0].id, f"{kind}.created", {"id":row.id, "reference_id":row.reference_id})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "Mục này đã được tạo hoặc dữ liệu đã thay đổi")
    return output(row)

@router.post("/{kind}/{item_id}/status")
def change_status(bid: str, kind: str, item_id: str, body: NextStatus,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    scope(bid, kind, user, db)
    if kind == "inventory": fail(405, "Không thể sửa lịch sử kho")
    item = db.scalar(select(IndustryWorkItem).where(IndustryWorkItem.id == item_id,
                         IndustryWorkItem.business_id == bid, IndustryWorkItem.kind == kind))
    if not item:
        fail(404, "Không tìm thấy công việc")
    if item.status == body.status:
        return output(item)
    if kind == "appointments" and body.status == "cancelled" and item.status in ("scheduled", "confirmed"):
        item.status = "cancelled"
    elif TRANSITIONS[kind].get(item.status) == body.status:
        item.status = body.status
    else:
        fail(409, "Trình tự trạng thái không hợp lệ")
    audit(db, bid, user[0].id, f"{kind}.status", {"id":item.id, "status":item.status})
    db.commit()
    return output(item)