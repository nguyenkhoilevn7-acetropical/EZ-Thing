"""Full demo crawl in a real browser: every merchant tab, modal and customer page.

Starts an isolated local staging server (SQLite, demo enabled), opens the
merchant back-office as a demo guest and visits every navigation tab of every
demo business on desktop and mobile, opens each "new ..." dialog, then walks
every customer-facing page. Records uncaught page errors, console errors and
failed API responses. Exits non-zero when any problem is found.

Usage: python tests/demo_full_crawl.py [report.json]
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

PORT = 8766
BASE = f"http://127.0.0.1:{PORT}"
REPORT = sys.argv[1] if len(sys.argv) > 1 else "demo-crawl-report.json"
# Expected, handled responses (not defects): unauthenticated probe before demo
# session, and plan-gated endpoints answered with an explicit 403 the UI shows.
IGNORED_STATUS = {("GET", "/api/auth/me", 401)}

env = os.environ.copy()
env.update({
    "EZ_THING_ENVIRONMENT": "staging",
    "EZ_THING_DEMO_MODE": "1",
    "COOKIE_SECURE": "0",
    "DATABASE_URL": "sqlite:///./demo-crawl.db",
})
if os.path.exists("demo-crawl.db"):
    os.remove("demo-crawl.db")
log = open("demo-crawl-server.log", "w")
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--host", "127.0.0.1"],
    env=env, stdout=log, stderr=subprocess.STDOUT)

problems = []
visited = []
context_label = {"where": "startup"}


def record(kind, detail):
    entry = {"where": context_label["where"], "kind": kind, "detail": detail[:600]}
    if entry not in problems:
        problems.append(entry)
        print("PROBLEM", json.dumps(entry, ensure_ascii=False), flush=True)


def wire(page):
    page.on("pageerror", lambda err: record("pageerror", str(err)))

    def on_console(msg):
        if msg.type != "error":
            return
        text = msg.text
        # Browser echoes every failed fetch as a console error; those are
        # recorded precisely by the response hook below.
        if "Failed to load resource" in text:
            return
        record("console", text)
    page.on("console", on_console)

    def on_response(resp):
        url = resp.url.replace(BASE, "")
        if not url.startswith("/api/") and not url.startswith("/assets/"):
            if resp.status >= 400 and resp.request.resource_type == "document":
                record("document", f"{resp.status} {url}")
            return
        if resp.status < 400:
            return
        path = url.split("?", 1)[0]
        method = resp.request.method
        if (method, path, resp.status) in IGNORED_STATUS:
            return
        try:
            body = resp.text()[:300]
        except Exception:  # noqa: BLE001 - diagnostic only
            body = ""
        record("http", f"{resp.status} {method} {url} :: {body}")
    page.on("response", on_response)
    page.on("dialog", lambda d: d.dismiss())


def settle(page, ms=900):
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(ms)


def safe(label, fn):
    context_label["where"] = label
    visited.append(label)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - every failure is a finding
        record("step-failed", f"{type(exc).__name__}: {exc}")


def close_modal(page):
    for selector in ('[data-action="close-modal"]', ".modal-close", '[data-action="close"]'):
        button = page.locator(selector)
        if button.count() and button.first.is_visible():
            button.first.click()
            page.wait_for_timeout(250)
            return
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)


def nav_tabs(page, mobile):
    container = ".mobile-nav" if mobile else ".side-nav"
    return page.eval_on_selector_all(
        f'{container} [data-action="tab"]',
        "els => [...new Set(els.map(e => e.dataset.value))]")


def open_tab(page, tab, mobile):
    container = ".mobile-nav" if mobile else ".side-nav"
    locator = page.locator(f'{container} [data-action="tab"][data-value="{tab}"]')
    if not locator.count() or not locator.first.is_visible():
        # Mobile "more" tabs live in the drawer / settings screen.
        page.evaluate("tab => { const b=[...document.querySelectorAll('[data-action=\"tab\"]')]"
                      ".find(x=>x.dataset.value===tab); if(b) b.click(); }", tab)
    else:
        locator.first.click()
    settle(page)
    if page.locator("#page-content").count() == 0:
        raise AssertionError("page content disappeared after opening tab " + tab)
    text = page.locator("#page-content").inner_text(timeout=5000).strip()
    if not text:
        raise AssertionError("tab rendered empty: " + tab)
    for bad in ("undefined", "NaN", "[object Object]"):
        if bad in text:
            record("render", f"tab {tab} shows '{bad}': " + text[text.find(bad) - 80:text.find(bad) + 40])


def select_business(page, bid):
    page.evaluate("bid => { const b=document.querySelector('[data-action=\"switch-business\"]');"
                  " if(b) b.click(); }", bid)
    page.wait_for_timeout(300)
    page.locator(f'[data-action="select-business"][data-value="{bid}"]').first.click()
    settle(page)
    page.locator(".app").wait_for(timeout=15000)


NEW_ACTIONS = ("new-order", "new-product", "new-customer", "new-table", "new-branch",
               "industry-new", "edit-modifiers", "adjust-stock")


def exercise_dialogs(page, tab):
    for action in NEW_ACTIONS:
        button = page.locator(f'#page-content [data-action="{action}"]')
        if not button.count() or not button.first.is_visible():
            continue
        safe(f"{context_label['where'].split(' :: ')[0]} :: {tab} :: open {action}",
             lambda: (button.first.click(), settle(page, 500), close_modal(page)))


def crawl_merchant(browser, mobile):
    page = browser.new_page(locale="vi-VN", viewport=({"width": 412, "height": 915} if mobile
                                                      else {"width": 1440, "height": 920}))
    wire(page)
    tag = "mobile" if mobile else "desktop"
    safe(f"merchant {tag} :: enter demo", lambda: (
        page.goto(BASE + "/app", wait_until="domcontentloaded"),
        page.locator(".app").wait_for(timeout=45000), settle(page)))
    businesses = page.evaluate("fetch('/api/businesses').then(r=>r.json())")
    print(f"{tag}: {len(businesses)} demo businesses", flush=True)
    for business in businesses:
        label = f"merchant {tag} :: {business['industry']} {business['name']}"
        safe(label + " :: select", lambda: select_business(page, business["id"]))
        try:
            tabs = nav_tabs(page, mobile)
        except Exception as exc:  # noqa: BLE001
            record("step-failed", f"cannot list tabs: {exc}")
            continue
        if mobile:
            # Bottom nav is a subset; also reach every desktop-only tab.
            tabs = list(dict.fromkeys(tabs + page.eval_on_selector_all(
                '[data-action="tab"]', "els => els.map(e => e.dataset.value)")))
        for tab in tabs:
            safe(f"{label} :: tab {tab}", lambda: open_tab(page, tab, mobile))
            context_label["where"] = f"{label} :: {tab}"
            if not mobile:
                exercise_dialogs(page, tab)
    page.close()


def crawl_customer(browser):
    page = browser.new_page(locale="vi-VN", viewport={"width": 412, "height": 915})
    wire(page)
    for path in ("/", "/menu/cafe", "/store/mart", "/store/online", "/booking/wellness",
                 "/reserve/cafe", "/app/storefront-design", "/admin"):
        def visit(path=path):
            page.goto(BASE + path, wait_until="domcontentloaded")
            settle(page, 1500)
            body = page.locator("body").inner_text(timeout=5000)
            if not body.strip():
                raise AssertionError("blank page")
        safe(f"customer :: {path}", visit)

    def cart_flow(path):
        page.goto(BASE + path, wait_until="domcontentloaded")
        page.locator(".customer-product").first.wait_for(timeout=25000)
        add = page.locator(".customer-product button").first
        add.click()
        settle(page, 500)
        options = page.locator("[data-overlay] input[type=radio], [data-overlay] input[type=checkbox]")
        if options.count():
            close_modal(page)
    for path in ("/menu/cafe", "/store/mart", "/store/online"):
        safe(f"customer :: {path} :: add to cart", lambda path=path: cart_flow(path))
    page.close()


try:
    for _ in range(120):
        if server.poll() is not None:
            raise RuntimeError("server crashed; see demo-crawl-server.log")
        try:
            with urllib.request.urlopen(BASE + "/api/config", timeout=2) as r:
                if json.load(r).get("demo_enabled"):
                    break
        except OSError:
            time.sleep(0.25)
    else:
        raise RuntimeError("server startup timed out")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        crawl_merchant(browser, mobile=False)
        crawl_merchant(browser, mobile=True)
        crawl_customer(browser)
        browser.close()
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
    log.close()
    with open("demo-crawl-server.log") as server_log:
        tracebacks = [line for line in server_log.read().splitlines()
                      if "Traceback" in line or "Error" in line]
    for line in tracebacks[:40]:
        record("server-log", line)
    with open(REPORT, "w") as out:
        json.dump({"visited": visited, "problems": problems}, out, ensure_ascii=False, indent=1)
    print(f"VISITED {len(visited)} steps, PROBLEMS {len(problems)}", flush=True)

sys.exit(1 if problems else 0)
