"""Tests for the scoped F&B reservation and contact workflows."""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(__file__).parent / 'reservation-tests.db')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as cli:
        yield cli


def write(client, path, data, csrf=None, method='POST'):
    return client.request(method, '/api' + path, json=data,
                          headers={'x-csrf-token': csrf} if csrf else {})


def guest(client, monkeypatch):
    monkeypatch.setenv('EZ_THING_ENVIRONMENT', 'staging')
    monkeypatch.setenv('EZ_THING_DEMO_MODE', '1')
    r = write(client, '/auth/demo', {})
    assert r.status_code == 201, r.text
    return r.json()['csrf_token']


def slot(hours=10, days=2):
    return (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')) + timedelta(days=days)).replace(
        hour=hours, minute=0, second=0, microsecond=0).isoformat()


def body(req='request-000001', party=2, start=None):
    return {'request_id': req, 'customer_name': 'Khách đặt bàn', 'phone': '0912345678',
            'party_size': party, 'start_at': start or slot(), 'duration_minutes': 90,
            'note': 'Sân vườn nếu có'}


def test_booking_frontend_routes(client):
    assert client.get('/reserve/cafe').status_code == 200
    assert '/assets/reservations.js' in client.get('/reserve/cafe').text
    legacy = client.get('/app/reservations', follow_redirects=False)
    assert legacy.status_code == 307
    assert legacy.headers['location'] == '/app?tab=reservations'
    assert '/assets/app.js' in client.get('/app/reservations').text
    assert '/assets/merchant-restaurant-suite.js' in client.get('/app/reservations').text
    for a in ['/assets/reservations.js', '/assets/reservations.css']:
        assert client.get(a).status_code == 200
    assert client.get('/reserve/unknown').status_code == 404


def test_public_booking_auto_assignment_idempotency_conflict_and_status(client, monkeypatch):
    csrf = guest(client, monkeypatch)
    preview = client.get('/api/preview/cafe').json()
    assert preview['tables']
    d = (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')) + timedelta(days=2)).date().isoformat()
    availability = client.get('/api/preview/cafe/reservations/availability',
                              params={'day': d, 'party_size': 6})
    assert availability.status_code == 200, availability.text
    assert any(x['available'] for x in availability.json()['slots'])
    b = body(party=6)
    assert write(client, '/preview/cafe/reservations', b).status_code == 403
    r = write(client, '/preview/cafe/reservations', b, csrf)
    assert r.status_code == 201, r.text
    assert r.json()['status'] == 'pending'
    assert r.json()['table_label']
    ident = r.json()['id']
    assert write(client, '/preview/cafe/reservations', b, csrf).json()['id'] == ident
    wrong = dict(b, note='Not the same request')
    assert write(client, '/preview/cafe/reservations', wrong, csrf).status_code == 409
    conflict = body(req='request-000002', party=6, start=slot(11))
    assert write(client, '/preview/cafe/reservations', conflict, csrf).status_code == 409
    other_day = body(req='request-000003', party=6, start=slot(13))
    assert write(client, '/preview/cafe/reservations', other_day, csrf).status_code == 201
    biz = next(x for x in client.get('/api/businesses').json() if x['industry'] == 'fnb')
    listing = client.get(f'/api/businesses/{biz["id"]}/reservations')
    assert listing.status_code == 200 and len(listing.json()) == 2
    assert write(client, f'/businesses/{biz["id"]}/reservations/{ident}/status',
                 {'status': 'seated'}, csrf).status_code == 409
    assert write(client, f'/businesses/{biz["id"]}/reservations/{ident}/status',
                 {'status': 'confirmed'}, csrf).status_code == 200
    assert client.get('/api/preview/cafe/reservations/' + ident).json()['status'] == 'confirmed'
    assert write(client, f'/businesses/{biz["id"]}/reservations/{ident}/status',
                 {'status': 'cancelled'}, csrf).status_code == 200
    assert write(client, '/preview/cafe/reservations', conflict, csrf).status_code == 201


def test_booking_invalid_datetime_capacity_and_cross_tenant(client, monkeypatch):
    csrf = guest(client, monkeypatch)
    invalid = body(start='2026-11-20T10:00:00')
    assert write(client, '/preview/cafe/reservations', invalid, csrf).status_code == 422
    invalid = body(start=slot(23))
    assert write(client, '/preview/cafe/reservations', invalid, csrf).status_code == 422
    invalid = body(party=20)
    assert write(client, '/preview/cafe/reservations', invalid, csrf).status_code == 409
    invalid = body()
    invalid['table_id'] = 'fake-table-id'
    assert write(client, '/preview/cafe/reservations', invalid, csrf).status_code == 422
    other = TestClient(app)
    try:
        other_csrf = guest(other, monkeypatch)
        r = write(client, '/preview/cafe/reservations', body(), csrf)
        assert r.status_code == 201
        assert other.get('/api/preview/cafe/reservations/' + r.json()['id']).status_code == 404
        fake_biz = next(x for x in other.get('/api/businesses').json() if x['industry'] == 'fnb')
        assert client.get(f'/api/businesses/{fake_biz["id"]}/reservations').status_code == 404
    finally:
        other.close()


def test_restaurant_contact_and_inquiry(client, monkeypatch):
    csrf = guest(client, monkeypatch)
    biz = next(x for x in client.get('/api/businesses').json() if x['industry'] == 'fnb')
    bid = biz['id']
    contact = {'phone': '0912345678', 'email': 'cafe@example.com',
               'address': '01 Đường mẫu, Q1', 'hours': '08:00 - 22:00'}
    assert write(client, f'/businesses/{bid}/reservations/contact', contact, method='PUT').status_code == 403
    r = write(client, f'/businesses/{bid}/reservations/contact', contact, csrf, 'PUT')
    assert r.status_code == 200, r.text
    assert client.get('/api/preview/cafe/reservations/contact').json()['phone'] == contact['phone']
    msg = {'request_id': 'inquiry-123456', 'name': 'Khách muốn hỏi',
           'phone': '0987654321', 'message': 'Quán còn bàn ngoài trời không?'}
    assert write(client, '/preview/cafe/inquiries', msg).status_code == 403
    r = write(client, '/preview/cafe/inquiries', msg, csrf)
    assert r.status_code == 201, r.text
    assert write(client, '/preview/cafe/inquiries', msg, csrf).json()['id'] == r.json()['id']
    inbox = client.get(f'/api/businesses/{bid}/inquiries').json()
    assert len(inbox) == 1 and inbox[0]['status'] == 'new'
    assert write(client, f'/businesses/{bid}/inquiries/{r.json()["id"]}/status',
                 {'status': 'closed'}, csrf).status_code == 409
    assert write(client, f'/businesses/{bid}/inquiries/{r.json()["id"]}/status',
                 {'status': 'contacted'}, csrf).status_code == 200
    assert write(client, f'/businesses/{bid}/inquiries/{r.json()["id"]}/status',
                 {'status': 'closed'}, csrf).status_code == 200
    assert client.get('/api/preview/online/reservations/contact').status_code == 404

def test_merchant_preferred_time_zone_availability_and_table_validation(client, monkeypatch):
    csrf = guest(client, monkeypatch)
    business = next(x for x in client.get('/api/businesses').json() if x['industry'] == 'fnb')
    bid = business['id']
    floor = client.get(f'/api/businesses/{bid}/floorplan').json()
    assert floor['branch_id'] and floor['tables']
    day = (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')) +
           timedelta(days=2)).date().isoformat()
    url = f'/api/businesses/{bid}/reservations/availability'
    base = {'day': day, 'party_size': 2, 'duration_minutes': 60,
            'branch_id': floor['branch_id']}
    zone = floor['tables'][0]['placement']['zone_id']
    valid = client.get(url, params={**base, 'zone_id': zone})
    assert valid.status_code == 200, valid.text
    assert any(x['available'] for x in valid.json()['slots'])
    other_zone = next(z['id'] for z in floor['zones'] if z['id'] != zone)
    empty = client.get(url, params={**base, 'zone_id': other_zone})
    assert empty.status_code == 200, empty.text
    assert not any(x['available'] for x in empty.json()['slots'])
    wrong = client.get(url, params={**base, 'zone_id': other_zone,
                                    'table_id': floor['tables'][0]['id']})
    assert wrong.status_code == 422
    assert client.get(url, params={**base, 'zone_id': 'unknown-zone'}).status_code == 422
    payload = {**body(req='merchant-preferred-zone-0001', start=slot(10)),
               'zone_id': zone, 'branch_id': floor['branch_id'],
               'duration_minutes': 60}
    booked = write(client, f'/businesses/{bid}/reservations', payload, csrf)
    assert booked.status_code == 201, booked.text
    blocked = write(client, f'/businesses/{bid}/reservations',
                    {**payload, 'request_id': 'merchant-preferred-zone-0002',
                     'zone_id': other_zone}, csrf)
    assert blocked.status_code == 409


def test_merchant_booking_form_has_time_selection_retry_and_disabled_unverified_slot():
    js = (Path(__file__).resolve().parents[1] /
          'app/static/merchant-restaurant-suite.js').read_text()
    assert 'name="preferred_time"' in js
    assert 'name="start_at"' in js
    assert 'data-suite=' in js
    assert 'retry-slots' in js
    assert "sel.disabled=true" in js
    assert "branch_id" in js and "zone_id" in js


def test_business_booking_policy_closures_slots_validation_and_idempotent_retry(client, monkeypatch):
    """The API, rather than the UI, determines which days/times can be booked."""
    csrf = guest(client, monkeypatch)
    bid = next(x['id'] for x in client.get('/api/businesses').json()
               if x['industry'] == 'fnb')
    endpoint = f'/businesses/{bid}/reservations/policy'
    current = client.get('/api' + endpoint)
    assert current.status_code == 200
    assert current.json() == {
        'open_time': '08:00', 'last_seating_time': '20:30',
        'close_time': '22:00', 'closed_weekdays': [], 'blocked_dates': []}
    assert client.get('/api/preview/cafe/reservations/policy').json() == current.json()

    day = (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')) + timedelta(days=2)).date()
    day_string = day.isoformat()
    schedule = {
        'open_time': '11:00', 'last_seating_time': '12:00',
        'close_time': '14:00', 'closed_weekdays': [], 'blocked_dates': []}
    assert write(client, endpoint, schedule, method='PUT').status_code == 403
    invalid = {**schedule, 'close_time': '10:00'}
    assert write(client, endpoint, invalid, csrf, 'PUT').status_code == 422
    invalid = {**schedule, 'closed_weekdays': [7]}
    assert write(client, endpoint, invalid, csrf, 'PUT').status_code == 422
    invalid = {**schedule, 'blocked_dates': [day_string, day_string]}
    assert write(client, endpoint, invalid, csrf, 'PUT').status_code == 422

    saved = write(client, endpoint, schedule, csrf, 'PUT')
    assert saved.status_code == 200, saved.text
    assert saved.json() == schedule
    slots = client.get(f'/api/businesses/{bid}/reservations/availability',
                       params={'day': day_string, 'party_size': 2, 'duration_minutes': 60})
    assert slots.status_code == 200, slots.text
    assert slots.json()['slots']
    assert all(11 <= datetime.fromisoformat(s['start_at']).hour <= 12
               for s in slots.json()['slots'])
    assert write(client, f'/businesses/{bid}/reservations',
                 body(req='before-hours-policy', start=slot(10)), csrf).status_code == 422

    initial = body(req='policy-idempotency-001', start=slot(11))
    first = write(client, f'/businesses/{bid}/reservations', initial, csrf)
    assert first.status_code == 201, first.text
    first_id = first.json()['id']

    blocked_weekday = {**schedule, 'closed_weekdays': [day.weekday()]}
    assert write(client, endpoint, blocked_weekday, csrf, 'PUT').status_code == 200
    closed = client.get(f'/api/businesses/{bid}/reservations/availability',
                        params={'day': day_string, 'party_size': 2})
    assert closed.status_code == 200
    assert closed.json()['slots'] == []
    assert closed.json()['closed_reason']
    assert write(client, f'/businesses/{bid}/reservations',
                 body(req='policy-new-rejected', start=slot(12)), csrf).status_code == 422
    # Previously accepted bookings remain visible and retryable after policy changes.
    retry = write(client, f'/businesses/{bid}/reservations', initial, csrf)
    assert retry.status_code == 201 and retry.json()['id'] == first_id

    holiday = {**schedule, 'blocked_dates': [day_string]}
    assert write(client, endpoint, holiday, csrf, 'PUT').status_code == 200
    assert client.get('/api/preview/cafe/reservations/policy').json()['blocked_dates'] == [day_string]
    holiday_slots = client.get('/api/preview/cafe/reservations/availability',
                               params={'day': day_string, 'party_size': 2})
    assert holiday_slots.status_code == 200 and holiday_slots.json()['slots'] == []
    assert write(client, f'/businesses/{bid}/reservations',
                 body(req='policy-closure-rejected', start=slot(12)), csrf).status_code == 422


def test_booking_policy_ui_is_in_existing_merchant_reservations_tab():
    source = (Path(__file__).resolve().parents[1] /
              'app/static/merchant-restaurant-suite.js').read_text()
    assert 'data-suite-form="reservation-policy"' in source
    assert "reservations/policy" in source
    assert "closed_weekdays" in source and "blocked_dates" in source
    assert "open_time" in source and "last_seating_time" in source
    assert "new-booking" in source
