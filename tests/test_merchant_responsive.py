"""Responsive merchant UI regression checks for narrow tablets and foldable devices.

Static contracts guard layout/accessibility changes; visual browser QA remains required.
"""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_merchant_adaptive_styles_loaded_after_main_css():
    markup = (STATIC / "index.html").read_text(encoding="utf-8")
    assert markup.index("/assets/styles.css") < markup.index("/assets/merchant-responsive.css")
    css = (STATIC / "merchant-responsive.css").read_text(encoding="utf-8")
    assert "@media (min-width:651px) and (max-width:1120px)" in css
    assert "@media (min-width:651px) and (max-width:1250px)" in css
    assert "@media (max-width:650px)" in css
    assert "container-name:order-table" in css
    assert "@container order-table (max-width:850px)" in css
    assert ".sidebar{overflow-y:auto" in css
    assert css.count("{") == css.count("}")


def test_order_cards_preserve_status_actions_and_full_labels():
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    cards = (STATIC / "order-cards.js").read_text(encoding="utf-8")
    styles = (STATIC / "order-cards.css").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "window.EZOrderCards.renderList(list,{E,V,D,status,I})" in app
    assert "order-rows" in cards and "data-match" in cards
    assert "role='listitem'" in cards and "role='region'" in cards
    for name in ("Mã đơn", "Sản phẩm", "Giá trị", "Danh sách đơn hàng"):
        assert name in cards
    for action in ("order-detail", "confirm-paid", "cancel-order"):
        assert "data-action='" + action + "'" in cards
    assert "o.status === 'open'" in cards
    assert "order-card-list" in styles and "@container ez-order-cards" in styles
    assert 'data-ez-merchant-theme="graphite"' in styles
    assert html.index("order-cards.js") < html.index("/assets/app.js")
    assert html.index("merchant-palette-refinement.css") < html.index("order-cards.css")
    assert "data-action=\"new-order\"" in app
    assert "function ordersTab()" in app
    assert "function tablesTab()" in app


def test_tablet_navigation_keeps_accessible_names():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "merchant-responsive.css").read_text(encoding="utf-8")
    assert 'aria-label="${E(name)}"' in js
    assert 'title="${E(name)}"' in js
    assert 'class="side-label"' in js
    assert ".side-link .side-label{display:none}" in css
    assert 'class="merchant-customer-link" href=' in js
    assert "aria-label=\"Xem frontend khách hàng\"" in js
