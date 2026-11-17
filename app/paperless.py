"""Paperless POS receipts and optional Google-member wallets.

Receipts are views of the existing paid sale_orders ledger, not fiscal invoices or
a second financial ledger. One-time QR bearer claims are never put into access logs:
the bearer goes in a URL fragment, then is POSTed for redemption.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select, or_
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import Business, Branch, Customer, SaleOrder, SaleOrderItem, now
from .main import current_user, tenant
from .team import MANAGE_ROLES, allow, require_duty

router = APIRouter(tags=["Paperless receipts and member loyalty"])
COOKIE_GUEST = "ez_guest_receipts"
COOKIE_MEMBER = "ez_member_receipts"
GUEST_MAX_AGE = 60 * 60 * 24 * 365
MEMBER_MAX_AGE = 60 * 60 * 24 * 30
QR_TTL_SECONDS = 15 * 60


def uid():
    return str(uuid.uuid4())


def digest(secret: str):
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def fresh():
    return secrets.token_urlsafe(36)


def deny(code: int, message: str):
    raise HTTPException(code, message)


class GuestWallet(Base):
    __tablename__ = "receipt_guest_wallets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Member(Base):
    __tablename__ = "receipt_members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    name: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    member_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MemberSession(Base):
    __tablename__ = "receipt_member_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("receipt_members.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MemberCustomer(Base):
    __tablename__ = "receipt_member_customers"
    __table_args__ = (UniqueConstraint("business_id", "customer_id"),)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey("receipt_members.id", ondelete="CASCADE"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)


class ReceiptClaim(Base):
    __tablename__ = "receipt_claim_tokens"
    order_id: Mapped[str] = mapped_column(ForeignKey("sale_orders.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReceiptOwner(Base):
    __tablename__ = "receipt_wallet_orders"
    order_id: Mapped[str] = mapped_column(ForeignKey("sale_orders.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    wallet_id: Mapped[str] = mapped_column(ForeignKey("receipt_guest_wallets.id", ondelete="CASCADE"), nullable=False)
    member_id: Mapped[str | None] = mapped_column(ForeignKey("receipt_members.id", ondelete="SET NULL"), nullable=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ClaimInput(BaseModel):
    token: str = Field(min_length=30, max_length=120)


class GoogleInput(BaseModel):
    credential: str = Field(min_length=50, max_length=10000)


class ProfileInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=8, max_length=30)


class PolicyInput(BaseModel):
    paperless_enabled: bool
    loyalty_enabled: bool
    spend_vnd_per_point: int = Field(ge=1000, le=1000000)


def safe_origin(request: Request):
    # Same-origin mutation only; Lax cookies alone do not defend login CSRF.
    source = request.headers.get("origin", "")
    expected = str(request.base_url).rstrip("/")
    if not source or not hmac.compare_digest(source.encode(), expected.encode()):
        deny(403, "Invalid request origin")


def put_cookie(response: Response, name: str, token: str, max_age: int):
    response.set_cookie(
        name, token, httponly=True, secure=os.getenv("COOKIE_SECURE", "0") == "1",
        samesite="lax", max_age=max_age, path="/",
    )


def guest_wallet(request: Request, db: Session) -> GuestWallet | None:
    token = request.cookies.get(COOKIE_GUEST, "")
    if not token:
        return None
    return db.scalar(select(GuestWallet).where(GuestWallet.secret_hash == digest(token)))


def signed_member(request: Request, db: Session) -> Member | None:
    token = request.cookies.get(COOKIE_MEMBER, "")
    if not token:
        return None
    row = db.get(MemberSession, digest(token))
    if not row:
        return None
    expires = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    if expires <= datetime.now(timezone.utc):
        return None
    return db.get(Member, row.member_id)


def member_public(member: Member | None):
    return None if member is None else {
        "id": member.member_code, "name": member.name, "phone": member.phone,
        "email": member.email, "profile_complete": bool(member.name.strip() and member.phone.strip()),
    }


def receipt_view(db: Session, order: SaleOrder):
    business = db.get(Business, order.business_id)
    branch = db.get(Branch, order.branch_id)
    rows = db.scalars(select(SaleOrderItem).where(
        SaleOrderItem.order_id == order.id,
        SaleOrderItem.business_id == order.business_id)).all()
    from .modifiers import order_selection_map
    options = order_selection_map(db, order.business_id, rows)
    return {
        "order_number": order.id[:8].upper(), "order_id": order.id,
        "business_id": order.business_id, "business_name": business.name if business else "",
        "branch": branch.name if branch else "",
        "date": (order.paid_at or order.created_at).isoformat(),
        "status": order.status, "total_vnd": order.total_vnd,
        "items": [
            {"name": row.product_name, "quantity": row.quantity,
             "unit_price_vnd": row.unit_price_vnd, "total_vnd": row.total_vnd,
             "modifiers": options.get(row.id, [])}
            for row in rows
        ],
        "document_type": "purchase_receipt", "is_tax_invoice": False,
    }


def assign_member_customer(db: Session, order: SaleOrder, member: Member):
    """Reuse the EXISTING customer/loyalty ledger; never replace another customer."""
    if not member.name.strip() or not member.phone.strip():
        return
    mapping = db.get(MemberCustomer, (order.business_id, member.id))
    if mapping is None:
        c = Customer(id=uid(), business_id=order.business_id, name=member.name,
                     phone=member.phone, address="")
        db.add(c)
        db.flush()
        mapping = MemberCustomer(business_id=order.business_id,
                                 member_id=member.id, customer_id=c.id)
        db.add(mapping)
        db.flush()
    if order.customer_id is None:
        order.customer_id = mapping.customer_id
        db.flush()
    if order.customer_id == mapping.customer_id and order.status == "paid":
        from .operations_v5 import loyalty_earn_on_paid
        loyalty_earn_on_paid(db, order.business_id, order)


def member_receipt_claims(db: Session, member: Member, wallet: GuestWallet | None):
    if wallet:
        for receipt in db.scalars(select(ReceiptOwner).where(
                ReceiptOwner.wallet_id == wallet.id).with_for_update()):
            if receipt.member_id is None:
                receipt.member_id = member.id
                order = db.get(SaleOrder, receipt.order_id)
                if order:
                    assign_member_customer(db, order, member)
    # When a profile is finished after Google sign-in, apply points to prior claims.
    if member.name.strip() and member.phone.strip():
        for receipt in db.scalars(select(ReceiptOwner).where(
                ReceiptOwner.member_id == member.id).with_for_update()):
            order = db.get(SaleOrder, receipt.order_id)
            if order:
                assign_member_customer(db, order, member)


def policy_for(b: Business):
    raw = (b.setup or {}).get("paperless_loyalty") or {}
    return {
        "paperless_enabled": bool(raw.get("paperless_enabled", False)),
        "loyalty_enabled": bool(raw.get("loyalty_enabled", True)),
        "spend_vnd_per_point": int(raw.get("spend_vnd_per_point", 10000)),
    }


@router.get("/api/wallet/config")
def wallet_config():
    client = os.getenv("EZ_GOOGLE_CLIENT_ID", "").strip()
    return {"google_client_id": client, "member_login_available": bool(client)}


@router.get("/api/wallet/me")
def wallet_me(request: Request, db: Session = Depends(db_session)):
    wallet = guest_wallet(request, db)
    member = signed_member(request, db)
    if not wallet and not member:
        return {"member": None, "receipts": [], "balances": []}
    filters = []
    if wallet:
        filters.append(ReceiptOwner.wallet_id == wallet.id)
    if member:
        filters.append(ReceiptOwner.member_id == member.id)
    owned = db.scalars(select(ReceiptOwner).where(or_(*filters))
                       .order_by(ReceiptOwner.claimed_at.desc()).limit(200)).all()
    orders = [db.get(SaleOrder, r.order_id) for r in owned]
    receipts = [receipt_view(db, o) for o in orders if o and o.status == "paid"]
    balances = []
    if member:
        from .workflows import IndustryWorkItem
        mappings = db.scalars(select(MemberCustomer).where(MemberCustomer.member_id == member.id)).all()
        for mapping in mappings:
            entries = db.scalars(select(IndustryWorkItem).where(
                IndustryWorkItem.business_id == mapping.business_id,
                IndustryWorkItem.kind == "loyalty",
                IndustryWorkItem.customer_id == mapping.customer_id)).all()
            b = db.get(Business, mapping.business_id)
            balances.append({"business_id": mapping.business_id,
                             "business_name": b.name if b else "",
                             "points": sum(int((x.details or {}).get("points", 0)) for x in entries)})
    return {"member": member_public(member), "receipts": receipts, "balances": balances}


@router.post("/api/businesses/{bid}/paperless/{oid}/share")
def share_receipt(bid: str, oid: str, request: Request, user=Depends(current_user),
                  db: Session = Depends(db_session)):
    safe_origin(request)
    tenant(bid, user, db)
    duty = require_duty(db, bid, user, {"order", "cashier"})
    from .team import require_branch
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.id == oid, SaleOrder.business_id == bid).with_for_update())
    if not order:
        deny(404, "Order not found")
    require_branch(duty, order.branch_id)
    if order.status != "paid":
        deny(409, "Only confirmed paid orders can be shared")
    token = fresh()
    row = db.get(ReceiptClaim, oid)
    if row is None:
        row = ReceiptClaim(order_id=oid, business_id=bid, secret_hash=digest(token),
                           expires_at=now() + timedelta(seconds=QR_TTL_SECONDS))
        db.add(row)
    else:
        # A claimed receipt stays bound to the first wallet. Re-sharing does not
        # authorize a new owner and the QR becomes a lookup for that same wallet.
        if row.claimed_at is not None:
            deny(409, "Receipt already saved to a customer wallet")
        row.secret_hash = digest(token)
        row.expires_at = now() + timedelta(seconds=QR_TTL_SECONDS)
    db.commit()
    url = str(request.base_url).rstrip("/") + "/receipt#" + token
    image = qrcode.make(url)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return {"order_number": oid[:8].upper(), "url": url,
            "qr_png_base64": base64.b64encode(output.getvalue()).decode("ascii"),
            "valid_for_seconds": QR_TTL_SECONDS}


@router.post("/api/wallet/claim")
def claim_receipt(body: ClaimInput, request: Request, response: Response,
                  db: Session = Depends(db_session)):
    safe_origin(request)
    row = db.scalar(select(ReceiptClaim).where(
        ReceiptClaim.secret_hash == digest(body.token)).with_for_update())
    if not row:
        deny(404, "Receipt QR invalid or replaced")
    expires = row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at
    wallet = guest_wallet(request, db)
    member = signed_member(request, db)
    linked = db.get(ReceiptOwner, row.order_id)
    if row.claimed_at is not None or linked is not None:
        if linked and ((wallet and linked.wallet_id == wallet.id) or
                       (member and linked.member_id == member.id)):
            order = db.get(SaleOrder, row.order_id)
            return {"receipt": receipt_view(db, order), "already_saved": True}
        deny(410, "Receipt QR already claimed")
    if expires <= datetime.now(timezone.utc):
        deny(410, "Receipt QR expired; ask the cashier to show a new one")
    order = db.get(SaleOrder, row.order_id)
    if not order or order.status != "paid" or order.business_id != row.business_id:
        deny(409, "Receipt is not paid")
    if not wallet:
        secret = fresh()
        wallet = GuestWallet(id=uid(), secret_hash=digest(secret))
        db.add(wallet)
        put_cookie(response, COOKIE_GUEST, secret, GUEST_MAX_AGE)
    db.add(ReceiptOwner(order_id=order.id, business_id=order.business_id,
                        wallet_id=wallet.id, member_id=member.id if member else None))
    row.claimed_at = now()
    db.flush()
    if member:
        assign_member_customer(db, order, member)
    db.commit()
    return {"receipt": receipt_view(db, order), "already_saved": False}


@router.post("/api/wallet/google")
def google_signin(body: GoogleInput, request: Request, response: Response,
                  db: Session = Depends(db_session)):
    safe_origin(request)
    audience = os.getenv("EZ_GOOGLE_CLIENT_ID", "").strip()
    if not audience:
        deny(503, "Google Member Sign-In is not configured")
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    try:
        claims = id_token.verify_oauth2_token(body.credential, google_requests.Request(), audience)
    except (ValueError, Exception):
        deny(401, "Invalid Google identity token")
    sub = str(claims.get("sub") or "")
    email = str(claims.get("email") or "")
    if not sub or not claims.get("email_verified") or not email or len(sub) > 255:
        deny(401, "Verified Google identity required")
    member = db.scalar(select(Member).where(Member.google_sub == sub).with_for_update())
    if not member:
        member = Member(id=uid(), google_sub=sub, email=email,
                        name="", phone="", member_code=secrets.token_hex(10).upper())
        db.add(member)
        db.flush()
    else:
        member.email = email
    wallet = guest_wallet(request, db)
    member_receipt_claims(db, member, wallet)
    secret = fresh()
    db.add(MemberSession(token_hash=digest(secret), member_id=member.id,
                         expires_at=now() + timedelta(seconds=MEMBER_MAX_AGE)))
    db.commit()
    put_cookie(response, COOKIE_MEMBER, secret, MEMBER_MAX_AGE)
    return {"member": member_public(member)}


@router.post("/api/wallet/profile")
def save_profile(body: ProfileInput, request: Request,
                 db: Session = Depends(db_session)):
    safe_origin(request)
    member = signed_member(request, db)
    if not member:
        deny(401, "Sign in with Google first")
    name = body.name.strip()
    phone = body.phone.strip()
    if len(name) < 2 or not re.fullmatch(r"\+?[0-9() .-]{8,30}", phone):
        deny(422, "Enter a valid name and phone number")
    member.name = name
    member.phone = phone
    wallet = guest_wallet(request, db)
    member_receipt_claims(db, member, wallet)
    # Keep the tenant customer names in sync only for this verified member.
    for mapping in db.scalars(select(MemberCustomer).where(MemberCustomer.member_id == member.id)):
        customer = db.get(Customer, mapping.customer_id)
        if customer:
            customer.name, customer.phone = name, phone
    db.commit()
    return {"member": member_public(member)}


@router.post("/api/wallet/logout")
def member_logout(request: Request, response: Response,
                  db: Session = Depends(db_session)):
    safe_origin(request)
    token = request.cookies.get(COOKIE_MEMBER, "")
    if token:
        session = db.get(MemberSession, digest(token))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(COOKIE_MEMBER, path="/", samesite="lax")
    return {"ok": True}


@router.get("/api/businesses/{bid}/paperless/settings")
def merchant_policy(bid: str, user=Depends(current_user),
                    db: Session = Depends(db_session)):
    business = tenant(bid, user, db)
    return policy_for(business)


@router.put("/api/businesses/{bid}/paperless/settings")
def update_policy(bid: str, body: PolicyInput, request: Request,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    safe_origin(request)
    business = tenant(bid, user, db)
    allow(db, bid, user, MANAGE_ROLES)
    from sqlalchemy.orm.attributes import flag_modified
    setup = dict(business.setup or {})
    setup["paperless_loyalty"] = body.model_dump()
    business.setup = setup
    flag_modified(business, "setup")
    db.commit()
    return policy_for(business)


@router.get("/api/businesses/{bid}/paperless/members")
def merchant_members(bid: str, user=Depends(current_user),
                     db: Session = Depends(db_session)):
    tenant(bid, user, db)
    allow(db, bid, user, MANAGE_ROLES)
    from .workflows import IndustryWorkItem
    mappings = db.scalars(select(MemberCustomer).where(MemberCustomer.business_id == bid)
                          .limit(200)).all()
    result = []
    for mapping in mappings:
        member = db.get(Member, mapping.member_id)
        customer = db.get(Customer, mapping.customer_id)
        if not member or not customer:
            continue
        entries = db.scalars(select(IndustryWorkItem).where(
            IndustryWorkItem.kind == "loyalty",
            IndustryWorkItem.business_id == bid,
            IndustryWorkItem.customer_id == customer.id)).all()
        result.append({"member_code": member.member_code, "name": customer.name,
                       "phone": customer.phone, "points": sum(
                           int((x.details or {}).get("points", 0)) for x in entries)})
    return result
