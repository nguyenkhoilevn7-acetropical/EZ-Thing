"""Tenant/branch-isolated floor plan settings for restaurant floor zones.

Floor plans are *presentation* metadata, separate from seats, reservation
assignment and payment state. All table IDs are validated against the branch.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import db_session
from .models import Branch, Business, DiningTable, Membership, SaleOrder
from .main import audit, current_user, feature, tenant

router = APIRouter(tags=["Restaurant floor plans"])
MAX_ZONES = 12
MAX_PLACEMENTS = 180

class Zone(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,32}$")
    name: str = Field(min_length=1, max_length=45)

    @field_validator("name")
    @classmethod
    def tidy(cls, value: str):
        return value.strip()


class Placement(BaseModel):
    table_id: str = Field(min_length=1, max_length=36)
    zone_id: str = Field(min_length=1, max_length=32)
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    shape: Literal["round", "square", "rectangle"] = "round"


class FloorplanWrite(BaseModel):
    branch_id: str = Field(min_length=1, max_length=36)
    revision: int = Field(ge=0)
    zones: list[Zone] = Field(min_length=1, max_length=MAX_ZONES)
    placements: list[Placement] = Field(default_factory=list, max_length=MAX_PLACEMENTS)

    @model_validator(mode="after")
    def validate_cross_references(self):
        zone_ids = [zone.id for zone in self.zones]
        if len(set(zone_ids)) != len(zone_ids):
            raise ValueError("Trùng mã khu vực")
        table_ids = [place.table_id for place in self.placements]
        if len(set(table_ids)) != len(table_ids):
            raise ValueError("Mỗi bàn chỉ được đặt một vị trí")
        if any(place.zone_id not in zone_ids for place in self.placements):
            raise ValueError("Bàn tham chiếu khu vực không tồn tại")
        return self


DEFAULT_ZONES = [
    {"id": "inside", "name": "Trong nhà"},
    {"id": "outdoor", "name": "Ngoài trời"},
    {"id": "vip", "name": "VIP"},
]


def scope(bid: str, branch_id: str | None, user, db: Session):
    business = tenant(bid, user, db)
    if business.industry != "fnb":
        raise HTTPException(404, "Sơ đồ khu vực chỉ áp dụng cho nhà hàng / Cafe")
    feature(business, "tables")
    branches = db.scalars(select(Branch).where(Branch.business_id == bid).order_by(Branch.created_at)).all()
    if not branches:
        raise HTTPException(404, "Không tìm thấy chi nhánh")
    branch = next((x for x in branches if x.id == branch_id), None) if branch_id else branches[0]
    if branch is None:
        raise HTTPException(404, "Chi nhánh không thuộc doanh nghiệp này")
    return business, branch, branches


def effective(business: Business, branch: Branch, db: Session):
    saved = ((business.setup or {}).get("floorplans") or {}).get(branch.id) or {}
    zones = saved.get("zones") or DEFAULT_ZONES
    zone_ids = {zone["id"] for zone in zones}
    placements = saved.get("placements") or []
    by_id = {p["table_id"]: p for p in placements
             if p["zone_id"] in zone_ids}
    tables = db.scalars(select(DiningTable).where(
        DiningTable.business_id == business.id, DiningTable.branch_id == branch.id
    ).order_by(DiningTable.label)).all()
    occupied = set(db.scalars(select(SaleOrder.table_id).where(
        SaleOrder.business_id == business.id, SaleOrder.branch_id == branch.id,
        SaleOrder.status == "open", SaleOrder.table_id.is_not(None)
    )).all())
    result = []
    for index, table in enumerate(tables):
        place = by_id.get(table.id)
        if place is None:
            # Non-destructive default layout, saved only when an owner edits it.
            place = {"table_id": table.id, "zone_id": zones[0]["id"],
                     "x": float(12 + (index % 6) * 15),
                     "y": float(15 + (index // 6) % 5 * 17), "shape": "round"}
        result.append({"id": table.id, "label": table.label, "seats": table.seats,
                       "branch_id": branch.id, "occupied": table.id in occupied,
                       "placement": place})
    return {"business_id": business.id, "branch_id": branch.id, "branch_name": branch.name,
            "revision": saved.get("revision", 0),
            "zones": zones, "tables": result,
            "editable": True}


@router.get("/api/businesses/{bid}/floorplan")
def get_floorplan(bid: str, branch_id: str | None = Query(default=None),
                  user=Depends(current_user), db: Session = Depends(db_session)):
    business, branch, branches = scope(bid, branch_id, user, db)
    return {**effective(business, branch, db),
            "branches": [{"id": b.id, "name": b.name} for b in branches]}


@router.put("/api/businesses/{bid}/floorplan")
def save_floorplan(bid: str, body: FloorplanWrite,
                   user=Depends(current_user), db: Session = Depends(db_session)):
    business, branch, branches = scope(bid, body.branch_id, user, db)
    member = db.scalar(select(Membership).where(
        Membership.business_id == bid, Membership.user_id == user[0].id
    ))
    if member is None or member.role != "owner":
        raise HTTPException(403, "Chỉ chủ doanh nghiệp có quyền thay đổi sơ đồ bàn")
    table_ids = set(db.scalars(select(DiningTable.id).where(
        DiningTable.business_id == bid, DiningTable.branch_id == branch.id
    )).all())
    invalid_ids = {p.table_id for p in body.placements} - table_ids
    if invalid_ids:
        raise HTTPException(422, "Có bàn không thuộc chi nhánh được chọn")
    saved_setup = dict(business.setup or {})
    floorplans = dict(saved_setup.get("floorplans") or {})
    current = floorplans.get(branch.id) or {}
    if int(current.get("revision", 0)) != body.revision:
        raise HTTPException(409, "Sơ đồ đã được cập nhật tại thiết bị khác. Vui lòng tải lại.")
    next_rev = body.revision + 1
    floorplans[branch.id] = {
        "revision": next_rev,
        "zones": [z.model_dump() for z in body.zones],
        "placements": [p.model_dump() for p in body.placements],
    }
    saved_setup["floorplans"] = floorplans
    business.setup = saved_setup
    audit(db, bid, user[0].id, "restaurant.floorplan.updated",
          {"branch_id": branch.id, "revision": next_rev,
           "zone_count": len(body.zones), "table_count": len(body.placements)})
    db.commit()
    db.refresh(business)
    return {**effective(business, branch, db),
            "branches": [{"id": b.id, "name": b.name} for b in branches]}
