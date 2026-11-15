"""EZ Thing product option groups (sizes, toppings) and immutable order snapshots.

Prices and required choices are enforced on the server for both merchant POS
and publicly reviewed orders. Tenants never share configurations. No customer
payment is taken by this module.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, db_session
from .models import Product, SaleOrderItem
from .main import audit, current_user, feature, tenant
from .team import allow, MANAGE_ROLES

router = APIRouter(tags=["Product add-ons and modifier groups"])


class ProductModifierSet(Base):
    __tablename__ = "product_modifier_sets"
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    groups: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class SaleOrderItemModifier(Base):
    __tablename__ = "sale_order_item_modifiers"
    item_id: Mapped[str] = mapped_column(ForeignKey("sale_order_items.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    selections: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class OptionIn(BaseModel):
    id: str = Field(min_length=3, max_length=48, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=90)
    price_vnd: int = Field(default=0, ge=0, le=2_000_000_000)
    inventory_product_id: str | None = Field(default=None, max_length=36)
    inventory_quantity: int = Field(default=1, ge=1, le=1000)


class GroupIn(BaseModel):
    id: str = Field(min_length=3, max_length=48, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=90)
    min_select: int = Field(default=0, ge=0, le=20)
    max_select: int = Field(default=1, ge=1, le=20)
    options: list[OptionIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def check_counts(self):
        if self.min_select > self.max_select or self.max_select > len(self.options):
            raise ValueError("Giới hạn chọn không phù hợp số tùy chọn")
        return self


class ModifierSetUpdate(BaseModel):
    expected_revision: int = Field(ge=0)
    groups: list[GroupIn] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def unique_identifiers(self):
        group_ids = [g.id for g in self.groups]
        option_ids = [o.id for g in self.groups for o in g.options]
        if len(set(group_ids)) != len(group_ids) or len(set(option_ids)) != len(option_ids):
            raise ValueError("ID nhóm và tùy chọn phải duy nhất")
        return self


def configuration(db: Session, business_id: str, product_id: str):
    row = db.scalar(select(ProductModifierSet).where(
        ProductModifierSet.business_id == business_id,
        ProductModifierSet.product_id == product_id))
    return row.groups if row else []


def configs(db: Session, business_id: str, product_ids: list[str]):
    if not product_ids:
        return {}
    rows = db.scalars(select(ProductModifierSet).where(
        ProductModifierSet.business_id == business_id,
        ProductModifierSet.product_id.in_(product_ids))).all()
    return {r.product_id: r.groups for r in rows}


def exposed_groups(groups: list[dict]):
    """Only the fields needed to order; never expose ingredient inventory IDs."""
    return [{"id": g["id"], "name": g["name"],
             "min_select": g["min_select"], "max_select": g["max_select"],
             "options": [{"id": o["id"], "name": o["name"],
                          "price_vnd": o["price_vnd"]} for o in g["options"]]}
            for g in groups]


@router.get("/api/businesses/{bid}/products/{pid}/modifiers")
def get_modifiers(bid: str, pid: str, user=Depends(current_user),
                  db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "products")
    p = db.scalar(select(Product.id).where(Product.id == pid, Product.business_id == bid))
    if p is None:
        raise HTTPException(404, "Không tìm thấy sản phẩm")
    record = db.scalar(select(ProductModifierSet).where(
        ProductModifierSet.product_id == pid,
        ProductModifierSet.business_id == bid))
    return {"product_id": pid, "revision": record.revision if record else 0,
            "groups": record.groups if record else []}


@router.put("/api/businesses/{bid}/products/{pid}/modifiers")
def save_modifiers(bid: str, pid: str, body: ModifierSetUpdate,
                   user=Depends(current_user), db: Session = Depends(db_session)):
    b = tenant(bid, user, db)
    feature(b, "products")
    allow(db, bid, user, MANAGE_ROLES)
    p = db.scalar(select(Product).where(
        Product.id == pid, Product.business_id == bid).with_for_update())
    if p is None:
        raise HTTPException(404, "Không tìm thấy sản phẩm")
    # Resolve all referenced inventory records inside this same tenant.
    for group in body.groups:
        for opt in group.options:
            if not opt.inventory_product_id:
                continue
            stock = db.scalar(select(Product).where(
                Product.id == opt.inventory_product_id,
                Product.business_id == bid, Product.active.is_(True)))
            if stock is None or not stock.track_stock or stock.id == pid:
                raise HTTPException(422, "Nguyên liệu topping không hợp lệ trong doanh nghiệp")
    row = db.scalar(select(ProductModifierSet).where(
        ProductModifierSet.product_id == pid,
        ProductModifierSet.business_id == bid).with_for_update())
    revision = row.revision if row else 0
    if revision != body.expected_revision:
        raise HTTPException(409, "Cấu hình đã thay đổi, vui lòng tải lại")
    saved = [g.model_dump(mode="json") for g in body.groups]
    if row is None:
        row = ProductModifierSet(product_id=pid, business_id=bid, revision=1, groups=saved)
        db.add(row)
    else:
        row.groups = saved
        row.revision += 1
    audit(db, bid, user[0].id, "product.modifiers.updated",
          {"product_id": pid, "revision": row.revision, "groups": len(saved)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Cấu hình vừa thay đổi, vui lòng tải lại")
    return {"product_id": pid, "revision": row.revision, "groups": saved}


def price_line(db: Session, business_id: str, product: Product, selected: list[str]):
    """Validate every selection, required group and current price server-side.

    Returns (unit price, immutable selected-option snapshot, extra stock quantities).
    No trust is placed in a browser-provided name, price, group or stock reference.
    """
    if len(selected) > 30 or len(selected) != len(set(selected)):
        raise HTTPException(422, "Tùy chọn trùng hoặc vượt giới hạn")
    groups = configuration(db, business_id, product.id)
    permitted = {o["id"] for g in groups for o in g["options"]}
    if any(opt not in permitted for opt in selected):
        raise HTTPException(422, "Topping/size không thuộc sản phẩm")
    chosen = set(selected)
    snapshots = []
    consumption = defaultdict(int)
    unit = product.price_vnd
    for group in groups:
        options = [o for o in group["options"] if o["id"] in chosen]
        if not group["min_select"] <= len(options) <= group["max_select"]:
            raise HTTPException(422, "Vui lòng chọn đúng số lượng ở nhóm " + group["name"])
        for option in options:
            unit += option["price_vnd"]
            stock_id = option.get("inventory_product_id")
            if stock_id:
                stock = db.scalar(select(Product).where(
                    Product.business_id == business_id,
                    Product.id == stock_id, Product.active.is_(True)))
                if stock is None or not stock.track_stock:
                    raise HTTPException(409, "Nguyên liệu topping đã ngừng bán")
                consumption[stock_id] += option.get("inventory_quantity", 1)
            snapshots.append({
                "group_id": group["id"], "group_name": group["name"],
                "option_id": option["id"], "name": option["name"],
                "price_vnd": option["price_vnd"],
            })
    if unit > 2_000_000_000:
        raise HTTPException(422, "Giá sản phẩm có topping vượt giới hạn")
    return unit, snapshots, dict(consumption)


def write_item_selection(db: Session, bid: str, item_id: str, snapshots: list[dict]):
    if snapshots:
        db.add(SaleOrderItemModifier(
            item_id=item_id, business_id=bid, selections=snapshots))


def order_selection_map(db: Session, bid: str, items: list[SaleOrderItem]):
    if not items:
        return {}
    rows = db.scalars(select(SaleOrderItemModifier).where(
        SaleOrderItemModifier.business_id == bid,
        SaleOrderItemModifier.item_id.in_([x.id for x in items]))).all()
    return {r.item_id: r.selections for r in rows}
