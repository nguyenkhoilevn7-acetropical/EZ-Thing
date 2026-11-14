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
    assert client.get('/app/reservations').status_code == 200
    assert '/assets/reservations.js' in client.get('/app/reservations').text
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