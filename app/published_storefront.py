"""Opt-in, public, tenant-scoped storefront and contact leads.

Only explicitly published non-demo tenants with active access are public.
No customer order, payment or inventory change occurs from guest enquiries.
"""
from __future__ import annotations
import hashlib
import os
import re
import secrets
import uuid
import unicodedata
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import Business, LoginFailure, Product, StorefrontMedia, now
from .main import ASSETS, audit, current_user, tenant
from .team import owner_only, allow, MANAGE_ROLES
from .storefront_brand import effective_brand
from .workflows import IndustryWorkItem

router = APIRouter(tags=["Real tenant storefronts"])
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED = {"admin", "api", "app", "assets", "demo", "preview", "www", "ezthing"}


class PublicSite(Base):
    __tablename__ = "public_storefronts"
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SiteSettings(BaseModel):
    slug: str = Field(min_length=3, max_length=60)
    published: bool = False

    @field_validator("slug")
    @classmethod
    def slug_safe(cls, v):
        if not SLUG_PATTERN.fullmatch(v) or v in RESERVED:
            raise ValueError("Chỉ dùng chữ thường, số và dấu gạch ngang trong địa chỉ")
        return v


class ContactRequest(BaseModel):
    request_id: str = Field(min_length=12, max_length=80)
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=30)
    message: str = Field(min_length=4, max_length=500)
    product_id: str | None = Field(default=None, max_length=36)


class LeadStatus(BaseModel):
    status: str = Field(pattern=r"^(contacted|closed)$")


def suggested_slug(b: Business) -> str:
    raw = b.name.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", raw)
    normalized = normalized.encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")[:42].strip("-")
    return (slug or "cua-hang") + "-" + b.id.replace("-", "")[:6]


def valid_public(db: Session, slug: str) -> Business:
    if not SLUG_PATTERN.fullmatch(slug) or len(slug) > 60:
        raise HTTPException(404, "Không tìm thấy cửa hàng")
    row = db.scalar(select(PublicSite).where(
        PublicSite.slug == slug, PublicSite.published.is_(True)))
    if row is None:
        raise HTTPException(404, "Cửa hàng chưa được xuất bản")
    b = db.get(Business, row.business_id)
    if b is None or b.subscription_status == "demo":
        raise HTTPException(404, "Không tìm thấy cửa hàng")
    from .platform_admin import is_business_blocked
    from .billing import summary
    if is_business_blocked(db, b.id) or summary(db, b)["requires_payment"]:
        raise HTTPException(404, "Cửa hàng đang tạm ngưng")
    return b


def serialize(row: PublicSite | None, b: Business):
    return {
        "slug": row.slug if row else suggested_slug(b),
        "published": bool(row and row.published),
        "public_url": "/shop/" + row.slug if row and row.published else None,
        "accepting_payments": False,
        "notice": "Trang giới thiệu và nhận yêu cầu liên hệ; chưa tự động nhận tiền.",
    }


@router.get("/api/businesses/{bid}/publishing")
def get_publishing(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    owner_only(db, bid, user)
    return serialize(db.get(PublicSite, bid), b)


@router.put("/api/businesses/{bid}/publishing")
def save_publishing(bid: str, body: SiteSettings,
                    user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    owner_only(db, bid, user)
    if b.subscription_status == "demo":
        raise HTTPException(403, "Không được xuất bản cửa hàng DEMO")
    row = db.scalar(select(PublicSite).where(
        PublicSite.business_id == bid).with_for_update())
    if row is None:
        row = PublicSite(business_id=bid, slug=body.slug, published=body.published)
        db.add(row)
    else:
        row.slug = body.slug
        row.published = body.published
    audit(db, bid, user[0].id, "storefront.publishing", {
        "published": body.published, "slug": body.slug})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Địa chỉ cửa hàng đã được đăng ký")
    return serialize(row, b)


@router.get("/shop/{slug}")
def public_site_page(slug: str):
    # This HTML is static; product, branding and publish state are checked by API.
    if not SLUG_PATTERN.fullmatch(slug) or len(slug) > 60:
        raise HTTPException(404, "Địa chỉ không hợp lệ")
    from .asset_pipeline import STATIC_ASSETS
    return STATIC_ASSETS.page("public-shop.html")


@router.get("/api/public/shops/{slug}")
def public_catalog(slug: str, db: Session = Depends(db_session)):
    b = valid_public(db, slug)
    photos = effective_brand(b)
    products = db.scalars(select(Product).where(
        Product.business_id == b.id, Product.active.is_(True))
        .order_by(Product.category, Product.name).limit(100)).all()
    from .modifiers import configs, exposed_groups
    modifier_configs = configs(db, b.id, [p.id for p in products])
    # No costs, raw stock numbers, customer records, staff or private settings.
    brand = {k: photos.get(k, "") for k in
             ("display_name", "description", "phone", "address",
              "banner_image", "hero_title", "accent_color", "logo_url",
              "logo_image", "banner_position_x", "banner_position_y",
              "logo_position_x", "logo_position_y", "footer_note")}
    if photos.get("banner_uploaded"):
        brand["banner_image"] = f"/api/public/shops/{slug}/media/banner"
    if photos.get("logo_uploaded"):
        brand["logo_image"] = f"/api/public/shops/{slug}/media/logo"
    return {
        "name": b.name, "industry": b.industry,
        "branding": brand,
        "products": [{"id": p.id, "name": p.name, "category": p.category,
                      "price_vnd": p.price_vnd,
                      "available": not p.track_stock or p.stock > 0,
                      "modifier_groups": exposed_groups(modifier_configs.get(p.id, []))}
                     for p in products],
        "contact_only": True, "online_payment": False,
    }


@router.get("/api/public/shops/{slug}/media/{kind}")
def public_brand_media(
    slug: str, kind: str, db: Session = Depends(db_session),
):
    # Only explicitly published, eligible storefronts expose their branding.
    business = valid_public(db, slug)
    if kind not in ("banner", "logo"):
        raise HTTPException(404, "Không tìm thấy loại ảnh")
    branding = effective_brand(business)
    if not branding.get(f"{kind}_uploaded"):
        raise HTTPException(404, "Ảnh chưa được xuất bản")
    image = db.get(StorefrontMedia, (business.id, kind))
    if image is None:
        raise HTTPException(404, "Ảnh không tồn tại")
    return Response(content=image.data, media_type="image/webp",
                    headers={"Cache-Control": "public, max-age=300",
                             "X-Content-Type-Options": "nosniff"})


@router.post("/api/public/shops/{slug}/inquiries", status_code=201)
def public_inquiry(slug: str, body: ContactRequest, request: Request,
                   db: Session = Depends(db_session)):
    b = valid_public(db, slug)
    # Origin control is a CSRF hardening layer; rate limiting handles scripts.
    origin = request.headers.get("origin")
    if origin:
        # Render's TLS proxy may provide an internal HTTP base_url.
        # Trust only the configured canonical public origin or ASGI origin.
        trusted = {str(request.base_url).rstrip("/")}
        canonical = os.getenv("EZ_THING_PUBLIC_BASE_URL", "").rstrip("/")
        if canonical.startswith("https://") and "/" not in canonical[8:]:
            trusted.add(canonical)
        if origin not in trusted:
            raise HTTPException(403, "Yêu cầu không đúng nguồn")
    fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    ref = hashlib.sha256((b.id + "|public-inquiry|" + body.request_id).encode()).hexdigest()[:36]
    existing = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == b.id,
        IndustryWorkItem.kind == "public_leads",
        IndustryWorkItem.reference_id == ref))
    if existing:
        if (existing.details or {}).get("fingerprint") != fingerprint:
            raise HTTPException(409, "Mã yêu cầu đã được sử dụng")
        return {"id": existing.id, "status": existing.status}
    if body.product_id and db.scalar(select(Product.id).where(
        Product.business_id == b.id, Product.id == body.product_id,
        Product.active.is_(True))) is None:
        raise HTTPException(404, "Sản phẩm không tồn tại")

    peer = request.client.host if request.client else "unknown"
    salt = os.environ.get("EZ_THING_RATE_LIMIT_SALT", "ezthing-pilot-v1")
    hashed_peer = hashlib.sha256((salt + "|site|" + b.id + "|" + peer).encode()).hexdigest()
    guard = db.scalar(select(LoginFailure).where(
        LoginFailure.identity_hash == hashed_peer).with_for_update())
    timestamp = now()
    if not guard:
        guard = LoginFailure(identity_hash=hashed_peer, failures=0,
                             window_started_at=timestamp)
        db.add(guard)
    started = guard.window_started_at.replace(tzinfo=timezone.utc) if guard.window_started_at.tzinfo is None else guard.window_started_at
    if started < timestamp - timedelta(hours=24):
        guard.failures = 0
        guard.window_started_at = timestamp
    if guard.failures >= 15:
        raise HTTPException(429, "Đã đạt giới hạn yêu cầu liên hệ trong ngày")
    guard.failures += 1
    item = IndustryWorkItem(
        id=str(uuid.uuid4()), business_id=b.id, kind="public_leads",
        reference_id=ref, product_id=body.product_id,
        title="Khách liên hệ từ website", status="new",
        details={
            "name": body.name.strip(), "phone": body.phone.strip(),
            "message": body.message.strip(), "fingerprint": fingerprint,
            "source": "published_storefront",
        })
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Yêu cầu đã được xử lý, vui lòng thử lại")
    return {"id": item.id, "status": item.status}


@router.get("/api/businesses/{bid}/public-leads")
def list_public_leads(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    allow(db, bid, user, MANAGE_ROLES)
    rows = db.scalars(select(IndustryWorkItem).where(
        IndustryWorkItem.business_id == bid, IndustryWorkItem.kind == "public_leads")
        .order_by(IndustryWorkItem.created_at.desc()).limit(100)).all()
    return [{"id": x.id, "status": x.status, "product_id": x.product_id,
             "name": (x.details or {}).get("name", ""),
             "phone": (x.details or {}).get("phone", ""),
             "message": (x.details or {}).get("message", ""),
             "created_at": x.created_at.isoformat()} for x in rows]


@router.post("/api/businesses/{bid}/public-leads/{iid}/status")
def set_public_lead_status(bid: str, iid: str, body: LeadStatus,
                           user=Depends(current_user), db: Session = Depends(db_session)):
    tenant(bid, user, db)
    allow(db, bid, user, MANAGE_ROLES)
    item = db.scalar(select(IndustryWorkItem).where(
        IndustryWorkItem.id == iid, IndustryWorkItem.business_id == bid,
        IndustryWorkItem.kind == "public_leads").with_for_update())
    if not item:
        raise HTTPException(404, "Không tìm thấy yêu cầu")
    if item.status == "closed" or (item.status == "new" and body.status != "contacted"):
        raise HTTPException(409, "Trạng thái không hợp lệ")
    item.status = body.status
    audit(db, bid, user[0].id, "public_lead.status", {"lead_id": iid, "status": body.status})
    db.commit()
    return {"ok": True, "status": item.status}
