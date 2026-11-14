(() => {
'use strict';
const root=document.getElementById('root');
const modalRoot=document.getElementById('modal-root');
const toastRoot=document.getElementById('toast-root');
const icons={
 home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
 chart:'<path d="M3 3v18h18M8 16v-5m5 5V7m5 9V4"/>',
 orders:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
 box:'<path d="m12 2 9 5-9 5-9-5 9-5Zm-9 5v10l9 5 9-5V7M12 12v10"/>',
 tables:'<rect x="5" y="7" width="14" height="9" rx="2"/><path d="M7 16v5m10-5v5M7 4v3m10-3v3"/>',
 users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
 sparkle:'<path d="m12 3 1.8 5.7L19.5 10l-5.7 1.8L12 17.5l-1.8-5.7L4.5 10l5.7-1.3L12 3ZM19 16l.6 1.4L21 18l-1.4.6L19 20l-.6-1.4L17 18l1.4-.6L19 16Z"/>',
 settings:'<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM19.4 15a1.7 1.7 0 0 0 .4 1.9l.1.1-1.9 1.9-.1-.1a1.7 1.7 0 0 0-1.9-.4 1.7 1.7 0 0 0-1 1.6V21h-3v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.4l-.1.1-1.9-1.9.1-.1a1.7 1.7 0 0 0 .4-1.9A1.7 1.7 0 0 0 6 14H5v-3h1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.4-1.9l-.1-.1 1.9-1.9.1.1a1.7 1.7 0 0 0 1.9.4A1.7 1.7 0 0 0 12 5h3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.4l.1-.1 1.9 1.9-.1.1a1.7 1.7 0 0 0-.4 1.9A1.7 1.7 0 0 0 21 11h1v3h-1a1.7 1.7 0 0 0-1.6 1Z"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',close:'<path d="M18 6 6 18M6 6l12 12"/>',search:'<circle cx="10.7" cy="10.7" r="7"/><path d="m16 16 5 5"/>',
 chevron:'<path d="m9 18 6-6-6-6"/>',back:'<path d="m15 18-6-6 6-6"/>',arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
 check:'<path d="m5 12 4 4L19 6"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>',
 wallet:'<rect x="3" y="5" width="18" height="15" rx="3"/><path d="M3 9h18m-5 6h2"/>',
 trend:'<path d="m3 17 6-6 4 4 8-8m-6 0h6v6"/>',
 warning:'<path d="m12 3 10 18H2L12 3Zm0 7v4m0 4h.01"/>',
 coffee:'<path d="M4 8h14v6a7 7 0 0 1-14 0V8Zm14 1h2a3 3 0 0 1 0 6h-2M2 21h20M7 2v3M12 2v3"/>',
 store:'<path d="M4 10v11h16V10M3 5h18l-1 5a3 3 0 0 1-5 1 3 3 0 0 1-6 0 3 3 0 0 1-5-1L3 5Z"/>',
 globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18m-9-9a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',
 lock:'<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
 logout:'<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5m5 5H9"/>',
 menu:'<path d="M4 7h16M4 12h16M4 17h16"/>',
 info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
 receipt:'<path d="M5 3h14v18l-3-2-4 2-4-2-3 2V3Zm4 5h6m-6 4h6"/>',
 refresh:'<path d="M21 11a9 9 0 0 0-15-6L3 8M3 3v5h5M3 13a9 9 0 0 0 15 6l3-3m0 5v-5h-5"/>',
 warehouse:'<path d="m3 9 9-6 9 6v12H3V9Zm3 12v-9h12v9M9 12v9m6-9v9"/>',
 crown:'<path d="m2 7 5 4 5-7 5 7 5-4-2 13H4L2 7Z"/>',
 dots:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>'
};
function I(name,size=''){return `<svg class="ic ${size}" viewBox="0 0 24 24" aria-hidden="true">${icons[name]||icons.box}</svg>`}
const E=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const V=x=>new Intl.NumberFormat(window.EZI18N?.locale()||'vi-VN').format(Number(x)||0)+'đ';
const D=x=>x?new Date(x).toLocaleString(window.EZI18N?.locale()||'vi-VN',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}):'—';
const s={user:null,csrf:null,demo:false,businesses:[],business:null,tab:'overview',authMode:'login',setupStep:1,answers:{name:'',industry:'fnb',need_tables:true,need_inventory:true,need_insights:true,need_branches:false,description:'',selected_plan:'PLUS'},recommendation:null,trialEnabled:false,cache:{},orderFilter:'all',orderDateFrom:'',orderDateTo:'',orderTableFilter:'all',orderBranchFilter:'all',orderSearch:''};
const restaurantSuite=window.EZRestaurantSuite?.({api,E,V,D,toast,modal,closeModal,newOrder,newTable,getState:()=>s,navigate:tab=>{s.tab=tab;history.pushState(null,'','/app?tab='+encodeURIComponent(tab));appFrame();window.scrollTo(0,0)}});
async function api(path,opt={}){
 const controller=new AbortController();
 const timeoutMs=path==='/auth/demo'?45000:(opt.method&&opt.method!=='GET'?30000:20000);
 const timer=setTimeout(()=>controller.abort(),timeoutMs);
 const init={credentials:'same-origin',...opt,signal:opt.signal||controller.signal,headers:{'Content-Type':'application/json','Accept-Language':window.EZI18N?.language()||'vi',...(opt.headers||{})}};
 if(s.csrf&&init.method&&init.method!=='GET')init.headers['x-csrf-token']=s.csrf;
 try{
   const response=await fetch('/api'+path,init);
   let data;try{data=await response.json()}catch{data={detail:'Máy chủ không phản hồi hợp lệ'}}
   if(!response.ok){
     if(response.status===402&&s.business&&!s.business.billing_required&&path.indexOf('/billing')===-1){
       s.business.billing_required=true;s.business.subscription_status='trial_expired';s.tab='billing';
       try{
         s.cache={billing:await api('/businesses/'+encodeURIComponent(s.business.id)+'/billing')};
         history.replaceState(null,'','/app?tab=billing');
         appFrame();
       }catch(_){toast('Dùng thử đã hết hạn. Tải lại trang để mở thanh toán.',true)}
     }
     const error=new Error(typeof data.detail==='string'?data.detail:'Thao tác không thành công');
     error.status=response.status;throw error;
   }
   return data;
 }catch(error){
   if(error.name==='AbortError')throw new Error('Kết nối quá thời gian. Kiểm tra mạng và thử lại.');
   throw error;
 }finally{clearTimeout(timer)}
}
function toast(message,bad=false){const el=document.createElement('div');el.className='toast'+(bad?' error':'');el.innerHTML=I(bad?'warning':'check','sm')+`<span>${E(message)}</span>`;toastRoot.append(el);setTimeout(()=>el.remove(),3500)}
function logo(brand){const picture=brand?.logo_url?`<img class="merchant-brand-image" src="${E(brand.logo_url)}" alt="Logo ${E(brand.display_name||'')}" loading="lazy"/>`:'';return picture?`<div class="wordmark ez-wordmark ez-tenant-wordmark"><div class="brand-symbol">${picture}</div><span class="ez-brand-name">${E(brand.display_name||'Thing')}</span></div>`:`<div class="wordmark ez-wordmark"><img class="ez-full-logo ez-full-logo-light" src="/assets/icons/ez-thing-wordmark-light.svg?v=minimal-01" alt="EZ Thing" decoding="async"><img class="ez-full-logo ez-full-logo-dark" src="/assets/icons/ez-thing-wordmark-dark.svg?v=minimal-01" alt="" aria-hidden="true" decoding="async"></div>`}
function auth(){root.innerHTML=`<div class="auth-layout"><section class="auth-main"><div class="auth-logo">${logo()}</div><div class="auth-card">
 <div class="pill green" style="margin-bottom:19px">${I('sparkle','sm')} BUSINESS MADE SIMPLE</div>
 <h1>${s.authMode==='login'?'Chào mừng trở lại 👋':'Bắt đầu kinh doanh thông minh'}</h1>
 <p style="font-size:14px;color:var(--muted);margin-bottom:27px">${s.authMode==='login'?'Đăng nhập để tiếp tục quản lý doanh nghiệp của bạn.':'Tạo tài khoản, dùng thử miễn phí 7 ngày. Chọn gói và thanh toán sau, không cần nhập thẻ.'}</p>
 <form id="auth-form">${s.authMode==='signup'?`<div class="formfield"><label>Họ và tên</label><input name="name" placeholder="Nguyễn Văn A" minlength="2" maxlength="100" required autocomplete="name"/></div>`:''}
 <div class="formfield"><label>Email</label><input type="email" name="email" placeholder="you@business.com" required autocomplete="email"/></div>
 <div class="formfield"><label>Mật khẩu</label><input type="password" name="password" minlength="${s.authMode==='signup'?10:1}" placeholder="${s.authMode==='signup'?'Ít nhất 10 ký tự':'Nhập mật khẩu'}" required autocomplete="${s.authMode==='signup'?'new-password':'current-password'}"/></div>
 <button class="btn wide" type="submit">${s.authMode==='login'?'Đăng nhập':'Bắt đầu dùng thử 7 ngày'} ${I('arrow','sm')}</button></form>
 <div class="auth-switch">${s.authMode==='login'?'Chưa có tài khoản?':'Đã có tài khoản?'} <button data-action="auth-toggle">${s.authMode==='login'?'Đăng ký ngay':'Đăng nhập'}</button></div>
 ${s.emailVerificationNotice?`<div class="subtle center" role="status" style="margin-top:14px">${E(s.emailVerificationNotice)}</div>`:''}
 ${s.authMode==='login'?'<div class="auth-switch"><button data-action="auth-resend-verification">Gửi lại email xác minh</button></div>':''}
 <div class="subtle center" style="margin-top:32px">🔒 Dữ liệu doanh nghiệp được phân tách theo tài khoản</div></div></section>
 <aside class="auth-visual"><div class="visual-card"><div class="visual-bar">${logo().replace('wordmark','wordmark').replace('font-size','font-size')}<div class="visual-dots"><i></i><i></i><i></i></div></div>
 <div class="visual-content"><div class="muted tiny strong" style="margin-bottom:14px">TỔNG QUAN KINH DOANH</div><div class="fake-grid"><div class="fake-kpi"><small class="muted">Doanh thu</small><b>24,8tr</b></div><div class="fake-kpi"><small class="muted">Đơn hàng</small><b>128</b></div><div class="fake-kpi"><small class="muted">Khách hàng</small><b>84</b></div></div><div class="fake-chart">${[28,45,35,69,54,80,65,95,70,100].map(i=>`<span style="height:${i}%"></span>`).join('')}</div></div></div>
 <div class="visual-float">${I('trend','sm')} +18.5% <small>Tăng trưởng doanh thu</small></div><div class="visual-copy"><h2>Mọi hoạt động.<br/>Một nơi quản lý.</h2><p>Đơn giản hơn mỗi ngày.</p></div></aside></div>`}
function setup(){const a=s.answers;root.innerHTML=`<div class="setup-wrap"><div class="setup-card"><div class="setup-header">${logo()}<div class="steps">${[1,2,3].map(i=>`<span class="step ${i<=s.setupStep?'active':''}"></span>`).join('')}</div></div>
 ${s.setupStep===1?`<div class="pill green" style="margin-bottom:17px">BƯỚC 1 / 3</div><h1>Doanh nghiệp của bạn kinh doanh gì?</h1><p class="intro">Chọn ngành nghề để chúng tôi thiết lập đúng các tính năng.</p>
 <div class="formfield"><label>Tên doanh nghiệp</label><input id="biz-name" maxlength="140" value="${E(a.name)}" placeholder="Ví dụ: The Garden Coffee"/></div>
 <div class="industry-grid">${[['fnb','coffee','Nhà hàng & Cafe','Đồ ăn, đồ uống'],['retail','store','Bán lẻ','Cửa hàng, shop'],['online','globe','Bán hàng online','Thương mại điện tử'],['services','calendar','Dịch vụ','Spa, salon, studio']].map(([id,ico,title,desc])=>`<button class="industry-choice ${a.industry===id?'active':''}" data-action="industry" data-value="${id}"><span class="choice-icon">${I(ico,'lg')}</span><span><strong>${title}</strong><small>${desc}</small></span></button>`).join('')}</div>`:''}
 ${s.setupStep===2?`<div class="pill green" style="margin-bottom:17px">BƯỚC 2 / 3</div><h1>Bạn cần quản lý những gì?</h1><p class="intro">Chỉ chọn những gì cần thiết. Có thể cấu hình lại sau.</p>
 ${[['need_tables','Quản lý sơ đồ bàn','Theo dõi bàn trống và bàn đang phục vụ','fnb'],['need_inventory','Theo dõi tồn kho','Biết số lượng hàng hóa còn lại',null],['need_insights','Phân tích kinh doanh','Báo cáo món bán chạy và cảnh báo kho',null],['need_branches','Nhiều chi nhánh','Quản lý nhiều địa điểm',null]].filter(x=>!x[3]||x[3]===a.industry).map(([key,title,desc])=>`<div class="choice-row"><div><strong>${title}</strong><div class="subtle">${desc}</div></div><button class="switch ${a[key]?'on':''}" data-action="answer-toggle" data-value="${key}" aria-label="${title}" aria-pressed="${a[key]}"></button></div>`).join('')}`:''}
 ${s.setupStep===3&&!s.trialEnabled?`<div class="pill green" style="margin-bottom:17px">BƯỚC 3 / 3</div><h1>Chọn gói phù hợp ✨</h1><p class="intro">Hệ thống đã đối chiếu nhu cầu với thư viện chức năng có sẵn. Bạn có thể chọn gói khác.</p>
 <p class="subtle" style="margin-bottom:13px">Gợi ý dựa trên quy tắc thiết lập • Không tự phát triển chức năng ngoài hệ thống</p>
 <div class="plan-grid">${[['BASIC','249.000','Quản lý cơ bản'],['PLUS','499.000','Phân tích & kho nâng cao'],['PRO','999.000','Nhiều chi nhánh']].map(([id,price,desc])=>`<button data-action="choose-plan" data-value="${id}" class="plan-choice ${a.selected_plan===id?'selected':''}"><div style="display:flex;justify-content:space-between;align-items:center"><h3>${id}</h3>${a.selected_plan===id?`<span class="pill green">${I('check','sm')}</span>`:''}</div><div class="price">${price}<small>đ/tháng*</small></div><div class="subtle">${desc}</div>${(id==='BASIC'?['Bán hàng & sản phẩm','Kho cơ bản','Tên, giới thiệu, banner mẫu']:id==='PLUS'?['Tất cả Basic','Phân tích số liệu','Điều chỉnh kho','Logo, banner riêng và màu thương hiệu']:['Tất cả Plus','Nhiều chi nhánh','Nhật ký quản trị','3 bố cục trang khách hàng']).map(f=>`<div class="plan-feature">${I('check','sm')}${f}</div>`).join('')}</button>`).join('')}</div>
 <div class="subtle" style="margin-top:16px">Gói đề xuất: <strong>${E(s.recommendation?.recommended_plan||'PLUS')}</strong>. *Giá dự kiến. Bản MVP chỉ kích hoạt chế độ pilot, chưa thu tiền hay kết nối thanh toán.</div>`:''}
 ${s.setupStep===3&&s.trialEnabled?`<div class="pill green" style="margin-bottom:17px">7-DAY FREE TRIAL</div>
<h1>7 ngày trải nghiệm. Không cần thẻ 💳</h1>
<p class="intro">Đầy đủ tính năng hiện có theo ngành, bao gồm phân tích và giao diện thương hiệu. Sau 7 ngày, bạn mới chọn gói Basic / Plus / Pro và thanh toán nếu muốn tiếp tục.</p>
<div class="surface pad" style="margin:18px 0"><div class="feature-list">
<div class="feature-row">✓ <strong>Không cần chọn gói trước</strong></div>
<div class="feature-row">✓ <strong>Không tự động trừ tiền</strong></div>
<div class="feature-row">✓ <strong>Nhắc ngày hết hạn tại trang quản lý</strong></div>
<div class="feature-row">✓ <strong>Dữ liệu được giữ nguyên khi trial hết hạn</strong></div>
</div></div><p class="subtle">Sản phẩm đang thử nghiệm; thanh toán chỉ kích hoạt khi cổng thanh toán được cấu hình và xác minh.</p>`:'' }
 <div class="setup-footer"><button class="btn ghost" data-action="setup-back">${I('back','sm')} ${s.setupStep===1?'Đăng xuất':'Quay lại'}</button><button class="btn" data-action="setup-next">${s.setupStep===3?(s.trialEnabled?'Bắt đầu thử 7 ngày':'Tạo không gian làm việc'):'Tiếp tục'} ${I('arrow','sm')}</button></div></div></div>`}
const navItems=[['overview','home','Tổng quan'],['orders','orders','Đơn hàng'],['products','box','Sản phẩm'],['tables','tables','Sơ đồ bàn'],['reservations','calendar','Đặt bàn trước'],['kitchen','coffee','Bếp & pha chế'],['inventory','warehouse','Sổ kho'],['delivery','globe','Giao hàng'],['appointments','calendar','Lịch hẹn'],['customers','users','Khách hàng'],['insights','sparkle','Phân tích'],['billing','wallet','Gói & thanh toán'],['account_lock','lock','Chờ gia hạn'],['team','users','Nhân sự'],['settings','settings','Cài đặt']];
const industryFeatures={fnb:['kitchen','kitchen'],retail:['inventory','stock_ledger'],online:['delivery','fulfillment'],services:['appointments','appointments']};
const activeIndustry=()=>industryFeatures[s.business?.industry]||[];
const menuItems=()=>s.business?.billing_required?navItems.filter(([id])=>id===(s.business?.role==='owner'?'billing':'account_lock')):navItems.filter(([id])=>{
 if(id==='team'||id==='billing')return s.business?.role==='owner';
 if(id==='insights'&&s.business?.role==='staff')return false;
 return id==='reservations'?(s.business?.industry==='fnb'&&has('tables')):
 !(['tables','insights','kitchen','inventory','delivery','appointments'].includes(id))||
 (id==='tables'?has('tables'):id==='insights'?has('insights'):id===activeIndustry()[0]&&has(activeIndustry()[1]));
});
const has=name=>Boolean(s.business?.active_modules?.includes(name));
function appFrame(){const b=s.business;window.EZMerchantTheme?.setBusiness(b.id);const nav=menuItems();const storefront={fnb:'/menu/cafe',retail:'/store/mart',online:'/store/online',services:'/booking/wellness'}[b.industry];const brand=s.cache.storefront?.branding;root.innerHTML=`<div class="app" style="--merchant-brand-accent:${E(brand?.accent_color||'#147D64')}"><aside class="sidebar"><a class="merchant-home-link" href="/" title="EZ Thing trang chủ" aria-label="EZ Thing trang chủ">${logo(brand)}<img class="sidebar-ez-icon sidebar-ez-icon-light" src="/assets/icons/ez-mark-light.svg?v=minimal-01" alt="" aria-hidden="true" decoding="async"><img class="sidebar-ez-icon sidebar-ez-icon-dark" src="/assets/icons/ez-mark-dark.svg?v=minimal-01" alt="" aria-hidden="true" decoding="async"></a><div class="side-caption">MERCHANT BACK-OFFICE</div><nav class="side-nav">${nav.map(([id,ico,name])=>`<button class="side-link ${s.tab===id?'active':''}" data-action="tab" data-value="${id}" title="${E(name)}" aria-label="${E(name)}">${I(ico)} <span class="side-label">${E(name)}</span></button>`).join('')}</nav><div class="sidebar-bottom">${s.demo?`<a class="merchant-customer-link" href="${storefront}" target="_self" aria-label="Xem frontend khách hàng" title="Xem frontend khách hàng">${I('globe','sm')} Xem frontend khách hàng ↗</a>`:''}<div class="help">${I('sparkle')}<strong>Thiết lập thông minh</strong><small>Cấu hình dựa trên ngành nghề và gói dịch vụ.</small></div><button class="business-switch" data-action="switch-business" style="width:calc(100% - 10px);background:var(--merchant-panel,var(--paper,#fff));color:var(--merchant-ink,var(--ink));text-align:left"><span class="b-avatar">${E((b.name||'E')[0].toUpperCase())}</span><span class="b-meta" style="flex:1"><strong>${E(b.name)}</strong><span>${E(b.plan)} • ${E(b.subscription_status||'Pilot')}</span></span>${I('chevron','sm')}</button></div></aside>
 <main class="main">${s.demo?`<div class="demo-ribbon">🧪 Chế độ DEMO • Toàn bộ dữ liệu chỉ để thử nghiệm</div>`:''}${b.subscription_status==='trialing'?`<div class="billing-trial-banner"><span>🎁 ${E(b.trial_days_remaining)} ngày trải nghiệm miễn phí còn lại</span><button class="btn sm secondary" data-action="tab" data-value="billing">Xem gói</button></div>`:''}<div id="offline-banner" class="offline-banner hide">Mất kết nối. Chỉ xem được giao diện đã lưu, không thể tạo đơn khi offline.</div><header class="topbar"><div class="topbar-left"><div class="eyebrow"><span class="merchant-brand-dot" aria-hidden="true"></span>${E(b.name)} <span style="padding:0 5px">/</span> ${E(b.plan)}</div><h1 id="page-title">${E(navItems.find(x=>x[0]===s.tab)?.[2]||'Tổng quan')}</h1></div><div class="topbar-right">${window.EZMerchantTheme?.pickerMarkup()||''}<span class="pill green">${I('check','sm')} ${s.demo?'DEMO BACK-OFFICE':'BACK-OFFICE'}</span>${s.demo?`<a class="merchant-preview-link" href="${storefront}">Xem trang khách ↗</a>`:''}<button class="iconbtn" title="Chuyển doanh nghiệp" data-action="switch-business">${I('store')}</button><button class="avatar" data-action="profile" title="Tài khoản">${E(s.user?.name?.[0]?.toUpperCase()||'E')}</button></div></header><section class="content" id="page-content"><div class="app-skeleton"></div></section></main>
 <nav class="mobile-nav">${(b.billing_required?(b.role==='owner'?[['billing','wallet','Thanh toán']]:[['account_lock','lock','Gia hạn']]):[['overview','home','Tổng quan'],['orders','orders','Đơn hàng'],['products','box','Sản phẩm'],[activeIndustry()[0]||'customers',s.business.industry==='fnb'?'coffee':s.business.industry==='retail'?'warehouse':s.business.industry==='online'?'globe':'calendar',s.business.industry==='fnb'?'Bếp':s.business.industry==='retail'?'Kho':s.business.industry==='online'?'Giao hàng':'Lịch hẹn'],['settings','menu','Thêm']]).map(([id,ico,label])=>`<button data-action="tab" data-value="${id}" class="${s.tab===id?'active':''}">${I(ico)}<span>${label}</span></button>`).join('')}</nav></div>`;setOnline();renderTab()}
function setOnline(){const el=document.getElementById('offline-banner');if(el)el.classList.toggle('hide',navigator.onLine)}
function cardEmpty(icon,title,sub,action='',text=''){return `<div class="empty"><div class="empty-icon">${I(icon,'xl')}</div><h3>${E(title)}</h3><p>${E(sub)}</p>${action?`<button class="btn sm" data-action="${action}">${I('plus','sm')} ${E(text)}</button>`:''}</div>`}
async function loadData(){const bid=s.business.id;const tasks={overview:`/businesses/${bid}/overview`,orders:`/businesses/${bid}/orders`,products:`/businesses/${bid}/products`,customers:`/businesses/${bid}/customers`,branches:`/businesses/${bid}/branches`,storefront:`/businesses/${bid}/storefront`};if(s.business.role==='owner'){
  tasks.billing=`/businesses/${bid}/billing`;
  tasks.team=`/businesses/${bid}/team`;
  tasks.publishing=`/businesses/${bid}/publishing`;
 }
 if(s.business.role==='owner'||s.business.role==='manager')
   tasks.publicLeads=`/businesses/${bid}/public-leads`;
 if(s.business.role==='owner'||s.business.role==='manager')
   tasks.orderRequests=`/businesses/${bid}/order-requests`;
 if(has('tables'))tasks.tables=`/businesses/${bid}/tables`;if(has(activeIndustry()[1]))tasks.industry=`/businesses/${bid}/industry/${activeIndustry()[0]}`;if(has('insights')&&s.business.role!=='staff'){tasks.insights=`/businesses/${bid}/insights`;tasks.receivables=`/businesses/${bid}/receivables`;}
 const results=await Promise.allSettled(Object.entries(tasks).map(async ([name,path])=>[name,await api(path)]));
 let failed=0;
 for(const result of results){
   if(result.status==='fulfilled')s.cache[result.value[0]]=result.value[1];
   else failed++;
 }
 if(failed&&!s.business?.billing_required)toast('Không tải được '+failed+' mục dữ liệu. Vui lòng thử lại.',true);
}
const section=(title,sub,right='')=>`<div class="section-header"><div><h2>${title}</h2><p>${sub}</p></div>${right}</div>`;
const kpi=(title,value,sub,icon,tint='')=>`<article class="surface kpi"><div class="kpi-top"><span>${title}</span><div class="kpi-icon ${tint}">${I(icon)}</div></div><h3>${value}</h3><p>${sub}</p></article>`;
function renderTab(){const el=document.getElementById('page-content');if(!el)return;const label=navItems.find(x=>x[0]===s.tab)?.[2]||'Tổng quan';document.getElementById('page-title').textContent=label;
 el.innerHTML=({overview:overviewTab,orders:ordersTab,products:productsTab,tables:()=>restaurantSuite?.renderFloorplan()||tablesTab(),reservations:()=>restaurantSuite?.renderReservations()||cardEmpty("calendar","Đặt bàn","Không tải được giao diện đặt bàn."),customers:customersTab,kitchen:industryTab,inventory:industryTab,delivery:industryTab,appointments:industryTab,insights:insightsTab,settings:settingsTab,billing:billingTab,team:teamTab,account_lock:lockedAccountTab}[s.tab]||overviewTab)();
 if(["tables","reservations"].includes(s.tab))restaurantSuite?.mount();
 if(s.tab==='orders'&&!s.cache.orderDashboard)loadOrdersDashboard().catch(err=>toast(err.message,true));}
function overviewTab(){const o=s.cache.overview||{};const orders=s.cache.orders||[];return `<div class="dashboard-welcome"><div style="z-index:2"><span class="pill" style="background:#ffffff21;color:#fff;border-color:#ffffff30">${I('sparkle','sm')} BUSINESS HUB</span><h2>Quản lý dễ dàng.<br/>Kinh doanh hiệu quả hơn.</h2><p>Tất cả đơn hàng, sản phẩm và số liệu của bạn ở một nơi.</p><button class="btn" data-action="new-order">${I('plus','sm')} Tạo đơn hàng</button></div><div class="hero-art">✳</div></div>
 <div class="kpi-grid">${kpi('Doanh thu hôm nay',o.today_revenue_vnd==null?'—':V(o.today_revenue_vnd),'Từ đơn đã xác nhận nhận tiền','wallet')}${kpi('Đơn hàng',o.order_count||0,`${o.open_count||0} đơn đang xử lý`,'orders','blue')}${kpi('Sản phẩm',o.product_count||0,'Sản phẩm trong danh mục','box','orange')}${kpi('Cảnh báo tồn kho',o.low_stock||0,'Còn tối đa 5 sản phẩm','warning','red')}</div>
 <div class="split"><div class="surface pad"><div class="panel-title"><h3>Đơn hàng gần đây</h3><button class="btn ghost sm" data-action="tab" data-value="orders">Xem tất cả ${I('arrow','sm')}</button></div>${orders.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Đơn hàng</th><th>Thời gian</th><th>Giá trị</th><th>Trạng thái</th></tr></thead><tbody>${orders.slice(0,5).map(o=>`<tr><td class="table-name">#${E(o.id.slice(0,8).toUpperCase())}</td><td>${D(o.created_at)}</td><td><b>${V(o.total_vnd)}</b></td><td>${status(o.status)}</td></tr>`).join('')}</tbody></table></div>`:cardEmpty('orders','Chưa có đơn hàng','Tạo đơn đầu tiên để bắt đầu theo dõi doanh thu.','new-order','Tạo đơn đầu tiên')}</div>
 <div class="surface pad"><div class="panel-title"><h3>Thao tác nhanh</h3><span class="pill">QUẢN LÝ</span></div><div class="task-list">${[['new-order','orders','Tạo đơn hàng','Bán hàng tại quầy hoặc tại bàn'],...(s.business.role==='staff'?[]:[['new-product','box','Thêm sản phẩm','Xây dựng danh mục kinh doanh']]),['new-customer','users','Thêm khách hàng','Lưu địa chỉ và thông tin liên hệ'],...(s.business.role!=='staff'&&has('tables')?[['new-table','tables','Thêm bàn','Thiết lập khu vực phục vụ']]:[])].map(([act,ico,name,desc])=>`<button class="task-item" data-action="${act}" style="background:var(--merchant-panel,var(--paper,#fff));color:var(--merchant-ink,var(--ink));text-align:left;cursor:pointer"><span class="task-icon">${I(ico)}</span><span style="flex:1"><strong>${name}</strong><p>${desc}</p></span>${I('chevron','sm')}</button>`).join('')}</div></div></div>`}
function status(val){return val==='cancelled'?'<span class="pill red">Đã hủy</span>':val==='paid'?`<span class="pill paid">Đã nhận tiền</span>`:val==='open'?`<span class="pill yellow">Chờ thanh toán</span>`:`<span class="pill">${E(val)}</span>`}
function ordersTab(){const result=s.cache.orderDashboard;const list=(result?.orders||s.cache.orders||[]).filter(x=>!s.orderSearch||[x.id,...x.items.map(i=>i.name)].join(' ').toLocaleLowerCase('vi').includes(s.orderSearch.toLocaleLowerCase('vi')));const ordersCount=result?.total_count??list.length;const opened=result?.open_count??list.filter(x=>x.status==='open').length;const paid=result?.paid_count??list.filter(x=>x.status==='paid').length;const cancelled=result?.cancelled_count??list.filter(x=>x.status==='cancelled').length;const revenue=s.business.role==='staff'?null:(result?.paid_vnd??list.filter(x=>x.status==='paid').reduce((sum,x)=>sum+x.total_vnd,0));return `${section('Quản lý đơn hàng','Đơn được tính giá từ dữ liệu sản phẩm trên server.',`<button class="btn" data-action="new-order">${I('plus','sm')} Tạo đơn</button>`)}<div class="suite-summary order-kpis"><div><strong>${ordersCount}</strong><span>Tổng đơn trong kỳ</span></div><div><strong>${opened}</strong><span>Chưa thanh toán</span></div><div><strong>${paid}</strong><span>Đã nhận tiền</span></div><div><strong>${revenue==null?'—':V(revenue)}</strong><span>Doanh thu từ đơn tạo trong kỳ</span></div></div>
 <div class="order-range-bar">
 <label>Từ ngày<input type="date" data-order-filter="from" value="${E(s.orderDateFrom)}"></label>
 <label>Đến ngày<input type="date" data-order-filter="to" value="${E(s.orderDateTo)}"></label>
 <label>Chi nhánh<select data-order-filter="branch"><option value="all">Tất cả chi nhánh</option>${(s.cache.branches||[]).map(b=>`<option value="${E(b.id)}" ${s.orderBranchFilter===b.id?'selected':''}>${E(b.name)}</option>`).join('')}</select></label>
 <label>Bàn<select data-order-filter="table"><option value="all">Tất cả bàn</option>${(s.cache.tables||[]).filter(t=>s.orderBranchFilter==='all'||t.branch_id===s.orderBranchFilter).map(t=>`<option value="${E(t.id)}" ${s.orderTableFilter===t.id?'selected':''}>${E(t.label)}</option>`).join('')}</select></label>
 <button type="button" class="btn secondary sm" data-action="order-reset">Xóa bộ lọc</button></div>
 <div class="toolbar"><div class="search">${I('search')}<input data-order-search type="search" value="${E(s.orderSearch)}" placeholder="Tìm mã đơn, sản phẩm..." aria-label="Tìm đơn hàng"/></div><div class="filters">${[['all','Tất cả'],['open','Chờ thanh toán'],['paid','Đã nhận tiền'],['cancelled','Đã hủy']].map(([id,n])=>`<button class="filter-btn ${s.orderFilter===id?'active':''}" data-action="order-filter" data-value="${id}">${n}</button>`).join('')}</div></div><div class="surface pad order-list-surface">${list.length?window.EZOrderCards.renderList(list,{E,V,D,status,I,canMarkPaid:s.business.role!=='staff',canCancel:s.business.role==='owner'}):cardEmpty('orders','Không có đơn hàng','Các đơn hàng sẽ hiển thị tại đây.','new-order','Tạo đơn')}</div><div class="subtle mt8">${result?.truncated?`Hiển thị ${result.limit} đơn gần nhất trong ${result.total_count} đơn phù hợp bộ lọc. Hãy thu hẹp ngày để xem phần còn lại. · `:''}Đã hủy: ${cancelled}. Xác nhận tiền là thao tác thủ công; doanh thu hiển thị theo ngày tạo đơn, không phải ngày nhận tiền. Chưa tích hợp ngân hàng.</div>`}
async function loadOrdersDashboard(){
 const business=s.business?.id;if(!business)return;
 const query=new URLSearchParams();
 if(s.orderDateFrom)query.set('from_day',s.orderDateFrom);
 if(s.orderDateTo)query.set('to_day',s.orderDateTo);
 if(s.orderFilter!=='all')query.set('status',s.orderFilter);
 if(s.orderBranchFilter&&s.orderBranchFilter!=='all')query.set('branch_id',s.orderBranchFilter);
 if(s.orderTableFilter&&s.orderTableFilter!=='all')query.set('table_id',s.orderTableFilter);
 query.set('limit','200');
 const result=await api('/businesses/'+encodeURIComponent(business)+'/order-dashboard?'+query.toString());
 if(s.business?.id!==business)return;
 s.cache.orderDashboard=result;
 if(s.tab==='orders')renderTab();
}
function orderDetails(id){
 const o=(s.cache.orderDashboard?.orders||s.cache.orders||[]).find(x=>x.id===id);if(!o)return;
 const table=s.cache.tables?.find(t=>t.id===o.table_id);
 const customer=s.cache.customers?.find(c=>c.id===o.customer_id);
 const age=Math.max(0,Math.floor((Date.now()-new Date(o.created_at).getTime())/60000));
 modal('Chi tiết đơn #'+o.id.slice(0,8).toUpperCase(),
 `<div class="order-detail-box"><p><strong>Trạng thái: </strong>${status(o.status)} · ${o.status==='open'?'Đơn mở '+age+' phút':o.status==='cancelled'?'Đơn đã hủy':'Đã thanh toán'}</p>
 <p><strong>Khởi tạo:</strong> ${D(o.created_at)} · <strong>Bàn:</strong> ${E(table?.label||'Mang đi / giao hàng')}</p>
 ${customer?`<p><strong>Khách:</strong> ${E(customer.name)} · ${E(customer.phone||'')}</p>`:''}
 <div class="order-detail-lines">${o.items.map(item=>`<div><span>${E(item.name)} ×${item.quantity} <small>${V(item.unit_price_vnd)} / món</small></span><strong>${V(item.total_vnd)}</strong></div>`).join('')}</div>
 <p><strong>Ghi chú:</strong> ${E(o.note||'Không có')}</p>
 <div class="summary-line"><strong>Tổng tiền</strong><b>${V(o.total_vnd)}</b></div>
 <div class="modal-footer"><button class="btn secondary" data-action="close-modal">Đóng</button>${o.status==='open'?`${s.business.role==='owner'?`<button class="btn" data-action="cancel-order" data-value="${E(o.id)}">Hủy đơn</button>`:''} ${s.business.role!=='staff'?`<button class="btn" data-action="confirm-paid" data-value="${E(o.id)}">Xác nhận đã nhận tiền</button>`:''}`:''}</div></div>`,true)
}
function productsTab(){const p=s.cache.products||[];return `${section('Danh mục sản phẩm',`${p.length} sản phẩm đang quản lý`,s.business.role==='staff'?'':`<button class="btn" data-action="new-product">${I('plus','sm')} Thêm sản phẩm</button>`)}<div class="toolbar"><div class="search">${I('search')}<input data-search="#product-rows" placeholder="Tìm tên sản phẩm, mã SKU..."/></div></div><div id="product-rows" class="product-grid">${p.length?p.map((x,idx)=>`<article data-match="${E((x.name+' '+x.sku+' '+x.category).toLowerCase())}" class="surface product-card"><div class="product-main"><div class="product-visual">${['☕','🍰','🥤','🛒','📦','🍽️'][idx%6]}</div><div style="min-width:0"><h3 title="${E(x.name)}">${E(x.name)}</h3><p>${E(x.category)} • ${E(x.sku)}</p></div></div><div class="product-footer"><div><strong>${V(x.price_vnd)}</strong><div class="subtle">${x.track_stock?'Tồn kho: '+x.stock:'Không theo dõi kho'}</div></div>${has('inventory_adjust')&&x.track_stock&&s.business.role!=='staff'?`<button class="btn sm secondary" data-action="adjust-stock" data-value="${E(x.id)}">${I('plus','sm')} Kho</button>`:`<span class="pill">${x.stock<=5&&x.track_stock?'Sắp hết':'Đang bán'}</span>`}</div></article>`).join(''):cardEmpty('box','Chưa có sản phẩm','Thêm sản phẩm để bắt đầu tạo đơn bán hàng.','new-product','Thêm sản phẩm')}</div>`}
function tablesTab(){const t=s.cache.tables||[];return `${section('Sơ đồ bàn',`${t.filter(x=>!x.occupied).length} bàn trống • ${t.filter(x=>x.occupied).length} bàn có khách`,s.business.role==='staff'?'':`<button class="btn" data-action="new-table">${I('plus','sm')} Thêm bàn</button>`)}<div class="table-grid">${t.length?t.map(x=>`<button class="table-tile ${x.occupied?'occupied':''}" data-action="table-order" data-value="${E(x.id)}"><div class="table-symbol">${I('tables')}</div><strong>${E(x.label)}</strong><small>${x.occupied?'● Đang phục vụ':'● Còn trống'} • ${x.seats} chỗ</small></button>`).join(''):`<div class="surface" style="grid-column:1/-1">${cardEmpty('tables','Chưa có bàn','Thiết lập bàn cho nhà hàng hoặc quán cafe.','new-table','Tạo bàn')}</div>`}</div><div class="subtle mt8">Bấm vào bàn để tạo đơn mới. Bàn có đơn chưa thanh toán sẽ được đánh dấu đang phục vụ.</div>`}
function customersTab(){const list=s.cache.customers||[];return `${section('Khách hàng',`${list.length} hồ sơ khách hàng`,`<button class="btn" data-action="new-customer">${I('plus','sm')} Thêm khách</button>`)}<div class="toolbar"><div class="search">${I('search')}<input data-search="#customer-rows" placeholder="Tìm tên, số điện thoại..."/></div></div><div id="customer-rows" class="customer-grid">${list.length?list.map(x=>`<article data-match="${E((x.name+' '+x.phone+' '+x.address).toLowerCase())}" class="surface customer-card"><div class="mini-avatar">${E(x.name?.[0]?.toUpperCase())}</div><strong>${E(x.name)}</strong><p>${E(x.phone||'Chưa có điện thoại')}</p><p>${E(x.address||'Chưa có địa chỉ')}</p></article>`).join(''):cardEmpty('users','Chưa có khách hàng','Thêm khách hàng khi cần giao hàng, lưu lịch sử đơn.','new-customer','Thêm khách hàng')}</div>`}
function insightsTab(){const inx=s.cache.insights||{};const debt=s.cache.receivables||{};if(!has('insights'))return cardEmpty('lock','Chức năng Plus / Pro','Nâng cấp để xem phân tích hoạt động.');return `${section('Phân tích kinh doanh','Dữ liệu thực tế được tính trực tiếp từ các đơn đã xác nhận thanh toán.')}<div class="split"><article class="surface pad"><div class="panel-title"><h3>Sản phẩm bán chạy</h3><span class="pill blue">${I('chart','sm')} DỮ LIỆU THẬT</span></div>${inx.top_products?.length?`<div class="insight-list">${inx.top_products.map((x,i)=>`<div class="insight-item"><div style="display:flex;align-items:center;gap:12px"><span class="mini-avatar">${i+1}</span><div><strong>${E(x.name)}</strong><div class="subtle">Đã bán ${x.quantity}</div></div></div><b>${V(x.revenue_vnd)}</b></div>`).join('')}</div>`:cardEmpty('chart','Chưa có số liệu','Khi đơn được xác nhận đã nhận tiền, bảng xếp hạng sẽ xuất hiện.')}</article><article class="surface pad"><div class="panel-title"><h3>Hàng sắp hết</h3><span class="pill yellow">${I('warning','sm')} KIỂM TRA KHO</span></div>${inx.low_stock?.length?`<div class="insight-list">${inx.low_stock.map(x=>`<div class="insight-item"><b>${E(x.name)}</b><span class="pill ${x.stock===0?'red':'yellow'}">Còn ${x.stock}</span></div>`).join('')}</div>`:cardEmpty('check','Tồn kho ổn định','Không có sản phẩm nào tồn kho thấp hơn hoặc bằng 5.')}</article></div><div class="surface pad" style="margin-top:17px"><div class="panel-title"><h3>Đơn chưa thanh toán theo khách hàng</h3><span class="pill yellow">${V(debt.unpaid_vnd||0)}</span></div>${debt.customers?.length?`<div class="insight-list">${debt.customers.slice(0,8).map(x=>`<div class="insight-item"><span><b>${E(x.name)}</b><small class="subtle" style="display:block">${x.unpaid_count} đơn</small></span><strong>${V(x.unpaid_vnd)}</strong></div>`).join('')}</div>`:cardEmpty('wallet','Chưa có công nợ','Chỉ tính các đơn có khách hàng được chọn và chưa ghi nhận thanh toán.')}</div><div class="surface pad" style="margin-top:17px"><div class="panel-title"><h3>Trợ lý phân tích</h3><span class="pill">Bản nền tảng</span></div><p class="muted">Bản MVP sử dụng dữ liệu SQL và quy tắc xác định, chưa kết nối mô hình AI tạo sinh. Khi có dữ liệu bán hàng, hệ thống có thể đưa ra cảnh báo rõ nguồn gốc.</p></div>`}
function billingTab(){return window.EZBillingUI?.render(s.cache.billing,E,V)||cardEmpty('wallet','Thanh toán','Chưa tải được dữ liệu thanh toán.')}
function teamTab(){return window.EZTeamUI?.render(s.cache.team,E)||cardEmpty('users','Nhân sự','Chưa tải được danh sách nhân sự.')}
function lockedAccountTab(){return cardEmpty('lock','Doanh nghiệp đang chờ gia hạn','Dùng thử hoặc gói thanh toán đã hết hạn. Chỉ tài khoản Chủ doanh nghiệp có quyền chọn gói và thanh toán. Vui lòng liên hệ chủ doanh nghiệp.')}
function settingsTab(){const b=s.business;const features=[['dashboard','Tổng quan'],['products','Quản lý sản phẩm'],['orders','Quản lý đơn hàng'],['tables','Quản lý bàn'],['inventory_basic','Theo dõi kho'],['inventory_adjust','Điều chỉnh kho'],['insights','Phân tích'],['multi_branch','Nhiều chi nhánh'],['kitchen','Bếp & pha chế'],['stock_ledger','Sổ kho'],['fulfillment','Giao vận'],['appointments','Lịch hẹn']];return `${section('Cài đặt không gian', 'Gói dịch vụ, tính năng và thông tin doanh nghiệp.')}<div class="mobile-only surface pad" style="margin-bottom:14px"><div class="panel-title"><h3>Chức năng khác</h3></div><div class="task-list">${[['customers','users','Khách hàng'],...(b.role==='owner'?[['team','users','Nhân sự'],['billing','wallet','Gói & thanh toán']]:[]),...(s.business?.industry==='fnb'&&has('tables')?[['reservations','calendar','Đặt bàn trước']]:[]),...(has('insights')?[['insights','sparkle','Phân tích']]:[]),...(has('tables')?[['tables','tables','Sơ đồ bàn']]:[]),[activeIndustry()[0],s.business.industry==='retail'?'warehouse':s.business.industry==='services'?'calendar':'coffee',navItems.find(x=>x[0]===activeIndustry()[0])?.[2]||'Quy trình ngành']].map(([id,ico,label])=>`<button class="task-item" data-action="tab" data-value="${id}" style="background:var(--merchant-panel,var(--paper,#fff));color:var(--merchant-ink,var(--ink));text-align:left">${I(ico)} <strong style="flex:1">${label}</strong>${I('chevron','sm')}</button>`).join('')}</div></div><div class="surface pad" style="margin-bottom:18px"><div class="panel-title"><div><h3>🌐 Thiết kế trang khách hàng theo thương hiệu</h3><p class="subtle">Mỗi nhà hàng hoặc cửa hàng có tên, banner, thông tin riêng và trang xem trước. BASIC: banner mẫu • PLUS: logo, banner riêng và màu sắc • PRO: thêm kiểu bố cục.</p></div><span class="pill green">${E(b.plan)}</span></div><a class="btn secondary" href="/app/storefront-design?bid=${E(b.id)}">${I('sparkle','sm')} Chỉnh sửa thương hiệu &amp; xem trước ↗</a><p class="subtle" style="margin:10px 0 0">Website công khai chỉ hoạt động khi chủ doanh nghiệp bật xuất bản. Không tự động thu tiền trên website.</p></div>${b.role!=='staff'?(window.EZPublishingUI?.render(s.cache.publishing,s.cache.publicLeads,E,b.role==='owner',s.cache.orderRequests)||''):''}<div class="split"><div class="surface pad"><div class="panel-title"><h3>Gói thuê bao</h3><span class="pill green">PILOT</span></div><div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:15px"><div><div class="subtle">GÓI ĐANG THỬ NGHIỆM</div><h2 style="font-size:31px;margin:3px 0">${E(b.plan)}</h2><div class="subtle">Không phát sinh thu phí trong bản MVP</div></div><div class="brand-symbol" style="height:56px;width:56px">${I('crown','lg')}</div></div><div class="divider"></div><div class="panel-title"><h3>Chi nhánh</h3>${has('multi_branch')&&b.role!=='staff'?`<button class="btn sm secondary" data-action="new-branch">${I('plus','sm')} Thêm</button>`:''}</div>${(s.cache.branches||[]).map(x=>`<div class="task-item" style="margin-top:8px"><span class="task-icon">${I('store','sm')}</span><strong>${E(x.name)}</strong></div>`).join('')}<div class="divider"></div><button class="btn secondary wide" data-action="switch-business">${I('refresh','sm')} Chuyển doanh nghiệp</button><button class="btn ghost wide" data-action="logout" style="margin-top:8px">${I('logout','sm')} ${s.demo?'Tạo phiên demo mới':'Đăng xuất'}</button></div><div class="surface pad"><div class="panel-title"><h3>Chức năng đang bật</h3><span class="pill">${b.active_modules.length} module</span></div><div class="feature-list">${features.map(([id,name])=>`<div class="feature-row" style="opacity:${has(id)?1:.46}">${I(has(id)?'check':'lock','sm')}<div><b>${name}</b><div><small>${has(id)?'Đang hoạt động':'Chưa bật'}</small></div></div></div>`).join('')}</div><p class="subtle mt8">Gói tính năng được kiểm tra tại API. Để chuyển gói cần hoàn thiện hệ thống thanh toán và cấp quyền.</p></div></div>`}
function industryTab(){
 const kind=activeIndustry()[0],items=s.cache.industry||[];
 const titles={kitchen:['Bếp & pha chế','Theo dõi đơn từ quầy đến khi phục vụ','Tạo phiếu bếp'],inventory:['Sổ nhập / xuất kho','Lịch sử biến động tồn kho từ giao dịch và điều chỉnh',''],delivery:['Đóng gói & giao hàng','Quản lý quy trình giao hàng nội bộ; chưa kết nối hãng vận chuyển','Tạo phiếu giao'],appointments:['Lịch hẹn dịch vụ','Quản lý nhân viên, khách và giờ hẹn; tránh đặt trùng giờ','Đặt lịch mới']};
 const [name,subtitle,action]=titles[kind]||['Quy trình','',null];
 const nextStatus={pending:kind==='kitchen'?'preparing':'packed',preparing:'ready',ready:'served',packed:'shipped',shipped:'delivered',scheduled:'confirmed',confirmed:'completed'};
 const nextText={preparing:'Bắt đầu làm',ready:'Đã sẵn sàng',served:'Đã phục vụ',packed:'Đóng gói xong',shipped:'Đã giao vận',delivered:'Đã giao thành công',confirmed:'Xác nhận lịch',completed:'Hoàn tất'};
 const labels={pending:'Chờ xử lý',preparing:'Đang chuẩn bị',ready:'Sẵn sàng',served:'Đã phục vụ',packed:'Đã đóng gói',shipped:'Đang giao',delivered:'Đã giao',scheduled:'Mới đặt',confirmed:'Đã xác nhận',completed:'Hoàn tất',cancelled:'Đã hủy'};
 const orderLookup=new Map((s.cache.orders||[]).map(o=>[o.id,o]));
 let content='';
 if(kind==='inventory') content=items.map(x=>`<div class="task-item"><div class="task-icon">${I(x.delta>=0?'plus':'box','sm')}</div><div style="flex:1;min-width:0"><strong>${E(x.product_name)}</strong><div class="subtle">${E(x.reason)} • ${D(x.created_at)}</div></div><span class="pill ${x.delta>=0?'green':'yellow'}">${x.delta>0?'+':''}${x.delta}</span></div>`).join('');
 else content=items.map(x=>{const o=orderLookup.get(x.reference_id);const next=nextStatus[x.status];return `<article class="task-item industry-task"><div class="task-icon">${I(kind==='kitchen'?'coffee':kind==='delivery'?'box':'calendar','sm')}</div><div style="flex:1;min-width:0"><strong>${E(x.title)}</strong><div class="subtle">${kind==='appointments'?`${D(x.scheduled_at)} • ${E(x.assignee)}`:`${o?E(o.items.map(i=>i.name+' ×'+i.quantity).join(' · ')):'Mã đơn '+E(x.reference_id?.slice(0,8)||'—')}`}</div>${kind==='delivery'&&x.details?.carrier?`<div class="subtle">${E(x.details.carrier)} ${E(x.details.tracking_number||'')}</div>`:''}</div><div class="industry-actions"><span class="pill ${['ready','served','delivered','completed'].includes(x.status)?'green':'yellow'}">${E(labels[x.status]||x.status)}</span>${next?`<button class="btn sm secondary" data-action="industry-next" data-value="${E(x.id)}|${E(next)}">${E(nextText[next])}</button>`:''}${kind==='appointments'&&['scheduled','confirmed'].includes(x.status)?`<button class="btn sm ghost" data-action="industry-cancel" data-value="${E(x.id)}">Hủy lịch</button>`:''}</div></article>`}).join('');
 return `${section(name,subtitle,action?`<button class="btn" data-action="industry-new">${I('plus','sm')} ${action}</button>`:'')}<div class="surface pad"><div class="panel-title"><h3>${kind==='inventory'?'Lịch sử tồn kho':`${items.length} công việc`}</h3><span class="pill blue">${E(s.business.industry.toUpperCase())}</span></div><div class="task-list">${content||cardEmpty(kind==='inventory'?'warehouse':'calendar','Chưa có dữ liệu','Tạo đơn hoặc cập nhật nghiệp vụ để bắt đầu.')}</div></div>${kind==='inventory'?`<p class="subtle mt8">Để nhập, xuất hoặc kiểm kho, chọn “Sản phẩm” rồi “Kho”. Mọi biến động được lưu trong sổ.</p>`:kind==='delivery'?`<p class="subtle mt8">Đây là trạng thái tự ghi nhận, chưa tích hợp đơn vị vận chuyển hoặc đối soát COD.</p>`:''}`;
}
function newIndustryWork(){
 const kind=activeIndustry()[0],bid=s.business.id;
 if(kind==='kitchen'||kind==='delivery'){
  const existing=new Set((s.cache.industry||[]).map(x=>x.reference_id));
  const options=(s.cache.orders||[]).filter(o=>!existing.has(o.id)&&(kind==='kitchen'||(o.customer_id&&(s.cache.customers||[]).some(c=>c.id===o.customer_id&&c.address))));
  if(!options.length){toast(kind==='kitchen'?'Cần có đơn chưa chuyển bếp':'Cần có đơn với khách và địa chỉ giao',true);return}
  modal(kind==='kitchen'?'Gửi phiếu xuống bếp':'Tạo phiếu giao hàng',`<form id="industry-form"><div class="formfield"><label>Đơn hàng</label><select name="order_id" required>${options.map(o=>`<option value="${E(o.id)}">#${E(o.id.slice(0,8).toUpperCase())} • ${V(o.total_vnd)}</option>`).join('')}</select></div>${kind==='delivery'?`<div class="formrow"><div class="formfield"><label>Đơn vị vận chuyển (tùy chọn)</label><input name="carrier" placeholder="Giao nội bộ" maxlength="80"/></div><div class="formfield"><label>Mã vận đơn (tùy chọn)</label><input name="tracking_number" maxlength="100"/></div></div>`:''}<div class="formfield"><label>Ghi chú</label><input name="note" maxlength="300" placeholder="Hướng dẫn xử lý..."/></div>${submitFoot('Tạo phiếu')}</form>`);
  return;
 }
 if(kind==='appointments'){
  const services=(s.cache.products||[]).filter(p=>!p.track_stock&&p.active),customers=s.cache.customers||[];
  if(!services.length){toast('Cần tạo dịch vụ (tắt theo dõi kho) trước',true);return}
  if(!customers.length){toast('Cần thêm khách hàng trước',true);return}
  modal('Đặt lịch dịch vụ',`<form id="industry-form"><div class="formrow"><div class="formfield"><label>Dịch vụ</label><select name="product_id" required>${services.map(p=>`<option value="${E(p.id)}">${E(p.name)} • ${V(p.price_vnd)}</option>`).join('')}</select></div><div class="formfield"><label>Khách hàng</label><select name="customer_id" required>${customers.map(c=>`<option value="${E(c.id)}">${E(c.name)}</option>`).join('')}</select></div></div><div class="formfield"><label>Nhân viên phụ trách</label><input name="assignee" required maxlength="100" placeholder="Ví dụ: Kỹ thuật viên A"/></div><div class="formrow"><div class="formfield"><label>Giờ hẹn</label><input name="start_at" type="datetime-local" required/></div><div class="formfield"><label>Thời lượng (phút)</label><input name="duration_minutes" type="number" min="15" max="480" value="60" required/></div></div><div class="formfield"><label>Ghi chú</label><input name="note" maxlength="300"/></div>${submitFoot('Lưu lịch hẹn')}</form>`);
 }
}
function modal(title,body,wide=false){modalRoot.innerHTML=`<div class="overlay" data-overlay><div class="dialog ${wide?'wide':''}" role="dialog" aria-modal="true" aria-label="${E(title)}"><div class="modal-header"><h2>${E(title)}</h2><button class="close-btn" data-action="close-modal" aria-label="Đóng">${I('close')}</button></div>${body}</div></div>`;document.body.style.overflow='hidden';modalRoot.querySelector('input,select,textarea,button')?.focus()}
function closeModal(){modalRoot.innerHTML='';document.body.style.overflow=''}
function submitFoot(label){return `<div class="modal-footer"><button type="button" class="btn secondary" data-action="close-modal">Hủy</button><button class="btn" type="submit">${E(label)} ${I('arrow','sm')}</button></div>`}
function newProduct(){modal('Thêm sản phẩm mới',`<form id="product-form"><div class="formfield"><label>Tên sản phẩm</label><input name="name" placeholder="Ví dụ: Cà phê sữa" maxlength="150" required/></div><div class="formrow"><div class="formfield"><label>Mã sản phẩm (SKU)</label><input name="sku" placeholder="CF001" required maxlength="80"/></div><div class="formfield"><label>Danh mục</label><input name="category" placeholder="Đồ uống" value="Đồ uống" maxlength="80"/></div></div><div class="formrow"><div class="formfield"><label>Giá bán (đ)</label><input name="price_vnd" type="number" min="0" max="2000000000" required placeholder="35000"/></div><div class="formfield"><label>Giá vốn (đ)</label><input name="cost_vnd" type="number" min="0" max="2000000000" value="0"/></div></div><div class="formfield"><label>Số lượng tồn ban đầu</label><input type="number" name="stock" min="0" value="0"/></div><div class="subtle">Kho sẽ tự trừ khi tạo đơn. Với dịch vụ/đồ uống chưa áp dụng định lượng, có thể tắt theo dõi kho.</div><label style="display:flex;align-items:center;gap:8px;margin-top:13px"><input name="track_stock" type="checkbox" ${s.business?.industry==='fnb'?'':'checked'} style="width:auto"/> Theo dõi số lượng tồn</label>${submitFoot('Lưu sản phẩm')}</form>`)}
function newTable(preBranch=''){const branches=s.cache.branches||[];const selector=branches.length?`<div class="formfield"><label>Chi nhánh</label><select name="branch_id">${branches.map(b=>`<option value="${E(b.id)}" ${b.id===preBranch?'selected':''}>${E(b.name)}</option>`).join('')}</select></div>`:'';modal('Thêm bàn',`<form id="table-form">${selector}<div class="formfield"><label>Tên bàn</label><input name="label" required maxlength="80" placeholder="Bàn 01"/></div><div class="formfield"><label>Số chỗ ngồi</label><input name="seats" type="number" min="1" max="50" value="4" required/></div>${submitFoot('Tạo bàn')}</form>`)}
function newCustomer(){modal('Thêm khách hàng',`<form id="customer-form"><div class="formfield"><label>Tên khách hàng</label><input name="name" placeholder="Nguyễn Văn A" required/></div><div class="formfield"><label>Điện thoại (tùy chọn)</label><input name="phone" placeholder="09..." inputmode="tel"/></div><div class="formfield"><label>Địa chỉ (tùy chọn)</label><textarea name="address" rows="2" placeholder="Địa chỉ giao hàng..."></textarea></div>${submitFoot('Lưu khách hàng')}</form>`)}
function newBranch(){modal('Thêm chi nhánh',`<form id="branch-form"><div class="formfield"><label>Tên chi nhánh</label><input name="name" placeholder="Chi nhánh Quận 1" required/></div>${submitFoot('Thêm chi nhánh')}</form>`)}
function newOrder(preTable=''){const p=s.cache.products||[];if(!p.length){toast('Cần thêm sản phẩm trước khi tạo đơn',true);return newProduct()}
 const row=(idx=0)=>`<div class="order-line"><select name="product_id" aria-label="Sản phẩm">${p.map((x,i)=>`<option value="${E(x.id)}" data-price="${x.price_vnd}" ${i===idx?'selected':''}>${E(x.name)} — ${V(x.price_vnd)}</option>`).join('')}</select><input type="number" name="quantity" min="1" max="1000" value="1" required aria-label="Số lượng"/><button type="button" class="close-btn" data-action="remove-line" aria-label="Xóa dòng">${I('close','sm')}</button></div>`;
 const tables=s.cache.tables||[];const cust=s.cache.customers||[];modal('Tạo đơn bán hàng',`<form id="order-form" data-request-id="${(crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2))}"><div class="formrow"><div class="formfield"><label>Khách hàng</label><select name="customer_id"><option value="">Khách lẻ</option>${cust.map(c=>`<option value="${E(c.id)}">${E(c.name)}</option>`).join('')}</select></div><div class="formfield"><label>Bàn ${has('tables')?'':'(không áp dụng)'}</label><select name="table_id" ${has('tables')?'':'disabled'}><option value="">Mang đi / giao hàng</option>${tables.map(t=>`<option value="${E(t.id)}" ${t.id===preTable?'selected':''}>${E(t.label)}</option>`).join('')}</select></div></div><label>Chi tiết sản phẩm</label><div id="order-lines">${row()}</div><button type="button" class="btn sm secondary" data-action="add-line">${I('plus','sm')} Thêm món / sản phẩm</button><div class="formfield" style="margin-top:17px"><label>Ghi chú</label><textarea name="note" maxlength="300" rows="2" placeholder="Ghi chú cho đơn hàng..."></textarea></div><div class="summary-line"><strong>Tổng tiền hàng</strong><b id="order-total">${V(p[0].price_vnd)}</b></div><div class="subtle mt8">Giá bán và tồn kho sẽ được tính lại trên server. Chưa có tính thuế, phí giao hay thanh toán tự động.</div>${submitFoot('Tạo đơn')}</form>`,true);s.newOrderRow=row;updateOrderTotal()}
function updateOrderTotal(){const el=document.getElementById('order-total');if(!el)return;let sum=0;document.querySelectorAll('#order-lines .order-line').forEach(row=>{const selected=row.querySelector('select').selectedOptions[0];sum+=(Number(selected?.dataset.price)||0)*(Number(row.querySelector('input').value)||0)});el.textContent=V(sum)}
function adjustStock(id){const p=s.cache.products?.find(x=>x.id===id);if(!p)return;modal(`Điều chỉnh kho • ${p.name}`,`<form id="stock-form" data-id="${E(id)}"><div class="pill green" style="margin-bottom:16px">Tồn hiện tại: ${p.stock}</div><div class="formfield"><label>Thay đổi số lượng (+ nhập / - xuất)</label><input type="number" name="delta" value="1" min="-100000" max="100000" required/></div><div class="formfield"><label>Lý do điều chỉnh</label><input name="reason" placeholder="Nhập bổ sung / Hàng hỏng..." required minlength="4" maxlength="40"/></div>${submitFoot('Lưu điều chỉnh')}</form>`)}
function confirmPaid(id){const o=(s.cache.orderDashboard?.orders||s.cache.orders||[]).find(x=>x.id===id);if(!o||o.status!=='open')return;modal('Xác nhận đã nhận tiền',`<div style="text-align:center;padding:9px"><div class="empty-icon" style="margin:0 auto 15px">${I('wallet','xl')}</div><h3 style="font-size:23px">${V(o.total_vnd)}</h3><p class="muted">Chỉ xác nhận sau khi bạn thực sự đã nhận đủ tiền từ khách hàng. Hệ thống chưa tự đối soát ngân hàng.</p></div><div class="modal-footer"><button class="btn secondary" data-action="close-modal">Quay lại</button><button class="btn" data-action="mark-paid" data-value="${E(id)}">Xác nhận đã nhận tiền</button></div>`)}
function cancelOrder(id){
 const o=(s.cache.orderDashboard?.orders||s.cache.orders||[]).find(x=>x.id===id);
 if(!o||o.status!=='open')return;
 modal('Hủy đơn chưa thanh toán',`<form id="cancel-order-form" data-id="${E(id)}"><p class="muted">Chỉ được hủy trước khi bếp hoặc giao vận bắt đầu xử lý. Tồn kho đã trừ sẽ được hoàn lại. Không dùng chức năng này để hoàn tiền đơn đã thanh toán.</p><div class="formfield"><label>Lý do hủy</label><textarea name="reason" minlength="4" maxlength="250" required placeholder="Ví dụ: Khách yêu cầu hủy đơn"></textarea></div>${submitFoot('Xác nhận hủy đơn')}</form>`);
}
function switchBusiness(){modal('Chọn doanh nghiệp',`<div class="task-list">${s.businesses.map(x=>`<button class="task-item" data-action="select-business" data-value="${E(x.id)}" style="text-align:left;background:var(--merchant-panel,var(--paper,#fff));color:var(--merchant-ink,var(--ink))"><span class="b-avatar">${E(x.name[0].toUpperCase())}</span><span style="flex:1"><strong>${E(x.name)}</strong><div class="subtle">${E(x.plan)} • ${E(x.industry)}</div></span>${I('chevron','sm')}</button>`).join('')}</div><div class="divider"></div><button class="btn wide secondary" data-action="new-business">${I('plus','sm')} Tạo doanh nghiệp mới</button>`)}
function account(){modal('Tài khoản',`<div class="task-item"><span class="avatar">${E(s.user?.name?.[0]?.toUpperCase()||'E')}</span><div><strong>${E(s.user?.name)}</strong><p class="subtle mb0">${E(s.user?.email)}</p></div></div><div class="modal-footer"><button class="btn secondary" data-action="logout">${I('logout','sm')} ${s.demo?'Tạo phiên demo mới':'Đăng xuất'}</button></div>`)}
async function refresh(){await loadData();renderTab()}
async function handleAction(act,val,button){try{
 if(act==='auth-toggle'){s.authMode=s.authMode==='login'?'signup':'login';auth()}
 else if(act==='auth-resend-verification'){
   const email=document.querySelector('#auth-form [name=email]')?.value?.trim()||'';
   if(!email){toast('Nhập email cần xác minh trước',true);return}
   await api('/auth/resend-verification',{method:'POST',body:JSON.stringify({email})});
   toast('Nếu tài khoản cần xác minh, email mới sẽ được gửi.');
 }
 else if(act==='industry'){s.answers.industry=val;setup()}
 else if(act==='answer-toggle'){s.answers[val]=!s.answers[val];setup()}
 else if(act==='choose-plan'){s.answers.selected_plan=val;setup()}
 else if(act==='setup-back'){if(s.setupStep===1){await api('/auth/logout',{method:'POST'});s.user=null;s.csrf=null;auth()}else{s.setupStep--;setup()}}
 else if(act==='setup-next'){if(s.setupStep===1){let name=document.getElementById('biz-name')?.value?.trim()||'';if(name.length<2){toast('Vui lòng nhập tên doanh nghiệp',true);return}s.answers.name=name;}if(s.setupStep===2){s.recommendation=await api('/onboarding/recommend',{method:'POST',body:JSON.stringify(s.answers)});s.answers.selected_plan=s.recommendation.recommended_plan}if(s.setupStep<3){s.setupStep++;setup();return}const b=await api('/businesses',{method:'POST',body:JSON.stringify(s.answers)});s.businesses.push(b);s.business=b;s.tab=b.billing_required?(b.role==='owner'?'billing':'account_lock'):'overview';if(b.billing_required){s.cache={};if(b.role==='owner')s.cache.billing=await api('/businesses/'+encodeURIComponent(b.id)+'/billing');appFrame()}else{await refresh();appFrame()}toast('Đã tạo không gian làm việc')}
 else if(act==='tab'){
 if(s.business?.billing_required&&val!==(s.business.role==='owner'?'billing':'account_lock'))return;
 if(val==='orders')s.cache.orderDashboard=null;
 s.tab=val;history.pushState(null,'','/app?tab='+encodeURIComponent(val));appFrame();window.scrollTo(0,0)
}
 else if(act==='industry-new')newIndustryWork()
 else if(act==='industry-next'){const [id,status]=val.split('|');await api(`/businesses/${s.business.id}/industry/${activeIndustry()[0]}/${id}/status`,{method:'POST',body:JSON.stringify({status})});await refresh();toast('Đã cập nhật trạng thái')}
 else if(act==='industry-cancel'){modal('Hủy lịch hẹn',`<p class="muted">Anh/chị có chắc chắn muốn hủy lịch này? Thao tác sẽ mở lại khung giờ cho khách khác.</p><div class="modal-footer"><button class="btn secondary" data-action="close-modal">Quay lại</button><button class="btn" data-action="industry-cancel-confirm" data-value="${E(val)}">Xác nhận hủy</button></div>`)}
 else if(act==='industry-cancel-confirm'){await api(`/businesses/${s.business.id}/industry/appointments/${val}/status`,{method:'POST',body:JSON.stringify({status:'cancelled'})});closeModal();await refresh();toast('Đã hủy lịch')}
 else if(act==='public-order-review'){
   const [id,decision]=val.split('|');
   const label=decision==='accept'?'Duyệt yêu cầu đặt hàng':'Từ chối yêu cầu đặt hàng';
   modal(label,`<form id="public-order-review-form" data-id="${E(id)}" data-decision="${E(decision)}">
     <p class="muted">${decision==='accept'?'Chỉ duyệt khi đã kiểm tra yêu cầu khách. Khi duyệt, hệ thống tạo đơn chưa thanh toán và trừ kho.':'Yêu cầu bị từ chối sẽ không tạo đơn và không trừ kho.'}</p>
     <div class="formfield"><label>Ghi chú duyệt (không bắt buộc)</label>
     <textarea name="reason" maxlength="180" rows="2"></textarea></div>
     ${submitFoot(decision==='accept'?'Xác nhận tạo đơn':'Xác nhận từ chối')}</form>`);
 }
 else if(act==='lead-next'){
   const [id,status]=val.split('|');
   await api('/businesses/'+encodeURIComponent(s.business.id)+'/public-leads/'+encodeURIComponent(id)+'/status',
    {method:'POST',body:JSON.stringify({status})});
   s.cache.publicLeads=await api('/businesses/'+encodeURIComponent(s.business.id)+'/public-leads');
   renderTab();toast('Đã cập nhật yêu cầu');
 }
 else if(act==='team-revoke'){
   await api('/businesses/'+encodeURIComponent(s.business.id)+'/team/invitations/'+encodeURIComponent(val)+'/revoke',{method:'POST',body:'{}'});
   s.cache.team=await api('/businesses/'+encodeURIComponent(s.business.id)+'/team');renderTab();
   toast('Đã thu hồi lời mời');
 }
 else if(act==='team-remove'){
   modal('Xóa nhân viên',`<p>Nhân viên sẽ bị gỡ quyền khỏi doanh nghiệp này. Dữ liệu đơn hàng vẫn được lưu.</p>
    <div class="modal-footer"><button class="btn secondary" data-action="close-modal">Quay lại</button>
    <button class="btn" data-action="team-remove-confirm" data-value="${E(val)}">Xác nhận xóa</button></div>`);
 }
 else if(act==='team-remove-confirm'){
   await api('/businesses/'+encodeURIComponent(s.business.id)+'/team/members/'+encodeURIComponent(val),{method:'DELETE'});
   closeModal();s.cache.team=await api('/businesses/'+encodeURIComponent(s.business.id)+'/team');renderTab();
   toast('Đã gỡ quyền nhân viên');
 }
 else if(act==='team-copy-link'){
   const input=document.getElementById('ez-team-share-url');
   if(input){input.focus();input.select();try{await navigator.clipboard.writeText(input.value);toast('Đã sao chép lời mời')}catch(_){toast('Chọn và sao chép đường dẫn đang hiển thị')}}
 }
 else if(act==='billing-refresh'){
  const bid=s.business?.id;
  if(!bid)return;
  const [businesses,billing]=await Promise.all([
    api('/businesses'),api('/businesses/'+encodeURIComponent(bid)+'/billing')
  ]);
  s.businesses=businesses;
  s.business=businesses.find(x=>x.id===bid)||s.business;
  s.cache.billing=billing;
  if(!s.business.billing_required)await loadData();
  if(s.business.billing_required)s.tab='billing';
  appFrame();
  toast('Đã cập nhật trạng thái thanh toán');
 }
 else if(act==='billing-pay'){
  const channel=document.getElementById('billing-channel')?.value||'card';
  const result=await api('/businesses/'+encodeURIComponent(s.business.id)+'/billing/checkout',
    {method:'POST',body:JSON.stringify({plan:val,channel})});
  const url=new URL(result.redirect_url);
  if(url.origin!=='https://sandbox.vnpayment.vn'||url.pathname!=='/paymentv2/vpcpay.html')
    throw Error('Địa chỉ thanh toán không hợp lệ');
  window.location.assign(url.href);
 }
 else if(act==='billing-card-info'){
   modal('Thêm thẻ / Add card','<p>💳 Thẻ chỉ được nhập trên trang thanh toán bảo mật VNPAY sau khi chọn gói. EZ Thing không lưu số thẻ hay CVV.</p><p class="muted">Chức năng lưu thẻ cần merchant được cấp API token hóa riêng từ VNPAY; hiện chưa kích hoạt.</p><div class="modal-footer"><button class="btn" data-action="close-modal">Đóng</button></div>');
 }
 else if(act==='new-order')newOrder()
 else if(act==='new-product')newProduct()
 else if(act==='new-table')newTable()
 else if(act==='new-customer')newCustomer()
 else if(act==='new-branch')newBranch()
 else if(act==='table-order')newOrder(val)
 else if(act==='adjust-stock')adjustStock(val)
 else if(act==='confirm-paid')confirmPaid(val)
 else if(act==='cancel-order')cancelOrder(val)
 else if(act==='mark-paid'){await api(`/businesses/${s.business.id}/orders/${val}/paid`,{method:'POST',body:JSON.stringify({confirmed:true})});restaurantSuite?.invalidate();closeModal();await refresh();toast('Đã ghi nhận thanh toán thủ công')}
 else if(act==='order-filter'){s.orderFilter=val;await loadOrdersDashboard()}
 else if(act==='order-detail')orderDetails(val)
 else if(act==='order-reset'){s.orderDateFrom='';s.orderDateTo='';s.orderTableFilter='all';s.orderBranchFilter='all';s.orderFilter='all';s.orderSearch='';await loadOrdersDashboard()}
 else if(act==='close-modal')closeModal()
 else if(act==='switch-business')switchBusiness()
 else if(act==='profile')account()
 else if(act==='new-business'){closeModal();s.answers={name:'',industry:'fnb',need_tables:true,need_inventory:true,need_insights:true,need_branches:false,description:'',selected_plan:'PLUS'};s.setupStep=1;setup()}
 else if(act==='select-business'){const b=s.businesses.find(x=>x.id===val);if(!b)return;
 s.business=b;s.tab=b.billing_required?(b.role==='owner'?'billing':'account_lock'):'overview';
 restaurantSuite?.invalidate();closeModal();s.cache={};
 history.replaceState(null,'','/app?tab='+s.tab);
 if(b.billing_required){if(b.role==='owner')s.cache.billing=await api('/businesses/'+encodeURIComponent(b.id)+'/billing');appFrame()}
 else{await refresh();appFrame()}
}
 else if(act==='logout'){const wasDemo=s.demo;await api('/auth/logout',{method:'POST'});closeModal();s.user=null;s.csrf=null;s.demo=false;s.business=null;s.businesses=[];s.cache={};s.authMode='login';if(wasDemo){await start()}else{auth();toast('Đã đăng xuất')}}
 else if(act==='add-line'){const wrap=document.getElementById('order-lines');if(wrap){wrap.insertAdjacentHTML('beforeend',s.newOrderRow());updateOrderTotal()}}
 else if(act==='remove-line'){const lines=document.querySelectorAll('#order-lines .order-line');if(lines.length>1){button.closest('.order-line')?.remove();updateOrderTotal()}else toast('Đơn phải có ít nhất một sản phẩm',true)}
 }catch(e){toast(e.message||'Có lỗi xảy ra',true)} }
async function handleSubmit(form){const bid=s.business?.id;const data=Object.fromEntries(new FormData(form).entries());const btn=form.querySelector('[type="submit"]');if(btn?.disabled)return; if(btn)btn.disabled=true;
 try{
 if(form.id==='auth-form'){
   const resp=await api('/auth/'+(s.authMode==='login'?'login':'signup'),{method:'POST',body:JSON.stringify(data)});
   if(resp.verification_required){
     s.authMode='login';
     s.emailVerificationNotice='Đã gửi email xác minh. Mở link trong email trước khi đăng nhập.';
     auth();
     toast('Vui lòng kiểm tra email để kích hoạt tài khoản');
     return;
   }
   s.emailVerificationNotice='';
   s.user=resp;s.csrf=resp.csrf_token;
   await afterAuth();return;
 }
 if(form.id==='public-order-review-form'){
   const id=form.dataset.id,action=form.dataset.decision;
   await api('/businesses/'+encodeURIComponent(bid)+'/order-requests/'+encodeURIComponent(id)+'/review',{
     method:'POST',body:JSON.stringify({action,reason:data.reason||''})
   });
   s.cache.orderRequests=await api('/businesses/'+encodeURIComponent(bid)+'/order-requests');
   s.cache.orderDashboard=null;
   await loadData();
   closeModal();renderTab();
   toast(action==='accept'?'Đã duyệt: tạo đơn và đồng bộ kho':'Đã từ chối yêu cầu');
   return;
 }
 if(form.id==='site-publish-form'){
   const result=await api('/businesses/'+encodeURIComponent(bid)+'/publishing',{
      method:'PUT',body:JSON.stringify({slug:data.slug.trim(),published:form.querySelector('[name=published]').checked})
   });
   s.cache.publishing=result;renderTab();
   toast(result.published?'Website đã công khai':'Đã lưu website ở chế độ riêng tư');
   return;
 }
 if(form.id==='team-invite-form'){
   const created=await api('/businesses/'+encodeURIComponent(bid)+'/team/invitations',{
     method:'POST',body:JSON.stringify({email:data.email,role:data.role})
   });
   s.cache.team=await api('/businesses/'+encodeURIComponent(bid)+'/team');
   renderTab();
   const link=new URL(created.invite_url,window.location.origin).href;
   modal('Chia sẻ lời mời',`<p>Link chỉ hiển thị một lần. Hãy gửi riêng cho ${E(created.email)}.</p>
      <div class="formfield"><label>Link tham gia</label><input id="ez-team-share-url" readonly value="${E(link)}"/></div>
      <div class="modal-footer"><button class="btn secondary" data-action="close-modal">Đóng</button>
      <button class="btn" data-action="team-copy-link">Sao chép link</button></div>`);
   return;
 }
 if(form.id==='product-form'){await api(`/businesses/${bid}/products`,{method:'POST',body:JSON.stringify({name:data.name,sku:data.sku,category:data.category,price_vnd:Number(data.price_vnd),cost_vnd:Number(data.cost_vnd||0),stock:Number(data.stock||0),track_stock:form.querySelector('[name=track_stock]').checked})});toast('Đã thêm sản phẩm')}
 else if(form.id==='table-form'){await api(`/businesses/${bid}/tables`,{method:'POST',body:JSON.stringify({label:data.label,seats:Number(data.seats),branch_id:data.branch_id||null})});restaurantSuite?.invalidate();toast('Đã thêm bàn')}
 else if(form.id==='customer-form'){await api(`/businesses/${bid}/customers`,{method:'POST',body:JSON.stringify(data)});toast('Đã thêm khách hàng')}
 else if(form.id==='branch-form'){await api(`/businesses/${bid}/branches`,{method:'POST',body:JSON.stringify(data)});toast('Đã thêm chi nhánh')}
 else if(form.id==='stock-form'){await api(`/businesses/${bid}/products/${form.dataset.id}/stock`,{method:'POST',body:JSON.stringify({delta:Number(data.delta),reason:data.reason})});toast('Đã cập nhật tồn kho')}
 else if(form.id==='industry-form'){const kind=activeIndustry()[0];const body=kind==='appointments'?{customer_id:data.customer_id,product_id:data.product_id,assignee:data.assignee,start_at:new Date(data.start_at).toISOString(),duration_minutes:Number(data.duration_minutes),note:data.note||''}:{order_id:data.order_id,carrier:data.carrier||'',tracking_number:data.tracking_number||'',note:data.note||''};await api(`/businesses/${bid}/industry/${kind}`,{method:'POST',body:JSON.stringify(body)});toast('Đã tạo công việc')}
 else if(form.id==='cancel-order-form'){await api(`/businesses/${bid}/orders/${form.dataset.id}/cancel`,{method:'POST',body:JSON.stringify({confirmed:true,reason:data.reason})});restaurantSuite?.invalidate();toast('Đã hủy đơn và hoàn tồn kho')}
 else if(form.id==='order-form'){const lines=[...form.querySelectorAll('.order-line')].map(row=>({product_id:row.querySelector('select').value,quantity:Number(row.querySelector('input').value)}));const assigned=s.cache.tables?.find(t=>t.id===data.table_id);await api(`/businesses/${bid}/orders`,{method:'POST',body:JSON.stringify({idempotency_key:form.dataset.requestId,customer_id:data.customer_id||null,table_id:data.table_id||null,branch_id:assigned?.branch_id||null,lines,note:data.note||''})});restaurantSuite?.invalidate();toast('Đã tạo đơn hàng')}
 else return;
 closeModal();await refresh();
 }catch(e){toast(e.message||'Không lưu được dữ liệu',true)}finally{if(btn)btn.disabled=false}}
async function afterAuth(){
 const cfg=await api('/config');s.trialEnabled=!!cfg.trial_enabled;
 const invite=new URLSearchParams(window.location.search).get('invite');
 if(invite){
   try{
     const accepted=await api('/team/accept',{method:'POST',body:JSON.stringify({token:invite})});
     toast('Đã gia nhập doanh nghiệp với vai trò '+accepted.role);
   }catch(error){toast(error.message||'Lời mời không hợp lệ hoặc email đăng nhập không trùng',true)}
   history.replaceState(null,'','/app');
 }
 s.businesses=await api('/businesses');
 if(!s.businesses.length){s.setupStep=1;setup();return}
 const current=s.businesses.find(b=>b.id===s.business?.id);
 s.business=current||(s.demo?s.businesses.find(b=>b.industry==='fnb'):null)||s.businesses[0];
 s.tab=new URLSearchParams(location.search).get('tab')||'overview';
 if(s.business.billing_required){
   s.tab=s.business.role==='owner'?'billing':'account_lock';s.cache={};
   if(s.business.role==='owner')s.cache.billing=await api('/businesses/'+encodeURIComponent(s.business.id)+'/billing');
 }else{
   if(!menuItems().some(x=>x[0]===s.tab))s.tab='overview';
   await loadData();
 }
 appFrame();
}
async function start(){
 const rawVerifyToken=new URLSearchParams(location.hash.slice(1)).get('verify')||new URLSearchParams(location.search).get('verify');
 const wantsVerification=!!rawVerifyToken;
 if(wantsVerification){
   // Clear token from history immediately so no later navigation/reload leaks it.
   history.replaceState(null,'','/app');
   try{
     await api('/auth/verify-email',{method:'POST',body:JSON.stringify({token:rawVerifyToken})});
     s.emailVerificationNotice='Email đã xác minh. Bạn có thể đăng nhập.';
   }catch(error){
     s.emailVerificationNotice=error.message||'Link xác minh không hợp lệ hoặc hết hạn.';
   }
 }
 let me;
 try{me=await api('/auth/me')}catch(e){
   if(e.status!==401){toast('Không kết nối được máy chủ: '+e.message,true);auth();return}
 }
 const wantsTrial=new URLSearchParams(location.search).get('trial')==='1';
 const wantsInvite=new URLSearchParams(location.search).has('invite');
 if(me&&me.demo&&(wantsTrial||wantsInvite||wantsVerification)){
   s.user=me;s.csrf=me.csrf_token;
   await api('/auth/logout',{method:'POST'});
   s.user=null;s.csrf=null;s.demo=false;s.authMode='signup';
   const cfg=await api('/config');s.trialEnabled=!!cfg.trial_enabled;
   auth();return;
 }
 if(me){s.user=me;s.csrf=me.csrf_token;s.demo=!!me.demo;await afterAuth();return}
 try{
   const config=await api('/config');
   s.trialEnabled=!!config.trial_enabled;
   if(config.demo_enabled&&!wantsTrial&&!wantsInvite&&!wantsVerification){
     const guest=await api('/auth/demo',{method:'POST'});
     s.user=guest;s.csrf=guest.csrf_token;s.demo=!!guest.demo;
     await afterAuth();return;
   }
 }catch(e){toast('Không mở được chế độ demo: '+e.message,true)}
 if(wantsTrial)s.authMode='signup';
 if(wantsVerification)s.authMode='login';
 if(new URLSearchParams(location.search).has('invite'))s.authMode='login';
 auth();
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-action]');if(b){e.preventDefault();handleAction(b.dataset.action,b.dataset.value||'',b)}else if(e.target.matches('[data-overlay]'))closeModal()});
document.addEventListener('submit',e=>{if(e.target.matches('form')){e.preventDefault();handleSubmit(e.target)}});
document.addEventListener('input',e=>{
 if(e.target.matches('[data-order-search]')){
  s.orderSearch=e.target.value;
  document.querySelectorAll('#order-rows [data-match]').forEach(row=>row.classList.toggle('hide',!row.dataset.match.includes(s.orderSearch.toLocaleLowerCase('vi'))));
 }
 if(e.target.closest('#order-lines'))updateOrderTotal();if(e.target.matches('[data-search]')){const query=e.target.value.toLowerCase().trim();document.querySelectorAll(e.target.dataset.search+' [data-match]').forEach(el=>el.classList.toggle('hide',!el.dataset.match.includes(query)))}});
document.addEventListener('change',e=>{
 if(e.target.matches('[data-team-role]')){
   const id=e.target.dataset.teamRole;
   api('/businesses/'+encodeURIComponent(s.business.id)+'/team/members/'+encodeURIComponent(id),{
      method:'PATCH',body:JSON.stringify({role:e.target.value})
   }).then(()=>api('/businesses/'+encodeURIComponent(s.business.id)+'/team'))
     .then(data=>{s.cache.team=data;renderTab();toast('Đã cập nhật phân quyền')})
     .catch(error=>{toast(error.message,true);s.cache.team=null;loadData().then(()=>renderTab())});
   return;
 }
 if(e.target.closest('#order-lines'))updateOrderTotal();
 const kind=e.target.dataset.orderFilter;
 if(kind){
  if(kind==='from')s.orderDateFrom=e.target.value;
  else if(kind==='to')s.orderDateTo=e.target.value;
  else if(kind==='branch'){s.orderBranchFilter=e.target.value;s.orderTableFilter='all';}
  else if(kind==='table')s.orderTableFilter=e.target.value;
  loadOrdersDashboard().catch(err=>toast(err.message,true));
 }
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});window.addEventListener('online',setOnline);window.addEventListener('offline',setOnline);
if('serviceWorker' in navigator && location.protocol==='https:')navigator.serviceWorker.register('/sw.js').catch(()=>{});
start();
})();