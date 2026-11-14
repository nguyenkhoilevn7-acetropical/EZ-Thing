/* EZ Thing centralized client i18n (VI/EN).
 * Translates UI text/attributes only; never sends content to external translation APIs.
 * Dynamic templates are translated via MutationObserver without modifying business data.
 */
(() => {
'use strict';
const entries = [
/* Public pricing, reservation pages and reservation workflows. */
["NHÀ HÀNG & CAFE","RESTAURANTS & CAFES"],
["Đặt bàn | EZ Thing Cafe","Table reservations | EZ Thing Cafe"],
["Quản lý đặt bàn | EZ Thing","Reservations management | EZ Thing"],
["EZ Thing • Thiết kế thương hiệu","EZ Thing • Brand design"],
["EZ Thing Control — Quản trị hệ thống","EZ Thing Control — Platform administration"],
["Cửa hàng trải nghiệm — EZ Thing","Demo storefront — EZ Thing"],
["BẢN DEMO • KHÔNG XÁC NHẬN ĐẶT BÀN THẬT","DEMO MODE • NO REAL TABLE RESERVATIONS"],
["Đặt bàn","Table booking"],
["Quản lý quán ↗","Merchant management ↗"],
["ĐẶT BÀN TRỰC TUYẾN","ONLINE TABLE RESERVATIONS"],
["Hẹn nhau","Make plans"],
["một buổi đẹp.","for a wonderful day."],
["Chọn ngày, khung giờ và số người. Quán sẽ kiểm tra bàn phù hợp trước khi xác nhận yêu cầu.","Choose a date, time and party size. The restaurant will check suitable tables before confirming your request."],
["Chọn thời gian","Choose a time"],
["Đặt trước 30 phút","Book at least 30 minutes ahead"],
["60–120 phút","60–120 minutes"],
["01 / ĐẶT BÀN","01 / RESERVATIONS"],
["Một chiếc bàn, đúng lúc.","The right table, at the right time."],
["Chọn giờ còn chỗ và để lại thông tin liên hệ.","Choose an available time and provide your contact details."],
["Thời gian & số khách","Date, time & guests"],
["Ngày đến","Visit date"],
["Số khách","Party size"],
["Thời lượng giữ bàn","Seating duration"],
["Giờ đến có thể chọn","Available arrival times"],
["Cập nhật","Refresh"],
["Đang tải giờ trống…","Loading available times…"],
["Thông tin khách","Guest information"],
["Tên người đặt bàn","Reservation name"],
["Ghi chú (tùy chọn)","Notes (optional)"],
["Ví dụ: muốn ngồi sân vườn, có trẻ nhỏ…","Example: garden seating, bringing children…"],
["Yêu cầu sẽ có trạng thái","Your request will be marked"],
["Chờ xác nhận","Pending confirmation"],
[". Chưa gửi SMS, email hay thu cọc.",". No SMS, email or deposit is sent or collected."],
["Gửi yêu cầu đặt bàn","Submit reservation request"],
["QUY TRÌNH","HOW IT WORKS"],
["Hẹn giờ.","Choose a time."],
["Chọn bàn.","Find a table."],
["Gặp nhau.","Meet up."],
["Chọn ngày và giờ còn chỗ","Choose an available date and time"],
["Quán kiểm tra và xác nhận","The restaurant checks and confirms"],
["Đến quán và nhận bàn","Arrive and take your table"],
["Đi nhóm đông?","Coming with a larger group?"],
["Hệ thống tìm bàn phù hợp với số khách. Nếu hết chỗ, chọn giờ khác hoặc nhắn quán.","We look for a table that fits your group. If unavailable, try another time or contact the restaurant."],
["Liên hệ với quán ↗","Contact the restaurant ↗"],
["02 / LIÊN HỆ","02 / CONTACT"],
["Còn điều gì","Anything else"],
["muốn hỏi?","you'd like to ask?"],
["Gọi điện nếu quán đã cung cấp số liên hệ, hoặc gửi lời nhắn vào Back-Office.","Call if the restaurant has provided a number, or send a message to its back-office."],
["Đang tải thông tin liên hệ…","Loading contact information…"],
["Để lại lời nhắn","Leave a message"],
["Tên của bạn","Your name"],
["Lời nhắn","Message"],
["Anh/chị muốn hỏi gì về đặt bàn?","What would you like to ask about reservations?"],
["Gửi lời nhắn","Send message"],
["Lời nhắn lưu trong hệ thống, không gửi SMS hoặc Zalo.","Messages are stored in the system; no SMS or Zalo message is sent."],
["Về thực đơn","Back to menu"],
["EZ THING • BACK-OFFICE NHÀ HÀNG / CAFE","EZ THING • RESTAURANT / CAFE BACK-OFFICE"],
["Lịch đặt bàn","Reservation calendar"],
["CỬA HÀNG / NHÀ HÀNG","RESTAURANT / CAFE"],
["& lịch hẹn.","& appointments."],
["Theo dõi khách đến, bàn giữ trước và liên hệ với khách trong một nơi.","Track arrivals, reserved tables and customer messages in one place."],
["Trang khách","Guest page"],
["Đang xác minh tài khoản…","Verifying account…"],
["LỊCH ĐẶT BÀN","RESERVATIONS"],
["Danh sách khách","Guest reservations"],
["Thêm lịch","Add reservation"],
["Mọi trạng thái","All statuses"],
["Đã xác nhận","Confirmed"],
["Đã nhận bàn","Seated"],
["Hoàn tất","Completed"],
["Đã hủy","Cancelled"],
["Không đến","No-show"],
["Xóa bộ lọc","Clear filters"],
["THÔNG TIN CÔNG KHAI","PUBLIC INFORMATION"],
["Thông tin liên hệ","Contact information"],
["Số điện thoại quán","Restaurant phone number"],
["Số cho khách gọi","Customer contact number"],
["Địa chỉ nhà hàng / cafe","Restaurant / cafe address"],
["Giờ mở cửa hiển thị","Displayed opening hours"],
["Lưu thông tin","Save information"],
["Giờ đặt bàn DEMO cố định 08:00–20:30. Thông tin giờ mở cửa chỉ dùng để hiển thị.","Demo reservation hours are fixed at 08:00–20:30. Published opening hours are display-only."],
["HỘP THƯ","INBOX"],
["Yêu cầu liên hệ","Contact inquiries"],
["Về quản lý","Back to management"],
["Thương hiệu của bạn.","Your brand."],
["BẢN XEM TRƯỚC RIÊNG TƯ · KHÔNG NHẬN ĐƠN HÀNG THẬT","PRIVATE PREVIEW · NO REAL ORDERS"],
["Quay về quản lý","Back to management"],
["Trải nghiệm riêng theo thương hiệu của bạn.","A customer experience tailored to your brand."],
["Khám phá thực đơn","Explore menu"],
["Phản hồi không hợp lệ","Invalid response"],
["Không thể thực hiện yêu cầu","Unable to complete the request"],
["Thử lại","Try again"],
["Gọi ngay","Call now"],
["Quán chưa cập nhật số điện thoại","The restaurant has not provided a phone number"],
["Gửi email","Send email"],
["Đang kiểm tra lịch trống…","Checking available times…"],
["Không có bàn phù hợp. Hãy chọn ngày/giờ hoặc số người khác.","No suitable tables available. Try another date, time or party size."],
["Vui lòng chọn giờ còn chỗ","Please choose an available time"],
["Vui lòng nhập đúng số điện thoại","Please enter a valid phone number"],
["Đã nhận yêu cầu!","Request received!"],
["Bàn được đề xuất:","Suggested table:"],
["Chờ quán xác nhận","Awaiting restaurant confirmation"],
["trước khi đến.","before arrival."],
["Kiểm tra trạng thái","Check status"],
["Mã yêu cầu:","Request ID:"],
["Trạng thái hiện tại:","Current status:"],
["Đã gửi yêu cầu đặt bàn DEMO","Demo reservation request submitted"],
["Lời nhắn đã tới hộp thư của quán (DEMO)","Your message was delivered to the restaurant's inbox (DEMO)"],
["Trang đặt bàn này chỉ hoạt động với tài khoản DEMO trên staging.","This reservation page is available only to DEMO accounts on staging."],
["Khách đã nhận bàn","Guest seated"],
["Khách không đến","Guest did not arrive"],
["Mới gửi","New"],
["Đã liên hệ","Contacted"],
["Đã đóng","Closed"],
["Xác nhận bàn","Confirm reservation"],
["Hủy yêu cầu","Cancel request"],
["Khách đã đến","Guest arrived"],
["Sắp diễn ra","Upcoming"],
["Chờ duyệt","Pending review"],
["Liên hệ mới","New inquiries"],
["Khách online","Online guest"],
["Nhân viên tạo","Staff-created"],
["Chưa có lịch đặt bàn phù hợp với bộ lọc.","No reservations match these filters."],
["Đóng yêu cầu","Close inquiry"],
["Chưa có lời nhắn nào.","No messages yet."],
["Xác nhận chuyển trạng thái lịch đặt bàn?","Confirm changing the reservation status?"],
["Đã cập nhật lịch đặt bàn","Reservation updated"],
["Đã cập nhật yêu cầu","Inquiry updated"],
["Thêm đặt bàn","Add reservation"],
["Đặt bàn thủ công","Manual reservation"],
["Họ tên khách","Guest name"],
["Điện thoại","Phone"],
["Thời lượng","Duration"],
["Giờ còn bàn","Available time"],
["Đang tải…","Loading…"],
["Đang kiểm tra…","Checking…"],
["Không còn bàn","No tables available"],
["Không thể tải giờ","Could not load available times"],
["Tạo đặt bàn","Create reservation"],
["Chọn giờ còn bàn","Choose an available time"],
["Đã tạo lịch, chờ xác nhận","Reservation created, awaiting confirmation"],
["Không tìm thấy doanh nghiệp Cafe / Nhà hàng có chức năng quản lý bàn trong tài khoản.","No restaurant or cafe business with table management was found in this account."],
["Đã làm mới đặt bàn","Reservations refreshed"],
["Đã lưu liên hệ. Trang khách sẽ thấy cập nhật này.","Contact information saved. The customer page will reflect the change."],
["Đang quản lý:","Managing:"],
["bàn phù hợp","suitable tables"],
["bàn","tables"],

['Doanh thu hôm nay',"Today's revenue"],
['Từ đơn đã xác nhận nhận tiền','From confirmed paid orders'],
['Cảnh báo tồn kho','Low-stock alerts'],
['Sản phẩm trong danh mục','Products in catalog'],
['Còn tối đa 5 sản phẩm','5 or fewer units in stock'],
['Sản phẩm đang quản lý','Managed products'],
['Đang xử lý','In progress'],
['Sắp hết','Running low'],
['Lưu địa chỉ và thông tin liên hệ','Save addresses and contact details'],
['Bán hàng tại quầy hoặc tại bàn','Sell at the counter or table'],
['Xây dựng danh mục kinh doanh','Build your product catalog'],
['Thiết lập khu vực phục vụ','Set up your service areas'],
['Thêm sản phẩm để bắt đầu tạo đơn bán hàng.','Add a product to start taking orders.'],
['Chưa có sản phẩm','No products yet'],
['Không theo dõi kho','Inventory not tracked'],
['Không có đơn hàng','No orders yet'],
['Các đơn hàng sẽ hiển thị tại đây.','Orders will appear here.'],
['Chưa có đơn hàng','No orders yet'],
['Tạo đơn đầu tiên để bắt đầu theo dõi doanh thu.','Create your first order to start tracking revenue.'],
['Còn trống','Available'],
['Đang phục vụ','Occupied'],
['Xác nhận nhận tiền chỉ ghi nhận thủ công; chưa tích hợp ngân hàng và đối soát tự động.','Payments are confirmed manually; bank reconciliation is not connected yet.'],

['CỬA HÀNG ONLINE','ONLINE STORE'],['ĐẶT BÀN TRƯỚC','TABLE RESERVATIONS'],
['Xem demo ↗','View demo ↗'],['Mở giao diện website đang xem','Open current website demo'],
['Trình chiếu giao diện website demo thực tế','Real website demo slideshow'],
['Chọn màn hình trình chiếu','Choose a demo screen'],
['Xem website cafe và nhà hàng','View cafe and restaurant website'],
['Xem website bán lẻ','View retail website'],
['Xem website bán hàng online','View online store'],
['Xem website spa wellness','View spa website'],
['Xem website đặt bàn trước','View table reservations'],

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
,
["Dữ liệu doanh nghiệp được phân tách theo tài khoản","Business data is separated by account"],
["🔒 Dữ liệu doanh nghiệp được phân tách theo tài khoản","🔒 Business data is separated by account"],
["Tăng trưởng doanh thu","Revenue growth"],
["Mọi hoạt động.","All operations."],
["Gợi ý dựa trên quy tắc thiết lập • Không tự phát triển chức năng ngoài hệ thống","Recommendation based on configured rules • No new features are auto-generated"],
["đ/tháng*","VND/month*"],
[". *Giá dự kiến. Bản MVP chỉ kích hoạt chế độ pilot, chưa thu tiền hay kết nối thanh toán.",". *Estimated prices. This MVP is a pilot; no payment system is connected."],
["🧪 Chế độ DEMO • Toàn bộ dữ liệu chỉ để thử nghiệm","🧪 DEMO mode • All data is for testing only"],
["Mất kết nối. Chỉ xem được giao diện đã lưu, không thể tạo đơn khi offline.","Connection lost. You can view cached data but cannot create orders offline."],
["Xem trang khách ↗","View customer page ↗"],
["Xác nhận nhận tiền chỉ ghi nhận thủ công; chưa tích hợp ngân hàng và đối soát tự động.","Confirming payment is a manual action; bank reconciliation is not integrated."],
["Bấm vào bàn để tạo đơn mới. Bàn có đơn chưa thanh toán sẽ được đánh dấu đang phục vụ.","Select a table to create an order. Tables with unpaid orders are marked as occupied."],
["Gói tính năng được kiểm tra tại API. Để chuyển gói cần hoàn thiện hệ thống thanh toán và cấp quyền.","Plan entitlements are enforced by the API. Billing and entitlement changes require additional integration."],
["Để nhập, xuất hoặc kiểm kho, chọn “Sản phẩm” rồi “Kho”. Mọi biến động được lưu trong sổ.","For stock receipt, issue or counts, open “Products” and then “Inventory”. All changes are logged."],
["Đây là trạng thái tự ghi nhận, chưa tích hợp đơn vị vận chuyển hoặc đối soát COD.","Delivery statuses are recorded internally; no courier or COD reconciliation is integrated."],
["Đơn vị vận chuyển (tùy chọn)","Courier (optional)"],
["Mã vận đơn (tùy chọn)","Tracking number (optional)"],
["Kho sẽ tự trừ khi tạo đơn. Với dịch vụ/đồ uống chưa áp dụng định lượng, có thể tắt theo dõi kho.","Stock is deducted when orders are placed. Stock tracking can be disabled for services or drinks without recipes."],
["Giá bán và tồn kho sẽ được tính lại trên server. Chưa có tính thuế, phí giao hay thanh toán tự động.","Prices and stock are recalculated on the server. Taxes, delivery fees and automatic payments are not included."],
["Thay đổi số lượng (+ nhập / - xuất)","Quantity change (+ receive / - issue)"],
["Chỉ xác nhận sau khi bạn thực sự đã nhận đủ tiền từ khách hàng. Hệ thống chưa tự đối soát ngân hàng.","Confirm only after you actually receive the full payment. Automatic bank reconciliation is not available."],
["Anh/chị có chắc chắn muốn hủy lịch này? Thao tác sẽ mở lại khung giờ cho khách khác.","Are you sure you want to cancel this booking? The time slot will become available again."],
["Quản lý ↗","Management ↗"],
["Khám phá ngay →","Explore now →"],
["· Chỉ sử dụng dữ liệu DEMO · Không xử lý đơn hàng thật.","· DEMO data only · No real orders processed."],
["Mở khu quản lý ↗","Open management ↗"],
["Tiếp tục đặt lịch ↗","Continue booking ↗"],
["Xác nhận lịch DEMO ↗","Confirm demo booking ↗"],
["Điều hành nền tảng. Có kiểm soát.","Operate the platform with confidence."],
["Quản trị doanh nghiệp, tài khoản, gói quyền truy cập và nhật ký thay đổi trên cùng một giao diện. Các thao tác quan trọng đều được xác nhận và lưu vết.","Manage businesses, accounts, plans and audit logs in one workspace. Sensitive actions require confirmation and are recorded."],
["EZ Thing v0.4 · Staging &nbsp; / &nbsp; Phân quyền máy chủ","EZ Thing v0.4 · Staging &nbsp; / &nbsp; Server-side access controls"],
["◈ Xem bản DEMO quản trị","◈ View admin DEMO"],
["Đổi tài khoản","Switch account"],
["🔐 Quyền truy cập được kiểm soát","🔐 Restricted access"],
["Đăng nhập + danh sách email được phép + mã bảo vệ bổ sung. Không mở quyền Super Admin cho khách DEMO.","Sign-in, allowlisted emails and an additional security code. DEMO accounts cannot gain Super Admin access."],
["Chưa cấu hình quản trị? Chủ hệ thống cần thiết lập","Admin not configured? The platform owner must configure"],
["và","and"],
["trong môi trường Render.","in the Render environment."],
["← Về website EZ Thing","← Back to EZ Thing"],
["Khu quản lý doanh nghiệp ↗","Merchant workspace ↗"],
["✳ CHẾ ĐỘ XEM TRƯỚC — Toàn bộ số liệu là giả lập, không có quyền thay đổi dữ liệu thật.","✳ PREVIEW MODE — All numbers are simulated; no permission to modify actual data."],
["Khu quản lý","Management"],
["↻ Làm mới","↻ Refresh"],
["↻ Thử lại","↻ Retry"],
["Xem doanh nghiệp →","View businesses →"],
["Phân bổ gói quản lý","Plan distribution"],
["Theo doanh nghiệp","By business"],
["Các gói hiện cấp quyền dùng thử. Không đồng nghĩa đã thanh toán.","Plans grant pilot access only and do not indicate payment."],
["Tất cả →","See all →"],
["Tìm thấy","Found"],
["← Trước","← Previous"],
["Tiếp →","Next →"],
["ⓘ &nbsp; Các doanh nghiệp dưới đây đều là dữ liệu mẫu. Mọi chức năng ghi dữ liệu đã bị vô hiệu hóa.","ⓘ &nbsp; All businesses below are examples. All data-changing actions are disabled."],
["Ngành","Industry"],
["Chi tiết →","Details →"],
["ⓘ &nbsp; Danh sách mẫu không chứa dữ liệu khách hàng thật.","ⓘ &nbsp; This sample list contains no real customer information."],
["Bảng giá chỉ là đề xuất. Đổi gói trong /admin chỉ thay quyền sử dụng module, không ghi nhận thanh toán, hóa đơn hay MRR.","Pricing is proposed only. Changing a plan in /admin affects feature access but does not record payments, invoices or MRR."],
["/ tháng · dự kiến","/ month · estimate"],
["Thanh toán chưa kích hoạt","Billing is not enabled"],
["ⓘ &nbsp; Trạng thái minh họa. Không thay thế giám sát hệ thống thực.","ⓘ &nbsp; Status is illustrative and does not replace live monitoring."],
["Đổi gói thử nghiệm","Change pilot plan"],
["Bản DEMO chỉ cho phép xem. Không có thao tác thay đổi dữ liệu.","The DEMO is read-only. Changes to real data are not permitted."],
["Gói hiện tại","Current plan"],
["Chủ doanh nghiệp","Business owner"],
["Email chủ sở hữu","Owner email"],
["Số chi nhánh","Branch count"],
["Module đang sử dụng","Enabled modules"],
["Không có dữ liệu chi tiết trong DEMO","Detailed data not available in DEMO"],
["Dữ liệu DEMO chỉ minh họa, không thể thao tác thật.","DEMO data is illustrative and cannot be changed."],
["Tham gia doanh nghiệp","Business memberships"],
["Quyền trong doanh nghiệp","Business role"],
["Không có chi tiết trong bản xem trước","No details in preview mode"],
["Tài khoản Super Admin được bảo vệ, không thể tự khóa hoặc khóa qua giao diện.","Super Admin accounts are protected and cannot be suspended from this interface."],
["CHỌN GÓI ĐÍCH","SELECT TARGET PLAN"],
["Gói pilot chỉ điều chỉnh quyền; không tạo hóa đơn hoặc thu phí. Hạ gói sẽ bị từ chối nếu số chi nhánh vượt giới hạn.","Pilot plans only change access; they do not issue invoices or charge subscriptions. Downgrades exceeding branch limits are rejected."],
["NHẬP CHÍNH XÁC TÊN DOANH NGHIỆP","ENTER THE EXACT BUSINESS NAME"],
["NHẬP CHÍNH XÁC EMAIL TÀI KHOẢN","ENTER THE EXACT ACCOUNT EMAIL"],
["LÝ DO THAY ĐỔI (TỐI THIỂU 8 KÝ TỰ)","REASON FOR CHANGE (AT LEAST 8 CHARACTERS)"],
["Tôi xác nhận đã kiểm tra đối tượng và hậu quả của thao tác.","I confirm that I have checked the target and consequences of this action."],
["Xem thực đơn ↗","View menu ↗"],
["Xin chào! 👋","Hello! 👋"],
["⌕ &nbsp; Tìm món yêu thích...","⌕ &nbsp; Find your favorite drink..."],
["Khám phá ngay ↗","Explore now ↗"],
["THIẾT KẾ CHO KINH DOANH THỰC TẾ","BUILT FOR REAL BUSINESSES"],
["◈ 1 nền tảng","◈ 1 platform"],
["✧ 4 ngành","✧ 4 industries"],
["↗ Triển khai linh hoạt","↗ Flexible setup"],
["◎ Dễ sử dụng","◎ Easy to use"],
["Xem menu khách hàng ↗","View customer menu ↗"],
["Xem cửa hàng mẫu ↗","View retail demo ↗"],
["Khám phá online shop ↗","Explore online shop ↗"],
["Xem trang đặt lịch ↗","View booking page ↗"],
["Trải nghiệm demo ↗","Try demo ↗"],
["PLUS • ĐỀ XUẤT","PLUS • RECOMMENDED"],
["© 2026 EZ Thing • Sản phẩm đang trong giai đoạn thử nghiệm.","© 2026 EZ Thing • Product in pilot testing."],
["EZ Thing — Mọi thứ kinh doanh, đơn giản hơn.","EZ Thing — Business made simple."]
,
["Mỗi doanh nghiệp.","Every business."],
["Một dấu ấn riêng.","Its own identity."],
["Tùy chỉnh tên, thông tin, banner, logo và màu sắc cho trang khách hàng của doanh nghiệp. Quyền sử dụng tùy theo gói đang kích hoạt.","Customize the name, details, banner, logo and colors of your storefront, according to your active plan."],
["← Quản lý doanh nghiệp","← Merchant management"],
["Thiết kế trang khách hàng theo thương hiệu","Branded customer storefront"],
["Chỉnh sửa thương hiệu & xem trước ↗","Edit branding & preview ↗"],
["Mỗi nhà hàng hoặc cửa hàng có tên, banner, thông tin riêng và trang xem trước. BASIC: banner mẫu • PLUS: logo, banner riêng và màu sắc • PRO: thêm kiểu bố cục.","Every restaurant or store has its own name, banner, details and preview. BASIC: preset banners • PLUS: logo, custom banner, colors • PRO: layouts."],
["Bản pilot chỉ xem trước cho chủ cửa hàng, chưa xuất bản website nhận đơn công khai.","Pilot version allows owner previews only; storefronts are not publicly published for real orders."],
["01 / QUẢN LÝ THƯƠNG HIỆU","01 / BRAND SETTINGS"],
["02 / XEM TRƯỚC","02 / PREVIEW"],
["03 / QUYỀN THEO GÓI","03 / PLAN BENEFITS"],
["Tùy chỉnh trang khách","Customize storefront"],
["Chọn doanh nghiệp của bạn","Select your business"],
["Thông tin cơ bản","Business details"],
["BASIC trở lên","BASIC and above"],
["Tên nhà hàng / cửa hàng","Restaurant / store name"],
["Giới thiệu ngắn","Short description"],
["Giới thiệu nét đặc sắc của thương hiệu","Describe what makes your brand unique"],
["Số điện thoại","Phone number"],
["Địa chỉ","Address"],
["Chọn banner mẫu","Choose a preset banner"],
["Có sẵn cho mọi gói.","Available on all plans."],
["Thiết kế nâng cao","Advanced styling"],
["PLUS trở lên","PLUS and above"],
["Tiêu đề trang chủ","Hero headline"],
["Một trải nghiệm đáng nhớ","An unforgettable experience"],
["Banner bằng đường dẫn ảnh","Custom banner image URL"],
["Logo bằng đường dẫn ảnh","Custom logo image URL"],
["Trong giai đoạn pilot chỉ hỗ trợ ảnh từ images.unsplash.com.","During the pilot only images.unsplash.com links are supported."],
["Màu thương hiệu","Brand color"],
["Kiểu trình bày","Layout options"],
["Lời nhắn chân trang","Footer message"],
["Cảm ơn bạn đã ghé thăm!","Thank you for visiting!"],
["Lưu thay đổi","Save changes"],
["Quyền được kiểm tra ở backend. Tất cả bản xem trước đều riêng tư.","Plan permissions are enforced by the API. All previews are private."],
["Ảnh và màu sắc thay đổi theo thiết lập.","Images and colors follow your settings."],
["Mở trang xem trước ↗","Open private preview ↗"],
["Cá nhân hóa theo gói","Branding by plan"],
["Giá bên dưới chỉ là đề xuất trong giai đoạn pilot. Chưa có upload ảnh trực tiếp, tên miền riêng, website công khai hoặc thanh toán thuê bao.","Displayed prices are proposals for the pilot. Direct uploads, custom domains, public storefronts and subscription billing are not yet available."],
["TRẢI NGHIỆM THƯƠNG HIỆU CỦA BẠN","YOUR BRAND EXPERIENCE"],
["Thực đơn & sản phẩm","Menu & products"],
["Liên hệ","Contact"],
["DÀNH RIÊNG CHO CỬA HÀNG","YOUR STOREFRONT"],
["Danh mục & sản phẩm","Categories & products"],
["Giá và danh mục được đọc từ doanh nghiệp hiện tại. Đây chỉ là bản xem trước riêng tư, không tạo đơn hàng thật.","Catalog and prices come from your business. This is a private preview that cannot create real orders."],
["Không thể mở bản xem trước. Hãy đăng nhập bằng tài khoản chủ doanh nghiệp.","Unable to open the preview. Sign in using the business owner account."],
["Chưa có sản phẩm. Vào mục Sản phẩm trong khu quản lý để thêm.","No products yet. Add them from Products in your merchant workspace."],
["Bản xem trước chỉ dành cho chủ cửa hàng; chưa công khai để nhận đơn thật.","Private preview for owners; no public order acceptance."],
["Đã tải cấu hình riêng của doanh nghiệp. Các thay đổi chưa lưu sẽ không được công bố.","Business branding loaded. Unsaved changes are not published."],
["Đã lưu thành công! Mở trang xem trước để kiểm tra thay đổi.","Saved successfully. Open the private preview to review your changes."],
["Bạn chưa có doanh nghiệp. Hãy tạo doanh nghiệp trong khu quản lý.","You have no businesses yet. Create one in the merchant workspace."],
["Hãy đăng nhập từ /app trước.","Please sign in from /app first."],
["Tên và giới thiệu riêng","Custom name and description"],
["Banner mẫu theo ngành","Industry-specific preset banner"],
["Trang xem trước riêng tư","Private storefront preview"],
["Tất cả quyền BASIC","Everything in BASIC"],
["Banner và logo bằng link ảnh hợp lệ","Banner and logo via approved image URLs"],
["Màu và tiêu đề hero","Brand color and hero title"],
["Tất cả quyền PLUS","Everything in PLUS"],
["3 kiểu bố cục trang khách","Three storefront layouts"],
["Thông điệp chân trang, tối đa 10 chi nhánh","Custom footer and up to 10 branches"],
["Tên, giới thiệu, banner mẫu","Name, description and preset banner"],
["Logo, banner riêng và màu thương hiệu","Logo, custom banner and brand color"],
["3 bố cục trang khách hàng","Three storefront layouts"],
["Thương hiệu riêng từ gói đầu tiên: tên nhà hàng, thông tin liên hệ, banner mẫu và quản lý đơn.","Your own brand from day one: restaurant name, contact details, preset banner and order management."],
["Thiết kế nổi bật hơn với logo, ảnh banner riêng, tiêu đề và màu sắc thương hiệu.","Stand out with a logo, custom banner, headline and brand colors."],
["Tùy biến giao diện sâu hơn, phù hợp thương hiệu và mô hình nhiều chi nhánh.","More layout control for your brand and multi-location business."],
["Mỗi doanh nghiệp được lưu thương hiệu độc lập. Gói hiện tại quyết định quyền chỉnh sửa tại backend. Trang khách hàng đang ở chế độ xem trước, chưa có domain riêng hoặc thanh toán thật.","Each business has isolated branding. Your plan controls editing permissions in the API. Storefronts are private previews with no custom domains or real payments."],
["Lời nhắn cuối trang","Footer note"],
["Đang dùng","Current"],
["Đang sử dụng","Current plan"],
["Đã tải cấu hình riêng của doanh nghiệp.","Your business branding is loaded."]
];
const translations=Object.fromEntries(entries);
const patterns=[
[/^(\d+) khách$/,'$1 guests'],
[/^(\d+) phút$/,'$1 minutes'],
[/^(\d+) bàn phù hợp$/,'$1 suitable tables'],
[/^(\d+) bàn$/,'$1 tables'],
[/^Đang quản lý: (.+)$/,'Managing: $1'],
[/^Trạng thái hiện tại: (.+)$/,'Current status: $1'],
[/^Mã yêu cầu: (.+)$/,'Request ID: $1'],
[/^Bàn được đề xuất: (.+)$/,'Suggested table: $1'],


[/^(\d+) đơn đang xử lý$/,'$1 orders in progress'],
[/^(\d+) bàn trống • (\d+) bàn có khách$/,'$1 available tables • $2 occupied tables'],
[/^(\d+) sản phẩm đang quản lý$/,'$1 managed products'],
[/^(\d+) hồ sơ khách hàng$/,'$1 customer profiles'],

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
const documentTitleOriginal = document.title;
const sourceNodes=new WeakMap();
const sourceAttrs=new WeakMap();
const ignore='script,style,code,pre,textarea,[contenteditable="true"],[data-ez-lang-ignore]';
const attrs=['placeholder','title','aria-label','alt'];
function translateCore(input){
  if(Object.prototype.hasOwnProperty.call(translations,input))return translations[input];
  for(const [re,to] of patterns){if(re.test(input))return input.replace(re,to);}
  return null;
}
function translate(input){
  if(current!=='en'||!input)return input;
  const direct=translateCore(input);
  if(direct!==null)return direct;
  // Localize only known interface copy. Decorative checkmarks, arrows and
  // icon markers around it must not defeat dictionary lookup or change user data.
  const marked=input.match(/^((?:[✓✔☑•◈✧◎◷◌↗↻←→+★☆✳✦🔒]\s+)*)(.+?)(\s+[↗→←])?$/u);
  if(marked && (marked[1] || marked[3])){
    const localized=translateCore(marked[2]);
    if(localized!==null)return marked[1]+localized+(marked[3]||'');
  }
  return input;
}
function translateNode(node){
  if(node.nodeType!==3||!node.parentElement||node.parentElement.closest(ignore))return;
  const value=node.nodeValue;
  if(!value||!value.trim())return;
  let entry=sourceNodes.get(node);
  if(!entry||(value!==entry.original&&value!==entry.rendered)){
    entry={original:value,rendered:value};sourceNodes.set(node,entry);
  }
  const match=entry.original.match(/^(\s*)([\s\S]*?)(\s*)$/);
  if(!match)return;
  const next=match[1]+translate(match[2])+match[3];
  entry.rendered=next;
  if(value!==next)node.nodeValue=next;
}
function translateAttrs(el){
  if(el.closest(ignore))return;
  let originals=sourceAttrs.get(el);
  if(!originals){originals={};sourceAttrs.set(el,originals);}
  for(const name of attrs){
    if(!el.hasAttribute(name))continue;
    const value=el.getAttribute(name)||'';
    let entry=originals[name];
    if(!entry||(value!==entry.original&&value!==entry.rendered)){
      entry={original:value,rendered:value};originals[name]=entry;
    }
    const next=translate(entry.original);
    entry.rendered=next;
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
  const compact=window.matchMedia('(max-width:700px)').matches;
  const target=(compact?document.body:document.querySelector('.site-header-actions,.customer-h-actions,.topbar-right,.top-actions,.auth-card,.auth-side,.auth-main,.reservation-nav'))||document.body;
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
    // Also localize browser/tab titles; the body tree walker excludes <head>.
    document.title=translate(documentTitleOriginal);
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
  window.addEventListener('resize',schedule);
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready,{once:true});
else ready();
})();
