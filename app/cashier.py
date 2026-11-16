"""Read-only cashier day summary; does NOT claim to close a shift or reconcile bank/cash.

EZ Thing pilot stores only manual paid confirmations. We cannot truthfully infer
cash/card/transfer breakdown or drawer variance without validated payment data.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import db_session
from .main import current_user, feature, tenant
from .models import Branch, SaleOrder
from .team import MANAGE_ROLES, allow

router = APIRouter(prefix="/api/businesses/{bid}/cashier", tags=["Cashier reconciliation"])
LOCAL = ZoneInfo("Asia/Ho_Chi_Minh")


@router.get("/close-preview")
def close_preview(bid: str, day: date | None = None,
                  branch_id: str | None = None,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    business = tenant(bid, user, db)
    feature(business, "orders")
    allow(db, bid, user, MANAGE_ROLES)
    selected = day or datetime.now(LOCAL).date()
    if selected < datetime.now(LOCAL).date() - timedelta(days=366):
        raise HTTPException(422, "Ngày báo cáo chỉ hỗ trợ trong vòng 366 ngày")
    if selected > datetime.now(LOCAL).date():
        raise HTTPException(422, "Không thể chốt báo cáo trong tương lai")
    if branch_id is not None:
        found = db.scalar(select(Branch.id).where(
            Branch.business_id == bid, Branch.id == branch_id))
        if not found:
            raise HTTPException(404, "Chi nhánh không thuộc doanh nghiệp")
    start = datetime.combine(selected, time.min, LOCAL).astimezone(timezone.utc)
    end = datetime.combine(selected + timedelta(days=1), time.min, LOCAL).astimezone(timezone.utc)
    scoped = [SaleOrder.business_id == bid]
    if branch_id is not None:
        scoped.append(SaleOrder.branch_id == branch_id)
    paid = db.execute(select(
        func.count(SaleOrder.id), func.coalesce(func.sum(SaleOrder.total_vnd), 0)
    ).where(*scoped, SaleOrder.status == "paid",
            SaleOrder.paid_at >= start, SaleOrder.paid_at < end)).one()
    created = db.execute(select(
        func.count(SaleOrder.id),
        func.count(SaleOrder.id).filter(SaleOrder.status == "cancelled"),
        func.count(SaleOrder.id).filter(SaleOrder.status == "open"),
    ).where(*scoped, SaleOrder.created_at >= start, SaleOrder.created_at < end)).one()
    outstanding_now = db.scalar(select(func.count(SaleOrder.id)).where(
        *scoped, SaleOrder.status == "open")) or 0
    recent = db.scalars(select(SaleOrder).where(
        *scoped, SaleOrder.status == "paid",
        SaleOrder.paid_at >= start, SaleOrder.paid_at < end)
        .order_by(SaleOrder.paid_at.desc(), SaleOrder.id.desc()).limit(40)).all()
    from .pos_payments import ManualTenderReceipt
    declared = db.execute(select(
        ManualTenderReceipt.method, func.coalesce(func.sum(ManualTenderReceipt.amount_vnd), 0)
    ).join(SaleOrder, SaleOrder.id == ManualTenderReceipt.order_id)
      .where(*scoped, ManualTenderReceipt.business_id == bid,
             SaleOrder.status == "paid", SaleOrder.paid_at >= start,
             SaleOrder.paid_at < end)
      .group_by(ManualTenderReceipt.method)).all()
    by_method = {method: int(amount) for method, amount in declared}
    cash_manual = by_method.get("cash", 0)
    transfer_manual = by_method.get("bank_transfer", 0)
    unclassified = max(0, int(paid[1] or 0) - cash_manual - transfer_manual)
    payment_rows = db.scalars(select(ManualTenderReceipt).where(
        ManualTenderReceipt.business_id == bid,
        ManualTenderReceipt.order_id.in_([x.id for x in recent] or [""]))).all()
    payment_map = {row.order_id: row for row in payment_rows}
    return {
        "mode": "read_only_preview", "can_close_shift": False,
        "business_id": bid, "branch_id": branch_id,
        "day": selected.isoformat(), "timezone": "Asia/Ho_Chi_Minh",
        "paid_at_day": {"count": int(paid[0] or 0), "amount_vnd": int(paid[1] or 0)},
        "created_at_day": {"count": int(created[0] or 0),
                           "cancelled_now": int(created[1] or 0),
                           "open_now": int(created[2] or 0)},
        "outstanding_now_count": int(outstanding_now),
        "unknown_payment_method_vnd": unclassified,
        "manual_cash_vnd": cash_manual,
        "manual_bank_transfer_vnd": transfer_manual,
        "cash_counted_vnd": None, "cash_variance_vnd": None,
        "bank_verified": False,
        "entries": [{"order_id": x.id, "amount_vnd": x.total_vnd,
                     "payment_method": (payment_map[x.id].method if x.id in payment_map
                                        else "unknown_legacy"),
                     "bank_verified": False,
                     "paid_at": x.paid_at.isoformat() if x.paid_at else None}
                    for x in recent],
        "entries_truncated": int(paid[0] or 0) > len(recent),
        "notice": "Có phân loại tiền mặt và chuyển khoản do nhân viên xác nhận thủ công. Không có xác minh ngân hàng, không đếm tiền két, đơn cũ có thể chưa rõ phương thức. Đây không phải chốt ca chính thức.",
    }
