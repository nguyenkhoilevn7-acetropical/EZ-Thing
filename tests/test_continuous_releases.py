"""Continuous delivery without public/manual version increments."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.asset_pipeline import AssetPipeline, STATIC_ASSETS
from app.main import app

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def hash_for(name: str) -> str:
    return hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:16]


def test_public_pages_use_content_hash_without_hardcoded_versions():
    with TestClient(app) as client:
        for page, expected in (
            ("/", "public.css"),
            ("/app", "app.js"),
            ("/admin", "admin.js"),
            ("/menu/cafe", "customer.js"),
            ("/reserve/cafe", "reservations.js"),
            ("/app/storefront-design", "brand-editor.js"),
        ):
            response = client.get(page)
            assert response.status_code == 200, (page, response.text[:200])
            assert response.headers["Cache-Control"].startswith("no-store")
            assert response.headers["content-type"].startswith("text/html")
            markup = response.text
            # Every reference must reflect the *current file bytes*, not
            # the dates or vXX tokens that may remain in old source HTML.
            assert "?v=" not in markup, page
            expected_url = "/assets/" + expected + "?h=" + hash_for(expected)
            assert expected_url in markup, (page, expected_url)
        # Icons, even if the source page used the old fixed ?v= query,
        # also get their real bytes-based fingerprint on the wire.
        assert ("/assets/icons/ez-mark-light.svg?h="
                + hash_for("icons/ez-mark-light.svg")) in client.get("/app").text


def test_manifest_and_service_worker_inherit_content_identity():
    with TestClient(app) as client:
        manifest = client.get("/manifest.webmanifest")
        assert manifest.status_code == 200
        assert "no-cache" in manifest.headers["Cache-Control"]
        for icon in manifest.json()["icons"]:
            path = icon["src"].split("?", 1)[0].removeprefix("/assets/")
            assert icon["src"].endswith("?h=" + hash_for(path))

        worker = client.get("/sw.js")
        assert worker.status_code == 200
        assert "no-store" in worker.headers["Cache-Control"]
        text = worker.text
        assert "ezthing-shell-" + STATIC_ASSETS.shell_hash in text
        assert "/assets/app.js?h=" + hash_for("app.js") in text
        assert "/assets/customer.js?h=" + hash_for("customer.js") in text
        assert "__EZ_CONTENT_HASH__" not in text
        assert "__EZ_PRECACHE_ASSETS__" not in text
        assert "url.pathname.startsWith('/api/')" in text
        assert "request.method !== 'GET'" in text
        assert "caches.open(SHELL)" in text
        assert "caches.keys()" in text


def test_single_asset_change_alters_html_url_and_worker_shell_without_manual_bump(tmp_path):
    root = tmp_path / "static"
    root.mkdir()
    (root / "app.js").write_text("console.log('before');", encoding="utf-8")
    (root / "styles.css").write_text("body{color:black}", encoding="utf-8")
    (root / "index.html").write_text(
        '<script defer src="/assets/app.js?v=obsolete"></script>'
        '<link href="/assets/styles.css" rel="stylesheet">', encoding="utf-8")
    (root / "sw.js").write_text(
        "const SHELL='ezthing-shell-__EZ_CONTENT_HASH__';"
        "const PRECACHE=__EZ_PRECACHE_ASSETS__;", encoding="utf-8")
    (root / "manifest.webmanifest").write_text(
        '{"name":"EZ Thing","icons":[]}', encoding="utf-8")

    before = AssetPipeline(root)
    old_markup = before.page("index.html").body.decode("utf-8")
    old_shell = before.shell_hash
    old_worker = before.service_worker().body.decode("utf-8")
    assert "?v=" not in old_markup

    (root / "app.js").write_text("console.log('after');", encoding="utf-8")
    after = AssetPipeline(root)
    new_markup = after.page("index.html").body.decode("utf-8")
    assert new_markup != old_markup
    assert before.hashes["/assets/app.js"] != after.hashes["/assets/app.js"]
    assert after.shell_hash != old_shell
    assert after.service_worker().body.decode("utf-8") != old_worker
    # An unrelated stylesheet is unchanged and retains the same URL.
    assert after.asset_url("/assets/styles.css") == before.asset_url("/assets/styles.css")
    assert after.asset_url("/assets/app.js?v=stale") == after.asset_url("/assets/app.js")

    # Changing only shell HTML still changes the worker cache key,
    # without changing the content hash of any JS asset.
    (root / "index.html").write_text(
        (root / "index.html").read_text() + "<p>Change</p>", encoding="utf-8")
    third = AssetPipeline(root)
    assert third.shell_hash != after.shell_hash
    assert third.asset_url("/assets/app.js") == after.asset_url("/assets/app.js")


def test_no_api_or_customer_financial_data_in_shell_preload():
    with TestClient(app) as client:
        worker = client.get("/sw.js").text
        assert not re.search(r'\bPRECACHE\s*=\s*\[[^\]]*"/api/', worker)
        assert "'/api/'" in worker or '"/api/"' in worker
        assert "url.pathname.startsWith('/assets/')" in worker
        assert "fetch(request)" in worker
        assert client.get("/api/config").headers["Cache-Control"] == "no-store"


def test_admin_hides_public_version_and_keeps_private_deployment_view():
    admin_js = (STATIC / "admin.js").read_text(encoding="utf-8")
    assert "EZ Thing v0.4" not in admin_js
    assert "Triển khai liên tục" in admin_js
    assert "d.release?.commit" in admin_js
    assert "d.release?.asset_fingerprint" in admin_js
