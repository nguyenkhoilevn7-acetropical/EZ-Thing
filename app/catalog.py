"""Versioned built-in module catalog. Onboarding selects allowed modules; it never generates code."""
from typing import Literal

PLANS = {
 "BASIC": {"name": "Basic", "price_vnd": 249000, "features": ["dashboard", "products", "orders", "tables", "inventory_basic", "kitchen", "stock_ledger", "fulfillment", "appointments"], "branches": 1},
 "PLUS": {"name": "Plus", "price_vnd": 499000, "features": ["dashboard", "products", "orders", "tables", "inventory_basic", "inventory_adjust", "insights", "kitchen", "stock_ledger", "fulfillment", "appointments"], "branches": 1},
 "PRO": {"name": "Pro", "price_vnd": 999000, "features": ["dashboard", "products", "orders", "tables", "inventory_basic", "inventory_adjust", "insights", "multi_branch", "kitchen", "stock_ledger", "fulfillment", "appointments"], "branches": 10},
}
FEATURES = {
 "dashboard": ("Tổng quan", "Dashboard"),
 "products": ("Sản phẩm", "Products"),
 "orders": ("Đơn hàng", "Orders"),
 "tables": ("Sơ đồ bàn", "Tables"),
 "inventory_basic": ("Theo dõi tồn kho", "Inventory"),
 "inventory_adjust": ("Điều chỉnh tồn kho", "Inventory adjustments"),
 "insights": ("Trợ lý phân tích", "Business insights"),
 "multi_branch": ("Nhiều chi nhánh", "Multi-branch"),
 "kitchen": ("Bếp & pha chế", "Kitchen tickets"),
 "stock_ledger": ("Sổ kho bán lẻ", "Retail stock ledger"),
 "fulfillment": ("Đóng gói & giao hàng", "Order fulfillment"),
 "appointments": ("Lịch hẹn dịch vụ", "Service appointments"),
}
INDUSTRIES = {"fnb": "Nhà hàng / Cafe", "retail": "Bán lẻ", "online": "Bán hàng online", "services": "Dịch vụ"}
# Planned modules are never enabled just because someone chose a paid tier.
ROADMAP = ["qr_order", "reservation", "recipe_costing", "customer_crm", "zalo_integration", "tax_invoice", "ai_forecast", "online_payment"]

def recommend(industry: str, need_tables: bool, need_inventory: bool, need_insights: bool, need_branches: bool):
    requested = ["dashboard", "products", "orders"]
    if industry == "fnb" and need_tables:
        requested.append("tables")
    requested.append({"fnb":"kitchen", "retail":"stock_ledger", "online":"fulfillment", "services":"appointments"}[industry])
    if need_inventory:
        requested.append("inventory_basic")
    if need_insights:
        requested.append("insights")
    if need_branches:
        requested.append("multi_branch")
    tier = "PRO" if need_branches else "PLUS" if need_insights else "BASIC"
    return {"recommended_plan": tier, "requested_modules": requested,
            "available_now": [f for f in requested if f in PLANS[tier]["features"]],
            "reason": "Gói được đề xuất theo nhu cầu quản lý đã chọn. Đây là cấu hình module có sẵn, không sinh phần mềm mới.",
            "planned": ROADMAP}