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
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "order-table-wrap" in js and "orders-table" in js
    assert 'role="region" aria-label="Danh sách đơn hàng"' in js
    for label in ("Mã đơn", "Sản phẩm", "Thời gian", "Giá trị", "Trạng thái", "Thao tác"):
        assert f'data-label-vi="{label}"' in js
    for label in ("Order ID", "Products", "Time", "Amount", "Status", "Action"):
        assert f'data-label-en="{label}"' in js
    assert "data-action=\"confirm-paid\"" in js
    assert "data-action=\"new-order\"" in js
    assert "function ordersTab()" in js
    assert "function tablesTab()" in js


def test_tablet_navigation_keeps_accessible_names():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "merchant-responsive.css").read_text(encoding="utf-8")
    assert 'aria-label="${E(name)}"' in js
    assert 'title="${E(name)}"' in js
    assert 'class="side-label"' in js
    assert ".side-link .side-label{display:none}" in css
    assert '.merchant-customer-link" href=' in js
    assert "aria-label=\"Xem frontend khách hàng\"" in js
