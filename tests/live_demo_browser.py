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
  assert values==["overview","pos","orders","kitchen","settings"], values
  page.goto(BASE+"/app?tab=kitchen",wait_until="domcontentloaded",timeout=15000)
  page.locator("#ez-kds .kds-station").first.wait_for(timeout=25000)
  assert page.locator("#ez-kds .kds-station").count()==5
  assert page.locator("#ez-kds #kds-live").inner_text().strip()
  # Configuration must be visible to the owner, and saving a category rule
  # should not rebuild the KDS shell or cause horizontal overflow.
  page.locator("#ez-kds-routing .ezroute-panel").wait_for(timeout=15000)
  page.locator("#ez-kds-routing .ezroute-panel>summary").click()
  assert page.locator("#ez-kds-routing [data-ezroute-form='settings']").is_visible()
  assert page.locator("#ez-kds-routing [name='auto_dispatch']").is_checked()
  cat_form=page.locator("#ez-kds-routing [data-ezroute-form='category']")
  page.wait_for_function("""() => !!document.querySelector(
    '#ez-kds-routing [data-ezroute-form="category"] [name="category"] option'
  )""",timeout=15000)
  current_category=cat_form.locator('[name="category"] option').first.inner_text()
  cat_form.locator('[name="category"]').select_option(index=0)
  cat_form.locator('[name="station"]').select_option("bar")
  cat_form.locator('[type="submit"]').click()
  page.locator("#ez-kds-routing .ezroute-badge").first.wait_for(timeout=12000)
  assert current_category.casefold() in page.locator("#ez-kds-routing .ezroute-summaries").inner_text().casefold()
  assert page.locator("#ez-kds-routing [data-ezroute-form='product'] [name='station'] option[value='skip']").count()==1
  assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
  print("PASS KDS routing UI: auto enabled and category mapping persisted",flush=True)
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
  assert "kitchen" not in more and "pos" not in more and "reservations" in more,more
  print("PASS F&B mobile navigation, Front Desk name and KDS station/item controls",flush=True)

  # V6 options are still managed in Product Settings, but actual sale
  # occurs in the full Quick Register instead of the legacy form dialog.
  page.goto(BASE+"/app?tab=products",wait_until="domcontentloaded",timeout=15000)
  edit_button=page.locator('.product-card [data-action="edit-modifiers"]').first
  edit_button.wait_for(timeout=25000)
  modifier_pid=edit_button.get_attribute("data-value")
  edit_button.click()
  page.locator("#ez-modifier-form").wait_for(timeout=15000)
  page.locator('[data-m6-action="add-size"]').click()
  page.locator('#ez-modifier-form [data-m6-option-index="1"] [data-m6-price]').fill("7000")
  page.locator('#ez-modifier-form [type="submit"]').click()
  page.locator("#ez-modifier-form").wait_for(state="detached",timeout=15000)

  page.goto(BASE+"/app?tab=orders",wait_until="domcontentloaded",timeout=15000)
  page.locator(".order-card").first.wait_for(timeout=25000)
  page.locator('[data-action="new-order"]').first.click()
  page.locator("#ez-register .ezreg-product").first.wait_for(timeout=15000)
  assert page.locator("#order-form").count()==0,"Legacy create-order modal remained in use"
  page.locator('.ezreg-product[data-value="'+modifier_pid+'"]').click()
  page.locator(".ezreg-option-dialog").wait_for(timeout=15000)
  assert not page.locator('[data-ezreg="option-save"]').is_enabled(), "Required size could be skipped"
  page.locator('.ezreg-option-group[data-min="1"] .ezreg-option').first.click()
  assert page.locator('[data-ezreg="option-save"]').is_enabled()
  page.locator('[data-ezreg="option-save"]').click()
  assert page.locator(".ezreg-cart-line").count()==1
  first_price=page.locator('.ezreg-cart-line .ezreg-line-side strong').first.inner_text()

  page.locator('.ezreg-product[data-value="'+modifier_pid+'"]').click()
  page.locator(".ezreg-option-dialog").wait_for(timeout=15000)
  page.locator('.ezreg-option-group[data-min="1"] .ezreg-option').last.click()
  page.locator('[data-ezreg="option-save"]').click()
  assert page.locator(".ezreg-cart-line").count()==2, "Different modifier variants collapsed"
  assert page.locator(".ezreg-cart-line .ezreg-line-side strong").first.inner_text()==first_price
  # At 412px the cart is intentionally a closed bottom sheet until opened.
  page.locator('[data-ezreg="cart-toggle"]').click()
  assert page.locator("#ezreg-cart.mobile-open").is_visible()
  page.locator('.ezreg-cart-line').first.locator('[data-ezreg="increase"]').click()
  page.locator('[data-ezreg="cart-close"]').first.click()
  assert page.locator(".ezreg-cart-line").first.locator(".ezreg-line-actions b").inner_text()=="2"
  assert page.locator(".ezreg-subtotal strong").inner_text().strip()
  print("PASS register: required Size validation, 2 variants, quantity, backend price preview",flush=True)

  # Chrome viewport checks on phones/tablets/desktops, including Graphite.
  for width in (360,412,720,1040,1440):
   page.set_viewport_size({"width":width,"height":880})
   overflow=page.evaluate("""() => ({
      scroll:document.documentElement.scrollWidth,inner:window.innerWidth,
      visible:!!document.querySelector('#ez-register .ezreg-product')
   })""")
   assert overflow["visible"] and overflow["scroll"]<=overflow["inner"]+2,(width,overflow)
   if width<=1040:
    page.locator('[data-ezreg="cart-toggle"]').click()
    assert page.locator("#ezreg-cart.mobile-open").is_visible()
    page.locator('[data-ezreg="cart-close"]').first.click()
   if width==412:
    page.evaluate("document.documentElement.setAttribute('data-ez-merchant-theme','graphite')")
    bg=page.locator(".ezreg-catalog").evaluate("(el)=>getComputedStyle(el).backgroundColor")
    assert bg!="rgb(255, 255, 255)",bg
  page.set_viewport_size({"width":1280,"height":800})
  page.evaluate("document.documentElement.setAttribute('data-ez-merchant-theme','apple')")
  page.locator('[data-ezreg="create"]').click()
  page.locator(".ezreg-last").wait_for(timeout=25000)
  assert page.locator(".ezreg-cart-line").count()==0
  assert page.locator(".ezreg-last").inner_text().strip()
  assert page.locator(".ezreg-last-actions [data-ezreg='paid']").count()==1
  print("PASS /app POS: responsive checkout, persisted order, no browser errors",flush=True)

  # Existing saved checks now enter the full payment flow, never one-click paid.
  page.locator('.ezreg-last-actions [data-ezreg="paid"]').click()
  page.locator("#ezpay-title").wait_for(timeout=8000)
  assert page.locator('[data-ezpay="method"][data-value="cash"]').count()==1
  assert not page.locator('.ezpay-methods button[disabled]').is_enabled()
  assert not page.locator("#ezpay-submit").is_enabled()
  assert page.locator('[data-ezpay-cash]').input_value()
  page.locator('[data-ezpay-cash]').fill("500000")
  assert page.locator("#ezpay-change-amount").inner_text().strip()
  page.locator('[data-ezpay-confirm]').check()
  assert page.locator("#ezpay-submit").is_enabled()
  page.locator("#ezpay-submit").click()
  page.locator(".ezpay-modal").wait_for(state="detached",timeout=25000)
  assert page.locator(".ezreg-last").inner_text().strip()
  page.locator(".ezreg-last-actions [data-ezreg='paid']").wait_for(state="detached",timeout=15000)
  print("PASS POS cash: saved check, tendered amount, change and manual confirmation",flush=True)

  # A new order can be created and manually confirmed as bank transfer
  # from the same register, without claiming banking gateway verification.
  page.locator('.ezreg-product').nth(1).click()
  page.locator('.ezreg-cart-line').first.wait_for(timeout=8000)
  page.locator('[data-ezreg="checkout"]').click()
  page.locator("#ezpay-title").wait_for(timeout=8000)
  page.locator('[data-ezpay="method"][data-value="bank_transfer"]').click()
  assert not page.locator("#ezpay-submit").is_enabled()
  assert "bank" in page.locator('.ezpay-bank').inner_text().lower() or "ngân hàng" in page.locator('.ezpay-bank').inner_text().lower()
  page.locator('[data-ezpay-reference]').fill("BANK-REVIEW-123")
  page.locator('[data-ezpay-confirm]').check()
  page.locator("#ezpay-submit").click()
  page.locator(".ezpay-modal").wait_for(state="detached",timeout=25000)
  assert page.locator('.ezreg-cart-line').count()==0
  print("PASS POS bank: new order then explicit manually recorded transfer, no gateway",flush=True)

  # Phone: payment drawer remains readable and never forces page horizontal scroll.
  page.set_viewport_size({"width":412,"height":915})
  page.locator('.ezreg-product').nth(1).click()
  page.locator('[data-ezreg="cart-toggle"]').click()
  page.locator('[data-ezreg="checkout"]').click()
  assert page.locator('.ezpay-modal').is_visible()
  page.locator('[data-ezpay="close"]').last.click()
  assert page.locator('.ezpay-modal').count()==0
  size=page.evaluate("""() => ({document:document.documentElement.scrollWidth,
                              viewport:window.innerWidth})""")
  assert size["document"]<=size["viewport"]+2,size
  print("PASS POS mobile cashier checkout and no horizontal overflow",flush=True)

  page.set_viewport_size({"width":1280,"height":800})


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

  # Owner previews five REAL task screens under the same admin session.
  # Preview never fires an order, payment or kitchen status mutation.
  page.set_viewport_size({"width":1280,"height":850})
  page.goto(BASE+"/app?tab=team",wait_until="domcontentloaded",timeout=15000)
  page.locator('[data-ezws="preview-picker"]').first.wait_for(timeout=15000)
  page.locator('[data-ezws="preview-picker"]').first.click()
  page.locator('.ezws-preview-choice[data-value="order"]').click()
  page.locator('.ezws-preview-bar').wait_for(timeout=15000)
  assert page.locator("#ez-register").is_visible()
  assert page.evaluate("document.body.dataset.ezWorkstationPreview")== "true"
  assert page.locator('.ezreg-product:not([disabled])').first.evaluate("(el)=>getComputedStyle(el).pointerEvents")=="auto"
  assert page.locator('#ez-register [data-ezreg="checkout"]').count()==1, "Owner preview should demonstrate checkout; actual staff duty remains restricted"
  for width in (412,720,820,1000,1280):
   page.set_viewport_size({"width":width,"height":860})
   # Changing viewport size can preserve the old document scroll offset.
   # Test initial workstation view from the top, not an intentionally scrolled queue.
   page.evaluate("""() => {
     window.scrollTo(0,0);
     document.scrollingElement.scrollTop=0;
     for(const n of document.querySelectorAll('.app>.main,.app .content'))n.scrollTop=0;
   }""")
   page.wait_for_function("""() => {
     const bar=document.querySelector('.ezws-preview-bar');
     return bar && Math.abs(parseFloat(getComputedStyle(document.body)
       .getPropertyValue('--ezws-preview-header-h'))-bar.getBoundingClientRect().height)<3
   }""",timeout=8000)
   layout=page.evaluate("""() => {
     const r=s=>document.querySelector(s)?.getBoundingClientRect();
     const bar=r('.ezws-preview-bar'),header=r('.ezreg-header'),cat=r('.ezreg-catalog');
     const content=r('.app .content'),cart=document.querySelector('.ezreg-cart');
     return {view:innerWidth,barBottom:bar.bottom,headTop:header.top,
       scrollY:scrollY,contentTop:content.top,contentPad:getComputedStyle(document.querySelector('.app .content')).paddingTop,
       catWidth:cat.width,contentWidth:content.width,
       cartDisplay:getComputedStyle(cart).display,
       documentWidth:document.documentElement.scrollWidth};
   }""")
   assert layout["documentWidth"]<=width+2,(width,layout)
   assert layout["headTop"]>=layout["barBottom"]-3,(width,layout)
   if width<700:
    # Narrow phones retain the sheet; left/right switch must not appear inert.
    assert layout["catWidth"]>=layout["contentWidth"]*.88,(width,layout)
    assert layout["cartDisplay"]=="none",(width,layout)
    assert not page.locator('[data-ezreg="flip-ticket"]').is_visible()
   else:
    # Landscape Fold/tablet/terminal: both catalog and receipt are ALWAYS visible.
    assert layout["catWidth"]>=layout["contentWidth"]*.48,(width,layout)
    assert layout["cartDisplay"]=="flex",(width,layout)
    assert not page.locator('.ezreg-mobile-cartbar').is_visible(),(width,layout)
    bounds=page.evaluate("""() => {
      const a=document.querySelector('.ezreg-catalog').getBoundingClientRect();
      const b=document.querySelector('.ezreg-cart').getBoundingClientRect();
      return {catalog:{left:a.left,right:a.right},cart:{left:b.left,right:b.right}}
    }""")
    assert (bounds["cart"]["left"]>=bounds["catalog"]["right"]-3 or
            bounds["cart"]["right"]<=bounds["catalog"]["left"]+3),(width,bounds)
   if width==820:
    # Verify DOM geometry, not only class state: the user-reported switch
    # previously changed state without any visible rearrangement.
    before=page.evaluate("""() => {
      const cat=document.querySelector('.ezreg-catalog').getBoundingClientRect();
      const cart=document.querySelector('.ezreg-cart').getBoundingClientRect();
      return cart.left<cat.left
    }""")
    page.locator('[data-ezreg="flip-ticket"]').click()
    after=page.evaluate("""() => {
      const cat=document.querySelector('.ezreg-catalog').getBoundingClientRect();
      const cart=document.querySelector('.ezreg-cart').getBoundingClientRect();
      return cart.left<cat.left
    }""")
    assert before != after,"Đổi bên must change actual receipt side at 820px"
    page.locator('[data-ezreg="flip-ticket"]').click()
  page.set_viewport_size({"width":1280,"height":850})
  print("PASS POS workstation: phone sheet, split panels at 720/820/1000/1280, live receipt flip",flush=True)
  # In-sandbox clicks must trigger the normal product, modifier, cart and save
  # flows. The virtual API catches ALL writes before network I/O.
  preview_start=len(requests)
  # Prior checkout smoke may exhaust the configured modifier product.
  # Interactive preview must respect stock and select a sellable item.
  page.locator('.ezreg-product:not([disabled])').first.click()
  if page.locator('.ezreg-option-dialog').count():
   # Screenshot regression: readable modifiers and 52px+ touch quantity targets.
   pop=page.locator('.ezreg-option-dialog')
   metrics=pop.evaluate("""el => {
     const choice=el.querySelector('.ezreg-option'),
       qty=el.querySelector('.ezreg-option-qty button'),
       head=el.querySelector('.ezreg-option-title h3');
     return {choiceFont:parseFloat(getComputedStyle(choice).fontSize),
       qtyWidth:qty.getBoundingClientRect().width,
       titleFont:parseFloat(getComputedStyle(head).fontSize)};
   }""")
   assert metrics["choiceFont"]>=15 and metrics["qtyWidth"]>=52 and metrics["titleFont"]>=22,metrics
   groups=page.locator('.ezreg-option-group[data-min="1"]')
   for index in range(groups.count()):
    groups.nth(index).locator('.ezreg-option').first.click()
   page.locator('[data-ezreg="option-save"]').click()
  page.locator('.ezreg-cart-line').first.wait_for(timeout=10000)
  for width in (412,820):
   page.set_viewport_size({"width":width,"height":900})
   if width<700:
    page.locator('.ezreg-mobile-cartbar').click()
    page.locator('#ezreg-cart.mobile-open').wait_for(timeout=8000)
   else:
    # At tablet width the receipt is visible without a popup.
    assert not page.locator('.ezreg-mobile-cartbar').is_visible()
    assert page.locator('#ezreg-cart').is_visible()
   layout=page.evaluate("""() => {
     const cart=document.querySelector('#ezreg-cart'),act=cart.querySelector('[data-ezreg="checkout"]'),
       r=cart.getBoundingClientRect(),a=act.getBoundingClientRect(),
       footer=cart.querySelector('.ezreg-cart-footer').getBoundingClientRect();
     return {width:innerWidth,cartX:r.left,cartRight:r.right,cartBottom:r.bottom,
       buttonBottom:a.bottom,buttonVisible:getComputedStyle(act).display!='none',
       footerBottom:footer.bottom};
   }""")
   assert layout["cartX"]>=-2 and layout["cartRight"]<=width+2,layout
   if width<700:
    assert abs((layout["cartX"]+layout["cartRight"])/2-width/2)<4,layout
   assert layout["cartBottom"]<=901 and layout["buttonBottom"]<=901,layout
   assert layout["buttonVisible"],layout
   assert layout["footerBottom"]<=901,layout
   if width<700:
    page.locator('#ezreg-cart [data-ezreg="cart-close"]').click()
  page.set_viewport_size({"width":1280,"height":850})
  print("PASS POS cart: phone popup at 412px, persistent ticket at 820px, checkout footer visible",flush=True)
  page.locator('.ezreg-cart [data-ezreg="create"]').click()
  page.locator('.ezreg-last').wait_for(timeout=10000)
  virtual_order=page.locator('.ezreg-last strong').first.inner_text()
  assert "Đơn" in virtual_order or "Order" in virtual_order, virtual_order
  print("PASS preview sandbox: clickable product, variants, cart and simulated order",flush=True)
  for task,selector in (
    ("kitchen","#ez-kds"),("bar","#ez-kds"),
    ("cashier",".ezrole-task"),("host","#ezhost-workspace"),
    ("order","#ez-register")
  ):
   page.locator('.ezws-preview-tabs [data-value="'+task+'"]').click()
   page.locator(selector).wait_for(timeout=15000)
   assert page.locator('.ezws-preview-tabs [data-value="'+task+'"]').get_attribute("aria-pressed")=="true"
   assert page.evaluate("document.body.dataset.ezWorkstationPreview")=="true"
   if task in ("bar","kitchen"):
    assert page.locator('.kds-act-recall').count()==0,"Staff KDS preview must hide manager-only actions"
    page.wait_for_function("""() => {
      const t=document.querySelector('.ezws-preview-bar')?.getBoundingClientRect();
      const h=document.querySelector('.kds-head')?.getBoundingClientRect();
      return t && h && h.top>=t.bottom-3
    }""",timeout=8000)
   if task=="host":
    page.locator('.ezhost-room-kpi').first.wait_for(timeout=15000)
    page.locator('.ezhost-room-table').first.wait_for(timeout=15000)
    assert page.locator('.ezhost-room-kpi').count()==4
    assert page.locator('.ezhost-room-table').count()>=3
    first=page.locator('[data-ezhost-action="seat"]').first
    first.click()
    page.locator('.ezhost-seat-form').wait_for(timeout=10000)
    confirm=page.locator('#modal-root .ezhost-confirm')
    assert confirm.count()==1 and confirm.is_visible(), "Host seat confirm CTA is missing"
    assert any(x in confirm.inner_text() for x in ("Xác nhận","Confirm")),confirm.inner_text()
    # The modal is outside .ezhost-room; its button must retain blue contrast.
    style=confirm.evaluate("""el => ({
       bg:getComputedStyle(el).backgroundColor,
       color:getComputedStyle(el).color,
       display:getComputedStyle(el).display,
       width:el.getBoundingClientRect().width
    })""")
    assert style["bg"] not in ("rgba(0, 0, 0, 0)","rgb(255, 255, 255)"),style
    assert style["width"]>150,style
    page.set_viewport_size({"width":412,"height":850})
    assert confirm.is_visible(), "Mobile modal confirm CTA must be visible"
    capacity=int(page.locator('.ezhost-seat-form [name="guest_count"]').get_attribute("max"))
    page.locator('[data-ezhost-step="1"]').click()
    assert page.locator('.ezhost-seat-form [name="guest_count"]').input_value()==str(min(2,capacity))
    page.locator('.ezhost-seat-form [name="guest_count"]').fill(str(min(3,capacity)))
    page.locator('.ezhost-seat-form [name="guest_name"]').fill("Khách thử")
    confirm.click()
    page.locator('.ezhost-seat-success').wait_for(timeout=12000)
    assert any(x in page.locator('.ezhost-seat-success').inner_text() for x in ("Đang phục vụ","occupied"))
    assert page.locator('.ezhost-room-table.busy').count()>=1
    assert "Khách thử" in page.locator('.ezhost-room-table.busy').first.inner_text()
    page.locator('.ezhost-seat-success [data-ezhost-action="dismiss"]').click()
    assert page.locator('.ezhost-room-kpi.occupied strong').inner_text().strip()
    page.set_viewport_size({"width":1280,"height":850})
    page.locator('[data-ezhost-tab="bookings"]').click()
    page.locator('[data-ezhost-action="book"]').wait_for(timeout=12000)
    page.locator('[data-ezhost-tab="floor"]').click()
    page.locator('.ezhost-room-map').wait_for(timeout=12000)
    assert page.locator('[data-ezhost-placement]').count()>=3
    page.locator('[data-ezhost-tab="tables"]').click()
   if task=="bar":
    page.locator('.kds-ticket').first.wait_for(timeout=10000)
    btn=page.locator('.kds-ticket [data-kds="status"][data-status="preparing"]').first
    btn.wait_for(timeout=10000)
    btn.click()
    page.locator('.kds-ticket .kds-chip-preparing').first.wait_for(timeout=10000)
   if task=="cashier":
    page.locator('.ezrole-order-card').first.wait_for(timeout=10000)
    page.locator('.ezrole-order-card [data-action="confirm-paid"]').first.click()
    page.locator('.ezpay-modal').wait_for(timeout=10000)
    page.locator('[data-ezpay-confirm]').check()
    page.locator('[data-ezpay="confirm"]').click()
    page.locator('.ezpay-modal').wait_for(state="detached",timeout=10000)
  assert not [r for r in requests[preview_start:]
              if r.startswith("> POST /api/businesses/") or
                 r.startswith("> PATCH /api/businesses/") or
                 r.startswith("> PUT /api/businesses/") or
                 r.startswith("> DELETE /api/businesses/")], "Preview caused real tenant mutation"
  print("PASS preview sandbox: Bar status, cashier payment and Host occupancy; zero business mutation requests",flush=True)
  page.set_viewport_size({"width":412,"height":850})
  assert page.locator(".ezws-preview-exit").is_visible()
  assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2")
  page.locator('.ezws-preview-exit').click()
  page.locator('.ezws-preview-bar').wait_for(state="detached",timeout=12000)
  assert page.evaluate("document.body.dataset.ezWorkstationPreview")=="false"
  print("PASS workstation owner preview: Order/Kitchen/Bar/Cashier/Host, mobile and read-only",flush=True)

  browser.close()
  print("REQUESTS",json.dumps(requests[-45:],ensure_ascii=False),flush=True)
  print("JS ERRORS",json.dumps(errors[-20:],ensure_ascii=False),flush=True)
  assert not errors,errors
finally:
 server.terminate()
 try:server.wait(timeout=5)
 except subprocess.TimeoutExpired:server.kill()
