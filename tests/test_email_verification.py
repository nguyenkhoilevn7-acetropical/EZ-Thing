"""Verified-email feature is fail-closed, opt-in, and token-safe."""
import os
from pathlib import Path
os.environ["DATABASE_URL"]="sqlite:///"+str(Path(__file__).parent/"pilot-tests.db")
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import User
from app.email_verification import EmailVerification


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    for name in ("EZ_THING_REQUIRE_VERIFIED_EMAIL","EZ_THING_SMTP_HOST",
                 "EZ_THING_SMTP_PORT","EZ_THING_SMTP_USER","EZ_THING_SMTP_PASSWORD",
                 "EZ_THING_SMTP_FROM","EZ_THING_PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def configure(monkeypatch):
    for name,value in {
        "EZ_THING_REQUIRE_VERIFIED_EMAIL":"1",
        "EZ_THING_SMTP_HOST":"mail.test.invalid",
        "EZ_THING_SMTP_USER":"test",
        "EZ_THING_SMTP_PASSWORD":"testing-only-credential",
        "EZ_THING_SMTP_FROM":"no-reply@test.invalid",
        "EZ_THING_PUBLIC_BASE_URL":"https://ez-thing-staging.onrender.com",
    }.items():
        monkeypatch.setenv(name,value)


def test_no_smtp_creates_no_unreachable_account(monkeypatch):
    monkeypatch.setenv("EZ_THING_REQUIRE_VERIFIED_EMAIL","1")
    with TestClient(app) as client:
        result=client.post("/api/auth/signup",json={
            "name":"Owner", "email":"owner-no-email@example.com",
            "password":"SafePassword!123"})
        assert result.status_code==503
        with SessionLocal() as db:
            assert db.scalar(select(User).where(User.email=="owner-no-email@example.com")) is None


def test_verification_token_cannot_be_reused_and_email_binds_to_user(monkeypatch):
    configure(monkeypatch)
    tokens=[]
    monkeypatch.setattr("app.email_verification.send_verification",
                        lambda user,token: tokens.append((user.email,token)))
    with TestClient(app) as cli:
        body={"name":"Owner","email":"verify-owner@example.com",
              "password":"SafePassword!123"}
        s=cli.post("/api/auth/signup",json=body)
        assert s.status_code==201,s.text
        assert s.json()["verification_required"] is True
        assert "csrf_token" not in s.json()
        assert not s.cookies.get("ez_session")
        assert len(tokens)==1 and tokens[0][0]==body["email"]
        login=cli.post("/api/auth/login",json={
            "email":body["email"],"password":body["password"]})
        assert login.status_code==403
        assert login.cookies.get("ez_session") is None
        assert "EMAIL_VERIFICATION_REQUIRED" in login.text
        wrong=cli.post("/api/auth/verify-email",json={"token":"not-a-real-token-with-at-least-32-characters"})
        assert wrong.status_code==400
        ok=cli.post("/api/auth/verify-email",json={"token":tokens[0][1]})
        assert ok.status_code==200,ok.text
        assert ok.json()["email_verified"] is True
        assert cli.post("/api/auth/verify-email",json={"token":tokens[0][1]}).status_code==400
        successful=cli.post("/api/auth/login",json={
            "email":body["email"],"password":body["password"]})
        assert successful.status_code==200
        assert successful.cookies.get("ez_session")
        with SessionLocal() as db:
            u=db.scalar(select(User).where(User.email==body["email"]))
            verification=db.get(EmailVerification,u.id)
            assert verification.verified_at is not None
            assert tokens[0][1] not in verification.token_hash


def test_resend_hides_account_existence_and_is_throttled(monkeypatch):
    from datetime import timedelta
    configure(monkeypatch)
    sent=[]
    monkeypatch.setattr("app.email_verification.send_verification",
                        lambda user, token: sent.append(token))
    with TestClient(app) as cli:
        body={"name":"Owner","email":"resend-owner@example.com",
              "password":"SafePassword!123"}
        assert cli.post("/api/auth/signup",json=body).status_code==201
        original=sent[0]
        unknown=cli.post("/api/auth/resend-verification",json={"email":"unknown@example.com"})
        early=cli.post("/api/auth/resend-verification",json={"email":body["email"]})
        assert early.status_code==200
        assert unknown.status_code==200
        assert early.json()==unknown.json()
        assert len(sent)==1
        with SessionLocal() as db:
            row=db.scalar(select(EmailVerification))
            row.sent_at=row.sent_at - timedelta(minutes=2)
            db.commit()
        late=cli.post("/api/auth/resend-verification",json={"email":body["email"]})
        assert late.status_code==200
        assert len(sent)==2 and sent[1]!=original
        assert cli.post("/api/auth/verify-email",json={"token":original}).status_code==400
        assert cli.post("/api/auth/verify-email",json={"token":sent[1]}).status_code==200


def test_old_user_can_still_log_in_if_verification_is_enabled_later(monkeypatch):
    with TestClient(app) as cli:
        body={"name":"Existing","email":"existing@example.com","password":"SafePassword!123"}
        assert cli.post("/api/auth/signup",json=body).status_code==201
        configure(monkeypatch)
        result=cli.post("/api/auth/login",json={"email":body["email"],"password":body["password"]})
        assert result.status_code==200
