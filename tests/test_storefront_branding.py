"""Tenant storefront customization: isolation, plans, and real editor contracts."""
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(__file__).parent / "pilot-tests.db")

from app.database import Base, engine, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Business, Membership, AuditEvent  # noqa: E402
from app.storefront_brand import TIER_FIELDS, effective_brand  # noqa: E402


@pytest.fixture(autouse=True)
def reset():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def register(cli, name):
    r = cli.post("/api/auth/signup", json={
        "name": name, "email": name + "@example.com", "password": "SafePassword!123",
    })
    assert r.status_code == 201, r.text
    return r.json()["csrf_token"]


def create(cli, csrf, name, plan):
    r = cli.post("/api/businesses", json={
        "name": name, "industry": "fnb", "selected_plan": plan,
        "need_tables": True, "need_inventory": True,
        "need_insights": plan != "BASIC", "need_branches": plan == "PRO",
    }, headers={"x-csrf-token": csrf})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def patch(cli, bid, csrf, payload):
    return cli.patch("/api/businesses/" + bid + "/storefront",
                     json=payload, headers={"x-csrf-token": csrf})


def test_plan_descriptions_and_private_preview_url():
    with TestClient(app) as cli:
        csrf = register(cli, "restaurant")
        bid = create(cli, csrf, "The Garden Cafe", "BASIC")
        meta = cli.get("/api/storefront/plans")
        assert meta.status_code == 200
        assert meta.json()["plans"]["BASIC"]["price_vnd"] == 249000
        assert meta.json()["plans"]["PRO"]["branches"] == 10
        cfg = cli.get(f"/api/businesses/{bid}/storefront")
        assert cfg.status_code == 200
        assert cfg.json()["branding"]["display_name"] == "The Garden Cafe"
        assert cfg.json()["preview_url"] == f"/preview/site/{bid}"
        assert cfg.json()["published"] is False
        assert set(cfg.json()["editable_fields"]) == TIER_FIELDS["BASIC"]
        assert cli.get(f"/preview/site/{bid}").status_code == 200
        assert cli.get("/app/storefront-design").status_code == 200


def test_basic_edits_are_isolated_and_locked_fields_denied():
    with TestClient(app) as one, TestClient(app) as two:
        token1 = register(one, "ownerone")
        first = create(one, token1, "Cafe One", "BASIC")
        token2 = register(two, "ownertwo")
        second = create(two, token2, "Cafe Two", "BASIC")
        success = patch(one, first, token1, {
            "display_name": "Cafe Renamed", "phone": "0901111222",
            "description": "Craft coffee", "banner_preset": "coffee",
        })
        assert success.status_code == 200, success.text
        assert success.json()["branding"]["display_name"] == "Cafe Renamed"
        assert success.json()["branding"]["banner_preset"] == "coffee"
        assert patch(one, first, token1, {"hero_title": "VIP"}).status_code == 403
        assert patch(one, first, token1, {"layout_style": "gallery"}).status_code == 403
        assert one.get(f"/api/businesses/{second}/storefront").status_code == 404
        assert two.get(f"/api/businesses/{first}/storefront").status_code == 404
        assert two.get(f"/preview/site/{first}").status_code == 404
        assert one.get(f"/api/businesses/{first}/storefront-preview").status_code == 200
        with SessionLocal() as db:
            records = db.scalars(select(AuditEvent).where(
                AuditEvent.business_id == first, AuditEvent.action == "storefront.updated"
            )).all()
            assert len(records) == 1


def test_plus_custom_branding_pro_layout_and_plan_downgrade():
    with TestClient(app) as cli:
        csrf = register(cli, "ownerplus")
        bid = create(cli, csrf, "Cafe Plus", "PLUS")
        photo = "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=1600"
        r = patch(cli, bid, csrf, {
            "hero_title": "Welcome to our cafe", "banner_url": photo,
            "logo_url": photo, "accent_color": "#BF506C",
        })
        assert r.status_code == 200, r.text
        assert r.json()["branding"]["banner_image"] == photo
        assert r.json()["branding"]["hero_title"] == "Welcome to our cafe"
        assert patch(cli, bid, csrf, {"footer_note": "See you soon"}).status_code == 403
        assert patch(cli, bid, csrf, {"banner_url": "https://evil.example/track.png"}).status_code == 422
        with SessionLocal() as db:
            b = db.get(Business, bid)
            b.plan = "PRO"
            db.commit()
        p = patch(cli, bid, csrf, {"layout_style": "gallery", "footer_note": "Thanks!"})
        assert p.status_code == 200
        assert p.json()["branding"]["layout_style"] == "gallery"
        with SessionLocal() as db:
            b = db.get(Business, bid)
            b.plan = "BASIC"
            db.commit()
            effective = effective_brand(b)
            assert effective["banner_url"] == ""
            assert effective["accent_color"] == "#147D64"
            assert effective["layout_style"] == "classic"
            assert effective["footer_note"] == ""


def test_non_owner_cannot_change_other_members_storefront():
    with TestClient(app) as cli:
        owner_token = register(cli, "ownerrole")
        bid = create(cli, owner_token, "Cafe", "PLUS")
        with SessionLocal() as db:
            member = db.scalar(select(Membership).where(Membership.business_id == bid))
            member.role = "staff"
            db.commit()
        assert cli.get(f"/api/businesses/{bid}/storefront").status_code == 200
        assert patch(cli, bid, owner_token, {"display_name": "Hacked"}).status_code == 403
