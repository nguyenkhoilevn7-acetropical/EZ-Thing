# EZ Thing — Competitive gap audit and remediation (2026-11-16)

## Evidence and scope

Repository reviewed: nguyenkhoilevn7-acetropical/EZ-Thing.
Reference baseline main: 5d89909bda9b4730c03184f38f4e46f25c3e90ae.
Scope: merchant/customer interfaces, tenant API, POS/KDS, print, finance,
inventory, booking, guest ordering, release safety, and regression tests.
Feature evidence for competitors is from official public pages, not private demos.
Absence of a feature on a marketing page does NOT prove the rival lacks it.

Sources:
- Sapo FnB overview: https://help.sapo.vn/tong-quan-cac-tinh-nang-tren-ung-dung-sapo-fnb-nha-hang-va-dich-vu
- Sapo operational print: https://help.sapo.vn/in-phieu-bep-tem-va-phieu-kiem-do-tren-ung-dung-sapo-fnb
- Sapo offline sales: https://help.sapo.vn/Huong-dan-su-dung-chuc-nang-ban-hang-Offline
- KiotViet F&B: https://www.kiotviet.vn/ho-tro
- KiotViet features: https://www.kiotviet.vn/phi-dich-vu
- iPOS FABi: https://huongdan.ipos.vn/docs/bang-tinh-nang-phan-mem-ipos-vn/tinh-nang-phan-mem-fabi/
- iPOS POSPC: https://huongdan.ipos.vn/docs/bang-tinh-nang-phan-mem-ipos-vn/tinh-nang-phan-mem-pospc/
- Odoo POS Restaurant: https://www.odoo.com/app/point-of-sale-restaurant-features
- Square Restaurants: https://squareup.com/us/en/restaurants/capabilities
- CloudPRNT protocol: https://star-m.jp/products/s_print/sdk/StarCloudPRNT/manual/en/protocol-reference/http-method-reference/job-request-get/get-request.html

Legend: YES = implemented in code, PARTIAL = implemented with major limitations,
NO = missing, NEW = added in this PR. Code presence is NOT hardware/production acceptance.

| Function | EZ Thing | Public competitor evidence | Remaining issue |
| --- | --- | --- | --- |
| Multiple businesses across sectors per account | YES | Odoo / Sapo / KiotViet | Not exclusive |
| Branded public web storefront, live preview | YES | Sapo QR branding, Odoo website | External browser/device acceptance |
| Three palette choices + dark mode | YES | Customization available elsewhere | Not exclusive |
| Seven-day no-card trial | PARTIAL | Subscription trials vary | Subscription billing sandbox |
| Menu options, sizes/toppings and inventory recipes | YES | Sapo / KiotViet / Odoo | Check price/stock consistency |
| Restaurant reservations, zones and table maps | YES | Sapo / KiotViet / Odoo | Load & physical service acceptance |
| Table-bound QR self ordering | PARTIAL | Sapo / Odoo / Square | Published guest request is not full QR POS |
| Guest website quotes, manager approval | YES | Sapo handles guest QR requests | Server price snapshots with audit |
| Kitchen display by individual item and station | YES | Square / Sapo / Odoo | Browser foreground, no true offline |
| Generic LAN/USB print and Star CloudPRNT | YES (no hardware) | Sapo / Odoo hardware printing | Hardware compatibility pending |
| Prebill, packing checklist, per-cup label, receipt copy | NEW | Sapo / iPOS | Device-printer model tests pending |
| Day paid-at reconciliation preview | NEW | iPOS / Odoo cash-shift workflows | Not cash count or shift closure |
| Combo menus with dynamic pricing | NO | Sapo / KiotViet / Odoo | P1 |
| Split / merge bills and split payments | NO | Sapo / iPOS / Odoo | P0, ledger design needed |
| Offline order edits, receipts, sync | NO | Sapo / Odoo | P0 before reliable POS operation |
| Campaigns, coupons, loyalty tiers | PARTIAL | Sapo / KiotViet / Odoo | Points exist; campaigns do not |
| Inventory valuation and purchase suppliers | PARTIAL | KiotViet / Odoo | COGS is current-cost estimate |
| Scanner/scale + retail labels | NO | iPOS / Odoo / Sapo | P1 hardware adapter |
| GrabFood/ShopeeFood, kiosks | NO | Sapo / Square / Odoo | P2 third-party integrations |
| e-invoicing for Vietnamese tax | NO | Sapo / KiotViet | P0 regulated service integration |
| Detailed payment methods and cash drawer | NO | Sapo / iPOS / Odoo | Cannot infer cash from paid flag |

## EZ differentiation candidates — not exclusivity claims

1. One account can manage distinct businesses across industries with separate
   merchant workspaces and public storefronts on a single SaaS codebase.
2. Business-specific live brand editing and preview plus three theme palettes,
   dark/light UI, and a no-card trial in one onboarding experience.
3. One tenant/branch-scoped print outbox supports both generic LAN/USB
   ESC/POS bridge and Star CloudPRNT with audit and explicit uncertain retries.
4. Accepted website quotes recheck price/modifiers against immutable submitted
   snapshots; no silent payment or duplicate order writes.
5. KDS ticket snapshots preserve historic menu/modifier names and
   per-line revisions prevent multiple tablets silently overwriting updates.

These are distinctive combinations or implementation details observed in EZ Thing.
Public competitor docs do not establish that any feature is absent in ALL rivals.

## Confirmed defects and changes in this branch

1. Published guest orders accepted into F&B created incomplete KDS work items
   (no canonical item snapshot); automatic printing was never enqueued.
   Now both KDS snapshot and print jobs are recorded in the same transaction.
2. CloudPRNT tokenless DELETE selected newest historical row, which could
   be completed already. Now only the active offered job is acknowledged.
   Tokenless firmware still has inherent uncertainty with delayed retries.
3. KDS API/UI wrongly said printing only via browser despite EZ Print.
   Metadata and disclaimer updated to show both browser and print connector.
4. Printer heartbeat serialized naive UTC timestamps and falsely appeared
   offline on browsers in other time zones. Now all device/job timestamps
   have explicit UTC offsets.
5. Paid receipt missed POS discount/tip breakdown. The print payload now
   shows subtotal, discount and tip when POS metadata exists.
6. Added prebill, packing checklist, labels for individual beverage cups,
   and an explicitly marked paid receipt copy. Frontend order detail allows
   preview without hardware, browser printing, or dispatch to a device.
7. Added date/branch-scoped cashier close preview derived from actual paid_at,
   with UNKNOWN payment method and no invented cash variance/bank verification.

## Acceptance and remaining risks

- Before merge: complete pytest and syntax CI, browser smoke and branch tests.
- After merge: deploy verified staging commit and check API/asset availability.
- Hardware still required to test paper width, Vietnamese Unicode, cut
  commands, USB driver and firmware variations.
- No production-ready offline ordering, full checkout ledger, fiscal e-invoice,
  payment reconciliation, split/merge or dynamic combos in this PR.
- Staging remains a pilot; production requires migrations, backup restore,
  security/performance acceptance on real devices.

## Recommended next implementation phases

P0: payment-method append-only records, split-bill correctness with idempotency,
offline sync/concurrency, fiscal invoice gateway, disaster recovery.
P1: combo menus, coupons, real cash-shift close, supplier purchasing,
barcode hardware and cost-history valuation.
P2: third-party food delivery, kiosk, CRM marketing and controlled AI insights.
