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
IGNORED_STATUS = {("GET", "/api/auth/me", 401), ("GET", "/api/admin/session", 403)}

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
OPEN_PAGES = []
visited = []
context_label = {"where": "startup"}


def record(kind, detail):
    entry = {"where": context_label["where"], "kind": kind, "detail": detail[:600]}
    if entry not in problems:
        problems.append(entry)
        print("PROBLEM", json.dumps(entry, ensure_ascii=False), flush=True)


TOAST_OBSERVER = """
(() => {
  window.__errorToasts = [];
  const bad = el => el.matches && (el.matches('.toast.error,.customer-toast.bad,#res-toast.error,.toast.show.error') );
  new MutationObserver(list => {
    for (const m of list) {
      const nodes = [m.target, ...m.addedNodes];
      for (const n of nodes) if (n.nodeType === 1 && bad(n) && n.textContent.trim())
        window.__errorToasts.push(n.textContent.trim());
    }
  }).observe(document, {subtree: true, childList: true, attributes: true,
                                         attributeFilter: ['class']});
})();
"""


def drain_toasts(page):
    try:
        messages = page.evaluate("() => { const x=[...new Set(window.__errorToasts||[])];"
                                 " window.__errorToasts=[]; return x; }")
    except Exception:  # noqa: BLE001
        return
    for message in messages:
        record("error-toast", message)


def wire(page):
    page.add_init_script(TOAST_OBSERVER)
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
    for page in OPEN_PAGES:
        if not page.is_closed():
            drain_toasts(page)


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
    OPEN_PAGES.append(page)
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
    OPEN_PAGES.append(page)
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


FILL_FORM = r"""
(form) => {
  const pad = n => String(n).padStart(2, '0');
  const tomorrow = new Date(Date.now() + 86400000);
  const day = tomorrow.getFullYear() + '-' + pad(tomorrow.getMonth() + 1) + '-' + pad(tomorrow.getDate());
  const tag = Math.random().toString(36).slice(2, 7).toUpperCase();
  for (const el of form.querySelectorAll('input,select,textarea')) {
    if (el.disabled || el.type === 'hidden' || el.type === 'submit' || el.type === 'button') continue;
    if (el.type === 'checkbox') { if (el.required) el.checked = true; continue; }
    if (el.type === 'radio') { if (!form.querySelector(`input[name="${el.name}"]:checked`)) el.checked = true; continue; }
    if (el.tagName === 'SELECT') {
      if (!el.value) { const o = [...el.options].find(x => x.value); if (o) el.value = o.value; }
      el.dispatchEvent(new Event('change', {bubbles: true})); continue;
    }
    if (el.value) continue;
    const name = (el.name || '').toLowerCase();
    let v;
    if (el.type === 'number') v = String(Math.max(Number(el.min || 1), 1));
    else if (el.type === 'date') v = day;
    else if (el.type === 'datetime-local') v = day + 'T10:00';
    else if (el.type === 'time') v = '10:00';
    else if (el.type === 'email' || name.includes('email')) v = 'demo.crawl@example.com';
    else if (el.type === 'tel' || name.includes('phone')) v = '0901234567';
    else if (name === 'sku') v = 'CRAWL-' + tag;
    else v = 'Demo kiểm thử ' + tag;
    const max = Number(el.maxLength) > 0 ? Number(el.maxLength) : 200;
    el.value = v.slice(0, max);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  }
  return [...form.querySelectorAll('[name]')].map(x => x.name + '=' + x.value).join('&');
}
"""


def submit_open_form(page, label):
    """Fill the currently open dialog form and submit it; record visible failures."""
    form = page.locator("#modal-root form, .overlay form, [role=dialog] form").first
    if not form.count():
        raise AssertionError("no form opened for " + label)
    form.evaluate(FILL_FORM)
    form.evaluate("f => f.requestSubmit ? f.requestSubmit() : f.submit()")
    settle(page, 1200)
    still_open = page.locator("#modal-root form, .overlay form").count()
    if still_open:
        invalid = page.evaluate("() => [...document.querySelectorAll('#modal-root :invalid, .overlay :invalid')]"
                                ".map(x => (x.name||x.tagName) + ': ' + x.validationMessage)")
        if invalid:
            record("form-invalid", f"{label}: {invalid}")
        close_modal(page)


def click_action(page, action, value=None):
    selector = f'#page-content [data-action="{action}"]'
    if value is not None:
        selector += f'[data-value="{value}"]'
    button = page.locator(selector)
    if not button.count():
        return False
    button.first.scroll_into_view_if_needed()
    button.first.click()
    settle(page, 600)
    return True


def pos_sale(page, pay):
    """Ring up products in the POS and either pay by cash or leave the check open."""
    open_tab(page, "pos", False)
    products = page.locator('#ez-register [data-ezreg="product"]:not([disabled])')
    if not products.count():
        raise AssertionError("POS shows no products")
    for index in range(min(2, products.count())):
        products.nth(index).click()
        page.wait_for_timeout(400)
        sheet = page.locator('[data-ezreg="option-save"]')
        if sheet.count() and sheet.first.is_visible():
            groups = page.eval_on_selector_all('#ez-register [data-ezreg="option"]',
                                               "els => [...new Set(els.map(e => e.dataset.group))]")
            for group in groups:
                page.locator(f'#ez-register [data-ezreg="option"][data-group="{group}"]').first.click()
                page.wait_for_timeout(150)
            sheet.first.click()
            page.wait_for_timeout(400)
            if sheet.count() and sheet.first.is_visible():
                record("pos", "option sheet did not accept first option of every group")
                page.locator('[data-ezreg="option-close"]').first.click()
    if pay:
        page.locator('#ez-register [data-ezreg="checkout"]').first.click()
        settle(page, 500)
        quick = page.locator('[data-ezpay="quick"]')
        if quick.count():
            quick.first.click()
        confirm_box = page.locator("[data-ezpay-confirm]")
        if confirm_box.count() and not confirm_box.first.is_checked():
            confirm_box.first.check()
        page.locator('[data-ezpay="confirm"]').first.click()
        settle(page, 1500)
    else:
        page.locator('#ez-register [data-ezreg="create"]').first.click()
        settle(page, 1500)


def crawl_workflows(browser):
    page = browser.new_page(locale="vi-VN", viewport={"width": 1440, "height": 920})
    wire(page)
    OPEN_PAGES.append(page)
    safe("flow :: enter demo", lambda: (
        page.goto(BASE + "/app", wait_until="domcontentloaded"),
        page.locator(".app").wait_for(timeout=45000), settle(page)))
    businesses = page.evaluate("fetch('/api/businesses').then(r=>r.json())")
    for business in businesses:
        label = f"flow :: {business['industry']}"
        safe(label + " :: select", lambda: select_business(page, business["id"]))
        tabs = nav_tabs(page, False)

        def create(tab, action, what):
            def run():
                open_tab(page, tab, False)
                if not click_action(page, action):
                    raise AssertionError(f"button {action} missing on tab {tab}")
                submit_open_form(page, what)
            safe(f"{label} :: {what}", run)

        if "products" in tabs:
            create("products", "new-product", "create product")

            def stock():
                open_tab(page, "products", False)
                if click_action(page, "adjust-stock"):
                    submit_open_form(page, "adjust stock")
            safe(f"{label} :: adjust stock", stock)
        if "customers" in tabs:
            create("customers", "new-customer", "create customer")
        if "pos" in tabs:
            safe(f"{label} :: POS sale paid by cash", lambda: pos_sale(page, pay=True))
            safe(f"{label} :: POS open check", lambda: pos_sale(page, pay=False))

            def cancel_open():
                open_tab(page, "orders", False)
                if click_action(page, "cancel-order"):
                    submit_open_form(page, "cancel order")
            safe(f"{label} :: cancel open order", cancel_open)

            def pay_open():
                pos_sale(page, pay=False)
                open_tab(page, "orders", False)
                if click_action(page, "confirm-paid"):
                    quick = page.locator('[data-ezpay="quick"]')
                    if quick.count():
                        quick.first.click()
                    box = page.locator("[data-ezpay-confirm]")
                    if box.count() and not box.first.is_checked():
                        box.first.check()
                    page.locator('[data-ezpay="confirm"]').first.click()
                    settle(page, 1200)
            safe(f"{label} :: pay open order from order list", pay_open)
        for tab in ("inventory", "delivery", "appointments"):
            if tab in tabs:
                def industry(tab=tab):
                    open_tab(page, tab, False)
                    if click_action(page, "industry-new"):
                        submit_open_form(page, "new " + tab)
                safe(f"{label} :: new {tab} item", industry)
        if "kitchen" in tabs:
            def kitchen():
                open_tab(page, "kitchen", False)
                status = page.locator('[data-kds="status"]')
                if status.count():
                    status.first.click()
                    settle(page, 800)
            safe(f"{label} :: kitchen advance first line", kitchen)
        if "settings" in tabs:
            def branch():
                open_tab(page, "settings", False)
                if click_action(page, "new-branch"):
                    submit_open_form(page, "new branch")
            safe(f"{label} :: new branch", branch)
        def verify_ledger():
            if "pos" not in tabs:
                return
            orders = page.evaluate("bid => fetch('/api/businesses/'+bid+'/orders').then(r=>r.json())",
                                   business["id"])
            statuses = {}
            for order in orders:
                statuses[order["status"]] = statuses.get(order["status"], 0) + 1
            print(f"LEDGER {business['industry']}: {statuses}", flush=True)
            for wanted in ("paid", "cancelled"):
                if not statuses.get(wanted):
                    record("ledger", f"no {wanted} order was produced by the UI flow: {statuses}")
        safe(f"{label} :: verify orders written by UI", verify_ledger)
        # Re-open every tab after the writes: data changes must still render.
        for tab in tabs:
            safe(f"{label} :: re-render {tab}", lambda tab=tab: open_tab(page, tab, False))
    page.close()


def crawl_customer_flows(browser):
    page = browser.new_page(locale="vi-VN", viewport={"width": 412, "height": 915})
    wire(page)
    OPEN_PAGES.append(page)

    def checkout(path):
        page.goto(BASE + path, wait_until="domcontentloaded")
        page.locator('[data-action="add"]').first.wait_for(timeout=30000)
        page.locator('[data-action="add"]').first.click()
        page.wait_for_timeout(400)
        page.locator('[data-action="open-cart"]').first.click()
        settle(page, 500)
        form = page.locator("[data-overlay] form").first
        if not form.count():
            raise AssertionError("cart has no checkout form")
        form.evaluate(FILL_FORM)
        form.evaluate("f => f.requestSubmit()")
        settle(page, 1500)
        if not page.locator(".customer-success").count():
            raise AssertionError("no success screen after checkout")
    for path in ("/menu/cafe", "/store/mart", "/store/online"):
        safe(f"customer flow :: {path} :: checkout", lambda path=path: checkout(path))

    def wellness():
        page.goto(BASE + "/booking/wellness", wait_until="domcontentloaded")
        page.locator('[data-action="slot"]').first.wait_for(timeout=30000)
        page.locator('[data-action="slot"]').first.click()
        page.wait_for_timeout(300)
        page.locator('[data-action="open-booking"]').first.click()
        settle(page, 500)
        form = page.locator("[data-overlay] form").first
        form.evaluate(FILL_FORM)
        form.evaluate("f => f.requestSubmit()")
        settle(page, 1500)
        if not page.locator(".customer-success").count():
            raise AssertionError("no success screen after booking")
    safe("customer flow :: wellness booking", wellness)

    def reserve():
        page.goto(BASE + "/reserve/cafe", wait_until="domcontentloaded")
        # Book tomorrow: today's demo slots (08:00-20:30) may already be past.
        page.locator("#booking-day").evaluate(
            "el => { const d=new Date(Date.now()+86400000);"
            " el.value=d.toISOString().slice(0,10); el.dispatchEvent(new Event('change',{bubbles:true})); }")
        page.locator("#booking-slots .slot-button").first.wait_for(timeout=30000)
        form = page.locator("#guest-reservation-form")
        # Fill contact fields first: changing party size reloads the slots
        # and correctly clears an earlier time choice.
        form.evaluate(FILL_FORM)
        page.wait_for_timeout(500)
        page.locator("#booking-slots .slot-button").first.wait_for(timeout=30000)
        page.locator("#booking-slots .slot-button").first.click()
        form.evaluate("f => f.requestSubmit()")
        settle(page, 1500)
        if not page.locator("#booking-result").inner_text().strip():
            raise AssertionError("reservation result is empty")
    safe("customer flow :: table reservation", reserve)

    def inquiry():
        form = page.locator("#guest-inquiry-form")
        form.evaluate(FILL_FORM)
        form.evaluate("f => f.requestSubmit()")
        settle(page, 1200)
    safe("customer flow :: contact inquiry", inquiry)
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
        crawl_workflows(browser)
        crawl_customer_flows(browser)
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
