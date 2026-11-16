"""EZ Thing F&B host: real, audited table operating state, separate from the order ledger.

No fake "paid" orders are made to occupy tables. Active SaleOrder always takes
precedence and may only be moved through the authorized POS check workflow.
This API is tenant/branch restricted and works without new database tables.
"""
from __future__ import annotations

from datetime import timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import db_session
from .models import Branch, Business, DiningTable, SaleOrder, now
from .main import audit, current_user, fail, feature, new_id, tenant
from .team import require_branch, require_duty
from .workflows import IndustryWorkItem

router = APIRouter(prefix="/api/businesses/{bid}/host", tags=["Restaurant host workstation"])
KIND = "host_table_state"


class HostAction(BaseModel):
    action: Literal["seat", "release", "cleaning", "ready", "block", "unblock",
                    "update", "transfer", "join", "unjoin"]
    guest_count: int | None = Field(default=None, ge=1, le=60)
    note: str = Field(default="", max_length=240)
    target_table_id: str | None = None
    reservation_id: str | None = None
    guest_name: str = Field(default="", max_length=100)
    guest_phone: str = Field(default="", max_length=25)
    expected_revision: int = Field(ge=0)


def scoped(db: Session, bid: str, user, branch_id: str | None):
    business = tenant(bid, user, db)
    if business.industry != "fnb":
        fail(404, "Nghiệp vụ lễ tân chỉ có cho nhà hàng/cafe")
    feature(business, "tables")
    duty = require_duty(db, bid, user, {"host"})
    if duty and duty.branch_id:
        if branch_id and duty.branch_id != branch_id:
            fail(403, "Không được vận hành chi nhánh khác")
        branch_id = duty.branch_id
    branch = db.scalar(select(Branch).where(
        Branch.business_id == bid, Branch.id == branch_id)) if branch_id else db.scalar(
        select(Branch).where(Branch.business_id == bid).order_by(Branch.created_at, Branch.id))
    if branch is None:
        fail(404, "Không tìm thấy chi nhánh thuộc doanh nghiệp")
    require_branch(duty, branch.id)
    return business, branch


def table_row(db: Session, bid: str, branch_id: str, tid: str):
    row = db.scalar(select(DiningTable).where(
        DiningTable.business_id == bid, DiningTable.branch_id == branch_id,
        DiningTable.id == tid))
    if row is None:
        fail(404, "Bàn không thuộc chi nhánh được phân công")
    return row


def active_order_ids(db: Session, bid: str, branch_id: str):
    rows = db.scalars(select(SaleOrder).where(
        SaleOrder.business_id == bid, SaleOrder.branch_id == branch_id,
        SaleOrder.status == "open", SaleOrder.table_id.is_not(None))).all()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row.table_id, []).append(row.id)
    return result


def host_rows(db: Session, bid: str):
    return {
        r.reference_id: r for r in db.scalars(select(IndustryWorkItem).where(
            IndustryWorkItem.business_id == bid, IndustryWorkItem.kind == KIND)).all()
    }


def current_view(table, state, orders):
    details = (state.details or {}) if state else {}
    occupied_by_order = bool(orders.get(table.id))
    status = "occupied" if occupied_by_order else (
        state.status if state and state.status in ("occupied", "cleaning", "blocked") else "available"
    )
    return {"id": table.id, "branch_id": table.branch_id, "label": table.label,
            "seats": table.seats, "occupied": status == "occupied",
            "status": status, "guest_count": details.get("guest_count", 0),
            "guest_name": details.get("guest_name", ""),
            "guest_phone": details.get("guest_phone", ""),
            "seated_at": details.get("seated_at"),
            "reservation_id": details.get("reservation_id"),
            "note": details.get("note", ""), "group_id": details.get("group_id"),
            "order_count": len(orders.get(table.id, [])),
            "has_open_check": occupied_by_order,
            "revision": int(details.get("revision", 0))}


def board_data(db: Session, bid: str, branch):
    tables = db.scalars(select(DiningTable).where(
        DiningTable.business_id == bid, DiningTable.branch_id == branch.id
    ).order_by(DiningTable.label)).all()
    states = host_rows(db, bid)
    orders = active_order_ids(db, bid, branch.id)
    return {"branch_id": branch.id, "branch_name": branch.name,
            "tables": [current_view(t, states.get(t.id), orders) for t in tables]}


@router.get("/board")
def board(bid: str, branch_id: str | None = Query(default=None),
          user=Depends(current_user), db: Session = Depends(db_session)):
    _, branch = scoped(db, bid, user, branch_id)
    return board_data(db, bid, branch)


@router.post("/tables/{tid}/action")
def act(bid: str, tid: str, body: HostAction, branch_id: str | None = Query(default=None),
        user=Depends(current_user), db: Session = Depends(db_session)):
    _, branch = scoped(db, bid, user, branch_id)
    # Lock tenant row, serializing all host operations without introducing
    # branch-local duplicate state rows. Protected against stale tablet updates.
    db.scalar(select(Business).where(Business.id == bid).with_for_update())
    table = table_row(db, bid, branch.id, tid)
    orders = active_order_ids(db, bid, branch.id)
    states = host_rows(db, bid)
    row = states.get(table.id)
    before = current_view(table, row, orders)
    if before["revision"] != body.expected_revision:
        fail(409, "Bàn đã được thiết bị khác cập nhật. Tải lại trạng thái bàn.")
    action = body.action
    if action in ("release", "ready", "cleaning", "block", "unblock", "transfer", "unjoin") and orders.get(tid):
        fail(409, "Bàn còn đơn bán hàng chưa thanh toán. Phải chuyển hoặc hoàn tất đơn tại POS trước.")
    if action == "seat" and before["status"] not in ("available",):
        fail(409, "Bàn đang có khách, đang dọn hoặc tạm khóa")
    reservation = None
    if action == "seat":
        # The tenant lock also serializes check-in and booking choices made here.
        current = now()
        def aware(value):
            return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        upcoming = db.scalars(select(IndustryWorkItem).where(
            IndustryWorkItem.business_id == bid,
            IndustryWorkItem.kind == "reservations",
            IndustryWorkItem.status.in_(("pending", "confirmed")))).all()
        for booking in upcoming:
            d = booking.details or {}
            if d.get("branch_id") != branch.id or d.get("table_id") != tid:
                continue
            start = aware(booking.scheduled_at) if booking.scheduled_at else None
            end = aware(booking.ends_at) if booking.ends_at else None
            if not start or not end:
                continue
            if start - timedelta(minutes=30) <= current <= end and booking.id != body.reservation_id:
                fail(409, "Bàn có lịch đặt trong khung giờ này. Hãy chọn khách đã đặt để nhận bàn.")
            if booking.id == body.reservation_id:
                reservation = booking
        if body.reservation_id:
            if not reservation or reservation.status != "confirmed":
                fail(409, "Lịch đặt bàn không hợp lệ hoặc chưa xác nhận.")
            if not reservation.scheduled_at or not reservation.ends_at or not (
                aware(reservation.scheduled_at) - timedelta(minutes=60) <= current
                <= aware(reservation.ends_at)):
                fail(409, "Chưa đến khung giờ nhận khách của lịch đặt.")
    elif body.reservation_id:
        fail(422, "Chỉ được liên kết lịch đặt khi nhận khách")
    if action == "seat":
        seat_count = body.guest_count or (
            int((reservation.details or {}).get("party_size", 1)) if reservation else 1)
        if seat_count > table.seats:
            fail(409, "Số khách vượt số ghế. Hãy chọn bàn phù hợp trước khi nhận khách.")
    if action == "block" and before["status"] not in ("available", "blocked"):
        fail(409, "Chỉ có thể khóa bàn đang trống")
    if action in ("transfer", "join") and not body.target_table_id:
        fail(422, "Chọn bàn đích trước")
    if action == "transfer" and before["status"] != "occupied":
        fail(409, "Chỉ chuyển khách từ bàn đang sử dụng")
    if action == "join" and before["status"] != "occupied":
        fail(409, "Chỉ ghép thêm bàn cho nhóm khách đang dùng bàn")
    if action in ("release", "cleaning") and before["status"] not in ("occupied", "cleaning"):
        fail(409, "Không có phiên dùng bàn để kết thúc")
    if action == "unjoin" and not before["group_id"]:
        fail(409, "Bàn không thuộc nhóm ghép")
    if action == "unjoin" and before["group_id"] == tid:
        fail(409, "Chọn bàn phụ để tách; bàn chính không được tách khi còn khách")
    if action == "transfer" and before["group_id"]:
        others = [s for sid,s in states.items() if sid!=tid and
                  s.status=="occupied" and
                  (s.details or {}).get("group_id")==before["group_id"]]
        if others:
            fail(409, "Hãy tách các bàn ghép trước khi chuyển bàn chính")
    if action == "update" and before["status"] != "occupied":
        fail(409, "Chỉ cập nhật số khách cho bàn đang có khách")
    if action == "update" and body.guest_count:
        linked = [table]
        if before["group_id"]:
            linked = db.scalars(select(DiningTable).where(
                DiningTable.business_id == bid, DiningTable.branch_id == branch.id,
                DiningTable.id.in_([
                    tid for tid,row in states.items()
                    if (row.details or {}).get("group_id") == before["group_id"]
                ]))).all()
        if body.guest_count > sum(t.seats for t in linked):
            fail(409, "Số khách vượt sức chứa. Hãy ghép thêm bàn trước")
    if action == "ready" and before["status"] not in ("cleaning", "blocked", "available"):
        fail(409, "Bàn chưa hoàn tất khâu dọn dẹp")
    if action == "unblock" and before["status"] != "blocked":
        fail(409, "Bàn không bị khóa")
    target = None
    target_row = None
    if action in ("transfer", "join"):
        if body.target_table_id == tid:
            fail(422, "Bàn đích phải khác bàn hiện tại")
        target = table_row(db, bid, branch.id, body.target_table_id)
        target_row = states.get(target.id)
        if current_view(target, target_row, orders)["status"] != "available":
            fail(409, "Bàn đích phải trống và không có đơn bán hàng mở")
    if row is None:
        row = IndustryWorkItem(id=new_id(), business_id=bid, kind=KIND,
                               reference_id=tid, title="Lễ tân • "+table.label,
                               status="available", details={"revision":0})
        db.add(row)
    details = dict(row.details or {})
    details["revision"] = before["revision"] + 1
    if action == "seat":
        row.status = "occupied"
        details.update({"guest_count": body.guest_count or (
                            (reservation.details or {}).get("party_size", 1) if reservation else 1),
                        "note": body.note.strip(),
                        "guest_name": body.guest_name.strip() or (
                            (reservation.details or {}).get("customer_name", "") if reservation else ""),
                        "guest_phone": body.guest_phone.strip() or (
                            (reservation.details or {}).get("phone", "") if reservation else ""),
                        "reservation_id": reservation.id if reservation else None,
                        "group_id": None, "seated_at": now().isoformat()})
        if reservation:
            reservation.status = "seated"
            audit(db, bid, user[0].id, "reservation.status", {
                "id": reservation.id, "status": "seated", "table_id": tid})
    elif action in ("release", "cleaning"):
        # Releasing a joined party also frees its attached empty-check tables.
        if before["group_id"]:
            for sid,child in states.items():
                if sid == tid or child.status != "occupied" or (
                    child.details or {}).get("group_id") != before["group_id"]:
                    continue
                if orders.get(sid):
                    fail(409, "Bàn ghép vẫn còn đơn chưa thanh toán")
                cd=dict(child.details or {})
                cd.update({"revision":int(cd.get("revision",0))+1,
                           "guest_count":0,"group_id":None,"note":body.note.strip()})
                child.details=cd;child.status="cleaning"
        row.status = "cleaning"
        details.update({"guest_count": 0, "group_id": None, "note": body.note.strip(),
                        "guest_name": "", "guest_phone": "", "reservation_id": None,
                        "seated_at": None})
    elif action in ("ready", "unblock"):
        row.status = "available"
        details.update({"guest_count":0,"group_id":None,"note":"",
                        "guest_name":"", "guest_phone":"", "reservation_id":None,
                        "seated_at":None})
    elif action == "block":
        row.status = "blocked"
        details.update({"guest_count": 0, "group_id": None, "note":body.note.strip()})
    elif action == "update":
        details.update({"guest_count":body.guest_count or before["guest_count"],
                        "guest_name":body.guest_name.strip() or before["guest_name"],
                        "guest_phone":body.guest_phone.strip() or before["guest_phone"],
                        "note":body.note.strip()})
    elif action == "join":
        group_id = before["group_id"] or tid
        details["group_id"] = group_id
        if target_row is None:
            target_row = IndustryWorkItem(
                id=new_id(),business_id=bid,kind=KIND,reference_id=target.id,
                title="Lễ tân • "+target.label,status="occupied",details={"revision":0})
            db.add(target_row)
        td = dict(target_row.details or {})
        td.update({"revision":int(td.get("revision",0))+1,"group_id":group_id,
                   "guest_count": 0,"note":body.note.strip()})
        target_row.details = td
        target_row.status = "occupied"
    elif action == "transfer":
        # A table transfer here means a host seating session ONLY; never
        # a POS check or a paid financial record.
        row.status = "available"
        details.update({"guest_count":0,"note":"","group_id":None,
                        "guest_name":"", "guest_phone":"", "reservation_id":None,
                        "seated_at":None})
        if target_row is None:
            target_row = IndustryWorkItem(
                id=new_id(),business_id=bid,kind=KIND,reference_id=target.id,
                title="Lễ tân • "+target.label,status="occupied",details={"revision":0})
            db.add(target_row)
        td = dict(target_row.details or {})
        td.update({"revision":int(td.get("revision",0))+1,"guest_count":
                   body.guest_count or before["guest_count"],"note":
                   body.note.strip() or before["note"],"group_id":None,
                   "guest_name":body.guest_name.strip() or before["guest_name"],
                   "guest_phone":body.guest_phone.strip() or before["guest_phone"],
                   "reservation_id":before["reservation_id"],
                   "seated_at":before["seated_at"] or now().isoformat()})
        target_row.details = td
        target_row.status="occupied"
    elif action == "unjoin":
        row.status="available"
        details.update({"guest_count":0,"group_id":None,"note":""})
        # Do not leave a one-table "linked group" badge after last unlink.
        group=before["group_id"]
        left=[s for sid,s in states.items()
              if sid!=tid and s.status=="occupied"
              and (s.details or {}).get("group_id")==group]
        if len(left)==1:
            main=left[0];md=dict(main.details or {})
            md.update({"group_id":None,"revision":int(md.get("revision",0))+1})
            main.details=md
    row.details = details
    audit(db,bid,user[0].id,"host.table_"+action,{
        "table_id":tid,"target_table_id":body.target_table_id,"before":before,
        "after_status":row.status,"revision":details["revision"]})
    db.commit()
    return board_data(db,bid,branch)
