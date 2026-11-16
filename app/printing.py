"""EZ Print: tenant-isolated, persistent printing for local ESC/POS and Star CloudPRNT HTTP.

The cloud API never opens sockets into merchant networks. Credentials are generated
once per device, stored only as SHA-256 hashes, and never included in list APIs.
Queue delivery is at-most-once until a human reviews uncertain/failed jobs.
Physical printer acknowledgement cannot guarantee paper actually exited.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import Branch, DiningTable, Product, SaleOrder, now
from .main import audit, current_user, order_out, tenant
from .team import MANAGE_ROLES, ROLES, allow

merchant = APIRouter(prefix="/api/businesses/{bid}/printers", tags=["EZ Print"])
device_api = APIRouter(prefix="/api/print", tags=["EZ Print device"])
STATIONS = {"all", "bar", "hot", "cold", "expo", "receipt", "packing", "label"}
PROTOCOLS = {"connector_lan", "connector_usb", "cloudprnt"}
STATION_NAMES = {
    "all": "Tất cả phiếu bếp", "bar": "Pha chế", "hot": "Bếp nóng",
    "cold": "Bếp lạnh", "expo": "Ra món", "receipt": "Thu ngân",
    "packing": "Kiểm đồ / đóng gói", "label": "Tem dán ly",
}
MAX_JOBS = 100


class PrintDevice(Base):
    __tablename__ = "print_devices"
    __table_args__ = (Index("ix_print_devices_business_branch", "business_id", "branch_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)
    station: Mapped[str] = mapped_column(String(12), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_print: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PrintJob(Base):
    __tablename__ = "print_jobs"
    __table_args__ = (
        UniqueConstraint("device_id", "event_key", name="uq_print_device_event"),
        Index("ix_print_jobs_claim", "device_id", "status", "created_at"),
        Index("ix_print_jobs_tenant_created", "business_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[str] = mapped_column(ForeignKey("print_devices.id", ondelete="CASCADE"), nullable=False)
    event_key: Mapped[str] = mapped_column(String(140), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    last_error: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PrinterCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    branch_id: str = Field(min_length=1, max_length=36)
    protocol: Literal["connector_lan", "connector_usb", "cloudprnt"]
    station: Literal["all", "bar", "hot", "cold", "expo", "receipt", "packing", "label"]
    auto_print: bool = True


class PrinterUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    station: Literal["all", "bar", "hot", "cold", "expo", "receipt"]
    enabled: bool
    auto_print: bool


class PrintAck(BaseModel):
    job_id: str = Field(min_length=1, max_length=36)
    success: bool
    error: str = Field(default="", max_length=200)


def admin_guard(db: Session, bid: str, user):
    business = tenant(bid, user, db)
    allow(db, bid, user, MANAGE_ROLES)
    return business


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(timezone.utc).isoformat()


def device_out(row: PrintDevice) -> dict:
    return {
        "id": row.id, "branch_id": row.branch_id, "name": row.name,
        "protocol": row.protocol, "station": row.station,
        "enabled": row.enabled, "auto_print": row.auto_print,
        "created_at": iso_utc(row.created_at),
        "last_seen_at": iso_utc(row.last_seen_at),
        "station_label": STATION_NAMES.get(row.station, row.station),
    }


def job_out(row: PrintJob) -> dict:
    return {
        "id": row.id, "device_id": row.device_id,
        "title": row.title, "status": row.status,
        "last_error": row.last_error,
        "created_at": iso_utc(row.created_at),
        "delivered_at": iso_utc(row.delivered_at),
        "printed_at": iso_utc(row.printed_at),
    }


def get_device(db: Session, bid: str, pid: str) -> PrintDevice:
    device = db.scalar(select(PrintDevice).where(
        PrintDevice.id == pid, PrintDevice.business_id == bid))
    if device is None:
        raise HTTPException(404, "Không tìm thấy máy in trong doanh nghiệp")
    return device


def fresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(42)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def device_secret(request: Request, row: PrintDevice, protocol: str):
    auth = request.headers.get("authorization", "")
    token = ""
    if protocol == "cloudprnt" and auth.lower().startswith("basic "):
        try:
            pair = base64.b64decode(auth[6:], validate=True).decode("utf-8")
            username, token = pair.split(":", 1)
            if not hmac.compare_digest(username, row.id):
                token = ""
        except (ValueError, UnicodeDecodeError):
            token = ""
    elif protocol == "connector" and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token or not hmac.compare_digest(
            hashlib.sha256(token.encode()).hexdigest(), row.token_hash):
        raise HTTPException(401, "Device credentials invalid",
                            headers={"WWW-Authenticate": "Basic realm=EZPrint" if protocol == "cloudprnt" else "Bearer"})


def authorized_device(db: Session, request: Request, pid: str, protocol: str) -> PrintDevice:
    row = db.get(PrintDevice, pid)
    if not row or not row.enabled:
        raise HTTPException(401, "Printer unavailable")
    if protocol == "cloudprnt" and row.protocol != "cloudprnt":
        raise HTTPException(404, "Not a CloudPRNT device")
    if protocol == "connector" and row.protocol not in ("connector_lan", "connector_usb"):
        raise HTTPException(404, "Not a local connector")
    device_secret(request, row, protocol)
    row.last_seen_at = now()
    return row


def enqueue(db: Session, device: PrintDevice, event_key: str,
            title: str, content: str) -> None:
    # A job is immutable after creation. Event keys prevent duplicate print
    # when /kds/fire or payment confirmation is requested more than once.
    exists = db.scalar(select(PrintJob.id).where(
        PrintJob.device_id == device.id, PrintJob.event_key == event_key))
    if exists:
        return
    db.add(PrintJob(
        id=str(uuid.uuid4()), business_id=device.business_id,
        device_id=device.id, event_key=event_key, title=title[:160],
        content=content[:12000], status="queued"))


def active_devices(db: Session, bid: str, branch_id: str, stations: set[str]):
    return db.scalars(select(PrintDevice).where(
        PrintDevice.business_id == bid,
        PrintDevice.branch_id == branch_id,
        PrintDevice.enabled.is_(True),
        PrintDevice.auto_print.is_(True),
        PrintDevice.station.in_(stations),
    )).all()


def clean(value: object, limit: int = 200) -> str:
    return " ".join(str(value or "").split())[:limit]


def render_ticket(name: str, order_id: str, lines: list[dict], note: str = "", *,
                  total: int | None = None,
                  payment_note: str = "PAYMENT: marked as received (manual)",
                  breakdown: dict | None = None) -> str:
    # A compact UTF-8, device-neutral receipt snapshot. ESC/POS encoding is
    # performed locally by the connector; CloudPRNT uses supported text/plain.
    out = ["EZ THING", clean(name, 100), "-" * 40, f"ORDER #{order_id[:8].upper()}",
           datetime.now(timezone.utc).strftime("UTC %Y-%m-%d %H:%M"), "-" * 40]
    for line in lines:
        out.append(f"{int(line['quantity'])} x {clean(line['name'], 120)}")
        for extra in line.get("modifiers", []):
            out.append("  + " + clean(extra.get("name", ""), 120))
        if total is not None:
            out.append("    " + f"{int(line.get('total_vnd') or 0):,}" + " VND")
    if note:
        out.extend(["-" * 40, "NOTE: " + clean(note, 250)])
    if total is not None:
        if breakdown:
            out.extend([
                f"SUBTOTAL: {int(breakdown['subtotal_vnd']):,} VND",
                f"DISCOUNT: -{int(breakdown['discount_vnd']):,} VND",
                f"TIP: +{int(breakdown['tip_vnd']):,} VND",
            ])
        out.extend(["-" * 40, f"TOTAL: {int(total):,} VND",
                    clean(payment_note, 120)])
    out.extend(["-" * 40, "EZ Thing POS - Not a tax invoice", "", ""])
    return "\n".join(out)


def enqueue_kitchen(db: Session, bid: str, order: SaleOrder,
                    ticket_id: str, details: dict) -> None:
    lines = details.get("kds_lines") or []
    for device in active_devices(db, bid, order.branch_id,
                                 {"all", "bar", "hot", "cold", "expo"}):
        selected = lines if device.station == "all" else [
            x for x in lines if x.get("station") == device.station]
        if selected:
            enqueue(db, device, f"kds:{ticket_id}", "Kitchen #" + order.id[:8],
                    render_ticket("KITCHEN / " + STATION_NAMES[device.station],
                                  order.id, selected, details.get("note", "")))


def pos_breakdown(db: Session, order: SaleOrder) -> dict | None:
    # POS discount/tip are adjustments on the existing order total, not
    # additional chargeable lines; show them explicitly to avoid false totals.
    from .pos_v7 import POSCheckMeta
    meta = db.scalar(select(POSCheckMeta).where(
        POSCheckMeta.order_id == order.id,
        POSCheckMeta.business_id == order.business_id))
    if meta is None:
        return None
    return {"subtotal_vnd": meta.subtotal_vnd,
            "discount_vnd": meta.discount_vnd, "tip_vnd": meta.tip_vnd}


def enqueue_receipt(db: Session, bid: str, order: SaleOrder) -> None:
    devices = active_devices(db, bid, order.branch_id, {"receipt"})
    if not devices:
        return
    snapshot = order_out(db, order)
    breakdown = pos_breakdown(db, order)
    from .pos_payments import ManualTenderReceipt
    receipt = db.scalar(select(ManualTenderReceipt).where(
        ManualTenderReceipt.business_id == bid,
        ManualTenderReceipt.order_id == order.id))
    payment_note = "PAYMENT: marked received manually; method unspecified"
    if receipt:
        if receipt.method == "cash":
            payment_note = (
                f"CASH (MANUAL) RECEIVED {receipt.cash_received_vnd:,} VND; "
                f"CHANGE {receipt.change_vnd:,} VND"
            )
        elif receipt.method == "bank_transfer":
            payment_note = "BANK TRANSFER (STAFF CONFIRMED; NOT BANK VERIFIED)"
    for device in devices:
        enqueue(db, device, f"paid:{order.id}", "Receipt #" + order.id[:8],
                render_ticket("CUSTOMER RECEIPT", order.id,
                              snapshot["items"], order.note,
                              total=order.total_vnd, breakdown=breakdown,
                              payment_note=payment_note))


def claim_next(db: Session, row: PrintDevice) -> PrintJob | None:
    # Do not silently retry ambiguous jobs: a connector/physical printer may
    # have succeeded but lost its acknowledgement.
    waiting = db.scalar(select(PrintJob).where(
        PrintJob.device_id == row.id, PrintJob.status == "queued")
        .order_by(PrintJob.created_at, PrintJob.id)
        .with_for_update(skip_locked=True).limit(1))
    if waiting:
        waiting.status = "offered"
        waiting.delivered_at = now()
    return waiting


@merchant.get("")
def list_printers(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    admin_guard(db, bid, user)
    rows = db.scalars(select(PrintDevice).where(
        PrintDevice.business_id == bid).order_by(PrintDevice.created_at)).all()
    return {"devices": [device_out(x) for x in rows],
            "protocols": sorted(PROTOCOLS), "stations": STATION_NAMES}


@merchant.post("", status_code=201)
def create_printer(bid: str, body: PrinterCreate,
                   user=Depends(current_user), db: Session = Depends(db_session)):
    admin_guard(db, bid, user)
    if not db.scalar(select(Branch.id).where(
            Branch.id == body.branch_id, Branch.business_id == bid)):
        raise HTTPException(404, "Chi nhánh không thuộc doanh nghiệp")
    raw, digest = fresh_token()
    row = PrintDevice(id=str(uuid.uuid4()), business_id=bid, branch_id=body.branch_id,
                      name=body.name.strip(), protocol=body.protocol, station=body.station,
                      auto_print=body.auto_print, token_hash=digest)
    db.add(row)
    audit(db, bid, user[0].id, "print.device_created",
          {"id": row.id, "protocol": row.protocol, "station": row.station})
    db.commit()
    return {**device_out(row), "device_token_once": raw,
            "cloudprnt_path": f"/api/print/cloudprnt/{row.id}" if row.protocol == "cloudprnt" else None,
            "connector_path": f"/api/print/connector/{row.id}" if row.protocol != "cloudprnt" else None}


@merchant.put("/{pid}")
def update_printer(bid: str, pid: str, body: PrinterUpdate,
                   user=Depends(current_user), db: Session = Depends(db_session)):
    admin_guard(db, bid, user)
    row = get_device(db, bid, pid)
    row.name, row.station = body.name.strip(), body.station
    row.enabled, row.auto_print = body.enabled, body.auto_print
    audit(db, bid, user[0].id, "print.device_updated", {"id": pid, "enabled": row.enabled})
    db.commit()
    return device_out(row)


@merchant.post("/{pid}/rotate-key")
def rotate_token(bid: str, pid: str, user=Depends(current_user),
                 db: Session = Depends(db_session)):
    admin_guard(db, bid, user)
    row = get_device(db, bid, pid)
    raw, digest = fresh_token()
    row.token_hash = digest
    audit(db, bid, user[0].id, "print.credentials_rotated", {"id": pid})
    db.commit()
    return {"device_id": pid, "device_token_once": raw}


@merchant.post("/{pid}/test", status_code=201)
def test_print(bid: str, pid: str, user=Depends(current_user),
               db: Session = Depends(db_session)):
    admin_guard(db, bid, user)
    device = get_device(db, bid, pid)
    if not device.enabled:
        raise HTTPException(409, "Máy in đang bị tắt")
    enqueue(db, device, "test:" + str(uuid.uuid4()), "Test print",
            render_ticket("PRINT CONNECTION TEST", "TEST-" + str(uuid.uuid4()),
                          [{"quantity": 1, "name": "EZ Thing is ready"}]))
    audit(db, bid, user[0].id, "print.test_queued", {"id": pid})
    db.commit()
    return {"queued": True, "device_id": pid,
            "message": "Queued for device; success requires physical acknowledgement"}


@merchant.get("/jobs")
def list_jobs(bid: str, device_id: str | None = None,
              user=Depends(current_user), db: Session = Depends(db_session)):
    admin_guard(db, bid, user)
    stmt = select(PrintJob).where(PrintJob.business_id == bid)
    if device_id:
        get_device(db, bid, device_id)
        stmt = stmt.where(PrintJob.device_id == device_id)
    rows = db.scalars(stmt.order_by(PrintJob.created_at.desc()).limit(MAX_JOBS)).all()
    return {"jobs": [job_out(x) for x in rows]}


@merchant.post("/jobs/{jid}/retry")
def retry_job(bid: str, jid: str, user=Depends(current_user),
              db: Session = Depends(db_session)):
    admin_guard(db, bid, user)
    row = db.scalar(select(PrintJob).where(
        PrintJob.id == jid, PrintJob.business_id == bid).with_for_update())
    if not row:
        raise HTTPException(404, "Không tìm thấy lệnh in")
    if row.status not in ("failed", "offered"):
        raise HTTPException(409, "Chỉ cho phép in lại phiếu lỗi hoặc chưa nhận xác nhận")
    device = get_device(db, bid, row.device_id)
    if not device.enabled:
        raise HTTPException(409, "Máy in đang bị tắt")
    # Resetting an uncertain job can print a second physical copy; explicit
    # manager action and audit are mandatory.
    row.status, row.delivered_at, row.last_error = "queued", None, ""
    audit(db, bid, user[0].id, "print.manual_retry", {"job_id": jid})
    db.commit()
    return job_out(row)


@device_api.get("/connector/{pid}/next")
def connector_next(pid: str, request: Request, db: Session = Depends(db_session)):
    device = authorized_device(db, request, pid, "connector")
    row = claim_next(db, device)
    db.commit()
    return {"job": ({"id": row.id, "content": row.content, "title": row.title}
                    if row else None), "poll_after_seconds": 3}


@device_api.post("/connector/{pid}/ack")
def connector_ack(pid: str, body: PrintAck, request: Request,
                  db: Session = Depends(db_session)):
    device = authorized_device(db, request, pid, "connector")
    row = db.scalar(select(PrintJob).where(
        PrintJob.device_id == device.id, PrintJob.id == body.job_id).with_for_update())
    if not row:
        raise HTTPException(404, "Unknown print job")
    if row.status == "printed" and body.success:
        return {"ok": True, "status": "printed"}
    if row.status != "offered":
        raise HTTPException(409, "Print job not awaiting acknowledgement")
    row.status = "printed" if body.success else "failed"
    row.last_error = "" if body.success else clean(body.error or "Local printer error", 200)
    row.printed_at = now() if body.success else None
    db.commit()
    return {"ok": True, "status": row.status}


@device_api.post("/cloudprnt/{pid}")
async def cloud_poll(pid: str, request: Request, db: Session = Depends(db_session)):
    device = authorized_device(db, request, pid, "cloudprnt")
    raw = await request.body()
    if len(raw) > 32768:
        raise HTTPException(413, "Status payload too large")
    try:
        status = json.loads(raw) if raw else {}
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid CloudPRNT status JSON")
    if not isinstance(status, dict):
        raise HTTPException(400, "Invalid CloudPRNT status object")
    # In-progress or faulted devices must not be offered another print job.
    if status.get("printingInProgress") is True or str(status.get("statusCode", "200")).startswith(("4", "5")):
        db.commit()
        return {"jobReady": False}
    existing = db.scalar(select(PrintJob).where(
        PrintJob.device_id == device.id, PrintJob.status == "offered")
        .order_by(PrintJob.created_at).limit(1))
    if existing:
        db.commit()
        return {"jobReady": False}
    row = claim_next(db, device)
    db.commit()
    return ({"jobReady": True, "mediaTypes": ["text/plain"],
             "jobToken": row.id} if row else {"jobReady": False})


@device_api.get("/cloudprnt/{pid}")
def cloud_download(pid: str, request: Request, uid: str | None = None,
                   type: str = Query(default="text/plain"), token: str | None = None,
                   db: Session = Depends(db_session)):
    device = authorized_device(db, request, pid, "cloudprnt")
    if type != "text/plain":
        raise HTTPException(415, "Only text/plain is supported by this adapter")
    row = db.scalar(select(PrintJob).where(
        PrintJob.device_id == pid, PrintJob.status == "offered")
        .order_by(PrintJob.created_at).limit(1))
    if not row or (token is not None and token != row.id):
        raise HTTPException(404, "No active print job")
    db.commit()
    return Response(content=row.content.encode("utf-8"), media_type="text/plain")


@device_api.delete("/cloudprnt/{pid}")
def cloud_confirm(pid: str, request: Request,
                  code: str = Query(default=""), token: str | None = None,
                  db: Session = Depends(db_session)):
    device = authorized_device(db, request, pid, "cloudprnt")
    # Token-capable clients identify the job; older firmware provides none.
    stmt = select(PrintJob).where(PrintJob.device_id == pid)
    if token:
        # Token-aware devices can confirm their exact job, including retries.
        stmt = stmt.where(PrintJob.id == token)
    else:
        # Legacy devices omit job tokens: only their *currently offered* job
        # can be confirmed. Selecting latest historical job is incorrect and
        # can silently mark the wrong receipt as printed.
        stmt = stmt.where(PrintJob.status == "offered")
    row = db.scalar(stmt.order_by(PrintJob.delivered_at, PrintJob.id).with_for_update().limit(1))
    if row is None:
        if not token:
            # No outstanding work. An old firmware may repeat DELETE after
            # receiving a timeout; treat as no-op, never mark another job.
            db.commit()
            return Response(status_code=200)
        raise HTTPException(404, "No print job to confirm")
    success = code.strip().upper() in ("OK", "200 OK", "200")
    if row.status in ("printed", "failed"):
        return Response(status_code=200)  # CloudPRNT retries DELETE on lost replies.
    if row.status != "offered":
        raise HTTPException(409, "Job was not offered")
    row.status = "printed" if success else "failed"
    row.last_error = "" if success else clean(code or "CloudPRNT reported error")
    row.printed_at = now() if success else None
    db.commit()
    return Response(status_code=200)

# Manual operational printouts: Sapo/iPOS parity without a second order ledger.
class ManualDocument(BaseModel):
    kind: Literal["prebill", "packing", "cup_label", "receipt"]
    device_id: str = Field(min_length=1, max_length=36)
    request_id: str = Field(min_length=12, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


DOCUMENT_STATIONS = {
    "prebill": {"receipt"},
    "receipt": {"receipt"},
    "packing": {"receipt", "packing", "expo"},
    "cup_label": {"bar", "label"},
}


def document_order(db: Session, bid: str, oid: str) -> SaleOrder:
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.business_id == bid, SaleOrder.id == oid))
    if not order:
        raise HTTPException(404, "Đơn hàng không thuộc doanh nghiệp")
    if order.status == "cancelled":
        raise HTTPException(409, "Không in chứng từ cho đơn đã hủy")
    return order


def documents_for_order(db: Session, bid: str, order: SaleOrder,
                        kind: str) -> list[dict]:
    if kind not in DOCUMENT_STATIONS:
        raise HTTPException(422, "Loại phiếu không được hỗ trợ")
    if kind == "prebill" and order.status != "open":
        raise HTTPException(409, "Chỉ in tạm tính cho đơn chưa thanh toán")
    if kind == "receipt" and order.status != "paid":
        raise HTTPException(409, "Chỉ in lại phiếu thanh toán cho đơn đã nhận tiền")
    if kind == "cup_label":
        from .models import Business
        business = db.scalar(select(Business).where(Business.id == bid))
        if not business or business.industry != "fnb":
            raise HTTPException(404, "Tem dán ly chỉ áp dụng cho nhà hàng/cafe")

    snapshot = order_out(db, order)
    table = None
    if order.table_id:
        table = db.scalar(select(DiningTable).where(
            DiningTable.id == order.table_id,
            DiningTable.business_id == bid,
            DiningTable.branch_id == order.branch_id))
    table_label = clean(table.label, 50) if table else "Mang di / Delivery"
    order_ref = order.id[:8].upper()
    if kind == "prebill":
        return [{"title": "Tam tinh #" + order_ref,
                 "content": render_ticket("PHIEU TAM TINH | " + table_label,
                                          order.id, snapshot["items"], order.note,
                                          total=order.total_vnd,
                                          payment_note="CHUA THANH TOAN - NOT PAID",
                                          breakdown=pos_breakdown(db, order))}]
    if kind == "receipt":
        return [{"title": "Ban sao thanh toan #" + order_ref,
                 "content": render_ticket("BAN SAO PHIEU THANH TOAN | " + table_label,
                                          order.id, snapshot["items"], order.note,
                                          total=order.total_vnd,
                                          breakdown=pos_breakdown(db, order))}]
    if kind == "packing":
        lines = [{
            "quantity": line["quantity"],
            "name": "[  ] " + clean(line["name"]),
            "modifiers": line.get("modifiers", []),
        } for line in snapshot["items"]]
        content = render_ticket("PHIEU KIEM DO | " + table_label,
                                order.id, lines, order.note)
        content += "\n[  ] DA KIEM / VERIFIED\n[  ] DA DONG GOI / PACKED\n"
        return [{"title": "Kiem do #" + order_ref, "content": content}]

    # Beverage cup labels: one immutable print job for each cup so the
    # local ESC/POS cutter separates labels rather than one uncut strip.
    # Product routing follows KDS's current station for an unfired order,
    # or the canonical ticket snapshot once it has been fired.
    from .kds import default_station, routing
    from .workflows import IndustryWorkItem
    job = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "kitchen",
        IndustryWorkItem.reference_id == order.id))
    kds_lines = (job.details or {}).get("kds_lines") if job else None
    if kds_lines is not None:
        beverage_ids = {line["id"] for line in kds_lines if line.get("station") == "bar"}
    else:
        products = db.scalars(select(Product).where(
            Product.business_id == bid,
            Product.id.in_([line["product_id"] for line in snapshot["items"]]))).all()
        by_product = {p.id: p for p in products}
        routes = routing(db, bid)
        beverage_ids = {
            line["id"] for line in snapshot["items"]
            if routes.get(line["product_id"], default_station(
                by_product.get(line["product_id"]))) == "bar"}
    beverages = [line for line in snapshot["items"] if line["id"] in beverage_ids]
    total_cups = sum(line["quantity"] for line in beverages)
    if not total_cups:
        raise HTTPException(409, "Đơn chưa có đồ uống được phân vào quầy pha chế")
    if total_cups > 40:
        raise HTTPException(422, "Tối đa 40 tem cho một lần in. Hãy chia đơn")

    documents = []
    count = 0
    for line in beverages:
        modifiers = [
            clean((opt.get("group_name", "") + ": " if opt.get("group_name") else "")
                  + opt.get("name", ""), 120)
            for opt in line.get("modifiers", [])]
        for unit in range(line["quantity"]):
            count += 1
            content = "\n".join([
                "EZ THING | CUP LABEL",
                "-" * 32,
                "ORDER #" + order_ref,
                "BAN / TABLE: " + table_label,
                "LY / CUP: " + str(count) + "/" + str(total_cups),
                clean(line["name"], 120),
                *["+" + extra for extra in modifiers],
                "NOTE: " + clean(order.note, 250) if order.note else "",
                "-" * 32, "", "",
            ])
            documents.append({
                "title": "Tem ly #" + order_ref + " " + str(count) + "/" + str(total_cups),
                "content": content,
            })
    return documents


def available_document_devices(db: Session, bid: str, order: SaleOrder, kind: str):
    return db.scalars(select(PrintDevice).where(
        PrintDevice.business_id == bid,
        PrintDevice.branch_id == order.branch_id,
        PrintDevice.enabled.is_(True),
        PrintDevice.station.in_(DOCUMENT_STATIONS[kind]))).all()


@merchant.get("/documents/{oid}/preview")
def preview_document(bid: str, oid: str,
                     kind: Literal["prebill", "packing", "cup_label", "receipt"] = "prebill",
                     user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    allow(db, bid, user, ROLES)
    order = document_order(db, bid, oid)
    docs = documents_for_order(db, bid, order, kind)
    devices = available_document_devices(db, bid, order, kind)
    return {
        "order_id": order.id,
        "kind": kind,
        "documents": docs,
        "available_devices": [{"id": x.id, "name": x.name,
                               "protocol": x.protocol, "station": x.station}
                              for x in devices],
        "tax_invoice": False,
        "status": "preview_only",
    }


@merchant.post("/documents/{oid}/print", status_code=201)
def print_document(bid: str, oid: str, body: ManualDocument,
                   user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    allow(db, bid, user, ROLES)
    order = document_order(db, bid, oid)
    device = db.scalar(select(PrintDevice).where(
        PrintDevice.id == body.device_id,
        PrintDevice.business_id == bid,
        PrintDevice.branch_id == order.branch_id,
        PrintDevice.enabled.is_(True)).with_for_update())
    if device is None:
        raise HTTPException(404, "Máy in không thuộc chi nhánh hoặc đã tắt")
    if device.station not in DOCUMENT_STATIONS[body.kind]:
        raise HTTPException(409, "Máy in không được gán cho loại chứng từ này")
    docs = documents_for_order(db, bid, order, body.kind)
    keys = [
        "manual:" + body.kind + ":" + oid + ":" + body.request_id + ":" + str(index)
        for index in range(len(docs))
    ]
    existing = db.scalars(select(PrintJob.event_key).where(
        PrintJob.device_id == device.id, PrintJob.event_key.in_(keys))).all()
    if existing:
        if len(existing) != len(keys):
            raise HTTPException(409, "Yêu cầu in trước đó chưa được ghi đầy đủ")
        return {"queued": True, "device_id": device.id, "kind": body.kind,
                "document_count": len(docs), "request_id": body.request_id,
                "replayed": True}
    for index, document in enumerate(docs):
        enqueue(db, device, keys[index], document["title"], document["content"])
    # Device row lock serializes repeat requests; the DB unique index is the
    # last line of defence when multiple application workers race.
    try:
        db.flush()
        queued_count = db.scalar(select(PrintJob.id).where(
            PrintJob.device_id == device.id, PrintJob.event_key == keys[0]))
        if queued_count is None:
            raise HTTPException(409, "Không thể lưu lệnh in")
        audit(db, bid, user[0].id, "print.manual_document",
              {"order_id": oid, "device_id": device.id,
               "kind": body.kind, "request_id": body.request_id,
               "document_count": len(docs)})
        db.commit()
    except IntegrityError:
        db.rollback()
        # Two requests using the same idempotency key can race on SQLite.
        # Check the committed queue; never blindly enqueue a second copy.
        present = db.scalars(select(PrintJob.event_key).where(
            PrintJob.device_id == device.id, PrintJob.event_key.in_(keys))).all()
        if len(present) != len(keys):
            raise HTTPException(409, "Lệnh in đang được xử lý ở thiết bị khác")
    return {"queued": True, "device_id": device.id, "kind": body.kind,
            "document_count": len(docs), "request_id": body.request_id,
            "replayed": False}
