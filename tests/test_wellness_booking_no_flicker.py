"""Regression guards against rebuilding the whole Wellness storefront on taps.

These static guards complement the real Chromium DOM-identity assertions in
tests/live_demo_browser.py.
"""
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def booking_js():
    return (STATIC / "customer.js").read_text(encoding="utf-8")


def test_wellness_booking_only_updates_scoped_widget():
    source = booking_js()
    widget = source.split("function updateBookingView(", 1)[1].split("function bookingForm(", 1)[0]
    assert "root.querySelector('.booking-layout')" in widget
    assert "booking.querySelector('.booking-slots')" in widget
    assert "booking.querySelectorAll('.booking-service')" in widget
    assert "layout()" not in widget
    assert "root.innerHTML" not in widget
    assert "window.scrollTo" not in widget


def test_slot_selection_does_not_destroy_the_dom():
    source = booking_js()
    actions = source.split("document.addEventListener('click',e=>{const el=", 1)[1]
    service_slot = actions.split("if(action==='open-cart')", 1)[1].split("if(action==='open-booking')", 1)[0]
    assert "if(!st.slots.includes(value))return" in service_slot
    assert "updateBookingView()" in service_slot
    assert "layout()" not in service_slot
    assert "window.scrollTo" not in service_slot


def test_concurrent_slot_queries_only_apply_the_latest_selection():
    source = booking_js()
    slots = source.split("async function slots(){", 1)[1].split("function bookingForm(", 1)[0]
    assert "const requestId=++slotRequestId" in slots
    assert "if(requestId!==slotRequestId)return" in slots
    assert "if(requestId===slotRequestId)" in slots
    assert "updateBookingView(true)" in slots
    assert "layout()" not in slots


def test_inputs_and_translations_remain_stable():
    source = booking_js()
    html = (STATIC / "customer.html").read_text(encoding="utf-8")
    assert 'id="book-date"' in source
    assert 'id="book-staff"' in source
    assert 'aria-pressed="${x===st.slot}"' in source
    assert 'aria-live="polite"' in source
    assert 'customer.js?v=20261114-wellness-stable-01' in html
