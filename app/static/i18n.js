/* EZ Thing centralized client i18n (VI/EN).
 * Translates UI text/attributes only; never sends content to external translation APIs.
 * Dynamic templates are translated via MutationObserver without modifying business data.
 */
(() => {
'use strict';
const entries = [
['Giải pháp','Solutions'],['Cách hoạt động','How it works'],['Bảng giá','Pricing'],['Quản lý cửa hàng','Merchant app'],['Khám phá demo','Explore demo'],
['EZ THING • TRẢI NGHIỆM KINH DOANH MỚI','EZ THING • A NEW WAY TO DO BUSINESS'],['Kinh doanh.','Business.'],['Thật đơn giản.','Made simple.'],
['Bán hàng, nhận đơn và đặt lịch trong một trải nghiệm liền mạch. Mỗi ngành có công cụ riêng, nhưng đều trực quan và dễ sử dụng.','Sell, receive orders and take bookings in one seamless experience. Each industry gets the right tools, all intuitive and easy to use.'],
['Khám phá trải nghiệm','Explore experiences'],['Bản quản lý demo','Merchant demo'],['4 mô hình kinh doanh','4 business types'],
['Giao diện và quy trình riêng cho từng ngành','Dedicated experiences and workflows for every industry'],
['CHỌN ĐÚNG CÔNG CỤ','THE RIGHT TOOLS'],['01 / GIẢI PHÁP','01 / SOLUTIONS'],['02 / CÁCH HOẠT ĐỘNG','02 / HOW IT WORKS'],['03 / GÓI DỊCH VỤ','03 / PLANS'],
['Mỗi ngành một cách vận hành.','Every business works differently.'],['Mọi thứ đều đơn giản.','Everything stays simple.'],
['Khách hàng mua sắm và đặt lịch trong giao diện riêng. Chủ cửa hàng sử dụng một không gian quản trị độc lập.','Customers shop and book through their own storefront. Business owners use a separate management workspace.'],
['01 / NHÀ HÀNG & CAFE','01 / RESTAURANTS & CAFES'],['02 / CỬA HÀNG BÁN LẺ','02 / RETAIL STORES'],['03 / BÁN HÀNG ONLINE','03 / ONLINE SELLING'],['04 / SPA & DỊCH VỤ','04 / SPA & SERVICES'],
['Menu gọi món','Ordering menu'],['Gian hàng bán lẻ','Retail storefront'],['Online Store','Online Store'],['Đặt lịch dịch vụ','Service booking'],
['Thực đơn, chọn bàn, giỏ hàng và gửi món xuống bếp.','Explore the menu, choose a table, add to cart and send orders to the kitchen.'],
['Chọn sản phẩm, giữ hàng và gửi yêu cầu cho cửa hàng.','Browse products, reserve items and send a request to the store.'],
['Danh mục sản phẩm, giỏ hàng, tạo đơn và theo dõi trạng thái.','Product catalog, shopping cart, checkout and order status.'],
['Chọn liệu trình, chuyên viên và khung giờ có sẵn.','Choose a treatment, specialist and available appointment time.'],
['Xem menu khách hàng','View customer menu'],['Xem cửa hàng mẫu','View retail demo'],['Khám phá online shop','Explore online shop'],['Xem trang đặt lịch','View booking page'],
['Các trải nghiệm trên sử dụng dữ liệu DEMO tách biệt, chưa nhận thanh toán hay đơn hàng thật.','These experiences use isolated DEMO data and do not accept real orders or payments.'],
['BẮT ĐẦU TRONG VÀI BƯỚC','GET STARTED IN A FEW STEPS'],['Từ ý tưởng đến vận hành.','From idea to operations.'],
['Không cần học phần mềm phức tạp.','No complicated software to learn.'],['BƯỚC 01','STEP 01'],['BƯỚC 02','STEP 02'],['BƯỚC 03','STEP 03'],
['Chọn ngành kinh doanh','Choose your business type'],['Thiết lập trong vài phút','Set up in minutes'],['Bắt đầu trải nghiệm','Start exploring'],
['Nhà hàng, cửa hàng, online hoặc dịch vụ. Hệ thống chỉ gợi ý các module đã được xây dựng và kiểm thử.','Restaurant, retail, online shop or services. Only existing, tested modules are recommended.'],
['Thêm sản phẩm, dịch vụ và những thông tin cần thiết. Những phần không liên quan được ẩn đi.','Add products, services and essential information. Irrelevant options stay out of the way.'],
['Chủ doanh nghiệp quản lý trong /app. Khách hàng sử dụng giao diện mua hàng hoặc đặt lịch riêng.','Business owners use /app. Customers use a dedicated shopping or booking interface.'],
['DÀNH CHO TỪNG GIAI ĐOẠN','BUILT FOR EVERY STAGE'],['Đủ dùng hôm nay.','Everything you need today.'],['Sẵn sàng phát triển ngày mai.','Ready to grow tomorrow.'],
['Giá bên dưới chỉ là','The prices below are'],['đề xuất','proposals'],['trong quá trình nghiên cứu thị trường, hiện chưa mở thanh toán thuê bao.','for market research; subscriptions are not yet enabled.'],
['Bắt đầu gọn nhẹ','Start simply'],['Vận hành hiệu quả','Run efficiently'],['Phát triển nhiều điểm bán','Grow across locations'],
['Danh mục, đơn hàng và các công cụ quản lý căn bản.','Catalog, orders and essential management tools.'],
['Thêm báo cáo hoạt động và kiểm soát tồn kho tốt hơn.','Add business reporting and better stock control.'],
['Thêm nhiều chi nhánh và nhật ký vận hành.','Manage multiple branches and operational activity logs.'],
['Trải nghiệm demo','Try the demo'],['/ tháng*','/ month*'],
['* Giá nghiên cứu, không phải giá bán chính thức. Bản pilot chưa có thanh toán gói.','* Research pricing, not official rates. Subscriptions are not billed during the pilot.'],
['Bớt việc quản lý.','Less time managing.'],['Thêm thời gian phát triển.','More time growing.'],['Mở không gian trải nghiệm','Open demo workspace'],
['Sản phẩm đang trong giai đoạn thử nghiệm.','Product currently in pilot testing.'],
['01 nơi quản lý','One workspace'],['Tất cả hoạt động','All operations'],['Mượt mà, dễ dùng','Smooth and intuitive'],
['EZ Thing / Cửa hàng của bạn','EZ Thing / Your storefront'],['KHÁM PHÁ HÔM NAY','DISCOVER TODAY'],
['Một chút tuyệt vời.','A little wonderful.'],['Trong từng lựa chọn.','In every choice.'],
['Trải nghiệm đặt món thật đơn giản, từ đầu đến cuối.','A simple ordering journey, from start to finish.'],['Xem thực đơn','View menu'],
['Hôm nay uống gì?','What will you drink today?'],['Tìm món yêu thích...','Find your favorite drink...'],['MENU HÔM NAY','TODAY’S MENU'],
['Thưởng thức','Enjoy'],['một chút','something'],['tươi mới.','fresh.'],['Khám phá món ngon','Explore the menu'],
['TRẢI NGHIỆM DEMO • KHÔNG THANH TOÁN HOẶC GIAO HÀNG THẬT','DEMO EXPERIENCE • NO REAL PAYMENTS OR DELIVERY'],
['Trang chủ','Home'],['Thực đơn','Menu'],['Đặt hàng','Order'],['Ưu đãi','Offers'],['Về chúng tôi','About us'],['Về EZ Thing','About EZ Thing'],['Hỗ trợ','Support'],
['Danh mục','Categories'],['Khuyến mãi','Promotions'],['Cửa hàng','Store'],['Sản phẩm','Products'],['Dịch vụ','Services'],['Đặt lịch','Book now'],
['Cà phê ngon hơn,','Better coffee,'],['cuộc sống nhẹ hơn.','a lighter day.'],
['Mua sắm dễ dàng','Shopping made easy'],['cho cuộc sống hiện đại.','for modern living.'],
['Thư giãn trọn vẹn,','Relax completely,'],['tái tạo năng lượng.','restore your energy.'],
['Cà phê đặc sắc, đồ uống sáng tạo và những phút giây thư giãn mỗi ngày. Chọn món nhanh, dễ dàng trong vài chạm.','Exceptional coffee, creative drinks and a moment of calm every day. Order in just a few taps.'],
['Hàng chọn lọc mỗi ngày, từ những món đồ thiết yếu đến phụ kiện phong cách — tất cả trong một nơi.','Curated everyday essentials and stylish accessories, all in one place.'],
['Mua sắm thông minh, trải nghiệm đơn giản. Đồ bạn cần — tất cả ở một nơi.','Smart shopping, a simple experience. Everything you need, all in one place.'],
['Không gian chăm sóc sức khỏe và sắc đẹp hiện đại, giúp bạn cân bằng thân – tâm – trí.','A modern wellness sanctuary to restore balance to your body and mind.'],
['Mua sắm ngay','Shop now'],['Đặt ngay','Order now'],['Đặt lịch ngay','Book now'],['Khám phá danh mục','Explore categories'],['Khám phá dịch vụ','Explore services'],
['Đồ uống chất lượng','Quality drinks'],['Cà phê chọn lọc, hương vị tinh tế','Carefully selected coffee, refined flavor'],
['Nguyên liệu tươi mới','Fresh ingredients'],['Thực đơn được cập nhật dễ dàng','A menu that stays fresh'],
['Đặt hàng nhanh','Easy ordering'],['Chỉ vài thao tác chọn món','Order in a few taps'],
['Trải nghiệm thân thiện','Friendly experience'],['Giao diện dễ dùng trên điện thoại','Easy to use on mobile'],
['Chọn hàng dễ dàng','Easy product selection'],['Xem nhanh danh sách sản phẩm','Browse products at a glance'],
['Mua sắm tiện lợi','Convenient shopping'],['Mọi thứ trong một nơi','Everything in one place'],
['Thông tin rõ ràng','Clear information'],['Giá được xác nhận từ hệ thống','Prices verified by the system'],
['Duyệt sản phẩm dễ dàng','Browse with ease'],['Tìm món bạn yêu thích','Find your favorites'],
['Thông tin giao hàng','Delivery information'],['Nhập địa chỉ khi tạo đơn DEMO','Enter your address for demo checkout'],
['Đặt hàng dễ dàng','Easy checkout'],['Giỏ hàng trong vài chạm','Your cart in a few taps'],
['Minh bạch giá bán','Transparent pricing'],['Tổng tiền do backend xác nhận','Total verified by the server'],
['Trợ giúp trải nghiệm','Help with your demo'],['Không cần tải thêm ứng dụng','No extra app required'],
['Đặt lịch dễ dàng','Easy booking'],['Chọn dịch vụ và thời gian phù hợp','Choose a service and time'],
['Không gian thư giãn','Relaxing atmosphere'],['Giao diện tinh tế, nhẹ nhàng','A calm, elegant experience'],
['Chăm sóc toàn diện','Complete care'],['Duyệt liệu trình theo nhu cầu','Browse treatments for your needs'],
['Lịch chuyên viên','Specialist schedules'],['Giờ trống được kiểm tra ở backend','Availability checked by the server'],
['DANH MỤC NỔI BẬT','FEATURED CATEGORIES'],['DANH MỤC','CATEGORIES'],['DỊCH VỤ CỦA CHÚNG TÔI','OUR SERVICES'],
['Chọn những gì bạn yêu thích.','Choose what you love.'],['Danh mục nổi bật','Featured categories'],['Dịch vụ nổi bật','Featured services'],
['Khám phá các nhóm hàng minh họa trước khi chọn sản phẩm DEMO.','Explore category inspiration before selecting demo products.'],
['Khám phá ý tưởng mua sắm, sau đó xem những sản phẩm DEMO hiện có.','Browse shopping inspiration, then explore available demo products.'],
['Những trải nghiệm thư giãn để bạn khám phá.','Explore our relaxing experiences.'],
['Thực phẩm tươi ngon','Fresh food'],['Đa dạng lựa chọn cho mỗi ngày.','Everyday essentials and more.'],
['Đồ gia dụng tiện ích','Useful home essentials'],['Gọn gàng hơn, thoải mái hơn.','A more comfortable home.'],
['Điện tử & Phụ kiện','Electronics & accessories'],['Công nghệ thiết thực mỗi ngày.','Practical tech for everyday life.'],
['Điện tử & Công nghệ','Electronics & technology'],['Gia dụng & Đời sống','Home & living'],['Thời trang & Phong cách','Fashion & style'],
['Làm đẹp & Chăm sóc','Beauty & personal care'],['Thể thao & Sức khỏe','Sports & wellness'],
['Thực phẩm','Food'],['Chăm sóc cá nhân','Personal care'],['Đồ gia dụng','Home essentials'],['Thời trang','Fashion'],['Quà tặng','Gifts'],
['Massage trị liệu','Therapeutic massage'],['Giảm căng thẳng, phục hồi cơ thể','Release tension and recover'],
['Chăm sóc da mặt','Facial care'],['Làm sạch, nuôi dưỡng và tái tạo','Cleanse, nourish and refresh'],
['Chăm sóc cơ thể','Body care'],['Thư giãn và phục hồi năng lượng','Unwind and recharge'],
['Trải nghiệm trọn gói','Complete wellness packages'],['Khám phá dịch vụ và đặt lịch','Explore services and book'],
['SẢN PHẨM NỔI BẬT','FEATURED PRODUCT'],['Hiệu năng mạnh mẽ cho công việc và sáng tạo.','Powerful performance for work and creativity.'],
['Khám phá trải nghiệm mua sắm bằng các sản phẩm mẫu đang có trong hệ thống.','Discover the shopping experience using sample products in our demo.'],
['Khám phá ngay','Explore now'],['Khám phá','Explore'],
['Khám phá thực đơn của chúng tôi','Discover our menu'],['Sản phẩm dành cho bạn','Products for you'],['Đặt lịch trải nghiệm','Book an experience'],
['Nổi bật','Featured'],['Cà phê','Coffee'],['Trà & nước ép','Tea & juice'],['Tất cả','All'],
['Đang có hàng','Available'],['Hết hàng','Sold out'],['Có sẵn','In stock'],
['Chưa tìm thấy sản phẩm phù hợp.','No matching products found.'],
['Tìm sản phẩm...','Search products...'],['Tìm món yêu thích...','Search drinks...'],
['Giỏ hàng','Cart'],['Xem giỏ hàng','View cart'],['Thêm vào giỏ hàng','Add to cart'],
['Đã thêm vào giỏ hàng','Added to cart'],['Hãy chọn ít nhất một sản phẩm','Please choose at least one product'],
['Gọi món DEMO','Demo order'],['Giữ hàng DEMO','Demo reservation'],['Đơn hàng DEMO','Demo order'],
['Đặt lịch DEMO','Demo booking'],['Gửi món đến quán','Send order to cafe'],['Gửi yêu cầu giữ hàng','Send reservation request'],
['Gửi đơn đặt hàng','Submit demo order'],['Xác nhận lịch DEMO','Confirm demo booking'],
['Đặt hàng thử nghiệm • Không thu tiền','Demo order • No payments collected'],
['Tạm tính từ máy chủ*','Subtotal confirmed by server*'],['Tên của bạn *','Your name *'],
['Tên khách hàng *','Customer name *'],['Họ và tên','Full name'],['Số điện thoại *','Phone number *'],
['Số điện thoại (tuỳ chọn)','Phone (optional)'],['Bàn đang ngồi *','Your table *'],['Chọn bàn','Choose a table'],
['Địa chỉ nhận hàng *','Delivery address *'],['Số nhà, đường, phường, thành phố','Street, ward, city'],
['Ghi chú (tuỳ chọn)','Notes (optional)'],['Ghi chú','Notes'],['Lưu ý cho cửa hàng','Special instructions'],
['* Tổng tiền cuối cùng được xác nhận tại backend. Không chuyển tiền, không phát sinh giao hàng thực tế.','* The final amount is calculated on the server. No payments or real deliveries.'],
['Đã gửi yêu cầu DEMO!','Demo request submitted!'],['Đã đặt lịch DEMO!','Demo booking confirmed!'],
['Phiếu bếp thử nghiệm đã được tạo. Vui lòng không thanh toán.','Demo kitchen ticket created. Do not make a payment.'],
['Đơn DEMO đã chuyển vào danh sách đóng gói. Không giao hàng thật.','Demo order sent to packing queue. No real delivery.'],
['Cửa hàng đã nhận yêu cầu giữ hàng thử nghiệm.','The store has received your demo reservation.'],
['Lịch thử nghiệm đã được ghi vào quản lý Spa/Wellness. Không phát sinh đặt cọc.','Demo booking saved in Spa/Wellness management. No deposit was charged.'],
['Tiếp tục trải nghiệm','Continue exploring'],['Mã DEMO:','Demo ID:'],
['Anh/chị có thể xem đơn hoặc lịch hẹn trong khu quản lý DEMO.','You can review orders or appointments in the demo workspace.'],
['Mở khu quản lý','Open merchant app'],['Bản xem trước','Preview'],
['Chọn dịch vụ và giờ hẹn • Không yêu cầu thanh toán','Choose a treatment and appointment time • No payment required'],
['Lịch hẹn DEMO','Demo appointments'],['01. Lựa chọn dịch vụ','01. Choose a service'],
['02. Chọn ngày và thời gian','02. Choose date and time'],['Ngày hẹn','Appointment date'],['Chuyên viên','Specialist'],
['Thời lượng minh họa 60 phút','Illustrative duration: 60 minutes'],
['Các chuyên viên và khung giờ chỉ là dữ liệu thử nghiệm. Hệ thống kiểm tra trùng lịch ở backend.','Specialists and time slots are demo data. The server prevents overlapping appointments.'],
['Chọn dịch vụ, ngày và chuyên viên để xem giờ trống.','Select a service, date and specialist to see available times.'],
['Đang kiểm tra lịch trống...','Checking available times...'],
['Tiếp tục đặt lịch','Continue booking'],['Không đặt cọc hoặc thu tiền trong bản DEMO.','No deposits or payments in demo mode.'],
['Xác nhận lịch hẹn','Confirm appointment'],['Yêu cầu thêm','Additional requests'],
['Lịch chỉ ghi vào doanh nghiệp DEMO của phiên hiện tại.','Bookings are saved only to your isolated demo workspace.'],
['Trải nghiệm hiện chưa mở','Experience currently unavailable'],
['Trang xem trước chỉ có ở staging DEMO','Preview available only on DEMO staging'],
['Không thể kết nối với bản DEMO','Unable to connect to the demo'],
['← Về trang chủ','← Back to home'],['Quản lý','Manage'],
['Đây là bản trải nghiệm giao diện. Hiện chưa có chương trình khuyến mãi hay giao dịch thanh toán thực tế. Sản phẩm, giá và lịch hẹn DEMO lấy từ hệ thống thử nghiệm riêng.','This is a UI demo. No active promotions or real payments are available. Products, prices and booking slots come from an isolated demo environment.'],
['Giao diện trải nghiệm được xây dựng bởi','Demo experience powered by'],
['Chỉ sử dụng dữ liệu DEMO','DEMO data only'],['Không xử lý đơn hàng thật.','No real orders are processed.'],
['Khu quản lý cửa hàng','Merchant management'],['Đang mở trải nghiệm...','Opening demo...'],
['Tổng quan','Overview'],['Đơn hàng','Orders'],['Khách hàng','Customers'],['Sơ đồ bàn','Table map'],['Bếp & pha chế','Kitchen & drinks'],
['Sổ kho','Stock ledger'],['Giao hàng','Delivery'],['Lịch hẹn','Appointments'],['Phân tích','Analytics'],['Cài đặt','Settings'],
['Đăng nhập','Sign in'],['Đăng xuất','Sign out'],['Đăng ký','Sign up'],['Email','Email'],['Mật khẩu','Password'],['Xác nhận','Confirm'],
['Tiếp tục','Continue'],['Bắt đầu','Get started'],['Tạo tài khoản','Create account'],['Tạo phiên demo mới','Start a new demo session'],
['Họ và tên','Full name'],['Tên doanh nghiệp','Business name'],['Quay lại','Back'],
['BƯỚC 1 / 3','STEP 1 / 3'],['BƯỚC 2 / 3','STEP 2 / 3'],['BƯỚC 3 / 3','STEP 3 / 3'],
['Doanh nghiệp của bạn kinh doanh gì?','What type of business do you run?'],
['Chọn ngành nghề để chúng tôi thiết lập đúng các tính năng.','Choose your industry so we can set up the right tools.'],
['Bạn cần quản lý những gì?','What do you need to manage?'],['Chỉ chọn những gì cần thiết. Có thể cấu hình lại sau.','Choose only what you need. You can change this later.'],
['Chọn gói phù hợp ✨','Choose a plan ✨'],
['Hệ thống đã đối chiếu nhu cầu với thư viện chức năng có sẵn. Bạn có thể chọn gói khác.','Your needs have been matched with available features. You can choose a different plan.'],
['Thiết lập thông minh','Smart setup'],['Cấu hình dựa trên ngành nghề và gói dịch vụ.','Tailored to your industry and plan.'],
['TỔNG QUAN KINH DOANH','BUSINESS OVERVIEW'],['Tất cả hoạt động.','All your operations.'],['Một nơi quản lý.','One workspace.'],['Đơn giản hơn mỗi ngày.','Simpler every day.'],
['Quản lý dễ dàng.','Management made easy.'],['Kinh doanh hiệu quả hơn.','Grow your business.'],
['Tất cả đơn hàng, sản phẩm và số liệu của bạn ở một nơi.','All your orders, products and metrics in one place.'],
['Đơn hàng gần đây','Recent orders'],['Trạng thái','Status'],['Giá trị','Amount'],['Thời gian','Time'],
['Thao tác nhanh','Quick actions'],['Tạo đơn hàng','Create order'],['Tạo đơn','New order'],['Xem tất cả','View all'],
['QUẢN LÝ','MANAGE'],['Đã nhận tiền','Paid'],['Chờ thanh toán','Awaiting payment'],['Mã đơn','Order ID'],['Mã đơn hàng','Order ID'],
['Sản phẩm bán chạy','Top-selling products'],['Hàng sắp hết','Low stock'],['Đơn chưa thanh toán theo khách hàng','Unpaid orders by customer'],
['Trợ lý phân tích','Business insights'],['Bản nền tảng','Platform edition'],['Chức năng khác','Other features'],
['Gói thuê bao','Subscription'],['GÓI ĐANG THỬ NGHIỆM','PILOT PLAN'],['Không phát sinh thu phí trong bản MVP','No subscription charges during the MVP'],
['Chi nhánh','Branches'],['Chức năng đang bật','Enabled features'],
['Tạo đơn bán hàng','Create sales order'],['Khách lẻ','Walk-in customer'],['Mang đi / giao hàng','Takeaway / delivery'],
['Chi tiết sản phẩm','Order items'],['Tổng tiền hàng','Order total'],['Điều chỉnh kho','Adjust inventory'],['Theo dõi kho','Track inventory'],
['Hủy','Cancel'],['Lưu','Save'],['Xóa','Delete'],['Chỉnh sửa','Edit'],['Thêm','Add'],['Tạo mới','Create new'],
['Làm mới','Refresh'],['Tìm kiếm','Search'],['Tìm doanh nghiệp','Find business'],['Nhà hàng / Cafe','Restaurant / Cafe'],
['Bán lẻ','Retail'],['Bán hàng online','Online selling'],['Dịch vụ / Wellness','Services / Wellness'],['Dịch vụ','Services'],
['Tên sản phẩm','Product name'],['Mã sản phẩm (SKU)','Product SKU'],['Giá bán (đ)','Selling price (VND)'],
['Giá vốn (đ)','Cost (VND)'],['Số lượng tồn ban đầu','Initial stock'],['Theo dõi số lượng tồn','Track stock levels'],
['Tên bàn','Table name'],['Số chỗ ngồi','Seats'],['Tên khách hàng','Customer name'],['Điện thoại (tùy chọn)','Phone (optional)'],
['Địa chỉ (tùy chọn)','Address (optional)'],['Tên chi nhánh','Branch name'],['Lý do điều chỉnh','Adjustment reason'],
['Xác nhận đã nhận tiền','Confirm payment received'],['Xác nhận hủy','Confirm cancellation'],['Hủy lịch','Cancel appointment'],
['Nhân viên phụ trách','Assigned staff'],['Giờ hẹn','Appointment time'],['Thời lượng (phút)','Duration (minutes)'],
['Quản lý đơn hàng','Manage orders'],['Cài đặt không gian','Workspace settings'],['Nhật ký','Audit log'],
['Tổng quan nền tảng','Platform overview'],['Doanh nghiệp','Businesses'],['Tài khoản','Accounts'],['Gói dịch vụ','Plans'],
['Nhật ký quản trị','Admin audit log'],['Hệ thống','System'],['Điều hành nền tảng. Có kiểm soát.','Platform management. With full control.'],
['Đăng nhập Super Admin','Super Admin sign-in'],['Mở khóa phiên quản trị','Unlock admin session'],
['QUẢN TRỊ HỆ THỐNG','SYSTEM ADMINISTRATION'],['EMAIL QUẢN TRỊ','ADMIN EMAIL'],['MẬT KHẨU','PASSWORD'],
['MÃ MỞ KHÓA QUẢN TRỊ','ADMIN UNLOCK CODE'],['Đăng nhập quản trị','Admin sign-in'],
['Tiếp tục đăng nhập','Continue signing in'],['Mở khóa quyền quản trị','Unlock admin access'],
['Tài khoản người dùng','User accounts'],['Tài khoản Super Admin','Super Admin account'],
['Quản lý doanh nghiệp','Manage businesses'],['Người dùng','Users'],['Gói','Plan'],['Ngày tạo','Created'],
['Lọc dữ liệu','Filter results'],['Tất cả ngành','All industries'],['Mọi gói','All plans'],
['Chi tiết','Details'],['Quản trị','Administration'],['Trước','Previous'],['Tiếp','Next'],
['Lý do','Reason'],['Hoạt động','Activity'],['Đối tượng','Target'],['Hoạt động quản trị gần đây','Recent admin activity'],
['Trạng thái hệ thống','System status'],['Chưa sẵn sàng Production','Not production-ready'],['Chưa thu tiền thuê bao','Subscriptions not yet billed'],
['Quản lý doanh nghiệp','Business management'],['Quản lý sản phẩm','Product management'],['Quản lý đơn hàng','Order management'],
['Quản lý bàn','Table management'],['Bếp / pha chế','Kitchen / bar'],['Kho cơ bản','Basic inventory'],
['Nhiều chi nhánh','Multi-branch'],['Báo cáo','Reports'],['Giao vận','Fulfillment'],
['Dữ liệu giả lập — không phản ánh hệ thống thật','Simulated data — not actual system records'],
['Chưa có dữ liệu','No data yet'],['Chưa có bản ghi nào phù hợp với bộ lọc.','No records match your filters.'],
['Không kết nối được máy chủ. Vui lòng thử lại.','Cannot connect to the server. Please try again.'],
['Máy chủ không phản hồi hợp lệ','Invalid server response'],['Thao tác không thành công','Operation failed'],
['Đang tải','Loading'],['Đang tải...','Loading...'],['Đóng','Close'],
['Khách mẫu 01','Demo customer 01'],['Khách mẫu 02','Demo customer 02'],['Khách mẫu 03','Demo customer 03'],
['Matcha Latte','Matcha latte'],['Cà phê sữa','Vietnamese milk coffee'],['Trà đào cam sả','Peach, orange & lemongrass tea'],
['Nước ép cam','Fresh orange juice'],['Trà vải','Lychee tea'],['Bình giữ nhiệt','Insulated bottle'],
['Túi tote','Tote bag'],['Sổ tay','Notebook'],['Áo thun','T-shirt'],['Nón lưỡi trai','Baseball cap'],
['Túi đeo chéo','Crossbody bag'],['Gói xông hơi','Sauna session'],['Massage thư giãn','Relaxation massage'],
['Gói chăm sóc da','Skincare package'],['Đồ uống','Beverages'],['Online','Online'],['Gói đề xuất:','Recommended plan:']
];
const translations=Object.fromEntries(entries);
const patterns=[
[/^Giỏ hàng \((\d+)\)$/,'Cart ($1)'],
[/^Giá trị: (.+)$/,'Amount: $1'],
[/^Mã DEMO: (.+)$/,'Demo ID: $1'],
[/^Tổng tiền minh hoạ: (.+)$/,'Illustrative total: $1'],
[/^(\d+) sản phẩm đang hiển thị • Giá do máy chủ cung cấp$/,'$1 products shown • Prices supplied by server'],
[/^(\d+) sản phẩm từ dữ liệu DEMO • Giá do máy chủ cung cấp$/,'$1 products from demo data • Server-confirmed prices'],
[/^(\d+) dịch vụ từ dữ liệu DEMO • Giá do máy chủ cung cấp$/,'$1 services from demo data • Server-confirmed prices'],
[/^(\d+) sản phẩm DEMO • Giá do máy chủ cung cấp$/,'$1 demo products • Server-confirmed prices'],
[/^Mã đơn (.+)$/,'Order ID $1'],
[/^Tìm thấy (\d+) bản ghi/,'Found $1 records'],
[/^Trang (\d+)\/(\d+)$/,'Page $1/$2'],
[/^(\d+) sản phẩm$/,'$1 products'],
[/^Thời lượng minh họa 60 phút$/,'Illustrative duration: 60 minutes'],
[/^Bàn (\d+)$/,'Table $1'],
[/^Sân vườn (\d+)$/,'Garden $1'],
[/^Chọn (.+) để xem giờ trống\.$/,'Select $1 to see available times.'],
[/^Thêm (.+) vào giỏ hàng$/,'Add $1 to cart'],
[/^Giảm số lượng$/,'Decrease quantity'],[/^Tăng số lượng$/,'Increase quantity'],
[/^Tìm (.+)\.\.\.$/,'Search $1...'],
[/^Hôm nay (.+)\?$/,'Today: $1?']
];
let current='vi';
try{const stored=localStorage.getItem('ezthing_language');const cookie=(document.cookie.match(/(?:^|;\s*)ez_lang=(en|vi)/)||[])[1];const browser=(navigator.language||'vi').toLowerCase();current=stored==='en'||stored==='vi'?stored:cookie|| (browser.startsWith('vi')?'vi':'en');}catch{current=(navigator.language||'vi').toLowerCase().startsWith('vi')?'vi':'en';}
const sourceNodes=new WeakMap();
const sourceAttrs=new WeakMap();
const ignore='script,style,code,pre,textarea,[contenteditable="true"],[data-ez-lang-ignore]';
const attrs=['placeholder','title','aria-label','alt'];
function translate(input){
  if(current!=='en'||!input)return input;
  if(Object.prototype.hasOwnProperty.call(translations,input))return translations[input];
  for(const [re,to] of patterns){if(re.test(input))return input.replace(re,to);}
  return input;
}
function translateNode(node){
  if(node.nodeType!==3||!node.parentElement||node.parentElement.closest(ignore))return;
  const value=node.nodeValue;
  if(!value||!value.trim())return;
  let original=sourceNodes.get(node);
  if(original===undefined||value!==original&&value!==translate(original)){original=value;sourceNodes.set(node,original);}
  const match=original.match(/^(\s*)([\s\S]*?)(\s*)$/);
  if(!match)return;
  const next=match[1]+translate(match[2])+match[3];
  if(value!==next)node.nodeValue=next;
}
function translateAttrs(el){
  if(el.closest(ignore))return;
  let originals=sourceAttrs.get(el);
  if(!originals){originals={};sourceAttrs.set(el,originals);}
  for(const name of attrs){
    if(!el.hasAttribute(name))continue;
    const value=el.getAttribute(name)||'';
    if(!(name in originals)||value!==originals[name]&&value!==translate(originals[name]))originals[name]=value;
    const next=translate(originals[name]);
    if(value!==next)el.setAttribute(name,next);
  }
}
function translateTree(node){
  if(node.nodeType===3){translateNode(node);return;}
  if(node.nodeType!==1||node.matches(ignore))return;
  translateAttrs(node);
  const walk=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);
  let currentNode;while((currentNode=walk.nextNode()))translateNode(currentNode);
  for(const child of node.querySelectorAll('[placeholder],[title],[aria-label],[alt]'))translateAttrs(child);
}
function makeSwitcher(){
  const box=document.createElement('div');
  box.className='ez-language-switch';
  box.setAttribute('role','group');
  box.setAttribute('aria-label','Language / Ngôn ngữ');
  box.setAttribute('data-ez-lang-ignore','');
  for(const lang of ['vi','en']){
    const b=document.createElement('button');
    b.type='button';b.dataset.lang=lang;
    b.textContent=lang==='vi'?'VI':'EN';
    b.setAttribute('aria-label',lang==='vi'?'Tiếng Việt':'English');
    b.addEventListener('click',()=>setLanguage(lang));
    box.appendChild(b);
  }
  return box;
}
function refreshSwitcher(){
  const target=document.querySelector('.site-header-actions,.customer-h-actions,.topbar-right,.top-actions,.auth-card,.auth-side,.auth-main')||document.body;
  let box=document.querySelector('.ez-language-switch');
  if(!box)box=makeSwitcher();
  if(box.parentElement!==target)target.appendChild(box);
  box.classList.toggle('ez-language-floating',target===document.body||target.classList.contains('auth-card')||target.classList.contains('auth-side')||target.classList.contains('auth-main'));
  for(const b of box.querySelectorAll('[data-lang]')){const active=b.dataset.lang===current;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));}
}
let running=false,scheduled=false;
function apply(){
  if(running)return;
  running=true;
  try{
    document.documentElement.lang=current;
    document.documentElement.dataset.ezLanguage=current;
    if(document.body)translateTree(document.body);
    refreshSwitcher();
  }finally{running=false;}
}
function schedule(){
  if(scheduled)return;scheduled=true;
  queueMicrotask(()=>{scheduled=false;apply();});
}
function setLanguage(lang){
  if(lang!=='vi'&&lang!=='en')return;
  current=lang;
  try{localStorage.setItem('ezthing_language',lang);}catch{}
  document.cookie='ez_lang='+lang+'; Max-Age=31536000; Path=/; SameSite=Lax';
  apply();
  document.dispatchEvent(new CustomEvent('ezthing:language-changed',{detail:{lang}}));
}
const api={language:()=>current,locale:()=>current==='en'?'en-US':'vi-VN',translate,setLanguage,apply};
Object.defineProperty(window,'EZI18N',{value:Object.freeze(api),writable:false});
const ready=()=>{
  apply();
  new MutationObserver(()=>schedule()).observe(document.documentElement,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:attrs});
  window.addEventListener('pageshow',schedule);
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready,{once:true});
else ready();
})();
