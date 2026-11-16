"""Cashier tender metadata for the EXISTING SaleOrder paid ledger.

No gateway, bank feed, split tender, financial duplicate, or external transfer:
manual tender records only identify *how staff claims money was received*.
A payment record is a 1:1 immutable receipt, not a second balance/ledger.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import SaleOrder, now
from .main import audit, current_user, feature, order_out, tenant
from .team import ROLES, allow

router = APIRouter(prefix="/api/businesses/{bid}/pos-payments", tags=["POS manual tenders"])


class ManualTenderReceipt(Base):
    """Tenant-owned immutable metadata for one already-paid SaleOrder."""
    __tablename__ = "manual_tender_receipts"
    __table_args__ = (
        UniqueConstraint("business_id", "request_id", name="uq_tender_tenant_request"),
    )
    order_id: Mapped[str] = mapped_column(
        ForeignKey("sale_orders.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(
        ForeignKey("branches.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cash_received_vnd: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    change_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    transfer_reference: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    confirmed_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TenderConfirmation(BaseModel):
    request_id: str = Field(min_length=12, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    confirmed: Literal[True]
    method: Literal["cash", "bank_transfer"]
    expected_total_vnd: int = Field(ge=0, le=9_000_000_000_000)
    cash_received_vnd: int | None = Field(default=None, ge=0, le=9_000_000_000_000)
    transfer_reference: str = Field(default="", max_length=120)


def view(row: ManualTenderReceipt) -> dict:
    return {
        "order_id": row.order_id, "method": row.method,
        "amount_vnd": row.amount_vnd,
        "cash_received_vnd": row.cash_received_vnd,
        "change_vnd": row.change_vnd,
        "transfer_reference": row.transfer_reference,
        "provider_verified": False,
        "confirmation_type": "staff_manual",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/{oid}")
def get_tender(bid: str, oid: str, user=Depends(current_user),
               db: Session = Depends(db_session)):
    business = tenant(bid, user, db)
    feature(business, "orders")
    allow(db, bid, user, ROLES)
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.business_id == bid, SaleOrder.id == oid))
    if not order:
        raise HTTPException(404, "Không tìm thấy đơn")
    receipt = db.scalar(select(ManualTenderReceipt).where(
        ManualTenderReceipt.business_id == bid, ManualTenderReceipt.order_id == oid))
    return {
        "order_id": oid, "status": order.status, "total_vnd": order.total_vnd,
        "payment": view(receipt) if receipt else None,
        "notice": "Thông tin thanh toán ghi nhận thủ công, chưa đối soát ngân hàng."
    }


@router.post("/{oid}")
def collect_manual_tender(
    bid: str, oid: str, body: TenderConfirmation,
    user=Depends(current_user), db: Session = Depends(db_session)
):
    b = tenant(bid, user, db)
    feature(b, "orders")
    # Staff can act as cashiers at POS. All manual confirmations are audited.
    allow(db, bid, user, ROLES)

    # Lock order first: cancellation, payment via legacy /paid and two
    # concurrent cashier devices cannot both settle the same sale.
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.business_id == bid, SaleOrder.id == oid).with_for_update())
    if not order:
        raise HTTPException(404, "Không tìm thấy đơn")

    prior = db.scalar(select(ManualTenderReceipt).where(
        ManualTenderReceipt.business_id == bid,
        ManualTenderReceipt.order_id == oid))
    if prior:
        if (order.status == "paid" and prior.request_id == body.request_id and
            prior.method == body.method and
            prior.amount_vnd == body.expected_total_vnd and
            prior.cash_received_vnd == body.cash_received_vnd and
            prior.transfer_reference == body.transfer_reference.strip()):
            return {"order": order_out(db, order), "payment": view(prior)}
        raise HTTPException(409, "Đơn đã được ghi nhận thanh toán, không được thu trùng")
    if order.status != "open":
        raise HTTPException(409, "Chỉ có thể thu tiền cho đơn đang mở")
    if order.total_vnd != body.expected_total_vnd:
        raise HTTPException(409, "Tổng tiền đã thay đổi. Kiểm tra lại trước khi thu")
    if body.method == "cash":
        if body.cash_received_vnd is None or body.cash_received_vnd < order.total_vnd:
            raise HTTPException(422, "Tiền mặt khách đưa phải đủ tổng tiền")
        if body.transfer_reference.strip():
            raise HTTPException(422, "Thanh toán tiền mặt không dùng mã chuyển khoản")
        received = body.cash_received_vnd
        change = received - order.total_vnd
        reference = ""
    else:
        if body.cash_received_vnd is not None:
            raise HTTPException(422, "Chuyển khoản không dùng số tiền mặt khách đưa")
        received = None
        change = 0
        reference = body.transfer_reference.strip()

    receipt = ManualTenderReceipt(
        order_id=order.id, business_id=bid, branch_id=order.branch_id,
        method=body.method, amount_vnd=order.total_vnd,
        cash_received_vnd=received, change_vnd=change,
        transfer_reference=reference, request_id=body.request_id,
        confirmed_by=user[0].id, provider_verified=False,
    )
    try:
        db.add(receipt)
        order.status = "paid"
        order.paid_at = now()
        from .operations_v5 import loyalty_earn_on_paid
        loyalty_earn_on_paid(db, bid, order)
        from .printing import enqueue_receipt
        enqueue_receipt(db, bid, order)
        audit(db, bid, user[0].id, "pos.tender_recorded_manual", {
            "order_id": oid, "method": body.method, "amount_vnd": order.total_vnd,
            "cash_received_vnd": received, "change_vnd": change,
            "provider_verified": False,
        })
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Đơn vừa được thiết bị khác ghi nhận thanh toán")
    db.refresh(receipt)
    return {"order": order_out(db, order), "payment": view(receipt)}
