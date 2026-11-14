# EZ Thing F&B table reservations and contact — staging v0.5

## Separate frontend and merchant back-office

- Guest: https://ez-thing-staging.onrender.com/reserve/cafe
- Merchant: https://ez-thing-staging.onrender.com/app/reservations
- Existing cafe menu: /menu/cafe with new **Đặt bàn** entry
- Merchant dashboard: /app with new **Đặt bàn trước** navigation for F&B tenants only
- Existing ordering and wellness booking flows remain unchanged.

## Implemented

- 30-minute arrival slots 08:00–20:30 Vietnam time, 30-minute notice, 30 days ahead
- Valid durations 60/90/120 minutes, group size 1–20, automatic choice of smallest table that fits
- Capacity and overlapping time reservations checked on server
- PostgreSQL advisory transaction lock per business prevents concurrent double booking
- Guest submits name, phone, optional note; status **pending** only (not confirmed)
- Merchant creates bookings, filters dates/statuses, confirms, seats, completes, cancels, records no-show
- Status transitions enforced: pending→confirmed/cancelled; confirmed→seated/cancelled/no_show; seated→completed
- Merchant publishes phone, email, address, opening hours (display only; booking hours fixed)
- Guest can phone/email directly when contact is configured, or send a DEMO inquiry
- Merchant contact inbox supports contacted/closed status and click-to-call
- Booking history stored as \`IndustryWorkItem(kind='reservations')\` and inquiries stored as \`IndustryWorkItem(kind='inquiries')\`
- Audit events record changes, reuse existing Business/Customer/DiningTable models, no second database
- Idempotency keys prevent repeated bookings from accidental double-taps
- Tenant boundary and CSRF checks required for all operations

## Explicit pilot constraints

**Do not mistake this for public production reservations.** Guest routes require a STAGING-only disposable DEMO identity and may not read non-demo businesses. No actual customer-facing anonymous booking enabled. No automatic email/SMS/Zalo, calendar sync, payment, deposits, branch-specific capacity, waitlist or table combining. Phone/email contact actions use the device's call/email app and do not claim a notification was delivered.

- Booking availability does not yet integrate live open POS orders, multi-table joining, walk-ins, server shift changes or restaurant-specific configurable service hours.
- Merchant change of contact details requires owner role.
- Reservations are stored in the existing pilot \`industry_work_items\` table; before commercial launch add Alembic migrations and formal retention/PII policy.
- Database is isolated Neon staging; no access to Minh Satori or other projects.

## Test criteria

- \`pytest -q\` includes \`tests/test_reservations.py\`.
- \`node --check app/static/reservations.js\` is included in CI.
- Confirm slots reflect party size, daylight/local timezone, notice window and duration.
- Creating a reservation for all available 6-seat tables during an overlapping window must fail 409.
- Replaying identical request ID must not create a second booking; changed payload must fail 409.
- Cancellation frees a table unless another reservation overlaps it.
- Check guest cannot access another tenant's booking, inventory, private contact records, or real businesses.
- Verify merchant status changes show in guest status lookup.
- Test visitor and merchant UI on real mobile and desktop before production use.

Reference implementations informing field selection and statuses:
- Sapo FnB: https://help.sapo.vn/tao-don-dat-ban-tren-phan-mem-sapo-fnb
- Sapo FnB overview: https://help.sapo.vn/xem-danh-sach-dat-ban-tren-trang-quan-tri-sapo-fnb
- OpenTable: https://support.opentable.com/s/article/Manage-reservations-on-OpenTable?language=en_US
