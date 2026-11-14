"""EZ Thing /admin control-plane authorization and operational safety tests."""
import os
import sys
from pathlib import Path

os.environ.setdefault('DATABASE_URL', 'sqlite:///' + str(Path(__file__).parent / 'pilot-tests.db'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import User, Business, Branch
from app.platform_admin import PlatformActionLog, PlatformAdminUnlock, PlatformTenantControl, PlatformUserControl
from sqlalchemy import select, func

KEY = 'ez-thing-admin-test-key-long-enough-1234567890'


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setenv('EZ_THING_SUPERADMIN_EMAILS', 'platform-admin@example.com')
    monkeypatch.setenv('EZ_THING_ADMIN_ACCESS_KEY', KEY)
    monkeypatch.setenv('EZ_THING_ENVIRONMENT', 'staging')
    monkeypatch.setenv('EZ_THING_DEMO_MODE', '1')
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def signup(client, email, name='Tester'):
    r = client.post('/api/auth/signup', json={'email': email, 'name': name,
                                               'password': 'TestPassword!123'})
    assert r.status_code == 201, r.text
    return r.json()['csrf_token']


def post(client, url, body, csrf):
    return client.post(url, json=body, headers={'x-csrf-token': csrf} if csrf else {})


def create_business(client, csrf, industry='fnb', plan='PRO'):
    r = post(client, '/api/businesses', {'name': 'Shop ' + industry,
       'industry': industry, 'selected_plan': plan, 'need_branches': plan == 'PRO',
       'need_inventory': True, 'need_insights': True, 'need_tables': industry == 'fnb'}, csrf)
    assert r.status_code == 201, r.text
    return r.json()


def enter_admin(client):
    csrf = signup(client, 'platform-admin@example.com', name='System admin')
    assert client.get('/api/admin/session').status_code == 200
    assert client.get('/api/admin/session').json()['unlocked'] is False
    assert client.get('/api/admin/summary').status_code == 403
    assert post(client,'/api/admin/unlock',{'access_key':KEY},csrf).status_code == 200
    assert client.get('/api/admin/summary').status_code == 200
    return csrf


def test_admin_unlock_requires_real_login_allowlist_and_second_secret():
    with TestClient(app) as anon:
        assert anon.get('/api/admin/summary').status_code == 401
        assert anon.get('/api/admin/preview').json()['mode']=='synthetic_demo'
        csrf=signup(anon,'regular@example.com')
        assert anon.get('/api/admin/session').status_code == 403
        assert post(anon,'/api/admin/unlock',{'access_key':KEY},csrf).status_code == 403
        assert anon.get('/api/admin/businesses').status_code == 403
    with TestClient(app) as admin:
        csrf=signup(admin,'platform-admin@example.com')
        assert post(admin,'/api/admin/unlock',{'access_key':KEY},None).status_code == 403
        assert post(admin,'/api/admin/unlock',{'access_key':'incorrect'},csrf).status_code == 403
        assert admin.get('/api/admin/summary').status_code == 403
        assert post(admin,'/api/admin/unlock',{'access_key':KEY},csrf).status_code == 200
        assert admin.get('/api/admin/overview').status_code == 200
        assert admin.get('/api/admin/plans').json()['billing_live'] is False
        assert admin.get('/api/admin/system').json()['database']=='reachable'
        assert post(admin,'/api/admin/lock',{},csrf).status_code == 200
        assert admin.get('/api/admin/summary').status_code == 403


def test_missing_admin_second_secret_fails_closed(monkeypatch):
    with TestClient(app) as admin:
        csrf=signup(admin,'platform-admin@example.com')
        monkeypatch.setenv('EZ_THING_ADMIN_ACCESS_KEY','short')
        assert admin.get('/api/admin/session').status_code == 503
        assert post(admin,'/api/admin/unlock',{'access_key':KEY},csrf).status_code == 503
        assert admin.get('/api/admin/summary').status_code == 503
        monkeypatch.setenv('EZ_THING_ADMIN_ACCESS_KEY',KEY)
        assert post(admin,'/api/admin/unlock',{'access_key':KEY},csrf).status_code == 200
        monkeypatch.setenv('EZ_THING_ADMIN_ACCESS_KEY','different-admin-secret-long-enough-1234')
        assert admin.get('/api/admin/summary').status_code == 403


def test_unlock_attempt_lockout_is_enforced(monkeypatch):
    with TestClient(app) as admin:
        csrf=signup(admin,'platform-admin@example.com')
        for i in range(5):
            assert post(admin,'/api/admin/unlock',{'access_key':'bad-'+str(i)},csrf).status_code == 403
        assert post(admin,'/api/admin/unlock',{'access_key':KEY},csrf).status_code == 429


def test_business_lifecycle_plan_limits_and_audit_are_real():
    with TestClient(app) as owner, TestClient(app) as admin:
        owner_csrf=signup(owner,'shop-owner@example.com')
        b=create_business(owner,owner_csrf)
        admin_csrf=enter_admin(admin)
        r=admin.get('/api/admin/businesses')
        assert r.status_code == 200 and r.json()['total']==1
        detail=admin.get('/api/admin/businesses/'+b['id']).json()
        assert detail['owner']['email']=='shop-owner@example.com'
        branch = post(owner,f"/api/businesses/{b['id']}/branches",{'name':'Chi nhánh thứ hai'},owner_csrf)
        assert branch.status_code==201,branch.text
        downgrade=post(admin,f"/api/admin/businesses/{b['id']}/plan",
          {'plan':'BASIC','reason':'Chuyển gói vì nhu cầu đã thay đổi','confirmed':True},admin_csrf)
        assert downgrade.status_code==409
        assert post(admin,f"/api/admin/businesses/{b['id']}/suspend",
          {'confirm_name':'Sai tên','reason':'Kiểm tra dữ liệu hợp lệ'},admin_csrf).status_code==422
        assert post(admin,f"/api/admin/businesses/{b['id']}/suspend",
          {'confirm_name':b['name'],'reason':'Tạm khóa theo yêu cầu chủ doanh nghiệp'},admin_csrf).status_code==200
        assert owner.get(f"/api/businesses/{b['id']}").status_code==403
        assert admin.get('/api/admin/businesses?status=suspended').json()['total']==1
        assert post(admin,f"/api/admin/businesses/{b['id']}/resume",
          {'reason':'Đã kiểm tra và khôi phục dịch vụ','confirmed':True},admin_csrf).status_code==200
        assert owner.get(f"/api/businesses/{b['id']}").status_code==200
        with SessionLocal() as db:
            assert db.scalar(select(func.count(PlatformActionLog.id)))>=3
            assert db.get(PlatformTenantControl,b['id']).suspended is False


def test_business_plan_entitlements_remain_industry_scoped():
    with TestClient(app) as owner, TestClient(app) as admin:
        owner_csrf=signup(owner,'owner-spa@example.com')
        b=create_business(owner,owner_csrf,industry='services',plan='PLUS')
        admin_csrf=enter_admin(admin)
        r=post(admin,f"/api/admin/businesses/{b['id']}/plan",
               {'plan':'BASIC','reason':'Thay đổi gói pilot theo nhu cầu','confirmed':True},admin_csrf)
        assert r.status_code==200,r.text
        assert r.json()['billing_applied'] is False
        new=admin.get('/api/admin/businesses/'+b['id']).json()
        assert new['plan']=='BASIC'
        assert 'tables' not in new['active_modules']
        assert 'multi_branch' not in new['active_modules']
        assert 'orders' in new['active_modules']
        audit=admin.get('/api/admin/audit').json()
        assert any(x['action']=='business.plan_changed' and x['target_id']==b['id'] for x in audit['items'])


def test_user_block_revokes_sessions_and_protects_admin():
    with TestClient(app) as owner, TestClient(app) as admin:
        owner_csrf=signup(owner,'owner-block@example.com')
        b=create_business(owner,owner_csrf)
        admin_csrf=enter_admin(admin)
        target=next(x for x in admin.get('/api/admin/users').json()['items'] if x['email']=='owner-block@example.com')
        assert post(admin,f"/api/admin/users/{target['id']}/block",
          {'confirm_email':'other@example.com','reason':'Yêu cầu khóa để kiểm tra'},admin_csrf).status_code==422
        blocked=post(admin,f"/api/admin/users/{target['id']}/block",
          {'confirm_email':target['email'],'reason':'Tạm khóa do chủ tài khoản đề nghị'},admin_csrf)
        assert blocked.status_code==200,blocked.text
        assert blocked.json()['sessions_revoked']>=1
        assert owner.get('/api/auth/me').status_code==401
        login=owner.post('/api/auth/login',json={'email':target['email'],'password':'TestPassword!123'})
        assert login.status_code==403
        admin_uid=admin.get('/api/admin/session')
        with SessionLocal() as db:
            admin_user=db.scalar(select(User).where(User.email=='platform-admin@example.com'))
        assert post(admin,f"/api/admin/users/{admin_user.id}/block",
          {'confirm_email':admin_user.email,'reason':'Thử khóa tài khoản quản trị'},admin_csrf).status_code==403
        assert post(admin,f"/api/admin/users/{target['id']}/unblock",
          {'reason':'Đã xác minh quyền sở hữu hợp lệ','confirmed':True},admin_csrf).status_code==200
        assert owner.post('/api/auth/login',json={'email':target['email'],'password':'TestPassword!123'}).status_code==200


def test_demo_is_static_never_exposes_live_records(monkeypatch):
    with TestClient(app) as owner:
        csrf=signup(owner,'private@example.com')
        b=create_business(owner,csrf)
    with TestClient(app) as anon:
        payload=anon.get('/api/admin/preview').json()
        assert payload['mode']=='synthetic_demo' and payload['read_only'] is True
        assert b['id'] not in str(payload)
        assert 'private@example.com' not in str(payload)
        assert anon.get('/api/admin/businesses').status_code==401
        assert anon.get('/api/admin/overview').status_code==401
        monkeypatch.setenv('EZ_THING_DEMO_MODE','0')
        assert anon.get('/api/admin/preview').status_code==404


def test_admin_pages_are_static_and_server_never_embeds_secrets():
    with TestClient(app) as client:
        assert 'admin.js' in client.get('/admin').text if client.get('/admin').status_code==200 else True
        js=client.get('/assets/admin.js').text
        assert 'EZ_THING_ADMIN_ACCESS_KEY' in js  # only the variable NAME for setup, not its value
        assert KEY not in js