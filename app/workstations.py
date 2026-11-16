"""Tenant-scoped workstation profiles. This assigns a *UI operating mode*, not RBAC.

Employee privileges remain those of their authenticated membership; clients can
be modified and must never be trusted as authorization evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import Branch, now
from .main import current_user, tenant, audit
from .team import allow, MANAGE_ROLES, role_for

router = APIRouter(prefix="/api/businesses/{bid}/workstations", tags=["POS workstation"])
Mode = Literal["manager", "order", "kitchen", "bar", "cashier", "host"]
MODES = {"manager", "order", "kitchen", "bar", "cashier", "host"}
STATIONS = {"all", "kitchen", "hot", "cold", "bar", "expo"}


class Workstation(Base):
    __tablename__ = "workstations"
    __table_args__ = (UniqueConstraint("business_id", "client_key", name="uq_workstation_business_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    client_key: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manager")
    station: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    branch_id: Mapped[str | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class RegisterDevice(BaseModel):
    client_key: str = Field(min_length=36, max_length=36, pattern=r"^[0-9a-fA-F-]{36}$")
    name: str = Field(default="Thiết bị mới", min_length=2, max_length=80)


class UpdateDevice(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    mode: Mode | None = None
    station: Literal["all", "kitchen", "hot", "cold", "bar", "expo"] | None = None
    branch_id: str | None = None


def serial(row: Workstation):
    return {"id": row.id, "name": row.name, "mode": row.mode,
            "station": row.station, "branch_id": row.branch_id,
            "client_key": row.client_key, "updated_at": row.updated_at.isoformat() if row.updated_at else None}


def ensure_fnb(b):
    if b.industry != "fnb":
        raise HTTPException(404, "Chế độ trạm chỉ áp dụng cho café và nhà hàng")


@router.put("/current")
def register_current(bid: str, body: RegisterDevice, user=Depends(current_user),
                     db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    ensure_fnb(b)
    try:
        import uuid
        key = str(uuid.UUID(body.client_key))
    except (ValueError, AttributeError):
        raise HTTPException(422, "Mã thiết bị không hợp lệ")
    row = db.scalar(select(Workstation).where(Workstation.business_id == bid,
                                              Workstation.client_key == key))
    if not row:
        role = role_for(db, bid, user[0].id)
        # Keep existing manager workflows; staff devices begin only in order mode.
        default_mode = "manager" if role in MANAGE_ROLES else "order"
        row = Workstation(id=str(uuid4()), business_id=bid, client_key=key,
                          name=body.name.strip(), mode=default_mode,
                          station="all", created_by=user[0].id, updated_by=user[0].id)
        db.add(row)
        audit(db, bid, user[0].id, "workstation.registered",
              {"device_id": row.id, "mode": default_mode})
        db.commit()
        db.refresh(row)
    result = serial(row)
    if role_for(db, bid, user[0].id) == "staff":
        from .team import duty_for, duty_payload
        duty = duty_payload(duty_for(db, bid, user[0].id))
        result["device_mode"] = row.mode
        result["mode"] = duty["mode"]
        result["station"] = duty["station"]
        result["branch_id"] = duty["branch_id"]
        result["duty"] = duty
        result["mode_mismatch"] = row.mode not in ("manager", duty["mode"])
    return result


@router.get("")
def list_devices(bid: str, user=Depends(current_user),
                 db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    ensure_fnb(b)
    allow(db, bid, user, MANAGE_ROLES)
    rows = db.scalars(select(Workstation).where(Workstation.business_id == bid)
                      .order_by(Workstation.created_at.desc()).limit(100)).all()
    return {"workstations": [serial(row) for row in rows]}


@router.patch("/{device_id}")
def update_device(bid: str, device_id: str, body: UpdateDevice,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    ensure_fnb(b)
    allow(db, bid, user, MANAGE_ROLES)
    row = db.scalar(select(Workstation).where(Workstation.business_id == bid,
                                              Workstation.id == device_id))
    if not row:
        raise HTTPException(404, "Không tìm thấy thiết bị")
    changes = body.model_fields_set
    if not changes:
        raise HTTPException(422, "Chưa chọn thiết lập")
    if "name" in changes:
        if body.name is None or not body.name.strip():
            raise HTTPException(422, "Tên thiết bị không hợp lệ")
        row.name = body.name.strip()
    if "mode" in changes:
        if body.mode is None:
            raise HTTPException(422, "Chọn vai trò thiết bị")
        row.mode = body.mode
        if "station" not in changes:
            row.station = ("bar" if row.mode == "bar" else
                           "kitchen" if row.mode == "kitchen" else "all")
    if "station" in changes:
        if body.station is None:
            raise HTTPException(422, "Trạm chế biến không hợp lệ")
        row.station = body.station
    if "branch_id" in changes:
        if body.branch_id and not db.scalar(select(Branch.id).where(
                Branch.business_id == bid, Branch.id == body.branch_id)):
            raise HTTPException(422, "Chi nhánh không thuộc doanh nghiệp")
        row.branch_id = body.branch_id or None
    row.updated_by = user[0].id
    row.updated_at = now()
    audit(db, bid, user[0].id, "workstation.updated",
          {"device_id": row.id, "fields": sorted(changes),
           "mode": row.mode, "station": row.station})
    db.commit()
    db.refresh(row)
    return serial(row)
