"""EZ Print: tenant security, KDS/paid events, CloudPRNT, LAN/USB connectors."""
import base64
import os
import sys
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
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def c():
    with TestClient(app) as client:
        yield client


def api(c, method, path, payload=None, csrf=None, auth=None):
    headers = {}
    if csrf:
        headers["x-csrf-token"] = csrf
    if auth:
        headers["authorization"] = auth
    return c.request(method, "/api" + path, json=payload, headers=headers)


def owner(c, email):
    r = api(c, "POST", "/auth/signup",
            {"name": "Printer Owner", "email": email, "password": "SafePassword!123"})
    assert r.status_code == 201, r.text
    csrf = r.json()["csrf_token"]
    b = api(c, "POST", "/businesses", {
        "name": "Printer Cafe", "industry": "fnb", "selected_plan": "PRO",
        "need_tables": True, "need_inventory": True, "need_insights": True,
        "need_branches": True}, csrf)
    assert b.status_code == 201, b.text
    bid = b.json()["id"]
    branches = api(c, "GET", f"/businesses/{bid}/branches")
    assert branches.status_code == 200, branches.text
    return bid, branches.json()[0]["id"], csrf


def register(c, bid, branch, csrf, protocol, station):
    r = api(c, "POST", f"/businesses/{bid}/printers", {
        "name": protocol + "-" + station,
        "branch_id": branch, "protocol": protocol, "station": station,
        "auto_print": True}, csrf)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["device_token_once"] and len(d["device_token_once"]) >= 32
    return d


def basic(device):
    credential = device["id"] + ":" + device["device_token_once"]
    return "Basic " + base64.b64encode(credential.encode()).decode()


def bearer(device):
    return "Bearer " + device["device_token_once"]


def order(c, bid, csrf):
    product = api(c, "POST", f"/businesses/{bid}/products", {
        "name": "Trà sữa", "sku": "TEA-" + uuid.uuid4().hex[:6],
        "category": "Đồ uống", "price_vnd": 35000,
        "track_stock": False}, csrf)
    assert product.status_code == 201, product.text
    r = api(c, "POST", f"/businesses/{bid}/orders", {
        "idempotency_key": uuid.uuid4().hex,
        "lines": [{"product_id": product.json()["id"], "quantity": 2}],
        "note": "Ít đá"}, csrf)
    assert r.status_code == 201, r.text
    return r.json()


def test_cloudprnt_and_connector_print_once_with_manual_payment(c):
    bid, br, csrf = owner(c, "dual-print-1@example.com")
    cloud = register(c, bid, br, csrf, "cloudprnt", "bar")
    local = register(c, bid, br, csrf, "connector_lan", "receipt")

    # Public/list APIs never return the one-time device secret.
    listed = api(c, "GET", f"/businesses/{bid}/printers")
    assert listed.status_code == 200
    assert "device_token_once" not in listed.text and "token_hash" not in listed.text

    o = order(c, bid, csrf)
    fired = api(c, "POST", f"/businesses/{bid}/kds/fire", {
        "order_id": o["id"]}, csrf)
    assert fired.status_code == 201, fired.text
    assert api(c, "POST", f"/businesses/{bid}/kds/fire", {
        "order_id": o["id"]}, csrf).status_code == 201

    jobs = api(c, "GET", f"/businesses/{bid}/printers/jobs").json()["jobs"]
    assert len(jobs) == 1 and jobs[0]["device_id"] == cloud["id"]

    cloud_path = f"/print/cloudprnt/{cloud['id']}"
    assert api(c, "POST", cloud_path, {}, auth="Basic bad").status_code == 401
    poll = api(c, "POST", cloud_path, {"statusCode": "200 OK"}, auth=basic(cloud))
    assert poll.status_code == 200, poll.text
    assert poll.json()["jobReady"] and poll.json()["mediaTypes"] == ["text/plain"]
    token = poll.json()["jobToken"]
    repeat_poll = api(c, "POST", cloud_path, {}, auth=basic(cloud))
    assert repeat_poll.json()["jobReady"] is False
    download = c.get("/api" + cloud_path + "?type=text/plain&token=" + token,
                     headers={"authorization": basic(cloud)})
    assert download.status_code == 200, download.text
    assert "Trà sữa" in download.text and "Ít đá" in download.text
    assert "70,000 VND" not in download.text  # Kitchen ticket, not receipt.
    assert c.delete("/api" + cloud_path + "?code=OK&token=" + token,
                    headers={"authorization": basic(cloud)}).status_code == 200
    assert c.delete("/api" + cloud_path + "?code=OK&token=" + token,
                    headers={"authorization": basic(cloud)}).status_code == 200

    paid = api(c, "POST", f"/businesses/{bid}/orders/{o['id']}/paid", {"confirmed": True}, csrf)
    assert paid.status_code == 200, paid.text
    assert api(c, "POST", f"/businesses/{bid}/orders/{o['id']}/paid",
               {"confirmed": True}, csrf).status_code == 200
    path = f"/print/connector/{local['id']}"
    missing = api(c, "GET", path + "/next")
    assert missing.status_code == 401
    next_job = api(c, "GET", path + "/next", auth=bearer(local))
    assert next_job.status_code == 200 and next_job.json()["job"]
    job = next_job.json()["job"]
    assert "70,000 VND" in job["content"]
    assert api(c, "GET", path + "/next", auth=bearer(local)).json()["job"] is None
    done = api(c, "POST", path + "/ack",
               {"job_id": job["id"], "success": True}, auth=bearer(local))
    assert done.status_code == 200 and done.json()["status"] == "printed"
    assert api(c, "GET", f"/businesses/{bid}/printers/jobs").json()["jobs"].__len__() == 2


def test_usb_failure_requires_manager_retry_and_credentials_can_rotate(c):
    bid, br, csrf = owner(c, "dual-print-2@example.com")
    usb = register(c, bid, br, csrf, "connector_usb", "receipt")
    created = api(c, "POST", f"/businesses/{bid}/printers/{usb['id']}/test",
                  {}, csrf)
    assert created.status_code == 201
    path = f"/print/connector/{usb['id']}"
    fetched = api(c, "GET", path + "/next", auth=bearer(usb)).json()["job"]
    assert fetched
    failed = api(c, "POST", path + "/ack", {
        "job_id": fetched["id"], "success": False, "error": "No paper"}, auth=bearer(usb))
    assert failed.status_code == 200 and failed.json()["status"] == "failed"
    assert api(c, "GET", path + "/next", auth=bearer(usb)).json()["job"] is None
    retry = api(c, "POST", f"/businesses/{bid}/printers/jobs/{fetched['id']}/retry",
                {}, csrf)
    assert retry.status_code == 200 and retry.json()["status"] == "queued"
    assert api(c, "GET", path + "/next", auth=bearer(usb)).json()["job"]["id"] == fetched["id"]
    rotated = api(c, "POST", f"/businesses/{bid}/printers/{usb['id']}/rotate-key",
                  {}, csrf)
    assert rotated.status_code == 200
    assert api(c, "GET", path + "/next", auth=bearer(usb)).status_code == 401
    fresh_secret = rotated.json()["device_token_once"]
    assert api(c, "GET", path + "/next", auth="Bearer " + fresh_secret).status_code == 200


def test_tenant_and_branch_isolation(c):
    bid, branch, csrf = owner(c, "dual-print-3@example.com")
    device = register(c, bid, branch, csrf, "cloudprnt", "hot")
    # Cannot register foreign branch, even while owner of first business.
    wrong = api(c, "POST", f"/businesses/{bid}/printers", {
        "name": "Foreign branch", "branch_id": str(uuid.uuid4()),
        "protocol": "cloudprnt", "station": "bar"}, csrf)
    assert wrong.status_code == 404
    # A second session has no access to the first tenant's printers.
    other = TestClient(app)
    try:
        bid2, branch2, csrf2 = owner(other, "dual-print-4@example.com")
        assert api(other, "GET", f"/businesses/{bid}/printers").status_code == 404
        assert api(other, "POST", f"/businesses/{bid}/printers/{device['id']}/test",
                   {}, csrf2).status_code == 404
    finally:
        other.close()
