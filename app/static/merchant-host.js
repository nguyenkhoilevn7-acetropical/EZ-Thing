/* EZ Thing Host Control: live tenant/branch table service and reservations.
   Admin's interactive preview uses the existing zero-write API sandbox. */
(() => {
"use strict";
window.EZHostWorkstation = function init({api,E,toast,getState,modal,closeModal,previewOnly}) {
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
      zone="all",editing=false,loading=false,ready=false,serial=0;
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
      '</div><p class="ezhost-room-hint">'+T(
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
      board=newBoard;bookings=newBookings.filter(r=>
        !assigned()||r.branch_id===assigned()||!r.branch_id);
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
  function actionDialog(action,t){
    const label={seat:"Nhận khách",release:"Trả bàn",cleaning:"Chờ dọn",
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
      (["seat","update"].includes(action)?
        '<label>'+T("Số khách","Guests")+'<input name="guest_count" type="number" min="1" max="60" value="'+
        esc(t.guest_count||1)+'" required></label>':"")+
      '<label>'+T("Ghi chú","Notes")+'<textarea name="note" maxlength="240" rows="2">'+
        esc(t.note||"")+'</textarea></label>'+
      '<footer><button type="button" data-ezhost-action="dismiss">'+T("Quay lại","Back")+
      '</button><button type="submit" class="ezhost-room-primary">'+T(label,action)+'</button></footer></form>');
  }
  async function submitAction(t,body){
    const result=await api(url("/host/tables/"+encodeURIComponent(t.id)+
      "/action?branch_id="+encodeURIComponent(activeBranch())),{
      method:"POST",body:JSON.stringify(body)
    });
    board=result;paint();closeModal?.();toast(T("Đã cập nhật bàn","Table updated"));
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
    bookings=await api(url("/reservations"));
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
      "[data-ezhost-filter],[data-ezhost-zone],[data-ezhost-booking]");
    if(!btn||!document.getElementById("ezhost-workspace")&&
      !btn.closest("[data-ezhost-form]"))return;
    event.preventDefault();event.stopImmediatePropagation();
    const job=async()=>{
      if(btn.dataset.ezhostTab){view=btn.dataset.ezhostTab;paint();return}
      if(btn.dataset.ezhostZone){zone=btn.dataset.ezhostZone;paint();return}
      if(btn.dataset.ezhostFilter){filter=btn.dataset.ezhostFilter;paint();return}
      if(btn.dataset.ezhostBooking){
        const r=bookings.find(x=>x.id===btn.dataset.value);
        if(!r)return;
        if(btn.dataset.ezhostBooking==="edit")bookingDialog(r);
        else await bookingAction(r.id,btn.dataset.ezhostBooking);
        return;
      }
      const action=btn.dataset.ezhostAction;
      if(action==="dismiss"){closeModal?.();return}
      if(action==="reload"){await load();return}
      if(action==="book"){bookingDialog(null);return}
      if(action==="new-zone"){addZone();return}
      if(action==="save-floor"){await saveFloor();return}
      if(action==="add-physical-table"){
        toast(T("Tạo bàn vật lý trong Admin → Sơ đồ bàn; màn hình lễ tân dùng chức năng Thêm bàn để ghép bàn phục vụ.",
          "Create physical tables in Admin → Floorplan. Hosts use Add table to join occupied tables."));return;
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
    if(event.target.matches("[data-ezhost-branch]")){
      branchId=event.target.value;ready=false;zone="all";filter="all";load().catch(e=>toast(e.message,true));
    }
  },true);
  document.addEventListener("submit",event=>{
    const form=event.target.closest("[data-ezhost-form]");
    if(!form)return;
    event.preventDefault();event.stopImmediatePropagation();
    const data=Object.fromEntries(new FormData(form));
    const button=form.querySelector("[type=submit]");
    if(button)button.disabled=true;
    const work=async()=>{
      if(form.dataset.ezhostForm==="action"){
        const t=at().find(x=>x.id===form.dataset.id);
        if(!t)throw Error(T("Không tìm thấy bàn","Table missing"));
        const action=form.dataset.command;
        await submitAction(t,{action,expected_revision:t.revision,
          guest_count:data.guest_count?Number(data.guest_count):null,
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
        bookings=await api(url("/reservations"));
        closeModal?.();paint();toast(T("Đã lưu lịch đặt bàn","Reservation saved"));
      }
    };
    work().catch(e=>toast(e.message,true)).finally(()=>{
      if(button?.isConnected)button.disabled=false;
    });
  },true);
  document.addEventListener("pointerdown",event=>{
    if(event.target.closest("#ezhost-workspace [data-ezhost-placement]"))
      dragStart(event);
  },true);
  return {render,mount,invalidate,load};
};
})();
