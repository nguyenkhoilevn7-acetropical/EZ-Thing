"""Explicit tenant RBAC and one-time email-bound team invitations.

Owner can invite manager/staff. Invites are NOT automatically emailed until a
transactional mail provider is configured; owner must share the link securely.
No user can self-elevate or invite themselves to an arbitrary tenant.
"""
from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, String, select, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import Branch, Business, Membership, User, now
from .main import audit, current_user, tenant

router = APIRouter(prefix="/api", tags=["Merchant team"])
ROLES = {"owner", "manager", "staff"}
MANAGE_ROLES = {"owner", "manager"}
DUTIES = {"order", "kitchen", "bar", "cashier", "host"}
KITCHEN_STATIONS = {"kitchen", "hot", "cold", "expo"}


class StaffDuty(Base):
    """Authenticated employee duty. The browser/device key never grants access."""
    __tablename__ = "staff_duties"
    __table_args__ = (UniqueConstraint("business_id", "user_id",
                                      name="uq_staff_duty_tenant_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="order")
    branch_id: Mapped[str | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    station: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    updated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StaffDutyUpdate(BaseModel):
    mode: Literal["order", "kitchen", "bar", "cashier", "host"]
    branch_id: str | None = None
    station: Literal["all", "kitchen", "hot", "cold", "expo", "bar"] = "all"


def duty_for(db: Session, bid: str, uid: str) -> StaffDuty | None:
    return db.scalar(select(StaffDuty).where(
        StaffDuty.business_id == bid, StaffDuty.user_id == uid))


def duty_payload(value: StaffDuty | None) -> dict:
    return {
        "mode": value.mode if value else "order",
        "branch_id": value.branch_id if value else None,
        "station": value.station if value else "all",
        "assigned": value is not None,
    }


def require_duty(db: Session, bid: str, user, allowed: set[str]) -> StaffDuty | None:
    """Enforce employee functional privilege, independently of device profile.

    Existing staff without an assignment are restricted to order-taking.
    Managers/owners retain current privileges and never impersonate staff.
    """
    role = allow(db, bid, user, ROLES)
    if role != "staff":
        return None
    assigned = duty_for(db, bid, user[0].id)
    mode = assigned.mode if assigned else "order"
    if mode not in allowed:
        raise HTTPException(403, "Tài khoản nhân viên không có quyền cho tác vụ này")
    return assigned


def require_branch(assignment: StaffDuty | None, branch_id: str) -> None:
    if assignment and assignment.branch_id and assignment.branch_id != branch_id:
        raise HTTPException(403, "Thiết bị/nhân viên không thuộc chi nhánh này")


def require_kds_station(assignment: StaffDuty | None, station: str) -> None:
    if not assignment:
        return
    if assignment.mode == "bar":
        allowed = {"bar"}
    else:
        allowed = {"hot", "cold", "expo"} if assignment.station == "kitchen" else {assignment.station}
    if station not in allowed:
        raise HTTPException(403, "Nhân viên không được xử lý món tại trạm này")


class TeamInvite(Base):
    __tablename__ = "team_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CreateInvite(BaseModel):
    email: EmailStr
    role: Literal["manager", "staff"] = "staff"


class AcceptInvite(BaseModel):
    token: str


class ChangeRole(BaseModel):
    role: Literal["manager", "staff"]


def role_for(db: Session, bid: str, uid: str) -> str | None:
    return db.scalar(select(Membership.role).where(
        Membership.business_id == bid, Membership.user_id == uid))


def allow(db: Session, bid: str, user, roles: set[str], message: str = "Không đủ quyền thao tác") -> str:
    role = role_for(db, bid, user[0].id)
    if role not in roles:
        raise HTTPException(status_code=403, detail=message)
    return role


def owner_only(db: Session, bid: str, user):
    return allow(db, bid, user, {"owner"}, "Chỉ chủ doanh nghiệp được quản lý nhân sự")


def utc(value: datetime):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.get("/businesses/{bid}/team")
def list_team(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    owner_only(db, bid, user)
    memberships = db.execute(select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.business_id == bid).order_by(User.name)).all()
    duties = {x.user_id: duty_payload(x) for x in db.scalars(
        select(StaffDuty).where(StaffDuty.business_id == bid)).all()}
    pending = db.scalars(select(TeamInvite).where(
        TeamInvite.business_id == bid, TeamInvite.accepted_at.is_(None),
        TeamInvite.revoked_at.is_(None), TeamInvite.expires_at > now())
        .order_by(TeamInvite.created_at.desc()).limit(100)).all()
    return {
        "members": [{"id": u.id, "name": u.name, "email": u.email,
                     "role": m.role, "duty": duties.get(u.id, duty_payload(None)) if m.role == "staff" else None}
                    for m, u in memberships],
        "invitations": [{"id": x.id, "email": x.email, "role": x.role,
                         "expires_at": utc(x.expires_at).isoformat()} for x in pending],
        "roles": ["manager", "staff"],
        "email_delivery": False,
    }


@router.post("/businesses/{bid}/team/invitations", status_code=201)
def create_invite(bid: str, body: CreateInvite,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    owner_only(db, bid, user)
    from .demo import is_demo_user
    if is_demo_user(user[0]):
        raise HTTPException(403, "Không thể mời nhân sự trong tài khoản demo")
    email = str(body.email).strip().lower()
    joined = db.scalar(select(Membership.id).join(User, User.id == Membership.user_id)
        .where(Membership.business_id == bid, User.email == email))
    if joined:
        raise HTTPException(409, "Tài khoản đã thuộc doanh nghiệp")
    active = db.scalar(select(TeamInvite.id).where(
        TeamInvite.business_id == bid, TeamInvite.email == email,
        TeamInvite.accepted_at.is_(None), TeamInvite.revoked_at.is_(None),
        TeamInvite.expires_at > now()))
    if active:
        raise HTTPException(409, "Thư mời đang còn hiệu lực; hãy thu hồi trước khi gửi lại")
    secret = secrets.token_urlsafe(36)
    invitation = TeamInvite(
        id=str(uuid.uuid4()), business_id=bid, email=email, role=body.role,
        token_hash=hashlib.sha256(secret.encode()).hexdigest(),
        invited_by=user[0].id, expires_at=now() + timedelta(hours=48),
    )
    db.add(invitation)
    audit(db, bid, user[0].id, "team.invited", {
        "invitation_id": invitation.id, "role": body.role,
    })
    db.commit()
    # Token is returned once. Do not include it in GET/list or audit.
    return {"id": invitation.id, "role": body.role,
            "expires_at": utc(invitation.expires_at).isoformat(),
            "invite_url": "/app?invite=" + secret, "email": email}


@router.post("/team/accept", status_code=200)
def accept_invite(body: AcceptInvite,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    from .demo import is_demo_user
    if is_demo_user(user[0]):
        raise HTTPException(403, "DEMO không được nhận lời mời doanh nghiệp thật")
    if len(body.token) < 32 or len(body.token) > 256:
        raise HTTPException(404, "Không tìm thấy lời mời hợp lệ")
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    invitation = db.scalar(select(TeamInvite).where(
        TeamInvite.token_hash == token_hash).with_for_update())
    if invitation is None or invitation.revoked_at or invitation.accepted_at or utc(invitation.expires_at) <= now():
        raise HTTPException(404, "Lời mời không còn hiệu lực")
    if invitation.email != user[0].email.lower():
        raise HTTPException(403, "Email đăng nhập phải trùng với email được mời")
    b = db.get(Business, invitation.business_id)
    if not b or b.subscription_status == "demo":
        raise HTTPException(404, "Doanh nghiệp không tồn tại")
    from .platform_admin import is_business_blocked
    if is_business_blocked(db, b.id):
        raise HTTPException(403, "Doanh nghiệp bị tạm khóa")
    existing = db.scalar(select(Membership.id).where(
        Membership.business_id == b.id, Membership.user_id == user[0].id))
    if existing:
        raise HTTPException(409, "Tài khoản đã thuộc doanh nghiệp")
    db.add(Membership(id=str(uuid.uuid4()), business_id=b.id,
                      user_id=user[0].id, role=invitation.role))
    invitation.accepted_at = now()
    if invitation.role == "staff" and b.industry == "fnb":
        first_branch = db.scalar(select(Branch.id).where(Branch.business_id == b.id)
                                 .order_by(Branch.created_at))
        db.add(StaffDuty(
            id=str(uuid.uuid4()), business_id=b.id, user_id=user[0].id,
            mode="order", station="all", branch_id=first_branch,
            updated_by=invitation.invited_by))
    audit(db, b.id, user[0].id, "team.joined", {"role": invitation.role})
    db.commit()
    return {"ok": True, "business_id": b.id, "role": invitation.role}


@router.post("/businesses/{bid}/team/invitations/{iid}/revoke")
def revoke_invite(bid: str, iid: str,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    owner_only(db, bid, user)
    invite = db.scalar(select(TeamInvite).where(
        TeamInvite.id == iid, TeamInvite.business_id == bid).with_for_update())
    if not invite or invite.accepted_at:
        raise HTTPException(404, "Không tìm thấy lời mời")
    if invite.revoked_at is None:
        invite.revoked_at = now()
        audit(db, bid, user[0].id, "team.invite_revoked", {"invitation_id": iid})
        db.commit()
    return {"ok": True}


@router.patch("/businesses/{bid}/team/members/{uid}")
def change_role(bid: str, uid: str, body: ChangeRole,
                user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    owner_only(db, bid, user)
    member = db.scalar(select(Membership).where(
        Membership.business_id == bid, Membership.user_id == uid).with_for_update())
    if member is None or member.role == "owner":
        raise HTTPException(403, "Không thể sửa chủ doanh nghiệp")
    before = member.role
    member.role = body.role
    if body.role == "staff" and before != "staff" and db.scalar(select(Business.industry).where(
            Business.id == bid)) == "fnb" and not duty_for(db, bid, uid):
        first_branch = db.scalar(select(Branch.id).where(Branch.business_id == bid)
                                 .order_by(Branch.created_at))
        db.add(StaffDuty(id=str(uuid.uuid4()), business_id=bid, user_id=uid,
                         mode="order", station="all", branch_id=first_branch,
                         updated_by=user[0].id))
    audit(db, bid, user[0].id, "team.role_changed", {
        "target_user_id": uid, "from": before, "to": body.role})
    db.commit()
    return {"ok": True, "role": body.role}


@router.delete("/businesses/{bid}/team/members/{uid}")
def remove_member(bid: str, uid: str,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    owner_only(db, bid, user)
    member = db.scalar(select(Membership).where(
        Membership.business_id == bid, Membership.user_id == uid).with_for_update())
    if not member or member.role == "owner":
        raise HTTPException(403, "Không thể xóa chủ doanh nghiệp")
    old_duty = duty_for(db, bid, uid)
    if old_duty:
        db.delete(old_duty)
    db.delete(member)
    audit(db, bid, user[0].id, "team.member_removed", {"target_user_id": uid})
    db.commit()
    return {"ok": True}


@router.get("/businesses/{bid}/team/my-duty")
def my_duty(bid: str, user=Depends(current_user),
            db: Session = Depends(db_session)):
    tenant(bid, user, db)
    role = allow(db, bid, user, ROLES)
    if role != "staff":
        return {"role": role, "mode": "manager", "station": "all",
                "branch_id": None, "assigned": True}
    return {"role": role, **duty_payload(duty_for(db, bid, user[0].id))}


@router.put("/businesses/{bid}/team/members/{uid}/duty")
def assign_staff_duty(bid: str, uid: str, body: StaffDutyUpdate,
                      user=Depends(current_user), db: Session = Depends(db_session)):
    business = tenant(bid, user, db)
    owner_only(db, bid, user)
    if business.industry != "fnb":
        raise HTTPException(404, "Phân công trạm POS chỉ áp dụng cho F&B")
    member = db.scalar(select(Membership).where(
        Membership.business_id == bid, Membership.user_id == uid).with_for_update())
    if not member or member.role != "staff":
        raise HTTPException(404, "Chỉ phân công cho nhân viên thuộc doanh nghiệp")
    if body.branch_id and not db.scalar(select(Branch.id).where(
            Branch.business_id == bid, Branch.id == body.branch_id)):
        raise HTTPException(422, "Chi nhánh không thuộc doanh nghiệp")
    if body.mode == "bar" and body.station not in {"all", "bar"}:
        raise HTTPException(422, "Nhân viên pha chế chỉ được gán trạm Bar")
    if body.mode == "kitchen" and body.station not in KITCHEN_STATIONS | {"all"}:
        raise HTTPException(422, "Trạm bếp không hợp lệ")
    if body.mode not in {"kitchen", "bar"} and body.station != "all":
        raise HTTPException(422, "Vai trò không chế biến không được gán trạm")
    normalized_station = "bar" if body.mode == "bar" else (
        "kitchen" if body.mode == "kitchen" and body.station == "all"
        else body.station)
    row = duty_for(db, bid, uid)
    previous = duty_payload(row)
    if row is None:
        row = StaffDuty(id=str(uuid.uuid4()), business_id=bid, user_id=uid,
                        updated_by=user[0].id)
        db.add(row)
    row.mode, row.branch_id, row.station = body.mode, body.branch_id, normalized_station
    row.updated_by, row.updated_at = user[0].id, now()
    audit(db, bid, user[0].id, "team.staff_duty_assigned", {
        "employee_id": uid, "before": previous, "after": duty_payload(row)})
    db.commit()
    return {"user_id": uid, "duty": duty_payload(row)}
