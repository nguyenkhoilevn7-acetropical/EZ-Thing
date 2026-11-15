# EZ Thing — V5 multi-industry operations (15 Nov 2026)

## Market scan

- Toast Tables: host waitlist, seating, schedules, online reservations and deposits (https://support.toasttab.com/en/article/Get-Help-with-Toast-Tables-Online-Waitlist-Reservations).
- Fresha: staff calendars, appointment and service resource availability (https://www.fresha.com/for-business/features).
- Shopify POS: multi-location inventory, stock movement and order fulfilment (https://www.shopify.com/pos/features).
- Loyverse: employee management, stock transfers and customer points (https://loyverse.com/features).
- Sapo FnB: ingredient recipes, inventory cost and kitchen workflows (https://help.sapo.vn/).

## Integrated UI / API

Merchant tab: `/app?tab=operations`. Mobile: Settings → Operations. Colors inherit the existing three merchant themes; no separate public storefront.

Feature | API `/api/businesses/{bid}/operations` | Status
---|---|---
Restaurant host waitlist | `/waitlist`, `/waitlist/{id}/status` | internal waiting/ready/seated/cancelled with 90min seating capacity lock
Branch reservation hours | existing `/reservations/policy?branch_id=...` | Owner-only and server-enforced, demo/main branch aligned
Staff schedule | `/staff`, `/shifts`, `/shifts/{id}/cancel` | tenant membership + overlap protected
Ingredient recipes | `/recipes`, `/recipes/{finished_product_id}` | multi-ingredient BOM; order deducts ingredient stock and cancellation restores exact movements
Location stock balances | `/inventory`, `/inventory/activate` | opt-in, physical count before activation, no silent migration of old orders
Transfer workflow | `/transfers`, `/transfers/{id}/status` | received updates branch balances only if enabled; business total remains conserved
Delivery timeline | `/deliveries/{id}/events` | internal tracking only; no carrier sync
Loyalty | `/loyalty`, `/loyalty/redeem` | once-per-paid-order earning, explicit reward log, no cash value
Expenses and estimated P&L | `/expenses`, `/finance` | current cost estimates, not statutory reporting
Notification drafts | `/notifications` | no email/SMS/Zalo dispatch
Booking deposit requests | `/deposits` | `pending_gateway`, explicitly unpaid, no charge
Multi-device sync | `/sync` | 15-second polling with tenant change version, no WebSocket guarantee

All APIs share session + CSRF, tenant isolation, plan/role checks, and existing `industry_work_items` work ledger. The new branch balance table is the only new schema and is versioned by additive Alembic revision `20261115_05`.

## Branch stock correctness contract

1. `Product.stock` remains the **business-wide sum**, including if branch ledger enabled.
2. Existing tenants start **disabled**. The Owner must physically reconcile stock before invoking `POST /inventory/activate` with `{"confirmation":"ALLOCATE_ALL_TO_PRIMARY_BRANCH"}`. Activation allocates all pre-existing tracked product balances to the primary branch. This is not an assertion of real-world stock at other outlets; an inventory count and transfers are required.
3. New tracked product openings, manual adjustments, merchant orders, approved guest orders, recipe consumption, transfers and unpaid cancellations update branch balances in the same transaction as existing global stock/movement changes.
4. Transfer request approval/receipt does not create product stock, and cross-branch receipt conserves the sum. Cancellation of an unpaid order reverses actual sale movements, not current recipe formula.
5. Concurrent writes use tenant-scoped PostgreSQL advisory locks; quantity nonnegative constraint and `UPDATE ... WHERE quantity >= q` prevent negative location inventory.
6. Multiple staff may read balances; only Owner may activate branch inventory. Manager/Owner may create transfers; staff may not.

## Production release blockers

- Deposits: require actual payment partner credentials, signed callback / webhook, reconciliation, refund/chargeback and bank confirmation tests. Never mark the current deposit requests as paid.
- Email/Zalo/SMS: opt-in consent, verified sender/channel, provider credentials, retry/outbox/delivery receipt and regulatory checks needed; V5 only stores drafts.
- Branch stock: verify physical counts and migration on staging first; activation is **not** automatic.
- Financial report: current product costs, not immutable historical lot or ingredient costs. Do **not** use as tax reports.
- Performance: polling is near-real-time, not guaranteed instant; production sizing, load test at scale and maintenance observability remain gates.
- Real backups: isolated Neon restore drill was documented under V4; keep automatic snapshots and regular restore testing before production data moves.

## Verification

- `pytest -q` includes V5 E2E scenarios for permissions, idempotency, recipes, sales, cancellations, location stock, transfer, loyalty, expense, deposits, draft and branch booking policies.
- `node --check app/static/operations-v5.js` is included in GitHub CI.
- `tests/live_demo_browser.py` exercises actual Chromium merchant tab, light/dark rendering and tenant API.
- Staging releases require green CI, manual Render deploy (auto-deploy off) and DB-backed `/api/ready` smoke. Production promotion is a separate explicit decision.

No writes to Minh Satori or other project databases. No external payments or messages are sent.
