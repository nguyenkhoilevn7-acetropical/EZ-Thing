"""Workstation assignment is tenant-scoped; display preferences are never RBAC."""
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def db_reset(monkeypatch):
    monkeypatch.delenv("EZ_THING_TRIAL_ENABLED", raising=False)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def create_shop(client, suffix, industry="fnb"):
    response = client.post("/api/auth/signup", json={
        "name": "Test Workstation Owner",
        "email": f"device-{suffix}@example.com",
        "password": "SafePassword!123",
    })
    assert response.status_code == 201, response.text
    csrf = {"x-csrf-token": response.json()["csrf_token"]}
    response = client.post("/api/businesses", headers=csrf, json={
        "name": "Restaurant " + suffix, "industry": industry,
        "need_tables": True, "need_inventory": True, "selected_plan": "PRO",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"], csrf


def test_register_repeat_then_manager_assigns_kitchen_and_bar():
    with TestClient(app) as client:
        bid, csrf = create_shop(client, "owner")
        base = f"/api/businesses/{bid}/workstations"
        key = str(uuid4())
        res = client.put(base + "/current", headers=csrf, json={
            "client_key": key, "name": "Tablet bếp"
        })
        assert res.status_code == 200, res.text
        original = res.json()
        assert original["mode"] == "manager"
        again = client.put(base + "/current", headers=csrf, json={
            "client_key": key, "name": "Repeated"
        })
        assert again.status_code == 200
        assert again.json()["id"] == original["id"]
        assert again.json()["name"] == "Tablet bếp"
        assert len(client.get(base).json()["workstations"]) == 1
        changed = client.patch(base + "/" + original["id"], headers=csrf,
                               json={"mode": "kitchen"})
        assert changed.status_code == 200, changed.text
        assert changed.json()["station"] == "kitchen"
        assert client.patch(base + "/" + original["id"], headers=csrf,
                            json={"mode": "bar", "station": "bar"}).json()["mode"] == "bar"
        assert client.put(base + "/current", headers=csrf, json={
            "client_key": key, "name": "Cannot overwrite assignment"
        }).json()["mode"] == "bar"


def test_cross_tenant_device_access_denied_and_branch_must_match():
    with TestClient(app) as owner, TestClient(app) as outsider:
        bid, csrf = create_shop(owner, "one")
        other_bid, other_csrf = create_shop(outsider, "two")
        key = str(uuid4())
        base = f"/api/businesses/{bid}/workstations"
        row = owner.put(base + "/current", headers=csrf,
                        json={"client_key": key, "name": "POS terminal"}).json()
        assert outsider.get(base).status_code == 404
        assert outsider.patch(base + "/" + row["id"], headers=other_csrf,
                             json={"mode": "manager"}).status_code == 404
        assert owner.patch(base + "/" + row["id"], headers=csrf,
                           json={"branch_id": "invalid-foreign-branch"}).status_code == 422
        foreign_branch = outsider.get(f"/api/businesses/{other_bid}/branches").json()[0]["id"]
        assert owner.patch(base + "/" + row["id"], headers=csrf,
                           json={"branch_id": foreign_branch}).status_code == 422
        assert owner.patch(base + "/" + str(uuid4()), headers=csrf,
                           json={"mode": "bar"}).status_code == 404
        assert owner.patch(base + "/" + row["id"], json={"mode": "bar"}).status_code == 403


def test_non_fnb_workstations_are_disabled():
    with TestClient(app) as client:
        bid, csrf = create_shop(client, "retail", industry="retail")
        response = client.put(f"/api/businesses/{bid}/workstations/current",
                              headers=csrf, json={
                                  "client_key": str(uuid4()), "name": "POS retail"})
        assert response.status_code == 404


def test_frontend_loads_focus_shell_and_keeps_api_permissions_explicit():
    static = Path(__file__).resolve().parents[1] / "app" / "static"
    html = (static / "index.html").read_text()
    app_js = (static / "app.js").read_text()
    profile = (static / "workstation-ui.js").read_text()
    css = (static / "workstation-ui.css").read_text()
    kds = (static / "merchant-kds.js").read_text()
    assert "workstation-ui.css" in html and "workstation-ui.js" in html
    assert html.index("workstation-ui.js") < html.index("app.js")
    assert "await workstationUI?.load()" in app_js
    assert "workstationUI?.drawer(nav)" in app_js
    assert 'body[data-ez-workstation-active="true"] .app>.sidebar' in css
    assert 'body[data-ez-workstation-active="true"] .ezreg-layout' in css
    assert "display mode is not an authorization boundary" in profile
    assert '"PATCH"' in profile
    assert 'key==="kitchen"&&["hot","cold"].includes(item.station)' in kds
    assert "includesStation(item,station)" in kds
