# EZ Thing v0.3 — Public, Merchant, Customer, Platform Admin

**Ngày:** 2026-11-14. **Môi trường:** staging/pilot only. **Dữ liệu:** dùng tài khoản demo riêng theo phiên, không liên quan Minh Satori.

## Nghiên cứu nguồn tham chiếu

- **Sapo FnB**: QR order có menu dành cho khách, chọn bàn, thao tác gọi món rồi xử lý đơn tại POS/bar. Trang khách và trang quản lý có hai vai trò độc lập. [Nguồn](https://help.sapo.vn/qr-order-tren-phan-mem-sapo-fnb) và [nguồn](https://help.sapo.vn/van-hanh-qr-order-tai-ban-tren-ung-dung-sapo-fnb).
- **Sapo Web Order**: tạo link bán hàng, khách xem thực đơn rồi gửi đơn về back-office. [Nguồn](https://www.sapo.vn/fnb-ban-hang-online-web-order.html).
- **Fresha**: khách xem dịch vụ, chọn chuyên viên, ngày giờ; đơn đặt lịch cần định danh đủ an toàn, tránh spam/no-show. [Nguồn](https://www.fresha.com/help-center/knowledge-base/online-presence/102398-learn-how-clients-book-appointments-online).

## Giao diện

1. `/`: landing page EZ Thing SaaS: giải pháp, 4 ngành, bảng giá thử nghiệm, link storefront và vào Merchant Back-Office.
2. `/app`: Merchant Back-Office, quản lý đơn hàng/sản phẩm/kho và các workflow theo ngành; có đường dẫn "Xem frontend khách hàng" chỉ trong DEMO.
3. `/menu/cafe`: cửa hàng F&B: xem menu/giá, chọn bàn, giỏ, gọi món DEMO; backend tạo đơn + phiếu bếp đồng nhất trong một transaction.
4. `/store/mart`: khách retail: duyệt sản phẩm, giỏ, yêu cầu giữ hàng DEMO; backend tạo đơn chưa thanh toán, cập nhật tồn kho.
5. `/store/online`: khách online: giỏ, thông tin giao, đặt hàng DEMO; backend tạo đơn + phiếu giao hàng nội bộ (không kết nối hãng vận chuyển).
6. `/booking/wellness`: khách Spa: lựa chọn dịch vụ, chuyên viên demo, ngày/giờ khả dụng trong 21 ngày, đặt lịch DEMO; server kiểm tra lịch trùng và transaction lock.
7. `/admin`: tên miền quản trị tách riêng đường dẫn, backend chỉ cho phép email server-side `EZ_THING_SUPERADMIN_EMAILS`; mode read-only; không có cách demo vượt quyền.

## Bảo mật / giới hạn

- **Không** mở nội dung private của doanh nghiệp không thuộc demo. Customer preview chỉ đọc tên/sku/giá/tình trạng bán, không trả giá vốn, tồn số lượng, số điện thoại khách, audit hay doanh thu.
- Tài khoản DEMO chỉ được tạo nếu có **hai biến môi trường** `EZ_THING_ENVIRONMENT=staging`, `EZ_THING_DEMO_MODE=1`. Cần cookie phiên hợp lệ và CSRF cho POST. Hoạt động của demo bị giới hạn số lượng.
- Mỗi khách xem tạo một chủ tài khoản DEMO tạm + 4 doanh nghiệp mẫu; data sẽ lưu vào DB staging thử nghiệm. Chưa có cơ chế cleanup định kỳ; cần bổ sung TTL cleanup trước khi public rộng rãi.
- Đơn từ storefront được server tính giá theo Product hiện hành. Lặp request_id hợp lệ không trừ kho hai lần; request_id với nội dung khác báo conflict.
- Lịch spa tự chọn theo mẫu 09:00–18:00, 3 chuyên viên **giả**; không phải lịch của nhân viên thật. Có advisory transaction lock trên PostgreSQL.
- Super Admin chỉ có thống kê tổng hợp; chưa có billing dashboard, phân quyền chi tiết, suspend/restore tenant, quản lý app, webhooks hoặc email sign-in thật. Không cấu hình `EZ_THING_SUPERADMIN_EMAILS` mặc định.
- Chưa có xác minh khách hàng qua OTP, rate limiting phân tán, chống abuse toàn diện, tạo mã QR sản xuất, kiểm soát PII, chính sách quyền riêng tư, thanh toán hay e-invoice. **Không sử dụng cho đơn hàng thật hoặc khách hàng thật.**

## Kiểm tra

```sh
python -m pytest -q
node --check app/static/app.js
node --check app/static/customer.js
node --check app/static/admin.js
node --check app/static/sw.js
```

Kiểm tra thủ công khi staging Live:
- Mở `/` trên desktop/điện thoại: chỉ thấy marketing, không thấy Dashboard.
- Mở `/app`: vào back-office DEMO; nút xem frontend theo ngành.
- Mở 4 storefront: xác nhận menu dịch vụ thay đổi đúng ngành; tạo đơn trong DEMO, quay về `/app` thấy đúng dữ liệu.
- Kiểm tra `/admin` từ demo luôn bị từ chối; test role có allowlist bằng account thật riêng nếu được phê duyệt.
- Không bật auto deploy production; không thay database Minh Satori.