"""DB-backed signup throttling before scrypt hashing and session creation.

Uses shared auth_login_failures table. Hashes untrusted identities; peer keys
should be additionally enforced at a CDN/edge gateway for production traffic.
"""
import hashlib
import os
from datetime import timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import LoginFailure, now


def utc(date):
    return date.replace(tzinfo=timezone.utc) if date and date.tzinfo is None else date


def signup_limit(db: Session, request: Request, email: str):
    peer = request.client.host if request.client else "unknown"
    # The salt can be rotated independently of password hashes. Configure
    # EZ_THING_RATE_LIMIT_SALT privately for production.
    salt = os.environ.get("EZ_THING_RATE_LIMIT_SALT", "ezthing-pilot-v1")
    identities = [
        ("email", email.strip().lower(), 8),
        ("peer", peer, 80),
    ]
    date = now()
    for category, identity, limit in identities:
        key = hashlib.sha256((salt + "|signup|" + category + "|" + identity).encode()).hexdigest()
        record = db.scalar(select(LoginFailure).where(
            LoginFailure.identity_hash == key).with_for_update())
        if record and utc(record.locked_until) and utc(record.locked_until) > date:
            raise HTTPException(429, "Quá nhiều lượt đăng ký. Vui lòng thử lại sau.")
        if record is None:
            record = LoginFailure(identity_hash=key, failures=0, window_started_at=date)
            db.add(record)
        if utc(record.window_started_at) <= date - timedelta(hours=1):
            record.failures = 0
            record.window_started_at = date
            record.locked_until = None
        record.failures += 1
        if record.failures >= limit:
            record.locked_until = date + timedelta(minutes=30)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent creation of the same bucket: refuse until next retry.
        raise HTTPException(429, "Đăng ký quá nhanh, vui lòng thử lại sau.")
