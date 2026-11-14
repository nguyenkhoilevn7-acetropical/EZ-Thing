"""Isolated, disposable demonstration workspaces for STAGING ONLY.

Each visitor receives their own account and tenants, never access to another
visitor's tenant or to any existing customer's records.
"""
import os
import secrets
import uuid

from .catalog import PLANS
from .models import (
    AuditEvent, Branch, Business, Customer, DiningTable, Membership, Product,
    SaleOrder, SaleOrderItem, StockMovement, User, now,
)
from .security import digest_password

DEMO_DOMAIN = "demo.ezthing.invalid"


def demo_enabled() -> bool:
    return os.getenv("EZ_THING_ENVIRONMENT") == "staging" and os.getenv("EZ_THING_DEMO_MODE") == "1"


def is_demo_user(user: User) -> bool:
    return user.email.endswith("@" + DEMO_DOMAIN)


def id_() -> str:
    return str(uuid.uuid4())


SEEDS = (
    {
        "industry": "fnb", "business": "Tropical Coffee • DEMO", "category": "Đồ uống",
        "products": (("Matcha Latte", "MATCHA", 49000, 14000, 42),
                     ("Cà phê sữa", "CAFE-SUA", 35000, 11000, 32),
                     ("Trà đào cam sả", "TRA-DAO", 45000, 13000, 21),
                     ("Cold Brew", "COLD-BREW", 42000, 12000, 16),
                     ("Nước ép cam", "CAM-EP", 39000, 15000, 8),
                     ("Trà vải", "TRA-VAI", 39000, 11000, 3)),
        "tables": (("Bàn 01", 2), ("Bàn 02", 4), ("Bàn 03", 4), ("Bàn 04", 6),
                   ("Sân vườn 01", 4), ("Sân vườn 02", 4)),
    },
    {
        "industry": "retail", "business": "Easy Mart • DEMO", "category": "Bán lẻ",
        "products": (("Bình giữ nhiệt", "BT-100", 159000, 80000, 24),
                     ("Túi tote", "TT-201", 99000, 35000, 18),
                     ("Sổ tay", "ST-003", 49000, 17000, 39)),
        "tables": (),
    },
    {
        "industry": "online", "business": "Online Shop • DEMO", "category": "Online",
        "products": (("Áo thun", "AT-001", 189000, 69000, 37),
                     ("Nón lưỡi trai", "NON-001", 119000, 42000, 15),
                     ("Túi đeo chéo", "TUI-001", 259000, 112000, 12)),
        "tables": (),
    },
    {
        "industry": "services", "business": "Wellness Spa • DEMO", "category": "Dịch vụ",
        "products": (("Gói xông hơi", "XH-001", 89000, 28000, 0),
                     ("Massage thư giãn", "MS-001", 299000, 110000, 0),
                     ("Gói chăm sóc da", "DA-001", 399000, 140000, 0)),
        "tables": (),
    },
)


def seed_demo(db) -> User:
    """Seed 4 business types with example data in one database transaction.

    Caller owns the commit/rollback through issue_session, so a failure never
    creates a half-initialized visitor account or a partial tenant.
    """
    u = User(id=id_(), email=f"guest-{uuid.uuid4().hex}@{DEMO_DOMAIN}",
             name="Khách trải nghiệm", password_hash=digest_password(secrets.token_urlsafe(32)))
    db.add(u)
    db.flush()

    for spec in SEEDS:
        biz_id, branch_id = id_(), id_()
        active = [x for x in PLANS["PRO"]["features"] if x != "tables" or spec["industry"] == "fnb"]
        db.add(Business(id=biz_id, name=spec["business"], industry=spec["industry"],
                        plan="PRO", requested_plan="PRO", subscription_status="demo",
                        active_modules=active, setup={"demo": True}))
        db.flush()
        db.add(Membership(id=id_(), business_id=biz_id, user_id=u.id, role="owner"))
        db.add(Branch(id=branch_id, business_id=biz_id, name="Chi nhánh chính"))
        db.flush()

        sample_customers = []
        for n in range(1, 4):
            customer = Customer(id=id_(), business_id=biz_id, name=f"Khách mẫu 0{n}",
                                phone="", address="Địa chỉ minh họa")
            db.add(customer)
            sample_customers.append(customer)

        sample_products = []
        for name, sku, price, cost, stock in spec["products"]:
            track = spec["industry"] != "services"
            product = Product(id=id_(), business_id=biz_id, name=name, sku=sku,
                              category=spec["category"], price_vnd=price, cost_vnd=cost,
                              stock=stock, track_stock=track)
            db.add(product)
            sample_products.append(product)

        table_ids = []
        for label, seats in spec["tables"]:
            table = DiningTable(id=id_(), business_id=biz_id, branch_id=branch_id,
                                label=label, seats=seats)
            db.add(table)
            table_ids.append(table.id)
        db.flush()

        # Two paid + one open order for visible dashboard and report examples.
        for index in range(3):
            p = sample_products[index % len(sample_products)]
            qty = index + 1
            paid = index < 2
            order = SaleOrder(id=id_(), business_id=biz_id, branch_id=branch_id,
                              table_id=(table_ids[index] if table_ids else None),
                              customer_id=sample_customers[index].id,
                              idempotency_key=f"sample-{index}-{uuid.uuid4().hex[:12]}",
                              request_fingerprint="demo_seed", status="paid" if paid else "open",
                              total_vnd=p.price_vnd * qty, note="DỮ LIỆU MINH HỌA",
                              paid_at=now() if paid else None)
            db.add(order)
            db.flush()
            db.add(SaleOrderItem(id=id_(), business_id=biz_id, order_id=order.id,
                                 product_id=p.id, product_name=p.name, quantity=qty,
                                 unit_price_vnd=p.price_vnd, total_vnd=p.price_vnd * qty))
            if p.track_stock:
                p.stock -= qty
                db.add(StockMovement(id=id_(), business_id=biz_id, product_id=p.id,
                                     delta=-qty, reason="sale", ref=order.id))
        db.add(AuditEvent(id=id_(), business_id=biz_id, actor_id=u.id,
                          action="demo.seeded", payload='{"sample_data": true}'))
    db.flush()
    return u
