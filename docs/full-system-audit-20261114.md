# EZ Thing — Cross-industry functional audit (14 Nov 2026)

Status: **staging pilot**, not production ready. Audited against the code currently in `main` plus the attached cancellation patch. Do **not** represent a planned or mocked integration as live.

## Verified capabilities and remaining gaps

| Domain | Verified in repository | Remaining required work | Priority |
|---|---|---|---|
| Tenant / access | Membership scoped by business ID, CSRF/session, admin suspend/block, server module gating | Staff RBAC per operation, email verification/MFA, rate limit across instances, row-level database isolation, subscription entitlement backend | P0 |
| Café / restaurant | Table creation, kitchen state machine, reservations, contact inbox, editable branch floor zones, internal order pricing | Real customer public booking beyond demo, transfer/split/merge checks, modifiers, ingredient recipe depletion, kitchen printer, shifts and reconciliation | P1 |
| Retail / minimart | Products, SKUs, stock movements, order creation, inventory adjustments | Barcode workflow, purchasing/receiving, stock counts, partial returns/exchanges, suppliers, per-location stock | P1 |
| Online shop | Customer demo checkout, server-priced order and internal delivery workflow | Shipping rates/labels/carriers, COD settlement, tracking webhooks, refunds, multi-channel synchronization, real public checkout | P1 |
| Spa / wellness | Services, staff-name scheduling, overlap detection, customer demo booking | Real staff roster & shifts, rooms/resources, cancellation policy, deposits, reminders, rescheduling, service packages | P1 |
| Orders across all 4 | Server-side totals, idempotency, atomic stock decrement, manual payment mark, order-dashboard | **This patch:** owner-only cancellation of unpaid/unprocessed orders; restore stock once; block paying cancelled orders; cancel pending kitchen/delivery tasks. Still need true paid-order refunds, partial payments, tax/discount/shipping | P0/P1 |
| Branding / i18n | Tier-based storefront theme editor and VI/EN switches, local theme palettes | Real public tenant domains, complete text coverage and native-language error messages, systematic 360/390/768/1024px/desktop audits | P1 |
| Data & delivery | Neon staging, SQLAlchemy models, GitHub Actions unit tests, Render manual deploy | Versioned migrations, backup/restore drill, monitoring, load tests, PCI/security review, staged rollouts and rollback plan | P0 |

## Industry workflow references

- Restaurant/POS: Square handles unified ordering, kitchen displays and floor plans: https://squareup.com/us/en/restaurants/capabilities
- Multi-location retail and returns: Shopify POS and inventory: https://help.shopify.com/en/manual/sell-in-person/shopify-pos and https://help.shopify.com/en/manual/inventory-and-locations
- Online shipping/cancellations: Shopify fulfillment: https://help.shopify.com/en/manual/fulfillment/features-overview
- Services: Fresha resources, calendar, booking deposits and staff permissions: https://www.fresha.com/for-business/features

## Acceptance gates (not met merely by unit tests)

1. Run full `pytest -q`, `node --check app/static/app.js` and GitHub Actions CI on the exact PR head.
2. Test same-account and cross-tenant permissions, concurrent inventory updates, simultaneous pay/cancel, double booking, quantity boundaries.
3. Test mobile, fold/tablet and desktop UI in both languages, all 3 themes, high contrast, keyboard navigation.
4. On an isolated, backed-up staging database, verify each of the 4 customer journeys and corresponding merchant dashboard state updates.
5. Verify no API advertises real banking, refunds, shipping or SMS before connectors are configured and end-to-end tested.
6. Keep all changes out of production until backups/migrations, payments, permissions, and release sign-off are complete.

## Cancellation contract introduced by this PR

`POST /api/businesses/{bid}/orders/{oid}/cancel`
with JSON `{"confirmed": true, "reason": "Customer cancellation"}`, authenticated cookie and CSRF header.

- Only a member with `owner` role may perform this compensating operation.
- Requires `open` order and all kitchen/delivery work items still `pending`.
- Returns 409 if paid, in fulfillment, or incompatible; no mutation.
- Restores precisely the negative `sale` stock ledger movements for the order, adds opposite `order_cancelled` movements, marks pending work items cancelled and audits reason.
- Safe repeated cancellation returns same cancelled order without a second stock restoration.
- Never sends refund, reverses card/bank transactions or synthesizes confirmation from carriers.

## Release notes

- This is one concrete vertical-spanning improvement, **not** an assertion that all listed gaps are implemented.
- Main may receive concurrent UX/i18n PRs: rebase and re-run CI before merge.
- Staging changes are not deployed automatically by this PR.
