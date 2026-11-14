"""Request-scoped localization of EZ Thing API labels and error responses.

Business names, customer records, SKUs, order totals, status enums, and ledger
data are deliberately never translated or rewritten.
"""
from __future__ import annotations

from fastapi import Request

LANGUAGES = ("vi", "en")
INDUSTRIES_EN = {
    "fnb": "Restaurant / Cafe",
    "retail": "Retail",
    "online": "Online selling",
    "services": "Services",
}
RECOMMENDATION_EN = (
    "Recommended from your selected management needs. "
    "This uses existing supported modules; no new software is generated."
)

ERROR_EN = {
    "Vui lòng đăng nhập": "Please sign in",
    "Phiên đăng nhập không hợp lệ": "Invalid sign-in session",
    "Phiên đăng nhập đã hết hạn": "Your session has expired",
    "Thiếu mã xác thực thao tác": "Missing request verification token",
    "Tài khoản không hợp lệ": "Invalid account",
    "Tài khoản đã bị tạm khóa": "This account has been suspended",
    "Tài khoản không bị khóa": "This account is not suspended",
    "Không tìm thấy doanh nghiệp": "Business not found",
    "Doanh nghiệp không tồn tại": "Business not found",
    "Doanh nghiệp đang bị tạm khóa": "This business has been suspended",
    "Doanh nghiệp đã bị tạm khóa": "This business is already suspended",
    "Doanh nghiệp không bị khóa": "This business is not suspended",
    "Chức năng không có trong gói đang kích hoạt": "Feature is unavailable on the current plan",
    "Quá nhiều phiên demo được tạo. Vui lòng thử lại sau.": "Too many demo sessions. Please try again later.",
    "Không có chế độ demo": "Demo mode is not available",
    "Email đã được sử dụng": "Email address is already in use",
    "Email hoặc mật khẩu không chính xác": "Invalid email or password",
    "Đã đạt số chi nhánh của gói": "The plan's branch limit has been reached",
    "Tên chi nhánh đã tồn tại": "Branch name already exists",
    "Mã SKU đã tồn tại trong doanh nghiệp": "This product SKU already exists",
    "Không tìm thấy sản phẩm theo dõi kho": "Tracked product not found",
    "Số lượng tồn kho không đủ": "Insufficient inventory",
    "Tên bàn đã tồn tại trong chi nhánh": "Table name already exists in this branch",
    "Không tìm thấy chi nhánh": "Branch not found",
    "Mã yêu cầu đã dùng cho giỏ hàng khác": "Request ID has been used for a different cart",
    "Không tìm thấy khách hàng": "Customer not found",
    "Bàn không thuộc chi nhánh": "Table does not belong to this branch",
    "Sản phẩm không tồn tại hoặc đã ngừng bán": "Product does not exist or is inactive",
    "Giá trị đơn vượt giới hạn": "Order exceeds the allowed limit",
    "Đơn bị trùng hoặc xung đột dữ liệu": "Duplicate order or data conflict",
    "Không tìm thấy đơn": "Order not found",
    "Nhật ký quản trị chỉ dành cho Pro": "Audit history is available on the Pro plan only",
    "Bản xem trước chỉ có ở staging DEMO": "Preview is available only on DEMO staging",
    "Không có gian hàng này": "Storefront not found",
    "Không tìm thấy gian hàng DEMO": "Demo storefront not found",
    "Dùng trang đặt lịch cho dịch vụ": "Use the booking page for services",
    "Mã yêu cầu đã được dùng với nội dung khác": "Request ID was already used with different content",
    "Phiên demo đã đạt giới hạn đơn hàng": "Demo order limit reached",
    "Cần số điện thoại và địa chỉ nhận hàng khi giao tận nơi": "Phone number and delivery address are required",
    "Vui lòng chọn bàn trước khi gọi món": "Please select a table before ordering",
    "Không có chi nhánh DEMO": "Demo branch not found",
    "Bàn không thuộc quán này": "Table does not belong to this cafe",
    "Tối đa 30 sản phẩm mỗi đơn DEMO": "Maximum 30 items per demo order",
    "Sản phẩm không có trong gian hàng này": "Product does not belong to this storefront",
    "Đơn thử nghiệm vượt giới hạn": "Demo order exceeds the allowed limit",
    "Đơn đã được xử lý, vui lòng kiểm tra trước khi gửi lại": "Order was already processed. Please verify before retrying.",
    "Không hỗ trợ": "Not supported",
    "Chuyên viên DEMO không hợp lệ": "Invalid demo specialist",
    "Dịch vụ không tồn tại": "Service not found",
    "Chỉ được đặt lịch trong 21 ngày tới": "Bookings are available only within the next 21 days",
    "Chuyên viên không tồn tại": "Specialist not found",
    "Ngày giờ cần múi giờ": "Appointment timestamp must include a timezone",
    "Mã đặt lịch đã dùng": "Booking ID has already been used",
    "Phiên DEMO đã đạt giới hạn lịch hẹn": "Demo booking limit reached",
    "Vui lòng chọn khung giờ có sẵn": "Please select an available time slot",
    "Khung giờ này đã được đặt, chọn giờ khác": "This time slot is booked. Please choose another.",
    "Lịch hẹn đã được tạo": "Appointment has already been created",
    "Không có quyền quản trị nền tảng": "You do not have platform administrator access",
    "Quản trị chưa được cấu hình xác thực tăng cường": "Additional admin verification is not configured",
    "Cần mở khóa phiên quản trị trước khi thực hiện thao tác": "Unlock the admin session before making changes",
    "Không có DEMO quản trị": "Admin demo is unavailable",
    "Đã vượt số lần thử. Vui lòng thử lại sau": "Too many attempts. Please try again later.",
    "Mã mở khóa không chính xác": "Invalid admin unlock code",
    "Ngành không hợp lệ": "Invalid industry",
    "Gói không hợp lệ": "Invalid plan",
    "Doanh nghiệp đang sử dụng gói này": "Business is already using this plan",
    "Gói đích không đủ số chi nhánh hiện tại; không tự xóa chi nhánh": "Target plan does not support the current branch count; no branches were deleted",
    "Tên xác nhận không khớp doanh nghiệp": "Confirmation name does not match the business",
    "Tài khoản không tồn tại": "Account not found",
    "Không thể khóa tài khoản quản trị nền tảng": "Cannot suspend a platform administrator account",
    "Email xác nhận không khớp": "Confirmation email does not match",
    "Không có quy trình này trong ngành kinh doanh": "This workflow is not supported for the industry",
    "Dùng chức năng nhập/xuất kho có sẵn": "Use the available stock adjustment workflow",
    "Vui lòng chọn đơn hàng": "Please select an order",
    "Không tìm thấy đơn hàng": "Order not found",
    "Đơn giao hàng cần có khách hàng và địa chỉ nhận hàng": "Delivery orders require a customer and delivery address",
    "Cần chọn khách, dịch vụ, nhân viên và thời gian": "Select customer, service, staff member and time",
    "Khách hàng hoặc dịch vụ không thuộc doanh nghiệp": "Customer or service does not belong to this business",
    "Dịch vụ đặt lịch phải tắt theo dõi tồn kho": "Appointment services must not track inventory",
    "Không thể đặt lịch trong quá khứ": "Cannot book an appointment in the past",
    "Nhân viên đã có lịch trùng giờ": "The staff member has an overlapping appointment",
    "Mục này đã được tạo hoặc dữ liệu đã thay đổi": "This item already exists or its data has changed",
    "Không thể sửa lịch sử kho": "Stock ledger history cannot be edited",
    "Không tìm thấy công việc": "Work item not found",
    "Trình tự trạng thái không hợp lệ": "Invalid status transition",
}


def selected_language(request: Request) -> str:
    """Explicit Accept-Language overrides the saved first-party cookie."""
    header = request.headers.get("accept-language", "").strip()
    if header:
        primary = header.split(",", 1)[0].split(";", 1)[0].lower().strip()
        if primary == "en" or primary.startswith("en-"):
            return "en"
        if primary == "vi" or primary.startswith("vi-"):
            return "vi"
    cookie = request.cookies.get("ez_lang", "vi").lower()
    return cookie if cookie in LANGUAGES else "vi"


def translate_error(detail, language: str):
    """Only human-readable error messages are localized; identifiers are untouched."""
    if language != "en" or not isinstance(detail, str):
        return detail
    value = ERROR_EN.get(detail)
    if value:
        return value
    prefix = "Không đủ tồn kho: "
    if detail.startswith(prefix):
        return "Insufficient stock: " + detail[len(prefix):]
    return detail
