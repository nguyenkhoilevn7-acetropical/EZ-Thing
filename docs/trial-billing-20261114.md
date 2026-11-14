# EZ Thing — 7-day trial and VNPAY-hosted billing (staging pilot)

## Business policy (14 November 2026)

- A real account's first business receives **7 calendar days** of free full-feature trial from server-side UTC creation timestamp. **No selected plan or payment card required**.
- Creating additional businesses on the same account **does not reset the trial**; those businesses enter `trial_expired` until paid.
- Trial does not charge or renew automatically; the customer decides after or during trial whether to buy a plan.
- At the deadline, business API returns HTTP 402, with customer data retained. Owners can still access `GET /api/businesses/{bid}/billing`, select a plan and pay.
- After verified payment: exact server-owned Basic / Plus / Pro features become active for 30 days. No recurring bank/card debit. Once the paid period expires, activity pauses until a new approved payment.
- Legacy staging `pilot` and isolated `demo` tenants are unaffected.
- Prices are preliminary: **Basic 249k, Plus 499k, Pro 999k VND per 30 days**, not contractual price commitments.
- These are **SaaS subscription payments only**, independent of customer product orders. A successful browser return is never proof of payment.

## Payment flow and safety

1. `POST /api/businesses/{bid}/billing/checkout` requires owner, session CSRF, plan and channel (card/bank/qr). Backend calculates amount from `app/catalog.py`.
2. When merchant credentials are provisioned, server creates a uniquely referenced VNPAY **Sandbox** checkout URL with HMAC-SHA512, expiry and VND amount x100.
3. Customer selects/inserts card **only** on the VNPAY-hosted checkout. EZ Thing has no card PAN/CVV fields and stores no card credentials.
4. `GET /api/billing/vnpay/ipn` is the **only** route that confirms payment. It checks signature, terminal, reference, amount, ResponseCode, TransactionStatus and existing ledger state, then atomically activates plan.
5. Duplicate, fraudulent and mismatched IPNs cannot create multiple paid periods; `GET /api/billing/vnpay/return` only redirects to the billing page.
6. Billing ledger stores plan, amount, gateway reference, amount/channel/status and timestamps; it does not claim to be a legally issued VAT invoice.
7. **Add card / saved card/tokenized recurring payment is not enabled** until a merchant tokenization contract, secured token vault, separate consent and revoke flows are completed. This must not be implemented by collecting raw card fields.

## Required staging configuration (Render, no secrets in repository)

```dotenv
EZ_THING_ENVIRONMENT=staging
EZ_THING_TRIAL_ENABLED=1
EZ_THING_BILLING_ENV=sandbox
EZ_THING_PUBLIC_BASE_URL=https://ez-thing-staging.onrender.com
# Request from VNPAY Sandbox merchant portal:
VNPAY_TMN_CODE=<merchant-specific terminal>
VNPAY_HASH_SECRET=<merchant-specific secret>
```

If VNPAY credentials are missing, `checkout_ready=false`; attempts to pay return 503, not a fictional payment confirmation. **Never use publicly shared sample merchant secrets**.

VNPAY Sandbox IPN URL to register with VNPAY merchant support:

`https://ez-thing-staging.onrender.com/api/billing/vnpay/ipn`

Customer return URL set by server:

`https://ez-thing-staging.onrender.com/api/billing/vnpay/return`

Checkout is hard-disabled outside **staging sandbox** until a separate production gateway audit is approved.

## Testing and go-live checklist

- Tests: trial clock and expiry/402, first-account-only trial, cross-tenant owner authorization, no gateway credentials, HMAC signature and amount, gateway return cannot activate, IPN idempotency and failed payment, branch/feature entitlements after paid activation.
- CI: `pytest -q`, `node --check app/static/app.js`, `node --check app/static/billing-ui.js`.
- Validate browser flows with real staging VNPAY test merchant credentials before asking anyone to pay.
- Do not enable production checkout before: signed merchant onboarding, PCI delegation, versioned DB migrations/backup, legal payment pages, refund/cancellation terms, tax-compliant receipts, data-protection review, alerting and reconciliation.
- Ensure VNPAY tokenization and recurring billing are separate opt-in projects; this PR only supports **one-time** hosted payment.

## Reference sources

- Official VNPAY checkout + verified IPN: https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html
- Official VNPAY tokenization: https://sandbox.vnpayment.vn/apis/docs/thanh-toan-token/token.html
- VNPAY supported card/QR methods: https://vnpay.vn/link-thanh-toan-vnpay-cho-doanh-nghiep-0ibcucbn3aw
- Stripe country availability (Vietnam not directly supported): https://stripe.com/global
