"""Real-browser end-to-end test: local staging server, isolated demo tenant."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
env=os.environ.copy()
env.update({
 "EZ_THING_ENVIRONMENT":"staging",
 "EZ_THING_DEMO_MODE":"1",
 "COOKIE_SECURE":"0",
 "DATABASE_URL":"sqlite:///./browser-smoke.db",
})
server=subprocess.Popen(
 [sys.executable,"-m","uvicorn","app.main:app","--port","8765","--host","127.0.0.1"],
 env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT
)
try:
 for _ in range(60):
  if server.poll() is not None:raise RuntimeError("test server crashed")
  try:
   with urllib.request.urlopen(BASE+"/api/config",timeout=2) as r:
    config=json.load(r)
   if config.get("demo_enabled"):break
   raise RuntimeError("demo disabled in local staging")
  except OSError:time.sleep(.25)
 else:raise RuntimeError("server startup timed out")
 print("LOCAL SERVER: ready with isolated staging demo enabled",flush=True)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
  page=browser.new_page(locale="en-US",viewport={"width":412,"height":915})
  requests,errors=[],[]
  page.on("request",lambda req: requests.append(f"> {req.method} {req.url.replace(BASE,'')}") if "/api/" in req.url else None)
  page.on("response",lambda resp: requests.append(f"< {resp.status} {resp.url.replace(BASE,'')}") if "/api/" in resp.url else None)
  page.on("pageerror",lambda err:errors.append(str(err)))
  page.on("console",lambda msg:errors.append(f"console: {msg.text}") if msg.type=="error" and "401 (Unauthorized)" not in msg.text else None)
  for channel in ("/menu/cafe","/store/mart","/store/online","/booking/wellness"):
   print("BROWSER visiting",channel,flush=True)
   page.goto(BASE+channel,wait_until="domcontentloaded",timeout=15000)
   page.locator(".merchant-hero").wait_for(timeout=25000)
   assert page.locator(".customer-loading").count()==0,channel
   assert page.locator(".customer-product").count()>0 or channel=="/booking/wellness",channel
   print("PASS",channel,"title=",page.title(),flush=True)
  # The Wellness selection widget must retain its header, hero, form and panel nodes
  # during each service / slot / specialist change (no page-wide flash).
  page.goto(BASE+"/booking/wellness",wait_until="domcontentloaded",timeout=15000)
  page.locator(".booking-slot").first.wait_for(timeout=25000)
  page.evaluate("""() => {
    window.__wellnessStable = {
      header: document.querySelector('.customer-header'),
      hero: document.querySelector('.merchant-hero'),
      date: document.querySelector('#book-date'),
      staff: document.querySelector('#book-staff'),
      panel: document.querySelector('#booking-right'),
      firstService: document.querySelector('.booking-service')
    };
  }""")
  assert page.locator(".booking-service").count()>=2
  page.locator(".booking-service").last.click()
  page.wait_for_function("""() => document.querySelector('.booking-slots')?.getAttribute('aria-busy') === 'false'
    && document.querySelectorAll('.booking-slot').length > 0""",timeout=25000)
  def wellness_dom_stable():
   return page.evaluate("""() => Object.entries(window.__wellnessStable).every(([key,node]) =>
     node === document.querySelector({
      header:'.customer-header',hero:'.merchant-hero',date:'#book-date',
      staff:'#book-staff',panel:'#booking-right',firstService:'.booking-service'
     }[key]))""")
  assert wellness_dom_stable(), "Service tap replaced storefront DOM"
  page.locator(".booking-slot").first.click()
  assert page.locator('.booking-slot[aria-pressed="true"]').count()==1
  assert page.locator('[data-action="open-booking"]').is_enabled()
  assert wellness_dom_stable(), "Time slot tap replaced storefront DOM"
  page.locator("#book-staff").select_option(label="Minh")
  page.wait_for_function("""() => document.querySelector('.booking-slots')?.getAttribute('aria-busy') === 'false'""",timeout=25000)
  assert wellness_dom_stable(), "Specialist selection replaced storefront DOM"
  assert page.locator('#book-staff').input_value() == "Minh"
  print("PASS /booking/wellness: stable DOM on service, time and specialist changes",flush=True)

  # Verify the merchant order cards using the same seeded demo session.
  page.set_viewport_size({"width":1060,"height":800})
  page.goto(BASE+"/app?tab=orders",wait_until="domcontentloaded",timeout=15000)
  page.locator(".order-card").first.wait_for(timeout=25000)
  assert page.locator(".order-card").count()>=3, "Sample orders not displayed"
  assert page.locator(".order-card-pay").count()>=1, "Unpaid order lost payment action"
  assert page.locator(".order-card-status .pill.paid").count()>=1, "Blue paid badge missing"
  assert page.locator(".order-card-cancel").count()>=1, "Cancel action missing"
  assert page.locator(".orders-table").count()==0, "Legacy responsive table rendered"
  page.locator(".order-card-details").first.click()
  assert page.locator("#modal-root").inner_text().strip(), "Details dialog failed"
  page.keyboard.press("Escape")
  page.set_viewport_size({"width":412,"height":915})
  assert page.locator(".order-card").first.is_visible(), "Mobile order card hidden"
  page.evaluate("document.documentElement.setAttribute('data-ez-merchant-theme','graphite')")
  background=page.locator(".order-card").first.evaluate("(el)=>getComputedStyle(el).backgroundColor")
  assert background!="rgb(255, 255, 255)", "Dark order card remained white"
  print("PASS /app?tab=orders: cards, detail, paid badge, mobile and dark mode",flush=True)
  # V7 actual browser smoke: open a check editor without page shell replacement.
  page.locator('.order-card-edit').first.wait_for(timeout=15000)
  page.locator('.order-card-edit').first.click()
  page.locator('#pos-v7-editor .v7-line').first.wait_for(timeout=15000)
  assert page.locator('#pos-v7-editor .v7-line').count()>=1
  page.locator('#pos-v7-editor [data-pos7-action="add-line"]').click()
  assert page.locator('#pos-v7-editor .v7-line').count()>=2
  page.locator('#pos-v7-editor [data-pos7-action="remove-line"]').last.click()
  assert page.locator('#pos-v7-editor .v7-line').count()>=1
  assert page.locator('#pos-v7-total').inner_text().strip()
  page.keyboard.press("Escape")
  assert page.locator('#pos-v7-editor').count()==0
  assert page.locator('.order-card').first.is_visible()
  page.locator('.order-card-move').first.click()
  page.locator('#pos-v7-move select[name=table_id]').wait_for(timeout=15000)
  page.keyboard.press("Escape")
  assert page.locator('.order-card').first.is_visible()
  print("PASS /app?tab=orders V7: edit and move panels, responsive controls, no page shell flash",flush=True)

  # V5 is an integrated merchant tab: render real cards, load tenant data,
  # keep the mobile navigation, and respect Graphite surfaces.
  page.goto(BASE+"/app?tab=operations",wait_until="domcontentloaded",timeout=15000)
  page.locator("#ez-operations-v5 .v5-panel").first.wait_for(timeout=25000)
  assert page.locator("#ez-operations-v5 .v5-panel").count()>=2
  assert page.locator(".mobile-nav").count()==1
  assert page.locator("#ez-operations-v5 .v5-warning").count()==0, "Operations API failed"
  page.evaluate("document.documentElement.setAttribute('data-ez-merchant-theme','graphite')")
  card_bg=page.locator("#ez-operations-v5 .v5-panel").first.evaluate(
     "(el)=>getComputedStyle(el).backgroundColor")
  assert card_bg!="rgb(255, 255, 255)", "V5 Graphite card is white"
  print("PASS /app?tab=operations: loaded live tenant sections, mobile nav and dark theme",flush=True)
  # F&B mobile workflow: front-of-house first, KDS on main nav, secondary tabs
  # only in More. Do not rebuild the page shell when tapping station chips.
  page.goto(BASE+"/app?tab=operations",wait_until="domcontentloaded",timeout=15000)
  page.locator("#ez-operations-v5 .v5-panel").first.wait_for(timeout=25000)
  assert any(label in page.locator("#ez-operations-v5 .v5-intro").inner_text()
             for label in ("Lễ tân & xếp bàn","Front Desk & Seating"))
  mobile_tabs=page.locator(".mobile-nav [data-value]")
  values=mobile_tabs.evaluate_all("(nodes)=>nodes.map(n=>n.dataset.value)")
  assert values==["overview","orders","reservations","kitchen","settings"], values
  page.goto(BASE+"/app?tab=kitchen",wait_until="domcontentloaded",timeout=15000)
  page.locator("#ez-kds .kds-station").first.wait_for(timeout=25000)
  assert page.locator("#ez-kds .kds-station").count()==5
  assert page.locator("#ez-kds #kds-live").inner_text().strip()
  assert page.locator("#ez-kds [data-kds-form=fire]").count() <= 1
  page.evaluate("window.__kdsOriginal=document.querySelector('#ez-kds')")
  page.locator('#ez-kds [data-kds="station"][data-value="bar"]').click()
  assert page.locator('#ez-kds [data-kds="station"][data-value="bar"]').get_attribute("class").find("active")>=0
  assert page.evaluate("window.__kdsOriginal===document.querySelector('#ez-kds')")
  page.locator('#ez-kds [data-kds-filter="view"]').select_option("item")
  assert page.evaluate("window.__kdsOriginal===document.querySelector('#ez-kds')")
  page.locator('#ez-kds [data-kds="station"][data-value="all"]').click()
  page.goto(BASE+"/app?tab=settings",wait_until="domcontentloaded",timeout=15000)
  page.locator('.mobile-only [data-action="tab"]').first.wait_for(timeout=25000)
  more=page.locator('.mobile-only [data-action="tab"]').evaluate_all("(nodes)=>nodes.map(n=>n.dataset.value)")
  assert "operations" in more and "products" in more and "tables" in more,more
  assert "kitchen" not in more and "reservations" not in more,more
  print("PASS F&B mobile navigation, Front Desk name and KDS station/item controls",flush=True)

  # V6: actual browser modifier editor, independent size choices and POS total.
  page.goto(BASE+"/app?tab=products",wait_until="domcontentloaded",timeout=15000)
  page.locator('.product-card [data-action="edit-modifiers"]').first.wait_for(timeout=25000)
  page.locator('.product-card [data-action="edit-modifiers"]').first.click()
  page.locator("#ez-modifier-form").wait_for(timeout=15000)
  page.locator('[data-m6-action="add-size"]').click()
  page.locator('#ez-modifier-form [data-m6-option-index="1"] [data-m6-price]').fill("7000")
  page.locator('#ez-modifier-form [type="submit"]').click()
  page.locator("#ez-modifier-form").wait_for(state="detached",timeout=15000)
  page.goto(BASE+"/app?tab=orders",wait_until="domcontentloaded",timeout=15000)
  page.locator('[data-action="new-order"]').first.click()
  page.locator('#order-form .m6-pos-group').first.wait_for(timeout=15000)
  first=page.locator('#order-lines .order-line').first
  first.locator('[data-pos-modifier]').first.check()
  base_price=int(first.locator('select[name="product_id"] option:checked').get_attribute('data-price'))
  page.locator('[data-action="add-line"]').click()
  second=page.locator('#order-lines .order-line').nth(1)
  second.locator('[data-pos-modifier]').last.check()
  assert first.locator('[data-pos-modifier]').first.is_checked(), "Different order lines share one size-radio group"
  assert second.locator('[data-pos-modifier]').last.is_checked()
  assert page.locator('#order-total').inner_text().replace(".","").replace(",","").replace("đ","").strip()==str(base_price*2+7000)
  page.keyboard.press("Escape")
  print("PASS /app V6: editor saves sizes and POS keeps per-line modifiers and pricing",flush=True)
  page.goto(BASE+"/app?tab=orders",wait_until="domcontentloaded",timeout=15000)
  page.locator(".order-card").first.wait_for(timeout=25000)

  # Verify the ACTUAL computed Restaurant/Reservations button and panel palette
  # under all three merchant themes; catches green CSS rules leaked after Apple blue.
  page.evaluate("""() => {
    const div = document.createElement('div');
    div.className = 'suite-container';
    div.id = 'suite-palette-probe';
    div.innerHTML = '<button class="suite-primary">Add reservation</button>' +
      '<button class="suite-secondary">Refresh</button>' +
      '<div class="suite-summary"><div><strong>0</strong></div></div>' +
      '<div class="suite-booking-filters"><label>Date<input type="date"></label></div>';
    document.body.appendChild(div);
  }""")
  for theme, expected_bg, expected_text in (
    ("apple", "rgb(0, 102, 204)", "rgb(255, 255, 255)"),
    ("tropical", "rgb(13, 147, 107)", "rgb(255, 255, 255)"),
    ("graphite", "rgb(168, 207, 255)", "rgb(17, 24, 32)"),
  ):
   page.evaluate("(theme) => document.documentElement.setAttribute('data-ez-merchant-theme',theme)",theme)
   # Theme transitions take 200ms. Assert the settled palette, not the old animation frame.
   page.wait_for_function("""(expected) => getComputedStyle(
     document.querySelector('#suite-palette-probe .suite-primary')).backgroundColor === expected""",
     arg=expected_bg, timeout=3000)
   colors=page.evaluate("""() => {
     const button=document.querySelector('#suite-palette-probe .suite-primary');
     const card=document.querySelector('#suite-palette-probe .suite-summary>div');
     const input=document.querySelector('#suite-palette-probe input');
     return {
      button:getComputedStyle(button).backgroundColor,
      text:getComputedStyle(button).color,
      card:getComputedStyle(card).backgroundColor,
      field:getComputedStyle(input).backgroundColor
     };
   }""")
   assert colors["button"]==expected_bg,(theme,colors)
   assert colors["text"]==expected_text,(theme,colors)
   if theme=="graphite":
    assert colors["card"]!="rgb(255, 255, 255)",(theme,colors)
    assert colors["field"]!="rgb(255, 255, 255)",(theme,colors)
   else:
    assert colors["card"]=="rgb(255, 255, 255)",(theme,colors)
  page.locator('#suite-palette-probe').evaluate("(element)=>element.remove()")
  print("PASS /app: restaurant accent blue/green/blue in Apple/Tropical/Graphite; dark surfaces",flush=True)
  # A compact Fold/tablet rail must show the centered EZ monogram, not
  # crop a full-width EZ Thing wordmark (651..1120 CSS pixels).
  for width in (720, 840, 1000, 1120, 1121, 1280):
   page.set_viewport_size({"width":width,"height":800})
   expect_compact = width <= 1120
   page.evaluate("""theme => document.documentElement.dataset.ezMerchantTheme=theme""", "apple")
   dims=page.evaluate("""() => {
     const sidebar=document.querySelector('.sidebar');
     const link=sidebar?.querySelector('.merchant-home-link');
     const wordmark=link?.querySelector('.wordmark');
     const small=link?.querySelector('.sidebar-ez-icon-light');
     const box=(el)=>el?({
       left:el.getBoundingClientRect().left,
       right:el.getBoundingClientRect().right,
       top:el.getBoundingClientRect().top,
       width:el.getBoundingClientRect().width,
       height:el.getBoundingClientRect().height,
       display:getComputedStyle(el).display
     }):null;
     return {sidebar:box(sidebar),link:box(link),wordmark:box(wordmark),small:box(small)};
   }""")
   assert dims["sidebar"] and dims["link"],(width,dims)
   if expect_compact:
    assert dims["small"]["display"] != "none",(width,dims)
    assert dims["wordmark"]["display"] == "none",(width,dims)
    assert dims["small"]["width"] > 0,(width,dims)
    center=(dims["small"]["left"]+dims["small"]["right"])/2
    railcenter=(dims["sidebar"]["left"]+dims["sidebar"]["right"])/2
    assert abs(center-railcenter) <= 2,(width,dims)
    assert dims["small"]["left"] >= dims["sidebar"]["left"],(width,dims)
    assert dims["small"]["right"] <= dims["sidebar"]["right"],(width,dims)
   else:
    assert dims["small"]["display"] == "none",(width,dims)
    assert dims["wordmark"]["display"] != "none",(width,dims)
  page.set_viewport_size({"width":1000,"height":800})
  page.evaluate("""() => document.documentElement.dataset.ezMerchantTheme='graphite'""")
  assert page.locator('.sidebar .sidebar-ez-icon-dark').is_visible(), "Graphite compact logo must be visible"
  assert not page.locator('.sidebar .sidebar-ez-icon-light').is_visible(), "Incorrect light EZ mark in Graphite"
  print("PASS /app: centered compact EZ icon on Fold/tablet, full wordmark on desktop, Graphite contrast",flush=True)

  browser.close()
  print("REQUESTS",json.dumps(requests[-45:],ensure_ascii=False),flush=True)
  print("JS ERRORS",json.dumps(errors[-20:],ensure_ascii=False),flush=True)
  assert not errors,errors
finally:
 server.terminate()
 try:server.wait(timeout=5)
 except subprocess.TimeoutExpired:server.kill()
