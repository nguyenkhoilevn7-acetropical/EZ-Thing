# Trạng thái triển khai — 14/11/2026

**Đã làm:** source độc lập, API & SPA, 14 unit/integration tests chạy local, JS syntax check, tài liệu Minh Satori và UI. Kết quả local không đồng nghĩa production E2E.

**Đã cập nhật:** GitHub repository EZ-Thing, Pull Request #1, GitHub Actions CI PASS tại commit đầu tiên và `render.yaml` blueprint staging cô lập. **Chưa làm:** xác nhận workspace Render để triển khai, tạo PostgreSQL managed riêng, kiểm thử smartphone, triển khai production. Không ảnh hưởng bất kỳ hệ thống đang vận hành nào.

## Lộ trình staging an toàn

1. [HOÀN THÀNH] Repo riêng `nguyenkhoilevn7-acetropical/EZ-Thing`; không sửa Minhsatori, DinkSocial, Ruler-AI, ACE Inventory AI.
2. [HOÀN THÀNH] Push đầy đủ source trực tiếp vào nhánh phát triển và kích hoạt GitHub Actions.
3. Tạo PostgreSQL riêng cho EZ Thing, dùng secret `DATABASE_URL` phía server; không commit mật khẩu.
4. Chuẩn bị migrations ban đầu, snapshot/restore và kiểm tra isolation trước khi nhập dữ liệu thật.
5. Triển khai web service HTTPS từ Dockerfile; `COOKIE_SECURE=1`.
6. Chạy thử 2 doanh nghiệp giả khác nhau, 2 user khác nhau. Kiểm tra 403/404, toàn bộ quyền gói, refresh mobile, app shell.
7. Thử tạo đơn lặp, ghi nhận tiền, mất mạng, khôi phục, tải 50+ người đồng thời.
8. Kiểm tra màn hình với Android/Samsung Fold, iPhone, tablet và desktop; accessibility và cử chỉ popup.
9. Tách pilot billing/plan selection khỏi checkout chính thức; không công khai gói Pro miễn phí.
10. Chỉ sau khi hoàn tất checklist và duyệt bảo mật mới mở cho khách thật.

## Dev commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
./scripts/run-dev.sh
pytest -q
```

Do môi trường duyệt Chromium chặn cả `localhost` và `file://`, screenshot QA không thực hiện được ở phiên này; cần kiểm thử trực quan trong môi trường phù hợp trước khi nghiệm thu.

## Render Blueprint (chuẩn bị, chưa kích hoạt)

- `render.yaml` khai báo web service Docker `ez-thing-staging` và PostgreSQL riêng `ez-thing-staging-db` trong **cùng workspace đã được chủ dự án lựa chọn**.
- `autoDeployTrigger: 'off'` ngăn tự triển khai khi push. `COOKIE_SECURE=1` dành cho HTTPS.
- Render Free PostgreSQL chỉ tồn tại tối đa 30 ngày và giới hạn 1 DB Free/workspace. Chỉ dùng dữ liệu giả; sao lưu hoặc nâng cấp trước khi hết hạn.
- Không được bật staging bằng cơ sở dữ liệu Minh Satori hoặc dùng SQLite lưu trữ thật trên Render không có persistent disk.
- `Base.metadata.create_all()` là cơ chế pilot, phải thay bằng migrations versioned trước khi có dữ liệu kinh doanh thật.
