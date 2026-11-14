# EZ Thing V4 — Restore drill, verified signup and merchant-approved customer carts

**2026-11-14 | Scope: EZ Thing staging only.** No production merchant payments, customer charges, subscription plan changes or Minh Satori writes.

## 1. Snapshot restore drill — VERIFIED (read-only)

- Neon project `summer-sunset-54214737`, snapshot `snap-crimson-sunset-az9ww78e` (taken before V3).
- Original branch `br-green-rice-azrlzrvn` (`main`, primary), **not changed or swapped**.
- Isolated restored branch `br-weathered-river-azxasam8`, name `ezthing-v4-restore-drill-20261114`, primary=false, default=false, restore_status=restored.
- Read-only SQL count verification on **both** branches:

  | Table | Original main | Restored branch |
  | --- | ---: | ---: |
  | users | 11 | 11 |
  | businesses | 44 | 44 |
  | sale_orders | 132 | 132 |

- The restored snapshot contains **neither** `team_invitations` nor `public_storefronts`, confirming it represents the earlier pre-V3 schema point.
- Original source branch retained V3 tables, and stays the only branch backing Render staging.
- **Outcome:** isolated restore and basic record integrity PASS. **Not verified:** full application startup against restored branch, all FK checks, media/blob restoration, RPO/RTO target, cross-region disaster recovery.
- The disposable restore branch remains for explicit authorized cleanup; no autonomous branch deletion was performed. Reclaim it in the Neon console once the owner accepts the drill.

## 2. Email verification (opt-in only)

- New `auth_email_verifications` schema and Alembic `20261114_02`.
- Secure random token, SHA-256 hashed at rest, expires in 30 minutes; single-use; activation URL fragment avoids placing tokens in HTTP request URLs.
- Server refuses login for an unverified newly registered account; previously existing users remain grandfathered.
- Controlled resend, hides whether account exists.
- Fails closed before creating a new user when verified-email mode is enabled but SMTP isn't fully configured.
- Requires these **private Render** values to activate:

  ```env
  EZ_THING_REQUIRE_VERIFIED_EMAIL=1
  EZ_THING_SMTP_HOST=<approved TLS SMTP provider>
  EZ_THING_SMTP_PORT=587
  EZ_THING_SMTP_USER=<provider account>
  EZ_THING_SMTP_PASSWORD=<private app password>
  EZ_THING_SMTP_FROM=<verified sender>
  EZ_THING_PUBLIC_BASE_URL=https://ez-thing-staging.onrender.com
  ```

- Never commit credentials. Verification mode is **not active on staging until SMTP is configured and a deliverability E2E test passes**.
- Provider hardening still required: SPF/DKIM/DMARC, outbound failure monitoring, DMARC alignment, lockout notifications, resend anti-enumeration, MFA for privileged users.

## 3. Guest customer order requests (no payment capture)

- F&B, Retail and Online real tenants with explicitly published site may accept public **order requests** (NOT payments).
- Customer selects products/quantities in responsive VI/EN cart, enters contact and (for online) delivery address. Unit prices, total, business scope, active state and availability all checked server-side.
- Public POST is idempotent per tenant+request_id. Abuse limits: max 2 pending requests per phone/tenant; 5 requests/day per phone and 80/day per connection peer.
- Guest submission writes **only `public_order_requests`**, without deducting any stock or creating a paid/unpaid sale order. No bank/card/online checkout.
- Manager/Owner sees queue in Merchant Settings, can approve/reject. On approval, transaction locks request/products, checks original price and stock, creates real `Customer`, `SaleOrder` with status **open**, `SaleOrderItem`, stock ledger sale movements, plus pending kitchen ticket (F&B) or delivery ticket (Online). Price changes cause HTTP 409; no silent repricing. Idempotent approval retry never double-deducts stock.
- On rejection, request becomes rejected; no stock adjustment occurs. Cancellation of the resulting unpaid open order must use the preexisting owner-only cancellation endpoint and respects kitchen/delivery processing guards.
- Services storefront still uses contact/booking preview; no fake service checkout.

## 4. Migration and checks

- `20261114_02_verified_email.py` and `20261114_03_public_order_requests.py` are additive Alembic revisions. Existing V3 migration chain preserved.
- Fresh deployments still require a reviewed schema bootstrap because V3 pilot uses `Base.metadata.create_all`; do not automatically reinitialize a production database.
- CI runs `pytest -q`, Node syntax validation, plus PR live Chromium demo smoke. Additional regression tests cover unauthenticated/public order isolation, idempotency, stock, forced repricing denial, multi-industry fulfillment, email token consumption, resend throttling, and migration.
- Staging release acceptance: merge only after all checks PASS, manual deploy of known main SHA on Render Free, verify deployment LIVE + new tables on Neon, and exercise an **isolated real trial tenant only**; never place test orders on unrelated merchant data.

## 5. External business/security precedents

- Shopify manual draft order / paid-after-confirmation: https://help.shopify.com/en/manual/fulfillment/managing-orders/create-orders
- Shopify payment capture and deferred payment: https://help.shopify.com/en/manual/fulfillment/managing-orders/payments
- OWASP email verification: https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html
- Neon snapshot recovery branch: https://neon.com/blog/announcing-neon-snapshots-a-smoother-path-to-recovery

## 6. Remaining release blockers

- Verified SMTP provider and real outbound mail smoke; verification toggle should remain OFF until then.
- Payment merchant account, VNPAY production credential test, refunds, fee/tax, receipt/settlement reconciliation, card tokenization with hosted provider.
- True custom domains and SSL onboarding for tenants.
- Full edge-layer bot throttling/CAPTCHA and per-tenant rate controls (the app's per-peer IP budget may be shared behind a reverse proxy).
- Auth MFA and password reset flow; staff fine-grained permissions for all industry-specific endpoints.
- Long-term encrypted backup policy, whole-system restore drill, retention policy/PII deletion flow and load tests.
- Browser E2E on actual merged SHA and all 3 merchant themes × VI/EN × phone/fold/tablet.
