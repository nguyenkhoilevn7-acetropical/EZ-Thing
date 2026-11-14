"""Regression tests for per-account brute-force protection and bounded SQL queries."""
import os
import uuid
from datetime import timedelta
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Branch, Business, LoginFailure, SaleOrder, now


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def cli():
    with TestClient(app) as client:
        yield client


def owner(cli):
    email = "metric-owner@example.com"
    res = cli.post("/api/auth/signup", json={
        "name": "Metrics owner", "email": email, "password": "SafePassword!123"
    })
    assert res.status_code == 201
    csrf = res.json()["csrf_token"]
    response = cli.post("/api/businesses", headers={"x-csrf-token": csrf},
                        json={"name": "Audit test", "industry": "retail"})
    assert response.status_code == 201, response.text
    return response.json()["id"], csrf


def test_health_vs_database_readiness(cli):
    assert cli.get("/api/health").json()["ok"] is True
    assert cli.get("/api/ready").json() == {"ok": True, "database": "ready"}
    from app.database import db_session
    from sqlalchemy.exc import OperationalError

    class BrokenDB:
        def execute(self, statement):
            raise OperationalError("SELECT 1", {}, Exception("fake DB offline"))

    def bad_session():
        yield BrokenDB()

    app.dependency_overrides[db_session] = bad_session
    try:
        result = cli.get("/api/ready")
        assert result.status_code == 503
        assert result.json()["detail"] == "Database unavailable"
        assert "fake DB offline" not in result.text
    finally:
        app.dependency_overrides.clear()
    assert cli.get("/api/health").status_code == 200


def test_per_identity_login_lockout_persists_and_recovers(cli):
    user = {
        "name": "Login Owner", "email": "login-rate@example.com",
        "password": "SafePassword!123",
    }
    assert cli.post("/api/auth/signup", json=user).status_code == 201
    for i in range(8):
        res = cli.post("/api/auth/login", json={
            "email": user["email"], "password": "wrong-password"
        })
        assert res.status_code == 401, f"attempt {i + 1}: {res.text}"
    assert cli.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"]
    }).status_code == 429
    with SessionLocal() as db:
        record = db.scalar(select(LoginFailure))
        assert record and record.failures == 8
        record.locked_until = now() - timedelta(minutes=20)
        record.window_started_at = now() - timedelta(minutes=20)
        db.commit()
    assert cli.post("/api/auth/login", json={
        "email": user["email"], "password": user["password"]
    }).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(LoginFailure)) is None


def test_aggregate_dashboard_and_order_listing_are_bounded(cli):
    bid, csrf = owner(cli)
    with SessionLocal() as db:
        branch_id = db.scalar(select(Branch.id).where(Branch.business_id == bid))
        assert branch_id
        for index in range(250):
            status = "paid" if index % 3 == 0 else "open" if index % 3 == 1 else "cancelled"
            db.add(SaleOrder(
                id=str(uuid.uuid4()), business_id=bid,
                branch_id=branch_id,
                idempotency_key="bulk-metric-" + str(index),
                request_fingerprint="test", status=status,
                total_vnd=12345,
                paid_at=now() if status == "paid" else None
            ))
        db.commit()
    selects = []
    def observer(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith("select"):
            selects.append(statement.lower())
    event.listen(engine, "before_cursor_execute", observer)
    try:
        dashboard = cli.get(f"/api/businesses/{bid}/overview")
        assert dashboard.status_code == 200, dashboard.text
        result = dashboard.json()
        assert result["order_count"] == 250
        assert result["open_count"] == len([i for i in range(250) if i % 3 == 1])
        assert result["paid_revenue_vnd"] == 84 * 12345
        assert result["today_revenue_vnd"] == 84 * 12345
        assert len(selects) <= 12, f"Too many overview queries: {len(selects)}"
        selects.clear()
        orders = cli.get(f"/api/businesses/{bid}/orders")
        assert orders.status_code == 200
        assert len(orders.json()) == 100
        assert len(selects) <= 12, f"N+1 order line requests: {len(selects)}"
    finally:
        event.remove(engine, "before_cursor_execute", observer)
