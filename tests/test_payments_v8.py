"""V8 Payment Engine: fake webhook cannot settle and verified events settle once."""
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    monkeypatch.delenv("EZ_SEPAY_HMAC_SECRETS", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def call(c, method, path, data=None, csrf=None):
    return c.request(method, "/api" + path, json=data,
                     headers={"x-csrf-token": csrf} if csrf else {})


def owner(c):
    signup = call(c, "POST", "/auth/signup", {
        "name": "POS Payment Owner",
        "email": f"pos-{uuid.uuid4().hex[:16]}@example.com",
        "password": "SafePassword!123"})
    assert signup.status_code == 201, signup.text
    csrf = signup.json()["csrf_token"]
    biz = call(c, "POST", "/businesses", {
        "name": "POS Payment Cafe", "industry": "fnb",
        "selected_plan": "PRO", "need_tables": True,
        "need_inventory": True, "need_insights": True,
        "need_branches": True}, csrf)
    assert biz.status_code == 201, biz.text
    bid = biz.json()["id"]
    product = call(c, "POST", f"/businesses/{bid}/products", {
        "name": "Milk Tea", "sku": "TEA", "price_vnd": 35000, "track_stock": False}, csrf)
    assert product.status_code == 201, product.text
    order = call(c, "POST", f"/businesses/{bid}/orders", {
        "idempotency_key": uuid.uuid4().hex,
        "lines": [{"product_id": product.json()["id"], "quantity": 2}]}, csrf)
    assert order.status_code == 201, order.text
    return bid, csrf, order.json()["id"]


def bank(c, bid, csrf):
    r = call(c, "PUT", f"/businesses/{bid}/payments/bank", {
        "bank_bin": "970436", "account_number": "1234567890",
        "account_name": "CAFE TEST MERCHANT"}, csrf)
    assert r.status_code == 200, r.text


def new_intent(c, bid, oid, csrf, method="bank_qr", request_id=None):
    return call(c, "POST", f"/businesses/{bid}/payments/intents", {
        "order_id": oid, "method": method,
        "request_id": request_id or uuid.uuid4().hex}, csrf)


def send_webhook(c, bid, secret, payload, timestamp=None, tamper=False):
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    ts = str(timestamp if timestamp is not None else int(time.time()))
    sig = "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + raw,
                               hashlib.sha256).hexdigest()
    if tamper:
        sig = "sha256=" + "0" * 64
    return c.post(f"/api/payments/sepay/{bid}", content=raw, headers={
        "content-type": "application/json",
        "x-sepay-timestamp": ts, "x-sepay-signature": sig})


def payload(ref, amount=70000, account="1234567890", event_id=92704):
    return {
        "id": event_id, "gateway": "Vietcombank",
        "accountNumber": account, "code": ref,
        "content": ref + " thanh toan",
        "transferType": "in", "transferAmount": amount,
        "referenceCode": "FT24012345678"}


def test_qr_no_manual_paid_and_verified_once(client, monkeypatch):
    bid, csrf, oid = owner(client)
    bank(client, bid, csrf)
    secret = "test-sepay-secret-with-strong-hmac-minimum-32"
    monkeypatch.setenv("EZ_SEPAY_HMAC_SECRETS", json.dumps({bid: secret}))
    key = "qr-pending-idempotent-request-01"
    payment = new_intent(client, bid, oid, csrf, request_id=key)
    assert payment.status_code == 201, payment.text
    data = payment.json()
    assert data["amount_vnd"] == 70000
    assert data["status"] == "pending"
    assert "970436-1234567890" in data["qr_image_url"]
    assert data["reference"] in data["qr_image_url"]
    assert new_intent(client, bid, oid, csrf, request_id=key).status_code == 201
    assert call(client, "POST", f"/businesses/{bid}/orders/{oid}/paid", {
        "confirmed": True}, csrf).status_code == 409

    fake = send_webhook(client, bid, secret, payload(data["reference"]), tamper=True)
    assert fake.status_code == 401
    assert send_webhook(client, bid, secret, payload(data["reference"]),
                        timestamp=int(time.time())-1000).status_code == 401

    wrong_amount = send_webhook(client, bid, secret, payload(
        data["reference"], amount=50000, event_id=92705))
    assert wrong_amount.status_code == 200
    assert wrong_amount.json()["outcome"] == "review_required"
    assert client.get(f"/api/businesses/{bid}/orders").json()[0]["status"] == "open"

    settled = send_webhook(client, bid, secret, payload(data["reference"]))
    assert settled.status_code == 200, settled.text
    assert settled.json()["outcome"] == "settled"
    assert client.get(f"/api/businesses/{bid}/orders").json()[0]["status"] == "paid"
    assert send_webhook(client, bid, secret, payload(data["reference"])).json() == {
        "success": True, "outcome": "settled", "duplicate": True}
    assert send_webhook(client, bid, secret, payload(
        data["reference"], event_id=92706)).json()["outcome"] == "review_required"


def test_missing_secret_and_wrong_bank_cannot_settle(client, monkeypatch):
    bid, csrf, oid = owner(client)
    bank(client, bid, csrf)
    intent = new_intent(client, bid, oid, csrf).json()
    secret = "another-test-hmac-secret-that-is-long-enough"
    event = payload(intent["reference"], account="00000000")
    assert send_webhook(client, bid, secret, event).status_code == 503
    monkeypatch.setenv("EZ_SEPAY_HMAC_SECRETS", json.dumps({bid: secret}))
    r = send_webhook(client, bid, secret, event)
    assert r.status_code == 200 and r.json()["outcome"] == "review_required"
    assert client.get(f"/api/businesses/{bid}/orders").json()[0]["status"] == "open"
    # Changing merchant bank account supersedes all QR intents.
    bank(client, bid, csrf)
    assert send_webhook(client, bid, secret, payload(
        intent["reference"], event_id=92740)).json()["outcome"] == "review_required"


def test_tenant_isolation_and_card_never_auto_settles(client):
    bid, csrf, oid = owner(client)
    assert new_intent(client, bid, oid, csrf).status_code == 409
    card = new_intent(client, bid, oid, csrf, method="card")
    assert card.status_code == 201, card.text
    assert card.json()["status"] == "pending"
    assert "qr_image_url" not in card.json()
    with TestClient(app) as second:
        second_bid, second_csrf, _ = owner(second)
        assert second_bid != bid
        assert second.get(f"/api/businesses/{bid}/payments/bank").status_code == 404
        assert new_intent(second, bid, oid, second_csrf).status_code == 404
    assert call(client, "POST", f"/businesses/{bid}/orders/{oid}/paid", {
        "confirmed": True}, csrf).status_code == 409


def test_request_key_idempotency_and_bank_change(client):
    bid, csrf, oid = owner(client)
    bank(client, bid, csrf)
    key = "same-request-identifier-0001"
    a = new_intent(client, bid, oid, csrf, request_id=key)
    b = new_intent(client, bid, oid, csrf, request_id=key)
    assert a.status_code == 201 and a.json() == b.json()
    assert new_intent(client, bid, oid, csrf, method="card",
                      request_id=key).status_code == 409
    first = a.json()["id"]
    bank(client, bid, csrf)
    history = client.get(f"/api/businesses/{bid}/payments/orders/{oid}")
    assert history.status_code == 200
    assert history.json()[0]["id"] == first
    assert history.json()[0]["status"] == "superseded"
