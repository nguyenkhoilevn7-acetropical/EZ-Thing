"""Cross-vertical safety tests for cancel, stock ledger and payment races."""
import os
from pathlib import Path
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Membership, StockMovement


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def owner(cli, tag="owner"):
    r = cli.post("/api/auth/signup", json={
        "name": "Owner Test", "email": tag + "@example.com", "password": "SafePassword!123",
    })
    assert r.status_code == 201, r.text
    return r.json()["csrf_token"]


def write(cli, csrf, url, payload):
    return cli.post("/api" + url, json=payload, headers={"x-csrf-token": csrf})


def create_business(cli, csrf, industry):
    r = write(cli, csrf, "/businesses", {
        "name": "Audit " + industry, "industry": industry, "selected_plan": "PLUS",
        "need_tables": True, "need_inventory": True, "need_insights": True,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def create_product(cli, csrf, bid, sku="AUDIT", tracked=True):
    r = write(cli, csrf, f"/businesses/{bid}/products", {
        "name": "Audit item", "sku": sku, "price_vnd": 20000,
        "stock": 10 if tracked else 0, "track_stock": tracked,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def order(cli, csrf, bid, pid, key="audit-order-01"):
    r = write(cli, csrf, f"/businesses/{bid}/orders", {
        "idempotency_key": key, "lines": [{"product_id": pid, "quantity": 3}],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def cancel(cli, csrf, bid, oid, reason="Khách muốn hủy"):
    return write(cli, csrf, f"/businesses/{bid}/orders/{oid}/cancel", {
        "confirmed": True, "reason": reason,
    })


@pytest.mark.parametrize("industry", ["fnb", "retail", "online", "services"])
def test_each_vertical_cancel_restores_stock_once_and_updates_dashboard(industry):
    with TestClient(app) as cli:
        csrf = owner(cli)
        bid = create_business(cli, csrf, industry)
        pid = create_product(cli, csrf, bid)
        oid = order(cli, csrf, bid, pid)
        assert cli.get(f"/api/businesses/{bid}/products").json()[0]["stock"] == 7

        first = cancel(cli, csrf, bid, oid)
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "cancelled"
        retry = cancel(cli, csrf, bid, oid)
        assert retry.status_code == 200
        assert retry.json()["status"] == "cancelled"
        assert cli.get(f"/api/businesses/{bid}/products").json()[0]["stock"] == 10

        dashboard = cli.get(f"/api/businesses/{bid}/order-dashboard").json()
        assert dashboard["cancelled_count"] == 1
        assert dashboard["open_count"] == dashboard["paid_count"] == 0
        assert dashboard["paid_vnd"] == 0
        filtered = cli.get(f"/api/businesses/{bid}/order-dashboard",
                           params={"status": "cancelled"}).json()
        assert filtered["total_count"] == 1
        assert filtered["orders"][0]["id"] == oid
        assert write(cli, csrf, f"/businesses/{bid}/orders/{oid}/paid",
                     {"confirmed": True}).status_code == 409

        with SessionLocal() as db:
            moves = db.scalars(select(StockMovement).where(
                StockMovement.business_id == bid, StockMovement.ref == oid
            )).all()
            assert [(m.reason, m.delta) for m in moves] == [
                ("sale", -3), ("order_cancelled", 3)
            ]


def test_paid_order_cannot_be_cancelled_or_restocked():
    with TestClient(app) as cli:
        csrf = owner(cli)
        bid = create_business(cli, csrf, "retail")
        pid = create_product(cli, csrf, bid)
        oid = order(cli, csrf, bid, pid)
        assert write(cli, csrf, f"/businesses/{bid}/orders/{oid}/paid",
                     {"confirmed": True}).status_code == 200
        rejected = cancel(cli, csrf, bid, oid)
        assert rejected.status_code == 409
        assert cli.get(f"/api/businesses/{bid}/products").json()[0]["stock"] == 7


def test_kitchen_pending_cancelled_and_in_progress_blocked():
    with TestClient(app) as cli:
        csrf = owner(cli)
        bid = create_business(cli, csrf, "fnb")
        pid = create_product(cli, csrf, bid)
        oid = order(cli, csrf, bid, pid)
        ticket = write(cli, csrf, f"/businesses/{bid}/industry/kitchen", {
            "order_id": oid,
        })
        assert ticket.status_code == 201, ticket.text
        assert cancel(cli, csrf, bid, oid).status_code == 200
        assert cli.get(f"/api/businesses/{bid}/industry/kitchen").json()[0]["status"] == "cancelled"
        assert write(cli, csrf, f"/businesses/{bid}/industry/kitchen", {
            "order_id": oid,
        }).status_code == 409
        assert write(cli, csrf, f"/businesses/{bid}/industry/kitchen/{ticket.json()['id']}/status", {
            "status": "preparing"
        }).status_code == 409

        other = order(cli, csrf, bid, pid, key="audit-order-02")
        work = write(cli, csrf, f"/businesses/{bid}/industry/kitchen", {
            "order_id": other,
        }).json()
        assert write(cli, csrf, f"/businesses/{bid}/industry/kitchen/{work['id']}/status", {
            "status": "preparing"
        }).status_code == 200
        assert cancel(cli, csrf, bid, other).status_code == 409
        assert cli.get(f"/api/businesses/{bid}/products").json()[0]["stock"] == 7


def test_nonstock_service_cancellation_and_staff_permissions():
    with TestClient(app) as cli:
        csrf = owner(cli)
        bid = create_business(cli, csrf, "services")
        pid = create_product(cli, csrf, bid, tracked=False)
        oid = order(cli, csrf, bid, pid)
        with SessionLocal() as db:
            member = db.scalar(select(Membership).where(Membership.business_id == bid))
            member.role = "staff"
            db.commit()
        assert cancel(cli, csrf, bid, oid).status_code == 403
        with SessionLocal() as db:
            member = db.scalar(select(Membership).where(Membership.business_id == bid))
            member.role = "owner"
            db.commit()
        assert cancel(cli, csrf, bid, oid).status_code == 200
        assert cli.get(f"/api/businesses/{bid}/products").json()[0]["stock"] == 0
        with SessionLocal() as db:
            assert db.scalars(select(StockMovement).where(
                StockMovement.business_id == bid, StockMovement.ref == oid
            )).all() == []
