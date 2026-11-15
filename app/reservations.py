"""F&B reservations and contact inbox for EZ Thing pilot.

All public writes are STAGING DEMO only and scoped to the visitor's own tenant.
Uses industry_work_items (no new database table). Never sends SMS or charges deposits.
"""
import hashlib
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .database import db_session
from .models import AuditEvent, Branch, Business, Customer, DiningTable, Membership, now
from .workflows import IndustryWorkItem
from .main import current_user, fail, feature, new_id, tenant
from .public import preview_scope

router = APIRouter(prefix="/api", tags=["F&B reservations"])
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
BUSY = ("pending", "confirmed", "seated")
STATUS_NEXT = {
    "pending": ("confirmed", "cancelled"),
    "confirmed": ("seated", "cancelled", "no_show"),
    "seated": ("completed",),
}
PHONE = re.compile(r"^[0-9+().\s-]{8,25}$")


class ReservationCreate(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    customer_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=8, max_length=25)
    party_size: int = Field(ge=1, le=20)
    start_at: datetime
    duration_minutes: Literal[60, 90, 120] = 90
    table_id: str | None = None
    zone_id: str | None = Field(default=None, max_length=32)
    branch_id: str | None = Field(default=None, max_length=36)
    note: str = Field(default="", max_length=240)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str):
        if not PHONE.fullmatch(value.strip()):
            raise ValueError("Số điện thoại không hợp lệ")
        return value.strip()

    @field_validator("start_at")
    @classmethod
    def valid_time(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Cần cung cấp giờ có múi giờ")
        return value


class ContactUpdate(BaseModel):
    phone: str = Field(default="", max_length=25)
    email: EmailStr | None = None
    address: str = Field(default="", max_length=200)
    hours: str = Field(default="08:00 – 22:00", max_length=100)

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value):
        value = value.strip()
        if value and not PHONE.fullmatch(value):
            raise ValueError("Số điện thoại liên hệ không hợp lệ")
        return value


class ReservationPolicy(BaseModel):
    """Owner-controlled booking rules; stored in the tenant's existing setup JSON.

    Times use Asia/Ho_Chi_Minh local time and 30-minute increments. All new
    reservations are enforced on the server, not just filtered in the UI.
    """
    open_time: str = Field(default="08:00", pattern=r"^(?:[01]\d|2[0-3]):(?:00|30)$")
    last_seating_time: str = Field(default="20:30", pattern=r"^(?:[01]\d|2[0-3]):(?:00|30)$")
    close_time: str = Field(default="22:00", pattern=r"^(?:[01]\d|2[0-3]):(?:00|30)$")
    closed_weekdays: list[int] = Field(default_factory=list, max_length=7)
    blocked_dates: list[date] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def check_schedule(self):
        if not self.open_time < self.last_seating_time < self.close_time:
            raise ValueError("Giờ mở cửa, giờ nhận khách cuối và giờ đóng cửa phải tăng dần")
        if any(day < 0 or day > 6 for day in self.closed_weekdays):
            raise ValueError("Thứ trong tuần phải từ 0 (thứ Hai) đến 6 (Chủ Nhật)")
        if len(set(self.closed_weekdays)) != len(self.closed_weekdays):
            raise ValueError("Không được lặp ngày nghỉ hàng tuần")
        if len(set(self.blocked_dates)) != len(self.blocked_dates):
            raise ValueError("Không được lặp ngày chặn đặt bàn")
        return self


class InquiryCreate(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=8, max_length=25)
    message: str = Field(min_length=5, max_length=500)

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value):
        if not PHONE.fullmatch(value.strip()):
            raise ValueError("Số điện thoại không hợp lệ")
        return value.strip()


class ReservationStatus(BaseModel):
    status: Literal["confirmed", "seated", "completed", "cancelled", "no_show"]


class InquiryStatus(BaseModel):
    status: Literal["contacted", "closed"]


def fnb_scope(bid, user, db):
    b = tenant(bid, user, db)
    if b.industry != "fnb":
        fail(404, "Chỉ áp dụng cho nhà hàng và cafe")
    feature(b, "tables")  # existing tenant entitlements, incl. older F&B accounts
    return b


def ensure_owner(db, bid, user):
    membership = db.scalar(select(Membership).where(Membership.business_id == bid,
                                                      Membership.user_id == user[0].id))
    if not membership or membership.role != "owner":
        fail(403, "Chỉ chủ doanh nghiệp được thay đổi thông tin liên hệ")


def contact_of(b):
    cfg = (b.setup or {}).get("contact") or {}
    return {"phone": cfg.get("phone") or "", "email": cfg.get("email") or "",
            "address": cfg.get("address") or "",
            "hours": cfg.get("hours") or "08:00 – 22:00"}


def policy_of(b):
    config = (b.setup or {}).get("reservation_policy") if b else None
    return ReservationPolicy.model_validate(config or {}).model_dump(mode="json")


def closed_reason(policy, day):
    if day.weekday() in policy["closed_weekdays"]:
        return "Nhà hàng không nhận đặt bàn vào thứ này"
    if day.isoformat() in policy["blocked_dates"]:
        return "Nhà hàng tạm ngưng nhận đặt bàn vào ngày đã chọn"
    return None


def reservation_out(row):
    d = row.details or {}
    return {"id": row.id, "status": row.status, "customer_name": d.get("customer_name", ""),
            "phone": d.get("phone", ""), "party_size": d.get("party_size", 0),
            "table_id": d.get("table_id", ""), "table_label": d.get("table_label", ""),
            "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
            "ends_at": row.ends_at.isoformat() if row.ends_at else None,
            "note": d.get("note", ""), "source": d.get("source", "merchant"),
            "created_at": row.created_at.isoformat()}


def inquiry_out(row):
    d = row.details or {}
    return {"id": row.id, "name": d.get("name", ""), "phone": d.get("phone", ""),
            "message": d.get("message", ""), "status": row.status,
            "created_at": row.created_at.isoformat()}


def valid_start(start, duration, business=None):
    local = start.astimezone(TZ)
    today = datetime.now(TZ).date()
    if local.date() < today or local.date() > today + timedelta(days=30):
        fail(422, "Chỉ nhận đặt bàn trong 30 ngày tới")
    if local.minute not in (0, 30) or local.second or local.microsecond:
        fail(422, "Giờ đặt bàn phải theo bước 30 phút")
    policy = policy_of(business)
    if reason := closed_reason(policy, local.date()):
        fail(422, reason)
    if not (time.fromisoformat(policy["open_time"]) <= local.time()
            <= time.fromisoformat(policy["last_seating_time"])):
        fail(422, "Giờ đến ngoài khung giờ nhận khách của nhà hàng")
    if start.astimezone(timezone.utc) < now() + timedelta(minutes=30):
        fail(422, "Cần đặt bàn trước tối thiểu 30 phút")
    end = start.astimezone(timezone.utc) + timedelta(minutes=duration)
    if (end.astimezone(TZ).date() != local.date()
            or end.astimezone(TZ).time() > time.fromisoformat(policy["close_time"])):
        fail(422, "Giờ kết thúc vượt giờ đóng cửa của nhà hàng")
    return start.astimezone(timezone.utc), end


def day_valid(day):
    today = datetime.now(TZ).date()
    if not today <= day <= today + timedelta(days=30):
        fail(422, "Chỉ nhận đặt bàn trong 30 ngày tới")


def eligible_area_tables(db, business, zone_id=None, branch_id=None):
    """Return only tables in the requested tenant/branch/area.

    Floorplan placement is server-owned metadata; client-submitted zone/table
    associations must never be trusted.
    """
    if not zone_id and not branch_id:
        return None
    branch_query = select(Branch).where(Branch.business_id == business.id)
    if branch_id:
        branch_query = branch_query.where(Branch.id == branch_id)
    else:
        branch_query = branch_query.order_by(Branch.created_at, Branch.id)
    branch = db.scalar(branch_query)
    if branch is None:
        fail(422, "Chi nhánh không hợp lệ")
    from .floorplan import effective
    layout = effective(business, branch, db)
    if zone_id and not any(z["id"] == zone_id for z in layout["zones"]):
        fail(422, "Khu vực đặt bàn không hợp lệ")
    return {t["id"] for t in layout["tables"]
            if not zone_id or t["placement"]["zone_id"] == zone_id}


def free_tables(db, bid, start, end, party_size, requested_table=None, allowed_ids=None):
    tables = db.scalars(select(DiningTable).where(DiningTable.business_id == bid,
                                                 DiningTable.seats >= party_size)
                       .order_by(DiningTable.seats, DiningTable.label)).all()
    overlaps = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind.in_(("reservations", "waitlist")),
        IndustryWorkItem.status.in_(BUSY),
        IndustryWorkItem.scheduled_at < end,
        IndustryWorkItem.ends_at > start)).all()
    taken = {(w.details or {}).get("table_id") for w in overlaps}
    return [t for t in tables if t.id not in taken and
            (requested_table is None or t.id == requested_table) and
            (allowed_ids is None or t.id in allowed_ids)]


def availability(db, b, day, party_size, duration, requested_table=None, allowed_ids=None):
    day_valid(day)
    policy = policy_of(b)
    reason = closed_reason(policy, day)
    if reason:
        return {"date": day.isoformat(), "party_size": party_size,
                "duration_minutes": duration, "slots": [],
                "closed_reason": reason, "timezone": "Asia/Ho_Chi_Minh"}
    output = []
    start_hour = int(policy["open_time"][:2])
    last_hour = int(policy["last_seating_time"][:2])
    for hour in range(start_hour, last_hour + 1):
        for minute in (0, 30):
            start = datetime.combine(day, time(hour, minute), tzinfo=TZ)
            try:
                first, end = valid_start(start, duration, b)
            except Exception as err:
                # Time validation is intentionally reused for unavailable slots.
                from fastapi import HTTPException
                if not isinstance(err, HTTPException):
                    raise
                continue
            count = len(free_tables(db, b.id, first, end, party_size, requested_table, allowed_ids))
            output.append({"start_at": start.isoformat(), "available_tables": count,
                           "available": count > 0})
    return {"date": day.isoformat(), "party_size": party_size,
            "duration_minutes": duration, "slots": output, "timezone": "Asia/Ho_Chi_Minh"}


def lock_capacity(db, bid):
    if db.bind and db.bind.dialect.name == "postgresql":
        number = int.from_bytes(hashlib.sha256(("reservation|" + bid).encode()).digest()[:8],
                                "big", signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": number})


def create_reservation(db, b, body, actor_id, source):
    reference = hashlib.sha256((source + "|" + b.id + "|" + body.request_id).encode()).hexdigest()[:36]
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode="json"),
                                             ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    lock_capacity(db, b.id)
    existing = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == b.id, IndustryWorkItem.kind == "reservations",
        IndustryWorkItem.reference_id == reference))
    if existing:
        if (existing.details or {}).get("fingerprint") != fingerprint:
            fail(409, "Mã yêu cầu đã dùng cho lượt đặt khác")
        return reservation_out(existing)
    # Resolve request idempotency before enforcing changed opening hours.
    # A retry must not lose access to the previously accepted reservation.
    start, end = valid_start(body.start_at, body.duration_minutes, b)
    total = db.scalars(select(IndustryWorkItem.id).where(
        IndustryWorkItem.business_id == b.id,
        IndustryWorkItem.kind == "reservations")).all()
    if source == "demo" and len(total) >= 50:
        fail(429, "Phiên DEMO đã đạt giới hạn đặt bàn")
    if source != "merchant" and (body.zone_id or body.branch_id):
        fail(422, "Khu vực chỉ dành cho người quản lý")
    allowed_ids = eligible_area_tables(db, b, body.zone_id, body.branch_id)
    if body.table_id and allowed_ids is not None and body.table_id not in allowed_ids:
        fail(422, "Bàn không thuộc khu vực hoặc chi nhánh được chọn")
    candidates = free_tables(db, b.id, start, end, body.party_size, body.table_id, allowed_ids)
    if not candidates:
        fail(409, "Không còn bàn phù hợp trong khung giờ này")
    table = candidates[0]
    customer = Customer(id=new_id(), business_id=b.id, name=body.customer_name.strip(),
                        phone=body.phone, address="")
    db.add(customer)
    db.flush()
    item = IndustryWorkItem(
        id=new_id(), business_id=b.id, kind="reservations", reference_id=reference,
        customer_id=customer.id, title=f"Đặt bàn • {body.customer_name.strip()}",
        status="pending", scheduled_at=start, ends_at=end,
        details={"customer_name": body.customer_name.strip(), "phone": body.phone,
                 "party_size": body.party_size, "table_id": table.id,
                 "table_label": table.label, "note": body.note.strip(),
                 "zone_id": body.zone_id, "branch_id": table.branch_id,
                 "fingerprint": fingerprint, "source": source})
    db.add(item)
    db.add(AuditEvent(id=new_id(), business_id=b.id, actor_id=actor_id,
                      action="reservation.created",
                      payload=json.dumps({"id": item.id, "source": source, "table": table.id})))
    db.commit()
    return reservation_out(item)


@router.get("/businesses/{bid}/reservations")
def merchant_reservations(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = fnb_scope(bid, user, db)
    records = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == b.id, IndustryWorkItem.kind == "reservations")
        .order_by(IndustryWorkItem.scheduled_at.desc()).limit(150)).all()
    return [reservation_out(w) for w in records]


@router.post("/businesses/{bid}/reservations", status_code=201)
def merchant_book(bid: str, body: ReservationCreate,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    b = fnb_scope(bid, user, db)
    return create_reservation(db, b, body, user[0].id, "merchant")


@router.post("/businesses/{bid}/reservations/{rid}/status")
def update_reservation(bid: str, rid: str, body: ReservationStatus,
                       user=Depends(current_user), db: Session = Depends(db_session)):
    b = fnb_scope(bid, user, db)
    rec = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.id == rid, IndustryWorkItem.business_id == b.id,
        IndustryWorkItem.kind == "reservations"))
    if rec is None:
        fail(404, "Không tìm thấy lượt đặt")
    if body.status not in STATUS_NEXT.get(rec.status, ()):
        fail(409, "Không thể chuyển sang trạng thái yêu cầu")
    rec.status = body.status
    db.add(AuditEvent(id=new_id(), business_id=b.id, actor_id=user[0].id,
                      action="reservation.status",
                      payload=json.dumps({"id": rid, "status": body.status})))
    db.commit()
    return reservation_out(rec)


@router.get("/businesses/{bid}/reservations/availability")
def merchant_slots(bid: str, day: date = Query(...), party_size: int = Query(ge=1, le=20),
                   duration_minutes: int = Query(default=90, ge=60, le=120),
                   table_id: str | None = Query(default=None, max_length=36),
                   zone_id: str | None = Query(default=None, max_length=32),
                   branch_id: str | None = Query(default=None, max_length=36),
                   user=Depends(current_user), db: Session = Depends(db_session)):
    if duration_minutes not in (60, 90, 120):
        fail(422, "Thời lượng chỉ hỗ trợ 60, 90 hoặc 120 phút")
    business = fnb_scope(bid, user, db)
    allowed_ids = eligible_area_tables(db, business, zone_id, branch_id)
    if table_id and db.scalar(select(DiningTable.id).where(
            DiningTable.business_id == bid, DiningTable.id == table_id)) is None:
        fail(404, "Bàn không thuộc nhà hàng")
    if table_id and allowed_ids is not None and table_id not in allowed_ids:
        fail(422, "Bàn không thuộc khu vực hoặc chi nhánh được chọn")
    return availability(db, business, day, party_size, duration_minutes,
                        table_id, allowed_ids)


@router.get("/preview/cafe/reservations/availability")
def demo_slots(day: date = Query(...), party_size: int = Query(ge=1, le=20),
               duration_minutes: int = Query(default=90, ge=60, le=120),
               user=Depends(current_user), db: Session = Depends(db_session)):
    if duration_minutes not in (60, 90, 120):
        fail(422, "Thời lượng chỉ hỗ trợ 60, 90 hoặc 120 phút")
    b = preview_scope(db, user, "cafe")
    return availability(db, b, day, party_size, duration_minutes)


@router.post("/preview/cafe/reservations", status_code=201)
def customer_book(body: ReservationCreate, user=Depends(current_user),
                  db: Session = Depends(db_session)):
    b = preview_scope(db, user, "cafe")
    if body.table_id:
        fail(422, "Khách hàng chỉ chọn số người và giờ, nhà hàng tự xếp bàn")
    return create_reservation(db, b, body, user[0].id, "demo")


@router.get("/businesses/{bid}/reservations/policy")
def merchant_reservation_policy(bid: str, user=Depends(current_user),
                                db: Session = Depends(db_session)):
    return policy_of(fnb_scope(bid, user, db))


@router.put("/businesses/{bid}/reservations/policy")
def save_reservation_policy(bid: str, body: ReservationPolicy,
                            user=Depends(current_user), db: Session = Depends(db_session)):
    business = fnb_scope(bid, user, db)
    ensure_owner(db, bid, user)
    setup = dict(business.setup or {})
    setup["reservation_policy"] = body.model_dump(mode="json")
    business.setup = setup
    db.add(AuditEvent(id=new_id(), business_id=business.id, actor_id=user[0].id,
                      action="restaurant.reservation_policy.updated", payload="{}"))
    db.commit()
    return policy_of(business)


@router.get("/preview/cafe/reservations/policy")
def demo_reservation_policy(user=Depends(current_user), db: Session = Depends(db_session)):
    # Read-only public-safe values; no merchant/private data is exposed.
    return policy_of(preview_scope(db, user, "cafe"))


@router.get("/businesses/{bid}/reservations/contact")
def merchant_contact(bid: str, user=Depends(current_user),
                     db: Session = Depends(db_session)):
    return contact_of(fnb_scope(bid, user, db))


@router.put("/businesses/{bid}/reservations/contact")
def save_contact(bid: str, body: ContactUpdate, user=Depends(current_user),
                 db: Session = Depends(db_session)):
    b = fnb_scope(bid, user, db)
    ensure_owner(db, bid, user)
    settings = dict(b.setup or {})
    settings["contact"] = body.model_dump(mode="json")
    b.setup = settings
    db.add(AuditEvent(id=new_id(), business_id=b.id, actor_id=user[0].id,
                      action="restaurant.contact.updated", payload="{}"))
    db.commit()
    return contact_of(b)


@router.get("/preview/cafe/reservations/contact")
def public_contact(user=Depends(current_user), db: Session = Depends(db_session)):
    return contact_of(preview_scope(db, user, "cafe"))


@router.get("/preview/cafe/reservations/{rid}")
def public_reservation(rid: str, user=Depends(current_user),
                       db: Session = Depends(db_session)):
    b = preview_scope(db, user, "cafe")
    rec = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == b.id, IndustryWorkItem.kind == "reservations",
        IndustryWorkItem.id == rid,
        IndustryWorkItem.details["source"].as_string() == "demo"))
    if not rec:
        fail(404, "Không tìm thấy lượt đặt của bạn")
    r = reservation_out(rec)
    return {k: r[k] for k in ("id", "status", "party_size", "scheduled_at", "table_label",
                               "customer_name")}


@router.post("/preview/cafe/inquiries", status_code=201)
def create_inquiry(body: InquiryCreate, user=Depends(current_user),
                   db: Session = Depends(db_session)):
    b = preview_scope(db, user, "cafe")
    reference = hashlib.sha256((b.id + "|inquiry|" + body.request_id).encode()).hexdigest()[:36]
    existing = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == b.id, IndustryWorkItem.kind == "inquiries",
        IndustryWorkItem.reference_id == reference))
    fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    if existing:
        if (existing.details or {}).get("fingerprint") != fingerprint:
            fail(409, "Mã yêu cầu đã được sử dụng")
        return {"id": existing.id, "status": existing.status}
    inquiries = db.scalars(select(IndustryWorkItem.id).where(
        IndustryWorkItem.business_id == b.id, IndustryWorkItem.kind == "inquiries")).all()
    if len(inquiries) >= 20:
        fail(429, "Phiên DEMO đã đạt giới hạn tin nhắn")
    item = IndustryWorkItem(id=new_id(), business_id=b.id, kind="inquiries",
                            reference_id=reference, title="Yêu cầu liên hệ",
                            status="new", details={"name": body.name.strip(), "phone": body.phone,
                            "message": body.message.strip(), "fingerprint": fingerprint})
    db.add(item)
    db.add(AuditEvent(id=new_id(), business_id=b.id, actor_id=user[0].id,
                      action="restaurant.inquiry.created", payload=json.dumps({"id": item.id})))
    db.commit()
    return {"id": item.id, "status": item.status}


@router.get("/businesses/{bid}/inquiries")
def list_inquiries(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = fnb_scope(bid, user, db)
    rows = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == b.id, IndustryWorkItem.kind == "inquiries")
        .order_by(IndustryWorkItem.created_at.desc()).limit(100)).all()
    return [inquiry_out(x) for x in rows]


@router.post("/businesses/{bid}/inquiries/{iid}/status")
def set_inquiry_status(bid: str, iid: str, body: InquiryStatus,
                       user=Depends(current_user), db: Session = Depends(db_session)):
    b = fnb_scope(bid, user, db)
    row = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == b.id, IndustryWorkItem.kind == "inquiries",
        IndustryWorkItem.id == iid))
    if not row:
        fail(404, "Không tìm thấy tin nhắn")
    if row.status == "closed" or (row.status == "new" and body.status != "contacted"):
        fail(409, "Trạng thái liên hệ không hợp lệ")
    row.status = body.status
    db.add(AuditEvent(id=new_id(), business_id=b.id, actor_id=user[0].id,
                      action="restaurant.inquiry.status",
                      payload=json.dumps({"id": iid, "status": body.status})))
    db.commit()
    return inquiry_out(row)
