# EZ Thing V3 — Tenant Teams, Published Storefronts and Schema Safety

**Date:** 2026-11-14. **Environment:** staging only.

## Implemented in this change

- Owner/Manager/Staff: owner invites by one-time, 48-hour, email-bound link; owner revokes invites, updates roles and removes employees. No email provider/SMTP credentials are configured; owner copies and shares the link privately.
- RBAC enforced server-side for privileged product, inventory, branch, restaurant table, payment marking, reporting and admin audit operations. Staff may create business orders, update customers and execute available workflows. Staff does **not** receive product costs or financial KPIs. Owner only controls team and subscription billing.
- Registration throttling by hashed email (8/hour) and transport peer (80/hour), stored in shared DB. These are defense-in-depth; require CAPTCHA/managed edge abuse prevention and email verification before public commercial rollout.
- Private by default, real tenant storefront publishing at `/shop/<unique-slug>`. Merchant owner chooses slug and enables/disables public access in Settings. Public catalog shows safe, active, tenant-owned products and branding; never shows costs, exact stock, customers, staff, real payment data or DEMO tenant data.
- Customers can send a contact request that appears as a `public_leads` item in the existing industry work table, with idempotency and per-transport-peer daily rate limit. Owner/Manager may mark contacted/closed.
- Public storefront is **inquiry-only**. No claim of online payment, checkout, refund, automatically accepted order, capacity reservation or shipping integration.
- Responsive standalone frontend, mobile navigation, Graphite dark mode, VN/EN labels. Billing page remains owner-only.
- Sales dashboard line items batch-fetched in one query to avoid N+1.

## Backup

A manual Neon staging snapshot was created **before** V3 writes:

- Project: `summer-sunset-54214737` (EZ Thing staging only; not Minh Satori)
- Source branch: `br-green-rice-azrlzrvn`
- Snapshot: `snap-crimson-sunset-az9ww78e`
- Snapshot name: `ezthing-staging-pre-v3-20261114`

**Snapshot existence is not proof of restorable backup**. Perform an isolated restore into a **new disposable branch**, run read-only row count/foreign key acceptance, document results, and only then mark backup/restore readiness. Avoid restoring into main or replacing live database without separate explicit approval.

## Alembic migrations

- `alembic.ini`, `migrations/env.py`, `migrations/versions/20261114_00_baseline.py` and `20261114_01_team_public.py` added.
- Baseline migration validates expected core tables rather than silently fabricating an empty production schema.
- Additive next migration creates only `team_invitations` and `public_storefronts` plus indexes, if missing.
- **No automatic destructive downgrades.** Existing pilot boot `Base.metadata.create_all` remains. This is a migration foundation, not a fully migrated production bootstrap.
- Commands for a prepared, isolated environment:
  ```sh
  export DATABASE_URL='...private...'
  alembic -c alembic.ini upgrade head
  alembic -c alembic.ini current
  ```
- Never commit DATABASE_URL. Do not run on EZ Thing staging live DB without verified backup, reviewed test migration and deploy window. The running pilot app may create the new tables before Alembic is manually stamped; additive migration explicitly accommodates that.
- Migration integration test uses **temporary SQLite only** and checks preserved business data; PostgreSQL-specific DDL still needs staging validation.

## Operational acceptance & remaining gaps

1. Owner invites registered staff with 48h one-time link; different email and other business cannot accept it.
2. Staff can create orders but cannot edit price/cost, stock, manually mark Paid, access billing or view private finance reports. Manager can perform operational management while Owner retains cancellation and team ownership.
3. Private store slug is inaccessible through catalog API until owner publishes it; after unpublish it returns HTTP 404. Duplicate slugs and cross-tenant access are rejected.
4. Guest leads are idempotent and cannot see or modify other tenant content; valid HTTPS Origin works behind Render proxy when `EZ_THING_PUBLIC_BASE_URL` is set.
5. Run full FastAPI/CI suite, Node JS parse checks, real-browser staging smoke, and manual mobile/desktop color audit on deployed SHA.
6. Still **missing** before a public/paid launch: transactional email/verified email ownership, shared gateway/edge rate controls, full permission matrix per feature, legal privacy notice, data retention/deletion policy, true tenant checkout/order/payment/refunds, VNPAY merchant production credentials, production migrations and restore drill, live domain mapping, load tests and monitoring.

## References

- Shopify staff permissions: https://help.shopify.com/en/manual/your-account/users/roles/roles
- Fresha team and service workflows: https://www.fresha.com/for-business/features
- Square verified payment notifications: https://developer.squareup.com/docs/webhooks/overview

**All code changes apply only to EZ Thing. No subscription paid upgrade or production merchant transaction is authorized by this release.**
