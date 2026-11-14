"""End-to-end RBAC, invitation and signup throttling contract tests."""
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def signup(cli, email):
    r = cli.post("/api/auth/signup", json={
        "name": "Team User", "email": email,
        "password": "SafePassword!123",
    })
    assert r.status_code == 201, r.text
    return r.json()["csrf_token"]


def post(cli, path, payload, csrf):
    return cli.post("/api" + path, json=payload, headers={"x-csrf-token": csrf})


def setup_business(cli, csrf):
    result = post(cli, "/businesses", {
        "name": "Real Shop", "industry": "retail", "selected_plan": "PRO",
        "need_inventory": True, "need_insights": True, "need_branches": True,
    }, csrf)
    assert result.status_code == 201, result.text
    return result.json()["id"]


def test_staff_invite_email_binds_token_and_prevents_escalation():
    with TestClient(app) as owner, TestClient(app) as invited, TestClient(app) as outsider:
        owner_csrf = signup(owner, "shop-owner@example.com")
        bid = setup_business(owner, owner_csrf)
        p = post(owner, f"/businesses/{bid}/products", {
            "name": "Tablet", "sku": "TAB-01", "price_vnd": 150000,
            "cost_vnd": 100000, "stock": 12
        }, owner_csrf)
        assert p.status_code == 201, p.text
        invite = post(owner, f"/businesses/{bid}/team/invitations", {
            "email": "worker@example.com", "role": "staff"
        }, owner_csrf)
        assert invite.status_code == 201, invite.text
        url = invite.json()["invite_url"]
        assert url.startswith("/app?invite=")
        token = url.split("=", 1)[1]
        assert token not in str(owner.get(f"/api/businesses/{bid}/team").json())

        outsider_csrf = signup(outsider, "outsider@example.com")
        wrong = post(outsider, "/team/accept", {"token": token}, outsider_csrf)
        assert wrong.status_code == 403
        worker_csrf = signup(invited, "worker@example.com")
        assert invited.get(f"/api/businesses/{bid}/products").status_code == 404
        ok = post(invited, "/team/accept", {"token": token}, worker_csrf)
        assert ok.status_code == 200, ok.text
        assert post(invited, "/team/accept", {"token": token}, worker_csrf).status_code == 404
        assert invited.get("/api/businesses").json()[0]["role"] == "staff"
        items = invited.get(f"/api/businesses/{bid}/products").json()
        assert items[0]["cost_vnd"] is None
        assert post(invited, f"/businesses/{bid}/products", {
            "name": "Hacked", "sku": "HACK", "price_vnd": 1,
        }, worker_csrf).status_code == 403
        assert post(invited, f"/businesses/{bid}/products/{p.json()['id']}/stock", {
            "delta": 10, "reason": "fake adjustment"
        }, worker_csrf).status_code == 403
        assert invited.get(f"/api/businesses/{bid}/insights").status_code == 403
        assert invited.get(f"/api/businesses/{bid}/receivables").status_code == 403
        assert invited.get(f"/api/businesses/{bid}/team").status_code == 403
        order = post(invited, f"/businesses/{bid}/orders", {
            "idempotency_key": "staff-demo-order-00001",
            "lines": [{"product_id": p.json()["id"], "quantity": 1}],
        }, worker_csrf)
        assert order.status_code == 201, order.text
        paid = post(invited, f"/businesses/{bid}/orders/{order.json()['id']}/paid",
                    {"confirmed": True}, worker_csrf)
        assert paid.status_code == 403
        assert invited.get(f"/api/businesses/{bid}/overview").json()["paid_revenue_vnd"] is None

        member_uid = invited.get("/api/auth/me").json()["id"]
        upd = owner.patch(f"/api/businesses/{bid}/team/members/{member_uid}",
            headers={"x-csrf-token": owner_csrf}, json={"role": "manager"})
        assert upd.status_code == 200, upd.text
        assert post(invited, f"/businesses/{bid}/orders/{order.json()['id']}/paid",
            {"confirmed": True}, worker_csrf).status_code == 200
        assert invited.get(f"/api/businesses/{bid}/insights").status_code == 200
        delete = owner.delete(f"/api/businesses/{bid}/team/members/{member_uid}",
            headers={"x-csrf-token": owner_csrf})
        assert delete.status_code == 200
        assert invited.get(f"/api/businesses/{bid}/products").status_code == 404
        owner_id = owner.get("/api/auth/me").json()["id"]
        assert owner.delete(f"/api/businesses/{bid}/team/members/{owner_id}",
            headers={"x-csrf-token": owner_csrf}).status_code == 403


def test_invite_revoke_and_cannot_self_join_other_tenant():
    with TestClient(app) as owner, TestClient(app) as staff:
        a = signup(owner, "business-owner@example.com")
        bid = setup_business(owner, a)
        r = post(owner, f"/businesses/{bid}/team/invitations", {
            "email": "invited@example.com", "role": "manager"
        }, a)
        iid = r.json()["id"]
        token = r.json()["invite_url"].split("=")[1]
        assert post(owner, f"/businesses/{bid}/team/invitations/{iid}/revoke",
                    {}, a).status_code == 200
        s = signup(staff, "invited@example.com")
        assert post(staff, "/team/accept", {"token": token}, s).status_code == 404


def test_signup_throttles_identity_even_with_no_existing_account():
    with TestClient(app) as client:
        payload = {"name": "New User", "email": "spam@example.com",
                   "password": "SafePassword!123"}
        assert client.post("/api/auth/signup", json=payload).status_code == 201
        for _ in range(7):
            assert client.post("/api/auth/signup", json=payload).status_code == 409
        assert client.post("/api/auth/signup", json=payload).status_code == 429
