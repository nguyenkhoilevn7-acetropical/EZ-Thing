# Kiến trúc EZ Thing v0.1

## Data flow

```text
Client SPA (HTML/CSS/JS) / PWA shell only
  | Same-origin cookie HttpOnly + X-CSRF-Token
  v
FastAPI endpoints
  | Authenticated session -> Membership scoped by business_id
  | Server-side feature catalog (Basic/Plus/Pro)
  | Service validation (SKU, table, branch, quantity, idempotency)
  v
SQLAlchemy transactions
  | PostgreSQL for staging/production (planned)
  | SQLite for local pilot development
  v
Business / User / Membership / Branch / Product / Customer
DiningTable / SaleOrder / SaleOrderItem / StockMovement / AuditEvent
```

## Business isolation

- One application; each business has a UUID.
- Query or mutation checks authenticated membership, then filters by exact business UUID.
- Product SKU unique **inside** each business, not global.
- Customer is selected by immutable customer ID; duplicate names are never auto-merged.
- Table belongs to one branch and business; cross-branch reference rejected.
- Production still needs PostgreSQL row-level security, comprehensive RBAC, security audits and tenant isolation penetration tests.

## Server-side entitlements

- The frontend hides irrelevant modules for usability; **not** an access control.
- The backend rejects restricted writes and reads regardless of UI.
- Plan changes are not exposed as a general API endpoint in v0.1.
- Onboarding chooses allowed modules from a static catalog; doesn't write arbitrary executable code.
- **Pilot exception**: first-time onboarding may choose a plan without payment. Do not use as a public subscription product before paid activation is implemented.

## Transaction rules

1. Client sends products/quantities and random idempotency key.
2. Server looks up active products for the current tenant, computes totals using current stored prices.
3. Same key + same request returns prior order; same key + changed intent rejects.
4. Stock update runs with `WHERE stock >= requested_quantity`; insufficient stock rolls back the entire transaction.
5. SaleOrder, lines, movements and audit commit in a single transaction.
6. Payment is a **manual status** with explicit confirmation and audited actor, not a payment provider result.
7. No VAT/discount/fee engine yet; amounts must never be called legal tax invoices.

## Pilot limitations

- Schema is created with SQLAlchemy `create_all`, no Alembic migrations yet.
- Password: scrypt; sessions: opaque cookie with CSRF token. No rate limits, MFA or email verification.
- No true bank reconciliation, refunds, discounts, taxes, reservations, QR ordering or kitchen dispatch.
- No true AI model integration yet: deterministic recommendations and SQL insights only.
- Multi-branch reporting has one-business summary, branch-specific reporting/stock to be extended.
- No offline sale records: service worker caches static shell only. Never claim offline orders were committed.

## Recommended production modules

`billing`, `staff-rbac`, `invoice-e`, `payments`, `inventory-recipes`, `kds`, `booking`, `ai-assistant-readonly`, `import-preview`, `integrations`, `migrations-backup`, `observability`.
