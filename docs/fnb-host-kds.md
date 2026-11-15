# EZ Thing — F&B Navigation, Front Desk & Kitchen Display

## Industry-first mobile navigation

- **F&B:** Tổng quan → Đơn hàng → Đặt bàn → Bếp → Thêm.
- **Retail:** Tổng quan → Đơn hàng → Sản phẩm → Khách hàng → Thêm.
- **Online:** Tổng quan → Đơn hàng → Sản phẩm → Giao hàng → Thêm.
- **Services:** Tổng quan → Lịch hẹn → Sản phẩm/Dịch vụ → Khách hàng → Thêm.

All entries are permission- and plan-filtered by the original `menuItems` function. Disabled modules are not impersonated. Primary mobile tabs are excluded from More; remaining modules are sorted by industry. Desktop sidebar uses the same prioritized group. If a planned tab is disabled, the closest available module is used as fallback. No user data or database schema is modified by navigation.

## Lễ tân & xếp bàn (formerly Vận hành)

This name explicitly describes staff-managed **waitlist, customer arrivals, manual seating, reservation deposit requests and floorplan**. Shortcuts lead to the existing Reservation Manager, Floorplan and Kitchen. Other existing operational tools (shifts, inventory, recipe and expenses) remain below.

- Existing waitlist requires server-controlled branch capacity before seating.
- “Ready” in waitlist is an **internal status**. It does **not** send real SMS/Zalo/email.
- Deposits are requests only; marked `pending_gateway`, no charge or payment confirmation.
- Staff do not see manager-only deposit or ingredient recipe forms, and their API is not queried.
- This release does not implement real payment, split/merge, external carrier communication or cross-table physical combinations.

## Kitchen & Bar

### Sending
1. POS creates and prices `SaleOrder` with selected modifiers and stock deductions.
2. Kitchen tab presents pending-to-fire orders. Authorized staff presses **Gửi bếp**.
3. Same `IndustryWorkItem` kitchen ticket is reused; repeated Fire calls are idempotent.
4. On first send, ticket snapshots the existing `SaleOrderItem` IDs, name, quantity, Size/Topping, note and prep station. Kitchen does not reprice or deduct any additional stock.
5. The old `/industry/kitchen` API continues to create and read the same kitchen job. For legacy jobs without snapshots, the KDS GET exposes a read-only compatibility view. First KDS write snapshots under row lock.

### Stations
- `bar` — Pha chế
- `hot` — Bếp nóng
- `cold` — Bếp lạnh
- `expo` — Ra món, showing ready dishes from **all stations** plus unknown-unassigned dishes.

Managers can assign future items to a prep station and transfer an in-progress item to another station with a reason. Unassigned items get heuristic suggestions from menu name/category; unknowns remain Expo. Current tickets are unaffected by changing catalog-wide station rules.

### Per-item status
- `pending → preparing → ready → served`
- `pending/preparing → held → preparing`
- Manager-only recalls: `ready → preparing` or `served → ready` with a reason.
- Full ticket is served only when **all** its items are served; cross-device changes require matching `kds_revision` or 409 Conflict.
- Ready dishes can get an **internal call-runner flag**. It appears on synced KDS tabs, but does not dispatch actual push, SMS or messages.
- Manager-only sold-out flag maps to the original `Product.active` and is audited. It impacts future checkout validations, not historic order or kitchen snapshots.
- Legacy whole-ticket state changes remain supported for uniform item state; mixed state tickets require the individual KDS flow.

### Device UI
- Group by ticket or by item.
- Station filters, branch filters, active counts, All Day unserved unit counts.
- Timer with warning at 3 minutes and overdue at 7 minutes.
- Large touch targets, responsive mobile/tablet, Apple blue/Tropical green/Graphite dark tokens.
- 5-second foreground-only polling, no forced page reload. Opt-in Web Audio alerts when a new ticket arrives, subject to browser permission and foreground activity.
- Browser Print sends the ticket to the OS print dialog, **no printer driver or physical KDS printer integration**.
- Fullscreen button uses browser Fullscreen API where available.
- No automatic background delivery, device-level push, LAN offline queue, real-time WebSocket or guaranteed audible alarm when the screen is asleep.

## Persistence / safety
- No new database tables. The canonical work item and its JSON `details` hold snapshot and status; product routing uses scoped `kds_route` work items.
- All endpoints re-check tenant, module entitlement, staff role and CSRF.
- Current SaleOrder, stocks, inventory movements, payment state and booking data are untouched by KDS state transitions.
- Do not enable production before stage testing, backups/restore, and explicit approval.

## Market design references

- Toast KDS setup and production item count: https://support.toasttab.com/en/article/Get-Started-With-the-Kitchen-Display-System
- Toast item-level vs full ticket fulfillment: https://support.toasttab.com/en/article/Item-and-Order-Fulfillment-on-KDS
- Toast prep stations and Expo: https://support.toasttab.com/en/article/Basic-Kitchen-Configuration
