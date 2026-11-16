"""Tenant-specific actual product photos for POS and published storefronts.

A bounded image is decoded, EXIF-transposed, metadata-stripped, and saved as
WebP in PostgreSQL. Never write merchant uploads to ephemeral Render disks.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import Product, now
from .main import current_user, tenant, feature, audit
from .team import MANAGE_ROLES, allow
from .storefront_brand import _normalized_image, MAX_INPUT_BYTES

router = APIRouter(tags=["Product media"])


class ProductMedia(Base):
    __tablename__ = "product_media"
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False, default="image/webp")
    revision: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


def product_for_tenant(db: Session, bid: str, pid: str) -> Product:
    product = db.scalar(select(Product).where(Product.business_id == bid, Product.id == pid))
    if not product:
        raise HTTPException(404, "Sản phẩm không thuộc doanh nghiệp")
    return product


def public_image_path(slug: str, pid: str, revision: str) -> str:
    return f"/api/public/shops/{slug}/products/{pid}/photo?v={revision}"


def private_image_path(bid: str, pid: str, revision: str) -> str:
    return f"/api/businesses/{bid}/products/{pid}/photo?v={revision}"


@router.put("/api/businesses/{bid}/products/{pid}/photo")
async def upload_product_photo(
    bid: str, pid: str, file: UploadFile = File(...),
    user=Depends(current_user), db: Session = Depends(db_session)
):
    business = tenant(bid, user, db)
    feature(business, "products")
    allow(db, bid, user, MANAGE_ROLES)
    product_for_tenant(db, bid, pid)
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(422, "Chỉ hỗ trợ ảnh JPEG, PNG, WebP")
    raw = await file.read(MAX_INPUT_BYTES + 1)
    await file.close()
    photo = _normalized_image(raw, "product")
    revision = secrets.token_hex(8)
    entry = db.get(ProductMedia, pid)
    if entry is None:
        entry = ProductMedia(product_id=pid, business_id=bid,
                             data=photo, content_type="image/webp", revision=revision)
        db.add(entry)
    else:
        if entry.business_id != bid:
            raise HTTPException(404, "Ảnh không thuộc doanh nghiệp")
        entry.data = photo
        entry.revision = revision
        entry.updated_at = now()
    audit(db, bid, user[0].id, "product.photo_uploaded",
          {"product_id": pid, "size_bytes": len(photo)})
    db.commit()
    return {"product_id": pid, "image_url": private_image_path(bid, pid, revision),
            "size_bytes": len(photo)}


@router.get("/api/businesses/{bid}/products/{pid}/photo")
def get_product_photo(
    bid: str, pid: str,
    user=Depends(current_user), db: Session = Depends(db_session)
):
    business = tenant(bid, user, db)
    feature(business, "products")
    product_for_tenant(db, bid, pid)
    image = db.scalar(select(ProductMedia).where(
        ProductMedia.business_id == bid, ProductMedia.product_id == pid))
    if not image:
        raise HTTPException(404, "Sản phẩm chưa có ảnh")
    return Response(content=image.data, media_type="image/webp",
                    headers={"Cache-Control": "private, max-age=300",
                             "X-Content-Type-Options": "nosniff"})


@router.delete("/api/businesses/{bid}/products/{pid}/photo")
def delete_product_photo(
    bid: str, pid: str,
    user=Depends(current_user), db: Session = Depends(db_session)
):
    business = tenant(bid, user, db)
    feature(business, "products")
    allow(db, bid, user, MANAGE_ROLES)
    product_for_tenant(db, bid, pid)
    entry = db.scalar(select(ProductMedia).where(
        ProductMedia.business_id == bid, ProductMedia.product_id == pid))
    if entry:
        db.delete(entry)
        audit(db, bid, user[0].id, "product.photo_deleted", {"product_id": pid})
        db.commit()
    return {"ok": True, "product_id": pid, "image_url": None}


@router.get("/api/public/shops/{slug}/products/{pid}/photo")
def public_product_photo(
    slug: str, pid: str, db: Session = Depends(db_session)
):
    from .published_storefront import valid_public
    business = valid_public(db, slug)
    product = db.scalar(select(Product).where(
        Product.business_id == business.id, Product.id == pid,
        Product.active.is_(True)))
    if not product:
        raise HTTPException(404, "Không tìm thấy sản phẩm")
    photo = db.scalar(select(ProductMedia).where(
        ProductMedia.business_id == business.id, ProductMedia.product_id == pid))
    if not photo:
        raise HTTPException(404, "Ảnh không tồn tại")
    return Response(content=photo.data, media_type="image/webp",
                    headers={"Cache-Control": "public, max-age=600",
                             "X-Content-Type-Options": "nosniff"})
