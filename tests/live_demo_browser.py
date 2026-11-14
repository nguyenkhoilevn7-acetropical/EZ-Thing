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
  browser.close()
  print("REQUESTS",json.dumps(requests[-45:],ensure_ascii=False),flush=True)
  print("JS ERRORS",json.dumps(errors[-20:],ensure_ascii=False),flush=True)
  assert not errors,errors
finally:
 server.terminate()
 try:server.wait(timeout=5)
 except subprocess.TimeoutExpired:server.kill()
