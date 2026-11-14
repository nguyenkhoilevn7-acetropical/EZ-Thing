"""Seven-day no-card trial, tenant lockout and VNPAY signed-IPN tests."""
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.billing import BillingCheckout, BillingSubscription, sign
from app.main import app
from app.models import Business, Membership, now


@pytest.fixture(autouse=True)
def database(monkeypatch):
    monkeypatch.setenv("EZ_THING_TRIAL_ENABLED", "1")
    monkeypatch.delenv("VNPAY_TMN_CODE", raising=False)
    monkeypatch.delenv("VNPAY_HASH_SECRET", raising=False)
    monkeypatch.delenv("EZ_THING_ENVIRONMENT", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def cli():
    with TestClient(app) as client:
        yield client


def signup(client, tag="owner"):
    res = client.post("/api/auth/signup", json={
        "name": "Billing owner", "email": tag + "@example.com",
        "password": "SafePassword!123",
    })
    assert res.status_code == 201, res.text
    return res.json()["csrf_token"]


def create_business(client, csrf, industry="retail"):
    res = client.post("/api/businesses",
        headers={"x-csrf-token": csrf},
        json={"name": "Subscription test", "industry": industry,
              "selected_plan": "BASIC", "need_insights": False,
              "need_branches": False, "need_inventory": True})
    assert res.status_code == 201, res.text
    return res.json()


def post(client, csrf, path, body):
    return client.post(path, headers={"x-csrf-token": csrf}, json=body)


def expire_trial(bid):
    with SessionLocal() as db:
        sub = db.get(BillingSubscription, bid)
        sub.trial_ends_at = now() - timedelta(seconds=1)
        db.commit()


def setup_vnpay(monkeypatch):
    monkeypatch.setenv("EZ_THING_ENVIRONMENT", "staging")
    monkeypatch.setenv("EZ_THING_BILLING_ENV", "sandbox")
    monkeypatch.setenv("EZ_THING_PUBLIC_BASE_URL", "https://ez-thing-staging.onrender.com")
    monkeypatch.setenv("VNPAY_TMN_CODE", "TESTCODE")
    monkeypatch.setenv("VNPAY_HASH_SECRET", "local-testing-secret-key-never-live")


def test_trial_is_free_without_card_and_expires_on_server(cli):
    csrf = signup(cli)
    b = create_business(cli, csrf)
    bid = b["id"]
    assert b["subscription_status"] == "trialing"
    assert b["plan"] == "TRIAL"
    assert b["billing_required"] is False
    assert 1 <= b["trial_days_remaining"] <= 7
    assert "multi_branch" in b["active_modules"]  # all existing features on trial
    assert cli.get("/api/config").json()["trial_enabled"] is True
    assert cli.get(f"/api/businesses/{bid}/products").status_code == 200
    status = cli.get(f"/api/businesses/{bid}/billing").json()
    assert status["auto_renew"] is False
    assert status["saved_cards"] == []
    assert status["checkout_ready"] is False
    assert status["plan"] is None

    expire_trial(bid)
    listed = cli.get("/api/businesses").json()[0]
    assert listed["subscription_status"] == "trial_expired"
    assert listed["billing_required"] is True
    assert listed["trial_days_remaining"] == 0
    assert cli.get(f"/api/businesses/{bid}/products").status_code == 402
    assert post(cli, csrf, f"/api/businesses/{bid}/customers", {
        "name": "Blocked customer"
    }).status_code == 402
    assert cli.get(f"/api/businesses/{bid}/billing").status_code == 200
    assert post(cli, csrf, f"/api/businesses/{bid}/billing/checkout", {
        "plan": "BASIC", "channel": "card"
    }).status_code == 503
    with SessionLocal() as db:
        assert db.get(BillingSubscription, bid).active_plan is None


def test_vnpay_card_sandbox_checkout_never_activates_on_redirect(cli, monkeypatch):
    setup_vnpay(monkeypatch)
    csrf = signup(cli)
    bid = create_business(cli, csrf)["id"]
    expire_trial(bid)
    res = post(cli, csrf, f"/api/businesses/{bid}/billing/checkout", {
        "plan": "BASIC", "channel": "card"
    })
    assert res.status_code == 201, res.text
    uri = urlparse(res.json()["redirect_url"])
    assert uri.scheme == "https" and uri.netloc == "sandbox.vnpayment.vn"
    fields = {k: v[0] for k, v in parse_qs(uri.query).items()}
    sig = fields.pop("vnp_SecureHash")
    assert sig == sign(fields)
    assert fields["vnp_Amount"] == "24900000"
    assert fields["vnp_BankCode"] == "INTCARD"
    assert fields["vnp_ExpireDate"]
    assert cli.get("/api/billing/vnpay/return", follow_redirects=False).status_code == 303
    assert cli.get(f"/api/businesses/{bid}/products").status_code == 402
    assert cli.get(f"/api/businesses/{bid}/billing").json()["transactions"][0]["status"] == "pending"

    payload = {
        "vnp_TxnRef": fields["vnp_TxnRef"], "vnp_TmnCode": "TESTCODE",
        "vnp_Amount": "24900000", "vnp_ResponseCode": "00",
        "vnp_TransactionStatus": "00", "vnp_TransactionNo": "123456789",
    }
    assert cli.get("/api/billing/vnpay/ipn", params=payload).json()["RspCode"] == "97"
    payload["vnp_SecureHash"] = sign(payload)
    assert cli.get("/api/billing/vnpay/ipn", params=payload).json()["RspCode"] == "00"
    assert cli.get("/api/billing/vnpay/ipn", params=payload).json()["RspCode"] == "02"
    b = cli.get("/api/businesses").json()[0]
    assert b["subscription_status"] == "active"
    assert b["plan"] == "BASIC"
    assert "multi_branch" not in b["active_modules"]
    assert cli.get(f"/api/businesses/{bid}/products").status_code == 200
    state = cli.get(f"/api/businesses/{bid}/billing").json()
    assert state["auto_renew"] is False
    assert state["transactions"][0]["status"] == "paid"
    assert post(cli, csrf, f"/api/businesses/{bid}/billing/checkout", {
        "plan": "PRO", "channel": "qr"
    }).status_code == 409


def test_ipn_rejects_bad_amount_and_does_not_activate(cli, monkeypatch):
    setup_vnpay(monkeypatch)
    token = signup(cli)
    bid = create_business(cli, token)["id"]
    attempt = post(cli, token, f"/api/businesses/{bid}/billing/checkout", {
        "plan": "PLUS", "channel": "bank"
    }).json()
    with SessionLocal() as db:
        ref = db.get(BillingCheckout, attempt["checkout_id"]).txn_ref
    request = {
        "vnp_TxnRef": ref, "vnp_TmnCode": "TESTCODE",
        "vnp_Amount": "1", "vnp_ResponseCode": "00",
        "vnp_TransactionStatus": "00", "vnp_TransactionNo": "567",
    }
    request["vnp_SecureHash"] = sign(request)
    assert cli.get("/api/billing/vnpay/ipn", params=request).json()["RspCode"] == "04"
    with SessionLocal() as db:
        assert db.get(BillingCheckout, attempt["checkout_id"]).status == "pending"
        assert db.get(BillingSubscription, bid).active_plan is None


def test_failed_signed_ipn_does_not_activate(cli, monkeypatch):
    setup_vnpay(monkeypatch)
    token = signup(cli)
    bid = create_business(cli, token)["id"]
    item = post(cli, token, f"/api/businesses/{bid}/billing/checkout", {
        "plan": "PRO", "channel": "qr"
    }).json()
    with SessionLocal() as db:
        ref = db.get(BillingCheckout, item["checkout_id"]).txn_ref
    request = {
        "vnp_TxnRef": ref, "vnp_TmnCode": "TESTCODE",
        "vnp_Amount": "99900000", "vnp_ResponseCode": "24",
        "vnp_TransactionStatus": "02",
    }
    request["vnp_SecureHash"] = sign(request)
    assert cli.get("/api/billing/vnpay/ipn", params=request).json()["RspCode"] == "00"
    with SessionLocal() as db:
        assert db.get(BillingCheckout, item["checkout_id"]).status == "failed"
        assert db.get(BillingSubscription, bid).active_plan is None


def test_only_owner_can_manage_billing_and_other_tenant_denied(cli):
    token = signup(cli)
    bid = create_business(cli, token)["id"]
    with TestClient(app) as other:
        second = signup(other, "other")
        assert other.get(f"/api/businesses/{bid}/billing").status_code == 403
        assert post(other, second, f"/api/businesses/{bid}/billing/checkout", {
            "plan": "BASIC", "channel": "card"
        }).status_code == 403
    with SessionLocal() as db:
        member = db.scalar(select(Membership).where(Membership.business_id == bid))
        member.role = "staff"
        db.commit()
    assert cli.get(f"/api/businesses/{bid}/billing").status_code == 403
