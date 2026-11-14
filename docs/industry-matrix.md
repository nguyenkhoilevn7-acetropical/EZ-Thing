# EZ Thing — Ma trận nghiệp vụ, phạm vi & nghiệm thu

Ngày 14/11/2026. Tên EZ Thing là mã dự án tạm. Không dùng dữ liệu thật.

## Đối chiếu phần mềm thương mại

| Ngành | Quy trình cần có | Tham chiếu | Đã có trong MVP v0.2 | Còn phải hoàn thiện |
|---|---|---|---|---|
| F&B / Café | Quầy bán → Bếp/Bar → Sẵn sàng → Phục vụ → Thu tiền | Sapo FnB | Tạo đơn, chọn bàn, phiếu bếp & trạng thái thủ công | Gọi món QR, quản lý ca, sửa/tách/gộp/chuyển bàn, in tem bếp, công thức nguyên liệu, hoàn tiền |
| Bán lẻ | Nhập hàng → Kho → Bán → Kiểm kho → Đổi trả | KiotViet | Tồn kho, ghi nhận nhập/xuất/điều chỉnh, lịch sử theo sản phẩm | Đơn mua nhà cung cấp, kiểm kho bằng số thực tế, mã vạch, đổi trả, hàng nhiều biến thể |
| Online shop | Nhận đơn → Đóng gói → Giao hàng → Giao thành công | Shopify | Đơn có khách/địa chỉ, phiếu giao, trạng thái xử lý nội bộ | Đồng bộ Shopee/TikTok/website, hãng vận chuyển, COD, vận đơn thực, trả/hoàn hàng |
| Dịch vụ / Spa | Chọn dịch vụ → Lịch hẹn → Nhân viên → Xác nhận → Hoàn tất | Fresha | Lịch nhân viên có phát hiện trùng giờ, trạng thái hẹn, hủy lịch | Lịch nhiều nhân viên/ngày, phòng/thiết bị, lịch tái hẹn, liệu trình, đặt cọc, nhắc hẹn |

## Nguyên tắc vận hành

1. Một mã nguồn chung, mỗi doanh nghiệp có business_id riêng và chỉ truy cập module đúng ngành.
2. Không đổi module tùy tiện bằng AI; onboarding chọn thư viện đã kiểm thử.
3. Sổ kho không cho chỉnh sửa trực tiếp; thay đổi qua phiếu điều chỉnh có audit.
4. Bếp/giao vận có trạng thái tuần tự, không được nhảy bước hoặc giả xác nhận hãng vận chuyển.
5. Dịch vụ tách khỏi sản phẩm tồn kho; lịch cùng nhân viên cùng thời điểm bị từ chối (PostgreSQL advisory lock để tránh ghi trùng đồng thời).
6. Hóa đơn/VAT/nhà vận chuyển/booking online chỉ được coi là tích hợp khi có kết nối thật và E2E pass.
7. Demo dữ liệu độc lập; không kết nối ledger Minh Satori hay các dự án khác.
8. Mô hình permission hiện là pilot; cần phân vai nhân viên, migrations, backup, rate limit, billing, stress tests trước production.

## Giai đoạn kế tiếp theo mức độ ưu tiên

1. F&B: order editor, chuyển bàn, bếp nhiều trạm và công thức định lượng.
2. Retail: PO nhập hàng, kiểm kho, trả hàng, barcode.
3. Online: vận đơn, COD, trả/hoàn, đồng bộ đa kênh.
4. Services: calendar tuần/ngày, nhân sự, thời gian nghỉ, phòng dịch vụ, đặt cọc.
5. Chung: quản lý nhân viên & role-based permissions, export, audit, backup, migrations, accessibility, performance và offline-read-only.

## Nguồn nghiệp vụ

- Sapo FnB: https://help.sapo.vn/tong-quan-cac-tinh-nang-tren-ung-dung-sapo-fnb-nha-hang-va-dich-vu
- KiotViet: https://www.kiotviet.vn/phi-dich-vu
- Shopify: https://help.shopify.com/en/manual/fulfillment/features-overview
- Fresha: https://www.fresha.com/for-business/features