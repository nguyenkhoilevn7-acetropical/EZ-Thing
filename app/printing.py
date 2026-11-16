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
from .models import Branch, SaleOrder, now
from .main import audit, current_user, order_out, tenant
from .team import MANAGE_ROLES, allow

merchant = APIRouter(prefix="/api/businesses/{bid}/printers", tags=["EZ Print"])
device_api = APIRouter(prefix="/api/print", tags=["EZ Print device"])
STATIONS = {"all", "bar", "hot", "cold", "expo", "receipt"}
PROTOCOLS = {"connector_lan", "connector_usb", "cloudprnt"}
STATION_NAMES = {
    "all": "Tất cả phiếu bếp", "bar": "Pha chế", "hot": "Bếp nóng",
    "cold": "Bếp lạnh", "expo": "Ra món", "receipt": "Thu ngân",
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
    station: Literal["all", "bar", "hot", "cold", "expo", "receipt"]
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


def device_out(row: PrintDevice) -> dict:
    return {
        "id": row.id, "branch_id": row.branch_id, "name": row.name,
        "protocol": row.protocol, "station": row.station,
        "enabled": row.enabled, "auto_print": row.auto_print,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "station_label": STATION_NAMES.get(row.station, row.station),
    }


def job_out(row: PrintJob) -> dict:
    return {
        "id": row.id, "device_id": row.device_id,
        "title": row.title, "status": row.status,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
        "printed_at": row.printed_at.isoformat() if row.printed_at else None,
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
                  total: int | None = None) -> str:
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
        out.extend(["-" * 40, f"TOTAL: {int(total):,} VND",
                    "PAYMENT: marked as received (manual)"])
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


def enqueue_receipt(db: Session, bid: str, order: SaleOrder) -> None:
    devices = active_devices(db, bid, order.branch_id, {"receipt"})
    if not devices:
        return
    snapshot = order_out(db, order)
    for device in devices:
        enqueue(db, device, f"paid:{order.id}", "Receipt #" + order.id[:8],
                render_ticket("CUSTOMER RECEIPT", order.id,
                              snapshot["items"], order.note,
                              total=order.total_vnd))


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
