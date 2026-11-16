"""Tenant-scoped Kitchen Display System backed by the *existing* kitchen work item.

KDS is an internal live tablet workflow, not a printer, cloud-push, offline
order transmission, or third-party dispatch integration. The kitchen work item
is the single canonical ticket. JSON snapshots are immutable against later
menu edits; status mutations copy-on-write to persist SQLAlchemy JSON changes.
"""
from __future__ import annotations

from collections import Counter
import hashlib
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
ROUTE_STATIONS = STATIONS | {"skip"}
ROUTE_LABELS = {**{
    "bar": "Pha chế / Bar", "hot": "Bếp nóng",
    "cold": "Bếp lạnh", "expo": "Ra món / Cần phân trạm",
}, "skip": "Không cần chế biến / Không gửi KDS"}
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
    station: Literal["bar", "hot", "cold", "expo", "skip"]


class CategoryRouteUpdate(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    station: Literal["bar", "hot", "cold", "expo", "skip"]


class DispatchSettingsUpdate(BaseModel):
    auto_dispatch: bool


class CategoryRouteRemove(BaseModel):
    category: str = Field(min_length=1, max_length=80)


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
            if (x.details or {}).get("station") in ROUTE_STATIONS}


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


def normalize_category(value: str) -> str:
    return " ".join(value.split()).casefold()


def category_route_key(category: str) -> str:
    return hashlib.sha256(normalize_category(category).encode()).hexdigest()[:32]


def category_routing(db: Session, bid: str) -> dict[str, str]:
    rows = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kds_category_route",
        IndustryWorkItem.status == "active",
    )).all()
    return {
        normalize_category(row.details["category"]): row.details["station"]
        for row in rows if row.details and row.details.get("category")
        and row.details.get("station") in ROUTE_STATIONS
    }


def dispatch_settings(db: Session, bid: str) -> dict:
    row = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kds_settings",
        IndustryWorkItem.reference_id == bid,
    ))
    return {"auto_dispatch": bool((row.details or {}).get("auto_dispatch", True))
            if row else True}


def auto_dispatch_order(db: Session, bid: str, order: SaleOrder, *,
                        source: str = "pos", force: bool = False) -> dict:
    """Create a single canonical KDS ticket/print outbox in the order transaction.

    Replaying a sale or confirming payment NEVER enqueues a new ticket.
    Non-prep-only orders are intentionally omitted. No external devices are
    contacted; EZ Print outbox is committed atomically with the order.
    """
    if not force and not dispatch_settings(db, bid)["auto_dispatch"]:
        return {"status": "manual", "ticket_id": None}
    old = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kitchen",
        IndustryWorkItem.reference_id == order.id,
    ))
    if old:
        return {"status": "sent", "ticket_id": old.id}
    db.flush()
    lines = ticket_lines(db, bid, order)
    if not lines:
        return {"status": "no_prep", "ticket_id": None}
    details = {
        "source": source, "note": order.note,
        "kds_lines": lines, "kds_revision": 0,
        "auto_dispatched": not force,
    }
    ticket = IndustryWorkItem(
        id=new_id(), business_id=bid, kind="kitchen",
        reference_id=order.id, customer_id=order.customer_id,
        title="Phiếu bếp • " + order.id[:8].upper(),
        status="pending", details=details,
    )
    db.add(ticket)
    from .printing import enqueue_kitchen
    enqueue_kitchen(db, bid, order, ticket.id, details)
    db.flush()
    return {"status": "sent", "ticket_id": ticket.id}


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
    categories = category_routing(db, bid)
    result = [{
        "id": x["id"],
        "product_id": x["product_id"],
        "name": x["name"],
        "quantity": x["quantity"],
        "station": routes.get(
            x["product_id"], categories.get(
                normalize_category(by_product[x["product_id"]].category)
                if x["product_id"] in by_product else "",
                default_station(by_product.get(x["product_id"])))),
        "status": "pending",
        "modifiers": [
            {"name": opt.get("name", ""), "group_name": opt.get("group_name", "")}
            for opt in x.get("modifiers", [])],
        "updated_at": None,
    } for x in items]
    return [line for line in result if line["station"] != "skip"]


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
        "printing": "browser_or_ez_print_connector",
    }


@router.get("/routes")
def routes(bid: str, user=Depends(current_user),
           db: Session = Depends(db_session)):
    guard(db, bid, user)
    return {"stations": STATION_LABELS, "route_stations": ROUTE_LABELS,
            "routes": routing(db, bid), "category_routes": category_routing(db, bid),
            "settings": dispatch_settings(db, bid),
            "fallback": "product_override_then_category_then_guess_or_expo"}


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


@router.delete("/routes/{product_id}")
def clear_product_route(bid: str, product_id: str,
                        user=Depends(current_user),
                        db: Session = Depends(db_session)):
    guard(db, bid, user)
    allow(db, bid, user, MANAGE_ROLES)
    exists = db.scalar(select(Product.id).where(
        Product.business_id == bid, Product.id == product_id))
    if not exists:
        fail(404, "Sản phẩm không thuộc doanh nghiệp")
    db.scalar(select(Business).where(Business.id == bid).with_for_update())
    route = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kds_route",
        IndustryWorkItem.reference_id == product_id).with_for_update())
    if route is not None:
        db.delete(route)
        audit(db, bid, user[0].id, "kds.route_cleared", {"product_id": product_id})
        db.commit()
    return {"product_id": product_id, "inherited": True}


@router.delete("/category-routes")
def clear_category_route(bid: str, body: CategoryRouteRemove,
                         user=Depends(current_user),
                         db: Session = Depends(db_session)):
    guard(db, bid, user)
    allow(db, bid, user, MANAGE_ROLES)
    db.scalar(select(Business).where(Business.id == bid).with_for_update())
    key = category_route_key(body.category)
    route = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kds_category_route",
        IndustryWorkItem.reference_id == key).with_for_update())
    if route is not None:
        db.delete(route)
        audit(db, bid, user[0].id, "kds.category_route_cleared", {
            "category": body.category.strip()})
        db.commit()
    return {"category": body.category.strip(), "inherited": True}


@router.put("/category-routes")
def set_category_route(bid: str, body: CategoryRouteUpdate,
                       user=Depends(current_user),
                       db: Session = Depends(db_session)):
    guard(db, bid, user)
    allow(db, bid, user, MANAGE_ROLES)
    category = " ".join(body.category.split())
    exists = db.scalar(select(Product.id).where(
        Product.business_id == bid, Product.category == category))
    if not exists:
        fail(404, "Danh mục không thuộc doanh nghiệp hoặc chưa có sản phẩm")
    db.scalar(select(Business).where(Business.id == bid).with_for_update())
    key = category_route_key(category)
    row = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kds_category_route",
        IndustryWorkItem.reference_id == key).with_for_update())
    if row is None:
        db.add(IndustryWorkItem(
            id=new_id(), business_id=bid, kind="kds_category_route",
            reference_id=key, status="active",
            title="Danh mục trạm • " + category[:125],
            details={"category": category, "station": body.station},
        ))
    else:
        row.details = {"category": category, "station": body.station}
        row.status = "active"
    audit(db, bid, user[0].id, "kds.category_route_changed", {
        "category": category, "station": body.station})
    db.commit()
    return {"category": category, "station": body.station}


@router.put("/settings")
def set_dispatch_settings(bid: str, body: DispatchSettingsUpdate,
                          user=Depends(current_user),
                          db: Session = Depends(db_session)):
    guard(db, bid, user)
    allow(db, bid, user, MANAGE_ROLES)
    db.scalar(select(Business).where(Business.id == bid).with_for_update())
    row = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kds_settings",
        IndustryWorkItem.reference_id == bid).with_for_update())
    if row is None:
        row = IndustryWorkItem(
            id=new_id(), business_id=bid, kind="kds_settings",
            reference_id=bid, status="active", title="Tự động phân trạm",
            details={"auto_dispatch": body.auto_dispatch})
        db.add(row)
    else:
        row.details = {"auto_dispatch": body.auto_dispatch}
    audit(db, bid, user[0].id, "kds.dispatch_setting_changed", {
        "auto_dispatch": body.auto_dispatch})
    db.commit()
    return {"auto_dispatch": body.auto_dispatch}


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



class CallRunner(BaseModel):
    expected_revision: int = Field(ge=0)


class TransferStation(BaseModel):
    expected_revision: int = Field(ge=0)
    station: Literal["bar", "hot", "cold", "expo"]
    reason: str = Field(min_length=4, max_length=160)


def lock_ticket_line(db: Session, bid: str, ticket_id: str, line_id: str):
    """Lock sale order first, then canonical kitchen job, like POS edits/cancel."""
    probe = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.id == ticket_id, IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kitchen"))
    if probe is None:
        fail(404, "Không tìm thấy phiếu")
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.id == probe.reference_id, SaleOrder.business_id == bid
    ).with_for_update())
    if order is None:
        fail(404, "Không tìm thấy đơn")
    job = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.id == ticket_id, IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kitchen").with_for_update())
    if not job or job.reference_id != order.id or job.status == "cancelled" or order.status == "cancelled":
        fail(409, "Phiếu đã bị hủy hoặc thay đổi")
    details = dict(job.details or {})
    lines = [dict(x) for x in (details.get("kds_lines") or ticket_lines(db, bid, order))]
    line = next((x for x in lines if x["id"] == line_id), None)
    if line is None:
        fail(404, "Món không thuộc phiếu")
    return order, job, details, lines, line


@router.post("/tickets/{ticket_id}/lines/{line_id}/call-runner")
def call_runner(bid: str, ticket_id: str, line_id: str, body: CallRunner,
                user=Depends(current_user), db: Session = Depends(db_session)):
    guard(db, bid, user)
    order, job, details, lines, line = lock_ticket_line(db, bid, ticket_id, line_id)
    if line["status"] != "ready":
        fail(409, "Chỉ gọi phục vụ khi món đã sẵn sàng")
    # Internal flag only. No Zalo/SMS/push or third-party acknowledgement.
    if line.get("runner_called_at"):
        return ticket_view(job, order, lines)
    revision = int(details.get("kds_revision", 0))
    if body.expected_revision != revision:
        fail(409, "Phiếu thay đổi ở thiết bị khác")
    line["runner_called_at"] = datetime.now(timezone.utc).isoformat()
    details.update(kds_lines=lines, kds_revision=revision+1)
    job.details = details
    audit(db, bid, user[0].id, "kds.runner_called", {
        "ticket_id": ticket_id, "line_id": line_id, "transport": "internal_flag"})
    db.commit()
    return ticket_view(job, order, lines)


@router.post("/tickets/{ticket_id}/lines/{line_id}/move-station")
def transfer_station(bid: str, ticket_id: str, line_id: str,
                     body: TransferStation, user=Depends(current_user),
                     db: Session = Depends(db_session)):
    guard(db, bid, user)
    allow(db, bid, user, MANAGE_ROLES)
    order, job, details, lines, line = lock_ticket_line(db, bid, ticket_id, line_id)
    revision = int(details.get("kds_revision", 0))
    if body.expected_revision != revision:
        fail(409, "Phiếu thay đổi ở thiết bị khác")
    if line["status"] in ("ready", "served"):
        fail(409, "Không chuyển trạm khi món đã xong")
    old = line["station"]
    if old == body.station:
        return ticket_view(job, order, lines)
    line["station"] = body.station
    line["updated_at"] = datetime.now(timezone.utc).isoformat()
    details.update(kds_lines=lines, kds_revision=revision+1)
    job.details = details
    audit(db, bid, user[0].id, "kds.station_transferred", {
        "ticket_id":ticket_id,"line_id":line_id,"from":old,
        "to":body.station,"reason":body.reason.strip()})
    db.commit()
    return ticket_view(job, order, lines)
