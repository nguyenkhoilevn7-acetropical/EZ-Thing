# EZ Thing — Platform Admin v0.4 (staging pilot)

## Entry point

- Platform: `https://ez-thing-staging.onrender.com/admin`
- Marketing: `/`, Merchant: `/app`, Customer demo: `/menu/cafe`, `/store/mart`, `/store/online`, `/booking/wellness`

The `/admin` UI is **separate from** the business back-office. All privileged APIs are under `/api/admin`.

## Modules available

| Module | Functionality |
| --- | --- |
| Overview | Real non-demo tenant/user/order counts, pilot plan distribution, recent admin activities. Does **not** claim MRR, paid subscriptions or revenue. |
| Businesses | Search/filter; detail, owner, members, branches, module list, safe pilot plan override; suspend and resume with explicit confirmation. |
| Accounts | Search/filter; memberships; temporary block/unblock; revoke sessions immediately when blocking. Do not block platform administrators. |
| Plans | Current Basic/Plus/Pro entitlements and **proposed** prices, explicit billing-not-live state. |
| Audit | Append-only API interface for administrative events with actor, target, before/after and reason. No delete endpoints. |
| System | API/PostgreSQL reachability, environment configuration flags, explicit gaps for migrations, billing, backups, email verification and full MFA. |

Staging includes a **synthetic read-only demo** of `/admin` using a fixed in-code sample. The preview does not query real users, businesses, customer records or orders; buttons cannot make real changes.

## Security model

1. A real `/api/auth/login` account with email in `EZ_THING_SUPERADMIN_EMAILS` is required. Self-registration is **not email-verified** in this pilot; never rely on the allowlist alone.
2. A second, independent `EZ_THING_ADMIN_ACCESS_KEY` (minimum **32 characters**, high entropy) must be configured as a Render **secret environment variable**, never committed to source control or embedded in JavaScript.
3. The user unlocks their own server session through `POST /api/admin/unlock` with the key and the regular anti-CSRF header. The server stores only a per-session authorization record tied to the login session and a hash revision of the key. Unlock expires in **30 minutes**, and is revoked on logout/session deletion.
4. Five failed key entries in a session impose a 15-minute lockout. A stolen login cookie is insufficient without the second secret. Demo users are excluded, independent of the allowlist.
5. All reads and writes re-check the server-side allowlist and unlock, while writes also require the per-session CSRF token. No platform permission derives from a tenant membership or pricing tier.
6. Critical actions require a reason; business suspension requires exact business name; user suspension requires exact email; plan changes require explicit confirmation. No permanent deletion or impersonation endpoints.
7. Business suspension is enforced by merchant-scoped API authorization and the public customer preview scope. Account suspension revokes all sessions and denies new login until reactivated.
8. New tables: `platform_tenant_controls`, `platform_user_controls`, `platform_admin_unlocks`, `platform_unlock_attempts`, `platform_action_log`. No alterations or destructive migration to existing operational tables.

### Secure configuration

Configure in **Render → My Workspace → ez-thing-staging → Environment**:

- `EZ_THING_SUPERADMIN_EMAILS`: comma-separated list of pre-existing real EZ Thing account email addresses (not demonstration accounts).
- `EZ_THING_ADMIN_ACCESS_KEY`: a randomly generated, high-entropy independent key, minimum 32 characters. Distribute through a secure password manager; **do not send via public chat or email**.
- Keep `COOKIE_SECURE=1`, `EZ_THING_ENVIRONMENT=staging` and `EZ_THING_DEMO_MODE=1` for the staging preview; disable `EZ_THING_DEMO_MODE` and harden the entire system before real users.

The admin console is operationally **locked until configured**. Use "Xem bản DEMO quản trị" to preview all screens without secrets.

## Operational constraints and remaining work

- Plan change **only** adjusts pilot entitlements. No payment capture, subscription renewal, refund, invoice issuance, webhook or MRR.
- Business/user actions are reversible and do not delete customer orders or products. No global bulk destructive operations.
- All users can still self-select pilot tiers upon creating a business; public billing has not been released.
- Email verification, phishing-resistant MFA for platform operators, RBAC team delegation, rate limiting at ingress, tamper-evident audit storage, fully verified backup/restore and Alembic migrations are still required before production.
- Free Render/Neon resources do not meet production operational and durability requirements.
- Existing business and user data must not be shared across tenants. Changes to production data must require explicit operational approval beyond the feature implementation.

### Test plan

- `pytest -q` (old core/API cases plus `tests/test_platform_admin.py`).
- `node --check app/static/admin.js`, and existing frontend JS checks.
- Use real Chromium/mobile acceptance to verify menu, filters, modal, confirmation forms and no horizontal overflow; staging demo is synthetic.
- Verify `/api/admin/summary` returns 401 anonymous, 403 regular/demo accounts or locked admins, 503 if secret not configured, and 200 only after full unlock.
- Verify blocked tenant gets 403 from merchant APIs and customer preview; blocked user has all sessions revoked and cannot log in.
- Review log records after every privileged mutation; check billings flags remain inactive.

## Reference models and security

- [OWASP Multi-Tenant Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)
- [Auth0 Organizations: tenant roles and membership](https://auth0.com/organizations)
- [Stripe Billing (actual subscription payments are *not* part of EZ Thing pilot)](https://stripe.com/billing/features)