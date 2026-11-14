> **PLATFORM ADMIN v0.4:** [Quản trị /admin](https://ez-thing-staging.onrender.com/admin) · [Tài liệu quản trị và bảo mật](docs/admin-console-v04.md). Staging có bản DEMO quản trị chỉ đọc. Quyền thao tác thật yêu cầu email được cấp phép + mã bảo vệ riêng (cấu hình trong Render); không cho tài khoản DEMO hoặc khách hàng truy cập.

# EZ Thing — AI Business OS (pilot MVP v0.3)

> **EZ Thing v0.3 — phân tách frontend (14/11/2026):** Truy cập trang giới thiệu tại [`/`](https://ez-thing-staging.onrender.com/), Merchant Back-Office tại [`/app`](https://ez-thing-staging.onrender.com/app), và 4 trang khách hàng DEMO: [`/menu/cafe`](https://ez-thing-staging.onrender.com/menu/cafe), [`/store/mart`](https://ez-thing-staging.onrender.com/store/mart), [`/store/online`](https://ez-thing-staging.onrender.com/store/online), [`/booking/wellness`](https://ez-thing-staging.onrender.com/booking/wellness). Super Admin tại `/admin` chỉ cho phép email được cấu hình server-side và hiện chỉ đọc. **Chỉ công bố các link sau khi deploy và kiểm thử LIVE thành công.**

**Trạng thái:** source code MVP chạy được tại môi trường local/staging độc lập. **Chưa triển khai production, chưa phải hệ thống POS thương mại hoàn chỉnh.** Tên EZ Thing là tên dự án tạm thời, chưa chốt nhãn hiệu.

## 1. Mô hình

- SaaS **Multi-tenant**: một codebase, nhiều doanh nghiệp; mọi truy vấn nghiệp vụ lọc theo `business_id` và kiểm tra quyền thành viên.
- **Basic / Plus / Pro**: quyền dùng module được kiểm tra tại backend. Trong **pilot**, chủ tài khoản có thể chọn gói để thử tính năng mà chưa thanh toán; sau pilot phải có Billing + Entitlement Service xác thực trước khi ra mắt công khai.
- **Onboarding thông minh**: hỏi ngành nghề và nhu cầu, **chỉ bật module đã viết sẵn**. Gợi ý hiện nay dựa trên quy tắc minh bạch, **chưa sử dụng LLM**.
- **F&B trước**: quản lý sản phẩm, bàn, đơn hàng, khách hàng, kho cơ bản, phân tích doanh thu.
- **Retail / Online / Services**: đã có bộ lõi chung (sản phẩm, khách, đơn hàng) nhưng module chuyên ngành của ba nhóm này chưa hoàn thiện.
- **Không dùng chung DB hoặc tài khoản** với Minh Satori.

## 2. Chạy local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# SQLite thử nghiệm mặc định tại ./ezthing.db
./scripts/run-dev.sh
```

Mở: http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/api/docs.

Lệnh kiểm thử:

```bash
pytest -q
node --check app/static/app.js
```

> Để chạy PostgreSQL, đặt `DATABASE_URL=postgresql+psycopg://...`. Không sử dụng database Minh Satori hoặc các dự án khác. Cấu trúc bảng đang tự khởi tạo bằng `create_all` **chỉ cho pilot**; production bắt buộc có migration/versioning và quy trình backup/restore.

## Staging v0.2 — quy trình riêng theo ngành (demo)

Các quy trình có API thật, phân quyền theo doanh nghiệp + module, và giao diện thao tác. Tham khảo [ma trận nghiệp vụ](docs/industry-matrix.md). Hiện tại chưa tích hợp máy in bếp, đơn vị vận chuyển hay SMS thông báo lịch hẹn; các trạng thái là **thao tác nội bộ**.

- **F&B:** phiếu bếp `Chờ xử lý → Đang chuẩn bị → Sẵn sàng → Đã phục vụ`.
- **Bán lẻ:** sổ nhập/xuất tồn kho theo sản phẩm, truy vết biến động thực tế.
- **Bán online:** `Chờ xử lý → Đã đóng gói → Đang giao → Đã giao`; đơn phải có khách hàng và địa chỉ giao.
- **Dịch vụ:** đặt lịch theo dịch vụ, khách hàng và nhân viên; kiểm tra trùng lịch, xác nhận và hủy lịch.

## 3. Tính năng đã viết mã và được test API

| Nhóm | Đã có | Ghi chú |
| --- | --- | --- |
| Tài khoản | Đăng ký, đăng nhập, đăng xuất | Password scrypt, session HttpOnly, CSRF |
| Doanh nghiệp | Tạo nhiều doanh nghiệp, lựa chọn ngành, gói | Pilot không có billing thật |
| Gói | Basic / Plus / Pro, module gating API | Theo danh sách tính năng hiện có |
| Sản phẩm | Thêm, xem, phân loại, giá bán, giá vốn, tồn kho | Mã SKU theo từng business |
| Kho | Trừ kho khi lên đơn; điều chỉnh tồn Plus+ | Không có định lượng nguyên liệu |
| Khách hàng | Tạo/xem hồ sơ, chọn ID trong đơn | Không đoán trùng bằng tên |
| F&B | Tạo bàn, xem trạng thái trống/đang phục vụ | Chưa có đặt bàn, QR, bếp |
| Đơn hàng | Tạo đơn, tổng giá server-side, idempotency | Chưa sửa/hủy đơn, giảm giá/VAT/ship |
| Thanh toán | Đánh dấu đã nhận tiền thủ công | **Không phải xác nhận của ngân hàng** |
| Báo cáo | Dashboard, top sản phẩm, kho thấp, đơn chưa thanh toán | Dựa trên dữ liệu SQL, không sinh bằng AI |
| Chi nhánh | Tạo nhiều chi nhánh cho Pro | Một số nghiệp vụ tổng hợp liên chi nhánh đang ở mức pilot |
| Nhật ký | Ghi audit về các thay đổi chính, xem Pro | Không ghi dữ liệu nhạy cảm vào log |
| UX | Sidebar desktop, bottom nav mobile, modal, toast, SPA | Chưa xác nhận trực quan trên thiết bị thật |
| PWA | Manifest + cache app shell | **Không có offline writes / offline orders** |

## 4. Gói tạm dùng để thử nghiệm

- Basic: 249.000đ/tháng (đề xuất), dashboard, sản phẩm, đơn hàng, bàn, kho cơ bản.
- Plus: 499.000đ/tháng (đề xuất), thêm điều chỉnh kho, phân tích và công nợ đơn chưa thanh toán.
- Pro: 999.000đ/tháng (đề xuất), thêm nhiều chi nhánh và nhật ký quản trị.

Giá chỉ là đề xuất kinh doanh, chưa thu tiền; không chốt pricing trước phỏng vấn khách hàng.

## 5. Những việc bắt buộc trước khi công khai cho khách thật

1. Phát triển migrations PostgreSQL, DB isolation sâu hơn/RLS, backup/restore, TLS, monitoring.
2. Bổ sung rate limiting, xác minh email, MFA quyền admin, quy trình bảo vệ dữ liệu và quyền truy xuất/xóa.
3. Payment gateway, webhook ký số, quản lý gia hạn, hủy và quyền của gói trả phí. Không cho tự chọn Pro như trong pilot.
4. Tích hợp hóa đơn điện tử theo quy định hiện hành; không dùng API PDF thông thường thay chứng từ thuế.
5. Kiểm soát kho F&B theo công thức định lượng nguyên liệu, order status bếp, sửa/hủy/hoàn tiền có đối soát, đồng bộ nhiều thiết bị.
6. Nghiệm thu trình duyệt/thiết bị thật và kiểm thử tải, khôi phục, mất kết nối trước khi dùng POS live.
7. Tích hợp LLM có kiểm soát permission, giới hạn ngân sách, truy vấn read-only và ghi sau phê duyệt.
8. Nhập Excel/Google Sheets, xuất PDF, tích hợp Zalo/đơn bán hàng đa kênh.

## 6. UI/UX

- Nút thao tác chính rõ ràng; tối đa một nút chính trong mỗi khu vực.
- Điện thoại ưu tiên bottom navigation; màn hình lớn dùng sidebar.
- Modal ngắn gọn, phản hồi rõ kết quả API; không báo thành công trước server.
- Dùng từ ngữ tiếng Việt, giá VND, font rõ; có hỗ trợ reduced motion.
- Người dùng được phép thoát onboarding và chọn lại doanh nghiệp. Lỗi phiên/không có mạng không được ghi đè dữ liệu.

## 7. Đối chiếu Minh Satori

Xem [`docs/minh-satori-reuse.md`](docs/minh-satori-reuse.md). Chỉ dùng thiết kế nghiệp vụ và mẫu kiểm tra an toàn; không copy ledger, danh bạ, khóa API hoặc chính sách chiết khấu của Minh Satori.

## 8. Nguồn so sánh công khai

- [Sapo FnB — QR Order](https://help.sapo.vn/qr-order-tren-phan-mem-sapo-fnb)
- [Sapo FnB — giao diện các tab trên app](https://help.sapo.vn/lam-quen-giao-dien-tren-ung-dung-sapo-fnb)
- [Zoho Creator — AI app/workflow](https://www.zoho.com/creator/)

## 9. Các lớp giao diện — v0.3

| Đường dẫn | Đối tượng | Trạng thái |
| --- | --- | --- |
| `/` | Khách đang tìm hiểu EZ Thing | Website giới thiệu, so sánh ngành và giá đề xuất; **không** phải dashboard |
| `/app` | Chủ doanh nghiệp / nhân viên | Back-Office nghiệp vụ từ v0.2, đăng nhập thật ngoài staging hoặc DEMO staging |
| `/menu/cafe` | Khách hàng F&B | Menu, giỏ, chọn bàn, gửi phiếu bếp **DEMO** |
| `/store/mart` | Khách hàng retail | Danh mục, yêu cầu giữ hàng **DEMO**, ghi đơn và sổ kho |
| `/store/online` | Khách hàng online | Danh mục, giỏ, gửi đơn giao **DEMO**, phiếu đóng gói |
| `/booking/wellness` | Khách hàng spa | Dịch vụ, chuyên viên giả, khung giờ trống, đặt hẹn **DEMO** |
| `/admin` | EZ Thing platform operator | Tài khoản nằm trong `EZ_THING_SUPERADMIN_EMAILS`, thống kê **read-only**; DEMO luôn 403 |

Các trang khách hàng demo dùng **cùng backend/DB** của phiên DEMO nhưng gọi API `/api/preview/...` riêng, chỉ trả dữ liệu public-safe; không dùng endpoint /api/businesses đọc thông tin riêng. `preview` chỉ hoạt động khi `EZ_THING_ENVIRONMENT=staging` và `EZ_THING_DEMO_MODE=1`, có session cookie và CSRF. Khách mới được tạo tenant demo riêng biệt. Chưa mở cửa hàng public thật, QR tại bàn công khai, thanh toán tự động hay kết nối shipper. Xem thêm [`docs/public-frontends-v03.md`](docs/public-frontends-v03.md).