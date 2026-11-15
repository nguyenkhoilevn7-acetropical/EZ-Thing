/* EZ Thing KDS — foreground-only station queue. Browser audio is opt-in. */
(() => {
"use strict";
const stations={all:"Tất cả",bar:"Pha chế",hot:"Bếp nóng",cold:"Bếp lạnh",expo:"Ra món"};
const states={pending:"Mới vào",preparing:"Đang làm",held:"Tạm giữ",ready:"Sẵn sàng",served:"Đã giao"};
const next={pending:["preparing","held"],preparing:["ready","held"],held:["preparing"],ready:["served"],served:[]};
const labels={preparing:"Nhận làm",ready:"Xong món",held:"Tạm giữ",served:"Đã giao"};
function init({api,getState,E,V,toast,modal,closeModal,refresh}){
 let data=null,station="all",branch="all",view="order",showDone=false;
 let active=false,poll=null,generation=0,sound=false,first=true,busy=false,known=new Set();
 const st=()=>getState(),bid=()=>st().business?.id;
 const url=path=>"/businesses/"+encodeURIComponent(bid())+"/kds"+path;
 const tx=(vn,en)=>window.EZI18N?.language?.()==="en"?en:vn;
 const esc=x=>E(x??"");
 const manager=()=>["owner","manager"].includes(st().business?.role);
 const since=t=>Math.max(0,Math.floor((Date.now()-new Date(t.created_at).getTime())/60000));
 const age=t=>since(t)>=7?"late":since(t)>=3?"warning":"normal";
 const stage=x=>stations[x]||x;
 function beep(){
  if(!sound)return;
  try{const AC=window.AudioContext||window.webkitAudioContext;if(!AC)return;
   const ctx=new AC(),osc=ctx.createOscillator(),gain=ctx.createGain();
   gain.gain.value=.06;osc.frequency.value=720;osc.connect(gain).connect(ctx.destination);
   osc.start();osc.stop(ctx.currentTime+.17);osc.onended=()=>ctx.close();
  }catch(_){}
 }
 function actions(item,t){
  let out="";
  for(const status of next[item.status]||[]){
   out+='<button class="kds-act kds-act-'+status+'" data-kds="status" data-ticket="'+esc(t.id)+'" data-line="'+esc(item.id)+'" data-rev="'+t.revision+'" data-status="'+status+'">'+tx(labels[status],status)+'</button>';
  }
  if(manager()&&["served","ready"].includes(item.status)){
    out+='<button class="kds-act kds-act-recall" data-kds="recall" data-ticket="'+esc(t.id)+'" data-line="'+esc(item.id)+'" data-rev="'+t.revision+'" data-status="'+(item.status==="served"?"ready":"preparing")+'">'+tx("Hoàn tác","Recall")+'</button>';
  }
  return out;
 }
 function dish(item,t){
   const mod=(item.modifiers||[]).map(x=>'<span class="kds-mod">'+esc((x.group_name?x.group_name+" · ":"")+x.name)+'</span>').join("");
   return '<article class="kds-dish kds-dish-'+esc(item.status)+'"><div class="kds-dish-head"><strong><em>'+Number(item.quantity)+'×</em> '+esc(item.name)+'</strong><small>'+esc(stage(item.station))+'</small></div>'+
     (mod?'<div class="kds-mods">'+mod+'</div>':"")+
     '<div class="kds-dish-foot"><span class="kds-chip kds-chip-'+esc(item.status)+'">'+esc(states[item.status]||item.status)+'</span><div class="kds-dish-actions">'+actions(item,t)+'</div></div></article>';
 }
 function filterRows(){
  return (data?.tickets||[]).map(t=>({...t,lines:t.lines.filter(x=>(station==="all"||x.station===station||(station==="expo"&&x.status==="ready"))&&(showDone||x.status!=="served"))})).filter(t=>t.lines.length);
 }
 function markup(){
  const rows=filterRows();
  if(!rows.length)return '<div class="kds-empty">☕ <strong>'+tx("Chưa có món ở trạm này","No dishes in this station")+'</strong><p>'+tx("Hãy gửi phiếu bếp từ đơn hàng để bắt đầu.","Fire an order to begin.")+'</p></div>';
  const cards=[];
  for(const t of rows){
    const header='<header class="kds-ticket-head"><div><strong>#'+esc(t.order_id.slice(0,8).toUpperCase())+'</strong><small>'+esc(st().cache?.tables?.find(x=>x.id===t.table_id)?.label||tx("Mang đi","Takeaway"))+'</small></div><span class="kds-timer '+age(t)+'">'+since(t)+' '+tx("phút","min")+'</span></header>';
    const note=t.note?'<div class="kds-note">⚑ '+esc(t.note)+'</div>':"";
    if(view==="item"){
      for(const item of t.lines)cards.push('<section class="kds-ticket '+age(t)+'">'+header+note+dish(item,t)+'</section>');
    }else{
      cards.push('<section class="kds-ticket '+age(t)+'">'+header+note+'<div class="kds-ticket-dishes">'+t.lines.map(x=>dish(x,t)).join("")+'</div><footer class="kds-ticket-foot">'+t.lines.length+' '+tx("món","items")+'<button class="kds-print" data-kds="print" data-ticket="'+esc(t.id)+'">'+tx("In phiếu","Print")+'</button></footer></section>');
    }
  }
  return '<div class="kds-grid">'+cards.join("")+'</div>';
 }
 function fireControl(){
   const orders=(st().cache?.orders||[]).filter(x=>x.status!=="cancelled"&&(branch==="all"||x.branch_id===branch)&&!(data?.tickets||[]).some(t=>t.order_id===x.id));
   if(!orders.length)return '<span class="subtle">'+tx("Không có đơn chưa gửi bếp","No unfired orders")+'</span>';
   return '<form data-kds-form="fire" class="kds-fire-form"><select name="order_id" required aria-label="Đơn hàng">'+orders.map(x=>'<option value="'+esc(x.id)+'">#'+esc(x.id.slice(0,8).toUpperCase())+' · '+V(x.total_vnd)+'</option>').join("")+'</select><button class="btn sm" type="submit">'+tx("Gửi bếp","Fire")+'</button></form>';
 }
 function routeControl(){
   if(!manager())return "";
   const products=st().cache?.products||[];
   const options=products.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.name)+(x.active?"":" · HẾT MÓN")+'</option>').join("");
   const names=Object.keys(stations).filter(x=>x!=="all").map(x=>'<option value="'+x+'">'+esc(stations[x])+'</option>').join("");
   return '<details class="kds-config"><summary>⚙ '+tx("Phân trạm và hết món","Stations & sold-out")+'</summary><div class="kds-config-grid"><form data-kds-form="route"><strong>'+tx("Chỉ định trạm chế biến","Assign prep station")+'</strong><select name="product_id">'+options+'</select><select name="station">'+names+'</select><button class="btn sm" type="submit">'+tx("Lưu trạm","Save")+'</button></form>'+
     '<form data-kds-form="availability"><strong>'+tx("Tạm ngừng / mở bán món","Menu availability")+'</strong><select name="product_id">'+options+'</select><select name="available"><option value="false">'+tx("Tạm hết món","Sold out")+'</option><option value="true">'+tx("Mở bán lại","Available")+'</option></select><input name="reason" required minlength="4" maxlength="180" placeholder="'+tx("Lý do thay đổi","Reason")+'"><button class="btn sm secondary" type="submit">'+tx("Cập nhật","Update")+'</button></form>'+
     '<p class="subtle">'+tx("Món chưa phân trạm được gợi ý từ tên/danh mục, còn lại vào Ra món. Thay đổi trạm chỉ áp dụng cho phiếu mới.","Unassigned products use category suggestions, otherwise Expo. Changes apply to future tickets.")+'</p></div></details>';
 }
 function render(){
  return '<div class="kds" id="ez-kds"><header class="kds-head"><div><small>KDS · EZ THING</small><h2>'+tx("Bếp & pha chế","Kitchen & Bar")+'</h2><p>'+tx("Xem theo trạm • Xử lý từng món • Ra món chính xác","Prep stations • Item status • Expediter")+'</p></div><div class="kds-head-actions"><button class="btn sm secondary" data-kds="sound" aria-pressed="'+sound+'">'+tx("🔕 Bật âm báo","🔕 Enable sound")+'</button><button class="btn sm secondary" data-kds="fullscreen">'+tx("⛶ Toàn màn hình","⛶ Fullscreen")+'</button></div></header>'+
   '<div class="kds-toolbar"><label>'+tx("Chi nhánh","Branch")+'<select data-kds-filter="branch"><option value="all">'+tx("Tất cả","All")+'</option>'+(st().cache?.branches||[]).map(b=>'<option value="'+esc(b.id)+'" '+(branch===b.id?"selected":"")+'>'+esc(b.name)+'</option>').join("")+'</select></label>'+
   '<label>'+tx("Hiển thị","View")+'<select data-kds-filter="view"><option value="order">'+tx("Theo đơn","By ticket")+'</option><option value="item">'+tx("Theo món","By item")+'</option></select></label><label class="kds-check"><input type="checkbox" data-kds-filter="done" '+(showDone?"checked":"")+'>'+tx("Món đã giao","Served items")+'</label></div>'+
   '<div class="kds-stations" role="group" aria-label="Trạm xử lý">'+Object.entries(stations).map(([id,name])=>'<button class="kds-station '+(station===id?"active":"")+'" data-kds="station" data-value="'+id+'">'+esc(name)+' <span data-count="'+id+'">0</span></button>').join("")+'</div>'+
   '<div class="kds-metrics"><div><strong id="kds-ticket-count">0</strong><span>'+tx("Phiếu đang xử lý","Active tickets")+'</span></div><div><strong id="kds-item-count">0</strong><span>'+tx("Món chưa giao","Unserved units")+'</span></div><div><strong id="kds-late-count">0</strong><span>'+tx("Phiếu trên 7 phút","Late tickets")+'</span></div><small id="kds-live" role="status">'+tx("Đang kết nối...","Connecting...")+'</small></div>'+
   '<div class="kds-fire"><div><strong>'+tx("Gửi phiếu xuống bếp","Send an order to kitchen")+'</strong><p>'+tx("Giá bán và kho đã ghi ở POS không thay đổi khi gửi bếp.","Firing a ticket does not alter POS pricing or stock.")+'</p></div><div id="kds-fire-slot">'+fireControl()+'</div></div>'+
   routeControl()+'<div id="kds-content"><div class="kds-empty">'+tx("Đang tải phiếu bếp...","Loading tickets...")+'</div></div><p class="kds-disclaimer">'+tx("Đồng bộ 5 giây khi đang mở màn hình. Âm báo cần bật thủ công; in qua trình duyệt, chưa hỗ trợ máy in phần cứng hoặc push khi tắt màn hình.","Foreground sync every 5s; opt-in sound and browser print only. No device printer or background push.")+'</p></div>';
 }
 function paint(){
  const root=document.getElementById("ez-kds");if(!root||!data)return;
  const tickets=data.tickets||[];
  const activeTickets=tickets.filter(t=>t.lines.some(x=>x.status!=="served"));
  const items=tickets.flatMap(x=>x.lines).filter(x=>x.status!=="served");
  root.querySelector("#kds-ticket-count").textContent=activeTickets.length;
  root.querySelector("#kds-item-count").textContent=items.reduce((s,x)=>s+Number(x.quantity),0);
  root.querySelector("#kds-late-count").textContent=activeTickets.filter(x=>age(x)==="late").length;
  for(const key of Object.keys(stations)){
    const count=items.filter(x=>key==="all"||x.station===key||(key==="expo"&&x.status==="ready")).reduce((s,x)=>s+Number(x.quantity),0);
    const badge=root.querySelector('[data-count="'+key+'"]');if(badge)badge.textContent=count;
  }
  root.querySelector("#kds-content").innerHTML=markup();
  root.querySelector("#kds-fire-slot").innerHTML=fireControl();
  root.querySelector("#kds-live").textContent="● "+tx("Đã đồng bộ","Synced");
 }
 async function load(force=false){
   if(!active||!bid())return;
   const id=bid(),serial=generation,qs=branch==="all"?"":"?branch_id="+encodeURIComponent(branch);
   const incoming=await api(url("/queue")+qs);
   if(serial!==generation||bid()!==id||st().tab!=="kitchen")return;
   const currentIds=new Set(incoming.tickets.map(x=>x.id));
   if(!first&&[...currentIds].some(x=>!known.has(x)))beep();
   known=currentIds;first=false;
   const changed=JSON.stringify(data?.tickets)!==JSON.stringify(incoming.tickets);
   data=incoming;
   if(force||changed)paint();
   else{
     document.querySelectorAll("#ez-kds .kds-ticket .kds-timer").forEach(el=>{
       const id=el.closest(".kds-ticket")?.querySelector(".kds-ticket-head strong")?.textContent;
       const ticket=data.tickets.find(t=>("#"+t.order_id.slice(0,8).toUpperCase())===id);
       if(ticket){el.textContent=since(ticket)+" "+tx("phút","min");el.className="kds-timer "+age(ticket);}
     });
   }
 }
 async function mount(){
  if(st().business?.industry!=="fnb")return;
  active=true;generation++;data=null;first=true;known=new Set();
  if(poll)clearInterval(poll);
  try{await load(true)}catch(err){toast(err.message,true)}
  poll=setInterval(()=>{
    if(!active||document.hidden||st().tab!=="kitchen"||busy)return;
    load().catch(()=>{const live=document.getElementById("kds-live");if(live)live.textContent=tx("Mất kết nối","Offline")});
  },5000);
 }
 function invalidate(){active=false;generation++;if(poll)clearInterval(poll);poll=null;data=null;first=true;known=new Set()}
 async function submit(form){
  if(busy)return;busy=true;
  const button=form.querySelector('[type=submit]');if(button)button.disabled=true;
  try{
    const input=Object.fromEntries(new FormData(form));
    if(form.dataset.kdsForm==="fire"){
      await api(url("/fire"),{method:"POST",body:JSON.stringify({order_id:input.order_id})});
      toast(tx("Đã gửi phiếu tới bếp","Ticket sent"));
    }else if(form.dataset.kdsForm==="route"){
      await api(url("/routes"),{method:"PUT",body:JSON.stringify(input)});
      toast(tx("Đã lưu trạm cho phiếu kế tiếp","Route saved"));
    }else if(form.dataset.kdsForm==="availability"){
      await api(url("/products/"+encodeURIComponent(input.product_id)+"/availability"),{
        method:"POST",body:JSON.stringify({available:input.available==="true",reason:input.reason})});
      await refresh();
      toast(tx("Đã cập nhật tình trạng món","Availability updated"));
    }else if(form.dataset.kdsForm==="recall"){
      await api(url("/tickets/"+encodeURIComponent(input.ticket)+"/lines/"+encodeURIComponent(input.line)+"/status"),{
        method:"POST",body:JSON.stringify({status:input.status,expected_revision:Number(input.rev),reason:input.reason})});
      closeModal();
    }
    if(st().tab==="kitchen")await load(true);
  }catch(err){toast(err.message,true)}
  finally{busy=false;if(button)button.disabled=false}
 }
 async function status(button){
  if(busy)return;busy=true;button.disabled=true;
  try{
    await api(url("/tickets/"+encodeURIComponent(button.dataset.ticket)+"/lines/"+encodeURIComponent(button.dataset.line)+"/status"),{
      method:"POST",body:JSON.stringify({status:button.dataset.status,expected_revision:Number(button.dataset.rev)})});
    await load(true);
  }catch(err){toast(err.message,true);await load(true).catch(()=>{})}
  finally{busy=false;button.disabled=false}
 }
 document.addEventListener("submit",e=>{
   const form=e.target.closest("[data-kds-form]");if(!form)return;
   e.preventDefault();e.stopImmediatePropagation();submit(form);
 },true);
 document.addEventListener("click",e=>{
  const button=e.target.closest("[data-kds]");if(!button)return;
  e.preventDefault();e.stopImmediatePropagation();
  const action=button.dataset.kds;
  if(action==="station"){
    station=button.dataset.value;
    document.querySelectorAll(".kds-station").forEach(b=>b.classList.toggle("active",b.dataset.value===station));
    paint();
  }else if(action==="status")status(button);
  else if(action==="recall"){
    modal(tx("Hoàn tác trạng thái món","Recall item"),
      '<form data-kds-form="recall"><p>'+tx("Quản lý phải ghi lý do hoàn tác.","Manager reason required.")+'</p><input type="hidden" name="ticket" value="'+esc(button.dataset.ticket)+'"><input type="hidden" name="line" value="'+esc(button.dataset.line)+'"><input type="hidden" name="status" value="'+esc(button.dataset.status)+'"><input type="hidden" name="rev" value="'+Number(button.dataset.rev)+'"><div class="formfield"><label>'+tx("Lý do","Reason")+'</label><textarea name="reason" required minlength="4" maxlength="160"></textarea></div><div class="modal-footer"><button type="button" class="btn secondary" data-action="close-modal">'+tx("Đóng","Close")+'</button><button class="btn" type="submit">'+tx("Xác nhận","Confirm")+'</button></div></form>');
  }else if(action==="sound"){
    sound=!sound;button.setAttribute("aria-pressed",String(sound));
    button.textContent=sound?tx("🔔 Đã bật","🔔 Sound on"):tx("🔕 Bật âm báo","🔕 Enable sound");
    if(sound)beep();
  }else if(action==="fullscreen"){
    const node=document.getElementById("ez-kds");
    if(document.fullscreenElement)document.exitFullscreen?.().catch(()=>{});
    else node?.requestFullscreen?.().catch(()=>toast(tx("Không thể toàn màn hình","Fullscreen unavailable"),true));
  }else if(action==="print"){
    const ticket=data?.tickets.find(x=>x.id===button.dataset.ticket);if(!ticket)return;
    let node=document.getElementById("kds-print-region");
    if(!node){node=document.createElement("div");node.id="kds-print-region";document.body.append(node)}
    node.innerHTML='<h2>EZ Thing · '+tx("Phiếu bếp","Kitchen ticket")+'</h2><strong>#'+esc(ticket.order_id.slice(0,8))+'</strong><p>'+esc(ticket.note)+'</p>'+ticket.lines.map(x=>'<p>'+Number(x.quantity)+'× '+esc(x.name)+' — '+(x.modifiers||[]).map(m=>esc(m.name)).join(", ")+'</p>').join("");
    window.print();
  }
 },true);
 document.addEventListener("change",e=>{
   const field=e.target.closest("[data-kds-filter]");if(!field||!active)return;
   if(field.dataset.kdsFilter==="branch"){branch=field.value;known=new Set();first=true;load(true).catch(err=>toast(err.message,true))}
   else if(field.dataset.kdsFilter==="view"){view=field.value;paint()}
   else if(field.dataset.kdsFilter==="done"){showDone=field.checked;paint()}
 },true);
 return {render,mount,invalidate};
}
window.EZKDS={init};
})();
