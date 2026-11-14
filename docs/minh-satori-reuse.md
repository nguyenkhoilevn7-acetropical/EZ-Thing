# Đối chiếu chức năng Minh Satori → EZ Thing Business OS

Ngày rà soát: 14/11/2026. Repo đọc tham khảo: [nguyenkhoilevn7-acetropical/Minhsatori](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori). **Không có thao tác ghi nào vào repo, DB hoặc dịch vụ production Minh Satori.**

| Chức năng trong Minh Satori | Nguồn tham khảo | Ngành sử dụng | Trạng thái trong EZ Thing v0.1 |
| --- | --- | --- | --- |
| Tạo đơn có `requestId` chống trùng | [`api/BotApi.gs`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/api/BotApi.gs) | F&B, Retail, Wholesale, Online | **Đã viết** key idempotency + payload fingerprint; API test |
| Tính tiền theo dòng, server kiểm tra giá | [`api/AI_REAL_INVOICE_CUTOVER_20261022.md`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/api/AI_REAL_INVOICE_CUTOVER_20261022.md) | F&B, Retail, Online | **Đã viết** server tính tổng giá; VAT/discount/ship chưa tích hợp |
| Quản lý khách hàng; tránh trùng hồ sơ mơ hồ | [`api/README.md`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/api/README.md) | Mọi ngành | **Đã viết** customer ID chính xác; chưa có merge hồ sơ |
| Công nợ chưa thanh toán, loại bỏ tính trùng | [`customer-debt.js`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/customer-debt.js), [`accounting-core.js`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/accounting-core.js) | Retail, Wholesale, Online, F&B | **Đã viết bản cơ bản** tổng đơn chưa trả theo customer ID, chưa hỗ trợ thanh toán một phần |
| Hóa đơn PDF, chia sẻ Zalo/Messenger | [`android/README.md`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/android/README.md) | Mọi ngành | **Chưa**. Chỉ cân nhắc phiếu bán hàng; hóa đơn thuế cần nhà cung cấp hợp lệ |
| Excel đối chiếu công nợ, nhập dữ liệu | [`customer-debt.js`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/customer-debt.js), [`accounting-workbook.js`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/accounting-workbook.js) | Retail, Wholesale, Online | **Chưa**. Dự kiến import-preview-approve để tránh ghi nhầm |
| VAT tùy chọn từng dòng | [PR #407](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/pull/407) | Retail/Wholesale và một số dịch vụ | **Chưa**. Tách tax engine để chọn chế độ đúng quy định |
| Phân quyền chủ sở hữu/nhân viên, HMAC | [`api/README.md`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/api/README.md) | Mọi ngành | **Đã có** tenant membership chủ sở hữu, CSRF và kiểm tra gói; **chưa** RBAC đầy đủ |
| Backup, revision, soft delete và phục hồi | [`api/README.md`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/api/README.md) | Mọi ngành | **Đã có** transaction DB và audit; **chưa** backup/restore, soft delete |
| Outbox trên Android chống mất response ghi | [`android/README.md`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/android/README.md) | Mọi ngành | **Đã có** server idempotency, **chưa** durable client outbox/offline sync |
| Cặp bill cộng tác viên, thanh toán chéo | [`api/COLLABORATOR_TWIN_INVOICE_ROLLOUT.md`](https://github.com/nguyenkhoilevn7-acetropical/Minhsatori/blob/main/api/COLLABORATOR_TWIN_INVOICE_ROLLOUT.md) | Wholesale/CTV/Agency | **Chưa**, không áp dụng máy móc vào F&B hay shop thường |

## Quy tắc giữ lại

1. Tất cả giá tiền và quyền ghi được xác thực tại server, client không được tự gửi tổng tiền hợp lệ.
2. Mỗi đơn có mã yêu cầu bất biến, retry giống hệt không tạo đơn trùng; thay đổi giỏ hàng với cùng mã phải bị từ chối.
3. Tất cả truy vấn dữ liệu của doanh nghiệp phải kiểm tra membership và `business_id`.
4. Không lấy VAT/chiết khấu riêng từ Minh Satori áp dụng cho khách khác.
5. AI không có quyền tự thay đổi đơn đã thanh toán, công nợ, hoàn tiền, hay xác nhận chuyển khoản.
6. Không dùng chung cơ sở dữ liệu, bí mật HMAC, OAuth, catalog khách hàng, ledger hoặc thông tin hóa đơn.
7. Không khẳng định code Minh Satori mới nhất đã phát hành production; trong tài liệu repo có nhiều tính năng được ghi **source only / chưa kích hoạt**.
