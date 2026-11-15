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
        assert cli.get(f"/preview/site/{bid}").status_code == 403
        assert cli.get(f"/api/businesses/{bid}/storefront-preview").status_code == 403


def test_demo_customer_frontend_uses_its_own_saved_brand(monkeypatch):
    monkeypatch.setenv("EZ_THING_ENVIRONMENT", "staging")
    monkeypatch.setenv("EZ_THING_DEMO_MODE", "1")
    with TestClient(app) as cli:
        guest = cli.post("/api/auth/demo", json={})
        assert guest.status_code == 201, guest.text
        csrf = guest.json()["csrf_token"]
        businesses = cli.get("/api/businesses").json()
        cafe = next(b for b in businesses if b["industry"] == "fnb")
        saved = patch(cli, cafe["id"], csrf, {
            "display_name": "Tropical Garden",
            "description": "Freshly roasted coffee",
            "banner_preset": "coffee",
        })
        assert saved.status_code == 200
        customer = cli.get("/api/preview/cafe")
        assert customer.status_code == 200
        branding = customer.json()["business"]["branding"]
        assert branding["display_name"] == "Tropical Garden"
        assert branding["banner_preset"] == "coffee"
        assert customer.json()["business"]["name"] == "Tropical Garden"

def test_plus_uploaded_images_persist_preview_crops_and_tenant_isolation():
    from io import BytesIO
    from PIL import Image
    from app.models import StorefrontMedia

    photo = BytesIO()
    Image.new("RGB", (160, 100), (31, 92, 166)).save(photo, format="PNG")
    content = photo.getvalue()

    with TestClient(app) as owner, TestClient(app) as other:
        csrf = register(owner, "uploader")
        bid = create(owner, csrf, "Upload Cafe", "PLUS")
        other_csrf = register(other, "otheruploader")
        other_bid = create(other, other_csrf, "Other Cafe", "PLUS")
        upload_url = f"/api/businesses/{bid}/storefront-media/banner"

        assert owner.put(upload_url, files={"file": ("banner.png", content, "image/png")}).status_code == 403
        invalid = owner.put(upload_url, files={"file": ("script.svg", b"<svg/>", "image/svg+xml")},
                            headers={"x-csrf-token": csrf})
        assert invalid.status_code == 422
        response = owner.put(upload_url, files={"file": ("banner.png", content, "image/png")},
                             headers={"x-csrf-token": csrf})
        assert response.status_code == 200, response.text
        branding = response.json()["branding"]
        assert branding["banner_uploaded"] is True
        assert branding["banner_image"].startswith(upload_url + "?v=")
        assert owner.get(upload_url).content[:4] == b"RIFF"
        assert owner.get(upload_url).headers["content-type"].startswith("image/webp")
        assert other.get(upload_url).status_code == 404
        assert other.get(f"/api/businesses/{other_bid}/storefront-media/banner").status_code == 404

        cropped = patch(owner, bid, csrf, {
            "banner_position_x": 17, "banner_position_y": 83,
            "logo_position_x": 5, "logo_position_y": 92,
        })
        assert cropped.status_code == 200, cropped.text
        brand = owner.get(f"/api/businesses/{bid}/storefront-preview").json()["business"]["branding"]
        assert brand["banner_position_x"] == 17
        assert brand["banner_position_y"] == 83
        assert brand["banner_uploaded"] is True
        assert patch(owner, bid, csrf, {"banner_position_x": 101}).status_code == 422

        logo_url = f"/api/businesses/{bid}/storefront-media/logo"
        logo = owner.put(logo_url, files={"file": ("logo.png", content, "image/png")},
                         headers={"x-csrf-token": csrf})
        assert logo.status_code == 200, logo.text
        assert logo.json()["branding"]["logo_image"].startswith(logo_url)
        with SessionLocal() as db:
            media = db.get(StorefrontMedia, (bid, "banner"))
            assert media and len(media.data) <= 850_000

        remove = owner.delete(upload_url, headers={"x-csrf-token": csrf})
        assert remove.status_code == 200
        assert remove.json()["branding"]["banner_uploaded"] is False
        assert owner.get(upload_url).status_code == 404

    with TestClient(app) as basic:
        token = register(basic, "basicuploader")
        basic_id = create(basic, token, "Basic Cafe", "BASIC")
        result = basic.put(f"/api/businesses/{basic_id}/storefront-media/banner",
                           files={"file": ("photo.png", content, "image/png")},
                           headers={"x-csrf-token": token})
        assert result.status_code == 403


def test_brand_editor_upload_controls_and_position_preview_are_wired():
    html = (Path(__file__).resolve().parents[1] / "app/static/brand-editor.html").read_text()
    js = (Path(__file__).resolve().parents[1] / "app/static/brand-editor.js").read_text()
    owner = (Path(__file__).resolve().parents[1] / "app/static/storefront-owner-preview.js").read_text()
    assert 'id="brand-banner-file"' in html and 'id="brand-logo-file"' in html
    assert 'data-drag-image="banner"' in html and 'data-drag-image="logo"' in html
    assert "URL.createObjectURL" in js and "pointermove" in js
    assert "storefront-media/" in js and "new FormData()" in js
    assert "brand.banner_position_x" in owner and "brand.logo_image" in owner
