"""Regression checks from the 2026-11-15 full frontend audit (logo, mobile, i18n, navigation)."""
import json
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
WORDMARK = "/assets/icons/ez-thing-wordmark-light.svg"
FAVICON = 'href="/assets/icons/ez-mark-light.svg'


def read(name):
    return (STATIC / name).read_text(encoding="utf-8")


def test_every_html_entrypoint_has_the_ez_favicon():
    for page in STATIC.glob("*.html"):
        assert FAVICON in page.read_text(encoding="utf-8"), page.name


def test_old_e_dot_mark_is_gone_everywhere():
    for path in list(STATIC.glob("*.html")) + list(STATIC.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        assert '<span class="brand-mark">e.</span>' not in text, path.name
        assert '<b>e.</b>' not in text, path.name
        assert '<span class="mark">e.</span>' not in text, path.name


def test_wordmark_on_reservations_brand_studio_and_demo_storefronts():
    for name in ("reservation-public.html", "reservation-admin.html", "brand-editor.html"):
        html = read(name)
        assert WORDMARK in html, name
        assert "brand-logo.css" in html, name
    customer = read("customer.js")
    assert customer.count('class="ez-full-logo customer-ez-logo"') == 2


def test_merchant_and_admin_show_wordmark_on_mobile():
    assert 'class="merchant-mobile-brand"' in read("app.js")
    assert 'class="admin-mobile-brand"' in read("admin.js")
    css = read("brand-logo.css")
    assert "@media(max-width:650px){.merchant-mobile-brand{display:inline-flex" in css
    assert "@media(max-width:780px){.admin-mobile-brand{display:inline-flex" in css


def test_mobile_only_settings_card_is_a_block():
    css = read("styles.css")
    assert ".mobile-only{display:block}" in css
    assert ".mobile-only{display:initial}" not in css


def test_account_lock_tab_only_when_payment_is_required():
    js = read("app.js")
    assert "if(id==='account_lock')return false;" in js


def test_order_table_filter_only_for_businesses_with_tables():
    assert "${has('tables')?`<label>Bàn<select data-order-filter=\"table\">" in read("app.js")


def test_english_patterns_translate_dynamic_merchant_copy():
    harness = r"""
const fs=require('fs');const src=fs.readFileSync(process.argv[1],'utf8');
const store={ezthing_language:'en'};
global.localStorage={getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v};
global.navigator={language:'en-US'};
global.document={cookie:'',title:'',readyState:'complete',documentElement:{dataset:{}},body:null,
 addEventListener(){},querySelector(){return null},querySelectorAll(){return []},dispatchEvent(){}};
global.window={setTimeout,addEventListener(){}};global.MutationObserver=class{observe(){}};
global.CustomEvent=class{};
try{eval(src)}catch(e){}
const t=window.EZI18N.translate;
console.log(JSON.stringify(['Đơn mở 120 phút','MATCHA · Đang có hàng','4 chỗ','2 công việc','Tồn kho: 7','Chờ xử lý','Bàn'].map(t)));
"""
    out = subprocess.run(["node", "-e", harness, str(STATIC / "i18n.js")],
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["Open for 120 minutes", "MATCHA · In stock", "4 seats",
                               "2 tasks", "Stock: 7", "Pending", "Table"]


def test_changed_scripts_are_cache_busted():
    from app.asset_pipeline import STATIC_ASSETS
    for entry in STATIC.glob("*.html"):
        source = read(entry.name)
        rendered = STATIC_ASSETS.page(entry.name).body.decode("utf-8")
        assert "?v=" not in rendered, entry.name
        for path in ("app.js", "admin.js", "customer.js", "i18n.js"):
            public = "/assets/" + path
            if public in source:
                assert public + "?h=" + STATIC_ASSETS.hashes[public] in rendered, entry.name
    assert "ezthing-shell-__EZ_CONTENT_HASH__" in read("sw.js")
