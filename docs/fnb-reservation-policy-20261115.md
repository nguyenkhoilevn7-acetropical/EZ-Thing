# F&B booking availability policy — 2026-11-15

## Market references

- [Toast Tables: schedules, 15/30-minute increments, max covers, online booking access, special dates](https://support.toasttab.com/en/article/Getting-Started-Toast-Waitlist)
- [Toast Tables: diagnosing unavailable slots and blocked dates](https://support.toasttab.com/en/article/Get-Help-with-Toast-Tables-Online-Waitlist-Reservations)
- [Fresha: appointment calendar, staff, resources, reminders and waitlist](https://www.fresha.com/for-business/features)
- [Shopify POS: inventory across locations](https://www.shopify.com/pos/features)

## Shipped in this PR

EZ Thing already had slot verification, seating zones, assignment and conflict prevention.
However, public contact hours were decorative and the booking API always used 08:00–20:30
and 22:00 closure. This branch introduces an owner-controlled booking policy rather
than pretending that arbitrary contact text is an operational schedule.

In Merchant Back-Office **/app > Đặt bàn**, the booking policy editor supports:

- Local opening time, last seating time, closing time (30-minute precision).
- Weekly closure days (Monday=0 to Sunday=6).
- Up to 60 individual blackout dates (ISO YYYY-MM-DD).
- VN/EN labels and existing Apple Blue/Tropical/Graphite theme variables.

This is a **business-level** policy applied to all its branches; per-branch hours,
shift caps, waitlist, notifications, booking deposits, holidays auto-sync and
external calendar integrations are **not** implemented in this PR.

## API

- `GET /api/businesses/{bid}/reservations/policy`: authenticated tenant member.
- `PUT /api/businesses/{bid}/reservations/policy`: tenant owner only, CSRF-protected.
- `GET /api/preview/cafe/reservations/policy`: existing staging visitor preview scope only.

Example:

```json
{
  "open_time": "08:00",
  "last_seating_time": "20:30",
  "close_time": "22:00",
  "closed_weekdays": [1],
  "blocked_dates": ["2026-12-25"]
}
```

New/legacy businesses preserve default 08:00–20:30 and closing 22:00.
The payload is validated by Pydantic; 422 for malformed/conflicting times,
invalid weekdays or duplicate blackout dates. Updates are written to the
existing tenant-scoped `businesses.setup.reservation_policy` JSON field;
no new PostgreSQL table or migration.

## Data invariants

- All new requests go through server-side `valid_start` and capacity checks.
- Availability returns `slots: []` and `closed_reason` for closed days.
- Existing reservations remain unchanged if settings change after booking.
- Idempotent retries with the original request id return the existing booking,
  even when the new schedule would prevent another booking at that time.
- Only owners may update the policy. Other tenant access is handled by the
  existing `fnb_scope/tenant` guard.
- No payment processing, card/token storage, SMS dispatch, bulk reservation
  mutation or production merchant data modification.

## Verification gates

1. GitHub Actions `EZ Thing pilot tests` succeeds on PR #45.
2. Review calendar-rule tests (closed weekdays, special dates, invalid times,
   idempotent retry, existing status workflow) and `node --check` for the
   integrated merchant JavaScript.
3. Review Apple Blue/Tropical/Graphite light/dark on desktop, mobile/fold:
   label contrast, focus, checkbox states, no navigation loss.
4. After explicit staging release approval: deploy **My Workspace** Render
   service because auto-deploy is disabled; verify `/api/ready`,
   `/app?tab=reservations` and test tenant UI and API end-to-end.
5. Do **not** enable public production bookings or payment until separately
   validated and approved.
