# Trạng thái triển khai — 14/11/2026

**Đã làm:** source độc lập, API & SPA, 14 unit/integration tests chạy local, JS syntax check, tài liệu Minh Satori và UI. Kết quả local không đồng nghĩa production E2E.

**Chưa làm:** tạo repository chính thức, staging cloud, database managed, CI live, trỏ domain, thử nghiệm smartphone thực tế, triển khai production. Không ảnh hưởng bất kỳ hệ thống đang vận hành nào.

## Lộ trình staging an toàn

1. Tạo repo mới độc lập, không đưa vào Minhsatori, DinkSocial, Ruler-AI, ACE Inventory AI.
2. Push ZIP/bundle vào repo mới; bật CI workflow.
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
