"""Check the already deployed Render staging demo end-to-end in Chromium."""
import json
import sys
import urllib.request
from playwright.sync_api import sync_playwright

BASE="https://ez-thing-staging.onrender.com"
with urllib.request.urlopen(BASE+"/api/config",timeout=15) as response:
    config=json.load(response)
print("Render staging /api/config:",json.dumps(config),flush=True)
assert config.get("demo_enabled") is True,"Demo guard disabled on staging"

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
    context=browser.new_context(locale="en-US",viewport={"width":412,"height":915})
    page=context.new_page()
    traffic=[]
    errors=[]
    page.on("request",lambda request: traffic.append(f"> {request.method} {request.url.replace(BASE,'')}") if "/api/" in request.url else None)
    page.on("response",lambda response: traffic.append(f"< {response.status} {response.url.replace(BASE,'')}") if "/api/" in response.url else None)
    page.on("pageerror",lambda e:errors.append(str(e)))
    print("Opening staging /menu/cafe",flush=True)
    page.goto(BASE+"/menu/cafe",wait_until="domcontentloaded",timeout=20000)
    print("DOMContentLoaded; waiting for merchant-hero",flush=True)
    page.locator(".merchant-hero").wait_for(timeout=30000)
    print("SUCCESS: storefront rendered; products =",page.locator(".customer-product").count(),flush=True)
    print("TRAFFIC",json.dumps(traffic,ensure_ascii=False),flush=True)
    print("JS ERRORS",json.dumps(errors,ensure_ascii=False),flush=True)
    assert page.locator(".customer-product").count()>=1
    assert any("POST /api/auth/demo" in line or "GET /api/auth/me" in line for line in traffic)
    assert any("GET /api/preview/cafe" in line for line in traffic)
    assert not errors
    browser.close()
