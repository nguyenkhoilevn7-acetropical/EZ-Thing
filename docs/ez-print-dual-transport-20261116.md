# EZ Print — hai phương án in cho từng doanh nghiệp (staging)

## Phạm vi

Cùng một queue PostgreSQL `print_devices` / `print_jobs`, không tạo đơn hàng
hay sổ thanh toán riêng. Mỗi máy in có `business_id` và `branch_id` cố định;
chỉ owner/manager được cấu hình, xem lịch sử và yêu cầu in lại.

1. **LAN/Wi-Fi / USB → EZ Print Connector** chạy trong mạng nội bộ của quán.
   Không cần mở port router. Kết nối outbound HTTPS dùng Bearer token cho agent.
   TCP port 9100 với máy hỗ trợ ESC/POS LAN; USB yêu cầu PyUSB và USB driver
   thích hợp, nhà sản xuất/model cụ thể phải xác minh trước khi sử dụng.
2. **Star CloudPRNT HTTP**: máy in hỗ trợ tính năng CloudPRNT sẽ POST poll → GET
   `text/plain` → DELETE xác nhận. Server nhận Basic Auth (username là
   device ID, password là khóa một lần), không cần máy tính trung gian.

CloudPRNT *không* đồng nghĩa mọi máy Wi-Fi là in cloud. Epson ePOS XML, Star
StarPRNT binary và những dòng máy ESC/POS không hỗ trợ CloudPRNT đều phải
dùng driver/giao thức tương ứng. Adapter CloudPRNT ban đầu phục vụ
`text/plain` UTF-8 để tương thích dòng Star hỗ trợ. Chưa có bảo đảm
hiển thị đầy đủ dấu tiếng Việt/độ rộng trên mọi model máy.

## Luồng nghiệp vụ

- `POST /api/businesses/{bid}/kds/fire`: giữ snapshot món + topping + trạm
  chế biến của KDS, tạo một lệnh cho từng máy **bật auto_print** cùng chi nhánh,
  station = `bar/hot/cold/expo` hoặc `all`. Lặp lại `fire` không tạo in trùng.
- `POST /api/businesses/{bid}/orders/{oid}/paid`: khi lần đầu chuyển đơn
  `open → paid`, tạo phiếu cho máy station = `receipt`, in tổng tiền do
  backend tính. Đánh dấu lại `paid` không tạo bản sao.
- Phiếu được lưu trong cùng SQL transaction với nghiệp vụ để không mất lệnh
  sau khi cập nhật đơn và không gửi phiếu cho một đơn bị rollback.
- Khi máy offline, lệnh `queued` được giữ trong PostgreSQL. Khi đã chuyển
  `offered`, hệ thống **không tự retry**: trường hợp mất ACK không thể biết
  giấy đã in hay chưa; owner/manager cần kiểm tra và chọn **In lại thủ công**.
- `printed` nghĩa là máy/connector báo thành công nhận dữ liệu, **không**
  phải bằng chứng giấy thực sự đã xuất ra. `failed` giữ thông báo lỗi và
  cần thao tác retry có audit.

## Giao diện

Merchant back-office → **Thêm & cài đặt → Thiết bị & máy in**.
Chọn chi nhánh → loại kết nối → khu vực in → bật/tắt auto_print → Thêm máy.
Chỉ lần đăng ký/đổi khóa mới trả về khóa đầy đủ. Danh sách, log và lịch sử
không xuất token.

### Kết nối LAN/Wi-Fi

Mỗi cửa hàng cần một Windows/Linux/macOS PC hoặc mini-PC đang chạy:

```bash
# Token lưu trong environment, không ghi vào repo hoặc lệnh gửi đi công khai
export EZ_PRINT_TOKEN='<token-chỉ-hiển-thị-một-lần>'
python3 scripts/ez_print_connector.py \
  --server https://ez-thing-staging.onrender.com \
  --device-id '<id-của-máy-trong-EZ-Thing>' \
  --mode lan --host 192.168.1.200 --port 9100
```

`--host` là IP nội bộ **máy in**, không phải máy chủ Render. Agent là
thành phần tùy chọn, chạy độc lập trên thiết bị cửa hàng; Render không thể
truy cập trực tiếp các IP `192.168.*` ở quán.

### Kết nối USB

```bash
pip install pyusb
export EZ_PRINT_TOKEN='<token>'
python3 scripts/ez_print_connector.py \
  --server https://ez-thing-staging.onrender.com \
  --device-id '<id>' --mode usb \
  --usb-vendor 0xVVVV --usb-product 0xPPPP
```

Lấy VID/PID và kiểm tra USB permission/driver theo model máy thực tế.
Chưa kiểm thử USB với thiết bị thật. Với các máy chỉ có driver hệ điều hành
mà không có endpoint tương thích, cần adapter khác.

### Kết nối Star CloudPRNT

Nhập vào cấu hình của máy in hỗ trợ CloudPRNT:

- Server URL: `https://<EZ-host>/api/print/cloudprnt/<device_id>`
- HTTP Basic username: `<device_id>`
- HTTP Basic password: `<device_token_once>`
- Bật TLS và chọn polling interval phù hợp.

Sử dụng **CloudPRNT HTTP**, không phải MQTT; chỉ thông báo `text/plain`.
Không sử dụng `application/octet-stream` để gửi lệnh ESC/POS thẳng tới Star
vì máy có thể dùng emulation không tương thích. Khi có model máy thật,
nâng cấp adapter riêng để in tiếng Việt có dấu bằng raster/bitmap nếu cần.

## API

| Chức năng | Endpoint |
| --- | --- |
| Danh sách/Thêm máy | `GET/POST /api/businesses/{bid}/printers` |
| Đổi cấu hình | `PUT /api/businesses/{bid}/printers/{id}` |
| Đổi khóa / in thử | `POST .../{id}/rotate-key`, `POST .../{id}/test` |
| Lịch sử | `GET /api/businesses/{bid}/printers/jobs` |
| In lại có audit | `POST /api/businesses/{bid}/printers/jobs/{job_id}/retry` |
| Connector pull | `GET /api/print/connector/{device_id}/next` |
| Connector ACK | `POST /api/print/connector/{device_id}/ack` |
| CloudPRNT | `POST/GET/DELETE /api/print/cloudprnt/{device_id}` |

**Thiết kế bảo mật:** Token ngẫu nhiên chỉ trả về một lần, phía server lưu
SHA-256; tenant RBAC + CSRF cho API merchant; riêng API device bắt buộc
Bearer hoặc Basic và HTTPS; không log hoặc lưu token trong trình duyệt.
Khi thu hồi máy, tắt `enabled` hoặc đổi token.

## Database, kiểm thử và triển khai

1. Chạy migration Alembic `20261116_08_printing.py` trước khi đưa vào production.
   `create_all` chỉ phục vụ pilot/staging hiện tại.
2. `pytest -q tests/test_printing.py` để test giả lập LAN, USB, CloudPRNT,
   phân quyền doanh nghiệp, đồng bộ phiếu bếp và thanh toán.
3. `python3 -m py_compile app/printing.py scripts/ez_print_connector.py` và
   `node --check app/static/merchant-print.js`.
4. Kết nối máy thật và test lần lượt: in thử, mất kết nối, thiếu giấy,
   trùng yêu cầu, hai chi nhánh, đổi token, mở lại quán.
5. Trước khi thương mại hóa: thực hiện queue concurrency/stress test trên
   PostgreSQL, kiểm thử model máy, quyền nhân viên và chế độ in offline.

**Chưa bao gồm:** hóa đơn điện tử thuế, tài liệu SDK Epson ePOS,
máy in laser/A4, tự nhận diện máy qua LAN, hỗ trợ toàn bộ firmware
CloudPRNT hoặc bảo đảm in Unicode/QR code trên mọi thiết bị.

## Nguồn giao thức chính thức

- Star CloudPRNT HTTP (POST/GET/DELETE): https://star-m.jp/products/s_print/sdk/StarCloudPRNT/manual/en/protocol-guide.html
- Star media types: https://star-m.jp/products/s_print/sdk/StarCloudPRNT/manual/en/protocol-reference/common-spec-reference/content-mediatypes/index.html
- Star status confirmation: https://star-m.jp/products/s_print/sdk/StarCloudPRNT/manual/en/protocol-reference/http-method-reference/job-confirmation-delete/index.html
