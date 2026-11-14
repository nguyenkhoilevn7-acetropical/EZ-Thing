(()=>{
'use strict';
const root=document.getElementById('customer-root');
const overlay=document.getElementById('customer-modal');
const toastRoot=document.getElementById('customer-toast');
const channel=location.pathname.startsWith('/menu/')?'cafe':location.pathname.startsWith('/booking/')?'wellness':location.pathname.endsWith('/mart')?'mart':'online';
const kinds={
 cafe:{industry:'fnb',label:'NHÀ HÀNG & CAFE',hero:'Một chút tươi mát,\nmột ngày tuyệt vời.',emoji:'☕',sub:'Hương vị tươi mới đang chờ bạn. Chọn món yêu thích, chọn bàn và gọi món trong vài chạm.',section:'Thực đơn hôm nay',cart:'Gọi món DEMO',action:'Gửi món đến quán'},
 mart:{industry:'retail',label:'CỬA HÀNG BÁN LẺ',hero:'Mua sắm nhỏ,\nniềm vui lớn.',emoji:'🛍️',sub:'Khám phá những món đồ hữu ích mỗi ngày. Chọn hàng và gửi yêu cầu giữ sản phẩm.',section:'Gợi ý cho bạn',cart:'Giữ hàng DEMO',action:'Gửi yêu cầu giữ hàng'},
 online:{industry:'online',label:'CỬA HÀNG ONLINE',hero:'Phong cách của bạn,\nchọn theo cách riêng.',emoji:'📦',sub:'Mua sắm dễ dàng từ điện thoại. Chọn sản phẩm, nhập địa chỉ và gửi đơn giao hàng DEMO.',section:'Sản phẩm nổi bật',cart:'Đơn hàng DEMO',action:'Gửi đơn đặt hàng'},
 wellness:{industry:'services',label:'SPA & WELLNESS',hero:'Khoảng thời gian\ndành cho chính bạn.',emoji:'🌿',sub:'Chọn một liệu trình, chuyên viên và khung giờ phù hợp. Đặt lịch đơn giản trong vài bước.',section:'Chọn trải nghiệm của bạn',cart:'Đặt lịch DEMO',action:'Xác nhận lịch DEMO'}
};
const info=kinds[channel];
const st={csrf:'',business:null,products:[],tables:[],staff:[],cart:{},filter:'Tất cả',search:'',sort:'default',onlyAvailable:false,pendingId:null,slotRequestId:0,flow:null,
       service:null,assignee:'Linh',date:'',slots:[],slot:null,bookingLoading:false,lastOrder:null};
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const V=n=>new Intl.NumberFormat('vi-VN').format(Number(n)||0)+'đ';
const icon=p=>{const s=(p.sku+' '+p.name).toLowerCase(); if(/matcha/.test(s))return '🍵';if(/cafe|cà phê|brew/.test(s))return '☕';if(/trà đào|đào/.test(s))return '🍑';if(/cam|nước ép/.test(s))return '🍊';if(/trà vải/.test(s))return '🍹';if(/bình giữ/.test(s))return '🥤';if(/tote|túi/.test(s))return '👜';if(/sổ/.test(s))return '📓';if(/áo/.test(s))return '👕';if(/nón/.test(s))return '🧢';if(/xông/.test(s))return '♨️';if(/massage/.test(s))return '💆';if(/da/.test(s))return '🌸';return info.emoji};
const id=()=>('d'+(globalThis.crypto?.randomUUID?.()||Math.random().toString(36).slice(2)+Date.now()).replace(/[^\w-]/g,''));
async function api(path,options={}){
 const r=await fetch('/api'+path,{credentials:'same-origin',cache:'no-store',...options,
  headers:{'Content-Type':'application/json',...(st.csrf&&options.method&&options.method!=='GET'?{'x-csrf-token':st.csrf}:{}),...(options.headers||{})}});
 let body;try{body=await r.json()}catch{body={detail:'Không nhận được phản hồi từ máy chủ'}};
 if(!r.ok){const e=new Error(typeof body.detail==='string'?body.detail:'Yêu cầu thất bại');e.status=r.status;throw e;}return body;
}
function toast(message,bad=false){toastRoot.textContent=message;toastRoot.className='customer-toast'+(bad?' bad':'');setTimeout(()=>{toastRoot.textContent='';toastRoot.className='';},3500)}
function blocked(message){root.innerHTML=`<header class="customer-header"><a class="customer-brand" href="/"><span class="mark">e.</span> EZ <strong>Thing</strong></a><a class="info-link" href="/app">Quản lý ↗</a></header><main class="closed-message"><span style="font-size:52px">🌿</span><h2>Trải nghiệm hiện chưa mở</h2><p>${E(message)}</p><a class="info-link" href="/">← Về trang chủ</a></main>`}
function header(){
 const count=cartQty();
 return `<div class="visitor-banner"><span class="banner-dot"></span> PHIÊN BẢN TRẢI NGHIỆM · KHÔNG THANH TOÁN THẬT</div>
 <header class="customer-header">
 <a class="customer-brand" href="/" aria-label="EZ Thing trang chủ"><span class="mark">${info.emoji}</span><span class="brand-words"><strong>${E(st.business?.name||'EZ Thing')}</strong><small>Powered by EZ Thing</small></span></a>
 <nav class="customer-h-actions" aria-label="Điều hướng cửa hàng">
   <a href="#section-main">${channel==='wellness'?'Dịch vụ':'Sản phẩm'}</a>
   <a href="#customer-about">Thông tin</a>
   ${channel!=='wellness'?`<button data-action="open-cart" class="head-cart" aria-label="Mở giỏ hàng"><span>Giỏ hàng</span><b>${count}</b></button>`:`<button data-action="book-scroll" class="head-cart">Đặt lịch <span aria-hidden="true">↗</span></button>`}
 </nav></header>`;
}
function hero(){
 const perks={
  cafe:['Menu & giá rõ ràng','Chọn bàn khi gửi món','Phiếu bếp thử nghiệm'],
  mart:['Kiểm tra hàng sẵn có','Giữ hàng tại cửa hàng','Không thanh toán trực tuyến'],
  online:['Chọn hàng nhanh chóng','Nhập địa chỉ khi đặt','Theo dõi tại khu quản lý'],
  wellness:['Dịch vụ & giá minh bạch','Chọn chuyên viên & giờ','Chống trùng lịch trên server']
 }[channel];
 return `<section class="merchant-hero kind-${info.industry}">
 <div class="merchant-copy">
  <span class="merchant-tag"><span class="hero-live-dot"></span> ${info.label} · GIAN HÀNG DEMO</span>
  <h1>${E(info.hero).replace(/\n/g,'<br>')}</h1><p>${E(info.sub)}</p>
  <div class="hero-buttons"><a class="hero-primary" href="#section-main">${channel==='wellness'?'Khám phá dịch vụ':'Khám phá sản phẩm'} <span aria-hidden="true">↗</span></a><span class="hero-caption">Không cần đăng nhập</span></div>
 </div>
 <div class="merchant-art" aria-hidden="true"><div class="art-halo"></div><div class="art-main">${info.emoji}</div>
 <div class="art-float art-float-top"><span>✦</span> ${channel==='wellness'?'Thời gian cho bạn':channel==='cafe'?'Hôm nay uống gì?':'Chọn điều bạn thích'}</div>
 <div class="art-float art-float-bottom"><span>✓</span> ${channel==='wellness'?'Đặt lịch theo giờ':'Mua sắm dễ dàng'}</div></div>
 </section>
 <div class="merchant-trust-strip">${perks.map((p,i)=>`<span><i>${['✓','✦','↗'][i]}</i>${E(p)}</span>`).join('')}</div>`;
}
function layout(){
 root.innerHTML=header()+`<main class="customer-main">${hero()}<section class="merchant-content" id="section-main">${channel==='wellness'?bookingHTML():catalogHTML()}</section></main>
 <section class="customer-about" id="customer-about"><span class="about-mark">${info.emoji}</span><div><strong>${E(st.business?.name||'EZ Thing')}</strong><p>Đây là bản xem trước được kết nối với doanh nghiệp DEMO và hệ thống quản lý. Không đặt mua, giao hàng hoặc thanh toán thật.</p></div><a href="/app">Mở quản lý demo ↗</a></section>
 <footer class="flow-footer">© EZ Thing · Trải nghiệm độc lập theo phiên · Không nhận thanh toán.</footer>
 <nav class="customer-bottom-nav" aria-label="Điều hướng nhanh"><a href="#section-main"><span aria-hidden="true">${channel==='wellness'?'🌿':'⌕'}</span>${channel==='wellness'?'Dịch vụ':'Khám phá'}</a><a href="#customer-about"><span aria-hidden="true">ⓘ</span>Thông tin</a>${channel==='wellness'?`<button data-action="book-scroll"><span aria-hidden="true">◷</span>Đặt lịch</button>`:`<button data-action="open-cart"><span aria-hidden="true">▣</span>Giỏ hàng <b>${cartQty()}</b></button>`}</nav>`+cartBar();
}
function cartQty(){return Object.values(st.cart).reduce((n,x)=>n+x,0)}
function cartTotal(){return st.products.reduce((n,p)=>n+p.price_vnd*(st.cart[p.id]||0),0)}
function cartBar(){if(channel==='wellness'||!cartQty())return '';return `<button class="cart-bar" data-action="open-cart"><span><span class="cart-count">${cartQty()}</span> Xem giỏ hàng</span><span class="cart-total">${V(cartTotal())} &nbsp; ↗</span></button>`}
function catalogHTML(){
 const cats=['Tất cả',...new Set(st.products.map(x=>x.category).filter(Boolean))];
 let filtered=st.products.filter(p=>(st.filter==='Tất cả'||p.category===st.filter)&&(p.name+' '+p.sku+' '+p.category).toLocaleLowerCase('vi-VN').includes(st.search.toLocaleLowerCase('vi-VN'))&&(!st.onlyAvailable||p.available));
 if(st.sort==='low')filtered=[...filtered].sort((a,b)=>a.price_vnd-b.price_vnd);
 if(st.sort==='high')filtered=[...filtered].sort((a,b)=>b.price_vnd-a.price_vnd);
 return `<div class="catalog-intro"><span class="eyebrow">${channel==='cafe'?'CHỌN MÓN TRONG VÀI CHẠM':channel==='mart'?'SẮM NHỮNG MÓN THIẾT YẾU': 'KHÁM PHÁ BỘ SƯU TẬP'}</span><div class="catalog-top"><div><h2>${info.section}<span class="heading-dot">.</span></h2><p>${st.products.length} ${channel==='cafe'?'món':'sản phẩm'} · Chọn yêu thích rồi kiểm tra giỏ hàng</p></div><div class="catalog-count">${filtered.length} kết quả</div></div></div>
 <div class="catalog-tools"><label class="search-wrap"><span class="visually-hidden">Tìm sản phẩm</span><input id="customer-search" type="search" autocomplete="off" placeholder="${channel==='cafe'?'Tìm món, matcha, cà phê...':'Tìm tên, loại sản phẩm...'}" value="${E(st.search)}"></label><label class="sort-wrap"><span class="visually-hidden">Sắp xếp sản phẩm</span><select id="customer-sort"><option value="default" ${st.sort==='default'?'selected':''}>Gợi ý</option><option value="low" ${st.sort==='low'?'selected':''}>Giá thấp trước</option><option value="high" ${st.sort==='high'?'selected':''}>Giá cao trước</option></select></label></div>
 <div class="category-bar" role="group" aria-label="Bộ lọc danh mục">${cats.map(cat=>`<button aria-pressed="${st.filter===cat}" class="chip ${st.filter===cat?'active':''}" data-action="category" data-value="${E(cat)}">${E(cat)}</button>`).join('')}<label class="available-toggle"><input type="checkbox" id="only-available" ${st.onlyAvailable?'checked':''}><span>Chỉ còn hàng</span></label></div>
 <div class="customer-grid">${filtered.length?filtered.map((p,i)=>`<article class="customer-product ${p.available?'':'is-sold-out'}">
 <button type="button" data-action="detail" data-value="${E(p.id)}" class="item-visual" aria-label="Xem chi tiết ${E(p.name)}"><span class="item-tag">${E(p.category)}</span><span class="item-emoji" aria-hidden="true">${icon(p)}</span><span class="item-visual-caption">Xem chi tiết ↗</span></button>
 <div class="item-info"><p class="product-overline">${channel==='cafe'?'THỨC UỐNG':channel==='online'?'BỘ SƯU TẬP':'HÀNG SẴN CÓ'}</p><h3>${E(p.name)}</h3><span class="sku">${p.available?'● Sẵn có':'○ Tạm hết hàng'} · ${E(p.sku)}</span>
 <div class="item-foot"><strong>${V(p.price_vnd)}</strong>${st.cart[p.id]?`<div class="card-qty"><button data-action="decrease" data-value="${E(p.id)}" aria-label="Bớt ${E(p.name)}">−</button><b>${st.cart[p.id]}</b><button data-action="add" data-value="${E(p.id)}" aria-label="Thêm ${E(p.name)}" ${p.available?'':'disabled'}>+</button></div>`:`<button class="add-btn" aria-label="Thêm ${E(p.name)} vào giỏ" data-action="add" data-value="${E(p.id)}" ${p.available?'':'disabled'}>+</button>`}</div></div></article>`).join(''):`<div class="catalog-empty"><span>⌕</span><h3>Chưa tìm thấy sản phẩm</h3><p>Thử từ khóa hoặc chọn danh mục khác.</p><button data-action="clear-filter">Xóa bộ lọc</button></div>`}</div>
 <p class="catalog-disclaimer">Giá và tình trạng hàng lấy từ hệ thống DEMO; giá cuối cùng được máy chủ xác minh trước khi gửi đơn.</p>`;
}
function refreshCatalog(){
 const input=document.getElementById('customer-search'),focus=document.activeElement===input,caret=focus?input.selectionStart:null;
 const content=document.getElementById('section-main');if(content)content.innerHTML=catalogHTML();
 const old=document.querySelector('.cart-bar');old?.remove();root.insertAdjacentHTML('beforeend',cartBar());
 const hdr=document.querySelector('.head-cart b');if(hdr)hdr.textContent=cartQty();
 const bottom=document.querySelector('.customer-bottom-nav button b');if(bottom)bottom.textContent=cartQty();
 if(focus){const newInput=document.getElementById('customer-search');newInput?.focus();if(caret!==null)newInput?.setSelectionRange(caret,caret)}
}
function detailHTML(product){
 const amount=st.cart[product.id]||0;
 return `<div class="customer-overlay" data-overlay><section class="customer-dialog product-dialog" role="dialog" aria-modal="true" aria-label="${E(product.name)}"><div class="dialog-head"><div><span class="eyebrow">${E(product.category)}</span><h2>${E(product.name)}</h2><p class="dialog-sub">Mã sản phẩm: ${E(product.sku)}</p></div><button class="close-modal" data-action="close" aria-label="Đóng">×</button></div>
 <div class="detail-image"><span aria-hidden="true">${icon(product)}</span><small>Hình minh họa · DEMO</small></div>
 <div class="detail-price"><div><small>Giá niêm yết</small><strong>${V(product.price_vnd)}</strong></div><span class="detail-availability">${product.available?'● Đang bán':'○ Tạm hết hàng'}</span></div>
 <p class="detail-info">${channel==='cafe'?'Chọn món và thêm vào giỏ, sau đó chọn bàn khi gửi đơn.':channel==='mart'?'Gửi yêu cầu giữ hàng thử nghiệm tại cửa hàng.':'Chọn số lượng và xác nhận thông tin giao hàng tại bước tiếp theo.'}</p>
 <button class="submit-btn" data-action="add-detail" data-value="${E(product.id)}" ${product.available&&amount<10?'':'disabled'}>${amount?'Thêm một sản phẩm nữa':'Thêm vào giỏ'} <span>+</span></button>
 <p class="fine-print">Giá và số lượng sẽ được kiểm tra lại trên máy chủ.</p></section></div>`;
}
function verifyCartQuote(form){
 const lines=Object.entries(st.cart).map(([product_id,quantity])=>({product_id,quantity}));
 api('/preview/'+channel+'/quote',{method:'POST',body:JSON.stringify({lines})})
 .then(q=>{
  if(!form?.isConnected)return;
  const price=overlay.querySelector('#server-total'),label=overlay.querySelector('#quote-status');
  if(price)price.textContent=V(q.total_vnd);
  if(label)label.textContent='Tổng tiền đã xác minh ✓';
  form.querySelector('[type=submit]').disabled=false;
 }).catch(err=>{
  if(!form?.isConnected)return;
  const label=overlay.querySelector('#quote-status');
  if(label)label.textContent='Chưa xác minh được: '+err.message;
  toast(err.message,true);
 });
}
function openCart(){if(!cartQty()){toast('Hãy chọn ít nhất một sản phẩm',true);return}
 const rows=st.products.filter(x=>st.cart[x.id]);const options=st.tables.map(t=>`<option value="${E(t.id)}">${E(t.label)}</option>`).join('');
 overlay.innerHTML=`<div class="customer-overlay" data-overlay><section role="dialog" aria-modal="true" aria-label="Giỏ hàng" class="customer-dialog"><div class="dialog-head"><div><h2>${info.cart}</h2><p class="dialog-sub">Đặt hàng thử nghiệm • Không thu tiền</p></div><button class="close-modal" data-action="close" aria-label="Đóng">×</button></div>
 <div class="cart-lines">${rows.map(p=>`<div class="cart-line"><span class="cart-line-emoji">${icon(p)}</span><div class="cart-line-main"><strong>${E(p.name)}</strong><small>${V(p.price_vnd)} / sản phẩm</small></div><div class="qty-control"><button type="button" data-action="decrease" data-value="${E(p.id)}" aria-label="Giảm số lượng">−</button><b>${st.cart[p.id]}</b><button type="button" data-action="increase" data-value="${E(p.id)}" aria-label="Tăng số lượng">+</button></div></div>`).join('')}</div><div class="total-row"><span id="quote-status">Đang kiểm tra giá trên máy chủ…</span><strong id="server-total">${V(cartTotal())}</strong></div>
 <form id="checkout-form"><div class="form-row"><label class="form-field"><span>Tên của bạn *</span><input name="customer_name" required minlength="2" maxlength="100" placeholder="Nhập tên"></label><label class="form-field"><span>Số điện thoại ${channel==='cafe'?'(tuỳ chọn)':'*'}</span><input name="phone" ${channel==='cafe'?'':'required'} maxlength="30" placeholder="09xx xxx xxx"></label></div>
 ${channel==='cafe'?`<label class="form-field"><span>Bàn đang ngồi *</span><select name="table_id" required><option value="">Chọn bàn</option>${options}</select></label>`:channel==='online'?`<label class="form-field"><span>Địa chỉ nhận hàng *</span><input name="address" required maxlength="300" placeholder="Số nhà, đường, phường, thành phố"></label>`:''}
 <label class="form-field"><span>Ghi chú (tuỳ chọn)</span><textarea name="note" maxlength="240" placeholder="Lưu ý cho cửa hàng"></textarea></label>
 <button class="submit-btn" type="submit" disabled>${info.action} ↗</button><p class="fine-print">* Tổng tiền cuối cùng được xác nhận tại backend. Không chuyển tiền, không phát sinh giao hàng thực tế.</p></form></section></div>`;
 document.body.style.overflow='hidden';overlay.querySelector('input')?.focus();verifyCartQuote(overlay.querySelector('#checkout-form'));}
function close(){overlay.innerHTML='';document.body.style.overflow=''}
function success(title,desc,code,details=''){overlay.innerHTML=`<div class="customer-overlay" data-overlay><section class="customer-dialog" role="dialog" aria-modal="true"><div class="customer-success"><div class="success-symbol">✓</div><h3>${E(title)}</h3><p>${E(desc)}</p><div class="receipt-id">Mã DEMO: <b>${E(code.slice(0,8).toUpperCase())}</b>${details?`<br><span>${E(details)}</span>`:''}</div><button class="submit-btn" data-action="close">Tiếp tục trải nghiệm</button><p class="fine-print">Anh/chị có thể xem đơn hoặc lịch hẹn trong khu quản lý DEMO.</p><a class="info-link" href="/app">Mở khu quản lý ↗</a></div></section></div>`}
async function checkout(form){const submit=form.querySelector('[type=submit]');submit.disabled=true;
 try{
 const d=Object.fromEntries(new FormData(form).entries());
 const body={request_id:st.pendingId||(st.pendingId=id()),lines:Object.entries(st.cart).map(([product_id,quantity])=>({product_id,quantity})),customer_name:d.customer_name,phone:d.phone||'',address:d.address||'',table_id:d.table_id||null,note:d.note||''};
 const res=await api('/preview/'+channel+'/checkout',{method:'POST',body:JSON.stringify(body)});
 st.cart={};st.pendingId=null;st.lastOrder=res;refreshCatalog();
 success('Đã gửi yêu cầu DEMO!',channel==='cafe'?'Phiếu bếp thử nghiệm đã được tạo. Vui lòng không thanh toán.':channel==='online'?'Đơn DEMO đã chuyển vào danh sách đóng gói. Không giao hàng thật.':'Cửa hàng đã nhận yêu cầu giữ hàng thử nghiệm.',res.id,`Tổng tiền minh hoạ: ${V(res.total_vnd)}`);
 }catch(e){toast(e.message,true)}finally{submit.disabled=false}}
function isoTomorrow(){return new Date(Date.now()+86400000).toLocaleDateString('sv-SE',{timeZone:'Asia/Ho_Chi_Minh'})}
function dateOffset(days){return new Date(Date.now()+days*86400000).toLocaleDateString('sv-SE',{timeZone:'Asia/Ho_Chi_Minh'})}
function bookingHTML(){
 const duration=Number(st.flow?.duration_minutes)||60,p=st.products,selected=p.find(x=>x.id===st.service);
 return `<div class="booking-intro"><span class="eyebrow">THƯ GIÃN · PHỤC HỒI · CHĂM SÓC</span><div class="catalog-top"><div><h2>${info.section}<span class="heading-dot">.</span></h2><p>Chọn dịch vụ, chuyên viên và giờ trống trong 21 ngày tới.</p></div><span class="catalog-count">Không thanh toán trước</span></div></div>
 <div class="booking-layout">
 <section class="booking-panel"><h3><span class="booking-step">01</span> Chọn dịch vụ</h3>
 <div class="booking-services">${p.map(x=>`<button type="button" aria-pressed="${st.service===x.id}" class="booking-service ${st.service===x.id?'selected':''}" data-action="service" data-value="${E(x.id)}"><span class="booking-service-emoji">${icon(x)}</span><span class="service-name"><strong>${E(x.name)}</strong><small>${E(x.category)} · ${duration} phút</small></span><span class="service-price">${V(x.price_vnd)}</span></button>`).join('')}</div>
 <p class="booking-note">Danh sách chuyên viên là dữ liệu minh họa. Giờ trống do máy chủ xác nhận và có thể thay đổi khi người khác đặt lịch.</p></section>
 <section class="booking-panel" id="booking-right"><h3><span class="booking-step">02</span> Chọn thời gian</h3>
 <div class="form-row"><label class="form-field"><span>Ngày hẹn</span><input id="book-date" type="date" required value="${E(st.date)}" min="${dateOffset(1)}" max="${dateOffset(21)}"></label>
 <label class="form-field"><span>Chuyên viên</span><select id="book-staff">${st.staff.map(x=>`<option value="${E(x)}" ${x===st.assignee?'selected':''}>${E(x)}</option>`).join('')}</select></label></div>
 <p class="booking-slot-title">Khung giờ còn trống <span>Giờ Việt Nam (GMT+7)</span></p>
 <div class="booking-slots" role="group" aria-label="Chọn giờ hẹn">${st.slots.map(x=>`<button type="button" aria-pressed="${st.slot===x}" data-action="slot" class="booking-slot ${x===st.slot?'selected':''}" data-value="${E(x)}">${new Date(x).toLocaleTimeString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',hour:'2-digit',minute:'2-digit'})}</button>`).join('')}</div>
 ${!st.slots.length?`<p class="slot-state" role="status">${st.bookingLoading?'Đang lấy khung giờ khả dụng…':'Hiện chưa có giờ trống cho lựa chọn này. Hãy thử ngày hoặc chuyên viên khác.'}</p>`:''}
 ${selected?`<div class="booking-summary"><span class="eyebrow">03 · XÁC NHẬN</span><strong>${E(selected.name)} · ${V(selected.price_vnd)}</strong><span>${E(st.assignee)} · ${st.slot?new Date(st.slot).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'Chưa chọn giờ'}</span></div>`:''}
 <button class="submit-btn" ${st.service&&st.slot?'':'disabled'} data-action="open-booking">Tiếp tục đặt lịch <span aria-hidden="true">↗</span></button>
 <p class="fine-print">Lịch thử nghiệm, không đặt cọc. Máy chủ sẽ kiểm tra giờ trống thêm lần nữa trước khi xác nhận.</p></section></div>`;
}
function refreshBooking(){const content=document.getElementById('section-main');if(content)content.innerHTML=bookingHTML()}
async function slots(){
 const request=++st.slotRequestId;
 st.slot=null;st.slots=[];st.bookingLoading=Boolean(st.service&&st.date);refreshBooking();
 if(!st.service||!st.date)return;
 try{
  const res=await api('/preview/wellness/slots?'+new URLSearchParams({product_id:st.service,day:st.date,assignee:st.assignee}));
  if(request===st.slotRequestId)st.slots=Array.isArray(res.slots)?res.slots:[];
 }catch(e){if(request===st.slotRequestId)toast(e.message,true)}
 finally{if(request===st.slotRequestId){st.bookingLoading=false;refreshBooking()}}
}
function bookingForm(){if(!st.service||!st.slot)return;const p=st.products.find(x=>x.id===st.service);overlay.innerHTML=`<div class="customer-overlay" data-overlay><section class="customer-dialog" role="dialog" aria-modal="true" aria-label="Xác nhận lịch hẹn"><div class="dialog-head"><div><h2>Xác nhận lịch DEMO</h2><p class="dialog-sub">${E(p.name)} • ${E(st.assignee)}</p></div><button class="close-modal" data-action="close">×</button></div><div class="receipt-id">${new Date(st.slot).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',weekday:'long',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})} · ${V(p.price_vnd)}</div><form id="booking-form"><label class="form-field"><span>Tên khách hàng *</span><input name="customer_name" required minlength="2" maxlength="100" placeholder="Họ và tên"></label><label class="form-field"><span>Số điện thoại *</span><input name="phone" required minlength="6" maxlength="30" placeholder="09xx xxx xxx"></label><label class="form-field"><span>Ghi chú (tuỳ chọn)</span><textarea name="note" maxlength="240" placeholder="Yêu cầu thêm"></textarea></label><button class="submit-btn" type="submit">Xác nhận lịch DEMO ↗</button></form><p class="fine-print">Lịch chỉ ghi vào doanh nghiệp DEMO của phiên hiện tại.</p></section></div>`;document.body.style.overflow='hidden'}
async function book(form){const btn=form.querySelector('[type=submit]');btn.disabled=true;try{const d=Object.fromEntries(new FormData(form).entries());const body={request_id:st.pendingId||(st.pendingId=id()),product_id:st.service,customer_name:d.customer_name,phone:d.phone,assignee:st.assignee,start_at:st.slot,note:d.note||''};const res=await api('/preview/wellness/appointments',{method:'POST',body:JSON.stringify(body)});st.pendingId=null;success('Đã đặt lịch DEMO!', 'Lịch thử nghiệm đã được ghi vào quản lý Spa/Wellness. Không phát sinh đặt cọc.',res.id,st.assignee);await slots();}catch(e){toast(e.message,true)}finally{btn.disabled=false}}
async function start(){try{const config=await api('/config');if(!config.demo_enabled){blocked('Trang xem trước theo ngành đang chỉ mở trên môi trường DEMO. Không có gian hàng công khai và chưa chấp nhận đặt hàng thật.');return}
 let me;try{me=await api('/auth/me')}catch(e){if(e.status!==401)throw e;}
 if(!me){me=await api('/auth/demo',{method:'POST'});}
 if(!me.demo){blocked('Hãy sử dụng phiên DEMO để thử trang mua hàng. Dữ liệu thật của doanh nghiệp không được công bố.');return}
 st.csrf=me.csrf_token;
 const data=await api('/preview/'+channel);st.business=data.business;st.products=data.products;st.tables=data.tables;st.staff=data.staff||[];st.flow=data.flow||null;st.date=isoTomorrow();document.body.dataset.channel=channel;st.service=st.products[0]?.id||null;
 layout();if(channel==='wellness')await slots();
 }catch(e){blocked(e.message||'Không thể kết nối với bản DEMO')}}
root.addEventListener('input',e=>{if(e.target.id==='customer-search'){st.search=e.target.value;refreshCatalog()}});
root.addEventListener('change',e=>{if(e.target.id==='customer-sort'){st.sort=e.target.value;refreshCatalog()}if(e.target.id==='only-available'){st.onlyAvailable=e.target.checked;refreshCatalog()}if(e.target.id==='book-date'){st.date=e.target.value;st.pendingId=null;slots()}if(e.target.id==='book-staff'){st.assignee=e.target.value;st.pendingId=null;slots()}});
document.addEventListener('click',e=>{const el=e.target.closest('[data-action]');if(!el){if(e.target.matches('[data-overlay]'))close();return}e.preventDefault();const {action,value}=el.dataset;
 if(action==='close'){close();return}if(action==='book-scroll'){document.getElementById('booking-right')?.scrollIntoView({behavior:'smooth'});return}
 if(action==='category'){st.filter=value;refreshCatalog();return}if(action==='clear-filter'){st.filter='Tất cả';st.search='';st.onlyAvailable=false;st.sort='default';refreshCatalog();return}if(action==='detail'){const p=st.products.find(x=>x.id===value);if(p){overlay.innerHTML=detailHTML(p);document.body.style.overflow='hidden';overlay.querySelector('.close-modal')?.focus()}return}if(action==='add-detail'){if(st.cart[value]>=10)return;st.cart[value]=(st.cart[value]||0)+1;st.pendingId=null;close();refreshCatalog();toast('Đã thêm vào giỏ hàng');return}if(action==='add'||action==='increase'){if(!st.products.some(x=>x.id===value&&x.available))return;st.cart[value]=Math.min(10,(st.cart[value]||0)+1);st.pendingId=null;refreshCatalog();if(action==='increase')openCart();else toast('Đã thêm vào giỏ hàng');return}
 if(action==='decrease'){if(st.cart[value]){st.cart[value]--;if(!st.cart[value])delete st.cart[value];st.pendingId=null;refreshCatalog();if(cartQty())openCart();else close()}return}
 if(action==='open-cart'){openCart();return}if(action==='service'){st.service=value;st.pendingId=null;slots();return}if(action==='slot'){st.slot=value;const content=document.getElementById('section-main');if(content)content.innerHTML=bookingHTML();return}if(action==='open-booking'){bookingForm();return}
});
document.addEventListener('submit',e=>{if(e.target.id==='checkout-form'){e.preventDefault();checkout(e.target)}if(e.target.id==='booking-form'){e.preventDefault();book(e.target)}});
document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
start();
})();