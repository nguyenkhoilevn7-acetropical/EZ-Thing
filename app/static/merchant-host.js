/* EZ Thing Host Control: live tenant/branch table service and reservations.
   Admin's interactive preview uses the existing zero-write API sandbox. */
(() => {
"use strict";
window.EZHostWorkstation = function init({api,E,toast,getState,modal,closeModal,previewOnly,onCreatePhysicalTable,onOpenOrder}) {
  const state=getState, biz=()=>state().business||{},id=()=>encodeURIComponent(biz().id||"");
  const url=p=>"/businesses/"+id()+p;
  const T=(vi,en)=>window.EZI18N?.language?.()==="en"?en:vi;
  const uid=()=>globalThis.crypto?.randomUUID?.()||
    "host-"+Date.now().toString(36)+Math.random().toString(36).slice(2);
  const fmtTime=s=>s?new Date(s).toLocaleString("vi-VN",{
    day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"—";
  const branchList=()=>state().cache.branches||[];
  const assigned=()=>state().workstation?.branch_id||"";
  let board=null,bookings=[],floorplan=null,branchId="",view="tables",filter="all",search="",
      zone="all",editing=false,loading=false,ready=false,serial=0,saving=false;
  const STATUS={
    available:["Trống","Available","free"],occupied:["Có khách","Occupied","busy"],
    cleaning:["Chờ dọn","Cleaning","cleaning"],blocked:["Tạm khóa","Blocked","blocked"],
    reserved:["Đã đặt","Reserved","reserved"]
  };
  const esc=x=>E(String(x??""));
  const owner=()=>biz().role==="owner";
  function activeBranch(){
    const branches=branchList(),allowed=assigned();
    if(allowed)return allowed;
    return branchId||branches[0]?.id||"";
  }
  const at=()=>board?.tables||[];
  const status=t=>STATUS[t.status]||STATUS.available;
  function card(t){
    const st=status(t),s=t.status,actions={
      available:[["seat","Nhận khách"],["block","Khóa bàn"]],
      occupied:[["update","Sửa thông tin"],["join","Thêm bàn"],["transfer","Chuyển bàn"],["release","Trả bàn"]],
      cleaning:[["ready","Đã dọn xong"]],blocked:[["unblock","Mở khóa"]]
    }[s]||[];
    return '<article class="ezhost-room-table '+st[2]+'" data-host-table="'+esc(t.id)+'">'+
      '<div class="ezhost-room-card-top"><div><span class="ezhost-room-seats">'+
      esc(t.seats)+' '+T("chỗ","seats")+'</span><h3>'+esc(t.label)+'</h3></div>'+
      '<span class="ezhost-room-status '+st[2]+'">● '+T(st[0],st[1])+'</span></div>'+
      '<div class="ezhost-room-meta">'+
      (t.guest_count?'<span>👥 '+esc(t.guest_count)+' '+T("khách","guests")+'</span>':"")+
      (t.guest_name?'<span>👤 '+esc(t.guest_name)+'</span>':"")+
      (t.seated_at?'<span>🕒 '+fmtTime(t.seated_at)+'</span>':"")+
      (t.group_id?'<span>🔗 '+T("Bàn ghép","Linked table")+'</span>':"")+
      (t.has_open_check?'<span>🧾 '+esc(t.order_count)+' '+T("đơn chưa thu","open checks")+'</span>':"")+
      (t.note?'<p>'+esc(t.note)+'</p>':"")+'</div>'+
      '<div class="ezhost-room-actions">'+
      actions.filter(([act])=>!(t.has_open_check&&["transfer","release"].includes(act)))
        .map(([act,label],i)=>'<button type="button" data-ezhost-action="'+act+
          '" data-value="'+esc(t.id)+'" class="'+(i===0?"primary":"")+'">'+
          T(label,{seat:"Seat",block:"Block",update:"Edit",join:"Add table",
            transfer:"Move",release:"Release",ready:"Ready",unblock:"Unblock"}[act])+
          '</button>').join("")+
      (t.group_id?'<button type="button" data-ezhost-action="unjoin" data-value="'+
        esc(t.id)+'">'+T("Tách bàn","Unlink")+'</button>':"")+
      '</div></article>';
  }
  function summary(){
    const all=at(),count=s=>all.filter(t=>t.status===s).length;
    return '<div class="ezhost-room-summary">'+
      [["available",T("Bàn trống","Available")],["occupied",T("Đang phục vụ","Occupied")],
       ["cleaning",T("Chờ dọn","Cleaning")],["blocked",T("Tạm khóa","Blocked")]]
      .map(([s,label])=>'<button type="button" class="ezhost-room-kpi '+s+
          (filter===s?" selected":"")+'" data-ezhost-filter="'+s+'">'+
        '<span>'+label+'</span><strong>'+count(s)+'</strong></button>').join("")+'</div>';
  }
  function tableScreen(){
    const rows=at().filter(t=>(filter==="all"||t.status===filter)&&
      t.label.toLocaleLowerCase("vi").includes(search.toLocaleLowerCase("vi")));
    return summary()+'<div class="ezhost-room-section"><div class="ezhost-room-toolbar">'+
      '<h3>'+T("Sơ đồ trạng thái bàn","Table occupancy")+
      ' <small>'+rows.length+' / '+at().length+'</small></h3>'+
      '<div class="ezhost-room-toolbar-actions">'+
      '<label class="ezhost-room-search">⌕ <input data-ezhost-search placeholder="'+
      T("Tìm tên bàn…","Search tables…")+'" value="'+esc(search)+'" aria-label="'+
      T("Tìm bàn","Search table")+'"></label>'+
      '<button type="button" data-ezhost-filter="all" class="'+(filter==="all"?"selected":"")+
      '">'+T("Tất cả bàn","All tables")+'</button></div></div>'+
      '<div class="ezhost-room-grid">'+rows.map(card).join("")+
      (!rows.length?'<div class="ezhost-room-empty">'+
      T("Không có bàn phù hợp. Thử đổi bộ lọc.","No matching tables; change filters.")+
      '</div>':"")+'</div></div>';
  }
  function bookingCard(r){
    const statusName={pending:"Chờ xác nhận",confirmed:"Đã xác nhận",
      seated:"Đã nhận khách",cancelled:"Đã hủy",no_show:"Không đến",completed:"Hoàn tất"};
    const active=["pending","confirmed"].includes(r.status);
    return '<article class="ezhost-booking-card" data-booking-id="'+esc(r.id)+'">'+
      '<div class="ezhost-booking-top"><div><strong>'+esc(r.customer_name)+'</strong>'+
      '<span>'+esc(r.phone)+'</span></div><span class="ezhost-booking-status '+esc(r.status)+'">'+
      esc(statusName[r.status]||r.status)+'</span></div>'+
      '<div class="ezhost-booking-meta"><span>🗓 '+fmtTime(r.scheduled_at)+
      '</span><span>🪑 '+esc(r.table_label)+'</span><span>👥 '+esc(r.party_size)+
      '</span></div>'+(r.note?'<p>'+esc(r.note)+'</p>':"")+
      '<div class="ezhost-booking-actions">'+
      (active?'<button type="button" data-ezhost-booking="edit" data-value="'+esc(r.id)+'">'+
      T("Sửa thông tin","Edit")+'</button>':"")+
      (r.status==="pending"?'<button type="button" data-ezhost-booking="confirmed" data-value="'+
        esc(r.id)+'">'+T("Xác nhận","Confirm")+'</button>':"")+
      (r.status==="confirmed"?'<button type="button" data-ezhost-booking="seated" data-value="'+
        esc(r.id)+'">'+T("Khách đã tới","Check in")+'</button>'+
        '<button type="button" data-ezhost-booking="no_show" data-value="'+esc(r.id)+'">'+
        T("Không đến","No-show")+'</button>':"")+
      (active?'<button type="button" class="danger" data-ezhost-booking="cancelled" data-value="'+
      esc(r.id)+'">'+T("Hủy đặt bàn","Cancel")+'</button>':"")+'</div></article>';
  }
  function bookingScreen(){
    const visible=bookings.filter(r=>!["cancelled","completed"].includes(r.status));
    return '<section class="ezhost-room-section"><div class="ezhost-room-toolbar"><div><h3>'+
      T("Đặt bàn & danh sách chờ","Reservations & arrivals")+'</h3><p>'+
      T("Chỉnh giờ, số khách, đổi bàn, xác nhận và hủy đặt chỗ.",
        "Edit time, guests, table, confirm or cancel bookings.")+'</p></div>'+
      '<button type="button" class="ezhost-room-primary" data-ezhost-action="book">'+
      '+ '+T("Tạo đặt bàn","New booking")+'</button></div>'+
      '<div class="ezhost-booking-grid">'+
      visible.map(bookingCard).join("")+
      (!visible.length?'<div class="ezhost-room-empty">'+T("Chưa có đặt bàn.","No reservations.")+'</div>':"")+
      '</div></section>';
  }
  function floorScreen(){
    if(!floorplan)return '<div class="ezhost-room-empty">'+T("Đang tải sơ đồ…","Loading floorplan…")+'</div>';
    const zones=floorplan.zones||[],layout=floorplan.tables||[],active=zones.find(z=>z.id===zone)||zones[0];
    const tiles=layout.filter(t=>t.placement?.zone_id===active?.id);
    return '<section class="ezhost-room-section ezhost-floor"><div class="ezhost-room-toolbar">'+
      '<div><h3>'+T("Sơ đồ bố trí bàn","Table layout")+'</h3><p>'+
      T("Kéo bàn tới vị trí mong muốn; chỉ Owner được lưu thay đổi.","Drag to position tables; only the Owner may save.")+
      '</p></div><div class="ezhost-room-toolbar-actions">'+
      (owner()?'<button type="button" data-ezhost-action="add-physical-table">'+T("+ Tạo bàn mới","+ New table")+'</button>':"")+
      (owner()?'<button type="button" data-ezhost-action="new-zone">'+T("+ Thêm khu","+ Add zone")+'</button>':"")+
      (owner()?'<button type="button" class="ezhost-room-primary" data-ezhost-action="save-floor">'+
        T("Lưu sơ đồ","Save layout")+'</button>':"")+'</div></div>'+
      '<div class="ezhost-room-zones">'+zones.map(z=>'<button type="button" data-ezhost-zone="'+
        esc(z.id)+'" class="'+(z.id===active?.id?"active":"")+'">'+esc(z.name)+'</button>').join("")+'</div>'+
      '<div class="ezhost-room-map" data-ezhost-map aria-label="'+T("Sơ đồ bàn kéo thả","Draggable floorplan")+'">'+
      tiles.map(t=>'<div role="button" tabindex="0" data-ezhost-placement="'+esc(t.id)+'" '+
      'class="ezhost-map-table '+(t.occupied?"busy":"")+'" style="left:'+Number(t.placement.x)+
      '%;top:'+Number(t.placement.y)+'%"><strong>'+esc(t.label)+'</strong>'+
      '<small>'+esc(t.seats)+' '+T("chỗ","seats")+'</small></div>').join("")+
      '</div>'+
      (owner()?'<div class="ezhost-room-zone-transfer">'+
      '<label>'+T("Chọn bàn","Select table")+'<select data-ezhost-floor-table>'+
      layout.map(t=>'<option value="'+esc(t.id)+'">'+esc(t.label)+'</option>').join("")+
      '</select></label><label>'+T("Chuyển sang khu vực","Move to zone")+
      '<select data-ezhost-floor-zone>'+zones.map(z=>'<option value="'+esc(z.id)+'">'+
      esc(z.name)+'</option>').join("")+'</select></label>'+
      '<button type="button" data-ezhost-action="assign-zone">'+T("Áp dụng","Apply")+'</button>'+
      '</div>':"")+
      '<p class="ezhost-room-hint">'+T(
        "Vị trí bàn là sơ đồ trực quan. Di chuyển bàn trên sơ đồ không chuyển hóa đơn hoặc khách đang dùng bàn.",
        "Layout positions are visual only; moving tiles does not move financial checks or seated guests.")+
      '</p></section>';
  }
  function html(){
    return '<section class="ezhost-room" id="ezhost-workspace">'+
      '<header class="ezhost-room-header"><div><span>EZ THING · FRONT DESK</span>'+
      '<h2>'+T("Lễ tân & điều phối bàn","Host & table operations")+'</h2>'+
      '<p>'+T("Nhận khách, chuyển bàn, đặt bàn và theo dõi trạng thái từng khu vực.",
      "Seat guests, move tables, manage bookings and floor areas.")+'</p></div>'+
      '<div class="ezhost-room-header-actions">'+
      (branchList().length>1?'<label>'+T("Chi nhánh","Branch")+
        '<select data-ezhost-branch>'+
        branchList().filter(b=>!assigned()||b.id===assigned())
        .map(b=>'<option value="'+esc(b.id)+'"'+(b.id===activeBranch()?" selected":"")+'>'+
        esc(b.name)+'</option>').join("")+'</select></label>':"")+
      '<button type="button" data-ezhost-action="reload">↻ '+T("Cập nhật","Refresh")+'</button>'+
      '<button type="button" data-ezws="fullscreen" aria-label="'+T("Toàn màn hình","Fullscreen")+'">⛶</button>'+
      '</div></header>'+
      '<div class="ezhost-room-tabs" role="tablist">'+
      [["tables",T("Vận hành bàn","Table operations")],["bookings",T("Đặt bàn","Bookings")],
       ["floor",T("Chỉnh sơ đồ","Floorplan")]]
      .map(([id,name])=>'<button type="button" role="tab" data-ezhost-tab="'+id+
      '" aria-selected="'+(id===view)+'" class="'+(id===view?"active":"")+'">'+name+'</button>')
      .join("")+'</div>'+
      (loading?'<p class="ezhost-room-hint">'+T("Đang đồng bộ…","Syncing…")+'</p>':"")+
      (view==="tables"?tableScreen():view==="bookings"?bookingScreen():floorScreen())+
      '<div class="ezhost-room-footer">'+(previewOnly()?
        '🧪 '+T("Dùng thử tương tác: không lưu dữ liệu thật.","Interactive demo: no real records are changed."):
        '🔒 '+T("Mọi thay đổi được ghi nhật ký theo nhân viên và chi nhánh.",
          "All changes are audited by employee and branch."))+'</div></section>';
  }
  function render(){return html()}
  function paint(){
    const root=document.getElementById("ezhost-workspace");
    if(root)root.outerHTML=html();
  }
  async function load(){
    const key=id(),generation=++serial;
    if(!key)return;
    branchId=activeBranch();loading=true;paint();
    try{
      const [newBoard,newBookings,newFloor]=await Promise.all([
        api(url("/host/board?branch_id="+encodeURIComponent(branchId))),
        api(url("/reservations")),
        api(url("/floorplan?branch_id="+encodeURIComponent(branchId)))
      ]);
      if(generation!==serial||id()!==key)return;
      board=newBoard;bookings=newBookings.filter(r=>r.branch_id===branchId);
      floorplan=newFloor;ready=true;
    }catch(e){if(generation===serial)toast(e.message,true)}
    finally{if(generation===serial){loading=false;paint()}}
  }
  function mount(){if(!ready||branchId!==activeBranch())load().catch(e=>toast(e.message,true))}
  function invalidate(){serial++;ready=false;board=null;bookings=[];floorplan=null;loading=false}
  function targetSelect(origin){
    return '<label>'+T("Chọn bàn đích","Destination table")+
      '<select name="target_table_id" required><option value="">'+T("Chọn bàn","Choose table")+'</option>'+
      at().filter(x=>x.id!==origin.id&&x.status==="available").map(x=>
      '<option value="'+esc(x.id)+'">'+esc(x.label)+' · '+esc(x.seats)+' '+T("chỗ","seats")+
      '</option>').join("")+'</select></label>';
  }
  function roomZone(t){
    const position=floorplan?.tables?.find(x=>x.id===t.id)?.placement;
    return floorplan?.zones?.find(z=>z.id===position?.zone_id)?.name||
      T("Khu vực chung","Main area");
  }
  function nearbyBookings(t){
    const time=Date.now();
    return bookings.filter(r=>r.table_id===t.id&&r.status==="confirmed"&&
      new Date(r.scheduled_at).getTime()<=time+3*3600000&&
      (!r.ends_at||new Date(r.ends_at).getTime()>time-3600000))
      .sort((a,b)=>Math.abs(new Date(a.scheduled_at)-time)-Math.abs(new Date(b.scheduled_at)-time));
  }
  function seatDialog(t,reservation=null){
    const choices=nearbyBookings(t);
    const linked=reservation||choices.find(r=>{
      const start=new Date(r.scheduled_at).getTime(),end=new Date(r.ends_at).getTime();
      return Date.now()>=start-30*60000&&Date.now()<=end;
    })||null;
    const count=linked?.party_size||t.guest_count||1;
    const max=Math.max(1,Number(t.seats)||1);
    const note=linked?.note||t.note||"";
    const match=choices.some(r=>r.id===linked?.id);
    const selectOptions='<option value="">'+T("Khách vãng lai · Không có đặt bàn",
      "Walk-in · No reservation")+'</option>'+choices.map(r=>
      '<option value="'+esc(r.id)+'"'+(r.id===linked?.id?" selected":"")+'>'+
      esc(r.customer_name)+' · '+fmtTime(r.scheduled_at)+'</option>').join("");
    modal(T("Nhận khách","Seat guests")+' · '+t.label,
      '<form class="ezhost-seat-form" data-ezhost-form="action" data-id="'+esc(t.id)+
      '" data-command="seat" data-capacity="'+max+'">'+
      '<div class="ezhost-seat-details"><span>🪑 '+esc(t.label)+'</span>'+
      '<span>'+esc(roomZone(t))+'</span><span>👥 '+max+' '+T("chỗ","seats")+'</span>'+
      '<span class="ezhost-seat-free">● '+T("Bàn trống","Available")+'</span></div>'+
      (choices.length?'<label>'+T("Liên kết lịch đặt bàn","Link reservation")+
        '<select name="reservation_id" data-ezhost-booking-select>'+selectOptions+'</select></label>':
        '<input type="hidden" name="reservation_id" value="">')+
      '<div class="ezhost-form-grid"><label>'+T("Tên khách (không bắt buộc)","Guest name (optional)")+
      '<input name="guest_name" autocomplete="off" maxlength="100" value="'+esc(linked?.customer_name||"")+
      '" placeholder="'+T("Tên người đại diện","Guest name")+'"></label>'+
      '<label>'+T("Điện thoại (không bắt buộc)","Phone (optional)")+
      '<input name="guest_phone" type="tel" inputmode="tel" maxlength="25" value="'+
      esc(linked?.phone||"")+'" placeholder="09..."></label></div>'+
      '<label>'+T("Số khách thực tế","Guests arriving")+
      '<div class="ezhost-guest-stepper">'+
      '<button type="button" data-ezhost-step="-1" aria-label="'+T("Giảm một khách","Remove one guest")+'">−</button>'+
      '<input name="guest_count" type="number" inputmode="numeric" min="1" max="'+max+
      '" value="'+esc(Math.min(max,count))+'" required>'+
      '<button type="button" data-ezhost-step="1" aria-label="'+T("Thêm một khách","Add one guest")+'">+</button></div>'+
      '<small class="ezhost-capacity-hint">'+T("Sức chứa tối đa: ","Maximum capacity: ")+max+
      ' '+T("khách. Nếu vượt, hãy chọn bàn lớn hơn.","guests. Choose a larger table if needed.")+
      '</small></label>'+
      (linked&&count>max?'<p class="ezhost-capacity-alert">'+
        T("Lịch đặt có nhiều khách hơn số ghế; vui lòng đổi hoặc ghép bàn trước.",
          "The reservation exceeds table capacity; change or combine tables first.")+'</p>':"")+
      '<label>'+T("Ghi chú tiếp đón","Reception note")+
      '<textarea name="note" maxlength="240" rows="2" placeholder="'+T(
        "Ví dụ: Ghế trẻ em, dị ứng thực phẩm…","For example: High chair, food allergy…")+
      '">'+esc(note)+'</textarea></label>'+
      (previewOnly()?'<p class="ezhost-demo-note">🧪 '+T(
        "Chế độ xem thử: xác nhận chỉ thay đổi dữ liệu trong phiên xem thử.",
        "Interactive preview: this only changes the in-session demo.")+'</p>':"")+
      '<footer class="modal-footer ezhost-form-footer">'+
      '<button type="button" class="btn secondary" data-ezhost-action="dismiss">'+
      T("Quay lại","Back")+'</button>'+
      '<button type="submit" class="btn ezhost-confirm" data-ezhost-confirm>'+
      T("✓ Xác nhận nhận khách","✓ Confirm seating")+'</button></footer></form>');
    document.querySelector('[data-ezhost-form="action"] [name="guest_count"]')?.focus();
  }
  function actionDialog(action,t,booking=null){
    if(action==="seat")return seatDialog(t,booking);
    const label={release:"Trả bàn",cleaning:"Chờ dọn",
      ready:"Đã dọn xong",block:"Khóa bàn",unblock:"Mở khóa",update:"Sửa thông tin",
      transfer:"Chuyển bàn",join:"Ghép bàn",unjoin:"Tách bàn"}[action]||action;
    if(["ready","unblock","unjoin","release"].includes(action)){
      return submitAction(t,{action,expected_revision:t.revision});
    }
    const destination=["transfer","join"].includes(action);
    modal(label+' · '+t.label,
      '<form data-ezhost-form="action" data-id="'+esc(t.id)+'" data-command="'+action+'">'+
      '<p class="ezhost-form-hint">'+(destination?
        T("Chỉ chuyển phiên nhận khách. Hóa đơn POS chưa thu không được chuyển âm thầm.",
          "Only host seating is moved; unpaid POS checks cannot be moved silently."):
        T("Thông tin sẽ được ghi nhận cho chi nhánh được phân công.",
          "Changes are logged under the assigned branch."))+'</p>'+
      (destination?targetSelect(t):"")+
      (action==="update"?
        '<label>'+T("Số khách","Guests")+'<input name="guest_count" type="number" min="1" max="'+
        esc(t.seats)+'" value="'+esc(t.guest_count||1)+'" required></label>'+
        '<div class="ezhost-form-grid"><label>'+T("Tên khách","Guest name")+
        '<input name="guest_name" maxlength="100" value="'+esc(t.guest_name||"")+'"></label>'+
        '<label>'+T("Điện thoại","Phone")+
        '<input name="guest_phone" type="tel" maxlength="25" value="'+esc(t.guest_phone||"")+
        '"></label></div>':"")+
      '<label>'+T("Ghi chú","Notes")+'<textarea name="note" maxlength="240" rows="2">'+
        esc(t.note||"")+'</textarea></label>'+
      '<footer class="modal-footer ezhost-form-footer"><button type="button" class="btn secondary" data-ezhost-action="dismiss">'+
      T("Quay lại","Back")+'</button><button type="submit" class="btn ezhost-confirm">'+
      T(label,action)+'</button></footer></form>');
  }
  async function submitAction(t,body){
    const result=await api(url("/host/tables/"+encodeURIComponent(t.id)+
      "/action?branch_id="+encodeURIComponent(activeBranch())),{
      method:"POST",body:JSON.stringify(body)
    });
    board=result;
    if(body.reservation_id)bookings=bookings.map(r=>
      r.id===body.reservation_id?{...r,status:"seated"}:r);
    paint();closeModal?.();
    if(body.action==="seat"){
      modal(T("Đã nhận khách","Guests seated")+' · '+t.label,
        '<div class="ezhost-seat-success" role="status">'+
        '<strong>✓ '+T("Nhận khách thành công","Guests seated successfully")+'</strong>'+
        '<p>🪑 '+esc(t.label)+' · '+esc(body.guest_count||1)+' '+T("khách","guests")+
        '</p><p>'+T("Bàn đã chuyển sang Đang phục vụ. Máy nhận Order có thể gọi món cho bàn này.",
        "The table is now occupied. The Order terminal can take its check.")+'</p>'+
        '<div class="ezhost-success-actions">'+
        '<button type="button" class="btn secondary" data-ezhost-action="dismiss">'+
        T("Tiếp tục lễ tân","Continue front desk")+'</button>'+
        ((biz().role==="owner"||biz().role==="manager")&&onOpenOrder?
          '<button type="button" class="btn ezhost-confirm" data-ezhost-action="start-order" data-value="'+
          esc(t.id)+'">'+T("Gọi món ngay","Take order now")+'</button>':"")+
        '</div></div>');
    }else toast(T("Đã cập nhật bàn","Table updated"));
  }
  function bookingDialog(r){
    const edit=Boolean(r),target=r?.table_id||"",defaultTime=new Date(Date.now()+86400_000);
    defaultTime.setMinutes(defaultTime.getMinutes()<30?30:60,0,0);
    const local=edit&&r.scheduled_at?new Date(new Date(r.scheduled_at).getTime()-
      new Date(r.scheduled_at).getTimezoneOffset()*60000).toISOString().slice(0,16):
      new Date(defaultTime.getTime()-defaultTime.getTimezoneOffset()*60000).toISOString().slice(0,16);
    modal(edit?T("Sửa lịch đặt bàn","Edit reservation"):T("Tạo lịch đặt bàn","New reservation"),
      '<form data-ezhost-form="booking" data-id="'+esc(r?.id||"")+'">'+
      '<div class="ezhost-form-grid"><label>'+T("Tên khách","Guest name")+
      '<input name="customer_name" required minlength="2" maxlength="100" value="'+esc(r?.customer_name||"")+
      '" placeholder="Nguyễn Văn A"></label>'+
      '<label>'+T("Điện thoại","Phone")+'<input name="phone" required minlength="8" maxlength="25" value="'+
      esc(r?.phone||"")+'" placeholder="090..."></label>'+
      '<label>'+T("Ngày & giờ tới","Arrival")+'<input name="start_at" type="datetime-local" required value="'+
      esc(local)+'"></label>'+
      '<label>'+T("Số khách","Guests")+'<input name="party_size" type="number" min="1" max="20" value="'+
      esc(r?.party_size||2)+'" required></label>'+
      '<label>'+T("Thời gian sử dụng bàn","Duration")+
      '<select name="duration_minutes">'+[60,90,120].map(n=>'<option value="'+n+'"'+
      (r&&r.scheduled_at&&r.ends_at&&
       (new Date(r.ends_at)-new Date(r.scheduled_at))/60000===n||!r&&n===90?" selected":"")+
      '>'+n+' phút</option>').join("")+'</select></label>'+
      '<label>'+T("Bàn","Table")+'<select name="table_id" required>'+
      '<option value="">'+T("Chọn bàn","Choose table")+'</option>'+
      at().map(t=>'<option value="'+esc(t.id)+'"'+(target===t.id?" selected":"")+'>'+
      esc(t.label)+' · '+t.seats+' '+T("chỗ","seats")+'</option>').join("")+
      '</select></label></div><label>'+T("Ghi chú","Note")+
      '<textarea name="note" maxlength="240" rows="2">'+esc(r?.note||"")+'</textarea></label>'+
      '<footer><button type="button" data-ezhost-action="dismiss">'+T("Đóng","Close")+
      '</button><button type="submit" class="ezhost-room-primary">'+
      T("Lưu đặt bàn","Save booking")+'</button></footer></form>');
  }
  async function bookingAction(rid,action){
    if(["cancelled","no_show"].includes(action)&&!confirm(
      action==="cancelled"?T("Hủy lịch đặt này?","Cancel this reservation?"):
      T("Đánh dấu khách không đến?","Mark as no-show?")))return;
    await api(url("/reservations/"+encodeURIComponent(rid)+"/status"),{
      method:"POST",body:JSON.stringify({status:action})
    });
    bookings=(await api(url("/reservations"))).filter(r=>r.branch_id===activeBranch());
    paint();toast(T("Đã cập nhật lịch đặt bàn","Reservation updated"));
  }
  function addZone(){
    if(!owner()||!floorplan)return;
    const name=prompt(T("Tên khu vực mới","New zone name"));
    if(!name?.trim())return;
    const z={id:"zone-"+uid().slice(0,8).replace(/[^a-z0-9-]/gi,""),name:name.trim().slice(0,45)};
    if(floorplan.zones.length>=12){toast(T("Tối đa 12 khu vực","Max 12 zones"),true);return}
    floorplan.zones.push(z);zone=z.id;paint();
  }
  function dragStart(event){
    const item=event.target.closest("[data-ezhost-placement]");
    if(!item||!owner()||!floorplan||view!=="floor")return;
    if(event.button!==0)return;
    const map=item.closest("[data-ezhost-map]"),ref=map?.getBoundingClientRect();
    if(!ref||ref.width<1||ref.height<1)return;
    item.setPointerCapture?.(event.pointerId);
    const p=floorplan.tables.find(t=>t.id===item.dataset.ezhostPlacement);
    if(!p)return;
    event.preventDefault();
    const onMove=e=>{
      const x=Math.min(95,Math.max(4,(e.clientX-ref.left)/ref.width*100));
      const y=Math.min(93,Math.max(6,(e.clientY-ref.top)/ref.height*100));
      item.style.left=x+"%";item.style.top=y+"%";
      p.placement.x=Math.round(x*100)/100;
      p.placement.y=Math.round(y*100)/100;
    };
    const onUp=()=>{
      item.removeEventListener("pointermove",onMove);
      item.removeEventListener("pointerup",onUp);
      item.removeEventListener("pointercancel",onUp);
    };
    item.addEventListener("pointermove",onMove);
    item.addEventListener("pointerup",onUp,{once:true});
    item.addEventListener("pointercancel",onUp,{once:true});
  }
  async function saveFloor(){
    if(!owner()||!floorplan)return;
    const body={branch_id:activeBranch(),revision:floorplan.revision,
      zones:floorplan.zones,
      placements:floorplan.tables.map(t=>({
        table_id:t.id,zone_id:t.placement.zone_id,x:t.placement.x,
        y:t.placement.y,shape:t.placement.shape||"round"
      }))};
    const saved=await api(url("/floorplan"),{method:"PUT",body:JSON.stringify(body)});
    floorplan=saved;paint();toast(T("Đã lưu sơ đồ bàn","Floorplan saved"));
  }
  document.addEventListener("click",event=>{
    const btn=event.target.closest("[data-ezhost-action],[data-ezhost-tab],"+
      "[data-ezhost-filter],[data-ezhost-zone],[data-ezhost-booking],[data-ezhost-step]");
    if(!btn||!document.getElementById("ezhost-workspace")&&
      !btn.closest("[data-ezhost-form]"))return;
    event.preventDefault();event.stopImmediatePropagation();
    if(btn.hasAttribute("data-ezhost-step")){
      const form=btn.closest('[data-ezhost-form="action"]');
      const field=form?.querySelector('[name="guest_count"]');
      if(field){
        const max=Number(field.max)||60,min=1;
        field.value=String(Math.max(min,Math.min(max,
          (Number(field.value)||1)+Number(btn.dataset.ezhostStep))));
      }
      return;
    }
    const job=async()=>{
      if(btn.dataset.ezhostTab){view=btn.dataset.ezhostTab;paint();return}
      if(btn.dataset.ezhostZone){zone=btn.dataset.ezhostZone;paint();return}
      if(btn.dataset.ezhostFilter){filter=btn.dataset.ezhostFilter;paint();return}
      if(btn.dataset.ezhostBooking){
        const r=bookings.find(x=>x.id===btn.dataset.value);
        if(!r)return;
        if(btn.dataset.ezhostBooking==="edit")bookingDialog(r);
        else if(btn.dataset.ezhostBooking==="seated"){
          const t=at().find(x=>x.id===r.table_id);
          if(!t||t.status!=="available")throw Error(T(
            "Bàn đặt không còn trống; hãy kiểm tra sơ đồ bàn.","Reserved table is no longer available."));
          actionDialog("seat",t,r);
        }else await bookingAction(r.id,btn.dataset.ezhostBooking);
        return;
      }
      const action=btn.dataset.ezhostAction;
      if(action==="dismiss"){closeModal?.();return}
      if(action==="reload"){await load();return}
      if(action==="book"){bookingDialog(null);return}
      if(action==="new-zone"){addZone();return}
      if(action==="save-floor"){await saveFloor();return}
      if(action==="add-physical-table"){
        onCreatePhysicalTable?.(activeBranch());return;
      }
      if(action==="assign-zone"){
        const tid=document.querySelector("[data-ezhost-floor-table]")?.value;
        const newZone=document.querySelector("[data-ezhost-floor-zone]")?.value;
        const tab=floorplan?.tables.find(x=>x.id===tid);
        if(!tab||!floorplan?.zones.some(x=>x.id===newZone))return;
        tab.placement.zone_id=newZone;zone=newZone;paint();return;
      }
      if(action==="start-order"){
        closeModal?.();onOpenOrder?.(btn.dataset.value);return;
      }
      const t=at().find(x=>x.id===btn.dataset.value);
      if(t)await actionDialog(action,t);
    };
    job().catch(e=>toast(e.message,true));
  },true);
  document.addEventListener("input",event=>{
    if(event.target.matches("[data-ezhost-search]")){
      search=event.target.value;
      document.querySelectorAll(".ezhost-room-table").forEach(card=>{
        const t=at().find(t=>t.id===card.dataset.hostTable);
        card.hidden=!t?.label.toLocaleLowerCase("vi").includes(search.toLocaleLowerCase("vi"));
      });
    }
  },true);
  document.addEventListener("change",event=>{
    if(event.target.matches("[data-ezhost-booking-select]")){
      const r=bookings.find(x=>x.id===event.target.value);
      const form=event.target.closest('[data-ezhost-form="action"]');
      if(form){
        const name=form.querySelector('[name="guest_name"]'),
          phone=form.querySelector('[name="guest_phone"]'),
          count=form.querySelector('[name="guest_count"]'),
          note=form.querySelector('[name="note"]');
        if(name)name.value=r?.customer_name||"";
        if(phone)phone.value=r?.phone||"";
        if(note)note.value=r?.note||"";
        if(count&&r)count.value=String(Math.min(Number(count.max)||60,r.party_size));
      }
      return;
    }
    if(event.target.matches("[data-ezhost-branch]")){
      branchId=event.target.value;ready=false;zone="all";filter="all";load().catch(e=>toast(e.message,true));
    }
  },true);
  document.addEventListener("submit",event=>{
    const form=event.target.closest("[data-ezhost-form]");
    if(!form)return;
    event.preventDefault();event.stopImmediatePropagation();
    if(saving)return;
    const data=Object.fromEntries(new FormData(form));
    const button=form.querySelector("[type=submit]");
    if(form.dataset.command==="seat"||form.dataset.command==="update"){
      const count=Number(data.guest_count);
      const capacity=Number(form.dataset.capacity||form.querySelector('[name="guest_count"]')?.max);
      if(!Number.isInteger(count)||count<1||count>capacity){
        toast(T("Số khách phải từ 1 đến sức chứa tối đa của bàn.",
          "Guest count must be within table capacity."),true);
        return;
      }
    }
    saving=true;
    if(button){button.disabled=true;button.textContent=T("Đang lưu…","Saving…")}
    const work=async()=>{
      if(form.dataset.ezhostForm==="action"){
        const t=at().find(x=>x.id===form.dataset.id);
        if(!t)throw Error(T("Không tìm thấy bàn","Table missing"));
        const action=form.dataset.command;
        await submitAction(t,{action,expected_revision:t.revision,
          guest_count:data.guest_count?Number(data.guest_count):null,
          guest_name:data.guest_name||"",guest_phone:data.guest_phone||"",
          reservation_id:data.reservation_id||null,
          target_table_id:data.target_table_id||null,note:data.note||""});
      }else if(form.dataset.ezhostForm==="booking"){
        const payload={customer_name:data.customer_name,phone:data.phone,
          party_size:Number(data.party_size),
          start_at:new Date(data.start_at).toISOString(),
          duration_minutes:Number(data.duration_minutes),table_id:data.table_id,
          note:data.note||""};
        if(!Number.isFinite(new Date(data.start_at).getTime()))throw Error(T("Giờ đặt bàn không hợp lệ","Invalid booking time"));
        if(form.dataset.id){
          await api(url("/reservations/"+encodeURIComponent(form.dataset.id)+"/edit"),{
            method:"POST",body:JSON.stringify(payload)});
        }else{
          await api(url("/reservations"),{method:"POST",body:JSON.stringify({
            ...payload,request_id:uid(),branch_id:activeBranch()})});
        }
        bookings=(await api(url("/reservations"))).filter(r=>r.branch_id===activeBranch());
        closeModal?.();paint();toast(T("Đã lưu lịch đặt bàn","Reservation saved"));
      }
    };
    work().catch(e=>toast(e.message,true)).finally(()=>{
      saving=false;
      if(button?.isConnected){button.disabled=false;
        button.textContent=form.dataset.command==="seat"?
          T("✓ Xác nhận nhận khách","✓ Confirm seating"):
          T("Lưu thay đổi","Save changes")}
    });
  },true);
  document.addEventListener("pointerdown",event=>{
    if(event.target.closest("#ezhost-workspace [data-ezhost-placement]"))
      dragStart(event);
  },true);
  return {render,mount,invalidate,load,branch:activeBranch};
};
})();
