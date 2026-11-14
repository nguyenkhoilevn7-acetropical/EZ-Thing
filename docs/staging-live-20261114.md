# EZ Thing — staging deployment record (2026-11-14)

## Current deployment (verified through connected Render and Neon)

- Website + API: https://ez-thing-staging.onrender.com
- Render workspace: **My Workspace** (workspace ID `tea-db65rlid0e5s739ghkpg`)
- Web service: `ez-thing-staging` (`srv-dbrv3nbrjlhs73cmrtog`), Free plan, Singapore.
- Docker service serves both the static SPA and FastAPI from the same origin.
- Initial deployed commit: `0e1b8404f3559ec3699f4860499f08493d29b8c6`.
- Initial Render deploy: `dep-dbrv3obrjlhs73cms290` — status `live` at 2026-11-14T05:31:16Z.
- Public homepage logged `GET / HTTP/1.1 200 OK`; Uvicorn startup completed.
- Database: **Neon Free**, a separate project `ez-thing-staging` (`summer-sunset-54214737`), Postgres 18, Singapore.
- SQL readback confirmed **12 application tables** in Neon: users, sessions, businesses, memberships, branches, customers, products, dining_tables, sale_orders, sale_order_items, stock_movements, audit_events.
- Render Environment holds `DATABASE_URL` as a private value. Never copy the connection URI into GitHub, issues, logs, tickets, chat, or client JS.
- `COOKIE_SECURE=1` and `autoDeploy=no`.
- Verified GitHub Actions success on commit `0e1b8404f3559ec3699f4860499f08493d29b8c6`.

## Why Neon instead of a new Render Free Postgres?

The workspace already has an active Free Render PostgreSQL instance used for Minh Satori. Render permits only **one active Free PostgreSQL per workspace**. The originally approved Blueprint for a second Free Postgres cannot be applied as planned. An earlier Blueprint object `exs-dbrv0c56e07s738bgid0` exists but did not produce the intended resources during inspection; its old plan is **superseded**, not the source of the live service.

Do not re-approve or clone the old plan without reviewing resource duplication. The actual live service was created separately via Render, with an independent Neon database.

## Live deployment operations

1. Review and merge code changes; run `pytest -q` and `node --check app/static/app.js` (CI should pass).
2. In Render **My Workspace**, open `ez-thing-staging` and deploy the desired reviewed GitHub commit manually (auto-deploy is disabled).
3. Check Render deploy state `live`, app startup logs and `/api/health`.
4. Confirm database access using a **read-only query** from the dedicated Neon project.
5. Run test-only sign-up, business creation, product/customer/order flows with fake data. Never use real customer records.
6. Inspect mobile/desktop UI in a browser and test API errors, session expiry, popup behavior, and viewport layout.
7. Keep credentials in Render/Neon environment settings only; rotate credentials immediately if exposed.

## Explicit limitations

- Pilot schema is created using SQLAlchemy `create_all`; **no Alembic migrations** yet.
- No verified end-to-end browser/device acceptance, production payments, LLM, commercial e-invoices, regulatory readiness, or formal load tests.
- Neon Free limits apply (compute, storage, transfer, idle suspension). Render Free may suspend the service when idle; first request may be slow.
- Unsecured user-facing pilot sign-up and self-selected Basic/Plus/Pro tiers are not a production billing/authentication system.
- Not suitable for real orders, payment collection, or sensitive customer data.

## No cross-project coupling

The EZ Thing backend does **not** connect to Minh Satori ledger, Render PostgreSQL, or other Neon projects. Existing apps must remain untouched.

## Links

- Repo: https://github.com/nguyenkhoilevn7-acetropical/EZ-Thing
- Render service: https://dashboard.render.com/web/srv-dbrv3nbrjlhs73cmrtog
- Neon console: https://console.neon.tech
- Render Free limits: https://render.com/docs/free
- Neon Free limits: https://neon.com/docs/introduction/plans
