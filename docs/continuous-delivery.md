# EZ Thing — Continuous Releases

## Quyết định

- Tên website luôn là EZ Thing. Không tăng số V8/V9 hay ngày cache trên giao diện mỗi khi nâng cấp.
- Theo dõi code bằng Git commit SHA / PR / CI / Render deployment. Không bắt khách cài lại ứng dụng web.
- Chuỗi migration PostgreSQL và hợp đồng API vẫn quản lý độc lập, không đổi/sửa số migration cũ.
- Không cưỡng bức tải lại trang đang mở khi người dùng nhập đơn hoặc xác nhận tiền.

## Cơ chế tự động

Ứng dụng dùng module app/asset_pipeline.py. Ngay khi server khởi động, nó tính SHA-256 của JS/CSS/SVG/PNG và các tài nguyên tĩnh. HTML được server chuyển mọi link cũ ?v= hoặc link chưa có query thành ?h=HASH_THẬT theo bytes đang phục vụ. Nguồn HTML legacy không bắt buộc đổi mã version; không sửa tay ?v nữa khi làm tính năng mới.

- Trang HTML của frontend, merchant, Admin, booking, site riêng doanh nghiệp, owner preview: no-store.
- Asset có hash đúng: public, max-age=3600 (không immutable 1 năm vì tên file gốc có thể đổi nội dung sau deploy).
- Asset cũ với ?v= hoặc không hash: no-cache, must-revalidate, giúp logo và asset JS sinh DOM không bị cũ.
- Manifest PWA: icon được hash tự động, no-cache.
- Service worker: tự sinh khóa cache ezthing-shell-SHA và danh sách preload JS/CSS/icon + HTML tĩnh; online network-first, offline fallback. SW không bao giờ intercept /api/*, request ghi hay dữ liệu theo doanh nghiệp.
- Sửa một file CSS hoặc JS làm URL của chính file đó thay đổi, không đụng tới hash của các file còn lại. Thay đổi HTML vẫn tạo worker mới.

## Phát hành an toàn

1. Tạo branch có tên nghiệp vụ, không theo số V.
2. Viết test, sửa code, tạo PR. Không thêm suffix phiên bản thủ công.
3. CI phải PASS pytest, JS syntax, Chromium browser smoke.
4. Chỉ merge sau khi CI PASS.
5. Staging Render hiện autoDeploy OFF: trigger deploy thủ công hoặc kết nối workflow có deploy-hook secret và cổng CI nếu muốn tự động staging. Không tự deploy production khi chưa có phê duyệt.
6. Xác minh Render deploy LIVE, readiness API, URL tài nguyên hash và browser sau deploy.
7. Production phải có kế hoạch migrate Alembic, backup và kiểm thử khôi phục.

## Super Admin

Tab Hệ thống hiển thị một phần Triển khai liên tục với commit SHA và asset fingerprint của build hiện tại. API /api/admin/system chỉ cho Super Admin đã mở khóa, không tiết lộ khóa hoặc DB URL. Đây chỉ là nhận diện build đang chạy; **chưa phải lịch sử release đầy đủ**. GitHub PRs/commits và Render deployments vẫn là lịch sử release thực tế.

## Kiểm thử

- pytest -q
- node --check app/static/sw.js
- node --check app/static/admin.js
- python tests/live_demo_browser.py

Bộ test_continuous_releases kiểm tra: hash tự đổi khi file thay đổi; cache đúng/sai hash; HTML phiên bản cũ tự chuyển sang hash; SW không cache API, dữ liệu tài chính hoặc request ghi; và Admin không hiển thị số version.

## Giới hạn

Query-hash dùng đường dẫn file cố định nên không bật Cache-Control immutable một năm. Khách đang mở tab sẽ tiếp tục phiên làm việc đến lần điều hướng hoặc refresh tiếp theo; không ép reload giữa lúc thao tác tài chính. Khi yêu cầu lịch sử deploy lâu dài ngay trong Admin, cần tích hợp GitHub/Render read-only có xác thực riêng; không tạo sự kiện giả hoặc DB thứ hai.
