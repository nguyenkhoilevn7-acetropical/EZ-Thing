"""Tenant-scoped Kitchen Display System backed by the *existing* kitchen work item.

KDS is an internal live tablet workflow, not a printer, cloud-push, offline
order transmission, or third-party dispatch integration. The kitchen work item
is the single canonical ticket. JSON snapshots are immutable against later
menu edits; status mutations copy-on-write to persist SQLAlchemy JSON changes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import db_session
from .main import audit, current_user, feature, fail, new_id, order_out, tenant
from .models import Business, Product, SaleOrder
from .team import MANAGE_ROLES, ROLES, allow
from .workflows import IndustryWorkItem

router = APIRouter(prefix="/api/businesses/{bid}/kds", tags=["Kitchen Display"])
STATIONS = {"bar", "hot", "cold", "expo"}
STATION_LABELS = {
    "bar": "Pha chế / Bar", "hot": "Bếp nóng",
    "cold": "Bếp lạnh", "expo": "Ra món / Chờ phân trạm",
}
PROGRESS = {
    "pending": {"preparing", "held"},
    "preparing": {"ready", "held"},
    "held": {"preparing"},
    "ready": {"served"},
    "served": set(),
}
DONE = {"served"}


class RouteUpdate(BaseModel):
    product_id: str = Field(min_length=1, max_length=36)
    station: Literal["bar", "hot", "cold", "expo"]


class FireTicket(BaseModel):
    order_id: str = Field(min_length=1, max_length=36)
    note: str = Field(default="", max_length=300)


class LineUpdate(BaseModel):
    status: Literal["preparing", "ready", "served", "held"]
    expected_revision: int = Field(ge=0)
    reason: str = Field(default="", max_length=160)


def guard(db: Session, bid: str, user):
    business = tenant(bid, user, db)
    if business.industry != "fnb":
        fail(404, "Bếp và pha chế chỉ dành cho nhà hàng/cafe")
    feature(business, "kitchen")
    allow(db, bid, user, ROLES)
    return business


def routing(db: Session, bid: str) -> dict[str, str]:
    rows = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kds_route",
        IndustryWorkItem.status == "active",
    )).all()
    return {x.reference_id: x.details["station"] for x in rows
            if (x.details or {}).get("station") in STATIONS}


def default_station(p: Product | None) -> str:
    """Best effort category-based proposal, not a guaranteed production recipe."""
    if p is None:
        return "expo"
    name = (p.name + " " + (p.category or "")).casefold()
    if any(t in name for t in ("cà phê", "coffee", "tea", "trà", "sinh tố",
                               "nước", "cocktail", "matcha", "juice", "bar",
                               "soda", "latte", "đồ uống", "beverage")):
        return "bar"
    if any(t in name for t in ("salad", "sashimi", "bếp lạnh", "cold", "gỏi")):
        return "cold"
    if any(t in name for t in ("cơm", "phở", "bún", "bánh mì", "pizza",
                               "mì", "đồ ăn", "food", "bếp nóng", "hot", "chiên")):
        return "hot"
    return "expo"


def ticket_lines(db: Session, bid: str, order: SaleOrder) -> list[dict]:
    """Snapshot all item/modifier information at the moment of firing."""
    items = order_out(db, order)["items"]
    if not items:
        fail(409, "Không thể gửi phiếu bếp khi đơn không có món")
    products = db.scalars(select(Product).where(
        Product.business_id == bid,
        Product.id.in_([x["product_id"] for x in items]),
    )).all()
    by_product = {p.id: p for p in products}
    routes = routing(db, bid)
    return [{
        "id": x["id"],
        "product_id": x["product_id"],
        "name": x["name"],
        "quantity": x["quantity"],
        "station": routes.get(x["product_id"], default_station(by_product.get(x["product_id"]))),
        "status": "pending",
        "modifiers": [
            {"name": opt.get("name", ""), "group_name": opt.get("group_name", "")}
            for opt in x.get("modifiers", [])],
        "updated_at": None,
    } for x in items]


def ticket_view(row: IndustryWorkItem, order: SaleOrder | None,
                lines: list[dict]) -> dict:
    def iso(value):
        if value is None:
            return None
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()
    return {
        "id": row.id,
        "order_id": row.reference_id,
        "branch_id": order.branch_id if order else None,
        "table_id": order.table_id if order else None,
        "status": row.status,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at or row.created_at),
        "revision": int((row.details or {}).get("kds_revision", 0)),
        "note": (row.details or {}).get("note", ""),
        "lines": lines,
    }


@router.get("/queue")
def queue(bid: str, branch_id: str | None = None,
          user=Depends(current_user), db: Session = Depends(db_session)):
    guard(db, bid, user)
    if branch_id:
        from .models import Branch
        exists = db.scalar(select(Branch.id).where(Branch.business_id == bid,
                                                   Branch.id == branch_id))
        if not exists:
            fail(404, "Chi nhánh không thuộc doanh nghiệp")
    # Snapshot tickets only. Paid orders can still be waiting on preparation.
    jobs = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid, IndustryWorkItem.kind == "kitchen",
        IndustryWorkItem.status != "cancelled")
        .order_by(IndustryWorkItem.created_at.desc()).limit(160)).all()
    order_ids = [job.reference_id for job in jobs if job.reference_id]
    orders = db.scalars(select(SaleOrder).where(
        SaleOrder.business_id == bid,
        SaleOrder.id.in_(order_ids))).all() if order_ids else []
    by_order = {o.id: o for o in orders}
    all_tickets = []
    counts = Counter()
    for job in reversed(jobs):
        o = by_order.get(job.reference_id)
        if not o or (branch_id and o.branch_id != branch_id):
            continue
        lines = (job.details or {}).get("kds_lines")
        if lines is None:
            # Legacy kitchen jobs predate the station snapshot. This is only
            # a read-only compatibility view: first write snapshots under lock.
            lines = ticket_lines(db, bid, o)
            for item in lines:
                item["status"] = job.status if job.status in (
                    "pending", "preparing", "ready", "served") else "pending"
        for line in lines:
            if line["status"] not in DONE:
                counts[line["station"]] += int(line["quantity"])
        all_tickets.append(ticket_view(job, o, lines))
    return {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "stations": STATION_LABELS,
        "tickets": all_tickets,
        "all_day": dict(counts),
        "ready_for_expo": sum(int(line["quantity"]) for ticket in all_tickets for line in ticket["lines"] if line["status"] == "ready"),
        "poll_after_seconds": 5,
        "transport": "foreground_polling",
        "notifications": "browser_tab_opt_in_only",
        "printing": "browser_print_only",
    }


@router.get("/routes")
def routes(bid: str, user=Depends(current_user),
           db: Session = Depends(db_session)):
    guard(db, bid, user)
    return {"stations": STATION_LABELS, "routes": routing(db, bid),
            "fallback": "category_guess_then_expo"}


@router.put("/routes")
def set_route(bid: str, body: RouteUpdate, user=Depends(current_user),
              db: Session = Depends(db_session)):
    guard(db, bid, user)
    allow(db, bid, user, MANAGE_ROLES)
    product = db.scalar(select(Product).where(
        Product.business_id == bid, Product.id == body.product_id))
    if not product:
        fail(404, "Sản phẩm không thuộc doanh nghiệp")
    # Serialize route edits on the business row and avoid duplicate creates.
    db.scalar(select(Business).where(Business.id == bid).with_for_update())
    row = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kds_route",
        IndustryWorkItem.reference_id == body.product_id).with_for_update())
    if row is None:
        row = IndustryWorkItem(
            id=new_id(), business_id=bid, kind="kds_route",
            reference_id=body.product_id, status="active",
            title="Trạm chế biến · " + product.name[:130],
            details={"station": body.station})
        db.add(row)
    else:
        row.details = {"station": body.station}
    audit(db, bid, user[0].id, "kds.route_changed",
          {"product_id":body.product_id, "station":body.station})
    db.commit()
    return {"product_id": product.id, "station": body.station}


@router.post("/fire", status_code=201)
def fire(bid: str, body: FireTicket,
         user=Depends(current_user), db: Session = Depends(db_session)):
    guard(db, bid, user)
    # Reuse existing canonical IndustryWorkItem, including its unique
    # business/kind/order constraint and lock/validation behavior.
    from .workflows import create_item, CreateWorkItem
    return create_item(bid, "kitchen", CreateWorkItem(order_id=body.order_id,
                                                      note=body.note), user, db)


@router.post("/tickets/{ticket_id}/lines/{line_id}/status")
def change_line(bid: str, ticket_id: str, line_id: str, body: LineUpdate,
                user=Depends(current_user), db: Session = Depends(db_session)):
    guard(db, bid, user)
    role = allow(db, bid, user, ROLES)
    # Canonical order lock first, like cancel/edit/payment and firing.
    probe = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid, IndustryWorkItem.id == ticket_id,
        IndustryWorkItem.kind == "kitchen"))
    if not probe:
        fail(404, "Phiếu bếp không tồn tại")
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.business_id == bid, SaleOrder.id == probe.reference_id
    ).with_for_update())
    if not order:
        fail(404, "Đơn hàng không tồn tại")
    job = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid, IndustryWorkItem.id == ticket_id,
        IndustryWorkItem.kind == "kitchen").with_for_update())
    if not job or job.reference_id != order.id:
        fail(409, "Phiếu bếp đã thay đổi")
    if job.status == "cancelled" or order.status == "cancelled":
        fail(409, "Đơn/phiếu đã hủy")
    details = dict(job.details or {})
    lines = [dict(x) for x in (details.get("kds_lines") or ticket_lines(db, bid, order))]
    revision = int(details.get("kds_revision", 0))
    chosen = next((x for x in lines if x["id"] == line_id), None)
    if chosen is None:
        fail(404, "Món không thuộc phiếu bếp")
    if chosen["status"] == body.status and revision == body.expected_revision:
        return ticket_view(job, order, lines)
    if revision != body.expected_revision:
        fail(409, "Phiếu đã thay đổi ở thiết bị khác. Hãy tải lại")
    old = chosen["status"]
    if body.status not in PROGRESS.get(old, set()):
        # Manager can recall a ready or served item after explicit reason.
        if not (role in MANAGE_ROLES and len(body.reason.strip()) >= 4
                and ((old, body.status) in {("ready", "preparing"), ("served", "ready")})):
            fail(409, "Không thể chuyển trạng thái món theo cách này")
    chosen["status"] = body.status
    chosen["updated_at"] = datetime.now(timezone.utc).isoformat()
    details["kds_lines"] = lines
    details["kds_revision"] = revision + 1
    job.details = details
    # A complete ticket is served only when *all* its items are served.
    statuses = {x["status"] for x in lines}
    if statuses == {"served"}:
        job.status = "served"
    elif statuses <= {"served", "ready"}:
        job.status = "ready"
    elif statuses & {"preparing", "held", "ready", "served"}:
        job.status = "preparing"
    else:
        job.status = "pending"
    audit(db, bid, user[0].id, "kds.line_status", {
        "ticket_id":job.id, "line_id":line_id, "from":old, "to":body.status,
        "revision":details["kds_revision"],
        "reason":body.reason.strip() if body.reason else None})
    db.commit()
    return ticket_view(job, order, lines)



class AvailabilityUpdate(BaseModel):
    available: bool
    reason: str = Field(min_length=4, max_length=180)


@router.post("/products/{product_id}/availability")
def product_availability(
        bid: str, product_id: str, body: AvailabilityUpdate,
        user=Depends(current_user), db: Session = Depends(db_session)):
    guard(db, bid, user)
    allow(db, bid, user, MANAGE_ROLES)
    row = db.scalar(select(Product).where(
        Product.id == product_id, Product.business_id == bid).with_for_update())
    if not row:
        fail(404, "Món không tồn tại trong doanh nghiệp")
    if row.active == body.available:
        return {"product_id": product_id, "available": row.active}
    row.active = body.available
    audit(db, bid, user[0].id, "kds.product_availability", {
        "product_id": product_id, "available": body.available,
        "reason": body.reason.strip()})
    db.commit()
    return {"product_id": product_id, "available": row.active}
