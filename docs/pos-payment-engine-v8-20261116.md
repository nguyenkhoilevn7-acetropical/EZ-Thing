# EZ Thing POS — Payment Engine V8 (staging implementation)

**Scope:** additive Payment Intent and incoming bank confirmation, on top of
`sale_orders`, existing POS V7, KDS and EZ Print. No new sales ledger.

## Implemented

- Owner-only business bank account configuration (Napas bank BIN, account number,
  beneficiary), shown under Merchant → Orders → **Ngân hàng QR**.
- Unpaid order → VietQR Quick Link with the server's exact VND total and unique
  `EZP...` reference. Existing pending intent reused by the browser.
- Card `pending` intent as an integration contract **only**; no SDK, charge,
  capture or terminal pairing. It cannot mark an order paid.
- SePay endpoint `POST /api/payments/sepay/{business_id}` validates raw-body
  HMAC SHA256 and a 5-minute timestamp tolerance, matches incoming transfer,
  target merchant bank account, amount and unique code, and locks the order
  before an atomic `open → paid` transition.
- Verified QR settlements continue existing loyalty and receipt enqueue logic.
- Idempotency: unique business+request ID, unique QR reference and unique
  SePay event ID. Unmatched, wrong amount, wrong bank, already-paid, cancelled
  or superseded events are retained as `review_required` (never auto-paid).
- A pending QR/card intent blocks legacy manual `mark_paid`. Owner/manager may
  cancel an unresolved intent with an audit trail before switching to cash.
- Merchant UI can display the QR and check/poll settlement status (does not
  trust a browser-declared payment confirmation).

## Access, limitations and staging setup

1. Run Alembic `20261116_09` migration **after** confirming backup,
   schema version and the `20261116_08` print migration. The pilot uses
   `create_all`; that is NOT proof a production migration succeeded.
2. Add a Render secret environment variable `EZ_SEPAY_HMAC_SECRETS`:
   JSON mapping from **business UUID → webhook HMAC secret**, each at least
   32 characters; configure one SePay webhook per merchant at the URL above.
   Keep this entire mapping **outside GitHub, screenshots and chat**.
   Each business's SePay HMAC secret must be distinct. Implement a secret manager
   before self-serve onboarding beyond pilot merchants.
3. In the SePay dashboard: receive inbound transactions only, JSON body,
   HMAC-SHA256, enable retries and code matching using `EZP` reference.
   SePay signs `<timestamp>.<raw body>`; do NOT use unsigned webhooks.
4. Set bank account via owner Merchant UI. Test with the SePay sandbox and an
   isolated staging bank account. Confirm bank name/BIN, money and permissions
   before a real transfer.
5. Add a `PROVIDER_SANDBOX` deployment gate if deploying future experimental
   processors. This V8 code never calls a bank from the server.
6. QR image generation uses VietQR third-party Quick Link; it needs Internet,
   and transmits merchant account, transfer reference and amount to VietQR.
   Access is limited to authenticated merchant POS, not public checkout.
7. Card payment is **not live** until an acquirer provides merchant onboarding,
   SDK and terminal test hardware.
8. Offline sales/printing are **not** implemented here. Service-worker shell
   caching is not an offline database. Multi-terminal offline requires a
   branch-local hub, durable local outbox, inventory reconciliation and
   conflict policy before enabling payment completion offline.
9. Manual legacy `paid` without a pending electronic intent means a manager
   has confirmed receiving cash/other funds; it is NOT a bank-signed event.

## Endpoints

| Endpoint | Roles | Outcome |
|---|---|---|
| `GET /api/businesses/{bid}/payments/bank` | member | Beneficiary status, no secret |
| `PUT /api/businesses/{bid}/payments/bank` | owner | Save bank, supersede pending QR |
| `POST /api/businesses/{bid}/payments/intents` | member | Create QR/card pending |
| `GET /api/businesses/{bid}/payments/orders/{oid}` | member | Payment attempt status |
| `POST /api/businesses/{bid}/payments/intents/{id}/cancel` | manager/owner | Abandon pending intent |
| `POST /api/payments/sepay/{bid}` | HMAC verified | Settle once or flag review |

## Required acceptance before accepting actual money

- `pytest -q tests/test_payments_v8.py tests/test_pos_v7.py tests/test_printing.py`
- `pytest -q`
- `node --check app/static/app.js`
- Real SePay sandbox webhook signed using an account from the same tenant;
  test wrong amount/bank/duplicate/expired timestamp, late arrival and offline.
- Browser tests on phone & tablet, Vietnamese QR labels.
- Confirm database migration, backup and rollback/restore rehearsal.
- Inspect human reconciliation for `review_required` events before any
  production payments are activated.

## Official references

- https://developer.sepay.vn/en/sepay-webhooks/xac-thuc
- https://docs.sepay.vn/tich-hop-webhooks.html
- https://www.vietqr.io/qr-dong
