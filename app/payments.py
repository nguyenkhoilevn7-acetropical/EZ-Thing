"""POS Payment Engine V8: QR intents and verified SePay settlement.

No customer-entered proof, screenshot, QR display or terminal instruction
ever marks a check paid. Only a verified incoming webhook settles QR.
Card intents are explicitly pending until a real acquiring SDK exists.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import uuid
from urllib.parse import urlencode
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import db_session
from .main import audit, current_user, feature, tenant
from .models import SaleOrder, now
from .payment_models import MerchantBankAccount, POSPaymentEvent, POSPaymentIntent
from .team import MANAGE_ROLES, allow

merchant = APIRouter(prefix="/api/businesses/{bid}/payments", tags=["POS payments"])
provider = APIRouter(prefix="/api/payments", tags=["Verified POS payment events"])
REF = re.compile(r"^EZP[A-F0-9]{16}$")


class BankDetails(BaseModel):
    bank_bin: str = Field(pattern=r"^[0-9]{6}$")
    account_number: str = Field(pattern=r"^[0-9]{6,19}$")
    account_name: str = Field(min_length=5, max_length=100, pattern=r"^[^<>]*$")


class NewPaymentIntent(BaseModel):
    request_id: str = Field(min_length=12, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    order_id: str = Field(min_length=36, max_length=36)
    method: Literal["bank_qr", "card"]


def _error(status: int, detail: str):
    raise HTTPException(status_code=status, detail=detail)


def _intent_response(intent: POSPaymentIntent, account: MerchantBankAccount | None):
    result = {
        "id": intent.id, "order_id": intent.order_id,
        "method": intent.method, "amount_vnd": intent.amount_vnd,
        "reference": intent.reference, "status": intent.status,
        "automatic_payment_confirmation": intent.method == "bank_qr" and _sepay_secret(intent.business_id) is not None,
        "payment_completed": intent.status == "paid",
    }
    if intent.method == "bank_qr" and account:
        # Quick Link is rendered by the client's browser; this is NOT evidence of payment.
        path = f"{account.bank_bin}-{account.account_number}-compact2.png"
        query = urlencode({
            "amount": intent.amount_vnd, "addInfo": intent.reference,
            "accountName": account.account_name,
        })
        result.update({
            "bank_bin": account.bank_bin, "account_number": account.account_number,
            "account_name": account.account_name,
            "qr_image_url": f"https://img.vietqr.io/image/{path}?{query}",
        })
    return result


@merchant.get("/bank")
def get_bank(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "orders")
    account = db.get(MerchantBankAccount, bid)
    return {
        "configured": account is not None,
        "bank_bin": account.bank_bin if account else None,
        "account_number": account.account_number if account else None,
        "account_name": account.account_name if account else None,
        "sepay_webhook_configured": _sepay_secret(bid) is not None,
    }


@merchant.put("/bank")
def update_bank(bid: str, body: BankDetails, user=Depends(current_user),
                db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "orders")
    allow(db, bid, user, {"owner"})
    account = db.get(MerchantBankAccount, bid)
    if account is None:
        account = MerchantBankAccount(business_id=bid, **body.model_dump())
        db.add(account)
    else:
        for key, value in body.model_dump().items():
            setattr(account, key, value)
    # Any old QR must not auto-settle against an account that has been changed.
    db.execute(update(POSPaymentIntent).where(
        POSPaymentIntent.business_id == bid,
        POSPaymentIntent.method == "bank_qr",
        POSPaymentIntent.status == "pending",
    ).values(status="superseded"))
    audit(db, bid, user[0].id, "payments.bank_configured", {
        "bank_bin": body.bank_bin, "account_last4": body.account_number[-4:]})
    db.commit()
    return get_bank(bid, user, db)


@merchant.post("/intents", status_code=201)
def create_intent(bid: str, body: NewPaymentIntent, user=Depends(current_user),
                  db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "orders")
    allow(db, bid, user, {"owner", "manager", "staff"})
    existing = db.scalar(select(POSPaymentIntent).where(
        POSPaymentIntent.business_id == bid,
        POSPaymentIntent.request_id == body.request_id))
    account = db.get(MerchantBankAccount, bid)
    if existing:
        if existing.order_id != body.order_id or existing.method != body.method:
            _error(409, "Request ID was used for another payment")
        return _intent_response(existing, account)
    # Ensure check and payment cannot be raced with edit, cancellation or another
    # settlement transaction. PostgreSQL row locking provides serialization.
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.id == body.order_id,
        SaleOrder.business_id == bid).with_for_update())
    if order is None:
        _error(404, "Order not found")
    if order.status != "open" or order.total_vnd <= 0:
        _error(409, "Order is no longer payable")
    if body.method == "bank_qr" and account is None:
        _error(409, "Merchant bank account is not configured")
    # A different active intent must not remain present with an older amount.
    db.execute(update(POSPaymentIntent).where(
        POSPaymentIntent.business_id == bid,
        POSPaymentIntent.order_id == order.id,
        POSPaymentIntent.status == "pending",
    ).values(status="superseded"))
    intent = POSPaymentIntent(
        id=str(uuid.uuid4()), business_id=bid, branch_id=order.branch_id,
        order_id=order.id, request_id=body.request_id, method=body.method,
        amount_vnd=order.total_vnd, reference="EZP" + uuid.uuid4().hex[:16].upper(),
        status="pending")
    db.add(intent)
    audit(db, bid, user[0].id, "payments.intent_created", {
        "order_id": order.id, "intent_id": intent.id,
        "method": intent.method, "amount_vnd": intent.amount_vnd})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _error(409, "Concurrent payment request; reload and retry")
    return _intent_response(intent, account)


@merchant.get("/orders/{oid}")
def payment_history(bid: str, oid: str, user=Depends(current_user),
                    db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "orders")
    allow(db, bid, user, {"owner", "manager", "staff"})
    if not db.scalar(select(SaleOrder.id).where(
            SaleOrder.business_id == bid, SaleOrder.id == oid)):
        _error(404, "Order not found")
    account = db.get(MerchantBankAccount, bid)
    entries = db.scalars(select(POSPaymentIntent).where(
        POSPaymentIntent.business_id == bid,
        POSPaymentIntent.order_id == oid).order_by(
        POSPaymentIntent.created_at.desc()).limit(50)).all()
    return [_intent_response(row, account) for row in entries]


class CancelPaymentIntent(BaseModel):
    reason: str = Field(min_length=5, max_length=200)


@merchant.post("/intents/{intent_id}/cancel")
def cancel_intent(bid: str, intent_id: str, body: CancelPaymentIntent,
                  user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "orders")
    allow(db, bid, user, MANAGE_ROLES)
    intent = db.scalar(select(POSPaymentIntent).where(
        POSPaymentIntent.id == intent_id,
        POSPaymentIntent.business_id == bid).with_for_update())
    if intent is None:
        _error(404, "Payment intent not found")
    if intent.status == "pending":
        intent.status = "superseded"
        audit(db, bid, user[0].id, "payments.intent_cancelled", {
            "intent_id": intent.id, "order_id": intent.order_id,
            "reason": body.reason})
        db.commit()
    elif intent.status == "paid":
        _error(409, "A settled payment cannot be cancelled here")
    return _intent_response(intent, db.get(MerchantBankAccount, bid))


def _sepay_secret(bid: str):
    try:
        mapping = json.loads(os.getenv("EZ_SEPAY_HMAC_SECRETS", "{}"))
    except (ValueError, TypeError):
        return None
    secret = mapping.get(bid) if isinstance(mapping, dict) else None
    return secret if isinstance(secret, str) and len(secret) >= 32 else None


def _verify_signature(request: Request, raw: bytes, bid: str):
    secret = _sepay_secret(bid)
    if secret is None:
        _error(503, "SePay integration not configured")
    if len(raw) > 65536:
        _error(413, "Webhook payload too large")
    timestamp = request.headers.get("x-sepay-timestamp", "")
    signature = request.headers.get("x-sepay-signature", "")
    if not timestamp.isascii() or not timestamp.isdigit():
        _error(401, "Invalid SePay timestamp")
    if abs(int(time.time()) - int(timestamp)) > 300:
        _error(401, "Expired SePay webhook")
    expected = "sha256=" + hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        _error(401, "Invalid SePay signature")


def _sepay_reference(body: dict):
    # A transaction may have an extracted payment code or only a description.
    code = body.get("code")
    if isinstance(code, str) and REF.fullmatch(code.strip().upper()):
        return code.strip().upper()
    description = body.get("content", "")
    if not isinstance(description, str):
        return None
    matches = set(re.findall(r"(?<![A-Z0-9])EZP[A-F0-9]{16}(?![A-Z0-9])",
                             description.upper()))
    return next(iter(matches)) if len(matches) == 1 else None


@provider.post("/sepay/{bid}")
async def sepay_incoming(bid: str, request: Request, db: Session = Depends(db_session)):
    raw = await request.body()
    _verify_signature(request, raw, bid)
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        _error(422, "Invalid webhook JSON")
    if not isinstance(body, dict):
        _error(422, "Invalid webhook payload")
    event_id = body.get("id")
    amount = body.get("transferAmount")
    if type(event_id) is not int or event_id <= 0 or type(amount) is not int or amount <= 0:
        _error(422, "Invalid bank transaction fields")
    event_id = str(event_id)
    payload_hash = hashlib.sha256(raw).hexdigest()
    old = db.scalar(select(POSPaymentEvent).where(
        POSPaymentEvent.provider == "sepay",
        POSPaymentEvent.external_id == event_id))
    if old:
        if old.payload_sha256 != payload_hash or old.business_id != bid:
            _error(409, "Conflicting provider event")
        return {"success": True, "outcome": old.outcome, "duplicate": True}
    ref = _sepay_reference(body)
    intent = db.scalar(select(POSPaymentIntent).where(
        POSPaymentIntent.business_id == bid,
        POSPaymentIntent.reference == ref).with_for_update()) if ref else None
    account = db.get(MerchantBankAccount, bid)
    order = db.scalar(select(SaleOrder).where(
        SaleOrder.id == intent.order_id,
        SaleOrder.business_id == bid).with_for_update()) if intent else None
    incoming_account = body.get("accountNumber")
    valid = (
        body.get("transferType") == "in"
        and account is not None
        and incoming_account == account.account_number
        and intent is not None and order is not None
        and intent.method == "bank_qr" and intent.status == "pending"
        and order.status == "open" and order.total_vnd == amount
        and intent.amount_vnd == amount
    )
    outcome = "settled" if valid else "review_required"
    db.add(POSPaymentEvent(
        id=str(uuid.uuid4()), business_id=bid,
        payment_id=intent.id if intent else None,
        provider="sepay", external_id=event_id, amount_vnd=amount,
        outcome=outcome, payload_sha256=payload_hash))
    if valid:
        intent.status = "paid"
        intent.external_transaction_id = event_id
        intent.settled_at = now()
        order.status = "paid"
        order.paid_at = now()
        from .operations_v5 import loyalty_earn_on_paid
        from .printing import enqueue_receipt
        loyalty_earn_on_paid(db, bid, order)
        enqueue_receipt(db, bid, order)
        db.execute(update(POSPaymentIntent).where(
            POSPaymentIntent.business_id == bid,
            POSPaymentIntent.order_id == order.id,
            POSPaymentIntent.id != intent.id,
            POSPaymentIntent.status == "pending",
        ).values(status="superseded"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(POSPaymentEvent).where(
            POSPaymentEvent.provider == "sepay",
            POSPaymentEvent.external_id == event_id))
        if existing and existing.payload_sha256 == payload_hash and existing.business_id == bid:
            return {"success": True, "outcome": existing.outcome, "duplicate": True}
        _error(409, "Payment event conflict")
    return {"success": True, "outcome": outcome, "duplicate": False}
