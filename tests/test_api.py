import os
import sys
from pathlib import Path

os.environ['DATABASE_URL']='sqlite:///'+str(Path(__file__).parent/'pilot-tests.db')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.database import Base,engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def cli():
    with TestClient(app) as client:
        yield client


def post(cli,path,payload,csrf=None):
    return cli.post('/api'+path,json=payload,headers={'x-csrf-token':csrf} if csrf else {})


def signup(cli,who='a'):
    res=post(cli,'/auth/signup',{'name':'Owner '+who,'email':who+'@example.com','password':'SafePassword!123'})
    assert res.status_code==201,res.text
    return res.json()['csrf_token']


def business(cli,csrf,industry='fnb',plan='PLUS',tables=True):
    res=post(cli,'/businesses',{'name':'Business '+industry,'industry':industry,
             'selected_plan':plan,'need_tables':tables,'need_inventory':True,
             'need_insights':plan!='BASIC','need_branches':plan=='PRO'},csrf)
    assert res.status_code==201,res.text
    return res.json()


def product(cli,bid,csrf,price=25000,stock=7,sku='P1'):
    res=post(cli,f'/businesses/{bid}/products',{'name':'Cà phê','sku':sku,'price_vnd':price,'stock':stock},csrf)
    assert res.status_code==201,res.text
    return res.json()


def order(cli,bid,pid,csrf,key='request-00001',qty=2,table=None,customer=None):
    return post(cli,f'/businesses/{bid}/orders',{'idempotency_key':key,'lines':[{'product_id':pid,'quantity':qty}],
          'table_id':table,'customer_id':customer},csrf)


def test_auth_requires_csrf_and_strong_password(cli):
    assert post(cli,'/auth/signup',{'name':'Test','email':'t@example.com','password':'short'}).status_code==422
    csrf=signup(cli)
    assert cli.get('/api/auth/me').status_code==200
    assert post(cli,'/businesses',{'name':'Test','industry':'fnb'}).status_code==403
    assert cli.get('/api/businesses').json()==[]
    assert post(cli,'/auth/logout',{},csrf).status_code==200
    assert cli.get('/api/auth/me').status_code==401


def test_onboarding_deterministic_and_no_arbitrary_code(cli):
    r=post(cli,'/onboarding/recommend',{'industry':'fnb','need_tables':True,'need_inventory':True,'need_insights':True,'need_branches':False})
    assert r.status_code==200
    j=r.json()
    assert j['recommended_plan']=='PLUS' and 'tables' in j['available_now']
    assert 'qr_order' not in j['available_now']
    assert 'qr_order' in j['planned']


def test_order_idempotency_totals_and_stock(cli):
    csrf=signup(cli);bid=business(cli,csrf)['id'];pid=product(cli,bid,csrf)['id']
    r=order(cli,bid,pid,csrf)
    assert r.status_code==201,r.text
    assert r.json()['total_vnd']==50000
    assert order(cli,bid,pid,csrf).json()['id']==r.json()['id']
    assert order(cli,bid,pid,csrf,qty=3).status_code==409
    data=cli.get(f'/api/businesses/{bid}/products').json()
    assert data[0]['stock']==5
    assert len(cli.get(f'/api/businesses/{bid}/orders').json())==1


def test_order_low_stock_no_mutation(cli):
    csrf=signup(cli);bid=business(cli,csrf)['id'];pid=product(cli,bid,csrf,stock=1)['id']
    assert order(cli,bid,pid,csrf).status_code==409
    assert cli.get(f'/api/businesses/{bid}/products').json()[0]['stock']==1
    assert cli.get(f'/api/businesses/{bid}/orders').json()==[]


def test_billing_is_manual_and_audited(cli):
    csrf=signup(cli);bid=business(cli,csrf)['id'];pid=product(cli,bid,csrf)['id']
    oid=order(cli,bid,pid,csrf).json()['id']
    assert post(cli,f'/businesses/{bid}/orders/{oid}/paid',{'confirmed':True},csrf).status_code==200
    assert cli.get(f'/api/businesses/{bid}/overview').json()['paid_revenue_vnd']==50000
    again=post(cli,f'/businesses/{bid}/orders/{oid}/paid',{'confirmed':True},csrf)
    assert again.status_code==200
    assert cli.get(f'/api/businesses/{bid}/overview').json()['paid_revenue_vnd']==50000


def test_plan_gates_and_fnb_only_tables(cli):
    csrf=signup(cli);basic=business(cli,csrf,plan='BASIC');bid=basic['id']
    assert post(cli,f'/businesses/{bid}/branches',{'name':'Nhánh 2'},csrf).status_code==403
    pid=product(cli,bid,csrf)['id']
    assert post(cli,f'/businesses/{bid}/products/{pid}/stock',{'delta':2,'reason':'Restock'},csrf).status_code==403
    assert cli.get(f'/api/businesses/{bid}/insights').status_code==403
    retail=business(cli,csrf,industry='retail',plan='PRO')
    assert 'tables' not in retail['active_modules']
    assert post(cli,f"/businesses/{retail['id']}/tables",{'label':'Bàn 1'},csrf).status_code==403
    assert post(cli,f"/businesses/{retail['id']}/branches",{'name':'Nhánh 2'},csrf).status_code==201


def test_branch_table_and_customer_scope(cli):
    csrf=signup(cli);bid=business(cli,csrf)['id'];pid=product(cli,bid,csrf)['id']
    t=post(cli,f'/businesses/{bid}/tables',{'label':'Bàn 01','seats':4},csrf)
    assert t.status_code==201
    c=post(cli,f'/businesses/{bid}/customers',{'name':'Khách A','phone':'0900000000'},csrf)
    assert c.status_code==201
    o=order(cli,bid,pid,csrf,table=t.json()['id'],customer=c.json()['id'])
    assert o.status_code==201
    assert cli.get(f'/api/businesses/{bid}/tables').json()[0]['occupied'] is True
    other=business(cli,csrf,industry='retail',plan='PLUS')['id']
    assert order(cli,other,pid,csrf,key='request-other').status_code==404
    assert order(cli,other,pid,csrf,key='request-other',customer=c.json()['id']).status_code==404


def test_cross_tenant_user_cannot_read_or_write(cli):
    csrf=signup(cli,'first');bid=business(cli,csrf)['id'];product(cli,bid,csrf)
    other=TestClient(app);csrf2=signup(other,'second')
    assert other.get(f'/api/businesses/{bid}/products').status_code==404
    assert post(other,f'/businesses/{bid}/customers',{'name':'Hacker'},csrf2).status_code==404
    assert other.get(f'/api/businesses/{bid}/orders').status_code==404
    other.close()


def test_same_sku_separate_tenants(cli):
    csrf=signup(cli);b1=business(cli,csrf)['id'];b2=business(cli,csrf,industry='online')['id']
    assert product(cli,b1,csrf,sku='ABC')['sku']=='ABC'
    assert product(cli,b2,csrf,sku='ABC')['sku']=='ABC'
    assert post(cli,f'/businesses/{b1}/products',{'name':'Khác','sku':'ABC','price_vnd':10000},csrf).status_code==409


def test_insights_only_paid_sales(cli):
    csrf=signup(cli);bid=business(cli,csrf,plan='PLUS')['id'];pid=product(cli,bid,csrf)['id']
    oid=order(cli,bid,pid,csrf).json()['id']
    assert cli.get(f'/api/businesses/{bid}/insights').json()['top_products']==[]
    post(cli,f'/businesses/{bid}/orders/{oid}/paid',{'confirmed':True},csrf)
    data=cli.get(f'/api/businesses/{bid}/insights').json()
    assert data['top_products'][0]['revenue_vnd']==50000
    assert data['ai_generated'] is False


def test_stock_adjust_no_negative_inventory(cli):
    csrf=signup(cli);bid=business(cli,csrf,plan='PLUS')['id'];pid=product(cli,bid,csrf,stock=1)['id']
    assert post(cli,f'/businesses/{bid}/products/{pid}/stock',{'delta':-2,'reason':'Damage'},csrf).status_code==409
    assert post(cli,f'/businesses/{bid}/products/{pid}/stock',{'delta':3,'reason':'Restock'},csrf).json()['stock']==4


def test_static_shell_served(cli):
    assert cli.get('/').status_code==200
    assert cli.get('/assets/app.js').status_code==200
    assert cli.get('/api/health').json()['ok'] is True


def test_receivables_by_exact_customer_id(cli):
    csrf=signup(cli);bid=business(cli,csrf,plan='PLUS')['id'];pid=product(cli,bid,csrf,stock=20)['id']
    c1=post(cli,f'/businesses/{bid}/customers',{'name':'Khách A'},csrf).json()['id']
    c2=post(cli,f'/businesses/{bid}/customers',{'name':'Khách A'},csrf).json()['id']
    order(cli,bid,pid,csrf,key='request-00001',customer=c1)
    oid=order(cli,bid,pid,csrf,key='request-00002',customer=c2).json()['id']
    x=cli.get(f'/api/businesses/{bid}/receivables')
    assert x.status_code==200
    assert len(x.json()['customers'])==2
    assert x.json()['unpaid_vnd']==100000
    post(cli,f'/businesses/{bid}/orders/{oid}/paid',{'confirmed':True},csrf)
    assert cli.get(f'/api/businesses/{bid}/receivables').json()['unpaid_vnd']==50000


def test_pilot_security_headers(cli):
    r=cli.get('/')
    assert r.headers['x-frame-options']=='DENY'
    assert "script-src 'self'" in r.headers['content-security-policy']
    assert 'camera=()' in r.headers['permissions-policy']


def test_demo_is_explicitly_disabled_by_default(cli, monkeypatch):
    monkeypatch.delenv('EZ_THING_ENVIRONMENT', raising=False)
    monkeypatch.delenv('EZ_THING_DEMO_MODE', raising=False)
    assert cli.get('/api/config').json() == {'demo_enabled': False}
    assert post(cli, '/auth/demo', {}).status_code == 404
    assert cli.get('/api/auth/me').status_code == 401
    monkeypatch.setenv('EZ_THING_ENVIRONMENT', 'production')
    monkeypatch.setenv('EZ_THING_DEMO_MODE', '1')
    assert post(cli, '/auth/demo', {}).status_code == 404
    monkeypatch.setenv('EZ_THING_ENVIRONMENT', 'staging')
    monkeypatch.setenv('EZ_THING_DEMO_MODE', '0')
    assert post(cli, '/auth/demo', {}).status_code == 404


def test_demo_opens_without_signup_and_has_sample_data(cli, monkeypatch):
    monkeypatch.setenv('EZ_THING_ENVIRONMENT', 'staging')
    monkeypatch.setenv('EZ_THING_DEMO_MODE', '1')
    assert cli.get('/api/config').json()['demo_enabled'] is True
    resp = post(cli, '/auth/demo', {})
    assert resp.status_code == 201, resp.text
    assert resp.json()['demo'] is True
    assert resp.cookies.get('ez_session')
    assert cli.get('/api/auth/me').json()['demo'] is True
    cs = resp.json()['csrf_token']
    businesses = cli.get('/api/businesses').json()
    assert {b['industry'] for b in businesses} == {'fnb','retail','online','services'}
    fnb = next(b for b in businesses if b['industry'] == 'fnb')
    assert fnb['subscription_status'] == 'demo'
    bid = fnb['id']
    products = cli.get(f'/api/businesses/{bid}/products').json()
    assert len(products) >= 6
    tables = cli.get(f'/api/businesses/{bid}/tables').json()
    assert len(tables) >= 6 and any(t['occupied'] for t in tables)
    orders = cli.get(f'/api/businesses/{bid}/orders').json()
    assert len(orders) == 3
    assert {o['status'] for o in orders} == {'paid', 'open'}
    overview = cli.get(f'/api/businesses/{bid}/overview').json()
    assert overview['paid_revenue_vnd'] > 0
    assert overview['order_count'] == 3
    assert len(cli.get(f'/api/businesses/{bid}/insights').json()['top_products']) >= 1
    assert post(cli, f'/businesses/{bid}/customers', {'name':'Chặn CSRF'}).status_code == 403
    created = post(cli, f'/businesses/{bid}/customers', {'name':'Khách tự tạo'}, cs)
    assert created.status_code == 201, created.text
    assert created.json()['name'] == 'Khách tự tạo'


def test_demo_tenants_cannot_access_other_demo_or_real_user_data(cli, monkeypatch):
    monkeypatch.setenv('EZ_THING_ENVIRONMENT', 'staging')
    monkeypatch.setenv('EZ_THING_DEMO_MODE', '1')
    csrf_real = signup(cli, 'real')
    real_bid = business(cli, csrf_real)['id']
    first = TestClient(app)
    second = TestClient(app)
    try:
        a = post(first, '/auth/demo', {})
        b = post(second, '/auth/demo', {})
        assert a.status_code == 201, a.text
        assert b.status_code == 201, b.text
        first_bid = first.get('/api/businesses').json()[0]['id']
        second_bid = second.get('/api/businesses').json()[0]['id']
        assert first_bid != second_bid
        assert first.get(f'/api/businesses/{second_bid}/products').status_code == 404
        assert second.get(f'/api/businesses/{first_bid}/orders').status_code == 404
        assert first.get(f'/api/businesses/{real_bid}/customers').status_code == 404
        assert cli.get(f'/api/businesses/{first_bid}/orders').status_code == 404
    finally:
        first.close()
        second.close()
