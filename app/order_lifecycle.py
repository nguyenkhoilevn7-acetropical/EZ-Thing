"""Tenant-scoped cancellation of *unpaid* orders, with atomic stock restoration.

This pilot operation is not a refund. No gateway, tax or external fulfillment
provider is called. A paid or already-processed order must use a future
supervised return/refund workflow, never this endpoint.
"""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .database import db_session
from .main import audit, current_user, fail, feature, order_out, tenant, new_id
from .models import Membership, Product, SaleOrder, StockMovement
from .workflows import IndustryWorkItem

router = APIRouter(tags=["Order lifecycle"])


class CancelOrder(BaseModel):
    confirmed: Literal[True]
    reason: str = Field(min_length=4, max_length=250)

    @field_validator("reason")
    @classmethod
    def non_blank_reason(cls, value: str):
        value = value.strip()
        if len(value) < 4:
            raise ValueError("Lý do hủy cần ít nhất 4 ký tự")
        return value


@router.post("/api/businesses/{bid}/orders/{oid}/cancel")
def cancel_unpaid_order(
    bid: str, oid: str, body: CancelOrder,
    user=Depends(current_user), db: Session = Depends(db_session),
):
    business = tenant(bid, user, db)
    feature(business, "orders")
    role = db.scalar(select(Membership.role).where(
        Membership.business_id == bid, Membership.user_id == user[0].id))
    if role != "owner":
        fail(403, "Chỉ chủ doanh nghiệp được hủy đơn và hoàn tồn kho")

    # Row lock serializes cancel against payment confirmation on PostgreSQL.
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.business_id == bid, SaleOrder.id == oid).with_for_update())
    if order is None:
        fail(404, "Không tìm thấy đơn hàng")
    if order.status == "cancelled":
        return order_out(db, order)  # Safe retry; do not restore stock twice.
    if order.status != "open":
        fail(409, "Đơn đã thanh toán hoặc không còn cho phép hủy")

    linked = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.reference_id == oid,
        IndustryWorkItem.kind.in_(("kitchen", "delivery")),
    ).with_for_update()).all()
    if any(job.status != "pending" for job in linked):
        fail(409, "Đơn đã vào bếp hoặc giao vận, không thể tự động hủy")

    # Restore ONLY units actually deducted when this order was created.
    # This preserves the distinction between tracked goods and services.
    original_moves = db.scalars(select(StockMovement).where(
        StockMovement.business_id == bid,
        StockMovement.ref == oid,
        StockMovement.reason == "sale",
        StockMovement.delta < 0,
    )).all()
    for movement in original_moves:
        changed = db.execute(update(Product).where(
            Product.id == movement.product_id, Product.business_id == bid,
        ).values(stock=Product.stock - movement.delta))
        if changed.rowcount != 1:
            db.rollback()
            fail(409, "Không thể đối soát sản phẩm khi hoàn tồn kho")
        from .operations_v5 import branch_stock_change
        branch_stock_change(db,bid,order.branch_id,movement.product_id,-movement.delta)
        db.add(StockMovement(
            id=new_id(), business_id=bid, product_id=movement.product_id,
            delta=-movement.delta, reason="order_cancelled", ref=oid,
        ))

    order.status = "cancelled"
    for job in linked:
        job.status = "cancelled"
    audit(db, bid, user[0].id, "order.cancelled", {
        "order_id": oid, "reason": body.reason,
        "restored_units": sum(-x.delta for x in original_moves),
    })
    db.commit()
    return order_out(db, order)
