(()=>{
'use strict';
const root=document.getElementById('admin-root');
const modal=document.getElementById('admin-modal');
const toastArea=document.getElementById('admin-toast');
const tabs={overview:['◈','Tổng quan'],businesses:['▦','Doanh nghiệp'],users:['♙','Tài khoản'],plans:['◇','Gói dịch vụ'],audit:['≡','Nhật ký'],system:['⚙','Hệ thống']};
const industryNames={fnb:'Nhà hàng & Cafe',retail:'Bán lẻ',online:'Bán hàng online',services:'Dịch vụ / Wellness'};
const actionLabels={'business.plan_changed':'Đổi gói doanh nghiệp','business.suspended':'Tạm khóa doanh nghiệp','business.resumed':'Khôi phục doanh nghiệp','user.blocked':'Khóa tài khoản','user.unblocked':'Mở khóa tài khoản','admin.unlocked':'Mở khóa quản trị','admin.locked':'Khóa quản trị'};
const features={dashboard:'Tổng quan',products:'Sản phẩm',orders:'Đơn hàng',tables:'Sơ đồ bàn',inventory_basic:'Kho cơ bản',inventory_adjust:'Điều chỉnh kho',insights:'Báo cáo',multi_branch:'Nhiều chi nhánh',kitchen:'Bếp / pha chế',stock_ledger:'Sổ kho',fulfillment:'Giao vận',appointments:'Lịch hẹn'};
let session=null;
let mode='gate';
let activeTab='overview';
let cache={};
let preview=null;
let offset={businesses:0,users:0,audit:0};
let filters={businesses:{q:'',industry:'',plan:'',status:'all'},users:{q:'',status:'all'},audit:{action:''}};
let busy=false;
let modalOpen=false;
const h=x=>String(x??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const fnum=n=>new Intl.NumberFormat(window.EZI18N?.locale()||'vi-VN').format(Number(n||0));
const fvnd=n=>fnum(n)+' đ';
const fdate=x=>{if(!x)return '—';const d=new Date(x);return Number.isNaN(d.getTime())?'—':new Intl.DateTimeFormat(window.EZI18N?.locale()||'vi-VN',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(d)};
const asStatus=blocked=>`<span class="status ${blocked?'off':''}">${blocked?'Tạm khóa':'Hoạt động'}</span>`;
const asPlan=p=>`<span class="pill ${h(p)}">${h(p||'—')}</span>`;
const empty=(title='Chưa có dữ liệu',msg='Chưa có bản ghi nào phù hợp với bộ lọc.')=>`<div class="empty"><div class="glyph">⌁</div><strong>${h(title)}</strong><p>${h(msg)}</p></div>`;
const toast=(msg,error=false)=>{const node=document.createElement('div');node.className='toast'+(error?' error':'');node.textContent=msg;toastArea.append(node);setTimeout(()=>node.remove(),3500)};
async function api(path,{method='GET',body=null}={}){
 const headers={'Accept':'application/json','Accept-Language':window.EZI18N?.language()||'vi'};
 if(body!==null)headers['Content-Type']='application/json';
 if(method!=='GET'&&session?.csrf_token)headers['x-csrf-token']=session.csrf_token;
 let res;
 try{res=await fetch(path,{method,headers,credentials:'same-origin',cache:'no-store',body:body===null?undefined:JSON.stringify(body)});}catch{throw new Error('Không kết nối được máy chủ. Vui lòng thử lại.')}
 let data={};try{data=await res.json()}catch{}
 if(!res.ok){const detail=data.detail;if(res.status===401||res.status===403&&/mở khóa phiên|quản trị/.test(String(detail||''))){}throw new Error(typeof detail==='string'?detail:`Máy chủ trả lỗi ${res.status}`)}
 return data;
}
function setAuth(kind,msg=''){
 mode='gate';cache={};session=null;
 const options=kind==='unlock';
 root.innerHTML=`<div class="auth-page"><div class="auth-art"><div><a class="logo admin-ez-logo ez-identity" href="/"><img class="ez-mark ez-mark-dark" src="/assets/icons/ez-mark-dark.svg?v=black-e-04" alt="" decoding="async"><em>Thing</em></a><div class="subbrand" style="padding:7px 0 0">PLATFORM CONTROL</div></div><div><span class="auth-pill">✦ Private workspace</span><h1>Điều hành nền tảng. Có kiểm soát.</h1><p>Quản trị doanh nghiệp, tài khoản, gói quyền truy cập và nhật ký thay đổi trên cùng một giao diện. Các thao tác quan trọng đều được xác nhận và lưu vết.</p></div><span class="muted small">EZ Thing v0.4 · Staging &nbsp; / &nbsp; Phân quyền máy chủ</span></div><div class="auth-side"><span class="chip">${options?'BƯỚC 2 / 2':'QUẢN TRỊ HỆ THỐNG'}</span><h2>${options?'Mở khóa phiên quản trị':'Đăng nhập Super Admin'}</h2><p class="muted small">${options?'Phiên đăng nhập đã được xác minh. Nhập mã bảo vệ quản trị đã cấu hình trên máy chủ. Phiên mở khóa chỉ có hiệu lực 30 phút.':'Sử dụng tài khoản quản trị được cấp quyền riêng. Tài khoản DEMO không có quyền thao tác quản trị.'}</p>${msg?`<div class="alert">${h(msg)}</div>`:''}<form class="auth-form" id="${options?'unlock-form':'login-form'}">${options?`<label class="field"><span>MÃ MỞ KHÓA QUẢN TRỊ</span><input name="access_key" type="password" minlength="32" autocomplete="off" required placeholder="Nhập mã bảo vệ..."/></label>`:`<label class="field"><span>EMAIL QUẢN TRỊ</span><input name="email" type="email" autocomplete="username" required placeholder="admin@..."/></label><label class="field"><span>MẬT KHẨU</span><input name="password" type="password" autocomplete="current-password" required placeholder="••••••••••"/></label>`}<button class="btn primary full" type="submit">${options?'Mở khóa quyền quản trị':'Tiếp tục đăng nhập'} <span aria-hidden="true">→</span></button></form><div class="auth-links"><button class="btn outline" type="button" data-action="demo">◈ Xem bản DEMO quản trị</button>${options?'<button class="btn light" type="button" data-action="switch-account">Đổi tài khoản</button>':''}</div><div class="safe-banner" style="margin-top:28px"><strong>🔐 Quyền truy cập được kiểm soát</strong><br>Đăng nhập + danh sách email được phép + mã bảo vệ bổ sung. Không mở quyền Super Admin cho khách DEMO.</div><p class="note" style="margin-top:21px">Chưa cấu hình quản trị? Chủ hệ thống cần thiết lập <strong>EZ_THING_SUPERADMIN_EMAILS</strong> và <strong>EZ_THING_ADMIN_ACCESS_KEY</strong> trong môi trường Render.</p><div class="auth-links"><a href="/">← Về website EZ Thing</a><a href="/app">Khu quản lý doanh nghiệp ↗</a></div></div></div>`;
}
async function init(){
 try{const d=await api('/api/admin/session');session=d;if(!d.unlocked){setAuth('unlock');session=d;return}mode='live';await showTab('overview');}
 catch(e){setAuth('login',e.message.includes('Không có quyền')?'Tài khoản hiện tại không có quyền Super Admin. Dùng tài khoản được cấp quyền để đăng nhập.':e.message.includes('chưa được cấu hình')?'Máy chủ chưa cấu hình quyền quản trị thật. Vẫn có thể mở bản DEMO để kiểm tra giao diện.':'');}
}
function navButton(id,compact=false){let [ico,name]=tabs[id];return `<button type="button" class="${compact?'':'navitem '}${activeTab===id?'active':''}" data-action="tab" data-tab="${id}" aria-label="${h(name)}"><span class="ico">${ico}</span>${compact?`<span>${h(name)}</span>`:h(name)}</button>`;}
function shell(title,subtitle){
 root.innerHTML=`${mode==='demo'?'<div class="demo-strip">✳ CHẾ ĐỘ XEM TRƯỚC — Toàn bộ số liệu là giả lập, không có quyền thay đổi dữ liệu thật. <button class="btn light" data-action="exit-demo" style="min-height:26px;padding:4px 9px">Đăng nhập quản trị</button></div>':''}<div class="shell"><aside class="sidebar"><a class="logo admin-ez-logo ez-identity" href="/"><img class="ez-mark ez-mark-dark" src="/assets/icons/ez-mark-dark.svg?v=black-e-04" alt="" decoding="async"><em>Thing</em></a><div class="subbrand">PLATFORM CONTROL</div><nav class="sidenav">${Object.keys(tabs).map(id=>navButton(id)).join('')}</nav><div class="side-bottom"><button class="navitem" data-action="${mode==='demo'?'exit-demo':'lock'}"><span class="ico">⌁</span>${mode==='demo'?'Thoát DEMO':'Khóa phiên quản trị'}</button><a class="navitem" href="/app"><span class="ico">↗</span>Khu quản lý</a><div class="side-user"><div class="avatar">${mode==='demo'?'D':h((session?.name||'A')[0].toUpperCase())}</div><div><strong>${mode==='demo'?'Tài khoản minh họa':h(session?.name||'Super Admin')}</strong><span>${mode==='demo'?'Chỉ xem dữ liệu giả':'Super Admin · Phiên 30 phút'}</span></div></div></div></aside><div class="workspace"><header class="topbar"><div><div class="eyebrow">EZ THING / PLATFORM</div><h1>${h(title)}</h1></div><div class="top-actions"><span class="admin-tag ${mode==='demo'?'demo':''}">${mode==='demo'?'● DEMO':'● ĐÃ XÁC THỰC'}</span><button data-action="refresh" type="button" class="btn outline hide-mobile" aria-label="Tải lại dữ liệu">↻ Làm mới</button></div></header><main class="main" id="admin-content"><div class="boot" style="min-height:350px"><div class="spinner"></div></div></main></div></div><nav class="mobile-nav" aria-label="Điều hướng quản trị">${Object.keys(tabs).map(id=>navButton(id,true)).join('')}</nav>`;
 const c=document.getElementById('admin-content');if(c)c.setAttribute('aria-busy','true');
}
const head=(title,subtitle='',right='')=>`<div class="heading"><div><h2>${h(title)}</h2><p>${h(subtitle)}</p></div>${right}</div>`;
function loadError(msg){const p=document.getElementById('admin-content');if(p)p.innerHTML=`${head('Không thể tải dữ liệu')}<div class="alert">${h(msg)}</div><button class="btn outline" style="margin-top:15px" data-action="refresh">↻ Thử lại</button>`;}
function useData(name){if(mode==='demo')return preview[name];return cache[name];}
async function getData(name,url){if(mode==='demo')return preview[name];return await api(url)}
function demoList(items,selection,limit=25){let rows=(items||[]).slice();const q=(selection.q||'').trim().toLowerCase();if(q)rows=rows.filter(x=>[x.name,x.email,x.owner?.email].some(t=>String(t||'').toLowerCase().includes(q)));if(selection.industry)rows=rows.filter(x=>x.industry===selection.industry);if(selection.plan)rows=rows.filter(x=>x.plan===selection.plan);if(selection.status==='active')rows=rows.filter(x=>!x.suspended);if(selection.status==='suspended')rows=rows.filter(x=>x.suspended);return {items:rows,total:rows.length,offset:0,limit}}
async function showTab(tab){
 if(!tabs[tab])tab='overview';activeTab=tab;
 const title=tabs[tab][1];shell(title);
 try{
  let data;
  if(tab==='overview'){data=await getData('overview','/api/admin/overview');if(mode==='demo')data={...data,recent_actions:preview.audit||[]};}
  else if(tab==='businesses')data=mode==='demo'?demoList(preview.businesses,filters.businesses):await api('/api/admin/businesses'+qs({...filters.businesses,limit:25,offset:offset.businesses}));
  else if(tab==='users')data=mode==='demo'?demoList(preview.users,filters.users):await api('/api/admin/users'+qs({...filters.users,limit:25,offset:offset.users}));
  else if(tab==='plans')data=mode==='demo'?{items:Object.entries(preview.plans).map(([id,x])=>({id,...x})),billing_live:false}:await api('/api/admin/plans');
  else if(tab==='audit')data=mode==='demo'?{items:preview.audit,total:preview.audit.length,offset:0,limit:50}:await api('/api/admin/audit'+qs({...filters.audit,limit:50,offset:offset.audit}));
  else data=await getData('system','/api/admin/system');
  if(activeTab!==tab)return;
  cache[tab]=data;
  const out=document.getElementById('admin-content');if(!out)return;
  out.innerHTML={overview:renderOverview,businesses:renderBusinesses,users:renderUsers,plans:renderPlans,audit:renderAudit,system:renderSystem}[tab](data);
  out.setAttribute('aria-busy','false');
 }catch(e){loadError(e.message);if(/mở khóa phiên/.test(e.message)){setAuth('unlock');session=await api('/api/auth/me').catch(()=>null);}}
}
function qs(params){const u=new URLSearchParams();for(const [k,v] of Object.entries(params||{}))if(v!==''&&v!==undefined)u.set(k,v);const s=u.toString();return s?'?'+s:''}
function renderOverview(d){
 const total=Number(d.businesses||0),plans=d.plans||{};
 const metrics=[['Doanh nghiệp',d.businesses,'◈','Tổng số đơn vị đang đăng ký'],['Người dùng',d.users,'♙','Không tính tài khoản DEMO'],['Đơn hàng',d.orders,'▤','Đơn nghiệp vụ pilot'],['Đang hoạt động',d.active_businesses,'✓',`${fnum(d.suspended_businesses||0)} doanh nghiệp tạm khóa`]];
 const stats=metrics.map(([label,n,ico,caption])=>`<div class="stat"><div class="stat-top"><span>${h(label)}</span><span class="stat-icon">${ico}</span></div><strong class="mono">${fnum(n)}</strong><div class="stat-caption">${h(caption)}</div></div>`).join('');
 const lines=Object.entries(plans).map(([k,v])=>`<div class="plan-row"><strong>${h(k)}</strong><div class="progress-track"><div style="width:${Math.min(100,Number(v)/Math.max(total,1)*100)}%"></div></div><strong class="mono">${fnum(v)}</strong></div>`).join('');
 const events=d.recent_actions||[];
 return `${head('Tổng quan nền tảng','Tình hình vận hành các doanh nghiệp và người dùng trong EZ Thing.','<button class="btn light" data-action="tab" data-tab="businesses">Xem doanh nghiệp →</button>')}<div class="warning-banner"><span>ⓘ</span><div><strong>${mode==='demo'?'Dữ liệu giả lập — không phản ánh hệ thống thật':'Môi trường pilot — chưa có hệ thống thu phí'}</strong><p>${h(d.notice||'Giá gói chỉ là đề xuất. Chưa tính doanh thu thuê bao hoặc MRR thực tế.')}</p></div></div><div class="stats">${stats}</div><div class="layout-two"><section class="panel"><div class="panel-header"><h3>Phân bổ gói quản lý</h3><span class="muted">Theo doanh nghiệp</span></div>${lines}<div class="section-hint">Các gói hiện cấp quyền dùng thử. Không đồng nghĩa đã thanh toán.</div></section><section class="panel"><div class="panel-header"><h3>Hoạt động quản trị gần đây</h3><button class="btn light" data-action="tab" data-tab="audit">Tất cả →</button></div>${events.length?`<div class="timeline">${events.map(x=>timelineRow(x)).join('')}</div>`:empty('Chưa có thao tác','Thao tác quản trị được ghi nhật ký tại đây.')}</section></div>`;
}
function timelineRow(x){return `<div class="timeline-item"><span class="timeline-dot">✓</span><div><strong>${h(actionLabels[x.action]||x.action)}</strong><p>${h(x.reason||'Hoạt động quản trị')} · ${h(fdate(x.created_at))}</p></div></div>`}
function tablePagination(data,what){const page=Math.floor(Number(data.offset||0)/Number(data.limit||25))+1,maxPage=Math.max(1,Math.ceil(Number(data.total||0)/Number(data.limit||25)));return `<div class="pager"><span>Tìm thấy <strong>${fnum(data.total)}</strong> bản ghi · Trang ${page}/${maxPage}</span><div class="flex-wrap"><button class="btn outline" data-action="page" data-entity="${what}" data-delta="-1" ${page<=1?'disabled':''}>← Trước</button><button class="btn outline" data-action="page" data-entity="${what}" data-delta="1" ${page>=maxPage?'disabled':''}>Tiếp →</button></div></div>`}
function renderBusinesses(d){const items=d.items||[];return `${head('Quản lý doanh nghiệp','Tìm kiếm, kiểm tra thông tin, đổi gói pilot hoặc tạm khóa có xác nhận.')}${mode==='demo'?'<div class="warning-banner">ⓘ &nbsp; Các doanh nghiệp dưới đây đều là dữ liệu mẫu. Mọi chức năng ghi dữ liệu đã bị vô hiệu hóa.</div>':''}<form class="filters" id="filter-businesses"><input class="search-field" name="q" aria-label="Tìm doanh nghiệp" placeholder="⌕ Tìm theo tên doanh nghiệp" value="${h(filters.businesses.q)}"/><select class="search-select" name="industry" aria-label="Ngành"><option value="">Tất cả ngành</option>${Object.entries(industryNames).map(([k,v])=>`<option value="${k}" ${filters.businesses.industry===k?'selected':''}>${h(v)}</option>`).join('')}</select><select class="search-select" name="plan" aria-label="Gói"><option value="">Mọi gói</option>${['BASIC','PLUS','PRO'].map(k=>`<option value="${k}" ${filters.businesses.plan===k?'selected':''}>${k}</option>`).join('')}</select><select class="search-select" name="status" aria-label="Trạng thái">${[['all','Mọi trạng thái'],['active','Đang hoạt động'],['suspended','Tạm khóa']].map(([k,v])=>`<option value="${k}" ${filters.businesses.status===k?'selected':''}>${v}</option>`).join('')}</select><button class="btn primary">Lọc dữ liệu</button></form>${items.length?`<div class="table-wrap"><table class="data-table business-table"><thead><tr><th>Doanh nghiệp</th><th>Ngành</th><th>Gói</th><th>Trạng thái</th><th>Ngày tạo</th><th></th></tr></thead><tbody>${items.map(b=>`<tr><td><div class="namecell"><span class="mini-avatar">${h((b.name||'B').slice(0,1).toUpperCase())}</span><div><strong>${h(b.name)}</strong><span>${h(b.owner?.email||'Không có chủ sở hữu')}</span></div></div></td><td>${h(industryNames[b.industry]||b.industry)}</td><td>${asPlan(b.plan)}</td><td>${asStatus(b.suspended)}</td><td>${h(fdate(b.created_at))}</td><td><button class="btn light" data-action="detail" data-type="business" data-id="${h(b.id)}">Chi tiết →</button></td></tr>`).join('')}</tbody></table></div>`:empty()}${tablePagination(d,'businesses')}`}
function renderUsers(d){const items=d.items||[];return `${head('Tài khoản người dùng','Quản trị quyền truy cập, xem doanh nghiệp tham gia và thu hồi phiên đăng nhập khi cần.')}${mode==='demo'?'<div class="warning-banner">ⓘ &nbsp; Danh sách mẫu không chứa dữ liệu khách hàng thật.</div>':''}<form class="filters" id="filter-users"><input class="search-field" name="q" placeholder="⌕ Tên hoặc email người dùng" aria-label="Tìm người dùng" value="${h(filters.users.q)}"/><select class="search-select" name="status" aria-label="Trạng thái">${[['all','Mọi trạng thái'],['active','Đang hoạt động'],['suspended','Tạm khóa']].map(([k,v])=>`<option value="${k}" ${filters.users.status===k?'selected':''}>${v}</option>`).join('')}</select><button class="btn primary">Tìm kiếm</button></form>${items.length?`<div class="table-wrap"><table class="data-table user-table"><thead><tr><th>Người dùng</th><th>Doanh nghiệp</th><th>Trạng thái</th><th>Ngày tạo</th><th></th></tr></thead><tbody>${items.map(u=>`<tr><td><div class="namecell"><span class="mini-avatar">${h((u.name||'U').slice(0,1).toUpperCase())}</span><div><strong>${h(u.name)}</strong><span>${h(u.email)}</span></div></div></td><td>${fnum(u.business_count||0)}</td><td>${asStatus(u.suspended)}</td><td>${h(fdate(u.created_at))}</td><td><button class="btn light" data-action="detail" data-type="user" data-id="${h(u.id)}">Chi tiết →</button></td></tr>`).join('')}</tbody></table></div>`:empty()}${tablePagination(d,'users')}`}
function renderPlans(d){return `${head('Gói dịch vụ','Quyền sử dụng và giới hạn của từng gói thử nghiệm.')}${!d.billing_live?'<div class="warning-banner"><span>ⓘ</span><div><strong>Chưa thu tiền thuê bao</strong><p>Bảng giá chỉ là đề xuất. Đổi gói trong /admin chỉ thay quyền sử dụng module, không ghi nhận thanh toán, hóa đơn hay MRR.</p></div></div>':''}<div class="plans">${(d.items||[]).map(p=>`<section class="plan-card ${p.id==='PLUS'?'featured':''}"><span class="chip">${p.id==='PLUS'?'ĐƯỢC ĐỀ XUẤT':'GÓI '+h(p.id)}</span><h3>${h(p.name)}</h3><div class="price mono">${fvnd(p.price_vnd)} <small>/ tháng · dự kiến</small></div><p class="muted small">Tối đa ${fnum(p.branches)} chi nhánh</p><ul>${(p.features||[]).map(f=>`<li>${h(features[f]||f)}</li>`).join('')}</ul><div class="divider" style="margin:15px 0"></div><h4 style="font-size:13px;margin:0 0 9px">🌐 Tùy chỉnh thương hiệu</h4><ul>${(p.branding?.vi||[]).map(x=>`<li>${h(x)}</li>`).join('')}</ul><p class="muted small">Bản pilot: xem trước riêng tư, chưa mở website công khai.</p><button class="btn outline full" disabled>Thanh toán chưa kích hoạt</button></section>`).join('')}</div>`}
function renderAudit(d){return `${head('Nhật ký quản trị','Lưu lại thời điểm, người thao tác, đối tượng và lý do thay đổi. Chỉ đọc, không thể xóa trong giao diện.')}${d.items?.length?`<div class="table-wrap"><table class="data-table audit-table"><thead><tr><th>Hoạt động</th><th>Đối tượng</th><th>Lý do</th><th>Thời gian</th></tr></thead><tbody>${d.items.map(x=>`<tr><td><strong>${h(actionLabels[x.action]||x.action)}</strong><div class="small muted">${h((x.actor_id||'').slice(0,8))}</div></td><td>${h(x.target_type||'—')}<div class="small muted">${h((x.target_id||'').slice(0,12))}</div></td><td>${h(x.reason||'—')}</td><td>${h(fdate(x.created_at))}</td></tr>`).join('')}</tbody></table></div>`:empty('Chưa có nhật ký','Những thay đổi có quyền cao sẽ được ghi tại đây.')}${tablePagination(d,'audit')}`}
function renderSystem(d){const flags=[['API','api'],['PostgreSQL','database'],['Môi trường','environment'],['Chế độ DEMO','demo_enabled'],['Xác thực quản trị','admin_mfa'],['Thuê bao','billing'],['Thanh toán','payment_gateway'],['Xác minh email','email_verification'],['Migration','migrations'],['Backup / Restore','backup']];return `${head('Trạng thái hệ thống','Thông tin vận hành pilot, không hiển thị khóa bí mật hoặc chuỗi kết nối.')}${mode==='demo'?'<div class="warning-banner">ⓘ &nbsp; Trạng thái minh họa. Không thay thế giám sát hệ thống thực.</div>':''}<div class="system-grid">${flags.map(([title,key])=>`<div class="system-row"><span>${h(title)}</span><strong>${h(String(d[key]===true?'Đã bật':d[key]===false?'Đã tắt':d[key]??'—').replace('not_integrated','Chưa tích hợp').replace('not_verified','Chưa kiểm chứng').replace('pilot_create_all','Pilot, chưa có migrations').replace('second_secret_only','Mã bảo vệ thứ hai').replace('access_key_session','Mã bảo vệ / phiên').replace('healthy','Hoạt động').replace('reachable','Đã kết nối').replace('staging','Staging'))}</strong></div>`).join('')}</div><div class="warning-banner" style="margin-top:20px"><span>!</span><div><strong>Chưa sẵn sàng Production</strong><p>Cần hoàn thiện Alembic migrations, backup/restore đã kiểm chứng, MFA chuẩn, email verification, billing webhook, rate limiting và load test trước khi mở cho khách hàng thật.</p></div></div>`}
function openModal(html,center=false){modalOpen=true;modal.innerHTML=`<div class="modal-overlay ${center?'center':''}" data-overlay="1"><section class="sheet" role="dialog" aria-modal="true" aria-label="Thông tin quản trị">${html}</section></div>`;requestAnimationFrame(()=>modal.querySelector('input,select,textarea,button')?.focus());}
function closeModal(){modal.innerHTML='';modalOpen=false;}
function detailHead(title,desc=''){return `<div class="detail-header"><div><span class="chip">PLATFORM CONTROL</span><h2>${h(title)}</h2></div><button class="close" aria-label="Đóng" data-action="close">×</button></div><p class="detail-sub">${h(desc)}</p>`;}
async function detail(type,id){
 let d;
 if(mode==='demo')d=(type==='business'?preview.businesses:preview.users).find(x=>x.id===id);
 else try{d=await api(`/api/admin/${type==='business'?'businesses':'users'}/${encodeURIComponent(id)}`)}catch(e){toast(e.message,true);return}
 if(!d)return toast('Không tìm thấy bản ghi',true);
 if(type==='business'){
 const a=mode==='live'?`<div class="actions"><button class="btn primary" data-action="operation" data-operation="plan" data-type="business" data-id="${h(id)}">Đổi gói thử nghiệm</button><button class="btn ${d.suspended?'light':'danger'}" data-action="operation" data-operation="${d.suspended?'resume':'suspend'}" data-type="business" data-id="${h(id)}">${d.suspended?'Khôi phục doanh nghiệp':'Tạm khóa doanh nghiệp'}</button></div>`:'<div class="alert">Bản DEMO chỉ cho phép xem. Không có thao tác thay đổi dữ liệu.</div>';
 openModal(`${detailHead(d.name,industryNames[d.industry]||d.industry)}<div class="keyfacts"><div class="keyfact"><span>Gói hiện tại</span><strong>${asPlan(d.plan)}</strong></div><div class="keyfact"><span>Trạng thái</span><strong>${asStatus(d.suspended)}</strong></div><div class="keyfact"><span>Chủ doanh nghiệp</span><strong>${h(d.owner?.name||'—')}</strong></div><div class="keyfact"><span>Email chủ sở hữu</span><strong>${h(d.owner?.email||'—')}</strong></div><div class="keyfact"><span>Số chi nhánh</span><strong>${fnum(d.branches?.length||0)}</strong></div><div class="keyfact"><span>Đơn hàng</span><strong>${fnum(d.orders||0)}</strong></div></div><h3 style="font-size:14px;margin-top:28px">Module đang sử dụng</h3><div class="flex-wrap">${(d.active_modules||[]).length?d.active_modules.map(f=>`<span class="pill">${h(features[f]||f)}</span>`).join(''):'<span class="muted small">Không có dữ liệu chi tiết trong DEMO</span>'}</div>${d.suspended?`<div class="warning-banner" style="margin-top:25px">⏸ ${h(d.suspend_reason||'Doanh nghiệp đang tạm khóa')}</div>`:''}<div style="margin-top:30px">${a}</div>`);
 }else{
 const a=mode==='live'?`<div class="actions"><button class="btn ${d.suspended?'light':'danger'}" data-action="operation" data-operation="${d.suspended?'unblock':'block'}" data-type="user" data-id="${h(id)}" ${d.is_platform_admin?'disabled':''}>${d.suspended?'Mở khóa tài khoản':'Tạm khóa tài khoản'}</button></div>`:'<div class="alert">Dữ liệu DEMO chỉ minh họa, không thể thao tác thật.</div>';
 openModal(`${detailHead(d.name,d.email)}<div class="keyfacts"><div class="keyfact"><span>Email</span><strong>${h(d.email)}</strong></div><div class="keyfact"><span>Trạng thái</span><strong>${asStatus(d.suspended)}</strong></div><div class="keyfact"><span>Tham gia doanh nghiệp</span><strong>${fnum(d.business_count||0)}</strong></div><div class="keyfact"><span>Ngày tạo</span><strong>${h(fdate(d.created_at))}</strong></div></div><h3 style="font-size:14px;margin-top:28px">Quyền trong doanh nghiệp</h3><ul class="details-list">${(d.memberships||[]).length?d.memberships.map(x=>`<li><strong>${h(x.business_name)}</strong><span class="muted">${h(x.role)} · ${h(x.plan)}</span></li>`).join(''):'<li class="muted">Không có chi tiết trong bản xem trước</li>'}</ul>${d.is_platform_admin?'<div class="warning-banner">Tài khoản Super Admin được bảo vệ, không thể tự khóa hoặc khóa qua giao diện.</div>':''}<div style="margin-top:24px">${a}</div>`);
 }
}
async function operation(type,id,action){
 if(mode!=='live'){toast('Chế độ DEMO không thể thực hiện thao tác ghi',true);return;}
 let d;try{d=await api(`/api/admin/${type==='business'?'businesses':'users'}/${encodeURIComponent(id)}`)}catch(e){toast(e.message,true);return;}
 const business=type==='business';
 const form=action==='plan'?
 `<label class="field"><span>CHỌN GÓI ĐÍCH</span><select name="plan" required>${['BASIC','PLUS','PRO'].filter(x=>x!==d.plan).map(x=>`<option value="${x}">${x}</option>`).join('')}</select></label><p class="note">Gói pilot chỉ điều chỉnh quyền; không tạo hóa đơn hoặc thu phí. Hạ gói sẽ bị từ chối nếu số chi nhánh vượt giới hạn.</p>`:
 action==='suspend'?`<label class="field"><span>NHẬP CHÍNH XÁC TÊN DOANH NGHIỆP</span><input name="confirm_name" required autocomplete="off" placeholder="${h(d.name)}"/></label>`:
 action==='block'?`<label class="field"><span>NHẬP CHÍNH XÁC EMAIL TÀI KHOẢN</span><input name="confirm_email" required autocomplete="off" placeholder="${h(d.email)}"/></label>`:'';
 const label=({plan:'Đổi gói',suspend:'Tạm khóa doanh nghiệp',resume:'Khôi phục doanh nghiệp',block:'Khóa tài khoản',unblock:'Mở khóa tài khoản'})[action];
 openModal(`${detailHead(label,business?d.name:d.email)}<p>${h(action==='plan'?'Chỉ thay đổi quyền sử dụng module trong giai đoạn pilot.':action==='block'?'Tài khoản sẽ bị chặn đăng nhập và mọi phiên hiện tại sẽ bị thu hồi.':action==='suspend'?'Mọi thao tác tại doanh nghiệp này sẽ bị từ chối cho đến khi được mở khóa.':'Thao tác được ghi nhật ký, không xóa dữ liệu cũ.')}</p><form id="operation-form" data-operation="${action}" data-type="${type}" data-id="${h(id)}"><div class="form-grid">${form}<label class="field"><span>LÝ DO THAY ĐỔI (TỐI THIỂU 8 KÝ TỰ)</span><textarea name="reason" minlength="8" maxlength="250" required placeholder="Lý do rõ ràng để đối soát nhật ký..." rows="3"></textarea></label>${['resume','unblock','plan'].includes(action)?'<label class="note"><input type="checkbox" name="confirmed" required> Tôi xác nhận đã kiểm tra đối tượng và hậu quả của thao tác.</label>':''}</div><div class="footer-actions"><button type="button" class="btn outline" data-action="close">Hủy</button><button type="submit" class="btn ${['suspend','block'].includes(action)?'danger':'primary'}">Xác nhận ${h(label.toLowerCase())}</button></div></form>`,true);
}
function pageMove(type,delta){const size=type==='audit'?50:25;offset[type]=Math.max(0,(offset[type]||0)+delta*size);showTab(type)}
async function sendOperation(form){if(busy)return;busy=true;const button=form.querySelector('button[type="submit"]');if(button)button.disabled=true;
 const type=form.dataset.type,id=form.dataset.id,op=form.dataset.operation;
 const url=`/api/admin/${type==='business'?'businesses':'users'}/${encodeURIComponent(id)}/${op}`;
 let payload={reason:form.elements.reason.value.trim()};
 if(op==='plan')payload={...payload,plan:form.elements.plan.value,confirmed:true};
 else if(op==='suspend')payload.confirm_name=form.elements.confirm_name.value.trim();
 else if(op==='block')payload.confirm_email=form.elements.confirm_email.value.trim();
 else payload.confirmed=true;
 try{await api(url,{method:'POST',body:payload});toast('Đã lưu thay đổi và ghi nhật ký quản trị');closeModal();await showTab(type==='business'?'businesses':'users');}
 catch(e){toast(e.message,true);if(button)button.disabled=false}finally{busy=false}
}
root.addEventListener('submit',async e=>{
 const form=e.target;if(!(form instanceof HTMLFormElement))return;
 if(!['login-form','unlock-form','filter-businesses','filter-users'].includes(form.id))return;
 e.preventDefault();
 if(form.id.startsWith('filter-')){
  const k=form.id.slice(7);filters[k]=Object.fromEntries(new FormData(form).entries());offset[k]=0;await showTab(k);return;
 }
 if(busy)return;busy=true;const button=form.querySelector('button[type="submit"]');if(button)button.disabled=true;
 try{
  if(form.id==='login-form'){
   const u=await api('/api/auth/login',{method:'POST',body:{email:form.elements.email.value.trim(),password:form.elements.password.value}});
   session=u;
   const d=await api('/api/admin/session');session=d;
   if(!d.unlocked){setAuth('unlock');session=d;}else{mode='live';await showTab('overview');}
  }else{
   await api('/api/admin/unlock',{method:'POST',body:{access_key:form.elements.access_key.value}});
   session=await api('/api/admin/session');mode='live';toast('Đã mở khóa phiên quản trị');await showTab('overview');
  }
 }catch(e){toast(e.message,true);if(button)button.disabled=false}finally{busy=false}
});
root.addEventListener('click',async e=>{
 const node=e.target.closest('[data-action]');if(!node)return;
 const action=node.dataset.action;
 if(action==='tab')return showTab(node.dataset.tab);
 if(action==='refresh')return showTab(activeTab);
 if(action==='demo'){
  try{preview=await api('/api/admin/preview');mode='demo';session=null;toast('Đang xem dữ liệu minh họa');await showTab('overview');}catch(err){toast(err.message,true)}return;
 }
 if(action==='exit-demo')return init();
 if(action==='switch-account'){setAuth('login');return;}
 if(action==='lock'){
  try{await api('/api/admin/lock',{method:'POST',body:{}})}catch(e){toast(e.message,true)}
  setAuth('unlock');try{session=await api('/api/auth/me')}catch{}return;
 }
 if(action==='page')return pageMove(node.dataset.entity,Number(node.dataset.delta||0));
 if(action==='detail')return detail(node.dataset.type,node.dataset.id);
 if(action==='close')return closeModal();
});
modal.addEventListener('click',async e=>{
 if(e.target.dataset.overlay==='1')return closeModal();
 const node=e.target.closest('[data-action]');if(!node)return;
 if(node.dataset.action==='close')return closeModal();
 if(node.dataset.action==='operation')return operation(node.dataset.type,node.dataset.id,node.dataset.operation);
});
modal.addEventListener('submit',async e=>{
 const form=e.target;
 if(form instanceof HTMLFormElement&&form.id==='operation-form'){e.preventDefault();await sendOperation(form)}
});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&modalOpen)closeModal()});
init();
})();