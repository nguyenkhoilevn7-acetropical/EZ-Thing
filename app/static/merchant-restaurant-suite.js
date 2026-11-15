/* EZ Thing Restaurant Operations — embedded booking desk and interactive floor plan.
   All mutations use the existing same-origin API session + CSRF through merchant app.
   A floor plan is visual metadata; bookings and orders remain authoritative. */
(function(){
'use strict';
window.EZRestaurantSuite=function(deps){
  const E=deps.E, V=deps.V, fmt=deps.D;
  const st={bid:null,branch:null,layout:null,bookings:[],inquiries:[],contact:{},policy:null,
    activeZone:null,editing:false,dirty:false,search:'',filter:'all',date:'',
    loading:null,request:0,lastMoved:0,selected:null};
  const next=()=>globalThis.crypto?.randomUUID?.()||('req-'+Date.now()+'-'+Math.random().toString(36).slice(2));
  const localDate=(v)=>new Date(v).toLocaleDateString('en-CA',{timeZone:'Asia/Ho_Chi_Minh'});
  const stamp=(v)=>new Date(v).toLocaleString(window.EZI18N?.locale()||'vi-VN',{timeZone:'Asia/Ho_Chi_Minh',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
  const time=(v)=>new Date(v).toLocaleTimeString(window.EZI18N?.locale()||'vi-VN',{timeZone:'Asia/Ho_Chi_Minh',hour:'2-digit',minute:'2-digit'});
  const today=()=>localDate(Date.now());
  const q=(selector)=>document.querySelector(selector);
  let slotRequest=0;
  const labels={pending:'Chờ xác nhận',confirmed:'Đã xác nhận',seated:'Đã nhận bàn',completed:'Hoàn tất',
    cancelled:'Đã hủy',no_show:'Không đến',new:'Mới',contacted:'Đã liên hệ',closed:'Đã đóng'};
  const transitions={pending:[['confirmed','Xác nhận'],['cancelled','Hủy lịch']],
    confirmed:[['seated','Nhận bàn'],['cancelled','Hủy lịch'],['no_show','Không đến']],
    seated:[['completed','Hoàn tất']]};
  const statusLabel=(r)=>labels[r]||r;
  const tr=(vi,en)=>(window.EZI18N?.language()||'vi')==='en'?en:vi;
  const option=(key,val,selected)=>'<option value="'+E(key)+'"'+(key===selected?' selected':'')+'>'+E(val)+'</option>';
  const button=(action,caption,extra)=>'<button type="button" data-suite="'+action+'"'+(extra||'')+'>'+caption+'</button>';
  function ensureBusiness(){
    const id=deps.getState().business?.id;
    if(id!==st.bid){
      st.bid=id;st.branch=null;st.layout=null;st.bookings=[];st.inquiries=[];st.contact={};st.policy=null;
      st.activeZone=null;st.editing=false;st.dirty=false;st.loading=null;st.request++;
    }
  }
  async function fetchAll(force){
    ensureBusiness();
    if(!st.bid)return;
    if(st.loading&&!force)return st.loading;
    if(st.layout&&!force)return;
    const generation=++st.request;
    const prefix='/businesses/'+encodeURIComponent(st.bid);
    const suffix=st.branch?'?branch_id='+encodeURIComponent(st.branch):'';
    st.loading=(async()=>{
      const [floor,booking,inquiry,contact,policy]=await Promise.all([
        deps.api(prefix+'/floorplan'+suffix),
        deps.api(prefix+'/reservations'),
        deps.api(prefix+'/inquiries'),
        deps.api(prefix+'/reservations/contact'),
        deps.api(prefix+'/reservations/policy'+(st.branch?'?branch_id='+encodeURIComponent(st.branch):''))
      ]);
      if(generation!==st.request)return;
      st.layout=floor;st.branch=floor.branch_id;st.bookings=booking;st.inquiries=inquiry;st.contact=contact;st.policy=st.branch?policy:await deps.api(prefix+'/reservations/policy?branch_id='+encodeURIComponent(floor.branch_id));
      st.activeZone=st.activeZone&&floor.zones.some(z=>z.id===st.activeZone)?st.activeZone:floor.zones[0]?.id;
      st.dirty=false;
    })().finally(()=>{if(generation===st.request)st.loading=null});
    return st.loading;
  }
  async function mount(){
    ensureBusiness();
    const root=q('#suite-root');if(!root)return;
    if(!st.layout){
      root.innerHTML='<div class="surface pad"><p class="subtle" role="status">Đang tải dữ liệu nhà hàng...</p></div>';
      try{await fetchAll(true)}catch(err){if(q('#suite-root'))q('#suite-root').innerHTML='<div class="surface pad"><p role="alert">'+E(err.message)+'</p>'+button('reload','Thử lại')+'</div>';return}
    }
    draw();
  }
  function renderFloorplan(){return '<div id="suite-root" data-section="floorplan" class="suite-container"></div>'}
  function renderReservations(){return '<div id="suite-root" data-section="reservations" class="suite-container"></div>'}
  function draw(){
    const root=q('#suite-root');if(!root||!st.layout)return;
    root.innerHTML=root.dataset.section==='reservations'?bookingPage():floorPage();
    if(root.dataset.section==='floorplan')enableDragging();
  }
  function zoneButtons(){
    return '<div class="floor-zone-tabs" role="group" aria-label="Khu vực">'+st.layout.zones.map(z=>
      button('zone',E(z.name)+' <span>'+st.layout.tables.filter(t=>t.placement.zone_id===z.id).length+'</span>',
        ' data-zone="'+E(z.id)+'" class="'+(st.activeZone===z.id?'active':'')+'"')).join('')+'</div>';
  }
  function stateForTable(t){
    const linked=st.bookings.filter(r=>r.table_id===t.id&&['pending','confirmed','seated'].includes(r.status))
      .sort((a,b)=>new Date(a.scheduled_at)-new Date(b.scheduled_at));
    const nextBooking=linked.find(r=>new Date(r.scheduled_at)>=Date.now()-2*3600000)||linked[0];
    if(t.occupied)return {code:'serving',text:'Đang phục vụ • Chưa thanh toán',book:nextBooking};
    if(nextBooking?.status==='seated')return {code:'serving',text:'Khách đã nhận bàn',book:nextBooking};
    if(nextBooking&&localDate(nextBooking.scheduled_at)===today())return {code:'reserved',text:'Đã đặt trước',book:nextBooking};
    return {code:'free',text:'Còn trống',book:nextBooking};
  }
  function floorPage(){
    const cfg=st.layout, current=cfg.zones.find(z=>z.id===st.activeZone)||cfg.zones[0];
    const tableCount=cfg.tables.length,occupied=cfg.tables.filter(t=>stateForTable(t).code==='serving').length,
      reserved=cfg.tables.filter(t=>stateForTable(t).code==='reserved').length;
    const toolbar='<div class="suite-toolbar"><div><h2>Sơ đồ bàn theo khu vực</h2><p>Từng chi nhánh có sơ đồ riêng. Chạm bàn để xem thông tin, hoặc bật chế độ chỉnh sửa để kéo thả.</p></div><div class="suite-toolbar-actions">'+
      '<label class="suite-label">Chi nhánh<select id="suite-branch" data-suite-change="branch">'+cfg.branches.map(x=>option(x.id,x.name,st.branch)).join('')+'</select></label>'+
      button('booking-tab','Lịch đặt bàn')+
      (cfg.editable?button('edit',st.editing?'Thoát chỉnh sửa':'✥ Sắp xếp bàn',' class="suite-primary"'):'')+'</div></div>';
    const actions=st.editing?
      '<div class="suite-edit-controls"><span>Chỉnh sửa khu vực • Kéo, chạm hoặc dùng phím mũi tên để di chuyển bàn.</span>'+
      button('new-zone','+ Thêm khu vực')+
      button('rename-zone','Đổi tên khu vực')+
      (cfg.zones.length>1?button('delete-zone','Xóa khu vực'):'')+
      button('undo-layout','Hoàn tác')+
      button('save-layout','Lưu sơ đồ',' class="suite-save"'+(!st.dirty?' disabled':''))+'</div>':'';
    const visible=cfg.tables.filter(t=>t.placement.zone_id===current.id);
    const board='<div class="suite-floor-viewport"><div class="suite-floor-board" id="suite-floor-board" role="group" aria-label="Sơ đồ '+E(current.name)+'">'+
      '<div class="suite-floor-title">'+E(current.name)+'</div>'+
      (visible.length?visible.map(t=>{
        const a=t.placement,stat=stateForTable(t);
        return '<button type="button" class="suite-table shape-'+E(a.shape)+' state-'+stat.code+
          '" data-suite="table" data-table-id="'+E(t.id)+'" style="left:'+a.x+'%;top:'+a.y+'%"'+
          ' title="'+E(t.label+': '+stat.text)+'" aria-label="'+E(t.label+' • '+t.seats+' chỗ • '+stat.text)+'">'+
          '<strong>'+E(t.label)+'</strong><small>'+t.seats+' chỗ</small></button>';
      }).join(''):'<p class="suite-floor-empty">Chưa có bàn ở khu vực này. Chỉnh sửa sơ đồ để chuyển bàn từ khu vực khác.</p>')+'</div></div>';
    return toolbar+
      '<div class="suite-summary">'+
      '<div><strong>'+tableCount+'</strong><span>Tổng bàn</span></div>'+
      '<div><strong>'+Math.max(0,tableCount-occupied-reserved)+'</strong><span>Còn trống</span></div>'+
      '<div><strong>'+occupied+'</strong><span>Đang phục vụ</span></div>'+
      '<div><strong>'+reserved+'</strong><span>Đã đặt trước</span></div></div>'+
      '<section class="suite-floor-card">'+zoneButtons()+actions+board+
      '<div class="suite-floor-footer"><div class="suite-legend"><span class="key-free">Trống</span><span class="key-reserved">Đã đặt</span><span class="key-serving">Đang phục vụ / chưa thanh toán</span></div>'+
      '<span>Chi nhánh: '+E(cfg.branch_name)+' • Vị trí lưu khi bấm “Lưu sơ đồ”</span></div>'+
      '</section>'+
      '<div class="suite-floor-help"><h3>Quản lý bàn & đơn hàng</h3><p>Bấm vào bàn để xem đơn chưa thanh toán, lịch đặt gần nhất và tạo đơn mới. Sơ đồ lưu riêng từng chi nhánh, không thay đổi số bàn hay giá đơn.</p>'+
      button('new-table','+ Thêm bàn')+'</div>';
  }
  function bookingPage(){
    const bookings=st.bookings,all=bookings.filter(r=>(st.filter==='all'||r.status===st.filter)
      &&(!st.date||localDate(r.scheduled_at)===st.date)
      &&(!st.search||[r.customer_name,r.phone,r.table_label].join(' ').toLocaleLowerCase('vi').includes(st.search.toLocaleLowerCase('vi'))));
    const upcoming=bookings.filter(r=>['pending','confirmed'].includes(r.status)&&new Date(r.scheduled_at)>=Date.now()-30*60000).length;
    const pending=bookings.filter(r=>r.status==='pending').length;
    const confirmed=bookings.filter(r=>r.status==='confirmed').length;
    const openInquiries=st.inquiries.filter(i=>i.status==='new').length;
    const toolbar='<div class="suite-toolbar"><div><h2>Đặt bàn & lịch hẹn</h2><p>Danh sách đặt bàn, sơ đồ khu vực, liên hệ và lịch khách tại cùng một Back-Office.</p></div><div class="suite-toolbar-actions">'+
      button('floor-tab','Sơ đồ khu vực')+button('new-booking','+ Thêm đặt bàn',' class="suite-primary"')+
      button('reload','↻ Làm mới')+'</div></div>';
    const filters='<div class="suite-booking-filters">'+
      '<label>Tìm khách<input data-suite-input="search" type="search" placeholder="Tên hoặc số điện thoại..." value="'+E(st.search)+'"></label>'+
      '<label>Ngày<input type="date" data-suite-change="date" value="'+E(st.date)+'"></label>'+
      '<label>Trạng thái<select data-suite-change="filter">'+
      [['all','Tất cả'],['pending','Chờ xác nhận'],['confirmed','Đã xác nhận'],['seated','Đã nhận bàn'],
      ['completed','Hoàn tất'],['cancelled','Đã hủy'],['no_show','Không đến']].map(x=>option(x[0],x[1],st.filter)).join('')+
      '</select></label>'+button('reset-filters','Xóa lọc')+'</div>';
    const records=all.map(r=>
      '<article class="suite-booking-item"><div class="suite-booking-top"><strong>'+E(r.customer_name)+'</strong>'+
      '<span class="suite-tag tag-'+E(r.status)+'">'+E(statusLabel(r.status))+'</span></div>'+
      '<div class="suite-booking-meta"><span>◷ '+E(stamp(r.scheduled_at))+'</span><span>👥 '+r.party_size+' khách</span>'+
      '<span>🪑 '+E(r.table_label||'Hệ thống xếp bàn')+'</span></div>'+
      '<div class="suite-booking-bottom"><span>'+E(r.note||'Không có ghi chú')+'</span><div class="suite-booking-actions">'+
      '<a href="tel:'+E(String(r.phone).replace(/[^+0-9]/g,''))+'">☎ '+E(r.phone)+'</a>'+
      (transitions[r.status]||[]).map(([status,text])=>button('booking-status',E(text),
        ' data-id="'+E(r.id)+'" data-status="'+E(status)+'"')).join('')+'</div></div></article>').join('');
    const contact='<div class="suite-two-col"><section class="surface pad"><h3>Thông tin liên hệ công khai</h3>'+
      '<form data-suite-form="contact"><label>Điện thoại<input name="phone" maxlength="25" value="'+E(st.contact.phone||'')+'"></label>'+
      '<label>Email<input name="email" type="email" value="'+E(st.contact.email||'')+'"></label>'+
      '<label>Địa chỉ<textarea name="address" maxlength="200">'+E(st.contact.address||'')+'</textarea></label>'+
      '<label>Giờ hiển thị<input name="hours" maxlength="100" value="'+E(st.contact.hours||'')+'"></label>'+
      '<button class="suite-primary" type="submit">Lưu thông tin liên hệ</button><small>Chỉ chủ doanh nghiệp có quyền sửa. Giờ đặt bàn được kiểm tra riêng ở backend.</small></form></section>'+
      '<section class="surface pad"><h3>Yêu cầu liên hệ</h3>'+
      (st.inquiries.length?st.inquiries.map(i=>'<div class="suite-inquiry"><strong>'+E(i.name)+'</strong><span class="suite-tag tag-'+E(i.status)+'">'+E(statusLabel(i.status))+'</span>'+
        '<p>'+E(i.message)+'</p><div><a href="tel:'+E(String(i.phone).replace(/[^+0-9]/g,''))+'">☎ '+E(i.phone)+'</a> '+
        (i.status==='new'?button('inquiry-status','Đã liên hệ',' data-id="'+E(i.id)+'" data-status="contacted"'):
        i.status==='contacted'?button('inquiry-status','Đóng yêu cầu',' data-id="'+E(i.id)+'" data-status="closed"'):'')+'</div></div>').join(''):
        '<p class="subtle">Chưa có lời nhắn.</p>')+'</section></div>';
    // Rules are part of the same Reservations tab; no separate page or menu loss.
    const policy=st.policy||{open_time:'08:00',last_seating_time:'20:30',
      close_time:'22:00',closed_weekdays:[],blocked_dates:[]};
    const weekdays=[['T2','Mon'],['T3','Tue'],['T4','Wed'],['T5','Thu'],['T6','Fri'],['T7','Sat'],['CN','Sun']];
    const policyPanel='<section class="surface pad suite-booking-policy" aria-labelledby="suite-policy-title">'+
      '<h3 id="suite-policy-title">'+tr('Quy tắc nhận đặt bàn','Reservation availability rules')+'</h3>'+
      '<p class="subtle">'+tr('Áp dụng riêng cho chi nhánh đang chọn: ','Applies to selected branch: ')+
        E(st.layout?.branch_name||'')+'. '+
        tr('Lịch cũ không bị tự động hủy.','Existing bookings remain unchanged.')+'</p>'+
      '<form data-suite-form="reservation-policy">'+
      '<div class="suite-booking-filters">'+
      '<label>'+tr('Giờ mở cửa','Opening time')+'<input type="time" step="1800" name="open_time" required value="'+E(policy.open_time)+'"></label>'+
      '<label>'+tr('Giờ nhận khách cuối','Last seating')+'<input type="time" step="1800" name="last_seating_time" required value="'+E(policy.last_seating_time)+'"></label>'+
      '<label>'+tr('Giờ đóng cửa','Closing time')+'<input type="time" step="1800" name="close_time" required value="'+E(policy.close_time)+'"></label></div>'+
      '<fieldset><legend>'+tr('Ngày nghỉ hằng tuần','Weekly closed days')+'</legend>'+
      '<div class="suite-policy-days">'+weekdays.map((label,i)=>
        '<label class="suite-policy-day"><input type="checkbox" name="closed_weekdays" value="'+i+'"'+
        (policy.closed_weekdays.includes(i)?' checked':'')+'><span>'+tr(label[0],label[1])+'</span></label>').join('')+
      '</div></fieldset>'+
      '<label>'+tr('Ngày tạm ngưng nhận đặt bàn (YYYY-MM-DD, mỗi dòng một ngày)',
        'Blackout dates (YYYY-MM-DD, one per line)')+
      '<textarea name="blocked_dates" rows="2" placeholder="2026-12-25">'+E(policy.blocked_dates.join('\n'))+'</textarea></label>'+
      '<button type="submit" class="suite-primary">'+tr('Lưu quy tắc đặt bàn','Save booking rules')+'</button>'+
      '</form></section>';
    return toolbar+'<div class="suite-summary"><div><strong>'+upcoming+'</strong><span>Sắp diễn ra</span></div>'+
      '<div><strong>'+pending+'</strong><span>Chờ duyệt</span></div>'+
      '<div><strong>'+confirmed+'</strong><span>Đã xác nhận</span></div>'+
      '<div><strong>'+openInquiries+'</strong><span>Liên hệ mới</span></div></div>'+
      '<section class="surface pad suite-booking-panel"><div class="panel-title"><h3>Danh sách đặt bàn</h3><span class="subtle">'+all.length+' kết quả trong dữ liệu gần đây</span></div>'+
      filters+'<div class="suite-booking-list">'+(records||'<p class="subtle">Chưa có lịch đặt bàn phù hợp.</p>')+'</div></section>'+contact+policyPanel;
  }
  function editZones(){
    if(!st.layout?.editable)return;
    st.editing=!st.editing;
    if(!st.editing&&st.dirty&&!confirm('Sơ đồ chưa lưu. Bỏ những thay đổi này?')){
      st.editing=true;return;
    }
    if(!st.editing&&st.dirty){st.layout=null;st.dirty=false;fetchAll(true).then(draw).catch(e=>deps.toast(e.message,true));return}
    draw();
  }
  function setZone(id){if(st.layout.zones.some(z=>z.id===id)){st.activeZone=id;draw()}}
  async function save(){
    if(!st.dirty)return;
    const id=st.bid;
    const body={branch_id:st.branch,revision:st.layout.revision,zones:st.layout.zones,
      placements:st.layout.tables.map(t=>t.placement)};
    const result=await deps.api('/businesses/'+encodeURIComponent(id)+'/floorplan',
      {method:'PUT',body:JSON.stringify(body)});
    st.layout=result;st.dirty=false;deps.toast('Đã lưu sơ đồ khu vực');draw();
  }
  function newZone(){
    if(st.layout.zones.length>=12)return deps.toast('Tối đa 12 khu vực.',true);
    const name=prompt('Tên khu vực mới (ví dụ: Sân vườn / Tầng 2 / VIP):');
    if(name===null)return;
    const clean=name.trim().slice(0,45);if(!clean)return deps.toast('Cần nhập tên khu vực.',true);
    const zone={id:'zone_'+next().replace(/-/g,'').slice(0,16),name:clean};
    st.layout.zones.push(zone);st.activeZone=zone.id;st.dirty=true;draw();
  }
  function renameZone(){
    const zone=st.layout.zones.find(x=>x.id===st.activeZone);if(!zone)return;
    const name=prompt('Tên khu vực',zone.name);if(name===null)return;
    const clean=name.trim().slice(0,45);if(!clean)return;
    zone.name=clean;st.dirty=true;draw();
  }
  function removeZone(){
    if(st.layout.zones.length<=1)return;
    const zone=st.layout.zones.find(x=>x.id===st.activeZone);
    if(!confirm('Xóa khu vực '+zone.name+'? Bàn tại đây sẽ chuyển về khu vực đầu tiên.'))return;
    const fallback=st.layout.zones.find(x=>x.id!==zone.id);
    st.layout.zones=st.layout.zones.filter(x=>x!==zone);
    for(const table of st.layout.tables)if(table.placement.zone_id===zone.id)table.placement.zone_id=fallback.id;
    st.activeZone=fallback.id;st.dirty=true;draw();
  }
  function inspectTable(id){
    const table=st.layout?.tables.find(t=>t.id===id);if(!table)return;
    if(st.editing){
      const editor='<form data-suite-form="table-placement" data-id="'+E(id)+'">'+
        '<div class="formrow"><div class="formfield"><label>Khu vực</label><select name="zone_id">'+
        st.layout.zones.map(zone=>option(zone.id,zone.name,table.placement.zone_id)).join('')+
        '</select></div><div class="formfield"><label>Hình dạng bàn</label><select name="shape">'+
        [['round','Tròn'],['square','Vuông'],['rectangle','Chữ nhật']].map(x=>option(x[0],x[1],table.placement.shape)).join('')+
        '</select></div></div><div class="formrow"><div class="formfield"><label>Vị trí ngang (0–100)</label>'+
        '<input name="x" type="number" min="5" max="95" step="1" value="'+table.placement.x+'" required></div>'+
        '<div class="formfield"><label>Vị trí dọc (0–100)</label>'+
        '<input name="y" type="number" min="8" max="92" step="1" value="'+table.placement.y+'" required></div></div>'+
        '<p class="subtle">Chuyển khu vực, chọn hình dạng hoặc nhập tọa độ; sau đó nhấn Lưu sơ đồ ở màn chính.</p>'+
        '<div class="modal-footer"><button class="btn" type="submit">Áp dụng vị trí</button></div></form>';
      return deps.modal('Sắp xếp '+table.label,editor,true);
    }
    const state=stateForTable(table);
    const orders=(deps.getState().cache.orders||[]).filter(o=>o.table_id===id&&o.status==='open');
    const bookings=st.bookings.filter(r=>r.table_id===id&&['pending','confirmed','seated'].includes(r.status))
      .sort((a,b)=>new Date(a.scheduled_at)-new Date(b.scheduled_at)).slice(0,5);
    const details='<div class="suite-table-detail"><div class="suite-tag tag-'+state.code+'">'+E(state.text)+'</div>'+
      '<p><strong>Sức chứa:</strong> '+table.seats+' khách • '+E(st.layout.branch_name)+'</p>'+
      '<h3>Đơn chưa thanh toán</h3>'+
      (orders.length?orders.map(o=>'<div class="suite-detail-line"><span>#'+E(o.id.slice(0,8).toUpperCase())+' • '+E(stamp(o.created_at))+'</span><strong>'+V(o.total_vnd)+'</strong></div>').join(''):'<p class="subtle">Không có đơn đang mở.</p>')+
      '<h3>Lịch đặt gần nhất</h3>'+
      (bookings.length?bookings.map(r=>'<div class="suite-detail-line"><span>'+E(r.customer_name)+' • '+r.party_size+' khách • '+E(stamp(r.scheduled_at))+'</span><span>'+E(statusLabel(r.status))+'</span></div>').join(''):'<p class="subtle">Chưa có lịch đặt đang hoạt động.</p>')+
      '<div class="modal-footer">'+button('floor-new-order','+ Tạo đơn',' class="suite-primary" data-table-id="'+E(id)+'"')+
      button('floor-booking','Quản lý đặt bàn')+'</div></div>';
    deps.modal(table.label,details,true);
  }
  function enableDragging(){
    if(!st.editing||!st.layout?.editable)return;
    const board=q('#suite-floor-board');
    if(!board)return;
    for(const el of board.querySelectorAll('.suite-table')){
      el.classList.add('draggable');el.setAttribute('aria-roledescription','Bàn có thể di chuyển');
      el.addEventListener('pointerdown',event=>{
        if(event.button!==0)return;
        const rect=board.getBoundingClientRect();
        const table=st.layout.tables.find(t=>t.id===el.dataset.tableId);
        if(!table)return;
        let moved=false,startX=event.clientX,startY=event.clientY;
        el.setPointerCapture(event.pointerId);
        const move=e=>{
          if(!el.hasPointerCapture(e.pointerId))return;
          if(Math.abs(e.clientX-startX)+Math.abs(e.clientY-startY)>4)moved=true;
          if(!moved)return;
          // Snap to 2% grid and keep center away from canvas edge.
          const x=Math.max(5,Math.min(95,Math.round((e.clientX-rect.left)/rect.width*50)*2));
          const y=Math.max(8,Math.min(92,Math.round((e.clientY-rect.top)/rect.height*50)*2));
          table.placement.x=x;table.placement.y=y;
          el.style.left=x+'%';el.style.top=y+'%';st.dirty=true;
          const save=q('[data-suite="save-layout"]');if(save)save.disabled=false;
        };
        const end=e=>{
          el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',end);
          el.removeEventListener('pointercancel',end);
          if(moved)st.lastMoved=Date.now();
        };
        el.addEventListener('pointermove',move);el.addEventListener('pointerup',end);
        el.addEventListener('pointercancel',end);
      });
      el.addEventListener('keydown',event=>{
        const offsets={ArrowLeft:[-2,0],ArrowRight:[2,0],ArrowUp:[0,-2],ArrowDown:[0,2]};
        const offset=offsets[event.key];if(!offset)return;
        event.preventDefault();
        const t=st.layout.tables.find(x=>x.id===el.dataset.tableId);if(!t)return;
        const speed=event.shiftKey?5:1;
        t.placement.x=Math.max(5,Math.min(95,t.placement.x+offset[0]*speed));
        t.placement.y=Math.max(8,Math.min(92,t.placement.y+offset[1]*speed));
        el.style.left=t.placement.x+'%';el.style.top=t.placement.y+'%';st.dirty=true;
        const save=q('[data-suite="save-layout"]');if(save)save.disabled=false;
      });
    }
  }
  async function openBookingForm(){
    const date=new Date(Date.now()+7*3600000).toISOString().slice(0,10);
    const html='<form data-suite-form="new-booking"><div class="formrow">'+
      '<div class="formfield"><label>Họ tên khách</label><input name="customer_name" required minlength="2" maxlength="100"></div>'+
      '<div class="formfield"><label>Số điện thoại</label><input name="phone" required minlength="8" maxlength="25" inputmode="tel"></div></div>'+
      '<div class="formrow"><div class="formfield"><label>Ngày đến</label><input name="day" type="date" required value="'+date+'" min="'+date+'"></div>'+
      '<div class="formfield"><label>Số khách</label><input name="party_size" type="number" min="1" max="20" value="2" required></div></div>'+
      '<div class="formrow"><div class="formfield"><label>Thời lượng</label><select name="duration_minutes">'+
      option('60','60 phút','90')+option('90','90 phút','90')+option('120','120 phút','90')+'</select></div>'+
      '<div class="formfield"><label>Giờ khách muốn đến</label><select name="preferred_time" aria-label="Giờ khách muốn đến">'+
      Array.from({length:26},(_,i)=>{const hh=String(8+Math.floor(i/2)).padStart(2,'0');const mm=i%2?'30':'00';const t=hh+':'+mm;return option(t,t,'18:00')}).join('')+
      '</select></div></div>'+
      '<div class="formrow"><div class="formfield"><label>Giờ còn bàn (đã xác minh)</label><select name="start_at" required aria-describedby="suite-time-status"><option value="">Đang tải...</option></select>'+
      '<div id="suite-time-status" role="status" aria-live="polite" class="suite-slot-status">Đang kiểm tra khả dụng...</div></div></div>'+
      '<div class="formrow"><div class="formfield"><label>Khu vực đặt bàn</label><select name="zone_id">'+
      option('auto','Để hệ thống tự xếp','auto')+
      st.layout.zones.map(z=>option(z.id,z.name,'auto')).join('')+'</select></div>'+
      '<div class="formfield"><label>Bàn cụ thể</label><select name="table_id"><option value="">Để hệ thống tự xếp</option></select></div></div>'+
      '<div class="formfield"><label>Ghi chú</label><textarea maxlength="240" name="note"></textarea></div>'+
      '<div class="subtle">Giờ trống và bàn phù hợp được kiểm tra lại ở backend khi tạo. Không thu tiền hoặc gửi SMS.</div>'+
      '<div class="modal-footer"><button class="btn" type="submit">Xác nhận đặt bàn</button></div></form>';
    deps.modal('Thêm đặt bàn',html,true);
    updateBookingTables();await slots();
  }
  function updateBookingTables(){
    const form=q('[data-suite-form="new-booking"]');if(!form)return;
    const area=form.elements.zone_id.value;
    const count=Number(form.elements.party_size.value)||1;
    const choice=form.elements.table_id,previous=choice.value;
    const available=st.layout.tables.filter(t=>t.seats>=count&&(area==='auto'||t.placement.zone_id===area));
    choice.innerHTML='<option value="">'+(area==='auto'?'Để hệ thống tự xếp':'Chọn bàn trong khu vực')+'</option>'+
      available.map(t=>option(t.id,t.label+' • '+t.seats+' chỗ',previous)).join('');
    if(!available.some(t=>t.id===previous))choice.value='';
  }
  async function slots(){
    const form=q('[data-suite-form="new-booking"]');if(!form)return;
    const serial=++slotRequest,sel=form.elements.start_at;
    const status=form.querySelector('#suite-time-status');
    const preferred=form.elements.preferred_time.value;
    const original=sel.value;
    sel.disabled=true;
    sel.innerHTML='<option value="">Đang kiểm tra...</option>';
    status.textContent='Đang kiểm tra bàn trống theo ngày, giờ và khu vực đã chọn...';
    const day=form.elements.day.value;
    const count=Number(form.elements.party_size.value);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isInteger(count)||count<1||count>20){
      status.textContent='Hãy chọn ngày và số khách hợp lệ.';return;
    }
    const params=new URLSearchParams({day,party_size:String(count),
      duration_minutes:form.elements.duration_minutes.value});
    if(st.branch)params.set('branch_id',st.branch);
    if(form.elements.zone_id.value!=='auto')params.set('zone_id',form.elements.zone_id.value);
    if(form.elements.table_id.value)params.set('table_id',form.elements.table_id.value);
    try{
      const data=await deps.api('/businesses/'+encodeURIComponent(st.bid)+'/reservations/availability?'+params);
      if(form!==q('[data-suite-form="new-booking"]')||serial!==slotRequest)return;
      const free=(data.slots||[]).filter(slot=>slot.available);
      sel.innerHTML='<option value="">Chọn giờ còn bàn</option>'+
        free.map(slot=>option(slot.start_at,time(slot.start_at)+' • '+slot.available_tables+' bàn','')).join('');
      const desired=free.find(slot=>slot.start_at.slice(11,16)===preferred);
      const previous=free.find(slot=>slot.start_at===original);
      if(desired||previous)sel.value=(desired||previous).start_at;
      sel.disabled=!free.length;
      if(!free.length){
        status.textContent=data.closed_reason||'Không có bàn trống phù hợp trong ngày. Thử ngày, khu vực hoặc số khách khác.';
      }else if(!desired){
        status.textContent='Giờ mong muốn chưa còn bàn. Chọn một trong '+free.length+' khung giờ trống bên trên.';
      }else{
        status.textContent='✓ Giờ khách muốn đến có bàn trống. Hệ thống sẽ xác minh lại khi xác nhận.';
      }
    }catch(err){
      if(form!==q('[data-suite-form="new-booking"]')||serial!==slotRequest)return;
      sel.disabled=true;sel.innerHTML='<option value="">Chưa xác minh được giờ</option>';
      status.textContent='Không thể kiểm tra giờ trống: '+(err.message||'Lỗi kết nối')+'. ';
      const retry=document.createElement('button');retry.type='button';
      retry.dataset.suite='retry-slots';retry.className='suite-slot-retry';retry.textContent='Thử lại';
      status.append(retry);
    }
  }
  async function reload(){
    st.layout=null;st.dirty=false;await fetchAll(true);draw();
  }
  async function action(type,element){
    const id=element.dataset.id||'';
    if(type==='reload')return reload();
    if(type==='retry-slots')return slots();
    if(type==='zone')return setZone(element.dataset.zone);
    if(type==='edit')return editZones();
    if(type==='new-zone')return newZone();
    if(type==='rename-zone')return renameZone();
    if(type==='delete-zone')return removeZone();
    if(type==='save-layout')return save();
    if(type==='undo-layout'){if(confirm('Hoàn tác tất cả vị trí chưa lưu?'))return reload();return}
    if(type==='table'){if(Date.now()-st.lastMoved<350)return;return inspectTable(element.dataset.tableId)}
    if(type==='floor-tab')return deps.navigate('tables');
    if(type==='booking-tab')return deps.navigate('reservations');
    if(type==='floor-booking'){deps.closeModal();return deps.navigate('reservations')}
    if(type==='new-table')return deps.newTable(st.branch);
    if(type==='floor-new-order'){deps.closeModal();return deps.newOrder(element.dataset.tableId)}
    if(type==='new-booking')return openBookingForm();
    if(type==='reset-filters'){st.date='';st.filter='all';st.search='';return draw()}
    if(type==='booking-status'){
      if(['cancelled','no_show'].includes(element.dataset.status)&&!confirm('Xác nhận đổi trạng thái lịch đặt bàn?'))return;
      await deps.api('/businesses/'+encodeURIComponent(st.bid)+'/reservations/'+encodeURIComponent(id)+'/status',
        {method:'POST',body:JSON.stringify({status:element.dataset.status})});
      deps.toast('Đã cập nhật lịch đặt');return reload();
    }
    if(type==='inquiry-status'){
      await deps.api('/businesses/'+encodeURIComponent(st.bid)+'/inquiries/'+encodeURIComponent(id)+'/status',
        {method:'POST',body:JSON.stringify({status:element.dataset.status})});
      deps.toast('Đã cập nhật liên hệ');return reload();
    }
  }
  async function submit(form){
    if(form.dataset.suiteForm==='table-placement'){
      const table=st.layout?.tables.find(t=>t.id===form.dataset.id);
      if(!table)throw Error('Không tìm thấy bàn');
      const values=Object.fromEntries(new FormData(form));
      if(!st.layout.zones.some(z=>z.id===values.zone_id))throw Error('Khu vực không hợp lệ');
      table.placement.zone_id=values.zone_id;
      table.placement.shape=values.shape;
      table.placement.x=Math.max(5,Math.min(95,Number(values.x)));
      table.placement.y=Math.max(8,Math.min(92,Number(values.y)));
      st.activeZone=values.zone_id;
      st.dirty=true;deps.closeModal();draw();
      return;
    }
    if(form.dataset.suiteForm==='contact'){
      const body=Object.fromEntries(new FormData(form));
      body.email=body.email||null;
      await deps.api('/businesses/'+encodeURIComponent(st.bid)+'/reservations/contact',
        {method:'PUT',body:JSON.stringify(body)});
      deps.toast('Đã lưu thông tin liên hệ');return reload();
    }
    if(form.dataset.suiteForm==='reservation-policy'){
      const values=new FormData(form);
      const body={
        open_time:String(values.get('open_time')||''),
        last_seating_time:String(values.get('last_seating_time')||''),
        close_time:String(values.get('close_time')||''),
        closed_weekdays:values.getAll('closed_weekdays').map(Number),
        blocked_dates:String(values.get('blocked_dates')||'').split(/[\s,;]+/).map(v=>v.trim()).filter(Boolean)
      };
      await deps.api('/businesses/'+encodeURIComponent(st.bid)+'/reservations/policy?branch_id='+encodeURIComponent(st.branch),
        {method:'PUT',body:JSON.stringify(body)});
      deps.toast(tr('Đã lưu quy tắc đặt bàn','Booking rules saved'));return reload();
    }
    if(form.dataset.suiteForm==='new-booking'){
      const body=Object.fromEntries(new FormData(form));
      if(!body.start_at)throw Error('Vui lòng chọn giờ còn bàn');
      body.request_id=next();body.party_size=Number(body.party_size);
      body.duration_minutes=Number(body.duration_minutes);
      delete body.day;
      delete body.preferred_time;
      if(body.zone_id==='auto')delete body.zone_id;
      if(st.branch)body.branch_id=st.branch;
      if(!body.table_id)delete body.table_id;
      await deps.api('/businesses/'+encodeURIComponent(st.bid)+'/reservations',
        {method:'POST',body:JSON.stringify(body)});
      deps.closeModal();deps.toast('Đã tạo lịch đặt bàn, chờ xác nhận');return reload();
    }
  }
  // Capture only suite controls; leave all existing merchant events untouched.
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-suite]');
    if(!button)return;
    event.preventDefault();event.stopPropagation();
    if(button.disabled)return;
    Promise.resolve(action(button.dataset.suite,button)).catch(err=>deps.toast(err.message,true));
  },true);
  document.addEventListener('submit',event=>{
    const form=event.target.closest('form[data-suite-form]');if(!form)return;
    event.preventDefault();event.stopPropagation();
    const button=form.querySelector('[type="submit"]');
    if(button?.disabled)return;if(button)button.disabled=true;
    Promise.resolve(submit(form)).catch(err=>deps.toast(err.message,true))
      .finally(()=>{if(button)button.disabled=false});
  },true);
  document.addEventListener('change',event=>{
    const el=event.target;if(!el.matches('[data-suite-change]'))return;
    event.stopPropagation();
    const type=el.dataset.suiteChange;
    if(type==='branch'){
      if(st.dirty&&!confirm('Sơ đồ chưa lưu. Chuyển chi nhánh và bỏ thay đổi?')){el.value=st.branch;return}
      st.branch=el.value;st.layout=null;st.loading=null;st.activeZone=null;st.editing=false;
      fetchAll(true).then(draw).catch(err=>deps.toast(err.message,true));
    }else if(type==='filter'){st.filter=el.value;draw()}
    else if(type==='date'){st.date=el.value;draw()}
  },true);
  document.addEventListener('input',event=>{
    const el=event.target;
    if(el.matches('[data-suite-input="search"]')){
      st.search=el.value;
      const selection=el.selectionStart;
      draw();
      const fresh=q('[data-suite-input="search"]');
      fresh?.focus();
      if(typeof selection==='number')fresh?.setSelectionRange(selection,selection);
    }
    if(el.closest('[data-suite-form="new-booking"]')){
      if(el.name==='party_size'){updateBookingTables();slots();}
    }
  },true);
  document.addEventListener('change',event=>{
    if(event.target.closest('[data-suite-form="new-booking"]')&&
      ['day','party_size','duration_minutes','zone_id','table_id','preferred_time'].includes(event.target.name)){
        if(event.target.name==='zone_id')updateBookingTables();
        if(event.target.name!=='party_size')slots();
      }
  },true);
  return {renderFloorplan,renderReservations,mount,invalidate:()=>{
    st.bid=null;st.layout=null;st.bookings=[];st.policy=null;st.dirty=false;st.editing=false;
  }, refresh:reload};
};
})();