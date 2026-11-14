"""Opt-in verified-email registration. Old accounts remain valid by design.

Enable only when SMTP credentials and a canonical HTTPS public URL are present.
Token is random, hashed in the database, expires in 30 minutes and cannot be
used twice. No mail credentials or tokens are logged or stored in the session.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import User, now

router = APIRouter(prefix="/api/auth", tags=["Verified email"])


class EmailVerification(Base):
    __tablename__ = "auth_email_verifications"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sends_count: Mapped[int] = mapped_column(Integer, default=1)


class ConfirmEmail(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class ResendEmail(BaseModel):
    email: EmailStr


def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def verification_required() -> bool:
    return os.getenv("EZ_THING_REQUIRE_VERIFIED_EMAIL") == "1"


def mail_config() -> tuple[str, int, str, str, str, str]:
    """Required before opting into verified signups; no insecure fallback."""
    server = os.getenv("EZ_THING_SMTP_HOST", "").strip()
    username = os.getenv("EZ_THING_SMTP_USER", "").strip()
    password = os.getenv("EZ_THING_SMTP_PASSWORD", "")
    sender = os.getenv("EZ_THING_SMTP_FROM", "").strip()
    base = os.getenv("EZ_THING_PUBLIC_BASE_URL", "").strip().rstrip("/")
    port = os.getenv("EZ_THING_SMTP_PORT", "587")
    if not (server and username and password and sender and
            base.startswith("https://") and "/" not in base[8:] and
            port.isdigit() and 1 <= int(port) <= 65535):
        raise HTTPException(503, "Xác minh email chưa được cấu hình đầy đủ")
    return server, int(port), username, password, sender, base


def token_pair():
    token = secrets.token_urlsafe(36)
    return token, hashlib.sha256(token.encode("utf-8")).hexdigest()


def pending_for_signup(db: Session, user: User) -> str:
    token, hashed = token_pair()
    db.add(EmailVerification(
        user_id=user.id, token_hash=hashed,
        expires_at=now() + timedelta(minutes=30), sent_at=now(),
        sends_count=1,
    ))
    return token


def verified(db: Session, user: User) -> bool:
    row = db.get(EmailVerification, user.id)
    # Existing users were created before the optional verification gate.
    return row is None or row.verified_at is not None


def send_verification(user: User, token: str) -> None:
    server, port, username, password, sender, base = mail_config()
    url = base + "/app#verify=" + token
    message = EmailMessage()
    message["From"] = sender
    message["To"] = user.email
    message["Subject"] = "EZ Thing - Xac minh dia chi email"
    message.set_content(
        "Xac minh email dang ky EZ Thing trong 30 phut.\n\n" + url +
        "\n\nNeu ban khong dang ky, vui long bo qua email nay."
    )
    try:
        with smtplib.SMTP(server, port, timeout=9) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        # Do not log the exception; some mail transports include secrets.
        raise HTTPException(503, "Không gửi được email xác minh. Vui lòng thử gửi lại.") from None


@router.post("/verify-email")
def confirm_email(body: ConfirmEmail, db: Session = Depends(db_session)):
    hashed = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    row = db.scalar(select(EmailVerification).where(
        EmailVerification.token_hash == hashed).with_for_update())
    if row is None or row.verified_at is not None or utc(row.expires_at) <= now():
        raise HTTPException(400, "Link xác minh không hợp lệ hoặc đã hết hạn")
    row.verified_at = now()
    row.token_hash = hashlib.sha256(("consumed:" + row.user_id + ":" + secrets.token_hex(16)).encode()).hexdigest()
    db.commit()
    return {"ok": True, "email_verified": True}


@router.post("/resend-verification")
def resend(body: ResendEmail, request: Request, db: Session = Depends(db_session)):
    # Consistent response for nonexistent, verified and pending identities;
    # never expose whether an email exists.
    generic = {"ok": True, "message": "Nếu tài khoản cần xác minh, email sẽ được gửi lại."}
    if not verification_required():
        return generic
    mail_config()
    email = str(body.email).strip().lower()
    u = db.scalar(select(User).where(User.email == email))
    if not u:
        return generic
    row = db.scalar(select(EmailVerification).where(
        EmailVerification.user_id == u.id).with_for_update())
    if not row or row.verified_at is not None:
        return generic
    current = now()
    if row.sends_count >= 5 or utc(row.sent_at) > current - timedelta(seconds=90):
        return generic
    token, hashed = token_pair()
    row.token_hash = hashed
    row.expires_at = current + timedelta(minutes=30)
    row.sent_at = current
    row.sends_count += 1
    db.commit()
    send_verification(u, token)
    return generic
