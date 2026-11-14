"""EZ Thing platform control plane, isolated from merchant operations.

Security rules:
- Real authenticated user; server email allowlist + second secret + short-lived unlock.
- Demo users never receive platform access; staging demo preview is synthetic.
- Every privileged request checks the unlock in the DB; writes require session CSRF.
- No destructive delete, billing claims, impersonation, or secret disclosure.
- Additive pilot schema; formal migrations required for production.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, select, delete, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from .catalog import PLANS, FEATURES, INDUSTRIES
from .database import Base, db_session
from .models import User, Business, Membership, Branch, Product, SaleOrder, AuditEvent, SessionToken, now
from .demo import is_demo_user, demo_enabled
from .main import current_user, fail

router = APIRouter(prefix="/api/admin", tags=["EZ Thing platform administration"])

DEMO_EMAIL_SUFFIX = "@demo.ezthing.invalid"


class PlatformTenantControl(Base):
    __tablename__ = "platform_tenant_controls"
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(String(250), default="")
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class PlatformUserControl(Base):
    __tablename__ = "platform_user_controls"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(String(250), default="")
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class PlatformAdminUnlock(Base):
    __tablename__ = "platform_admin_unlocks"
    session_hash: Mapped[str] = mapped_column(ForeignKey("sessions.token_hash", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    secret_revision: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PlatformUnlockAttempt(Base):
    __tablename__ = "platform_unlock_attempts"
    session_hash: Mapped[str] = mapped_column(ForeignKey("sessions.token_hash", ondelete="CASCADE"), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PlatformActionLog(Base):
    __tablename__ = "platform_action_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(24))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    before_state: Mapped[str] = mapped_column(Text, default="{}")
    after_state: Mapped[str] = mapped_column(Text, default="{}")
    reason: Mapped[str] = mapped_column(String(250), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


def is_user_blocked(db: Session, uid: str) -> bool:
    return bool(db.scalar(select(PlatformUserControl.suspended).where(PlatformUserControl.user_id == uid)))


def is_business_blocked(db: Session, bid: str) -> bool:
    return bool(db.scalar(select(PlatformTenantControl.suspended).where(PlatformTenantControl.business_id == bid)))


def admin_emails() -> set[str]:
    return {email.strip().lower() for email in os.getenv("EZ_THING_SUPERADMIN_EMAILS", "").split(",") if email.strip()}


def admin_key() -> str | None:
    raw = os.getenv("EZ_THING_ADMIN_ACCESS_KEY", "")
    # Fail closed with weak or missing configuration.
    return raw if len(raw) >= 32 else None


def secret_revision(secret: str) -> str:
    return hashlib.sha256(("ezthing-admin-v04:" + secret).encode("utf-8")).hexdigest()


def utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def authorized_identity(user):
    u, session = user
    if is_demo_user(u) or u.email.strip().lower() not in admin_emails():
        fail(403, "Không có quyền quản trị nền tảng")
    return u, session


def admin_identity(user=Depends(current_user)):
    u, session = authorized_identity(user)
    if not admin_key():
        fail(503, "Quản trị chưa được cấu hình xác thực tăng cường")
    return u, session


def admin_required(user=Depends(admin_identity), db: Session = Depends(db_session)):
    u, session = user
    secret = admin_key()
    proof = db.get(PlatformAdminUnlock, session.token_hash)
    if not (secret and proof and proof.user_id == u.id and
            proof.secret_revision == secret_revision(secret) and
            utc(proof.expires_at) > datetime.now(timezone.utc)):
        fail(403, "Cần mở khóa phiên quản trị trước khi thực hiện thao tác")
    return user


def log_action(db: Session, actor_id: str, action: str, target_type: str, target_id: str,
               before: dict | None = None, after: dict | None = None, reason: str = ""):
    db.add(PlatformActionLog(id=str(uuid.uuid4()), actor_id=actor_id, action=action,
                             target_type=target_type, target_id=target_id,
                             before_state=json.dumps(before or {}, ensure_ascii=False),
                             after_state=json.dumps(after or {}, ensure_ascii=False),
                             reason=reason))


def real_business_filter():
    return Business.subscription_status != "demo"


def real_user_filter():
    return ~User.email.like("%@demo.ezthing.invalid")


def short_date(d):
    return utc(d).isoformat() if d else None


def tenant_row(db, business: Business):
    control = db.get(PlatformTenantControl, business.id)
    owner = db.execute(select(User.name, User.email).join(Membership, Membership.user_id == User.id)
                       .where(Membership.business_id == business.id, Membership.role == "owner")
                       .limit(1)).first()
    return {"id": business.id, "name": business.name, "industry": business.industry,
            "industry_label": INDUSTRIES.get(business.industry, business.industry),
            "plan": business.plan, "subscription_status": business.subscription_status,
            "suspended": bool(control.suspended) if control else False,
            "suspend_reason": control.reason if control and control.suspended else "",
            "owner": {"name": owner[0], "email": owner[1]} if owner else None,
            "created_at": short_date(business.created_at)}


def user_row(db, user: User):
    control = db.get(PlatformUserControl, user.id)
    return {"id": user.id, "name": user.name, "email": user.email,
            "created_at": short_date(user.created_at),
            "suspended": bool(control.suspended) if control else False,
            "suspend_reason": control.reason if control and control.suspended else "",
            "business_count": db.scalar(select(func.count(Membership.id)).where(Membership.user_id == user.id)) or 0,
            "is_platform_admin": user.email.lower() in admin_emails()}


class UnlockRequest(BaseModel):
    access_key: str = Field(min_length=1, max_length=512)


class ChangePlanRequest(BaseModel):
    plan: Literal["BASIC", "PLUS", "PRO"]
    reason: str = Field(min_length=8, max_length=250)
    confirmed: Literal[True]


class SuspendBusinessRequest(BaseModel):
    confirm_name: str = Field(min_length=2, max_length=140)
    reason: str = Field(min_length=8, max_length=250)


class ResumeRequest(BaseModel):
    reason: str = Field(min_length=8, max_length=250)
    confirmed: Literal[True]


class BlockUserRequest(BaseModel):
    confirm_email: str = Field(min_length=5, max_length=254)
    reason: str = Field(min_length=8, max_length=250)


@router.get("/preview")
def safe_admin_preview():
    # No database access and no real personal information, even on a public URL.
    if not demo_enabled():
        fail(404, "Không có DEMO quản trị")
    return {
        "mode": "synthetic_demo", "read_only": True,
        "overview": {"businesses": 32, "users": 84, "orders": 1248,
                     "active_businesses": 31, "suspended_businesses": 1,
                     "plans": {"BASIC": 19, "PLUS": 10, "PRO": 3},
                     "notice": "Dữ liệu minh họa, không phải số liệu thực tế hay doanh thu thuê bao"},
        "businesses": [
            {"id": "sample-a", "name": "Tropical Cafe • Mẫu", "industry": "fnb", "plan": "PLUS", "owner": {"name": "Chủ quán mẫu", "email": "sample@example.invalid"}, "subscription_status": "pilot", "suspended": False},
            {"id": "sample-b", "name": "Easy Mart • Mẫu", "industry": "retail", "plan": "BASIC", "owner": {"name": "Người quản lý mẫu", "email": "retail@example.invalid"}, "subscription_status": "pilot", "suspended": False},
            {"id": "sample-c", "name": "Online Shop • Mẫu", "industry": "online", "plan": "PRO", "owner": {"name": "Nhà bán mẫu", "email": "online@example.invalid"}, "subscription_status": "pilot", "suspended": True},
            {"id": "sample-d", "name": "Wellness Spa • Mẫu", "industry": "services", "plan": "PLUS", "owner": {"name": "Spa mẫu", "email": "spa@example.invalid"}, "subscription_status": "pilot", "suspended": False},
        ],
        "users": [
            {"id": "user-a", "name": "Người dùng mẫu A", "email": "user-a@example.invalid", "business_count": 2, "suspended": False},
            {"id": "user-b", "name": "Người dùng mẫu B", "email": "user-b@example.invalid", "business_count": 1, "suspended": False},
            {"id": "user-c", "name": "Người dùng mẫu C", "email": "user-c@example.invalid", "business_count": 1, "suspended": True},
        ],
        "audit": [
            {"id": "example-1", "action": "business.plan_changed", "target_type": "business", "target_id": "sample-a", "reason": "Mở rộng chi nhánh • minh họa", "created_at": "2026-11-14T08:00:00+00:00"},
            {"id": "example-2", "action": "business.suspended", "target_type": "business", "target_id": "sample-c", "reason": "Kiểm tra thủ công • minh họa", "created_at": "2026-11-14T07:00:00+00:00"},
        ],
        "plans": {k: {"name": v["name"], "price_vnd": v["price_vnd"], "features": v["features"], "branches": v["branches"]} for k, v in PLANS.items()},
        "system": {"api": "demo_only", "database": "not_checked", "billing": "not_integrated",
                   "admin_mfa": "access_key_session", "backup": "not_verified", "migrations": "pilot_create_all"},
    }


@router.get("/session")
def admin_session(user=Depends(admin_identity), db: Session = Depends(db_session)):
    u, session = user
    proof = db.get(PlatformAdminUnlock, session.token_hash)
    key = admin_key()
    unlocked = bool(proof and key and proof.user_id == u.id and
                    proof.secret_revision == secret_revision(key) and
                    utc(proof.expires_at) > datetime.now(timezone.utc))
    return {"email": u.email, "name": u.name, "role": "super_admin", "unlocked": unlocked,
            "expires_at": short_date(proof.expires_at) if unlocked else None,
            "csrf_token": session.csrf_token}


@router.post("/unlock")
def unlock_admin(payload: UnlockRequest, user=Depends(admin_identity), db: Session = Depends(db_session)):
    u, session = user
    row = db.get(PlatformUnlockAttempt, session.token_hash)
    if row and row.locked_until and utc(row.locked_until) > datetime.now(timezone.utc):
        fail(429, "Đã vượt số lần thử. Vui lòng thử lại sau")
    correct = hmac.compare_digest(payload.access_key.encode(), admin_key().encode())
    if not correct:
        if row is None:
            row = PlatformUnlockAttempt(session_hash=session.token_hash, failures=0)
            db.add(row)
        row.failures += 1
        row.updated_at = now()
        if row.failures >= 5:
            row.locked_until = now() + timedelta(minutes=15)
            row.failures = 0
        db.commit()
        fail(403, "Mã mở khóa không chính xác")
    if row is not None:
        db.delete(row)
    record = db.get(PlatformAdminUnlock, session.token_hash)
    if record is None:
        record = PlatformAdminUnlock(session_hash=session.token_hash, user_id=u.id,
                                     secret_revision=secret_revision(admin_key()),
                                     expires_at=now() + timedelta(minutes=30))
        db.add(record)
    else:
        record.user_id = u.id
        record.secret_revision = secret_revision(admin_key())
        record.expires_at = now() + timedelta(minutes=30)
    log_action(db, u.id, "admin.unlocked", "user", u.id)
    db.commit()
    return {"ok": True, "unlocked": True, "expires_at": short_date(record.expires_at)}


@router.post("/lock")
def lock_admin(user=Depends(admin_required), db: Session = Depends(db_session)):
    u, session = user
    log_action(db, u.id, "admin.locked", "user", u.id)
    db.execute(delete(PlatformAdminUnlock).where(PlatformAdminUnlock.session_hash == session.token_hash))
    db.commit()
    return {"ok": True, "unlocked": False}


@router.get("/summary")
def summary(user=Depends(admin_required), db: Session = Depends(db_session)):
    businesses = db.scalar(select(func.count(Business.id)).where(real_business_filter())) or 0
    users = db.scalar(select(func.count(User.id)).where(real_user_filter())) or 0
    orders = db.scalar(select(func.count(SaleOrder.id)).join(Business, Business.id == SaleOrder.business_id)
                       .where(real_business_filter())) or 0
    return {"businesses": businesses, "users": users, "orders": orders,
            "mode": "pilot_control_plane"}


@router.get("/overview")
def overview(user=Depends(admin_required), db: Session = Depends(db_session)):
    base = summary(user, db)
    statuses = db.execute(select(Business.plan, func.count(Business.id)).where(real_business_filter())
                          .group_by(Business.plan)).all()
    suspended = db.scalar(select(func.count(PlatformTenantControl.business_id)).join(
        Business, PlatformTenantControl.business_id == Business.id).where(
        PlatformTenantControl.suspended.is_(True), real_business_filter())) or 0
    active = max(0, base["businesses"] - suspended)
    recent = db.scalars(select(PlatformActionLog).order_by(PlatformActionLog.created_at.desc()).limit(7)).all()
    return {**base, "active_businesses": active, "suspended_businesses": suspended,
            "plans": {key: next((int(count) for name, count in statuses if key == name), 0) for key in PLANS},
            "recent_actions": [audit_row(x) for x in recent],
            "notice": "Gói chỉ là quyền sử dụng pilot; hệ thống chưa thu thuê bao hoặc xác nhận MRR"}


@router.get("/businesses")
def list_businesses(user=Depends(admin_required), db: Session = Depends(db_session),
                    q: str = Query(default="", max_length=120),
                    industry: str = Query(default="", max_length=24),
                    plan: str = Query(default="", max_length=12),
                    status: Literal["all", "active", "suspended"] = "all",
                    limit: int = Query(default=25, ge=1, le=100),
                    offset: int = Query(default=0, ge=0, le=100000)):
    query = select(Business).where(real_business_filter())
    if q.strip():
        query = query.where(Business.name.ilike(f"%{q.strip()}%"))
    if industry:
        if industry not in INDUSTRIES: fail(422, "Ngành không hợp lệ")
        query = query.where(Business.industry == industry)
    if plan:
        if plan not in PLANS: fail(422, "Gói không hợp lệ")
        query = query.where(Business.plan == plan)
    if status == "suspended":
        query = query.join(PlatformTenantControl).where(PlatformTenantControl.suspended.is_(True))
    elif status == "active":
        blocked = select(PlatformTenantControl.business_id).where(PlatformTenantControl.suspended.is_(True))
        query = query.where(~Business.id.in_(blocked))
    count = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(query.order_by(Business.created_at.desc(), Business.id).offset(offset).limit(limit)).all()
    return {"items": [tenant_row(db, r) for r in rows], "total": int(count), "offset": offset, "limit": limit}


@router.get("/businesses/{bid}")
def business_detail(bid: str, user=Depends(admin_required), db: Session = Depends(db_session)):
    b = db.get(Business, bid)
    if not b or b.subscription_status == "demo": fail(404, "Doanh nghiệp không tồn tại")
    members = db.execute(select(Membership.role, User.id, User.name, User.email)
                         .join(User, User.id == Membership.user_id)
                         .where(Membership.business_id == bid).order_by(User.name).limit(100)).all()
    branches = db.scalars(select(Branch).where(Branch.business_id == bid)).all()
    return {**tenant_row(db, b), "active_modules": b.active_modules or [],
            "requested_plan": b.requested_plan,
            "members": [{"role": role, "id": uid, "name": name, "email": email}
                        for role, uid, name, email in members],
            "branches": [{"id": x.id, "name": x.name} for x in branches],
            "products": db.scalar(select(func.count(Product.id)).where(Product.business_id == bid)) or 0,
            "orders": db.scalar(select(func.count(SaleOrder.id)).where(SaleOrder.business_id == bid)) or 0}


@router.post("/businesses/{bid}/plan")
def change_business_plan(bid: str, payload: ChangePlanRequest,
                         user=Depends(admin_required), db: Session = Depends(db_session)):
    u, _ = user
    b = db.scalar(select(Business).where(Business.id == bid).with_for_update())
    if b is None or b.subscription_status == "demo": fail(404, "Doanh nghiệp không tồn tại")
    if b.plan == payload.plan: fail(409, "Doanh nghiệp đang sử dụng gói này")
    branch_count = db.scalar(select(func.count(Branch.id)).where(Branch.business_id == bid)) or 0
    if branch_count > PLANS[payload.plan]["branches"]:
        fail(409, "Gói đích không đủ số chi nhánh hiện tại; không tự xóa chi nhánh")
    previous = {"plan": b.plan, "modules": b.active_modules or []}
    allowed = set(PLANS[payload.plan]["features"])
    # Never enable an unrelated industry module; keep core and industry workflow.
    industry_flag = {"fnb": "kitchen", "retail": "stock_ledger", "online": "fulfillment", "services": "appointments"}.get(b.industry)
    wanted = set(b.active_modules or []) | {"dashboard", "products", "orders"}
    if industry_flag: wanted.add(industry_flag)
    if b.industry == "fnb" and (b.setup or {}).get("need_tables", True): wanted.add("tables")
    if (b.setup or {}).get("need_inventory"): wanted.add("inventory_basic")
    if (b.setup or {}).get("need_insights"): wanted.add("insights")
    if (b.setup or {}).get("need_branches"): wanted.add("multi_branch")
    b.active_modules = sorted(wanted & allowed)
    b.plan = payload.plan
    current = {"plan": b.plan, "modules": b.active_modules or []}
    log_action(db, u.id, "business.plan_changed", "business", b.id, previous, current, payload.reason.strip())
    db.commit()
    return {"ok": True, "business": tenant_row(db, b), "active_modules": b.active_modules,
            "billing_applied": False, "note": "Chỉ đổi quyền dùng trong pilot; không thu tiền"}


@router.post("/businesses/{bid}/suspend")
def suspend_business(bid: str, payload: SuspendBusinessRequest,
                     user=Depends(admin_required), db: Session = Depends(db_session)):
    u, _ = user
    b = db.scalar(select(Business).where(Business.id == bid).with_for_update())
    if b is None or b.subscription_status == "demo": fail(404, "Doanh nghiệp không tồn tại")
    if payload.confirm_name.strip() != b.name: fail(422, "Tên xác nhận không khớp doanh nghiệp")
    control = db.get(PlatformTenantControl, bid)
    if control and control.suspended: fail(409, "Doanh nghiệp đã bị tạm khóa")
    if not control:
        control = PlatformTenantControl(business_id=bid)
        db.add(control)
    control.suspended = True
    control.reason = payload.reason.strip()
    control.updated_by = u.id
    control.updated_at = now()
    log_action(db, u.id, "business.suspended", "business", bid, {"suspended": False},
               {"suspended": True}, payload.reason.strip())
    db.commit()
    return {"ok": True, "suspended": True}


@router.post("/businesses/{bid}/resume")
def resume_business(bid: str, payload: ResumeRequest,
                    user=Depends(admin_required), db: Session = Depends(db_session)):
    u, _ = user
    b = db.scalar(select(Business).where(Business.id == bid).with_for_update())
    if b is None or b.subscription_status == "demo": fail(404, "Doanh nghiệp không tồn tại")
    control = db.get(PlatformTenantControl, bid)
    if not control or not control.suspended: fail(409, "Doanh nghiệp không bị khóa")
    control.suspended = False
    control.reason = ""
    control.updated_at = now()
    control.updated_by = u.id
    log_action(db, u.id, "business.resumed", "business", bid,
               {"suspended": True}, {"suspended": False}, payload.reason.strip())
    db.commit()
    return {"ok": True, "suspended": False}


@router.get("/users")
def list_users(user=Depends(admin_required), db: Session = Depends(db_session),
               q: str = Query(default="", max_length=120),
               status: Literal["all", "active", "suspended"] = "all",
               limit: int = Query(default=25, ge=1, le=100),
               offset: int = Query(default=0, ge=0, le=100000)):
    query = select(User).where(real_user_filter())
    if q.strip(): query = query.where((User.name.ilike(f"%{q.strip()}%")) | (User.email.ilike(f"%{q.strip()}%")))
    if status == "suspended":
        query = query.join(PlatformUserControl).where(PlatformUserControl.suspended.is_(True))
    elif status == "active":
        blocked = select(PlatformUserControl.user_id).where(PlatformUserControl.suspended.is_(True))
        query = query.where(~User.id.in_(blocked))
    count = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(query.order_by(User.created_at.desc(), User.id).offset(offset).limit(limit)).all()
    return {"items": [user_row(db, x) for x in rows], "total": int(count), "limit": limit, "offset": offset}


@router.get("/users/{uid}")
def user_detail(uid: str, user=Depends(admin_required), db: Session = Depends(db_session)):
    u = db.get(User, uid)
    if u is None or is_demo_user(u): fail(404, "Tài khoản không tồn tại")
    memberships = db.execute(select(Membership.role, Business.id, Business.name, Business.plan)
                             .join(Business, Membership.business_id == Business.id)
                             .where(Membership.user_id == uid, real_business_filter())).all()
    return {**user_row(db, u), "memberships": [{"role": role, "business_id": bid,
                                                 "business_name": name, "plan": plan}
                                                for role, bid, name, plan in memberships]}


@router.post("/users/{uid}/block")
def block_user(uid: str, payload: BlockUserRequest, user=Depends(admin_required), db: Session = Depends(db_session)):
    admin, _ = user
    target = db.scalar(select(User).where(User.id == uid).with_for_update())
    if not target or is_demo_user(target): fail(404, "Tài khoản không tồn tại")
    if target.id == admin.id or target.email.lower() in admin_emails():
        fail(403, "Không thể khóa tài khoản quản trị nền tảng")
    if payload.confirm_email.strip().lower() != target.email.lower():
        fail(422, "Email xác nhận không khớp")
    control = db.get(PlatformUserControl, target.id)
    if control and control.suspended: fail(409, "Tài khoản đã bị tạm khóa")
    if not control:
        control = PlatformUserControl(user_id=target.id)
        db.add(control)
    control.suspended = True
    control.reason = payload.reason.strip()
    control.updated_by = admin.id
    control.updated_at = now()
    # Revoke every existing session; this also invalidates admin unlocks on those sessions.
    session_hashes = db.scalars(select(SessionToken.token_hash).where(SessionToken.user_id == uid)).all()
    if session_hashes:
        db.execute(delete(PlatformAdminUnlock).where(PlatformAdminUnlock.session_hash.in_(session_hashes)))
        db.execute(delete(PlatformUnlockAttempt).where(PlatformUnlockAttempt.session_hash.in_(session_hashes)))
    db.execute(delete(SessionToken).where(SessionToken.user_id == uid))
    log_action(db, admin.id, "user.blocked", "user", uid,
               {"suspended": False}, {"suspended": True}, payload.reason.strip())
    db.commit()
    return {"ok": True, "suspended": True, "sessions_revoked": len(session_hashes)}


@router.post("/users/{uid}/unblock")
def unblock_user(uid: str, payload: ResumeRequest, user=Depends(admin_required), db: Session = Depends(db_session)):
    admin, _ = user
    target = db.scalar(select(User).where(User.id == uid).with_for_update())
    if not target or is_demo_user(target): fail(404, "Tài khoản không tồn tại")
    control = db.get(PlatformUserControl, uid)
    if not control or not control.suspended: fail(409, "Tài khoản không bị khóa")
    control.suspended = False
    control.reason = ""
    control.updated_by = admin.id
    control.updated_at = now()
    log_action(db, admin.id, "user.unblocked", "user", uid,
               {"suspended": True}, {"suspended": False}, payload.reason.strip())
    db.commit()
    return {"ok": True, "suspended": False}


def audit_row(row):
    return {"id": row.id, "actor_id": row.actor_id, "action": row.action,
            "target_type": row.target_type, "target_id": row.target_id,
            "before": json.loads(row.before_state or "{}"), "after": json.loads(row.after_state or "{}"),
            "reason": row.reason, "created_at": short_date(row.created_at)}


@router.get("/audit")
def audit_feed(user=Depends(admin_required), db: Session = Depends(db_session),
               action: str = Query(default="", max_length=80),
               limit: int = Query(default=50, ge=1, le=200),
               offset: int = Query(default=0, ge=0, le=100000)):
    stmt = select(PlatformActionLog)
    if action.strip(): stmt = stmt.where(PlatformActionLog.action == action.strip())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(PlatformActionLog.created_at.desc(), PlatformActionLog.id.desc())
                      .offset(offset).limit(limit)).all()
    return {"items": [audit_row(x) for x in rows], "total": int(total), "limit": limit, "offset": offset}


@router.get("/plans")
def plans(user=Depends(admin_required)):
    from .storefront_brand import PLANS_BRANDING
    return {"items": [{"id": key, "name": value["name"], "price_vnd": value["price_vnd"],
                       "branches": value["branches"], "features": value["features"],
                       "branding": PLANS_BRANDING[key]}
                      for key, value in PLANS.items()], "billing_live": False,
            "note": "Giá tham khảo. Đổi gói chỉ thay quyền truy cập pilot, không thu phí."}


@router.get("/system")
def system_status(user=Depends(admin_required), db: Session = Depends(db_session)):
    db.execute(text("SELECT 1"))
    return {"api": "healthy", "database": "reachable", "environment": os.getenv("EZ_THING_ENVIRONMENT", "unset"),
            "demo_enabled": demo_enabled(), "admin_unlock_ttl_minutes": 30,
            "billing": "not_integrated", "email_verification": "not_integrated",
            "admin_mfa": "second_secret_only", "migrations": "pilot_create_all",
            "backup": "not_verified", "payment_gateway": "not_integrated",
            "server_time": datetime.now(timezone.utc).isoformat()}