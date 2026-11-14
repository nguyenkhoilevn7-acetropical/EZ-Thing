(()=>{
'use strict';
const $=id=>document.getElementById(id),mode=document.body.dataset.reservationMode;
const E=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const uuid=()=>globalThis.crypto?.randomUUID?.()||('req-'+Date.now()+'-'+Math.random().toString(36).slice(2));
const dayText=d=>{const y=d.getUTCFullYear(),m=String(d.getUTCMonth()+1).padStart(2,'0'),x=String(d.getUTCDate()).padStart(2,'0');return `${y}-${m}-${x}`;};
const today=()=>dayText(new Date(Date.now()+7*3600000));
const plusDays=(v,n)=>{const d=new Date(v+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+n);return dayText(d);};
const formatTime=v=>new Date(v).toLocaleString(window.EZI18N?.locale()||'vi-VN',{timeZone:'Asia/Ho_Chi_Minh',hour:'2-digit',minute:'2-digit'});
const formatDate=v=>new Date(v).toLocaleString(window.EZI18N?.locale()||'vi-VN',{timeZone:'Asia/Ho_Chi_Minh',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'});
const statusText={pending:'Chờ xác nhận',confirmed:'Đã xác nhận',seated:'Khách đã nhận bàn',completed:'Hoàn tất',cancelled:'Đã hủy',no_show:'Khách không đến',new:'Mới gửi',contacted:'Đã liên hệ',closed:'Đã đóng'};
const validPhone=v=>/^[0-9+().\s-]{8,25}$/.test(String(v||'').trim());
const tel=v=>'tel:'+String(v||'').replace(/[^0-9+]/g,'');
let csrf='',guestDuration=90,guestSlot='',selectedBusiness='',bookings=[],inquiries=[],contact={};
async function api(path,method='GET',body=null){
 const o={method,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','Accept-Language':window.EZI18N?.language()||'vi'}};
 if(method!=='GET'){if(csrf)o.headers['x-csrf-token']=csrf;o.body=JSON.stringify(body??{});}
 const r=await fetch('/api'+path,o);let data;try{data=await r.json();}catch{data={detail:'Phản hồi không hợp lệ'}};
 if(!r.ok){const msg=typeof data.detail==='string'?data.detail:'Không thể thực hiện yêu cầu';const err=new Error(msg);err.status=r.status;throw err;}return data;
}
function toast(message,error=false){const el=$('res-toast');if(!el)return;el.textContent=message;el.className='toast show'+(error?' error':'');clearTimeout(el._timer);el._timer=setTimeout(()=>{el.className='toast';},4000);}
async function authenticate(){
 try{const me=await api('/auth/me');csrf=me.csrf_token;return me;}
 catch(err){if(err.status!==401)throw err;const me=await api('/auth/demo','POST',{});csrf=me.csrf_token;return me;}
}
function errorBlock(message){return `<div class="empty-block">${E(message)} <button class="link-button" type="button" onclick="location.reload()">Thử lại</button></div>`;}
function setMinMaxDate(el){if(!el)return;const day=today();el.min=day;el.max=plusDays(day,30);el.value=day;}
async function loadContact(){const data=await api('/preview/cafe/reservations/contact');const el=$('contact-details');if(!el)return;const pieces=[];
 if(data.phone)pieces.push(`<a href="${E(tel(data.phone))}">☎ ${E(data.phone)} <span>Gọi ngay ↗</span></a>`);
 else pieces.push('<div>☎ Quán chưa cập nhật số điện thoại</div>');
 if(data.email)pieces.push(`<a href="mailto:${E(data.email)}">✉ ${E(data.email)} <span>Gửi email ↗</span></a>`);
 if(data.address)pieces.push(`<div>⌖ ${E(data.address)}</div>`);
 pieces.push(`<div>◷ ${E(data.hours)}</div>`);
 el.innerHTML=pieces.join('');
}
async function loadGuestSlots(){const day=$('booking-day')?.value,size=$('booking-size')?.value,el=$('booking-slots');if(!day||!el)return;guestSlot='';el.innerHTML='<div class="muted-message">Đang kiểm tra lịch trống…</div>';
 try{const r=await api(`/preview/cafe/reservations/availability?day=${encodeURIComponent(day)}&party_size=${encodeURIComponent(size)}&duration_minutes=${guestDuration}`);
   const available=r.slots.filter(s=>s.available);
   el.innerHTML=available.length?available.map(s=>`<button type="button" data-slot="${E(s.start_at)}" class="slot-button"><b>${E(formatTime(s.start_at))}</b><small>${s.available_tables} bàn phù hợp</small></button>`).join(''):'<div class="muted-message">Không có bàn phù hợp. Hãy chọn ngày/giờ hoặc số người khác.</div>';
 }catch(err){el.innerHTML=errorBlock(err.message);}
}
async function submitGuestBooking(form){if(!guestSlot){toast('Vui lòng chọn giờ còn chỗ',true);return;}
 const fields=Object.fromEntries(new FormData(form));if(!validPhone(fields.phone)){toast('Vui lòng nhập đúng số điện thoại',true);return;}
 const btn=form.querySelector('[type=submit]');btn.disabled=true;
 try{const r=await api('/preview/cafe/reservations','POST',{request_id:uuid(),customer_name:fields.customer_name.trim(),phone:fields.phone.trim(),party_size:Number(fields.party_size),duration_minutes:guestDuration,start_at:guestSlot,note:fields.note||''});
   $('booking-result').hidden=false;
   $('booking-result').innerHTML=`<div class="result-check">✓</div><h3>Đã nhận yêu cầu!</h3><p><b>${E(r.customer_name)}</b> • ${r.party_size} khách • ${E(formatDate(r.scheduled_at))}</p><p>Bàn được đề xuất: ${E(r.table_label)}. <strong>Chờ quán xác nhận</strong> trước khi đến.</p><div class="result-actions"><button id="check-res-status" type="button" class="secondary-button">↻ Kiểm tra trạng thái</button><a class="secondary-button" href="/menu/cafe">Xem thực đơn</a></div><div id="customer-res-status" class="small-print">Mã yêu cầu: ${E(r.id.slice(0,8).toUpperCase())}</div>`;
   $('check-res-status').onclick=async()=>{try{const x=await api('/preview/cafe/reservations/'+encodeURIComponent(r.id));$('customer-res-status').textContent='Trạng thái hiện tại: '+(statusText[x.status]||x.status);}catch(err){toast(err.message,true);}};
   $('booking-result').scrollIntoView({behavior:'smooth',block:'center'});toast('Đã gửi yêu cầu đặt bàn DEMO');await loadGuestSlots();
 }catch(err){toast(err.message,true);await loadGuestSlots();}finally{btn.disabled=false;}
}
async function submitInquiry(form){const data=Object.fromEntries(new FormData(form));const btn=form.querySelector('button[type=submit]');btn.disabled=true;
 try{await api('/preview/cafe/inquiries','POST',{request_id:uuid(),name:data.name.trim(),phone:data.phone.trim(),message:data.message.trim()});form.reset();toast('Lời nhắn đã tới hộp thư của quán (DEMO)');}
 catch(err){toast(err.message,true);}finally{btn.disabled=false;}
}
async function startGuest(){const me=await authenticate();if(!me.demo)throw Error('Trang đặt bàn này chỉ hoạt động với tài khoản DEMO trên staging.');
 setMinMaxDate($('booking-day'));
 for(const key of ['booking-day','booking-size'])$(key).addEventListener('change',loadGuestSlots);
 $('refresh-slots').addEventListener('click',loadGuestSlots);
 document.querySelectorAll('[data-duration]').forEach(b=>b.addEventListener('click',()=>{guestDuration=Number(b.dataset.duration);document.querySelectorAll('[data-duration]').forEach(x=>x.classList.toggle('active',x===b));loadGuestSlots();}));
 $('booking-slots').addEventListener('click',e=>{const b=e.target.closest('[data-slot]');if(!b)return;guestSlot=b.dataset.slot;document.querySelectorAll('[data-slot]').forEach(x=>x.classList.toggle('selected',x===b));});
 $('guest-reservation-form').addEventListener('submit',e=>{e.preventDefault();submitGuestBooking(e.target);});
 $('guest-inquiry-form').addEventListener('submit',e=>{e.preventDefault();submitInquiry(e.target);});
 await Promise.allSettled([loadGuestSlots(),loadContact()]);
}
const statusOptions={pending:[['confirmed','Xác nhận bàn'],['cancelled','Hủy yêu cầu']],confirmed:[['seated','Khách đã đến'],['cancelled','Hủy lịch'],['no_show','Khách không đến']],seated:[['completed','Hoàn tất']]} ;
function showMerchant(){const all=bookings,filter=$('manager-filter').value,day=$('manager-date').value;
 const todays=all.filter(x=>x.scheduled_at?.slice(0,10)===day||formatDate(x.scheduled_at).includes(day.split('-').reverse().join('/')));
 $('reservation-stats').innerHTML=[['Sắp diễn ra',all.filter(x=>['pending','confirmed'].includes(x.status)).length,'◷'],['Chờ duyệt',all.filter(x=>x.status==='pending').length,'✉'],['Đã xác nhận',all.filter(x=>x.status==='confirmed').length,'✓'],['Liên hệ mới',inquiries.filter(x=>x.status==='new').length,'☏']].map(([title,n,icon])=>`<div class="stat-card"><span>${icon}</span><b>${n}</b><small>${title}</small></div>`).join('');
 const rows=all.filter(x=>(filter==='all'||x.status===filter)&&(!day||x.scheduled_at?.slice(0,10)===day||new Date(x.scheduled_at).toLocaleDateString('en-CA',{timeZone:'Asia/Ho_Chi_Minh'})===day));
 $('manager-bookings').innerHTML=rows.length?rows.map(r=>`<article class="booking-item"><div class="booking-item-time"><span>${E(formatDate(r.scheduled_at))}</span><b class="status status-${E(r.status)}">${E(statusText[r.status]||r.status)}</b></div><div class="booking-item-main"><div class="guest-initial">${E(r.customer_name?.[0]||'K')}</div><div><h3>${E(r.customer_name)}</h3><p>👥 ${r.party_size} khách &nbsp;•&nbsp; 🪑 ${E(r.table_label)} &nbsp;•&nbsp; ${E(r.source==='demo'?'Khách online':'Nhân viên tạo')}</p>${r.note?`<p class="guest-note">${E(r.note)}</p>`:''}</div></div><div class="booking-item-actions"><a class="secondary-button" href="${E(tel(r.phone))}">☎ ${E(r.phone)}</a>${(statusOptions[r.status]||[]).map(([code,label])=>`<button type="button" class="${code==='cancelled'||code==='no_show'?'text-danger':'secondary-button'}" data-status="${code}" data-res-id="${E(r.id)}">${E(label)}</button>`).join('')}</div></article>`).join(''):'<div class="empty-block">Chưa có lịch đặt bàn phù hợp với bộ lọc.</div>';
 $('manager-inquiries').innerHTML=inquiries.length?inquiries.map(q=>`<article class="inquiry-item"><div><strong>${E(q.name)}</strong> <span class="status status-${E(q.status)}">${E(statusText[q.status]||q.status)}</span></div><p>${E(q.message)}</p><div class="booking-item-actions"><a class="secondary-button" href="${E(tel(q.phone))}">☎ ${E(q.phone)}</a>${q.status==='new'?`<button class="secondary-button" data-inquiry-status="contacted" data-inquiry-id="${E(q.id)}">Đã liên hệ</button>`:q.status==='contacted'?`<button class="secondary-button" data-inquiry-status="closed" data-inquiry-id="${E(q.id)}">Đóng yêu cầu</button>`:''}</div></article>`).join(''):'<div class="empty-block">Chưa có lời nhắn nào.</div>';
}
async function loadMerchant(){const bid=encodeURIComponent(selectedBusiness);const result=await Promise.all([api('/businesses/'+bid+'/reservations'),api('/businesses/'+bid+'/inquiries'),api('/businesses/'+bid+'/reservations/contact')]);bookings=result[0];inquiries=result[1];contact=result[2];const form=$('manager-contact-form');for(const name of ['phone','email','address','hours'])form.elements[name].value=contact[name]||'';showMerchant();}
async function changeStatus(id,status){if(['cancelled','no_show'].includes(status)&&!confirm(window.EZI18N?.translate('Xác nhận chuyển trạng thái lịch đặt bàn?')||'Xác nhận chuyển trạng thái lịch đặt bàn?'))return;
 try{await api(`/businesses/${encodeURIComponent(selectedBusiness)}/reservations/${encodeURIComponent(id)}/status`,'POST',{status});await loadMerchant();toast('Đã cập nhật lịch đặt bàn');}catch(err){toast(err.message,true);}
}
async function changeInquiry(id,status){try{await api(`/businesses/${encodeURIComponent(selectedBusiness)}/inquiries/${encodeURIComponent(id)}/status`,'POST',{status});await loadMerchant();toast('Đã cập nhật yêu cầu');}catch(err){toast(err.message,true);}}
async function newMerchantBooking(){const modal=$('res-modal');modal.hidden=false;modal.innerHTML=`<div class="modal-backdrop" data-close-modal><div class="modal-dialog" role="dialog" aria-modal="true" aria-label="Thêm đặt bàn" onclick="event.stopPropagation()"><div class="modal-head"><h2>Đặt bàn thủ công</h2><button type="button" id="close-res-modal" class="close-modal">×</button></div><form id="merchant-booking-form"><div class="form-grid"><label class="field"><span>Họ tên khách</span><input name="customer_name" minlength="2" maxlength="100" required></label><label class="field"><span>Điện thoại</span><input name="phone" minlength="8" maxlength="25" required></label></div><div class="form-grid"><label class="field"><span>Ngày đến</span><input name="day" type="date" id="merchant-booking-day" required></label><label class="field"><span>Số khách</span><input name="party_size" id="merchant-booking-size" type="number" min="1" max="20" value="2" required></label></div><div class="form-grid"><label class="field"><span>Thời lượng</span><select name="duration_minutes" id="merchant-booking-duration"><option value="60">60 phút</option><option value="90" selected>90 phút</option><option value="120">120 phút</option></select></label><label class="field"><span>Giờ còn bàn</span><select name="start_at" id="merchant-booking-slot" required><option value="">Đang tải…</option></select></label></div><label class="field"><span>Ghi chú</span><textarea name="note" maxlength="240" rows="2"></textarea></label><button type="submit" class="submit-button">Tạo đặt bàn <span>→</span></button></form></div></div>`;
 setMinMaxDate($('merchant-booking-day'));
 async function update(){const d=$('merchant-booking-day').value,n=$('merchant-booking-size').value,dur=$('merchant-booking-duration').value,sel=$('merchant-booking-slot');sel.innerHTML='<option value="">Đang kiểm tra…</option>';
 try{const r=await api(`/businesses/${encodeURIComponent(selectedBusiness)}/reservations/availability?day=${encodeURIComponent(d)}&party_size=${encodeURIComponent(n)}&duration_minutes=${encodeURIComponent(dur)}`);const free=r.slots.filter(x=>x.available);sel.innerHTML=free.length?free.map(x=>`<option value="${E(x.start_at)}">${E(formatTime(x.start_at))} (${x.available_tables} bàn)</option>`).join(''):'<option value="">Không còn bàn</option>';}catch(e){sel.innerHTML='<option value="">Không thể tải giờ</option>';toast(e.message,true);}}
 ['merchant-booking-day','merchant-booking-size','merchant-booking-duration'].forEach(x=>$(x).addEventListener('change',update));await update();
 modal.querySelector('[data-close-modal]').addEventListener('click',()=>modal.hidden=true);$('close-res-modal').onclick=()=>modal.hidden=true;
 $('merchant-booking-form').addEventListener('submit',async e=>{e.preventDefault();const f=Object.fromEntries(new FormData(e.target));if(!f.start_at){toast('Chọn giờ còn bàn',true);return;}const button=e.target.querySelector('[type=submit]');button.disabled=true;try{await api('/businesses/'+encodeURIComponent(selectedBusiness)+'/reservations','POST',{request_id:uuid(),customer_name:f.customer_name,phone:f.phone,party_size:Number(f.party_size),start_at:f.start_at,duration_minutes:Number(f.duration_minutes),note:f.note||''});modal.hidden=true;await loadMerchant();toast('Đã tạo lịch, chờ xác nhận');}catch(err){toast(err.message,true);}finally{button.disabled=false;}});
}
async function startMerchant(){await authenticate();const list=await api('/businesses');const b=list.find(x=>x.industry==='fnb'&&x.active_modules?.includes('tables'));if(!b)throw Error('Không tìm thấy doanh nghiệp Cafe / Nhà hàng có chức năng quản lý bàn trong tài khoản.');selectedBusiness=b.id;$('manager-status').textContent='Đang quản lý: '+b.name;$('manager-content').hidden=false;
 for(const el of ['manager-date','manager-filter'])$(el).addEventListener('change',showMerchant);
 $('clear-res-filter').onclick=()=>{$('manager-date').value='';$('manager-filter').value='all';showMerchant();};
 $('manager-refresh').onclick=async()=>{try{await loadMerchant();toast('Đã làm mới đặt bàn');}catch(e){toast(e.message,true);}};
 $('manager-add-booking').onclick=newMerchantBooking;
 $('manager-bookings').addEventListener('click',e=>{const b=e.target.closest('[data-status]');if(b)changeStatus(b.dataset.resId,b.dataset.status);});
 $('manager-inquiries').addEventListener('click',e=>{const b=e.target.closest('[data-inquiry-status]');if(b)changeInquiry(b.dataset.inquiryId,b.dataset.inquiryStatus);});
 $('manager-contact-form').addEventListener('submit',async e=>{e.preventDefault();const f=Object.fromEntries(new FormData(e.target));const btn=e.target.querySelector('[type=submit]');btn.disabled=true;try{await api('/businesses/'+encodeURIComponent(selectedBusiness)+'/reservations/contact','PUT',{phone:f.phone,email:f.email||null,address:f.address,hours:f.hours||'08:00 – 22:00'});toast('Đã lưu liên hệ. Trang khách sẽ thấy cập nhật này.');}catch(err){toast(err.message,true);}finally{btn.disabled=false;}});
 await loadMerchant();
}
async function start(){try{if(mode==='guest')await startGuest();else if(mode==='merchant')await startMerchant();}catch(e){if(mode==='merchant'){$('manager-status').innerHTML=errorBlock(e.message);$('manager-content').hidden=true;}else {$('booking-slots').innerHTML=errorBlock(e.message);$('submit-reservation').disabled=true;$('contact-details').textContent=e.message;}toast(e.message,true);}}
start();
})();