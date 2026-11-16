"""V7 POS checks: safe open-check edits, discounts, tips, and same-branch table moves.

All mutations operate on the existing SaleOrder / StockMovement ledgers.
No payment, refund, tax calculation, kitchen re-fire, or split/merge is implied.
"""
from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, String, UniqueConstraint, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .main import audit, current_user, feature, order_out, tenant
from .models import DiningTable, Product, SaleOrder, SaleOrderItem, StockMovement
from .schemas import OrderLine
from .team import ROLES, MANAGE_ROLES, allow
from .workflows import IndustryWorkItem

router = APIRouter(prefix="/api/businesses/{bid}/pos", tags=["POS advanced checks"])
MAX_TOTAL = 9_000_000_000_000


class POSCheckMeta(Base):
    __tablename__ = "pos_check_meta"
    order_id: Mapped[str] = mapped_column(ForeignKey("sale_orders.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subtotal_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    discount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tip_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class POSMutation(Base):
    __tablename__ = "pos_check_mutations"
    __table_args__ = (UniqueConstraint("business_id", "request_id", name="uq_pos_mutation_tenant_request"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("sale_orders.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(30))
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON, nullable=False)


class RequestKey(BaseModel):
    request_id: str = Field(min_length=12, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    expected_revision: int = Field(ge=0)


class ReplaceOpenCheck(RequestKey):
    lines: list[OrderLine] = Field(min_length=1, max_length=50)
    discount_vnd: int = Field(default=0, ge=0, le=2_000_000_000)
    tip_vnd: int = Field(default=0, ge=0, le=2_000_000_000)
    note: str = Field(default="", max_length=300)


class MoveCheck(RequestKey):
    table_id: str | None = Field(default=None, max_length=36)


def error(code: int, detail: str):
    raise HTTPException(code, detail)


def get_check(db: Session, bid: str, oid: str, locked=False) -> SaleOrder:
    q = select(SaleOrder).where(SaleOrder.business_id == bid, SaleOrder.id == oid)
    if locked:
        q = q.with_for_update()
    order = db.scalar(q)
    if order is None:
        error(404, "Không tìm thấy đơn hàng")
    return order


def editable(db: Session, bid: str, oid: str, order: SaleOrder):
    if order.status != "open":
        error(409, "Chỉ sửa đơn chưa thanh toán")
    # Once a ticket has been sent to KDS or delivery, editing without a
    # compensating prep event could silently misprepare an order.
    jobs = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid, IndustryWorkItem.reference_id == oid,
        IndustryWorkItem.kind.in_(("kitchen", "delivery")),
        IndustryWorkItem.status.not_in(("cancelled", "rejected")),
    ).with_for_update()).all()
    if jobs:
        error(409, "Đơn đã gửi bếp hoặc giao vận; không được tự sửa")


def metadata(db: Session, bid: str, oid: str) -> POSCheckMeta | None:
    return db.scalar(select(POSCheckMeta).where(
        POSCheckMeta.business_id == bid, POSCheckMeta.order_id == oid).with_for_update())


def show(db: Session, order: SaleOrder, meta: POSCheckMeta | None = None):
    meta = meta if meta is not None else metadata(db, order.business_id, order.id)
    obj = order_out(db, order)
    obj.update({
        "revision": meta.revision if meta else 0,
        "subtotal_vnd": meta.subtotal_vnd if meta else sum(i["total_vnd"] for i in obj["items"]),
        "discount_vnd": meta.discount_vnd if meta else 0,
        "tip_vnd": meta.tip_vnd if meta else 0,
        "payment_collected": False,
    })
    return obj


def previous_mutation(db: Session, bid: str, oid: str, request_id: str, action: str, fingerprint: str):
    past = db.scalar(select(POSMutation).where(
        POSMutation.business_id == bid, POSMutation.request_id == request_id))
    if past is None:
        return None
    if past.order_id != oid or past.action != action or past.fingerprint != fingerprint:
        error(409, "Mã thao tác đã được dùng cho nội dung khác")
    return past.response


def record_mutation(db: Session, bid: str, oid: str, request_id: str,
                    action: str, fingerprint: str, result: dict):
    db.add(POSMutation(
        id=str(uuid.uuid4()), business_id=bid, order_id=oid,
        request_id=request_id, action=action, fingerprint=fingerprint,
        response=result))


def fingerprint(body: BaseModel) -> str:
    return hashlib.sha256(body.model_dump_json(exclude_none=False).encode()).hexdigest()


def check_revision(meta: POSCheckMeta | None, expected: int):
    actual = meta.revision if meta else 0
    if actual != expected:
        error(409, "Đơn đã thay đổi ở thiết bị khác, vui lòng tải lại")


def changed_stock(db: Session, bid: str, oid: str, branch_id: str, new_units: dict[str,int]):
    """Bring exact existing sale usage in line with the replacement cart.

    The *signed* adjustment movements are append-only. Both later cancellation
    and finance estimation use sale + pos_adjust, preserving correct net stock
    even if a recipe changed after the original order.
    """
    from .operations_v5 import branch_stock_change
    existing = defaultdict(int)
    old = db.scalars(select(StockMovement).where(
        StockMovement.business_id == bid, StockMovement.ref == oid,
        StockMovement.reason.in_(("sale", "pos_adjust")))).all()
    for m in old:
        existing[m.product_id] -= m.delta
    if any(q < 0 for q in existing.values()):
        error(409, "Dữ liệu kho của đơn không cân bằng")
    changes = {pid: existing.get(pid, 0) - new_units.get(pid, 0)
               for pid in set(existing) | set(new_units)}
    # Restore first to avoid false out-of-stock after replacing an item.
    for pid, delta in sorted(changes.items(), key=lambda x: (x[1] <= 0, x[0])):
        if not delta:
            continue
        updated = db.execute(update(Product).where(
            Product.id == pid, Product.business_id == bid,
            Product.track_stock.is_(True),
            Product.stock + delta >= 0,
        ).values(stock=Product.stock + delta))
        if updated.rowcount != 1:
            error(409, "Không đủ tồn kho để cập nhật đơn")
        branch_stock_change(db, bid, branch_id, pid, delta)
        db.add(StockMovement(
            id=str(uuid.uuid4()), business_id=bid, product_id=pid,
            delta=delta, reason="pos_adjust", ref=oid))
    return {pid: delta for pid, delta in changes.items() if delta}


@router.get("/orders/{oid}")
def pos_check(bid: str, oid: str, user=Depends(current_user),
              db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "orders")
    from .team import require_duty, require_branch
    duty = require_duty(db, bid, user, {"order", "cashier"})
    order = get_check(db, bid, oid)
    require_branch(duty, order.branch_id)
    return show(db, order)


@router.put("/orders/{oid}")
def replace_check(bid: str, oid: str, body: ReplaceOpenCheck,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "orders")
    role = allow(db, bid, user, ROLES)
    from .team import require_duty
    require_duty(db, bid, user, {"order"})
    fp = fingerprint(body)
    done = previous_mutation(db, bid, oid, body.request_id, "replace", fp)
    if done is not None:
        return done
    order = get_check(db, bid, oid, locked=True)
    from .team import require_branch, duty_for
    require_branch(duty_for(db, bid, user[0].id) if role == "staff" else None, order.branch_id)
    # A concurrent identical retry may have committed while this call waited
    # on the order lock. Check again before testing the revision.
    done = previous_mutation(db, bid, oid, body.request_id, "replace", fp)
    if done is not None:
        return done
    editable(db, bid, oid, order)
    meta = metadata(db, bid, oid)
    check_revision(meta, body.expected_revision)
    if role not in MANAGE_ROLES and (body.discount_vnd or body.tip_vnd):
        error(403, "Giảm giá và tiền tip cần quyền quản lý")
    # All selected modifiers are validated against the current tenant config.
    from .modifiers import price_line, write_item_selection, SaleOrderItemModifier
    from .operations_v5 import consumption_for_sale
    quantities = defaultdict(int)
    lines = []
    subtotal = 0
    for item in body.lines:
        p = db.scalar(select(Product).where(
            Product.business_id == bid, Product.id == item.product_id,
            Product.active.is_(True)))
        if p is None:
            error(404, "Sản phẩm không còn bán; hãy bỏ món này khỏi đơn")
        unit, options, extras = price_line(db, bid, p, item.selected_options)
        subtotal += unit * item.quantity
        quantities[p.id] += item.quantity
        for ingredient, amount in extras.items():
            quantities[ingredient] += amount * item.quantity
        lines.append((p, item.quantity, unit, options))
    if body.discount_vnd > subtotal:
        error(422, "Tiền giảm giá không được lớn hơn tiền món")
    total = subtotal - body.discount_vnd + body.tip_vnd
    if total > MAX_TOTAL:
        error(422, "Tổng đơn vượt giới hạn")
    if role not in MANAGE_ROLES:
        # Staff cannot silently clear a manager-approved discount or tip.
        if meta and (meta.discount_vnd or meta.tip_vnd):
            error(403, "Đơn có giảm giá/tip cần quản lý chỉnh sửa")
    requested_stock = consumption_for_sale(db, bid, quantities)
    deltas = changed_stock(db, bid, oid, order.branch_id, requested_stock)
    old_items = db.scalars(select(SaleOrderItem).where(
        SaleOrderItem.business_id == bid, SaleOrderItem.order_id == oid)).all()
    old_snapshot = order_out(db, order, items=old_items)["items"]
    if old_items:
        db.execute(delete(SaleOrderItemModifier).where(
            SaleOrderItemModifier.business_id == bid,
            SaleOrderItemModifier.item_id.in_([x.id for x in old_items])))
        db.execute(delete(SaleOrderItem).where(
            SaleOrderItem.business_id == bid,
            SaleOrderItem.order_id == oid))
    for p, qty, unit, options in lines:
        line_id = str(uuid.uuid4())
        db.add(SaleOrderItem(
            id=line_id, business_id=bid, order_id=oid, product_id=p.id,
            product_name=p.name, quantity=qty, unit_price_vnd=unit,
            total_vnd=qty * unit))
        write_item_selection(db, bid, line_id, options)
    order.total_vnd = total
    order.note = body.note
    if meta is None:
        meta = POSCheckMeta(order_id=oid, business_id=bid)
        db.add(meta)
    meta.revision = body.expected_revision + 1
    meta.subtotal_vnd = subtotal
    meta.discount_vnd = body.discount_vnd
    meta.tip_vnd = body.tip_vnd
    db.flush()
    result = show(db, order, meta)
    audit(db, bid, user[0].id, "pos.check_replaced", {
        "order_id": oid, "from_revision": body.expected_revision,
        "to_revision": meta.revision, "before": old_snapshot,
        "stock_deltas": deltas, "subtotal_vnd": subtotal,
        "discount_vnd": body.discount_vnd, "tip_vnd": body.tip_vnd})
    record_mutation(db, bid, oid, body.request_id, "replace", fp, result)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        done = previous_mutation(db, bid, oid, body.request_id, "replace", fp)
        if done is not None:
            return done
        error(409, "Thao tác trùng hoặc dữ liệu đơn đã thay đổi")
    return result


@router.post("/orders/{oid}/move-table")
def move_table(bid: str, oid: str, body: MoveCheck,
               user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "orders")
    feature(b, "tables")
    allow(db, bid, user, MANAGE_ROLES)
    fp = fingerprint(body)
    done = previous_mutation(db, bid, oid, body.request_id, "move_table", fp)
    if done is not None:
        return done
    order = get_check(db, bid, oid, locked=True)
    # A concurrent identical retry may have committed while this call waited
    # on the order lock. Check again before testing the revision.
    done = previous_mutation(db, bid, oid, body.request_id, "move_table", fp)
    if done is not None:
        return done
    editable(db, bid, oid, order)
    meta = metadata(db, bid, oid)
    check_revision(meta, body.expected_revision)
    table = None
    if body.table_id:
        table = db.scalar(select(DiningTable).where(
            DiningTable.business_id == bid, DiningTable.id == body.table_id,
            DiningTable.branch_id == order.branch_id))
        if not table:
            error(404, "Bàn phải thuộc cùng chi nhánh với đơn")
    if meta is None:
        meta = POSCheckMeta(order_id=oid, business_id=bid)
        db.add(meta)
    old_table = order.table_id
    order.table_id = table.id if table else None
    meta.revision = body.expected_revision + 1
    # Preserve subtotal and adjustments if there was no previous POS edit.
    if meta.revision == 1:
        meta.subtotal_vnd = order.total_vnd
    db.flush()
    result = show(db, order, meta)
    audit(db, bid, user[0].id, "pos.table_moved", {
        "order_id": oid, "old_table_id": old_table,
        "new_table_id": order.table_id, "revision": meta.revision})
    record_mutation(db, bid, oid, body.request_id, "move_table", fp, result)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        done = previous_mutation(db, bid, oid, body.request_id, "move_table", fp)
        if done is not None:
            return done
        error(409, "Thao tác trùng hoặc dữ liệu bàn đã thay đổi")
    return result
