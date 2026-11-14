"""Regression tests for complete bilingual UI across public pricing and reservation pages."""
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

import pytest

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
ASSET = (STATIC / "i18n.js").read_text(encoding="utf-8")

ENTRY = re.compile(r"""\[\s*(['"])((?:\\.|(?!\1)[\s\S])*?)\1\s*,\s*(['"])((?:\\.|(?!\3)[\s\S])*?)\3\s*\]""")
KNOWN = {m.group(2) for m in ENTRY.finditer(ASSET)}
VI = re.compile(r"[À-ỹĐđ]")
DECOR = re.compile(r"^(?:[✓✔☑•◈✧◎◷◌↗↻←→+★☆✳✦🔒]\s+)*")
TRAIL = re.compile(r"\s+[↗→←]$")


class PageStrings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.strings = []
        self.attrs = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        for name, val in attrs:
            if name in {"title", "alt", "placeholder", "aria-label"} and val:
                self.attrs.append(val.strip())

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, value):
        if not self.hidden and value.strip():
            self.strings.append(value.strip())


def supported(text):
    if not VI.search(text):
        return True
    if text in KNOWN:
        return True
    cleaned = TRAIL.sub("", DECOR.sub("", text))
    if cleaned in KNOWN:
        return True
    # VND prices remain in their source currency; numeric counts are localized.
    if re.fullmatch(r"[\d.,]+đ", cleaned):
        return True
    if re.fullmatch(r"\d+\s+(khách|phút)", cleaned):
        return True
    return False


@pytest.mark.parametrize("name", [
    "public.html",
    "reservation-public.html",
    "reservation-admin.html",
    "brand-editor.html",
    "storefront-owner-preview.html",
])
def test_public_ui_static_text_and_accessible_labels_have_translations(name):
    page = PageStrings()
    page.feed((STATIC / name).read_text(encoding="utf-8"))
    missing = [s for s in page.strings + page.attrs if not supported(s)]
    assert not missing, f"Missing English UI strings in {name}: {missing}"


@pytest.mark.parametrize("name,script", [
    ("reservation-public.html", "reservations.js"),
    ("reservation-admin.html", "reservations.js"),
    ("public.html", "premium.js"),
    ("brand-editor.html", "brand-editor.js"),
    ("storefront-owner-preview.html", "storefront-owner-preview.js"),
])
def test_language_script_loaded_before_page_script(name, script):
    html = (STATIC / name).read_text(encoding="utf-8")
    assert "/assets/i18n.js" in html
    assert "/assets/i18n.css" in html
    assert html.index("i18n.js") < html.index(script)


def test_booking_api_sends_selected_language_and_formats_timestamps_locally():
    js = (STATIC / "reservations.js").read_text(encoding="utf-8")
    assert "'Accept-Language':window.EZI18N?.language()||'vi'" in js
    assert "toLocaleString(window.EZI18N?.locale()||'vi-VN'" in js
    assert "window.EZI18N?.translate('Xác nhận chuyển trạng thái lịch đặt bàn?')" in js


def test_translation_engine_preserves_glyphs_and_language_toggle():
    if not shutil.which("node"):
        pytest.skip("Node is not installed; static translation completeness is still verified")
    harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
function instance(lang) {
  const win = {};
  const doc = {
    readyState: 'loading',
    title: 'EZ Thing — Mọi thứ kinh doanh, đơn giản hơn.',
    cookie: '',
    addEventListener: () => {},
  };
  vm.runInNewContext(source, {
    window: win,
    document: doc,
    navigator: {language: lang === 'en' ? 'en-US' : 'vi-VN'},
    localStorage: {getItem: () => lang},
  });
  return win.EZI18N;
}
const en = instance('en');
const vi = instance('vi');
const tests = [
  ['✓ Tất cả quyền BASIC', '✓ Everything in BASIC'],
  ['✓ Banner và logo bằng link ảnh hợp lệ', '✓ Banner and logo via approved image URLs'],
  ['✓ 3 kiểu bố cục trang khách', '✓ Three storefront layouts'],
  ['✓ Thông điệp chân trang, tối đa 10 chi nhánh', '✓ Custom footer and up to 10 branches'],
  ['Khu quản lý ↗', 'Merchant workspace ↗'],
  ['Khám phá thực đơn →', 'Explore menu →'],
  ['◷ Đặt trước 30 phút', '◷ Book at least 30 minutes ahead'],
  ['↻ Cập nhật', '↻ Refresh'],
  ['2 khách', '2 guests'],
  ['90 phút', '90 minutes'],
  ['12 bàn phù hợp', '12 suitable tables'],
  ['Đặt bàn | EZ Thing Cafe', 'Table reservations | EZ Thing Cafe'],
  ['Cà phê Nguyễn', 'Cà phê Nguyễn'],
  ['249.000đ', '249.000đ'],
];
for (const [sourceText, expected] of tests) {
  const actual = en.translate(sourceText);
  if (actual !== expected) throw Error(JSON.stringify({sourceText, expected, actual}));
  if (vi.translate(sourceText) !== sourceText) {
    throw Error('VI mode modified source text: ' + sourceText);
  }
}
console.log('PASS ' + tests.length + ' in-browser translation cases');
"""
    result = subprocess.run(
        ["node", "-e", harness, str(STATIC / "i18n.js")],
        check=False, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
