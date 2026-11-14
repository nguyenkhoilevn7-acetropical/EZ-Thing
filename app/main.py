"""EZ Thing pilot API, tenant isolated and server-enforced entitlements.

No Minh Satori production integration; no automated AI, billing or tax issuance.
"""
import hashlib
import json
import os
from collections import deque
from threading import Lock
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import case, func, select, update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .catalog import INDUSTRIES, PLANS, ROADMAP, FEATURES, recommend
from .demo import demo_enabled, is_demo_user, seed_demo
from .i18n import INDUSTRIES_EN, RECOMMENDATION_EN, selected_language, translate_error
from .database import Base, db_session, engine
from .models import (AuditEvent, Branch, Business, Customer, DiningTable, Membership,
                     Product, SaleOrder, SaleOrderItem, SessionToken, StockMovement, User, LoginFailure, now)
from .schemas import (BranchCreate, ConfirmPayment, CreateBusiness, CreateOrder,
                      CustomerCreate, Login, OnboardAnswers, ProductCreate, SignUp,
                      StockAdjust, TableCreate)
from .security import check_password, digest_password, session_pair, token_hash

Base.metadata.create_all(bind=engine)  # Pilot only; production must use versioned migrations.
app = FastAPI(title="EZ Thing Business MVP", version="0.5.0", docs_url="/api/docs")
ASSETS = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/"):
        response.headers["Content-Language"] = selected_language(request)
        response.headers["Vary"] = "Accept-Language, Cookie"
    # Only safe, public customer previews can be framed by the same origin.
    # Back-office, super-admin and APIs remain non-embeddable.
    preview_paths = {"/menu/cafe", "/store/mart", "/store/online", "/booking/wellness", "/reserve/cafe"}
    same_origin_preview = request.url.path in preview_paths
    response.headers["X-Frame-Options"] = "SAMEORIGIN" if same_origin_preview else "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://images.unsplash.com; "
        "connect-src 'self'; " + ("frame-ancestors 'self'; " if same_origin_preview else "frame-ancestors 'none'; ") +
        "base-uri 'none'; form-action 'self'"
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def localized_http_errors(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": translate_error(exc.detail, selected_language(request))},
        headers=exc.headers,
    )


def new_id():
    return str(uuid.uuid4())


def money(v: int):
    return int(v or 0)


def fail(status: int, detail: str):
    raise HTTPException(status_code=status, detail=detail)


def current_user(request: Request, db: Session = Depends(db_session)):
    token = request.cookies.get("ez_session")
    if not token:
        fail(401, "Vui lòng đăng nhập")
    session = db.get(SessionToken, token_hash(token))
    if not session:
        fail(401, "Phiên đăng nhập không hợp lệ")
    expires = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    if expires <= datetime.now(timezone.utc):
        fail(401, "Phiên đăng nhập đã hết hạn")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("x-csrf-token") != session.csrf_token:
            fail(403, "Thiếu mã xác thực thao tác")
    user = db.get(User, session.user_id)
    if not user:
        fail(401, "Tài khoản không hợp lệ")
    from .platform_admin import is_user_blocked
    if is_user_blocked(db, user.id):
        fail(403, "Tài khoản đã bị tạm khóa")
    return user, session


def tenant(bid: str, user: tuple, db: Session) -> Business:
    u, _ = user
    member = db.scalar(select(Membership).where(Membership.business_id == bid, Membership.user_id == u.id))
    if not member:
        fail(404, "Không tìm thấy doanh nghiệp")
    business = db.get(Business, bid)
    if not business:
        fail(404, "Không tìm thấy doanh nghiệp")
    from .platform_admin import is_business_blocked
    if is_business_blocked(db, business.id):
        fail(403, "Doanh nghiệp đang bị tạm khóa")
    from .billing import require_access
    require_access(db, business)
    return business


def feature(b: Business, name: str):
    if name not in (b.active_modules or []):
        fail(403, "Chức năng không có trong gói đang kích hoạt")


def audit(db, bid, uid, action, payload=None):
    db.add(AuditEvent(id=new_id(), business_id=bid, actor_id=uid, action=action,
                      payload=json.dumps(payload or {}, ensure_ascii=False)))


def issue_session(db: Session, response: Response, user: User):
    token, digest, csrf, expires = session_pair()
    db.add(SessionToken(token_hash=digest, user_id=user.id, csrf_token=csrf, expires_at=expires))
    db.commit()
    response.set_cookie("ez_session", token, httponly=True, samesite="strict",
                        secure=os.getenv("COOKIE_SECURE", "0") == "1", max_age=604800, path="/")
    return {"id": user.id, "name": user.name, "email": user.email,
            "csrf_token": csrf, "demo": is_demo_user(user)}


@app.get("/api/health")
def health():
    """Cheap liveness probe; does not expose infrastructure details."""
    return {"ok": True, "version": "0.5.1"}


@app.get("/api/ready")
def ready(db: Session = Depends(db_session)):
    """Database-backed readiness for deploy validation and monitoring."""
    from sqlalchemy.exc import SQLAlchemyError
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"ok": True, "database": "ready"}


@app.get("/api/catalog")
def catalog(request: Request):
    lang = selected_language(request)
    features = FEATURES if lang == "vi" else {code: (labels[1], labels[1]) for code, labels in FEATURES.items()}
    industries = INDUSTRIES if lang == "vi" else INDUSTRIES_EN
    return {"plans": PLANS, "features": features, "industries": industries,
            "roadmap": ROADMAP, "language": lang, "supported_languages": ["vi", "en"]}


@app.get("/api/languages")
def languages(request: Request):
    return {"current": selected_language(request), "supported": ["vi", "en"],
            "default": "vi"}


# Staging-only, best-effort throttle. Production must use a shared rate limiter.
_demo_lock = Lock()
_demo_attempts = {}
_demo_global = deque()


def demo_rate_limit(request: Request):
    timestamp = datetime.now(timezone.utc).timestamp()
    # Trust the transport peer, never an unverified X-Forwarded-For header.
    peer = request.client.host if request.client else "unknown"
    with _demo_lock:
        while _demo_global and _demo_global[0] < timestamp - 3600:
            _demo_global.popleft()
        attempts = _demo_attempts.setdefault(peer, deque())
        while attempts and attempts[0] < timestamp - 3600:
            attempts.popleft()
        if len(attempts) >= 60 or len(_demo_global) >= 300:
            fail(429, "Quá nhiều phiên demo được tạo. Vui lòng thử lại sau.")
        attempts.append(timestamp)
        _demo_global.append(timestamp)
        # Drop expired peer buckets occasionally to bound memory usage.
        if len(_demo_attempts) > 1000:
            for key in list(_demo_attempts):
                if not _demo_attempts[key] or _demo_attempts[key][-1] < timestamp - 3600:
                    del _demo_attempts[key]


@app.get("/api/config")
def public_config(response: Response):
    response.headers["Cache-Control"] = "no-store"
    from .billing import trial_enabled
    result = {"demo_enabled": demo_enabled()}
    if trial_enabled():
        result["trial_enabled"] = True
    return result


@app.post("/api/auth/demo", status_code=201)
def enter_demo(request: Request, response: Response, db: Session = Depends(db_session)):
    # This is not an authentication bypass. It creates a new guest identity
    # and new private business tenants, then issues a normal scoped session.
    if not demo_enabled():
        fail(404, "Không có chế độ demo")
    demo_rate_limit(request)
    user = seed_demo(db)
    result = issue_session(db, response, user)
    response.headers["Cache-Control"] = "no-store"
    return result


@app.post("/api/auth/signup", status_code=201)
def signup(body: SignUp, response: Response, db: Session = Depends(db_session)):
    email = str(body.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        fail(409, "Email đã được sử dụng")
    u = User(id=new_id(), email=email, name=body.name.strip(), password_hash=digest_password(body.password))
    db.add(u)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        fail(409, "Email đã được sử dụng")
    return issue_session(db, response, u)


@app.post("/api/auth/login")
def login(body: Login, response: Response, db: Session = Depends(db_session)):
    """Limit password attempts per normalized email across workers (DB-backed)."""
    from .platform_admin import is_user_blocked
    identity = str(body.email).strip().lower()
    digest = hashlib.sha256(("login:" + identity).encode("utf-8")).hexdigest()
    attempt = db.scalar(select(LoginFailure).where(
        LoginFailure.identity_hash == digest).with_for_update())
    timestamp = now()
    def utc(v):
        return v.replace(tzinfo=timezone.utc) if v and v.tzinfo is None else v
    if attempt and utc(attempt.locked_until) and utc(attempt.locked_until) > timestamp:
        fail(429, "Quá nhiều lần đăng nhập thất bại. Thử lại sau 15 phút.")
    u = db.scalar(select(User).where(User.email == identity))
    if not u or not check_password(body.password, u.password_hash):
        if not attempt:
            attempt = LoginFailure(identity_hash=digest, failures=0, window_started_at=timestamp)
            db.add(attempt)
        if utc(attempt.window_started_at) < timestamp - timedelta(minutes=15):
            attempt.failures = 0
            attempt.window_started_at = timestamp
            attempt.locked_until = None
        attempt.failures += 1
        if attempt.failures >= 8:
            attempt.locked_until = timestamp + timedelta(minutes=15)
        try:
            db.commit()
        except IntegrityError:
            # Concurrent first wrong attempts may race on unique identity key.
            db.rollback()
        fail(401, "Email hoặc mật khẩu không chính xác")
    if is_user_blocked(db, u.id):
        fail(403, "Tài khoản đã bị tạm khóa")
    if attempt:
        db.delete(attempt)
    return issue_session(db, response, u)


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    u, session = user
    return {"id": u.id, "name": u.name, "email": u.email,
            "csrf_token": session.csrf_token, "demo": is_demo_user(u)}


@app.post("/api/auth/logout")
def logout(response: Response, user=Depends(current_user), db: Session = Depends(db_session)):
    db.delete(user[1]); db.commit(); response.delete_cookie("ez_session", path="/")
    return {"ok": True}


@app.post("/api/onboarding/recommend")
def onboard(body: OnboardAnswers, request: Request):
    """Deterministic recommendation (not a generative AI service)."""
    result = recommend(body.industry, body.need_tables, body.need_inventory, body.need_insights, body.need_branches)
    if selected_language(request) == "en":
        result["reason"] = RECOMMENDATION_EN
    return result


@app.post("/api/businesses", status_code=201)
def business_create(body: CreateBusiness, user=Depends(current_user), db: Session = Depends(db_session)):
    u, _ = user
    candidate = recommend(body.industry, body.need_tables, body.need_inventory,
                          body.need_insights, body.need_branches)
    plan = body.selected_plan or candidate["recommended_plan"]
    requested = candidate["requested_modules"]
    allowed = set(PLANS[plan]["features"])
    required = {"dashboard", "products", "orders"}
    active = sorted(((set(requested) | required) & allowed) | ({"inventory_adjust"} if body.need_inventory and "inventory_adjust" in allowed else set()))
    if "tables" in active and body.industry != "fnb":
        active.remove("tables")
    from .billing import trial_enabled, start_trial, industry_modules, BillingSubscription
    enable_trial = trial_enabled() and not is_demo_user(u)
    b = Business(id=new_id(), name=body.name.strip(), industry=body.industry, plan=plan,
                 requested_plan=plan, subscription_status="pilot", active_modules=active,
                 setup={"need_tables": body.need_tables, "need_inventory": body.need_inventory,
                        "need_insights": body.need_insights, "need_branches": body.need_branches,
                        "description": body.description})
    db.add(b)
    db.flush()
    if enable_trial:
        # A real account gets one seven-day trial, regardless of how many
        # businesses it creates. Additional business workspaces need a paid plan.
        previous = db.scalar(select(BillingSubscription.business_id)
            .join(Membership, Membership.business_id == BillingSubscription.business_id)
            .where(Membership.user_id == u.id))
        start_trial(db, b, u.id, days=0 if previous else 7)
        b.active_modules = industry_modules(b, "PRO")
    db.add(Membership(id=new_id(), user_id=u.id, business_id=b.id, role="owner"))
    db.add(Branch(id=new_id(), business_id=b.id, name="Chi nhánh chính"))
    audit(db, b.id, u.id, "business.created", {
        "subscription_status": b.subscription_status,
        "selected_plan": None if enable_trial else plan,
        "modules": b.active_modules,
    })
    db.commit()
    return business_out(b, db, u.id)


def business_out(b: Business, db: Session, user_id: str | None = None):
    from .billing import summary
    subscription = summary(db, b)
    from .team import role_for
    return {"id": b.id, "name": b.name, "industry": b.industry,
            "role": role_for(db, b.id, user_id) if user_id else None,
            "plan": subscription["plan"] or "TRIAL",
            "subscription_status": subscription["status"], "active_modules": b.active_modules,
            "trial_ends_at": subscription.get("trial_ends_at"),
            "trial_days_remaining": subscription.get("days_remaining"),
            "billing_required": subscription.get("requires_payment", False),
            "setup": b.setup}


@app.get("/api/businesses")
def business_list(user=Depends(current_user), db: Session = Depends(db_session)):
    ids = db.scalars(select(Membership.business_id).where(Membership.user_id == user[0].id)).all()
    return [business_out(b, db, user[0].id) for b in db.scalars(select(Business).where(Business.id.in_(ids)).order_by(Business.created_at.asc())).all()]


@app.get("/api/businesses/{bid}")
def business_get(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    return business_out(tenant(bid, user, db), db, user[0].id)


@app.get("/api/businesses/{bid}/overview")
def overview(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "dashboard")
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    local_day = datetime.now(tz).date()
    since = datetime.combine(local_day, time.min, tzinfo=tz).astimezone(timezone.utc)
    until = datetime.combine(local_day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    from .team import role_for
    can_view_revenue = role_for(db, bid, user[0].id) in ("owner", "manager")
    # All aggregate computations stay in SQL: no materialization of order history.
    count, opened, revenue, today_revenue = db.execute(select(
        func.count(SaleOrder.id),
        func.sum(case((SaleOrder.status == "open", 1), else_=0)),
        func.coalesce(func.sum(case(
            (SaleOrder.status == "paid", SaleOrder.total_vnd), else_=0)), 0),
        func.coalesce(func.sum(case((
            (SaleOrder.status == "paid") &
            (SaleOrder.paid_at >= since) &
            (SaleOrder.paid_at < until), SaleOrder.total_vnd
        ), else_=0)), 0),
    ).where(SaleOrder.business_id == bid)).one()
    return {"order_count": int(count), "open_count": int(opened or 0),
            "paid_revenue_vnd": int(revenue) if can_view_revenue else None,
            "today_revenue_vnd": int(today_revenue) if can_view_revenue else None,
            "product_count": db.scalar(select(func.count(Product.id)).where(Product.business_id == bid)) or 0,
            "low_stock": db.scalar(select(func.count(Product.id)).where(Product.business_id == bid,
                                              Product.track_stock.is_(True), Product.stock <= 5, Product.active.is_(True))) or 0,
            "branch_count": db.scalar(select(func.count(Branch.id)).where(Branch.business_id == bid)) or 0}


@app.get("/api/businesses/{bid}/branches")
def branches(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    return [{"id": br.id, "name": br.name} for br in db.scalars(select(Branch).where(Branch.business_id == bid))]


@app.post("/api/businesses/{bid}/branches", status_code=201)
def branch_create(bid: str, body: BranchCreate, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "multi_branch")
    from .team import allow, MANAGE_ROLES
    allow(db, bid, user, MANAGE_ROLES)
    if (db.scalar(select(func.count(Branch.id)).where(Branch.business_id == bid)) or 0) >= PLANS[b.plan]["branches"]:
        fail(403, "Đã đạt số chi nhánh của gói")
    br = Branch(id=new_id(), business_id=bid, name=body.name.strip())
    db.add(br); audit(db, bid, user[0].id, "branch.created", {"name": br.name})
    try: db.commit()
    except IntegrityError:
        db.rollback(); fail(409, "Tên chi nhánh đã tồn tại")
    return {"id": br.id, "name": br.name}


@app.get("/api/businesses/{bid}/products")
def products(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "products")
    from .team import role_for
    can_view_cost = role_for(db, bid, user[0].id) in ("owner", "manager")
    products = db.scalars(select(Product).where(Product.business_id == bid).order_by(Product.created_at.desc())).all()
    return [{**product_out(p), **({} if can_view_cost else {"cost_vnd": None})} for p in products]


def product_out(p):
    return {"id": p.id, "name": p.name, "sku": p.sku, "category": p.category,
            "price_vnd": p.price_vnd, "cost_vnd": p.cost_vnd, "stock": p.stock,
            "track_stock": p.track_stock, "active": p.active}


@app.post("/api/businesses/{bid}/products", status_code=201)
def product_create(bid: str, body: ProductCreate, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "products")
    from .team import allow, MANAGE_ROLES
    allow(db, bid, user, MANAGE_ROLES)
    p = Product(id=new_id(), business_id=bid, **body.model_dump())
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); fail(409, "Mã SKU đã tồn tại trong doanh nghiệp")
    if body.track_stock and body.stock:
        db.add(StockMovement(id=new_id(), business_id=bid, product_id=p.id,
                             delta=body.stock, reason="opening_stock"))
    audit(db, bid, user[0].id, "product.created", {"sku": body.sku})
    try: db.commit()
    except IntegrityError:
        db.rollback(); fail(409, "Mã SKU đã tồn tại trong doanh nghiệp")
    return product_out(p)


@app.post("/api/businesses/{bid}/products/{pid}/stock")
def stock_adjust(bid: str, pid: str, body: StockAdjust, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "inventory_adjust")
    from .team import allow, MANAGE_ROLES
    allow(db, bid, user, MANAGE_ROLES)
    p = db.scalar(select(Product).where(Product.id == pid, Product.business_id == bid))
    if not p or not p.track_stock:
        fail(404, "Không tìm thấy sản phẩm theo dõi kho")
    updated = db.execute(update(Product).where(Product.id == pid, Product.business_id == bid,
                                                Product.stock + body.delta >= 0).values(stock=Product.stock + body.delta))
    if not updated.rowcount:
        fail(409, "Số lượng tồn kho không đủ")
    db.add(StockMovement(id=new_id(), business_id=bid, product_id=pid,
                         delta=body.delta, reason=body.reason))
    audit(db, bid, user[0].id, "stock.adjusted", {"product_id": pid, "delta": body.delta})
    db.commit(); db.refresh(p)
    return product_out(p)


@app.get("/api/businesses/{bid}/customers")
def customers(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    return [customer_out(c) for c in db.scalars(select(Customer).where(Customer.business_id == bid).order_by(Customer.name))]


def customer_out(c):
    return {"id": c.id, "name": c.name, "phone": c.phone, "address": c.address}


@app.post("/api/businesses/{bid}/customers", status_code=201)
def customer_create(bid: str, body: CustomerCreate, user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    from .team import allow, ROLES
    allow(db, bid, user, ROLES)
    c = Customer(id=new_id(), business_id=bid, name=body.name.strip(),
                 phone=body.phone.strip(), address=body.address.strip())
    db.add(c); audit(db, bid, user[0].id, "customer.created", {"customer_id": c.id})
    db.commit(); return customer_out(c)


@app.get("/api/businesses/{bid}/tables")
def tables(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "tables")
    active = set(db.scalars(select(SaleOrder.table_id).where(SaleOrder.business_id == bid,
                                                            SaleOrder.status == "open", SaleOrder.table_id.is_not(None))).all())
    rows = db.scalars(select(DiningTable).where(DiningTable.business_id == bid).order_by(DiningTable.label)).all()
    return [{"id": t.id, "label": t.label, "seats": t.seats, "branch_id": t.branch_id,
             "occupied": t.id in active} for t in rows]


@app.post("/api/businesses/{bid}/tables", status_code=201)
def table_create(bid: str, body: TableCreate, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "tables")
    from .team import allow, MANAGE_ROLES
    allow(db, bid, user, MANAGE_ROLES)
    branch = branch_for(db, bid, body.branch_id)
    table = DiningTable(id=new_id(), business_id=bid, branch_id=branch.id,
                        label=body.label.strip(), seats=body.seats)
    db.add(table); audit(db, bid, user[0].id, "table.created", {"label": body.label})
    try: db.commit()
    except IntegrityError:
        db.rollback(); fail(409, "Tên bàn đã tồn tại trong chi nhánh")
    return {"id": table.id, "label": table.label, "seats": table.seats, "branch_id": table.branch_id}


def branch_for(db, bid, branch_id):
    if branch_id:
        br = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.business_id == bid))
    else:
        br = db.scalar(select(Branch).where(Branch.business_id == bid).order_by(Branch.created_at))
    if not br: fail(404, "Không tìm thấy chi nhánh")
    return br


def order_out(db, o, items=None):
    if items is None:
        items = db.scalars(select(SaleOrderItem).where(SaleOrderItem.order_id == o.id,
                                                      SaleOrderItem.business_id == o.business_id)).all()
    return {"id": o.id, "branch_id": o.branch_id, "table_id": o.table_id,
            "customer_id": o.customer_id, "status": o.status, "total_vnd": o.total_vnd,
            "note": o.note, "created_at": o.created_at.isoformat(),
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            "items": [{"product_id": x.product_id, "name": x.product_name,
                       "quantity": x.quantity, "unit_price_vnd": x.unit_price_vnd,
                       "total_vnd": x.total_vnd} for x in items]}


@app.get("/api/businesses/{bid}/orders")
def orders(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "orders")
    rows = db.scalars(select(SaleOrder).where(SaleOrder.business_id == bid)
                      .order_by(SaleOrder.created_at.desc()).limit(100)).all()
    if not rows:
        return []
    # One bounded query for order lines instead of one SELECT per order.
    items = db.scalars(select(SaleOrderItem).where(
        SaleOrderItem.business_id == bid,
        SaleOrderItem.order_id.in_([o.id for o in rows]))).all()
    by_order = defaultdict(list)
    for item in items:
        by_order[item.order_id].append(item)
    return [order_out(db, o, items=by_order[o.id]) for o in rows]


@app.post("/api/businesses/{bid}/orders", status_code=201)
def order_create(bid: str, body: CreateOrder, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "orders")
    fingerprint = hashlib.sha256(body.model_dump_json(exclude_none=True).encode()).hexdigest()
    old = db.scalar(select(SaleOrder).where(SaleOrder.business_id == bid,
                                            SaleOrder.idempotency_key == body.idempotency_key))
    if old:
        if old.request_fingerprint != fingerprint:
            fail(409, "Mã yêu cầu đã dùng cho giỏ hàng khác")
        return order_out(db, old)
    branch = branch_for(db, bid, body.branch_id)
    if body.customer_id and not db.scalar(select(Customer).where(Customer.id == body.customer_id,
                                                                 Customer.business_id == bid)):
        fail(404, "Không tìm thấy khách hàng")
    if body.table_id:
        feature(b, "tables")
        t = db.scalar(select(DiningTable).where(DiningTable.id == body.table_id,
                         DiningTable.business_id == bid, DiningTable.branch_id == branch.id))
        if not t: fail(404, "Bàn không thuộc chi nhánh")
    quantities = defaultdict(int)
    for ln in body.lines: quantities[ln.product_id] += ln.quantity
    products_by_id = {}
    for pid in quantities:
        p = db.scalar(select(Product).where(Product.id == pid, Product.business_id == bid, Product.active.is_(True)))
        if not p: fail(404, "Sản phẩm không tồn tại hoặc đã ngừng bán")
        products_by_id[pid] = p
    total = sum(products_by_id[pid].price_vnd * qty for pid, qty in quantities.items())
    if total > 9_000_000_000_000: fail(422, "Giá trị đơn vượt giới hạn")
    o = SaleOrder(id=new_id(), business_id=bid, branch_id=branch.id, table_id=body.table_id,
                  customer_id=body.customer_id, total_vnd=total, note=body.note,
                  idempotency_key=body.idempotency_key, request_fingerprint=fingerprint)
    try:
        db.add(o)
        db.flush()
        for pid, qty in quantities.items():
            p = products_by_id[pid]
            if p.track_stock:
                changed = db.execute(update(Product).where(Product.id == pid, Product.business_id == bid,
                                         Product.stock >= qty).values(stock=Product.stock - qty))
                if not changed.rowcount:
                    db.rollback(); fail(409, f"Không đủ tồn kho: {p.name}")
                db.add(StockMovement(id=new_id(), business_id=bid, product_id=pid,
                                     delta=-qty, reason="sale", ref=o.id))
            db.add(SaleOrderItem(id=new_id(), business_id=bid, order_id=o.id, product_id=pid,
                                 product_name=p.name, quantity=qty, unit_price_vnd=p.price_vnd,
                                 total_vnd=qty * p.price_vnd))
        audit(db, bid, user[0].id, "order.created", {"order_id": o.id, "total_vnd": total})
        db.commit()
    except IntegrityError:
        db.rollback()
        old = db.scalar(select(SaleOrder).where(SaleOrder.business_id == bid,
                                                SaleOrder.idempotency_key == body.idempotency_key))
        if old and old.request_fingerprint == fingerprint:
            return order_out(db, old)
        fail(409, "Đơn bị trùng hoặc xung đột dữ liệu")
    return order_out(db, o)


@app.post("/api/businesses/{bid}/orders/{oid}/paid")
def order_paid(bid: str, oid: str, body: ConfirmPayment, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "orders")
    from .team import allow, MANAGE_ROLES
    allow(db, bid, user, MANAGE_ROLES)
    # Lock before checking status: concurrent cancellation must not mark a
    # cancelled order as paid (or restore stock after a payment).
    o = db.scalar(select(SaleOrder).where(
        SaleOrder.id == oid, SaleOrder.business_id == bid).with_for_update())
    if not o: fail(404, "Không tìm thấy đơn")
    if o.status not in ("open", "paid"):
        fail(409, "Đơn đã hủy, không thể xác nhận thanh toán")
    if o.status == "open":
        o.status = "paid"; o.paid_at = now()
        audit(db, bid, user[0].id, "order.marked_paid_manual", {"order_id": oid})
        db.commit()
    return order_out(db, o)


@app.get("/api/businesses/{bid}/insights")
def insights(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "insights")
    from .team import allow, MANAGE_ROLES
    allow(db, bid, user, MANAGE_ROLES)
    rows = db.execute(select(SaleOrderItem.product_name,
                              func.sum(SaleOrderItem.quantity).label("qty"),
                              func.sum(SaleOrderItem.total_vnd).label("total"))
                      .join(SaleOrder, SaleOrder.id == SaleOrderItem.order_id)
                      .where(SaleOrderItem.business_id == bid, SaleOrder.status == "paid")
                      .group_by(SaleOrderItem.product_name)
                      .order_by(func.sum(SaleOrderItem.total_vnd).desc()).limit(5)).all()
    low = db.scalars(select(Product).where(Product.business_id == bid,
                                           Product.track_stock.is_(True), Product.active.is_(True),
                                           Product.stock <= 5).order_by(Product.stock).limit(10)).all()
    return {"top_products": [{"name": name, "quantity": int(qty), "revenue_vnd": int(total)}
                             for name, qty, total in rows],
            "low_stock": [{"name": p.name, "stock": p.stock} for p in low],
            "method": "deterministic_sql", "ai_generated": False}


@app.get("/api/businesses/{bid}/receivables")
def receivables(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db); feature(b, "insights")
    from .team import allow, MANAGE_ROLES
    allow(db, bid, user, MANAGE_ROLES)
    rows = db.execute(select(Customer.id, Customer.name, func.count(SaleOrder.id),
                             func.sum(SaleOrder.total_vnd))
                      .join(SaleOrder, SaleOrder.customer_id == Customer.id)
                      .where(Customer.business_id == bid, SaleOrder.business_id == bid,
                             SaleOrder.status == "open")
                      .group_by(Customer.id, Customer.name)
                      .order_by(func.sum(SaleOrder.total_vnd).desc())).all()
    customers = [{"id": cid, "name": name, "unpaid_count": count,
                  "unpaid_vnd": int(total)} for cid, name, count, total in rows]
    return {"customers": customers, "unpaid_vnd": sum(x["unpaid_vnd"] for x in customers),
            "definition": "Các đơn chưa ghi nhận thanh toán, có khách hàng được chỉ định; chưa hỗ trợ thanh toán một phần."}


@app.get("/api/businesses/{bid}/audit")
def audits(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    from .team import owner_only
    owner_only(db, bid, user)
    if b.plan != "PRO": fail(403, "Nhật ký quản trị chỉ dành cho Pro")
    rows = db.scalars(select(AuditEvent).where(AuditEvent.business_id == bid)
                      .order_by(AuditEvent.created_at.desc()).limit(50)).all()
    return [{"action": e.action, "created_at": e.created_at.isoformat()} for e in rows]


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ASSETS / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def sw():
    return FileResponse(ASSETS / "sw.js", media_type="application/javascript")


@app.get("/")
def index():
    return FileResponse(ASSETS / "public.html", headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/app/storefront-design")
def storefront_design_page():
    return FileResponse(ASSETS / "brand-editor.html", headers={"Cache-Control": "no-store"})


@app.get("/app/reservations")
def restaurant_reservation_manager():
    return RedirectResponse("/app?tab=reservations", status_code=307, headers={"Cache-Control": "no-store"})


@app.get("/app")
@app.get("/app/{path:path}")
def merchant_app(path: str = ""):
    return FileResponse(ASSETS / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/reserve/cafe")
def public_restaurant_reservation():
    return FileResponse(ASSETS / "reservation-public.html", headers={"Cache-Control": "no-store"})


@app.get("/menu/cafe")
@app.get("/store/mart")
@app.get("/store/online")
@app.get("/booking/wellness")
def customer_frontend():
    return FileResponse(ASSETS / "customer.html", headers={"Cache-Control": "no-store"})


@app.get("/admin")
def super_admin_frontend():
    return FileResponse(ASSETS / "admin.html", headers={"Cache-Control": "no-store"})


# Register industry workflows only after core auth/tenant dependencies are defined.
from .workflows import IndustryWorkItem, router as industry_router  # noqa: E402
Base.metadata.create_all(bind=engine)  # Pilot additive table; use Alembic before production.
app.include_router(industry_router)

# Public customer preview is scoped to staging-only guest tenants.
from .public import router as preview_router  # noqa: E402
app.include_router(preview_router)
# Platform control plane: safe additive pilot tables and protected API.
from .platform_admin import router as platform_admin_router  # noqa: E402
Base.metadata.create_all(bind=engine)  # Additive pilot only; requires Alembic for production.
app.include_router(platform_admin_router)

# Scoped restaurant table booking and customer contact requests.
from .reservations import router as reservations_router  # noqa: E402
app.include_router(reservations_router)

# Private tenant-specific branded storefront editor and owner previews.
from .storefront_brand import router as storefront_brand_router  # noqa: E402
app.include_router(storefront_brand_router)

# Tenant-scoped floorplan (existing Business.setup JSON; no migration or duplicate tables).
from .floorplan import router as floorplan_router  # noqa: E402
app.include_router(floorplan_router)

# Server-side order KPIs and filtered history for the same existing ledger.
from .order_dashboard import router as order_dashboard_router  # noqa: E402
app.include_router(order_dashboard_router)

# Order cancellation shares the SaleOrder ledger, stock movements and existing audit log.
from .order_lifecycle import router as order_lifecycle_router  # noqa: E402
app.include_router(order_lifecycle_router)

# Opt-in 7-day trial and VNPAY Sandbox billing; create new tables only.
from .billing import router as billing_router  # noqa: E402
Base.metadata.create_all(bind=engine)  # Pilot only; replace with versioned migrations before production.
app.include_router(billing_router)

# Team invitation storage is a pilot additive table until Alembic migration.
from .team import router as team_router  # noqa: E402
Base.metadata.create_all(bind=engine)
app.include_router(team_router)

