"""Regression tests for the integrated host desk, floor zones and order dashboard."""
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Membership

ASSETS = Path(__file__).resolve().parents[1] / "app" / "static"


@pytest.fixture(autouse=True)
def clean():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def owner(cli, tag="a"):
    res = cli.post("/api/auth/signup", json={
        "name": "Owner " + tag, "email": tag + "@example.com",
        "password": "SafePassword!123"
    })
    assert res.status_code == 201, res.text
    return res.json()["csrf_token"]


def create_business(cli, csrf, name, plan="PRO"):
    res = cli.post("/api/businesses", headers={"x-csrf-token": csrf}, json={
        "name": name, "industry": "fnb", "selected_plan": plan,
        "need_tables": True, "need_inventory": True,
        "need_insights": True, "need_branches": plan == "PRO",
    })
    assert res.status_code == 201, res.text
    return res.json()["id"]


def write(cli, method, path, csrf, payload):
    return cli.request(method, "/api" + path,
                       headers={"x-csrf-token": csrf}, json=payload)


def test_floorplan_default_and_save_per_branch():
    with TestClient(app) as cli:
        token = owner(cli)
        bid = create_business(cli, token, "Cafe One")
        branches = cli.get(f"/api/businesses/{bid}/branches").json()
        first_branch = branches[0]["id"]
        other = write(cli, "POST", f"/businesses/{bid}/branches", token,
                      {"name": "Branch Two"})
        assert other.status_code == 201, other.text
        second_branch = other.json()["id"]
        first = write(cli, "POST", f"/businesses/{bid}/tables", token,
                      {"label": "Bàn 01", "seats": 4, "branch_id": first_branch})
        second = write(cli, "POST", f"/businesses/{bid}/tables", token,
                       {"label": "VIP 02", "seats": 6, "branch_id": second_branch})
        assert first.status_code == second.status_code == 201
        path = f"/businesses/{bid}/floorplan"
        current = cli.get("/api" + path, params={"branch_id": first_branch})
        assert current.status_code == 200, current.text
        data = current.json()
        assert data["revision"] == 0 and data["editable"] is True
        assert {zone["id"] for zone in data["zones"]} == {"inside", "outdoor", "vip"}
        assert [t["id"] for t in data["tables"]] == [first.json()["id"]]
        new_zones = data["zones"] + [{"id": "roof", "name": "Sân thượng"}]
        payload = {"branch_id": first_branch, "revision": 0,
                   "zones": new_zones,
                   "placements": [{"table_id": first.json()["id"],
                                   "zone_id": "roof", "x": 44, "y": 52,
                                   "shape": "rectangle"}]}
        saved = write(cli, "PUT", path, token, payload)
        assert saved.status_code == 200, saved.text
        assert saved.json()["revision"] == 1
        assert saved.json()["tables"][0]["placement"]["zone_id"] == "roof"
        assert saved.json()["tables"][0]["placement"]["shape"] == "rectangle"
        assert write(cli, "PUT", path, token, payload).status_code == 409
        independent = cli.get("/api" + path, params={"branch_id": second_branch}).json()
        assert independent["revision"] == 0
        assert independent["tables"][0]["id"] == second.json()["id"]
        assert write(cli, "PUT", path, token, {**payload,
                 "placements": [{**payload["placements"][0], "table_id": second.json()["id"]}],
                 "revision": 1}).status_code == 422
        assert write(cli, "PUT", path, token,
                     {**payload, "revision": 1,
                      "placements": [{**payload["placements"][0], "x": 155}]}).status_code == 422


def test_floorplan_tenant_isolation_and_owner_edit_permission():
    with TestClient(app) as one, TestClient(app) as two:
        token = owner(one, "owner1")
        bid = create_business(one, token, "Restaurant One", "PLUS")
        token2 = owner(two, "owner2")
        other_bid = create_business(two, token2, "Restaurant Two", "PLUS")
        assert two.get(f"/api/businesses/{bid}/floorplan").status_code == 404
        assert one.get(f"/api/businesses/{other_bid}/floorplan").status_code == 404
        cfg = one.get(f"/api/businesses/{bid}/floorplan").json()
        with SessionLocal() as db:
            member = db.scalar(select(Membership).where(Membership.business_id == bid))
            member.role = "staff"
            db.commit()
        read = one.get(f"/api/businesses/{bid}/floorplan")
        assert read.status_code == 200 and read.json()["editable"] is False
        response = write(one, "PUT", f"/businesses/{bid}/floorplan", token, {
            "branch_id": cfg["branch_id"], "revision": cfg["revision"],
            "zones": cfg["zones"], "placements": [],
        })
        assert response.status_code == 403


def test_order_dashboard_counts_money_from_existing_orders():
    with TestClient(app) as cli:
        token = owner(cli, "orders")
        bid = create_business(cli, token, "Cafe Orders", "PLUS")
        product = write(cli, "POST", f"/businesses/{bid}/products", token, {
            "name": "Cà phê", "sku": "COFFEE-1", "price_vnd": 25000,
            "stock": 50, "track_stock": False
        })
        assert product.status_code == 201, product.text
        for n in range(2):
            res = write(cli, "POST", f"/businesses/{bid}/orders", token, {
                "idempotency_key": "suite-test-%d" % n,
                "lines": [{"product_id": product.json()["id"], "quantity": n+1}],
            })
            assert res.status_code == 201, res.text
            if n == 0:
                paid = write(cli, "POST",
                             f"/businesses/{bid}/orders/{res.json()['id']}/paid",
                             token, {"confirmed": True})
                assert paid.status_code == 200, paid.text
        path = f"/api/businesses/{bid}/order-dashboard"
        data = cli.get(path).json()
        assert data["total_count"] == 2 and data["open_count"] == 1
        assert data["paid_count"] == 1 and data["paid_vnd"] == 25000
        assert len(data["orders"]) == 2
        only_open = cli.get(path, params={"status": "open"}).json()
        assert only_open["total_count"] == 1 and only_open["paid_vnd"] == 0
        assert cli.get(path, params={"from_day": "2020-01-01",
                                     "to_day": "2020-02-01"}).json()["total_count"] == 0
        assert cli.get(path, params={"from_day": "2026-11-15",
                                     "to_day": "2026-11-14"}).status_code == 422
        assert cli.get(path, params={"branch_id": "not-other-business"}).status_code == 404


def test_booking_is_integrated_into_existing_app_shell():
    with TestClient(app) as cli:
        legacy = cli.get("/app/reservations", follow_redirects=False)
        assert legacy.status_code == 307
        assert legacy.headers["location"] == "/app?tab=reservations"
        markup = cli.get("/app?tab=reservations").text
        assert "/assets/app.js" in markup
        assert "/assets/merchant-restaurant-suite.js" in markup
        assert "/assets/merchant-restaurant-suite.css" in markup
        assert "reservation-nav" not in markup
        assert cli.get("/assets/merchant-restaurant-suite.js").status_code == 200


def test_floor_map_and_order_controls_are_present_in_source():
    appjs = (ASSETS / "app.js").read_text(encoding="utf-8")
    code = (ASSETS / "merchant-restaurant-suite.js").read_text(encoding="utf-8")
    assert "window.location.assign('/app/reservations')" not in appjs
    assert "reservations:()=>restaurantSuite?.renderReservations()" in appjs
    assert "order-dashboard?" in appjs
    assert "data-order-filter" in appjs and "order-details" not in appjs
    for feature in ("zone", "save-layout", "new-zone", "rename-zone",
                    "delete-zone", "table-placement", "new-booking", "booking-status",
                    "inquiry-status", "enableDragging", "aria-roledescription"):
        assert feature in code
    assert "merchant-brand-dot" in appjs
