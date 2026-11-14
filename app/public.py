"""Scoped customer-facing *demo previews*.

This is intentionally NOT an anonymous production storefront or booking engine.
Every preview is backed by an isolated guest's own DEMO tenants.  A visitor
must have a staging-only demo session; neither business records nor customer
records from non-demo tenants are exposed through this router.
"""
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import db_session
from .demo import demo_enabled, is_demo_user
from .models import (AuditEvent, Branch, Business, Customer, DiningTable, Membership,
                     Product, SaleOrder, SaleOrderItem, StockMovement, now)
from .workflows import IndustryWorkItem
from .main import current_user, new_id, order_out, fail
from .storefront_brand import effective_brand  # Customer-facing demo appearance only

router = APIRouter(prefix='/api/preview', tags=['Demo customer storefront'])
CHANNELS = {'cafe':'fnb','mart':'retail','online':'online','wellness':'services'}
SPECIALISTS = ('Linh', 'Minh', 'An')  # illustrative staff; no real staff roster
TZ = ZoneInfo('Asia/Ho_Chi_Minh')


class PublicLine(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=10)


class PreviewCheckout(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    lines: list[PublicLine] = Field(min_length=1, max_length=20)
    customer_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(default='', max_length=30)
    address: str = Field(default='', max_length=300)
    table_id: str | None = None
    note: str = Field(default='', max_length=240)


class PreviewAppointment(BaseModel):
    request_id: str = Field(min_length=8, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    product_id: str
    customer_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=6, max_length=30)
    assignee: str = Field(min_length=1, max_length=100)
    start_at: datetime
    note: str = Field(default='', max_length=240)


def preview_business(db: Session, user, channel: str):
    if not demo_enabled() or not is_demo_user(user[0]):
        fail(404, 'Bản xem trước chỉ có ở staging DEMO')
    industry = CHANNELS.get(channel)
    if industry is None:
        fail(404, 'Không có gian hàng này')
    b = db.scalar(select(Business).join(Membership, Membership.business_id == Business.id)
                  .where(Membership.user_id == user[0].id, Business.industry == industry,
                         Business.subscription_status == 'demo'))
    if b is None:
        fail(404, 'Không tìm thấy gian hàng DEMO')
    return b


def preview_scope(db, user, channel):
    b = preview_business(db, user, channel)
    from .platform_admin import is_business_blocked
    if is_business_blocked(db, b.id):
        fail(403, "Doanh nghiệp đang bị tạm khóa")
    return b


def p_output(p):
    # Only customer-facing fields; no cost_vnd, stock ledger, or private customer data.
    return {'id':p.id,'sku':p.sku,'name':p.name,'category':p.category,
            'price_vnd':p.price_vnd,'available':p.active and (not p.track_stock or p.stock > 0),
            'stock_hint':'Hết hàng' if p.track_stock and p.stock <= 0 else 'Có sẵn'}


@router.get('/{channel}')
def storefront(channel: str, user=Depends(current_user), db: Session=Depends(db_session)):
    b=preview_scope(db,user,channel)
    rows=db.scalars(select(Product).where(Product.business_id==b.id,Product.active.is_(True))
                    .order_by(Product.name)).all()
    result={'business':{'name':b.name.replace(' • DEMO',''),'industry':b.industry,
                         'branding':effective_brand(b) if (b.setup or {}).get('storefront') else None},
            'channel':channel,'demo':True,'products':[p_output(p) for p in rows],
            'staff':list(SPECIALISTS) if channel=='wellness' else [],'tables':[]}
    if channel=='cafe':
        t=db.scalars(select(DiningTable).where(DiningTable.business_id==b.id).order_by(DiningTable.label)).all()
        result['tables']=[{'id':x.id,'label':x.label} for x in t]
    return result


def fingerprint(body: BaseModel):
    return hashlib.sha256(json.dumps(body.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest()


@router.post('/{channel}/checkout',status_code=201)
def demo_checkout(channel: str, body: PreviewCheckout,
                  user=Depends(current_user),db: Session=Depends(db_session)):
    if channel=='wellness':fail(404,'Dùng trang đặt lịch cho dịch vụ')
    b=preview_scope(db,user,channel)
    key='web-'+body.request_id
    fp=fingerprint(body)
    previous=db.scalar(select(SaleOrder).where(SaleOrder.business_id==b.id,SaleOrder.idempotency_key==key))
    if previous:
        if previous.request_fingerprint!=fp:fail(409,'Mã yêu cầu đã được dùng với nội dung khác')
        return order_out(db,previous)
    existing=db.scalar(select(func.count(SaleOrder.id)).where(SaleOrder.business_id==b.id)) or 0
    if existing>=45:fail(429,'Phiên demo đã đạt giới hạn đơn hàng')
    if channel in ('online','mart') and (not body.phone.strip() or not body.address.strip() and channel=='online'):
        fail(422,'Cần số điện thoại và địa chỉ nhận hàng khi giao tận nơi')
    if channel=='cafe' and not body.table_id:
        fail(422,'Vui lòng chọn bàn trước khi gọi món')
    branch=db.scalar(select(Branch).where(Branch.business_id==b.id).order_by(Branch.created_at))
    if branch is None:fail(404,'Không có chi nhánh DEMO')
    if body.table_id:
        if channel!='cafe' or db.scalar(select(DiningTable).where(DiningTable.id==body.table_id,
                       DiningTable.business_id==b.id, DiningTable.branch_id==branch.id)) is None:
            fail(404,'Bàn không thuộc quán này')
    quantities=defaultdict(int)
    for ln in body.lines:quantities[ln.product_id]+=ln.quantity
    if sum(quantities.values())>30:fail(422,'Tối đa 30 sản phẩm mỗi đơn DEMO')
    products={}
    for pid in quantities:
        p=db.scalar(select(Product).where(Product.id==pid,Product.business_id==b.id,Product.active.is_(True)))
        if not p:fail(404,'Sản phẩm không có trong gian hàng này')
        products[pid]=p
    total=sum(products[pid].price_vnd*qty for pid,qty in quantities.items())
    if total>20_000_000:fail(422,'Đơn thử nghiệm vượt giới hạn')
    try:
        customer=Customer(id=new_id(),business_id=b.id,name=body.customer_name.strip(),
                          phone=body.phone.strip(),address=body.address.strip())
        db.add(customer);db.flush()
        o=SaleOrder(id=new_id(),business_id=b.id,branch_id=branch.id,
                    table_id=body.table_id,customer_id=customer.id,
                    idempotency_key=key,request_fingerprint=fp,
                    note=('DEMO CUSTOMER • '+body.note).strip(),total_vnd=total)
        db.add(o);db.flush()
        for pid,qty in quantities.items():
            p=products[pid]
            if p.track_stock:
                changed=db.execute(update(Product).where(Product.id==pid,Product.business_id==b.id,
                               Product.stock>=qty).values(stock=Product.stock-qty))
                if not changed.rowcount:fail(409,'Không đủ tồn kho: '+p.name)
                db.add(StockMovement(id=new_id(),business_id=b.id,product_id=pid,
                                     delta=-qty,reason='sale',ref=o.id))
            db.add(SaleOrderItem(id=new_id(),business_id=b.id,order_id=o.id,product_id=pid,
                                 product_name=p.name,quantity=qty,unit_price_vnd=p.price_vnd,
                                 total_vnd=p.price_vnd*qty))
        if channel in ('cafe','online'):
            kind='kitchen' if channel=='cafe' else 'delivery'
            db.add(IndustryWorkItem(id=new_id(),business_id=b.id,kind=kind,reference_id=o.id,
                  customer_id=customer.id,title=('Phiếu bếp • ' if channel=='cafe' else 'Đơn giao • ')+o.id[:8].upper(),
                  status='pending',details={'note':body.note.strip(),'source':'customer-demo'}))
        db.add(AuditEvent(id=new_id(),business_id=b.id,actor_id=user[0].id,
                          action='preview.checkout',payload=json.dumps({'order_id':o.id,'channel':channel})))
        db.commit()
    except IntegrityError:
        db.rollback()
        old=db.scalar(select(SaleOrder).where(SaleOrder.business_id==b.id,SaleOrder.idempotency_key==key))
        if old and old.request_fingerprint==fp:return order_out(db,old)
        fail(409,'Đơn đã được xử lý, vui lòng kiểm tra trước khi gửi lại')
    except Exception:
        db.rollback()
        raise
    return order_out(db,o)


@router.get('/{channel}/orders/{order_id}')
def preview_order(channel:str,order_id:str,user=Depends(current_user),db:Session=Depends(db_session)):
    if channel=='wellness':fail(404,'Không hỗ trợ')
    b=preview_scope(db,user,channel)
    o=db.scalar(select(SaleOrder).where(SaleOrder.business_id==b.id,SaleOrder.id==order_id,
                                        SaleOrder.idempotency_key.like('web-%')))
    if not o:fail(404,'Không tìm thấy đơn')
    return order_out(db,o)


def demo_slots(db,b,product,assignee,day):
    if assignee not in SPECIALISTS:fail(422,'Chuyên viên DEMO không hợp lệ')
    if product is None or product.business_id!=b.id or product.track_stock or not product.active:
        fail(404,'Dịch vụ không tồn tại')
    today=datetime.now(TZ).date()
    if day<today or day>today+timedelta(days=21):
        fail(422,'Chỉ được đặt lịch trong 21 ngày tới')
    result=[]
    for hour in range(9,18):
        start=datetime.combine(day,time(hour,0),tzinfo=TZ).astimezone(timezone.utc)
        end=start+timedelta(minutes=60)
        if start<now()+timedelta(minutes=30):continue
        conflict=db.scalar(select(IndustryWorkItem.id).where(
            IndustryWorkItem.business_id==b.id,IndustryWorkItem.kind=='appointments',
            func.lower(IndustryWorkItem.assignee)==assignee.casefold(),
            IndustryWorkItem.status.in_(['scheduled','confirmed']),
            IndustryWorkItem.scheduled_at<end,IndustryWorkItem.ends_at>start))
        if not conflict:result.append(start.isoformat())
    return result


@router.get('/wellness/slots')
def available_slots(product_id:str=Query(...),day:date=Query(...),assignee:str=Query(...),
                    user=Depends(current_user),db:Session=Depends(db_session)):
    b=preview_scope(db,user,'wellness')
    product=db.get(Product,product_id)
    return {'slots':demo_slots(db,b,product,assignee,day),'timezone':'Asia/Ho_Chi_Minh'}


@router.post('/wellness/appointments',status_code=201)
def book_demo_appointment(body:PreviewAppointment,user=Depends(current_user),db:Session=Depends(db_session)):
    b=preview_scope(db,user,'wellness')
    if body.assignee not in SPECIALISTS:fail(422,'Chuyên viên không tồn tại')
    if body.start_at.tzinfo is None or body.start_at.utcoffset() is None:
        fail(422,'Ngày giờ cần múi giờ')
    product=db.scalar(select(Product).where(Product.id==body.product_id,Product.business_id==b.id))
    ref=hashlib.sha256((b.id+'|'+body.request_id).encode()).hexdigest()[:36]
    fp=fingerprint(body)
    old=db.scalar(select(IndustryWorkItem).where(IndustryWorkItem.business_id==b.id,
                  IndustryWorkItem.kind=='appointments',IndustryWorkItem.reference_id==ref))
    if old:
        if (old.details or {}).get('fingerprint')!=fp:fail(409,'Mã đặt lịch đã dùng')
        return {'id':old.id,'status':old.status,'scheduled_at':old.scheduled_at.isoformat()}
    count=db.scalar(select(func.count(IndustryWorkItem.id)).where(
        IndustryWorkItem.business_id==b.id,IndustryWorkItem.kind=='appointments')) or 0
    if count>=35:fail(429,'Phiên DEMO đã đạt giới hạn lịch hẹn')
    start=body.start_at.astimezone(timezone.utc)
    if start.minute!=0 or start.second!=0:fail(422,'Vui lòng chọn khung giờ có sẵn')
    try:
        # Protect concurrent appointments on PostgreSQL with the same advisory lock
        # as the merchant booking endpoint.
        if db.bind and db.bind.dialect.name=='postgresql':
            key=int.from_bytes(hashlib.sha256(f'{b.id}|{body.assignee.casefold()}'.encode()).digest()[:8],'big',signed=True)
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':key})
        if start.isoformat() not in demo_slots(db,b,product,body.assignee,start.astimezone(TZ).date()):
            fail(409,'Khung giờ này đã được đặt, chọn giờ khác')
        customer=Customer(id=new_id(),business_id=b.id,name=body.customer_name.strip(),phone=body.phone.strip())
        db.add(customer);db.flush()
        row=IndustryWorkItem(id=new_id(),business_id=b.id,kind='appointments',reference_id=ref,
            customer_id=customer.id,product_id=product.id,assignee=body.assignee,
            title=f'{product.name} • {customer.name}',status='scheduled',
            scheduled_at=start,ends_at=start+timedelta(minutes=60),
            details={'note':body.note,'fingerprint':fp,'source':'customer-demo'})
        db.add(row)
        db.add(AuditEvent(id=new_id(),business_id=b.id,actor_id=user[0].id,action='preview.appointment',
                         payload=json.dumps({'id':row.id})))
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409,'Lịch hẹn đã được tạo')
    except Exception:
        db.rollback()
        raise
    return {'id':row.id,'status':row.status,'scheduled_at':row.scheduled_at.isoformat()}