"""Live browser smoke check for EZ Thing demo storefronts; staging only."""
import json
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

BASE = "https://ez-thing-staging.onrender.com"

def dump_get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=25) as r:
            data = r.read(3000).decode("utf-8", errors="replace")
            print(f"HTTP {path}: {r.status} {data[:800]}", flush=True)
    except Exception as e:
        print(f"HTTP {path} FAILED: {e!r}", flush=True)

for path in ("/api/health", "/api/config"):
    dump_get(path)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
    context = browser.new_context(locale="en-US", viewport={"width": 412, "height": 915})
    page = context.new_page()
    requests = []
    errors = []
    page.on("request", lambda req: requests.append(f"> {req.method} {req.url.replace(BASE, '')}"))
    page.on("response", lambda resp: requests.append(f"< {resp.status} {resp.url.replace(BASE, '')}") if "/api/" in resp.url else None)
    page.on("pageerror", lambda err: errors.append(f"PAGE ERROR: {err}"))
    page.on("console", lambda msg: errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type=="error" else None)
    print("BROWSER: opening /menu/cafe", flush=True)
    try:
        page.goto(BASE + "/menu/cafe", wait_until="domcontentloaded", timeout=45000)
        print("BROWSER: document loaded", flush=True)
        for s in (5, 10):
            page.wait_for_timeout(s*1000)
            print("BROWSER:", json.dumps({
                "step_s": s, "url": page.url,
                "title": page.title(),
                "text": page.locator("body").inner_text(timeout=5000)[:850],
                "loader_count": page.locator(".customer-loading").count()
            }, ensure_ascii=False), flush=True)
    except Exception as e:
        print(f"BROWSER EXCEPTION: {e!r}", flush=True)
    print("REQUESTS",json.dumps(requests,indent=2),flush=True)
    print("JS_ERRORS",json.dumps(errors,indent=2),flush=True)
    browser.close()
    if any("PAGE ERROR" in e for e in errors):
        sys.exit(2)
    if not requests or not any("/api/auth/" in v for v in requests):
        print("DIAGNOSIS: AUTH WAS NEVER REQUESTED AFTER CONFIG",flush=True)
        sys.exit(3)
