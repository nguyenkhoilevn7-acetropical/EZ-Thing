# EZ Thing — SaaS expansion delivery plan (15 Nov 2026)

## Architectural rule
Extend the **existing** multi-tenant FastAPI, PostgreSQL/Neon, Render, Vanilla JS and single order/stock/payment ledgers. Keep `business_id` isolation, account/CSRF/role/entitlement checks, VI/EN, responsive mobile/dark mode, and production-safe additive Alembic migrations. Never create an unrelated app or separate money ledger. Production rollout requires staging, migration rehearsal, backup, monitoring and feature flags.

## This release — V6 size and product add-ons
**In code, awaiting final CI/staging verification at authoring:**
- Merchant product card **Size / Topping** editor. Multiple groups; names, per-option integer-VND surcharge, required minimum and maximum selection; up to eight groups and twenty options per group. Optimistic revision checks on edit.
- Optional ingredient SKU link and quantity: physical topping stock consumed with existing recipe and stock ledger; base drink can remain untracked when produced to order.
- Merchant POS order lines display independent options and update estimated total.
- Public opt-in shop catalog/cart supports modifier dialogs, multiple combinations of the same product and server-only price calculation.
- Guest order requests remain uncharged and unreserved until merchant acceptance; acceptance revalidates current server prices and names, stock and availability, rejecting changed options.
- Persist selected option names and prices **per sale-order-item** so receipts do not change when product configurations are edited.
- Unit tests: pricing, required groups, distinct combos, idempotency, tenant boundaries, ingredient deduction/reversal, stale configuration conflicts, public review. 
- Existing `SaleOrder`/`SaleOrderItem`/`StockMovement` remain authoritative.
- Schema: additive `product_modifier_sets` and `sale_order_item_modifiers` using Alembic `20261115_06`; no destructive migration.
- **Not included:** nested modifier sets, fractional ingredient quantities, precise recipe costing, modifier item-level entitlements, automatic supplier procurement, actual payment capture.

### Example
Product: Trà Sữa, base price 35,000 VND, untracked finished goods.

| Group | Selection rules | Choices |
| --- | --- | --- |
| Size | minimum 1, maximum 1 | M +0 VND, L +7,000 VND |
| Topping | minimum 0, maximum 2 | Trân châu +5,000 VND; Thạch +3,000 VND |

Trà Sữa M + Trân châu = 40,000 VND. Trà Sữa L + Trân châu = 47,000 VND. A separate inventory SKU for Trân châu may deduct its configured number of integer units per serving.

## Implementation sequence: 28 previously proposed modules

- **Gate A — Transactional F&B (highest priority):**
  01. POS advanced: edit open tickets, split/merge, move tables, combos, discount/tax/tips, refunds under audit.
  02. QR order at the physical table: signed rotating table link, kiosk session, guest call/checkout request and throttling.
  03. KDS: prep routing to kitchen/bar, ticket queue and timings, realtime synchronization and thermal printer support.
  04. Real payments: merchant-selected provider, no raw card storage, signed webhook, immutable capture/refund references, reconciliation and dispute logs.
  05. Compliant e-invoice provider integration, gated by up-to-date tax and vendor requirements.
  06. Security, migrations, backups, load tests and tenant leakage checks.
- **Gate B — Multi-branch operations:**
  07. Suppliers, purchase order, receiving, historical cost and payables.
  08. Batch/expiry/barcode inventory, waste, physical counts, unit conversions and safe replenishment.
  09. Timesheets, shift requests, labor cost/payroll integrations, closing cash reconciliation.
  10. CRM tiers, consent, points redemption discount, gift cards, retention campaigns.
  11. Booking modification, confirmations and cancellation/forfeiture policy with verified payments.
  12. Delivery carrier APIs, shipping quotes, COD reconciliation.
  13. Accurate finance and historical COGS, cash flow, exports.
- **Gate C — Domain-specific vertical apps:**
  14. Restaurant catering, happy hour, recipe unit conversions and kiosk.
  15. Retail product variants, returns, warranty and wholesale price books.
  16. Online checkout, SEO, abandoned checkout, marketplaces and fulfillment.
  17. Spa/salon room and therapist capacity, packages, memberships, appointment recurrence.
- **Gate D — SaaS commercialization:**
  18. Themeable website builder, image manipulation and rollback of published revisions.
  19. Custom domains, DNS verification, TLS automation and paid white labeling.
  20. Super Admin tenant observability, impersonation with audit/consent, feature entitlements and quotas.
  21. Production subscription billing with verified payments, invoices, upgrades and dunning.
  22. Developer APIs, scoped keys, signed webhooks, retries, rate quotas.
  23. AI Business Assistant: grounded SQL analytics, forecast and owner-approved write actions.
  24. Opt-in AI marketing campaigns, budget and messaging consent controls.
  25. Staff/mobile PWA with push, safe offline queue and idempotent sync.
  26. Reseller/agency commissions tied to verified subscription revenue.
  27. Automation rules and durable outbox, explicit opt-in and audit.
  28. Tenant-level infrastructure quotas, backup verification, slow-query profiling and rollback.

## Non-negotiable release gates
- **Real checkout/deposit:** previous issue #47 requires provider credentials, valid signatures, refunds, idempotency and reconciliation.
- **Email/Zalo OA delivery:** previous issue #48 requires vendor onboarding, verified templates, consent and durable send audit.
- **Production assurance:** previous issue #49 requires PostgreSQL migration rehearsal, load testing, restore drills and observability.
- **Fractional ingredient quantities:** base model uses integer stock; conversions need their own migration and tests before a recipe can deduct 0.05 kg.
- **Scoping and costs:** a feature marked **planned** is not available until PR, CI, staging verification and release confirmation. No UI text may claim real payment or carrier integration until connected.

## Market pattern references
- Toast modifier groups: https://doc.toasttab.com/doc/platformguide/adminAddingModifierGroupsAndModifiers.html
- Square modifiers and selection count: https://js.squareup.com/help/us/en/article/5119-create-and-manage-item-modifiers
- Toast required/optional modifiers: https://support.toasttab.com/en/article/Required-Optional-Modifiers

## Developer demo checklist
1. Create tracked ingredient `Pearls` with stock 20; create untracked drink `Milk Tea` at 35,000 VND.
2. On the drink, create one required Size group and one optional Topping group, link Pearls as topping inventory.
3. In merchant POS, create two lines of Milk Tea, one M + Pearls, another L, and verify each line price, total and stocks.
4. Publish store only for a real subscribed tenant. In customer shop, choose two different combinations, review cart and submit request.
5. Check no stock movement at guest submission; merchant acceptance creates a single sale with immutable options and ingredient movements.
6. Change topping price; verify older receipt unchanged. Cancel an unpaid sale; confirm exact ingredient stock restoration.
7. Inspect dark/blue/mobile layouts and VI/EN after deploy.
