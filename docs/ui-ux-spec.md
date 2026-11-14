# EZ Thing — App-like UI/UX specification

- **Nguyên tắc:** 1 màn hình = 1 mục tiêu chính, các hành động phụ ẩn sau nút phụ.
- **Khách mới:** Đăng ký → chọn ngành + tên doanh nghiệp → trả lời nhu cầu → chọn gói → cấu hình module đã có. Cho xem khuyến nghị và giá trước khi tạo.
- **Chủ cửa hàng:** Dashboard có doanh thu thực thu, số đơn chưa xử lý, sản phẩm, tồn kho cần kiểm tra; nút tạo đơn nằm ngay đầu trang.
- **POS:** Ở MVP, tối thiểu 1–2 thao tác để mở form đặt hàng; chọn món, số lượng, khách, bàn, ghi chú. Không chấp nhận sửa giá thành tiền từ trình duyệt.
- **Điện thoại:** thanh điều hướng dưới cùng với 5 mục chính; menu Thêm dẫn đến khách hàng và phân tích. Bấm vùng ngoài hoặc Escape sẽ đóng popup.
- **Desktop:** sidebar cố định và vùng nội dung tối đa 1480px, không cuộn ngang toàn trang; bảng dữ liệu có khung cuộn ngang riêng khi cần.
- **Form:** có label đầy đủ; ràng buộc số lượng/tiền; thông báo lỗi cụ thể; chống bấm gửi lặp; không hiển thị thành công khi API thất bại.
- **Popup:** modal bo góc 24px, animation ~250ms, phông nền blur 7px; trên mobile chuyển thành bottom sheet; tuân thủ `prefers-reduced-motion`.
- **Phân quyền:** menu được lọc theo active_modules cho trải nghiệm, nhưng API là nguồn chân lý về quyền.
- **Offline:** chỉ hiển thị giao diện shell đã cache; không được tạo đơn offline hoặc giả lập thành công.
- **Thiết kế:** nền xám/xanh nhạt #f6f8f7, thẻ trắng, accent xanh ngọc #0d936b, typography DM Sans / Manrope + hệ thống dự phòng, khoảng trắng thoáng, icon SVG nhất quán.
- **Chưa nghiệm thu:** thử trên Samsung fold/mobile, iPhone, iPad, máy in bếp, máy POS cảm ứng, bàn phím screen reader và kết nối kém.
