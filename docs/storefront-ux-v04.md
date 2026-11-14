# EZ Thing v0.4 — Storefront UX + backend contract

Date: 2026-11-14. Scope: **staging DEMO only**. Do not turn this on for real customers, real payments, real shipping, or real reservations.

## Market research → implementation decisions

| Reference | Verified approach | EZ Thing staging implementation | Intentionally deferred |
|---|---|---|---|
| [Toast online ordering](https://support.toasttab.com/en/article/Getting-Started-Online-Ordering) and [Sapo FnB QR Order](https://help.sapo.vn/qr-order-tren-phan-mem-sapo-fnb) | Guest-oriented menu, distinct merchant operations, server-side menu visibility, kitchen flow | Restaurant-branded menu, category chips, detailed cart, table selection; order creates kitchen work item | Production QR codes, guest-to-bar payments, staff call/settlement |
| [Shopify ecommerce UX](https://www.shopify.com/blog/ecommerce-ux), [Baymard 2026 checkout](https://baymard.com/research-articles/current-state-of-checkout-ux) | Discoverability, clear prices, fast navigation, low-friction checkout, legible error handling | Search, sort, categories, availability, quick-detail sheet, thumb-friendly actions, cart estimate verified by server | Payments, shipping providers, real returns, loyalty |
| [Fresha scheduling](https://www.fresha.com/for-business/features/scheduling) | Choose service/staff/date/time, confirm availability, show booking outcome | Service category/price/60-min duration, specialist choice, 21-day range, conflict-safe slots, live progress state | Real staff rosters, resources, deposits, SMS |
| [Baymard product UX 2026](https://baymard.com/research-articles/current-state-ecommerce-product-page-ux) | Clear product differentiation and purchase decisions | Distinct product details and state; backend-authoritative final price | Merchant-uploaded product media and reviews |

This is feature-level study, not a claim that competitor designs or assets were copied. Only behavior supported by the existing staging backend is advertised.

## Frontend separation and shared UI rules

- / → marketing/solutions site.
- /app → merchant back-office; users operate inventory, kitchen, fulfillment, appointments.
- /admin → server allowlisted platform admin, inaccessible to demo visitors.
- /menu/cafe → customer F&B storefront.
- /store/mart → customer retail in-store hold preview.
- /store/online → customer order delivery preview without a carrier.
- /booking/wellness → customer appointment booking preview.
- All customer channels share typography, mobile bottom navigation, modal patterns, search/sort/price display, and error handling; each has separate color/hero/flow/capabilities.
- The customer header does **not** lead with operations/navigation controls. A small link to demo management remains in the informational footer for reviewer access only.
- CSS upgrade is additive: customer-v04.css applied after customer.css. No new NPM dependencies or database migrations.

## API contract mapping

| Customer action | API | Back-office effect | Safety |
|---|---|---|---|
| Browse categories/products | GET /api/preview/{channel} | Read-only Product scoped to demo business | Only public SKU/name/category/price/availability; no cost/stock count |
| Verify cart | POST /api/preview/{channel}/quote | None; read-only | Authentication + CSRF, tenant isolation, max 10/item, max 30 items, max 20M VND |
| Submit F&B table order | POST /api/preview/cafe/checkout | SaleOrder + kitchen work item | Table belongs to demo branch; server revalidates & calculates prices |
| Retail request | POST /api/preview/mart/checkout | SaleOrder + StockMovement | Phone required; **no payment** |
| Online order request | POST /api/preview/online/checkout | SaleOrder + delivery work item | Phone and address required; **no carrier dispatch** |
| View order progress | GET /api/preview/{channel}/orders/{order_id}/status | Read-only SaleOrder/work status | Minimal status and totals, no customer PII |
| Select spa time | GET /api/preview/wellness/slots | Read-only availability | 21-day window, 60-min slot, per-staff conflicts |
| Create spa appointment | POST /api/preview/wellness/appointments | Appointment work item | Advisory transaction lock, idempotency; DEMO only |
| View spa progress | GET /api/preview/wellness/appointments/{id}/status | Read-only appointment status | Scope to demo tenant + customer-demo source |

Contract source of truth:
- Backend: app/public.py + app/demo.py.
- Frontend: app/static/customer.js + app/static/customer-v04.css.
- Tests: tests/test_api.py and tests/test_frontend_contract.py.

## Manual acceptance checklist

- [ ] View all four customer links at 360px, 390px, tablet and desktop: no horizontal overflow or merchant dashboard in customer header.
- [ ] New demo sessions show actual per-industry categories; search, filter, sort and product-detail modal work.
- [ ] Cart quote succeeds before submit; unavailable/foreign products never place orders; errors shown without false confirmation.
- [ ] F&B picks an actual demo table; kitchen ticket appears under same demo tenant in /app.
- [ ] Retail hold appears in /app, stock movement reflects its request. **No real pickup/reservation commitment.**
- [ ] Online checkout requires address; internal delivery work item appears in /app, no fake tracking carrier.
- [ ] Spa supports selected service, date within 21-day bound, staff, 60-min slots. Confirmed booking removes slot on refresh.
- [ ] Customer receipt status matches read-only back-office data, not a fabricated progress animation.
- [ ] Closing sheet via outside tap / Escape, keyboard accessibility, reduced-motion, empty search state, category chips.
- [ ] Verify real merchant user, other demo tenant, anonymous requester cannot access demo preview/status.
- [ ] Verify mobile page cache is refreshed; no stale old v0.3 JS/CSS.

## Known pilot limitations / follow-on backend milestones

1. No merchant-uploaded product images/description/media schema, variants/modifiers, or public tenant branding editor. Art/emoji are placeholders and clearly labeled as illustration.
2. Retail "hold" currently deducts available inventory similarly to a sale; dedicated reserved-vs-on-hand ledger, hold expiration, release/return flows and cancellation are **required before real customers**.
3. No persistent cross-device visitor account or public storefront: customer flows use isolated DEMO session cookie only. Demo tenant cleanup/TTL and distributed throttling remain outstanding.
4. Fixed 60-minute spa slots and illustrative staff; real resource/staff calendars, service duration settings, breaks and reminders are not implemented.
5. No payment gateway, fulfillment carrier, bank reconciliation, invoicing, taxes, automated push notifications, or public admin access.
6. Browser/E2E regression and deploy must be verified on staging; source PR and JS syntax alone are not a production acceptance gate.

## Verification

\`\`\`sh
python -m pytest -q
node --check app/static/app.js
node --check app/static/customer.js
node --check app/static/admin.js
node --check app/static/sw.js
\`\`\`

Review PR → green CI → inspect staging /api/health + four guest flows and merchant workflows → manual deploy staging only. Production requires separate owner sign-off.
