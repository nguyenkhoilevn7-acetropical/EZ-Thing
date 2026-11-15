# EZ Thing V7 — POS chỉnh đơn đang mở / Open-check POS edits

## Trạng thái / scope

This is the **first safe slice of P0 #01** from the 28-module roadmap, not a complete Toast/Square-class POS. No live card charge or refunds. Read-only order listing keeps using `SaleOrder`; no second order ledger.

### Supported
- **Sửa đơn chưa thanh toán:** revise the full item list, quantities, size/topping options and order note. Recalculate each item from **current server-side catalog and modifier rules**; user must explicitly confirm. Past cancelled/paid checks cannot be edited.
- **Phụ thu tip, giảm giá:** per-check integer-VND manager/owner-only values, discount `<= subtotal`; no implicit VAT or service charge. Staff can change ordinary lines only when check has no manager adjustment.
- **Chuyển bàn:** within the original branch, including takeaway (null table). Destination table may have another open check; both checks stay separate, not merged.
- **Đồng bộ kho:** append signed `pos_adjust` movements against the original `SaleOrder.id`, enforcing non-negative stock by product and per activated branch. Returns are applied before consumption. Cancellation rebalances net of `sale` and `pos_adjust`, even if item recipes were edited. Expense/profit report includes signed corrections in its current-cost **estimate**.
- **Identity/safety:** every write checks tenant, roles, CSRF middleware and open status; `SELECT ... FOR UPDATE` serializes concurrent order mutation, payment, cancellation and kitchen ticket creation on PostgreSQL; optimistic revision + idempotency request ID stops stale/replayed edits.
- **Audit:** `AuditEvent` records previous item snapshots, new revision, inventory deltas and monetary adjustments. Existing individual modifier snapshots are recreated for new open-check lines, and paid receipts remain unchanged.

### Not supported yet
- Splitting/merging checks: stock originally tracked **per order**, not per item, so splitting without a per-line stock snapshot risks double returns on cancellations; do not implement it by merely moving existing `SaleOrderItem` rows.
- Editing kitchen-sent / delivery-dispatched checks: requires compensating prep tickets / order-change events to prevent incorrect cooking or dispatch; V7 refuses all linked live tickets, including pending.
- Partial payments, refunds, VNPAY capture, e-invoices and automatic tax computation. Staff cannot manually confirm paid state from V7.
- Inventory lots, expiry, fractional units, historical weighted COGS, enforced tips allocation. Current POS report remains a management estimate.

## Manual acceptance
1. Open [merchant orders](/app?tab=orders) and select an unpaid order.
2. Click **Sửa món** / **Edit**. Add/remove line, update quantity or size/topping; optionally set discount/tip as manager.
3. Verify browser estimated total then save. Server recalculates independently. Check current stock, order detail and price.
4. From an open F&B order click **Chuyển bàn**, choose a table in the same branch. The original branch and order ID must stay unchanged.
5. Try stale revision and same request ID with a different payload: 409 Conflict.
6. Try edits after payment and after sending kitchen/delivery ticket: 409 Conflict; no movement or price change.
7. After editing an unpaid tracked stock order, cancel it as owner. Confirm exactly the net stock of the revised order was returned.
8. Inspect tablet/mobile layouts and Blue/Tropical/Graphite dark theme; refresh page to ensure revision and discount/tip persist.

## Database and deployment
- Migration: `20261115_07_pos_checks.py` adds `pos_check_meta` and `pos_check_mutations`, no destructive table changes; legacy checks start with revision 0.
- Existing DB tables `sale_orders`, `sale_order_items`, `sale_order_item_modifiers`, `stock_movements`, `audit_events` stay authoritative.
- The pilot environment calls `Base.metadata.create_all`; **a real production rollout must run Alembic migrations** and verify full backup/restoration. Render's Docker image doesn't include the migrations folder, so do not infer a production migration succeeded just because a container boots.
- CI: run `pytest -q`, `node --check app/static/pos-v7.js`, live Playwright demo browser. Never enable in production until deployment and database version reviewed.

## Market references
- Toast table transfers and permissions: https://support.toasttab.com/en/article/New-POS-Managing-Tables
- Toast item and check edits: https://support.toasttab.com/en/article/New-POS-Experience-Ordering-Screens
- Toast combines only unpaid open checks: https://support.toasttab.com/en/article/Combining-Checks-1492892550423
