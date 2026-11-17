"""Guest QR receipt security and Google-member loyalty, isolated staging database."""
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.workflows import IndustryWorkItem


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    monkeypatch.delenv("EZ_GOOGLE_CLIENT_ID", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def merchant(client, email):
    signup = client.post("/api/auth/signup", json={
        "name": "Paperless Owner", "email": email, "password": "SafePassword!123"
    })
    assert signup.status_code == 201, signup.text
    csrf = {"x-csrf-token": signup.json()["csrf_token"]}
    business = client.post("/api/businesses", headers=csrf, json={
        "name": "Paperless Coffee", "industry": "fnb", "selected_plan": "PRO",
        "need_tables": True, "need_inventory": True, "need_insights": True
    })
    assert business.status_code == 201, business.text
    bid = business.json()["id"]
    product = client.post(f"/api/businesses/{bid}/products", headers=csrf, json={
        "name": "Iced Tropical Tea", "sku": "TEA-ONE",
        "price_vnd": 35000, "track_stock": False
    })
    assert product.status_code == 201, product.text
    return csrf, bid, product.json()["id"]


def create_paid(client, csrf, bid, pid, paid=True):
    o = client.post(f"/api/businesses/{bid}/orders", headers=csrf, json={
        "idempotency_key": "receipt-order-" + str(len(client.cookies)) + "-" +
        __import__("uuid").uuid4().hex[:12],
        "lines": [{"product_id": pid, "quantity": 2}],
    })
    assert o.status_code == 201, o.text
    oid = o.json()["id"]
    if paid:
        settled = client.post(f"/api/businesses/{bid}/orders/{oid}/paid",
                              headers=csrf, json={"confirmed": True})
        assert settled.status_code == 200, settled.text
    return oid


def same_origin(client, method, url, payload, headers=None):
    return client.request(method, url,
        headers={"Origin": "http://testserver", **(headers or {})},
        json=payload)


def test_guest_claim_one_time_no_identity_and_google_member_points(monkeypatch):
    with TestClient(app) as shop, TestClient(app) as guest, TestClient(app) as stranger:
        csrf, bid, pid = merchant(shop, "paperless-owner@example.com")
        oid = create_paid(shop, csrf, bid, pid)
        share = same_origin(shop, "POST", f"/api/businesses/{bid}/paperless/{oid}/share",
                            {}, headers=csrf)
        assert share.status_code == 200, share.text
        qr = share.json()
        assert "/receipt#" in qr["url"] and qr["qr_png_base64"]
        assert qr["order_number"] == oid[:8].upper()
        token = qr["url"].split("#", 1)[1]
        assert guest.get("/api/wallet/me").json() == {
            "member": None, "receipts": [], "balances": []
        }
        claimed = same_origin(guest, "POST", "/api/wallet/claim", {"token": token})
        assert claimed.status_code == 200, claimed.text
        r = claimed.json()["receipt"]
        assert r["total_vnd"] == 70000
        assert r["items"][0]["quantity"] == 2
        assert r["document_type"] == "purchase_receipt"
        assert r["is_tax_invoice"] is False
        assert guest.get("/api/wallet/me").json()["receipts"][0]["order_id"] == oid
        assert guest.get("/api/wallet/me").json()["member"] is None
        assert same_origin(guest, "POST", "/api/wallet/claim",
                           {"token": token}).json()["already_saved"] is True
        assert same_origin(stranger, "POST", "/api/wallet/claim",
                           {"token": token}).status_code == 410
        assert stranger.get("/api/wallet/me").json()["receipts"] == []
        assert same_origin(shop, "POST", f"/api/businesses/{bid}/paperless/{oid}/share",
                           {}, csrf).status_code == 409
        assert same_origin(guest, "POST", "/api/wallet/claim",
                           {"token": "bogus" * 12}).status_code == 404

        monkeypatch.setenv("EZ_GOOGLE_CLIENT_ID", "test-google-client")
        from google.oauth2 import id_token
        def verified(credential, request, audience):
            assert audience == "test-google-client"
            assert credential == "VALID" * 12
            return {"sub": "google-stable-sub-1", "email": "guest@gmail.com",
                    "email_verified": True}
        monkeypatch.setattr(id_token, "verify_oauth2_token", verified)
        sign = same_origin(guest, "POST", "/api/wallet/google",
                           {"credential": "VALID" * 12})
        assert sign.status_code == 200, sign.text
        assert sign.json()["member"]["profile_complete"] is False
        profile = same_origin(guest, "POST", "/api/wallet/profile", {
            "name": "Nguyen Member", "phone": "0912345678"
        })
        assert profile.status_code == 200, profile.text
        details = guest.get("/api/wallet/me").json()
        assert details["member"]["profile_complete"] is True
        assert details["balances"] == [{
            "business_id": bid, "business_name": "Paperless Coffee", "points": 7
        }]
        code = guest.get("/api/wallet/member-qr")
        assert code.status_code == 200 and code.headers["content-type"] == "image/png"
        assert len(code.content) > 100
        assert same_origin(guest, "POST", "/api/wallet/google",
                           {"credential": "VALID" * 12}).status_code == 200
        with SessionLocal() as db:
            credits = db.scalars(select(IndustryWorkItem).where(
                IndustryWorkItem.business_id == bid,
                IndustryWorkItem.kind == "loyalty",
                IndustryWorkItem.reference_id == oid)).all()
            assert len(credits) == 1 and credits[0].details["points"] == 7
        assert same_origin(guest, "POST", "/api/wallet/logout", {}).status_code == 200
        assert guest.get("/api/wallet/me").json()["member"] is None
        assert len(guest.get("/api/wallet/me").json()["receipts"]) == 1
        assert same_origin(guest, "POST", "/api/wallet/forget-device", {}).status_code == 200
        assert guest.get("/api/wallet/me").json()["receipts"] == []
        assert same_origin(guest, "POST", "/api/wallet/google",
                           {"credential": "VALID" * 12}).status_code == 200
        assert len(guest.get("/api/wallet/me").json()["receipts"]) == 1


def test_receipts_are_paid_only_scoped_and_settings_require_origin():
    with TestClient(app) as owner, TestClient(app) as other:
        csrf, bid, pid = merchant(owner, "paperless-first@example.com")
        csrf2, bid2, _ = merchant(other, "paperless-second@example.com")
        pending = create_paid(owner, csrf, bid, pid, paid=False)
        endpoint = f"/api/businesses/{bid}/paperless/{pending}/share"
        assert same_origin(owner, "POST", endpoint, {}, csrf).status_code == 409
        assert same_origin(other, "POST", endpoint, {}, csrf2).status_code == 404
        bad_origin = owner.post(endpoint, headers={
            **csrf, "Origin": "https://attacker.example"
        }, json={})
        assert bad_origin.status_code == 403
        assert owner.get(f"/api/businesses/{bid}/paperless/settings").json() == {
            "paperless_enabled": False, "loyalty_enabled": True,
            "spend_vnd_per_point": 10000,
        }
        policy = same_origin(owner, "PUT", f"/api/businesses/{bid}/paperless/settings", {
            "paperless_enabled": True, "loyalty_enabled": True,
            "spend_vnd_per_point": 20000
        }, csrf)
        assert policy.status_code == 200, policy.text
        assert owner.get(f"/api/businesses/{bid}/paperless/settings").json()["paperless_enabled"] is True
        assert other.get(f"/api/businesses/{bid}/paperless/members").status_code == 404
        page = owner.get("/wallet")
        assert page.status_code == 200 and "My Receipts" in page.text
        assert owner.get("/receipt").status_code == 200


def test_assets_and_single_ledger():
    static = Path(__file__).resolve().parents[1] / "app/static"
    shell = (static / "index.html").read_text()
    for path in ("merchant-paperless.js", "merchant-paperless.css"):
        assert path in shell
    wallet = (static / "receipt-wallet.js").read_text()
    assert "location.hash" in wallet and "history.replaceState" in wallet
    pos = (static / "merchant-register.js").read_text()
    assert "digital-receipt" in pos and "EZPaperlessPOS" in pos
    printing = (Path(__file__).resolve().parents[1] / "app/printing.py").read_text()
    assert 'policy.get("paperless_enabled", False)' in printing
