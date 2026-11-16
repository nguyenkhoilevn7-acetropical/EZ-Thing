/* Merchant device setup. No device credentials in localStorage or logs. */
(() => {
"use strict";
function init({api,E,toast,getState}) {
 let devices=[],jobs=[],secret=null,loading=false,container=null,serial=0;
 const getBid=()=>getState().business?.id;
 const rootUrl=()=>"/businesses/"+encodeURIComponent(getBid())+"/printers";
 const label={
   connector_lan:"LAN / Wi-Fi (ESC/POS)",
   connector_usb:"USB (ESC/POS)",
   cloudprnt:"CloudPRNT (Star)",
   all:"Tất cả phiếu bếp",bar:"Pha chế",hot:"Bếp nóng",
   cold:"Bếp lạnh",expo:"Ra món",receipt:"Thu ngân",
   queued:"Chờ máy in",offered:"Đã gửi · chờ xác nhận",
   printed:"Đã xác nhận",failed:"Có lỗi",
 };
 const fmt=t=>t?new Date(t).toLocaleString(window.EZI18N?.locale()||"vi-VN"):"Chưa kết nối";
 const stationOptions=current=>["all","bar","hot","cold","expo","receipt"].map(x=>
   '<option value="'+x+'" '+(current===x?"selected":"")+'>'+E(label[x])+'</option>').join("");
 function render() {
  const role=getState().business?.role;
  return '<section class="surface pad ez-print" id="ez-print"><div class="panel-title"><div>'+
    '<h3>🖨 Thiết bị &amp; máy in</h3><p class="subtle">LAN/Wi-Fi · USB · CloudPRNT. Phân phiếu bếp, pha chế và thu ngân riêng từng chi nhánh.</p></div>'+
    '<span class="pill blue">EZ PRINT</span></div>'+
    '<div id="ez-print-body">'+(role==="staff"
      ?'<p class="subtle">Chỉ chủ doanh nghiệp hoặc quản lý được phép cấu hình máy in.</p>'
      :'<p class="subtle">Đang tải cấu hình máy in...</p>')+'</div></section>';
 }
 function branchOptions() {
  return (getState().cache.branches||[]).map(b=>
   '<option value="'+E(b.id)+'">'+E(b.name)+'</option>').join("");
 }
 function markup() {
  const branches=getState().cache.branches||[];
  const disabled=branches.length===0?'disabled':'';
  const tokenPanel=secret?
   '<aside class="print-secret"><strong>🔑 Khóa kết nối (chỉ hiển thị một lần)</strong>'+
   '<p>Hãy lưu trong máy chạy Print Connector hoặc nhập vào trang cấu hình CloudPRNT. Không chia sẻ khóa này công khai.</p>'+
   '<code>'+E(secret.device_token_once)+'</code>'+
   '<div class="print-setup"><div>Device ID: <code>'+E(secret.id||secret.device_id)+'</code></div>'+
   ((secret.cloudprnt_path||devices.find(x=>x.id===(secret.id||secret.device_id))?.protocol==='cloudprnt')?
    '<div>CloudPRNT server URL: <code>'+E(location.origin+(secret.cloudprnt_path||'/api/print/cloudprnt/'+(secret.id||secret.device_id)))+'</code></div>':
    '<div>Local connector endpoint: <code>'+E(location.origin+(secret.connector_path||'/api/print/connector/'+(secret.id||secret.device_id)))+'</code></div>')+
   '</div><button class="btn sm secondary" data-print="hide-secret">Đã lưu, ẩn khóa</button></aside>':"";
  const devs=devices.length?devices.map(d=>{
    const seen=d.last_seen_at?Math.round((Date.now()-new Date(d.last_seen_at).getTime())/1000):null;
    const online=seen!==null&&seen>=0&&seen<90;
    return '<form class="print-device" data-print-update="'+E(d.id)+'">'+
      '<div class="print-device-head"><strong>'+E(d.name)+'</strong><span class="pill '+(online?"green":"")+'">'+
      (online?"● Đã kết nối":"○ Chưa có kết nối gần đây")+'</span></div>'+
      '<small>'+E(label[d.protocol]||d.protocol)+' · '+E(branches.find(x=>x.id===d.branch_id)?.name||"Chi nhánh")+" · "+
       E(fmt(d.last_seen_at))+'</small>'+
      '<div class="print-fields"><label>Tên máy<input name="name" maxlength="100" required minlength="2" value="'+E(d.name)+'"></label>'+
      '<label>In khu vực<select name="station">'+stationOptions(d.station)+'</select></label></div>'+
      '<div class="print-flags"><label><input type="checkbox" name="enabled" '+(d.enabled?"checked":"")+'> Bật thiết bị</label>'+
      '<label><input type="checkbox" name="auto_print" '+(d.auto_print?"checked":"")+'> In tự động</label></div>'+
      '<div class="print-actions"><button type="submit" class="btn sm secondary">Lưu cấu hình</button>'+
      '<button type="button" class="btn sm secondary" data-print="test" data-id="'+E(d.id)+'">In thử</button>'+
      '<button type="button" class="btn sm ghost" data-print="rotate" data-id="'+E(d.id)+'">Đổi khóa</button></div></form>';
   }).join(""):'<p class="subtle">Chưa có máy in. Có thể tạo thiết bị mẫu ngay bây giờ; hệ thống chỉ in khi máy thật kết nối.</p>';
  const entries=jobs.length?
    '<div class="print-jobs">'+jobs.slice(0,25).map(j=>
      '<div class="print-job"><div><strong>'+E(j.title)+'</strong><small>'+
      E(devices.find(x=>x.id===j.device_id)?.name||"Máy in")+
      ' · '+E(fmt(j.created_at))+' · '+E(label[j.status]||j.status)+
      (j.last_error?' · '+E(j.last_error):"")+'</small></div>'+
      (["failed","offered"].includes(j.status)?
       '<button type="button" class="btn sm secondary" data-print="retry" data-id="'+E(j.id)+'">In lại thủ công</button>':"")+
      '</div>').join("")+'</div>':
    '<p class="subtle">Chưa có lệnh in nào.</p>';
  return tokenPanel+'<div class="print-split"><div><h4>Thêm máy in</h4>'+
    '<form id="ez-print-create" class="print-add">'+
    '<label>Tên thiết bị<input name="name" required minlength="2" maxlength="100" placeholder="Ví dụ: Quầy pha chế"></label>'+
    '<label>Chi nhánh<select name="branch_id" required>'+branchOptions()+'</select></label>'+
    '<label>Kết nối<select name="protocol"><option value="connector_lan">LAN / Wi-Fi (ESC/POS)</option>'+
    '<option value="connector_usb">USB (ESC/POS)</option><option value="cloudprnt">Star CloudPRNT</option></select></label>'+
    '<label>Khu vực<select name="station">'+stationOptions("bar")+'</select></label>'+
    '<label class="print-check"><input type="checkbox" name="auto_print" checked> Tự động in khi gửi bếp / xác nhận thanh toán</label>'+
    '<button class="btn" type="submit" '+disabled+'>Thêm máy in</button></form>'+
    '<p class="subtle">LAN/USB cần một máy tính hoặc mini-PC chạy EZ Print Connector. CloudPRNT không cần máy trung gian.</p></div>'+
    '<div><div class="print-heading"><h4>Máy in đã đăng ký ('+devices.length+')</h4>'+
    '<button class="btn sm ghost" data-print="refresh">↻ Tải lại</button></div>'+devs+'</div></div>'+
    '<div class="print-heading"><h4>Hàng đợi &amp; lịch sử in</h4><small>100 lệnh gần nhất · Không tự in lại nếu kết quả chưa rõ</small></div>'+
    entries+
    '<p class="subtle">Trạng thái “Đã xác nhận” do connector/máy báo về; không thay thế kiểm tra bản in thực tế. Phiếu thu ngân không phải hóa đơn điện tử thuế.</p>';
 }
 function draw() {
   const slot=container?.querySelector("#ez-print-body");
   if(slot)slot.innerHTML=markup();
 }
 async function refresh() {
   if(loading||!getBid())return;
   loading=true;
   const sequence=++serial,bid=getBid();
   try {
     const [a,b]=await Promise.all([api(rootUrl()),api(rootUrl()+"/jobs")]);
     if(sequence!==serial||bid!==getBid())return;
     devices=a.devices||[];jobs=b.jobs||[];draw();
   } catch(e) {toast(e.message,true)}
   finally {loading=false}
 }
 function asObject(form) {
   const f=new FormData(form),obj=Object.fromEntries(f);
   obj.enabled=!!form.querySelector('[name="enabled"]:checked');
   obj.auto_print=!!form.querySelector('[name="auto_print"]:checked');
   return obj;
 }
 async function submit(event) {
   const f=event.target;
   if(!f.matches("#ez-print-create,[data-print-update]"))return;
   event.preventDefault();
   if(loading)return;
   const button=f.querySelector('[type=submit]');
   if(button)button.disabled=true;
   try {
     const updateId=f.dataset.printUpdate;
     const data=asObject(f);
     const path=updateId?rootUrl()+"/"+encodeURIComponent(updateId):rootUrl();
     const r=await api(path,{method:updateId?"PUT":"POST",body:JSON.stringify(data)});
     if(!updateId)secret=r;
     toast(updateId?"Đã lưu cấu hình máy in":"Đã đăng ký thiết bị. Hãy lưu khóa kết nối.");
     await refresh();
   }catch(e){toast(e.message,true)}
   finally{if(button)button.disabled=false}
 }
 async function click(event) {
   const btn=event.target.closest("button[data-print]");
   if(!btn||!container?.contains(btn))return;
   const action=btn.dataset.print,id=btn.dataset.id;
   if(action==="hide-secret"){secret=null;draw();return}
   if(action==="refresh"){await refresh();return}
   if(action==="retry"&&!confirm("Chỉ in lại khi đã kiểm tra máy chưa in phiếu này. Có thể phát sinh bản sao. Tiếp tục?"))return;
   if(action==="rotate"&&!confirm("Khóa hiện tại sẽ ngừng hoạt động ngay. Anh cần cấu hình lại máy in. Tiếp tục?"))return;
   btn.disabled=true;
   try {
     if(action==="test")await api(rootUrl()+"/"+encodeURIComponent(id)+"/test",{method:"POST",body:"{}"});
     if(action==="rotate")secret=await api(rootUrl()+"/"+encodeURIComponent(id)+"/rotate-key",{method:"POST",body:"{}"});
     if(action==="retry")await api(rootUrl()+"/jobs/"+encodeURIComponent(id)+"/retry",{method:"POST",body:"{}"});
     toast(action==="test"?"Đã xếp hàng in thử":action==="rotate"?"Đã tạo khóa mới":"Đã xếp hàng in lại");
     await refresh();
   }catch(e){toast(e.message,true)}
   finally{btn.disabled=false}
 }
 async function mount() {
   const node=document.getElementById("ez-print");
   if(!node||getState().business?.role==="staff")return;
   container=node;container.addEventListener("submit",submit);
   container.addEventListener("click",click);
   await refresh();
 }
 return {render,mount};
}
window.EZPrintUI=init;
})();
