# EZ Thing — Paperless Receipts & Optional Google Members
2026-11-17 · staging/pilot

## Business precedent
- Toast POS: digital receipts, optional loyalty registration from receipt, customer-facing checkout.
  https://support.toasttab.com/en/article/Basic-Digital-Receipt-Configuration
  https://support.toasttab.com/en/article/How-Guests-Enroll-in-Toast-Loyalty
- Google Identity Services: verify Google ID token signature, issuer, expiry and audience; identify user by the stable Google subject.
  https://developers.google.com/identity/gsi/web/guides/verify-google-id-token

## Delivered features
1. Paid order displays a short-lived Digital Receipt QR on the POS. No paper required.
2. QR fragment secret is never transmitted in the initial URL HTTP request. Guest claims into anonymous, HttpOnly browser wallet.
3. Guest history includes store, branch, date, product, quantity, selected addons, price and total. No guest name, phone, email or signup.
4. Optional Google Member login with name and phone profile form. Member can recover their receipts across devices.
5. Existing merchant Customer and existing IndustryWorkItem loyalty ledger reused. No second order/finance/loyalty ledger.
6. Merchant Paperless setting suppresses customer receipt auto-print, while kitchen, bar, labels and manual print remain.
7. Merchant Members & Loyalty page manages paperless and points rate. Receipt is a purchase receipt, not a tax invoice.

## API
- GET /api/wallet/config, /api/wallet/me
- POST /api/wallet/claim, /api/wallet/google, /api/wallet/profile, /api/wallet/logout, /api/wallet/forget-device
- GET /api/wallet/member-qr
- POST /api/businesses/{bid}/paperless/{oid}/share
- GET/PUT /api/businesses/{bid}/paperless/settings
- GET /api/businesses/{bid}/paperless/members

## Database
Versioned Alembic 20261117_13 on 20261116_12 adds receipt_guest_wallets,
receipt_members, receipt_member_sessions, receipt_member_customers,
receipt_claim_tokens, receipt_wallet_orders. SaleOrder remains authoritative.
Tokens and session identifiers are stored only as SHA-256 hashes.

## Google Sign-In staging activation
1. Create Google OAuth 2.0 Web Client; authorized JavaScript origin: https://ez-thing-staging.onrender.com
2. Put public Google Client ID in Render environment variable EZ_GOOGLE_CLIENT_ID.
3. Member button is disabled until a valid OAuth Client ID is configured; guest receipts still work.
4. Enable Paperless in merchant Members & Loyalty settings. Do not enable production without migration and recovery verification.

## Acceptance
- QR only for confirmed paid orders; token expires within 15 minutes.
- First wallet claims the receipt. Other guest wallets cannot claim or see it.
- Repeated QR claim by the original wallet is idempotent.
- Member can link receipts from same guest wallet after verified Google login.
- Points earned once per order by existing loyalty ledger, owner-configured spend rate.
- No cross-tenant reads, no guest PII, no print unless customer receipt auto-print enabled.

## Deferred
- Camera OCR scanning external legacy receipt photos and staff-review import workflow.
- POS scanning Member QR before payment (points currently credit when verified member claims a paid receipt).
- SMS/Zalo/email delivery, coupons and reward redemption, refunds/reversals.
- Production security/privacy assessment, backup and migration rollout.

Do not treat purchase receipts as VAT/e-invoices.
