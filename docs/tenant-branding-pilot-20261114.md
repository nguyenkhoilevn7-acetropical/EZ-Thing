# EZ Thing — Tenant Storefront Branding (Pilot)

**Scope:** Restaurant/cafe first, reusable across Retail, Online Shop and Services. No separate database per merchant.

## How customers get unique storefronts

- Each business already owns a unique `business_id` and tenant-scoped catalog.
- Brand Studio is a private authenticated Merchant App area: `/app/storefront-design?bid=<business_id>`.
- Owners can open `/preview/site/<business_id>`. The server enforces membership and owner role. It is **not a public consumer URL**.
- For staged *demo* tenants, the existing customer frontend (`/menu/cafe` and other channels) reflects saved tenant branding. No order/payment data leaks from other tenant accounts.
- Data persists under `Business.setup.storefront` (existing JSON column), with a server-side allowlist for fields and image URLs. Real orders, VAT, invoices and payment flows are unchanged.

## Available customization (server-enforced; price proposals only)

| Capability | BASIC 249,000₫/mo* | PLUS 499,000₫/mo* | PRO 999,000₫/mo* |
| --- | --- | --- | --- |
| Business name, description, phone, address | Yes | Yes | Yes |
| Choose a preset banner | Yes | Yes | Yes |
| Owner-only storefront preview | Yes | Yes | Yes |
| Custom banner URL and logo URL (approved CDN) | No | Yes | Yes |
| Hero title and accent color | No | Yes | Yes |
| Layout style: Classic, Editorial, Gallery | No | No | Yes |
| Custom footer note | No | No | Yes |
| Existing branch limit | 1 | 1 | 10 |

*Pilot pricing hypotheses, not live subscription payments.*

### Backend

- GET `/api/storefront/plans`: machine-readable plan capabilities.
- GET `/api/businesses/{id}/storefront`: current plan, effective branding, allowed fields, private preview link.
- PATCH `/api/businesses/{id}/storefront`: owner-only, CSRF-validated, audit-logged. Unsupported plan fields fail with HTTP 403 and code `BRANDING_PLAN_REQUIRED`.
- GET `/api/businesses/{id}/storefront-preview`: owner-only, safe product fields only, no customer data.
- GET `/preview/site/{id}`: owner-only HTML preview; no real checkout.

### Security rules

1. **Do not claim public publishing is enabled.** It is deliberately disabled until a separately reviewed customer-facing publishing workflow exists.
2. Do not put business-editable CSS, HTML or JavaScript in the storefront.
3. The pilot accepts only HTTPS `images.unsplash.com/photo-...` images. A durable uploads service (object storage with image scanning/transforms, tenant access controls, file-size and MIME checks) is required before merchant-supplied photos are production-ready.
4. No public-facing URL slug, DNS verification, custom domain, checkout activation or paid billing is implemented in this phase.
5. Downgrade behavior: paid-tier fields remain stored but are omitted from the **effective** storefront for the lower tier; re-upgrading can restore them.
6. DB must use reviewed versioned migrations, backup/restore and a real billing entitlement system before production rollout; pilot `create_all` is not production-safe.

## Industry comparisons

- **Toast Online Ordering:** merchant-specific logo, banner and public links, including per-location branding; https://support.toasttab.com/en/article/Customize-Your-Online-Ordering-Site
- **Toast Websites:** site editor for theme, typography, navigation, banners and storefront layout; https://support.toasttab.com/en/article/Optimize-Toast-Websites
- **Toast Online Ordering Pro:** plan-dependent theme, colors, typography and layout; https://support.toasttab.com/en/article/Getting-Started-with-Toast-Online-Ordering-Pro

## Manual acceptance checklist

1. Create two different restaurants under separate accounts, set unique names and banners; verify isolation.
2. Edit BASIC name, description and preset. Attempt locked PLUS field -> 403.
3. Edit PLUS logo/banner URL, hero title and palette. PRO can switch layout and change footer.
4. Verify private previews are inaccessible without the corresponding owner session.
5. Verify Mobile 360px, Tablet 768px and Desktop 1440px.
6. Verify VI/EN switch in marketing, Brand Studio, owner preview and admin plan cards.
7. Verify app checkout, order pricing, restaurant reservations and all other existing business flows remain unchanged.
