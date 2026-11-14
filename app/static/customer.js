(()=>{
'use strict';
const root=document.getElementById('customer-root');
const overlay=document.getElementById('customer-modal');
const toastRoot=document.getElementById('customer-toast');
const channel=location.pathname.startsWith('/menu/')?'cafe':location.pathname.startsWith('/booking/')?'wellness':location.pathname.endsWith('/mart')?'mart':'online';
const kinds={
 cafe:{industry:'fnb',label:'EZ THING CAFE',hero:'Cà phê ngon hơn,\ncuộc sống nhẹ hơn.',emoji:'☕',sub:'Cà phê đặc sắc, đồ uống sáng tạo và những phút giây thư giãn mỗi ngày. Chọn món nhanh, dễ dàng trong vài chạm.',section:'Khám phá thực đơn của chúng tôi',cart:'Gọi món DEMO',action:'Gửi món đến quán'},
 mart:{industry:'retail',label:'EZ THING MART',hero:'Mua sắm dễ dàng\ncho cuộc sống hiện đại.',emoji:'🛍️',sub:'Hàng chọn lọc mỗi ngày, từ những món đồ thiết yếu đến phụ kiện phong cách — tất cả trong một nơi.',section:'Sản phẩm dành cho bạn',cart:'Giữ hàng DEMO',action:'Gửi yêu cầu giữ hàng'},
 online:{industry:'online',label:'EZ THING',hero:'Online Shop',emoji:'📦',sub:'Mua sắm thông minh, trải nghiệm đơn giản. Đồ bạn cần — tất cả ở một nơi.',section:'Sản phẩm nổi bật',cart:'Đơn hàng DEMO',action:'Gửi đơn đặt hàng'},
 wellness:{industry:'services',label:'EZ THING SPA & WELLNESS',hero:'Thư giãn trọn vẹn,\ntái tạo năng lượng.',emoji:'🌿',sub:'Không gian chăm sóc sức khỏe và sắc đẹp hiện đại, giúp bạn cân bằng thân – tâm – trí.',section:'Đặt lịch trải nghiệm',cart:'Đặt lịch DEMO',action:'Xác nhận lịch DEMO'}
};
const navMap={
 cafe:[['Trang chủ','#top'],['Thực đơn','#section-main'],['Ưu đãi','#offers'],['Về chúng tôi','#about'],['Đặt bàn','/reserve/cafe']],
 mart:[['Sản phẩm','#section-main'],['Danh mục','#featured'],['Khuyến mãi','#offers'],['Cửa hàng','#section-main'],['Về EZ Thing','#about']],
 online:[['Online Shop','#top'],['Danh mục','#featured'],['Ưu đãi','#offers'],['Hỗ trợ','#about']],
 wellness:[['Spa & Wellness','#top'],['Dịch vụ','#featured'],['Đặt lịch','#booking-right'],['Ưu đãi','#offers'],['Về chúng tôi','#about']]
};
const images={
 cafe:{'matcha':'photo-1515823064-d6e0c04616a7','cà phê':'photo-1461023058943-07fcbe16d735','cold brew':'photo-1517701604599-bb29b565090c','trà đào':'photo-1556679343-c7306c1976bc','trà vải':'photo-1544145945-f90425340c7e','nước ép':'photo-1600271886742-f049cd451bba'},
 mart:{'bình giữ':'photo-1602143407151-7111542de6e8','túi':'photo-1548036328-c9fa89d128fa','sổ':'photo-1531346878377-a5be20888e57'},
 online:{'áo':'photo-1521572163474-6864f9cf17ab','nón':'photo-1588850561407-ed78c282e89b','túi':'photo-1547949003-9792a18a2601'},
 wellness:{'xông':'photo-1540555700478-4be289fbecef','massage':'photo-1544161515-4ab6ce6db874','chăm sóc da':'photo-1570172619644-dfd03ed5d881'}
};
const webphoto=(id,w=960)=>'https://images.unsplash.com/'+id+'?auto=format&fit=crop&w='+w+'&q=84';
function productPhoto(p){const name=(p.name||'').toLowerCase();const pair=Object.entries(images[channel]).find(([match])=>name.includes(match));return webphoto(pair?.[1]||'photo-1498049794561-7780e7231661',760)}
function svgIcon(key){
 const paths={
 cup:'<path d="M5 8h13v9a5 5 0 0 1-5 5h-3a5 5 0 0 1-5-5z"/><path d="M18 10h2a3 3 0 0 1 0 6h-2"/>',
 leaf:'<path d="M20 4C10 4 4 10 4 19c8 2 16-5 16-15Z"/><path d="M5 20c3-5 7-9 12-12"/>',
 bolt:'<path d="m13 2-9 12h7l-1 8 10-13h-7z"/>',
 heart:'<path d="M20.8 5.7a5.3 5.3 0 0 0-7.5 0L12 7l-1.3-1.3a5.3 5.3 0 1 0-7.5 7.5L12 22l8.8-8.8a5.3 5.3 0 0 0 0-7.5z"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 10h18"/>',
 flower:'<path d="M12 12c-5-7-2-10 0-10s5 3 0 10Zm0 0c7-5 10-2 10 0s-3 5-10 0Zm0 0c5 7 2 10 0 10s-5-3 0-10Zm0 0c-7 5-10 2-10 0s3-5 10 0Z"/>',
 person:'<circle cx="12" cy="8" r="4"/><path d="M4 22v-2a8 8 0 0 1 16 0v2"/>',
 shield:'<path d="M12 2 4 6v6c0 5 3 8 8 10 5-2 8-5 8-10V6z"/><path d="m8 12 3 3 5-6"/>',
 basket:'<path d="M4 10h16l-2 11H6zM8 10l4-7 4 7"/>',
 home:'<path d="m3 11 9-8 9 8v10H3z"/><path d="M9 21v-7h6v7"/>',
 tech:'<rect x="4" y="4" width="16" height="13" rx="1"/><path d="M2 21h20M9 17v4m6-4v4"/>',
 shirt:'<path d="M8 3 3 7v6l4-2v10h10V11l4 2V7l-5-4-4 3z"/>',
 gift:'<rect x="3" y="9" width="18" height="13"/><path d="M12 9v13M3 13h18"/><path d="M12 9c-8-1-8-8-4-8 3 0 4 5 4 8Zm0 0c8-1 8-8 4-8-3 0-4 5-4 8Z"/>',
 tag:'<path d="M3 3h9l9 9-9 9-9-9z"/><circle cx="8" cy="8" r="1"/>',
 truck:'<path d="M2 6h13v12H2zM15 10h4l3 3v5h-7"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
 box:'<path d="m3 7 9-4 9 4v10l-9 4-9-4zM3 7l9 5 9-5M12 12v9"/>',
 headphones:'<path d="M3 13v-1a9 9 0 0 1 18 0v1"/><rect x="2" y="13" width="5" height="8" rx="2"/><rect x="17" y="13" width="5" height="8" rx="2"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/>',
 bag:'<path d="M4 8h16l-1 13H5z"/><path d="M8 9V7a4 4 0 0 1 8 0v2"/>',
 menu:'<path d="M4 7h16M4 12h16M4 17h16"/>'
 };
 return '<svg aria-hidden="true" viewBox="0 0 24 24">'+(paths[key]||paths.box)+'</svg>';
}
const info=kinds[channel];
const st={csrf:'',business:null,products:[],tables:[],staff:[],cart:{},filter:channel==='cafe'?'Nổi bật':'Tất cả',search:'',pendingId:null,
       service:null,assignee:'Linh',date:'',slots:[],slot:null,bookingLoading:false,lastOrder:null};
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const V=n=>new Intl.NumberFormat(window.EZI18N?.locale()||'vi-VN').format(Number(n)||0)+'đ';
const icon=p=>{const s=(p.sku+' '+p.name).toLowerCase(); if(/matcha/.test(s))return '🍵';if(/cafe|cà phê|brew/.test(s))return '☕';if(/trà đào|đào/.test(s))return '🍑';if(/cam|nước ép/.test(s))return '🍊';if(/trà vải/.test(s))return '🍹';if(/bình giữ/.test(s))return '🥤';if(/tote|túi/.test(s))return '👜';if(/sổ/.test(s))return '📓';if(/áo/.test(s))return '👕';if(/nón/.test(s))return '🧢';if(/xông/.test(s))return '♨️';if(/massage/.test(s))return '💆';if(/da/.test(s))return '🌸';return info.emoji};
const id=()=>('d'+(globalThis.crypto?.randomUUID?.()||Math.random().toString(36).slice(2)+Date.now()).replace(/[^\w-]/g,''));
async function api(path,options={}){
 const r=await fetch('/api'+path,{credentials:'same-origin',cache:'no-store',...options,
  headers:{'Content-Type':'application/json','Accept-Language':window.EZI18N?.language()||'vi',...(st.csrf&&options.method&&options.method!=='GET'?{'x-csrf-token':st.csrf}:{}),...(options.headers||{})}});
 let body;try{body=await r.json()}catch{body={detail:'Không nhận được phản hồi từ máy chủ'}};
 if(!r.ok){const e=new Error(typeof body.detail==='string'?body.detail:'Yêu cầu thất bại');e.status=r.status;throw e;}return body;
}
function toast(message,bad=false){toastRoot.textContent=message;toastRoot.className='customer-toast'+(bad?' bad':'');setTimeout(()=>{toastRoot.textContent='';toastRoot.className='';},3500)}
function blocked(message){root.innerHTML=`<header class="customer-header"><a class="customer-brand" href="/"><span class="mark">e.</span> EZ <strong>Thing</strong></a><a class="info-link" href="/app">Quản lý ↗</a></header><main class="closed-message"><span style="font-size:52px">🌿</span><h2>Trải nghiệm hiện chưa mở</h2><p>${E(message)}</p><a class="info-link" href="/">← Về trang chủ</a></main>`}

function header(){
 const brand=channel==='cafe'?'Cafe':channel==='mart'?'Mart':channel==='online'?'Online Shop':'';
 const menu=navMap[channel].map(([name,href])=>`<a href="${href}">${E(name)}</a>`).join('');
 return `<div class="visitor-banner">TRẢI NGHIỆM DEMO • KHÔNG THANH TOÁN HOẶC GIAO HÀNG THẬT</div>
 <header class="customer-header" id="top">
   <a class="customer-brand" href="/" aria-label="Trang chủ EZ Thing">${st.business?.branding?E(st.business.branding.display_name):`EZ Thing ${brand?`<strong>${brand}</strong>`:""}`}</a>
   <nav class="customer-primary-nav" id="customer-primary-nav" aria-label="Danh mục trang">${menu}</nav>
   <div class="customer-h-actions">
     ${channel==='cafe'?'<a href="/reserve/cafe" class="book-now-link">Đặt bàn</a>':''}
     ${channel!=='wellness'?`<button type="button" data-action="search" aria-label="Tìm sản phẩm">${svgIcon('search')}</button><button type="button" class="cart-toggle" data-action="open-cart" aria-label="Mở giỏ hàng">${svgIcon('bag')}<span class="cart-count-top">${cartQty()}</span></button>`:`<button type="button" class="book-now-link" data-action="book-scroll">Đặt lịch ngay</button>`}
     <button type="button" class="menu-toggle" data-action="toggle-menu" aria-label="Mở menu điều hướng" aria-controls="customer-primary-nav" aria-expanded="false">${svgIcon('menu')}</button>
   </div>
 </header>`;
}
function hero(){
 const custom=st.business?.branding;
 const headline=custom?.hero_title||custom?.display_name||info.hero;
 const label=custom?.display_name||info.label;
 const subtitle=custom?.description||info.sub;
 return `<section class="merchant-hero kind-${info.industry}" aria-label="${E(label)}">
  <div class="merchant-copy">
   <span class="merchant-tag">${E(label)}</span>
   <h1>${E(headline).replace(/\n/g,'<br>')}</h1>
   <p>${E(subtitle)}</p>
   <div class="hero-actions-shop">
    <button class="hero-cta" type="button" data-action="${channel==='wellness'?'book-scroll':'shop-scroll'}">${channel==='wellness'?'Đặt lịch ngay':channel==='cafe'?'Đặt ngay':'Mua sắm ngay'} <span aria-hidden="true">→</span></button>
    <a class="hero-cta secondary" href="#${channel==='wellness'?'featured':channel==='cafe'?'section-main':'featured'}">${channel==='wellness'?'Khám phá dịch vụ':channel==='cafe'?'Xem thực đơn':'Khám phá danh mục'}</a>
   </div>
  </div>
 </section>`;
}
function benefitsHTML(){
 const sets={
  cafe:[['cup','Đồ uống chất lượng','Cà phê chọn lọc, hương vị tinh tế'],['leaf','Nguyên liệu tươi mới','Thực đơn được cập nhật dễ dàng'],['bolt','Đặt hàng nhanh','Chỉ vài thao tác chọn món'],['heart','Trải nghiệm thân thiện','Giao diện dễ dùng trên điện thoại']],
  mart:[['basket','Chọn hàng dễ dàng','Xem nhanh danh sách sản phẩm'],['home','Mua sắm tiện lợi','Mọi thứ trong một nơi'],['shield','Thông tin rõ ràng','Giá được xác nhận từ hệ thống'],['tag','Duyệt sản phẩm dễ dàng','Tìm món bạn yêu thích']],
  online:[['truck','Thông tin giao hàng','Nhập địa chỉ khi tạo đơn DEMO'],['box','Đặt hàng dễ dàng','Giỏ hàng trong vài chạm'],['shield','Minh bạch giá bán','Tổng tiền do backend xác nhận'],['headphones','Trợ giúp trải nghiệm','Không cần tải thêm ứng dụng']],
  wellness:[['calendar','Đặt lịch dễ dàng','Chọn dịch vụ và thời gian phù hợp'],['flower','Không gian thư giãn','Giao diện tinh tế, nhẹ nhàng'],['leaf','Chăm sóc toàn diện','Duyệt liệu trình theo nhu cầu'],['person','Lịch chuyên viên','Giờ trống được kiểm tra ở backend']]
 };
 return `<section class="shop-benefits" id="why" aria-label="Lợi ích">${sets[channel].map(([i,h,d])=>`<div class="benefit"><span class="benefit-icon">${svgIcon(i)}</span><div><strong>${h}</strong><small>${d}</small></div></div>`).join('')}</section>`;
}
function categoryPromo(){
 if(channel==='cafe')return '';
 const groups={
 mart:[
  ['Thực phẩm tươi ngon','Đa dạng lựa chọn cho mỗi ngày.','photo-1542838132-92c53300491e'],
  ['Đồ gia dụng tiện ích','Gọn gàng hơn, thoải mái hơn.','photo-1618221195710-dd6b41faaea6'],
  ['Điện tử & Phụ kiện','Công nghệ thiết thực mỗi ngày.','photo-1498049794561-7780e7231661']],
 online:[
  ['Điện tử & Công nghệ','','photo-1498049794561-7780e7231661'],
  ['Gia dụng & Đời sống','','photo-1493663284031-b7e3aefcae8e'],
  ['Thời trang & Phong cách','','photo-1547949003-9792a18a2601'],
  ['Làm đẹp & Chăm sóc','','photo-1608248543803-ba4f8c70ae0b'],
  ['Thể thao & Sức khỏe','','photo-1517836357463-d25dfeac3438']],
 wellness:[
  ['Massage trị liệu','Giảm căng thẳng, phục hồi cơ thể','photo-1544161515-4ab6ce6db874'],
  ['Chăm sóc da mặt','Làm sạch, nuôi dưỡng và tái tạo','photo-1570172619644-dfd03ed5d881'],
  ['Chăm sóc cơ thể','Thư giãn và phục hồi năng lượng','photo-1512290923902-8a9f81dc236c'],
  ['Trải nghiệm trọn gói','Khám phá dịch vụ và đặt lịch','photo-1540555700478-4be289fbecef']]
 };
 const names={mart:['DANH MỤC NỔI BẬT','Chọn những gì bạn yêu thích.','Khám phá các nhóm hàng minh họa trước khi chọn sản phẩm DEMO.'],online:['DANH MỤC','Danh mục nổi bật','Khám phá ý tưởng mua sắm, sau đó xem những sản phẩm DEMO hiện có.'],wellness:['DỊCH VỤ CỦA CHÚNG TÔI','Dịch vụ nổi bật','Những trải nghiệm thư giãn để bạn khám phá.']};
 const [tag,title,desc]=names[channel];
 const strip=channel==='mart'?`<div class="category-strip" aria-label="Gợi ý danh mục">${[['basket','Thực phẩm'],['leaf','Chăm sóc cá nhân'],['home','Đồ gia dụng'],['tech','Điện tử & Phụ kiện'],['shirt','Thời trang'],['gift','Quà tặng'],['tag','Khuyến mãi']].map(([i,n])=>`<a href="#section-main"><span class="category-icon">${svgIcon(i)}</span><span>${n}</span></a>`).join('')}</div>`:'';
 const cols=channel==='online'?' cols-five':'';
 const tiles=groups[channel].map(([name,desc,photo])=>`<a href="#${channel==='wellness'?'booking-right':'section-main'}" class="showcase-tile"><img src="${webphoto(photo,800)}" alt="${E(name)} — hình minh họa" loading="lazy" decoding="async"><div class="showcase-tile-copy"><h3>${E(name)}</h3><p>${E(desc)}</p><span class="tile-action" aria-hidden="true">${channel==='wellness'?'→':channel==='online'?'→':'Khám phá →'}</span></div></a>`).join('');
 const promo=channel==='online'?`<section class="promo-feature" aria-label="Khám phá sản phẩm DEMO"><img src="${webphoto('photo-1496181133206-80ce9b88a853',1500)}" loading="lazy" alt="Laptop trên bàn làm việc"><div class="promo-copy"><span>SẢN PHẨM NỔI BẬT</span><h3>Hiệu năng mạnh mẽ cho công việc và sáng tạo.</h3><p>Khám phá trải nghiệm mua sắm bằng các sản phẩm mẫu đang có trong hệ thống.</p><a href="#section-main">Khám phá ngay →</a></div></section>`:'';
 return `${strip}<section id="featured" class="showcase-categories ${channel==='wellness'?'showcase-services':''}"><div class="showcase-container"><div class="section-overline">${tag}</div><h2 class="showcase-title">${title}</h2><p class="showcase-lead">${desc}</p><div class="showcase-grid${cols}">${tiles}</div>${promo}</div></section>`;
}
function layout(){
 document.body.dataset.storefront=channel;
 root.innerHTML=header()+`<main class="customer-main">${hero()}${benefitsHTML()}${categoryPromo()}<section class="merchant-content" id="section-main">${channel==='wellness'?bookingHTML():catalogHTML()}</section><section id="offers" class="demo-explainer">Đây là bản trải nghiệm giao diện. Hiện chưa có chương trình khuyến mãi hay giao dịch thanh toán thực tế. Sản phẩm, giá và lịch hẹn DEMO lấy từ hệ thống thử nghiệm riêng.</section></main><footer id="about" class="flow-footer">Giao diện trải nghiệm được xây dựng bởi <a href="/">EZ Thing</a> · Chỉ sử dụng dữ liệu DEMO · Không xử lý đơn hàng thật. <a href="/app">Khu quản lý cửa hàng</a></footer>`+cartBar();
 const custom=st.business?.branding;
 if(custom){
  const heroEl=root.querySelector('.merchant-hero');
  if(heroEl){heroEl.classList.add('custom-branded');heroEl.style.setProperty('--customer-banner','url("'+custom.banner_image+'")');heroEl.style.setProperty('--customer-accent',custom.accent_color||'#147D64')}
 }
}

function cartQty(){return Object.values(st.cart).reduce((n,x)=>n+x,0)}
function cartTotal(){return st.products.reduce((n,p)=>n+p.price_vnd*(st.cart[p.id]||0),0)}
function cartBar(){if(channel==='wellness'||!cartQty())return '';return `<button class="cart-bar" data-action="open-cart"><span><span class="cart-count">${cartQty()}</span> Xem giỏ hàng</span><span class="cart-total">${V(cartTotal())} &nbsp; ↗</span></button>`}

function catalogHTML(){
 const cats=channel==='cafe'?['Nổi bật','Cà phê','Trà & nước ép','Tất cả']:['Tất cả',...new Set(st.products.map(x=>x.category).filter(Boolean))];
 const search=st.search.toLocaleLowerCase('vi');
 const selected=st.products.filter(p=>{
  const n=p.name.toLocaleLowerCase('vi');
  if(!(n+' '+p.sku.toLocaleLowerCase('vi')).includes(search))return false;
  if(channel==='cafe'){
   if(st.filter==='Cà phê')return /cà phê|cafe|cold brew/i.test(n);
   if(st.filter==='Trà & nước ép')return /trà|nước ép|cam/i.test(n);
   return true;
  }
  return st.filter==='Tất cả'||p.category===st.filter;
 });
 const filtered=channel==='cafe'&&st.filter==='Nổi bật'?selected.slice(0,4):selected;
 return `<div class="catalog-top"><div><h2>${E(info.section)}</h2><p>${selected.length} ${channel==='wellness'?'dịch vụ':'sản phẩm'} từ dữ liệu DEMO • Giá do máy chủ cung cấp</p></div><label class="search-wrap"><input id="customer-search" aria-label="Tìm sản phẩm" placeholder="Tìm ${channel==='cafe'?'món yêu thích':'sản phẩm'}..." value="${E(st.search)}"></label></div>
 <div class="category-bar">${cats.map(cat=>`<button type="button" class="chip ${st.filter===cat?'active':''}" data-action="category" data-value="${E(cat)}">${E(cat)}</button>`).join('')}</div>
 <div class="customer-grid">${filtered.length?filtered.map(p=>`<article class="customer-product"><div class="item-visual"><span class="item-emoji" aria-hidden="true">${icon(p)}</span><img class="item-photo" alt="${E(p.name)} — hình minh họa" loading="lazy" decoding="async" src="${productPhoto(p)}"><span class="item-tag">${E(p.category)}</span></div><div class="item-info"><h3>${E(p.name)}</h3><span class="sku">${E(p.sku)} · ${p.available?'Đang có hàng':'Hết hàng'}</span><div class="item-foot"><strong>${V(p.price_vnd)}</strong><button type="button" class="add-btn" aria-label="Thêm ${E(p.name)} vào giỏ hàng" data-action="add" data-value="${E(p.id)}" ${p.available?'':'disabled'}>+</button></div></div></article>`).join(''):`<div class="catalog-empty">Chưa tìm thấy sản phẩm phù hợp.</div>`}</div>`;
}
function refreshCatalog(){
 const content=document.getElementById('section-main');
 if(content)content.innerHTML=catalogHTML();
 document.querySelector('.cart-bar')?.remove();
 root.insertAdjacentHTML('beforeend',cartBar());
 const hdr=document.querySelector('.cart-count-top');
 if(hdr)hdr.textContent=String(cartQty());
}

function openCart(){if(!cartQty()){toast('Hãy chọn ít nhất một sản phẩm',true);return}
 const rows=st.products.filter(x=>st.cart[x.id]);const options=st.tables.map(t=>`<option value="${E(t.id)}">${E(t.label)}</option>`).join('');
 overlay.innerHTML=`<div class="customer-overlay" data-overlay><section role="dialog" aria-modal="true" aria-label="Giỏ hàng" class="customer-dialog"><div class="dialog-head"><div><h2>${info.cart}</h2><p class="dialog-sub">Đặt hàng thử nghiệm • Không thu tiền</p></div><button class="close-modal" data-action="close" aria-label="Đóng">×</button></div>
 <div class="cart-lines">${rows.map(p=>`<div class="cart-line"><span class="cart-line-emoji">${icon(p)}</span><div class="cart-line-main"><strong>${E(p.name)}</strong><small>${V(p.price_vnd)} / sản phẩm</small></div><div class="qty-control"><button type="button" data-action="decrease" data-value="${E(p.id)}" aria-label="Giảm số lượng">−</button><b>${st.cart[p.id]}</b><button type="button" data-action="increase" data-value="${E(p.id)}" aria-label="Tăng số lượng">+</button></div></div>`).join('')}</div><div class="total-row"><span>Tạm tính từ máy chủ*</span><strong>${V(cartTotal())}</strong></div>
 <form id="checkout-form"><div class="form-row"><label class="form-field"><span>Tên của bạn *</span><input name="customer_name" required minlength="2" maxlength="100" placeholder="Nhập tên"></label><label class="form-field"><span>Số điện thoại ${channel==='cafe'?'(tuỳ chọn)':'*'}</span><input name="phone" ${channel==='cafe'?'':'required'} maxlength="30" placeholder="09xx xxx xxx"></label></div>
 ${channel==='cafe'?`<label class="form-field"><span>Bàn đang ngồi *</span><select name="table_id" required><option value="">Chọn bàn</option>${options}</select></label>`:channel==='online'?`<label class="form-field"><span>Địa chỉ nhận hàng *</span><input name="address" required maxlength="300" placeholder="Số nhà, đường, phường, thành phố"></label>`:''}
 <label class="form-field"><span>Ghi chú (tuỳ chọn)</span><textarea name="note" maxlength="240" placeholder="Lưu ý cho cửa hàng"></textarea></label>
 <button class="submit-btn" type="submit">${info.action} ↗</button><p class="fine-print">* Tổng tiền cuối cùng được xác nhận tại backend. Không chuyển tiền, không phát sinh giao hàng thực tế.</p></form></section></div>`;
 document.body.style.overflow='hidden';overlay.querySelector('input')?.focus();}
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
function bookingHTML(){const p=st.products;return `<div class="catalog-top"><div><h2>${info.section}</h2><p>Chọn dịch vụ và giờ hẹn • Không yêu cầu thanh toán</p></div><span class="chip">Lịch hẹn DEMO</span></div><div class="booking-layout"><section class="booking-panel"><h3>01. Lựa chọn dịch vụ</h3><div class="booking-services">${p.map(x=>`<button class="booking-service ${st.service===x.id?'selected':''}" data-action="service" data-value="${E(x.id)}"><span class="booking-service-emoji">${icon(x)}</span><span style="flex:1"><strong>${E(x.name)}</strong><small>Thời lượng minh họa 60 phút</small></span><span class="service-price">${V(x.price_vnd)}</span></button>`).join('')}</div><p class="booking-note">Các chuyên viên và khung giờ chỉ là dữ liệu thử nghiệm. Hệ thống kiểm tra trùng lịch ở backend.</p></section><section class="booking-panel" id="booking-right"><h3>02. Chọn ngày và thời gian</h3><div class="form-row"><label class="form-field"><span>Ngày hẹn</span><input id="book-date" type="date" value="${E(st.date)}" min="${isoTomorrow()}"></label><label class="form-field"><span>Chuyên viên</span><select id="book-staff">${st.staff.map(x=>`<option value="${E(x)}" ${x===st.assignee?'selected':''}>${E(x)}</option>`).join('')}</select></label></div><div class="booking-slots">${st.slots.map(x=>`<button data-action="slot" class="booking-slot ${x===st.slot?'selected':''}" data-value="${E(x)}">${new Date(x).toLocaleTimeString(window.EZI18N?.locale()||'vi-VN',{timeZone:'Asia/Ho_Chi_Minh',hour:'2-digit',minute:'2-digit'})}</button>`).join('')}</div>${!st.slots.length?`<p class="slot-state">${st.bookingLoading?'Đang kiểm tra lịch trống...':'Chọn dịch vụ, ngày và chuyên viên để xem giờ trống.'}</p>`:''}<button class="submit-btn" ${st.service&&st.slot?'':'disabled'} data-action="open-booking">Tiếp tục đặt lịch ↗</button><p class="fine-print">Không đặt cọc hoặc thu tiền trong bản DEMO.</p></section></div>`}
async function slots(){if(!st.service||!st.date)return;st.slot=null;st.slots=[];st.bookingLoading=true;layout();try{const res=await api('/preview/wellness/slots?'+new URLSearchParams({product_id:st.service,day:st.date,assignee:st.assignee}));st.slots=res.slots||[];}catch(e){toast(e.message,true)}finally{st.bookingLoading=false;layout()}}
function bookingForm(){if(!st.service||!st.slot)return;const p=st.products.find(x=>x.id===st.service);overlay.innerHTML=`<div class="customer-overlay" data-overlay><section class="customer-dialog" role="dialog" aria-modal="true" aria-label="Xác nhận lịch hẹn"><div class="dialog-head"><div><h2>Xác nhận lịch DEMO</h2><p class="dialog-sub">${E(p.name)} • ${E(st.assignee)}</p></div><button class="close-modal" data-action="close">×</button></div><div class="receipt-id">${new Date(st.slot).toLocaleString(window.EZI18N?.locale()||'vi-VN',{timeZone:'Asia/Ho_Chi_Minh',weekday:'long',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'})} · ${V(p.price_vnd)}</div><form id="booking-form"><label class="form-field"><span>Tên khách hàng *</span><input name="customer_name" required minlength="2" maxlength="100" placeholder="Họ và tên"></label><label class="form-field"><span>Số điện thoại *</span><input name="phone" required minlength="6" maxlength="30" placeholder="09xx xxx xxx"></label><label class="form-field"><span>Ghi chú (tuỳ chọn)</span><textarea name="note" maxlength="240" placeholder="Yêu cầu thêm"></textarea></label><button class="submit-btn" type="submit">Xác nhận lịch DEMO ↗</button></form><p class="fine-print">Lịch chỉ ghi vào doanh nghiệp DEMO của phiên hiện tại.</p></section></div>`;document.body.style.overflow='hidden'}
async function book(form){const btn=form.querySelector('[type=submit]');btn.disabled=true;try{const d=Object.fromEntries(new FormData(form).entries());const body={request_id:st.pendingId||(st.pendingId=id()),product_id:st.service,customer_name:d.customer_name,phone:d.phone,assignee:st.assignee,start_at:st.slot,note:d.note||''};const res=await api('/preview/wellness/appointments',{method:'POST',body:JSON.stringify(body)});st.pendingId=null;success('Đã đặt lịch DEMO!', 'Lịch thử nghiệm đã được ghi vào quản lý Spa/Wellness. Không phát sinh đặt cọc.',res.id,st.assignee);await slots();}catch(e){toast(e.message,true)}finally{btn.disabled=false}}
async function start(){try{const config=await api('/config');if(!config.demo_enabled){blocked('Trang xem trước theo ngành đang chỉ mở trên môi trường DEMO. Không có gian hàng công khai và chưa chấp nhận đặt hàng thật.');return}
 let me;try{me=await api('/auth/me')}catch(e){if(e.status!==401)throw e;}
 if(!me){me=await api('/auth/demo',{method:'POST'});}
 if(!me.demo){blocked('Hãy sử dụng phiên DEMO để thử trang mua hàng. Dữ liệu thật của doanh nghiệp không được công bố.');return}
 st.csrf=me.csrf_token;
 const data=await api('/preview/'+channel);st.business=data.business;st.products=data.products;st.tables=data.tables;st.staff=data.staff||[];st.date=isoTomorrow();st.service=st.products[0]?.id||null;
 layout();if(channel==='wellness')await slots();
 }catch(e){blocked(e.message||'Không thể kết nối với bản DEMO')}}
root.addEventListener('input',e=>{if(e.target.id==='customer-search'){st.search=e.target.value;const caret=e.target.selectionStart;refreshCatalog();const el=document.getElementById('customer-search');el?.focus();el?.setSelectionRange(caret,caret)}});
root.addEventListener('change',e=>{if(e.target.id==='book-date'){st.date=e.target.value;st.pendingId=null;slots()}if(e.target.id==='book-staff'){st.assignee=e.target.value;st.pendingId=null;slots()}});
document.addEventListener('click',e=>{const el=e.target.closest('[data-action]');if(!el){if(e.target.matches('[data-overlay]'))close();return}e.preventDefault();const {action,value}=el.dataset;
 if(action==='close'){close();return}if(action==='toggle-menu'){const h=document.querySelector('.customer-header');setMobileMenuOpen(!h?.classList.contains('mobile-open'));return}if(action==='search'){document.getElementById('section-main')?.scrollIntoView({behavior:'smooth'});document.getElementById('customer-search')?.focus({preventScroll:true});return}if(action==='shop-scroll'){document.getElementById('section-main')?.scrollIntoView({behavior:'smooth'});return}if(action==='book-scroll'){document.getElementById('booking-right')?.scrollIntoView({behavior:'smooth'});return}
 if(action==='category'){st.filter=value;refreshCatalog();return}if(action==='add'||action==='increase'){if(!st.products.some(x=>x.id===value&&x.available))return;st.cart[value]=Math.min(10,(st.cart[value]||0)+1);st.pendingId=null;refreshCatalog();if(action==='increase')openCart();else toast('Đã thêm vào giỏ hàng');return}
 if(action==='decrease'){if(st.cart[value]){st.cart[value]--;if(!st.cart[value])delete st.cart[value];st.pendingId=null;refreshCatalog();if(cartQty())openCart();else close()}return}
 if(action==='open-cart'){openCart();return}if(action==='service'){st.service=value;st.pendingId=null;slots();return}if(action==='slot'){st.slot=value;const y=window.scrollY;layout();window.scrollTo(0,y);return}if(action==='open-booking'){bookingForm();return}
});
document.addEventListener('submit',e=>{if(e.target.id==='checkout-form'){e.preventDefault();checkout(e.target)}if(e.target.id==='booking-form'){e.preventDefault();book(e.target)}});
function setMobileMenuOpen(open){
 const header=document.querySelector('.customer-header');
 if(!header)return;
 header.classList.toggle('mobile-open',open);
 header.querySelector('.menu-toggle')?.setAttribute('aria-expanded',String(open));
}
document.addEventListener('keydown',e=>{if(e.key==='Escape'){close();setMobileMenuOpen(false)}});
document.addEventListener('click',e=>{
 if(e.target.closest('.customer-primary-nav a') || !e.target.closest('.customer-header'))setMobileMenuOpen(false);
});
window.addEventListener('resize',()=>{if(window.innerWidth>1280)setMobileMenuOpen(false)});
document.addEventListener('error',event=>{
 const target=event.target;
 if(!(target instanceof HTMLImageElement)||target.dataset.ezFallback)return;
 target.dataset.ezFallback='1';
 target.src='/assets/storefront-fallback.svg';
 target.parentElement?.classList.add('image-fallback');
},true);
start();
})();