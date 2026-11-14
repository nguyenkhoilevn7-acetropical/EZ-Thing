# EZ Thing — Deep engineering audit (2026-11-14), batch 2

## Source of truth

- Repository: `nguyenkhoilevn7-acetropical/EZ-Thing`, staging-only deploy.
- Main stack: FastAPI, SQLAlchemy, PostgreSQL 18 on Neon, Render Docker web service.
- Render service `ez-thing-staging`: **Free, 1 instance, Singapore, autoDeploy off** as inspected 2026-11-14.
- Neon project `ez-thing-staging`: Free, Singapore, baseline 132 orders and 132 line items (approximate PG statistics). Do **not** assume this is representative production traffic.
- Main CI was PASS at audit baseline.
- Do not activate any paid resource, charge, or production database migration without explicit financial and operational sign-off.

## Market engineering patterns reviewed

- [Shopify idempotent requests](https://shopify.dev/docs/api/usage/idempotent-requests): idempotency keys for payments and retry-safe inventory changes.
- [Shopify refund/inventory idempotency updates](https://shopify.dev/changelog/adding-idempotency-for-inventory-adjustments-and-refund-mutations): protect against duplicate stock adjustment, transfer and refunds.
- [Square webhook best practices](https://developer.squareup.com/docs/webhooks/overview): authenticate gateway events, deduplicate event ids and tolerate asynchronous delivery.
- [Fresha business features](https://www.fresha.com/for-business/features): appointment resources/staff/service scheduling and merchant workflow benchmarks.

## Confirmed issues and remediations in this PR

| Priority | Observed condition | Change |
|---|---|---|
| P0 | Login had no failed-password rate limit | Persist failure counter by SHA-256 normalized email across instances; 8 attempts/15 min followed by HTTP 429 |
| P0 | Full order table loaded into Python for /overview | SQL aggregates only, including timezone-aware Asia/Ho_Chi_Minh paid revenue |
| P1 | Orders list did one SELECT per order for line items | Batch SELECT for 100 most recent order line items |
| P1 | /api/health reported process alive without DB readiness | Added /api/ready with read-only SELECT 1 and sanitized 503 |
| P1 | Neon pool could grow past expected resource budget | Bounded pool, recycling, connect and checkout timeouts; no plan upgrade |
| P1 | Docker process received shutdown signal indirectly | exec uvicorn for graceful SIGTERM; Docker readiness HEALTHCHECK |
| P1 | No composite query index for dashboard/order detail/stock reversal | New SQLAlchemy indexes + re-runnable staging SQL migration |
| P1 | Merchant API fetch had no timeout and trial expiry could leave stale navigation | Abort timeouts, automatic billing transition on 402, consolidated loading errors |
| P1 | Inline white backgrounds broke Graphite dark cards | Changed inline merchant surfaces to palette tokens |
| P2 | Subscription payment webhook is asynchronous | Billing history now offers explicit refresh of verified status |

## Validation

- `pytest -q` plus Node syntax check in GitHub Actions.
- New tests: 8 failures -> lockout, successful login resets, database offline readiness 503 without leaking exception, large-volume dashboard correct and constant query count.
- Preserve existing F&B, Retail, Online, Services, trial, VNPAY and demo fixtures.
- Live deploy must use reviewed commit only; verify /api/health, /api/ready, /api/config, /app and all five public preview pages.
- Database index migration: `scripts/migrations/20261114_perf_indexes.sql`, apply **only to EZ Thing staging**, verify `pg_indexes` afterward. Existing tables are not altered automatically by `Base.metadata.create_all`.

## Remaining release blockers, NOT claimed resolved

1. Versioned Alembic schema migrations, database backup/restore drill, point-in-time recovery policy. Auto `create_all` still exists in pilot startup.
2. Merchant staff granular RBAC, invitation/permission management, audit detail.
3. Signup email verification, IP/gateway rate limit (the newly added login limiter is per identity only).
4. True merchant customer-facing tenant storefront and domain mapping; current public preview paths are demo only.
5. Real card token vault, VNPAY merchant credentials and PSP end-to-end settlement tests.
6. Refunds/partial payments, tax invoices, inventory purchase order, restaurant bill split/merge, delivery carrier events, wellness resource collisions and reminders.
7. Full browser e2e across 3 themes x 2 languages x multiple breakpoints, load testing, SLO monitoring/alerts.
8. Render live service `healthCheckPath` was blank despite `render.yaml` documenting `/api/health`. Configure `/api/ready` in Render Dashboard (requires dashboard capability) before production; Docker HEALTHCHECK is not a substitute for Render config.
9. Render Free with single instance may sleep; any paid upgrade needs explicit owner approval. Do not equate passing CI with production scalability.
