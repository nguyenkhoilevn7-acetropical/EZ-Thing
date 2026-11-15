"""Per-business storefront appearance and pilot-tier entitlements.

Use Business.setup JSON for pilot to avoid an unversioned schema change.
This is owner-only preview functionality. It never publishes a public shop.
"""
from __future__ import annotations

import re
import secrets
from io import BytesIO
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import PLANS
from .database import db_session
from .models import Business, Membership, Product, StorefrontMedia
from .main import ASSETS, audit, current_user, tenant
from .i18n import selected_language

router = APIRouter(tags=["Storefront customization"])

# Preset photo IDs are server controlled. Never interpolate user-provided CSS/HTML.
BANNERS = {
    "coffee": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=1600&auto=format&fit=crop&q=85",
    "dining": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1600&auto=format&fit=crop&q=85",
    "retail": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=1600&auto=format&fit=crop&q=85",
    "online": "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=1600&auto=format&fit=crop&q=85",
    "wellness": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1600&auto=format&fit=crop&q=85",
}
DEFAULT_PRESET = {"fnb": "dining", "retail": "retail", "online": "online", "services": "wellness"}

BASE_FIELDS = {"display_name", "description", "phone", "address", "banner_preset"}
PLUS_FIELDS = BASE_FIELDS | {"hero_title", "accent_color", "banner_url", "logo_url",
                             "banner_position_x", "banner_position_y",
                             "logo_position_x", "logo_position_y"}
PRO_FIELDS = PLUS_FIELDS | {"layout_style", "footer_note"}
TIER_FIELDS = {"BASIC": BASE_FIELDS, "PLUS": PLUS_FIELDS, "PRO": PRO_FIELDS}
ALLOWED_ACCENTS = {"#147D64", "#BF506C", "#2B62A9", "#7556A8", "#C26D30"}
UNSPLASH_URL = re.compile(
    r"^https://images\.unsplash\.com/photo-[0-9]+-[a-zA-Z0-9]+"
    r"(?:\?[a-zA-Z0-9_=&%.-]*)?$"
)

PLANS_BRANDING = {
    "BASIC": {
        "vi": ["Tên và mô tả riêng", "Liên hệ & địa chỉ", "Banner mẫu", "Xem trước trang riêng tư"],
        "en": ["Custom name and description", "Contact and address", "Preset banner", "Private storefront preview"],
    },
    "PLUS": {
        "vi": ["Tất cả BASIC", "Banner và logo bằng URL ảnh hợp lệ", "Tiêu đề hero và màu thương hiệu"],
        "en": ["Everything in BASIC", "Logo and banner from approved image links", "Hero title and brand color"],
    },
    "PRO": {
        "vi": ["Tất cả PLUS", "3 kiểu bố cục", "Thông điệp cuối trang", "Tối đa 10 chi nhánh theo gói"],
        "en": ["Everything in PLUS", "3 layout styles", "Custom footer note", "Up to 10 branches under the plan"],
    },
}


class StorefrontUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=280)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=250)
    banner_preset: Literal["coffee", "dining", "retail", "online", "wellness"] | None = None
    hero_title: str | None = Field(default=None, max_length=100)
    accent_color: Literal["#147D64", "#BF506C", "#2B62A9", "#7556A8", "#C26D30"] | None = None
    banner_url: str | None = Field(default=None, max_length=350)
    logo_url: str | None = Field(default=None, max_length=350)
    banner_position_x: int | None = Field(default=None, ge=0, le=100)
    banner_position_y: int | None = Field(default=None, ge=0, le=100)
    logo_position_x: int | None = Field(default=None, ge=0, le=100)
    logo_position_y: int | None = Field(default=None, ge=0, le=100)
    layout_style: Literal["classic", "editorial", "gallery"] | None = None
    footer_note: str | None = Field(default=None, max_length=160)

    @field_validator("banner_url", "logo_url")
    @classmethod
    def validated_image_url(cls, value):
        if value is None or not value.strip():
            return ""
        value = value.strip()
        if not UNSPLASH_URL.fullmatch(value):
            raise ValueError("Chỉ hỗ trợ URL HTTPS từ images.unsplash.com trong bản pilot")
        return value

    @field_validator("display_name")
    @classmethod
    def validated_name(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Tên cửa hàng không được để trống")
        return value.strip() if value is not None else None


def effective_brand(b: Business) -> dict:
    saved = dict((b.setup or {}).get("storefront") or {})
    tier = b.plan if b.plan in TIER_FIELDS else "BASIC"
    allowed = TIER_FIELDS[tier]
    default = DEFAULT_PRESET.get(b.industry, "dining")
    preset = saved.get("banner_preset", default)
    if preset not in BANNERS:
        preset = default
    result = {
        "display_name": b.name,
        "description": saved.get("description", (b.setup or {}).get("description", "")),
        "phone": saved.get("phone", ""),
        "address": saved.get("address", ""),
        "banner_preset": preset,
        "hero_title": saved.get("hero_title", "") if "hero_title" in allowed else "",
        "accent_color": saved.get("accent_color", "#147D64") if "accent_color" in allowed else "#147D64",
        "banner_url": saved.get("banner_url", "") if "banner_url" in allowed else "",
        "logo_url": saved.get("logo_url", "") if "logo_url" in allowed else "",
        "banner_position_x": saved.get("banner_position_x", 50) if "banner_position_x" in allowed else 50,
        "banner_position_y": saved.get("banner_position_y", 50) if "banner_position_y" in allowed else 50,
        "logo_position_x": saved.get("logo_position_x", 50) if "logo_position_x" in allowed else 50,
        "logo_position_y": saved.get("logo_position_y", 50) if "logo_position_y" in allowed else 50,
        "layout_style": saved.get("layout_style", "classic") if "layout_style" in allowed else "classic",
        "footer_note": saved.get("footer_note", "") if "footer_note" in allowed else "",
    }
    result["banner_uploaded"] = bool(saved.get("banner_uploaded")) if "banner_url" in allowed else False
    result["logo_uploaded"] = bool(saved.get("logo_uploaded")) if "logo_url" in allowed else False
    banner_asset = f"/api/businesses/{b.id}/storefront-media/banner?v={saved.get('banner_asset_rev', '')}"
    logo_asset = f"/api/businesses/{b.id}/storefront-media/logo?v={saved.get('logo_asset_rev', '')}"
    result["banner_image"] = (banner_asset if result["banner_uploaded"]
                              else result["banner_url"] or BANNERS[preset])
    result["logo_image"] = logo_asset if result["logo_uploaded"] else result["logo_url"]
    return result


def result_for_business(b: Business) -> dict:
    tier = b.plan if b.plan in TIER_FIELDS else "BASIC"
    return {
        "business_id": b.id,
        "industry": b.industry,
        "plan": tier,
        "plan_pilot": b.subscription_status in ("pilot", "demo"),
        "published": False,
        "notice": "Bản xem trước chỉ dành cho chủ cửa hàng; chưa công khai để nhận đơn thật.",
        "preview_url": f"/preview/site/{b.id}",
        "editable_fields": sorted(TIER_FIELDS[tier]),
        "branding": effective_brand(b),
        "presets": BANNERS,
        "plans": PLANS_BRANDING,
    }


def assert_owner(db: Session, bid: str, uid: str):
    membership = db.scalar(
        select(Membership).where(
            Membership.business_id == bid, Membership.user_id == uid,
        )
    )
    if membership is None or membership.role != "owner":
        raise HTTPException(403, "Chỉ chủ doanh nghiệp mới có quyền sửa thương hiệu")


@router.get("/api/storefront/plans")
def storefront_plans():
    return {
        "plans": {name: {"name": name, "price_vnd": item["price_vnd"],
                          "branches": item["branches"], "branding": PLANS_BRANDING[name],
                          "fields": sorted(TIER_FIELDS[name])}
                  for name, item in PLANS.items()},
        "pilot": True,
        "public_publishing": False,
    }


@router.get("/api/businesses/{bid}/storefront")
def get_storefront(bid: str, user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    return result_for_business(b)


@router.patch("/api/businesses/{bid}/storefront")
def edit_storefront(bid: str, body: StorefrontUpdate, request: Request,
                    user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    assert_owner(db, bid, user[0].id)
    changes = body.model_dump(exclude_unset=True)
    changes = {k: v for k, v in changes.items() if v is not None}
    forbidden = sorted(set(changes) - TIER_FIELDS.get(b.plan, BASE_FIELDS))
    if forbidden:
        raise HTTPException(403, detail={
            "code": "BRANDING_PLAN_REQUIRED",
            "fields": forbidden,
            "message": ("This customization is not available on your current plan"
                        if selected_language(request) == "en"
                        else "Tính năng tùy chỉnh này chưa có trong gói hiện tại"),
        })
    if "display_name" in changes:
        b.name = changes.pop("display_name")
    setup = dict(b.setup or {})
    saved = dict(setup.get("storefront") or {})
    # A newly selected external URL supersedes an earlier upload. Empty URL
    # fields do not disable an existing uploaded asset.
    if changes.get("banner_url"):
        saved["banner_uploaded"] = False
    if changes.get("logo_url"):
        saved["logo_uploaded"] = False
    saved.update(changes)
    setup["storefront"] = saved
    b.setup = setup
    audit(db, bid, user[0].id, "storefront.updated",
          {"changed": sorted(set(body.model_fields_set))})
    db.commit()
    db.refresh(b)
    return result_for_business(b)


MAX_INPUT_BYTES = 6 * 1024 * 1024
MEDIA_LIMITS = {"banner": (1920, 1200, 850_000),
                "logo": (800, 800, 350_000)}


def _normalized_image(content: bytes, kind: str) -> bytes:
    """Decode and re-encode to trusted WebP, strip metadata, bound disk/DB size."""
    if not content or len(content) > MAX_INPUT_BYTES:
        raise HTTPException(413, "Ảnh không được vượt quá 6 MB")
    try:
        with Image.open(BytesIO(content)) as original:
            if original.format not in ("JPEG", "PNG", "WEBP"):
                raise HTTPException(422, "Chỉ hỗ trợ ảnh JPEG, PNG hoặc WebP")
            if original.width * original.height > 20_000_000:
                raise HTTPException(413, "Kích thước ảnh quá lớn")
            original.load()
            edited = ImageOps.exif_transpose(original)
            edited.thumbnail(MEDIA_LIMITS[kind][:2], Image.Resampling.LANCZOS)
            if edited.mode in ("RGBA", "LA") or "transparency" in edited.info:
                edited = edited.convert("RGBA")
            else:
                edited = edited.convert("RGB")
            limit = MEDIA_LIMITS[kind][2]
            for quality in (84, 74, 62, 50):
                result = BytesIO()
                edited.save(result, format="WEBP", quality=quality, method=4)
                if result.tell() <= limit:
                    return result.getvalue()
            raise HTTPException(413, "Ảnh quá phức tạp, vui lòng chọn ảnh nhỏ hơn")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as err:
        raise HTTPException(422, "Dữ liệu ảnh không hợp lệ") from err


def _edit_media_owner(db, bid, user):
    business = tenant(bid, user, db)
    assert_owner(db, bid, user[0].id)
    if business.plan not in ("PLUS", "PRO"):
        raise HTTPException(403, "Gói PLUS trở lên mới có quyền tải ảnh riêng")
    return business


@router.put("/api/businesses/{bid}/storefront-media/{kind}")
async def upload_storefront_media(
    bid: str, kind: Literal["banner", "logo"], file: UploadFile = File(...),
    user=Depends(current_user), db: Session = Depends(db_session),
):
    b = _edit_media_owner(db, bid, user)
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(422, "Chỉ hỗ trợ JPEG, PNG hoặc WebP")
    raw = await file.read(MAX_INPUT_BYTES + 1)
    await file.close()
    image = _normalized_image(raw, kind)
    revision = secrets.token_hex(8)
    media = db.get(StorefrontMedia, (bid, kind))
    if media is None:
        media = StorefrontMedia(business_id=bid, kind=kind,
                               content_type="image/webp", data=image, revision=revision)
        db.add(media)
    else:
        media.data = image
        media.content_type = "image/webp"
        media.revision = revision
    setup = dict(b.setup or {})
    saved = dict(setup.get("storefront") or {})
    saved[f"{kind}_uploaded"] = True
    saved[f"{kind}_asset_rev"] = revision
    saved[f"{kind}_url"] = ""
    setup["storefront"] = saved
    b.setup = setup
    audit(db, bid, user[0].id, "storefront.media.uploaded",
          {"kind": kind, "byte_size": len(image)})
    db.commit()
    db.refresh(b)
    return result_for_business(b)


@router.get("/api/businesses/{bid}/storefront-media/{kind}")
def get_storefront_media(
    bid: str, kind: Literal["banner", "logo"],
    user=Depends(current_user), db: Session = Depends(db_session),
):
    tenant(bid, user, db)
    media = db.get(StorefrontMedia, (bid, kind))
    if media is None:
        raise HTTPException(404, "Ảnh chưa được tải lên")
    return Response(content=media.data, media_type=media.content_type,
                    headers={"Cache-Control": "private, max-age=300",
                             "X-Content-Type-Options": "nosniff"})


@router.delete("/api/businesses/{bid}/storefront-media/{kind}")
def delete_storefront_media(
    bid: str, kind: Literal["banner", "logo"],
    user=Depends(current_user), db: Session = Depends(db_session),
):
    b = _edit_media_owner(db, bid, user)
    media = db.get(StorefrontMedia, (bid, kind))
    if media is not None:
        db.delete(media)
    setup = dict(b.setup or {})
    saved = dict(setup.get("storefront") or {})
    saved[f"{kind}_uploaded"] = False
    saved[f"{kind}_asset_rev"] = ""
    setup["storefront"] = saved
    b.setup = setup
    audit(db, bid, user[0].id, "storefront.media.deleted", {"kind": kind})
    db.commit()
    db.refresh(b)
    return result_for_business(b)


@router.get("/api/businesses/{bid}/storefront-preview")
def owner_storefront_preview_data(
    bid: str, user=Depends(current_user), db: Session = Depends(db_session),
):
    b = tenant(bid, user, db)
    assert_owner(db, bid, user[0].id)
    products = db.scalars(
        select(Product).where(Product.business_id == bid, Product.active.is_(True))
        .order_by(Product.created_at.desc()).limit(48)
    ).all()
    return {
        "preview_only": True,
        "published": False,
        "business": {"name": b.name, "industry": b.industry,
                     "branding": effective_brand(b)},
        "products": [
            {"id": p.id, "name": p.name, "category": p.category,
             "price_vnd": p.price_vnd} for p in products
        ],
    }


@router.get("/preview/site/{bid}")
def owner_storefront_preview_page(
    bid: str, user=Depends(current_user), db: Session = Depends(db_session),
):
    tenant(bid, user, db)
    assert_owner(db, bid, user[0].id)
    from .asset_pipeline import STATIC_ASSETS
    return STATIC_ASSETS.page("storefront-owner-preview.html")
