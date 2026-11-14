"""EZ Thing 7-day no-card trial and VNPAY hosted billing (staging pilot).

Never accepts card PAN, CVV, bank credentials or client-supplied amounts.
Trial does not auto-renew. Real settlement is ONLY from a signed VNPAY IPN.
Legacy pilot/demo businesses are left untouched.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .catalog import PLANS
from .database import Base, db_session
from .models import Business, Membership, now

router = APIRouter(tags=["Trial and subscription billing"])
LOCAL = ZoneInfo("Asia/Ho_Chi_Minh")
TRIAL_DAYS = 7
PLAN_CODES = frozenset(("BASIC", "PLUS", "PRO"))
BANK_CODES = {"card": "INTCARD", "bank": "VNBANK", "qr": "VNPAYQR"}


class BillingSubscription(Base):
    __tablename__ = "billing_subscriptions"
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True
    )
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    trial_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_plan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BillingCheckout(Base):
    __tablename__ = "billing_checkouts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    txn_ref: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(10))
    channel: Mapped[str] = mapped_column(String(16))
    amount_vnd: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="pending")
    provider_transaction: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StartCheckout(BaseModel):
    plan: Literal["BASIC", "PLUS", "PRO"]
    channel: Literal["card", "bank", "qr"] = "card"


def utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def trial_enabled() -> bool:
    return os.getenv("EZ_THING_TRIAL_ENABLED", "0") == "1"


def start_trial(db: Session, b: Business, owner_id: str):
    if not trial_enabled():
        return
    date = now()
    db.add(BillingSubscription(
        business_id=b.id, owner_user_id=owner_id, trial_started_at=date,
        trial_ends_at=date + timedelta(days=TRIAL_DAYS), active_plan=None,
    ))
    b.subscription_status = "trial"
    b.plan = "PRO"       # Temporary full module access, NOT a purchased plan.
    b.requested_plan = "BASIC"


def summary(db: Session, business: Business) -> dict:
    sub = db.get(BillingSubscription, business.id)
    if sub is None:
        return {"status": business.subscription_status, "plan": business.plan,
                "trial_ends_at": None, "period_end": None, "days_remaining": None,
                "requires_payment": False, "auto_renew": False}
    moment = now()
    if sub.active_plan:
        state = "active" if utc(sub.period_end) and utc(sub.period_end) > moment else "expired"
        expiration = sub.period_end
    else:
        state = "trialing" if utc(sub.trial_ends_at) > moment else "trial_expired"
        expiration = sub.trial_ends_at
    remaining = max(0, (utc(expiration) - moment).total_seconds())
    return {"status": state, "plan": sub.active_plan,
            "trial_started_at": utc(sub.trial_started_at).isoformat(),
            "trial_ends_at": utc(sub.trial_ends_at).isoformat(),
            "period_end": utc(sub.period_end).isoformat() if sub.period_end else None,
            "days_remaining": int((remaining + 86399) // 86400),
            "requires_payment": state in ("trial_expired", "expired"),
            "auto_renew": False, "currency": "VND"}


def require_access(db: Session, b: Business):
    # Legacy pilots and isolated synthetic demos remain working.
    sub = db.get(BillingSubscription, b.id)
    if not sub:
        if b.subscription_status in ("trial", "active"):
            raise HTTPException(402, "Thuê bao chưa được xác thực")
        return
    if summary(db, b)["requires_payment"]:
        raise HTTPException(402, "Dùng thử đã kết thúc. Vui lòng chọn gói và thanh toán trong mục Billing.")


def owner_business(db: Session, bid: str, user):
    from .main import fail
    b = db.get(Business, bid)
    membership = db.scalar(select(Membership).where(
        Membership.business_id == bid, Membership.user_id == user[0].id,
        Membership.role == "owner"))
    if not b or membership is None:
        fail(403, "Chỉ chủ doanh nghiệp được quản lý thanh toán")
    from .platform_admin import is_business_blocked
    if is_business_blocked(db, bid):
        fail(403, "Doanh nghiệp đang bị tạm khóa")
    return b


def vnpay_ready() -> bool:
    # Explicit staged rollout; no arbitrary gateway or unverified live URLs.
    return (os.getenv("EZ_THING_ENVIRONMENT") == "staging" and
            os.getenv("EZ_THING_BILLING_ENV", "sandbox") == "sandbox" and
            len(os.getenv("VNPAY_TMN_CODE", "")) >= 8 and
            len(os.getenv("VNPAY_HASH_SECRET", "")) >= 16 and
            valid_base_url())


def valid_base_url() -> bool:
    url = os.getenv("EZ_THING_PUBLIC_BASE_URL", "")
    parsed = urlparse(url)
    return bool(parsed.scheme == "https" and parsed.hostname and
                not parsed.username and not parsed.password and
                not parsed.path.strip("/") and not parsed.query and not parsed.fragment)


def pay_base_url() -> str:
    return "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"


def signed_payload(params: dict[str, str]) -> str:
    return urlencode(sorted(params.items()))


def sign(params: dict[str, str]) -> str:
    secret = os.getenv("VNPAY_HASH_SECRET", "")
    if len(secret) < 16:
        raise RuntimeError("VNPAY credentials are not configured")
    return hmac.new(secret.encode(), signed_payload(params).encode(), hashlib.sha512).hexdigest()


def industry_modules(b: Business, plan: str) -> list[str]:
    # Same built-in entitlement catalog; paid activation cannot mint unknown modules.
    industry_only = {
        "tables": "fnb", "kitchen": "fnb", "stock_ledger": "retail",
        "fulfillment": "online", "appointments": "services"
    }
    setup = b.setup or {}
    modules = set(PLANS[plan]["features"])
    modules = {m for m in modules if m not in industry_only or industry_only[m] == b.industry}
    if b.industry == "fnb" and not setup.get("need_tables", True):
        modules.discard("tables")
    if not setup.get("need_inventory", True):
        modules -= {"inventory_adjust", "inventory_basic"}
    return sorted(modules)


@router.get("/api/businesses/{bid}/billing")
def get_billing(bid: str, user=Depends(__import__("app.main", fromlist=["current_user"]).current_user),
                db: Session = Depends(db_session)):
    b = owner_business(db, bid, user)
    status = summary(db, b)
    rows = db.scalars(select(BillingCheckout).where(
        BillingCheckout.business_id == bid
    ).order_by(BillingCheckout.created_at.desc()).limit(50)).all()
    return {
        **status,
        "plans": [{"code": p, "amount_vnd": PLANS[p]["price_vnd"],
                   "currency": "VND", "billing_period": "30_days"}
                  for p in ("BASIC", "PLUS", "PRO")],
        "checkout_ready": vnpay_ready(),
        "payment_channels": ["card", "bank", "qr"],
        "card_vault_available": False,
        "saved_cards": [],
        "provider": "vnpay_sandbox" if vnpay_ready() else "unconfigured",
        "transactions": [{
            "id": item.id, "reference": item.txn_ref, "plan": item.plan,
            "amount_vnd": item.amount_vnd, "channel": item.channel,
            "status": item.status, "created_at": utc(item.created_at).isoformat(),
            "paid_at": utc(item.paid_at).isoformat() if item.paid_at else None,
        } for item in rows],
        "notice": "One-time hosted checkout. No auto-renewal. No card data is stored by EZ Thing.",
    }


@router.post("/api/businesses/{bid}/billing/checkout", status_code=201)
def create_checkout(bid: str, body: StartCheckout, request: Request,
                    user=Depends(__import__("app.main", fromlist=["current_user"]).current_user),
                    db: Session = Depends(db_session)):
    from .main import audit, fail, new_id
    b = owner_business(db, bid, user)
    sub = db.scalar(select(BillingSubscription).where(
        BillingSubscription.business_id == bid).with_for_update())
    if sub is None or b.subscription_status == "demo":
        fail(403, "Chức năng thanh toán chỉ dành cho tài khoản dùng thử thật")
    if not vnpay_ready():
        fail(503, "Thanh toán thẻ/QR chưa được cấp tài khoản VNPAY Sandbox.")
    if sub.active_plan and summary(db, b)["status"] == "active":
        fail(409, "Gói còn hiệu lực. Chức năng gia hạn và đổi gói sẽ được triển khai riêng.")
    price = int(PLANS[body.plan]["price_vnd"])  # Never trust any client amount.
    reference = secrets.token_hex(12)
    created = now().astimezone(LOCAL)
    expire = created + timedelta(minutes=15)
    attempt = BillingCheckout(
        id=new_id(), business_id=bid, txn_ref=reference, plan=body.plan,
        channel=body.channel, amount_vnd=price, status="pending"
    )
    db.add(attempt)
    audit(db, bid, user[0].id, "billing.checkout_created", {
        "reference": reference, "plan": body.plan, "price_vnd": price,
        "provider": "vnpay_sandbox",
    })
    db.commit()
    params = {
        "vnp_Version": "2.1.0", "vnp_Command": "pay",
        "vnp_TmnCode": os.environ["VNPAY_TMN_CODE"],
        "vnp_Amount": str(price * 100), "vnp_CurrCode": "VND",
        "vnp_TxnRef": reference,
        "vnp_OrderInfo": f"EZ Thing plan {body.plan} {reference}",
        "vnp_OrderType": "other",
        "vnp_CreateDate": created.strftime("%Y%m%d%H%M%S"),
        "vnp_ExpireDate": expire.strftime("%Y%m%d%H%M%S"),
        "vnp_IpAddr": request.client.host if request.client else "127.0.0.1",
        "vnp_Locale": "en" if request.headers.get("accept-language", "").startswith("en") else "vn",
        "vnp_BankCode": BANK_CODES[body.channel],
        "vnp_ReturnUrl": os.environ["EZ_THING_PUBLIC_BASE_URL"].rstrip("/") + "/api/billing/vnpay/return",
    }
    return {"status": "pending", "checkout_id": attempt.id,
            "redirect_url": pay_base_url() + "?" + signed_payload(params) +
                            "&vnp_SecureHash=" + sign(params)}


def ipn_answer(code: str, message: str):
    return {"RspCode": code, "Message": message}


def callback_params(request: Request) -> dict[str, str] | None:
    pairs = list(request.query_params.multi_items())
    if len(pairs) != len({key for key, _ in pairs}):
        return None
    return dict(pairs)


def valid_ipn(params: dict[str, str] | None) -> bool:
    if not params or not vnpay_ready():
        return False
    given = params.get("vnp_SecureHash", "")
    fields = {k: v for k, v in params.items() if k.startswith("vnp_") and
              k not in ("vnp_SecureHash", "vnp_SecureHashType")}
    return len(given) == 128 and hmac.compare_digest(sign(fields), given.lower())


@router.get("/api/billing/vnpay/ipn")
def vnpay_ipn(request: Request, db: Session = Depends(db_session)):
    """Idempotent server-to-server verification. Browser return NEVER grants access."""
    params = callback_params(request)
    if not valid_ipn(params):
        return ipn_answer("97", "Invalid signature")
    if params.get("vnp_TmnCode") != os.getenv("VNPAY_TMN_CODE"):
        return ipn_answer("97", "Invalid terminal")
    ref = params.get("vnp_TxnRef", "")
    order = db.scalar(select(BillingCheckout).where(
        BillingCheckout.txn_ref == ref).with_for_update())
    if order is None:
        return ipn_answer("01", "Order not found")
    if params.get("vnp_Amount") != str(order.amount_vnd * 100):
        return ipn_answer("04", "Invalid amount")
    if order.status != "pending":
        return ipn_answer("02", "Order already confirmed")
    if params.get("vnp_ResponseCode") != "00" or params.get("vnp_TransactionStatus") != "00":
        order.status = "failed"
        db.commit()
        return ipn_answer("00", "Payment failure recorded")
    subscription = db.scalar(select(BillingSubscription).where(
        BillingSubscription.business_id == order.business_id).with_for_update())
    b = db.scalar(select(Business).where(Business.id == order.business_id).with_for_update())
    if subscription is None or b is None:
        return ipn_answer("01", "Subscription not found")
    order.status = "paid"
    order.paid_at = now()
    order.provider_transaction = params.get("vnp_TransactionNo", "")[:50]
    subscription.active_plan = order.plan
    subscription.period_end = now() + timedelta(days=30)
    b.plan = order.plan
    b.requested_plan = order.plan
    b.active_modules = industry_modules(b, order.plan)
    b.subscription_status = "active"
    from .main import audit
    audit(db, b.id, subscription.owner_user_id, "billing.payment_verified", {
        "checkout_id": order.id, "plan": order.plan,
        "amount_vnd": order.amount_vnd, "provider": "vnpay_sandbox",
    })
    db.commit()
    return ipn_answer("00", "Confirm Success")


@router.get("/api/billing/vnpay/return")
def vnpay_return():
    # A successful browser redirect is NOT evidence of a successful payment.
    return RedirectResponse(url="/app?tab=billing&payment_return=1", status_code=303,
                            headers={"Cache-Control": "no-store"})
