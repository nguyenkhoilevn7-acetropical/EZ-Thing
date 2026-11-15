"""Server-derived order KPIs and filtered list for Merchant App.

All amounts/statuses are read from the existing SaleOrder ledger. No new ledger.
The selected date range is interpreted in Asia/Ho_Chi_Minh local time.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from collections import defaultdict
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .database import db_session
from .models import Branch, DiningTable, SaleOrder, SaleOrderItem
from .main import current_user, feature, order_out, tenant

router = APIRouter(tags=["Orders dashboard"])
LOCAL = ZoneInfo("Asia/Ho_Chi_Minh")

@router.get("/api/businesses/{bid}/order-dashboard")
def order_dashboard(
    bid: str, from_day: date | None = None, to_day: date | None = None,
    status: Literal["all", "open", "paid", "cancelled"] = "all",
    table_id: str | None = None,
    branch_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=200),
    user=Depends(current_user), db: Session = Depends(db_session),
):
    b = tenant(bid, user, db)
    feature(b, "orders")
    if from_day and to_day and from_day > to_day:
        raise HTTPException(422, "Ngày bắt đầu phải trước ngày kết thúc")
    if from_day and to_day and (to_day - from_day).days > 365:
        raise HTTPException(422, "Khoảng lọc tối đa là 365 ngày")
    if branch_id and db.scalar(select(Branch.id).where(
            Branch.business_id == bid, Branch.id == branch_id)) is None:
        raise HTTPException(404, "Chi nhánh không thuộc doanh nghiệp")
    if table_id:
        table_record = db.scalar(select(DiningTable).where(
            DiningTable.business_id == bid, DiningTable.id == table_id))
        if table_record is None or (branch_id and table_record.branch_id != branch_id):
            raise HTTPException(404, "Bàn không thuộc doanh nghiệp / chi nhánh")
    clauses = [SaleOrder.business_id == bid]
    if from_day:
        start = datetime.combine(from_day, time.min, LOCAL).astimezone(timezone.utc)
        clauses.append(SaleOrder.created_at >= start)
    if to_day:
        end = datetime.combine(to_day + timedelta(days=1), time.min, LOCAL).astimezone(timezone.utc)
        clauses.append(SaleOrder.created_at < end)
    if status != "all":
        clauses.append(SaleOrder.status == status)
    if branch_id:
        clauses.append(SaleOrder.branch_id == branch_id)
    if table_id:
        clauses.append(SaleOrder.table_id == table_id)
    count, opened, paid, cancelled, paid_vnd = db.execute(select(
        func.count(SaleOrder.id),
        func.sum(case((SaleOrder.status == "open", 1), else_=0)),
        func.sum(case((SaleOrder.status == "paid", 1), else_=0)),
        func.sum(case((SaleOrder.status == "cancelled", 1), else_=0)),
        func.sum(case((SaleOrder.status == "paid", SaleOrder.total_vnd), else_=0)),
    ).where(*clauses)).one()
    rows = db.scalars(select(SaleOrder).where(*clauses).order_by(
        SaleOrder.created_at.desc(), SaleOrder.id.desc()).limit(limit)).all()
    by_order = defaultdict(list)
    if rows:
        for item in db.scalars(select(SaleOrderItem).where(
                SaleOrderItem.business_id == bid,
                SaleOrderItem.order_id.in_([o.id for o in rows]))):
            by_order[item.order_id].append(item)
    from .modifiers import order_selection_map
    selections = order_selection_map(db, bid, [x for group in by_order.values() for x in group])
    from .team import role_for
    finance = role_for(db, bid, user[0].id) in ("owner", "manager")
    return {
        "scope": "created_at", "timezone": "Asia/Ho_Chi_Minh",
        "limit": limit, "truncated": int(count or 0) > len(rows),
        "total_count": int(count or 0), "open_count": int(opened or 0),
        "paid_count": int(paid or 0), "cancelled_count": int(cancelled or 0),
        "paid_vnd": int(paid_vnd or 0) if finance else None,
        "orders": [order_out(db, o, items=by_order[o.id], selections=selections) for o in rows],
    }
