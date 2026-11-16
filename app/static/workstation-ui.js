/* EZ Thing workstation display profiles: restaurant-specific, server-persisted.
 * IMPORTANT: display mode is not an authorization boundary. Session membership
 * is authoritative for every API call. Never trust this client for permissions.
 */
(() => {
  "use strict";
  const MODES={
    manager:["Trung tâm quản lý","Management",null],
    order:["Máy nhận order","Order terminal","pos"],
    kitchen:["Màn hình bếp","Kitchen display","kitchen"],
    bar:["Màn hình pha chế","Bar display","kitchen"],
    cashier:["Máy thu ngân","Cashier terminal","orders"],
    host:["Máy lễ tân","Host terminal","operations"]
  };
  const choose=(vn,en)=>window.EZI18N?.language?.()==="en"?en:vn;
  const blank=()=>({mode:"manager",station:"all",branch_id:null,id:"",name:""});
  function key(){
    try{
      const existing=localStorage.getItem("ez_thing_workstation_key");
      if(existing&&/^[a-f0-9-]{36}$/i.test(existing))return existing;
      const created=crypto.randomUUID();
      localStorage.setItem("ez_thing_workstation_key",created);
      return created;
    }catch{return null}
  }
  window.EZWorkstations={
    create({api,E,toast,getState,modal,closeModal,onChanged}){
      let current=blank(),biz="",drawerOpen=false,temporary=false,pending=false,previewMode=null,sandbox=null;
      const state=getState;
      const owner=()=>["owner","manager"].includes(state().business?.role);
      const active=()=>state().business?.industry==="fnb"&&!state().business?.billing_required;
      const mode=()=>active()?(previewMode||current.mode):"manager";
      const focused=()=>mode()!=="manager"&&(Boolean(previewMode)||!temporary);
      const home=()=>MODES[mode()]?.[2]||"overview";
      const lang=()=>window.EZI18N?.language?.()==="en";
      function applyProfile(row){
        current={...blank(),...(row||{})};
        if(!MODES[current.mode])current.mode="manager";
        state().workstation=previewMode?virtualProfile(previewMode):current;
        if(state().business?.id===biz&&!temporary&&current.mode!=="manager"&&!previewMode)state().tab=home();
        document.body.dataset.ezWorkstation=focused()?mode():"manager";
        document.body.dataset.ezWorkstationActive=focused()?"true":"false";
      }
      async function load(){
        const b=state().business;
        temporary=false;drawerOpen=false;previewMode=null;
        if(!b||b.industry!=="fnb"||b.billing_required){
          biz=b?.id||"";applyProfile(blank());return;
        }
        biz=b.id;const id=key();
        if(!id){applyProfile(blank());return}
        try{
          const row=await api("/businesses/"+encodeURIComponent(biz)+"/workstations/current",{
            method:"PUT",body:JSON.stringify({client_key:id,name:choose("Thiết bị "+id.slice(0,6),"Device "+id.slice(0,6))})
          });
          if(state().business?.id!==biz)return;
          applyProfile(row);
        }catch(error){
          // No persisted override means never silently impose device limits.
          applyProfile(blank());
          toast(choose("Không tải được cấu hình thiết bị","Device mode unavailable")+": "+error.message,true);
        }
      }
      const modeLabel=(id)=>{const x=MODES[id]||MODES.manager;return x[lang()?1:0]};
      const safe=(v)=>E(String(v??""));
      const virtualProfile=(task)=>({
        ...current,mode:task,
        station:task==="bar"?"bar":task==="kitchen"?"kitchen":"all",
        preview_only:true
      });
      const previewOnly=()=>Boolean(previewMode);
      // All demo mutations are ephemeral and bound to this browser-tab session.
      // Never reuse a real tenant idempotency key or call an actual write endpoint.
      const clone=x=>JSON.parse(JSON.stringify(x));
      const fakeId=()=>globalThis.crypto?.randomUUID?.()||
        "virtual-"+Date.now().toString(36)+"-"+Math.random().toString(36).slice(2);
      const prepStation=p=>{
        const name=String((p?.name||"")+" "+(p?.category||"")).toLocaleLowerCase("vi");
        if(/salad|nguội|cold kitchen|gỏi/.test(name))return "cold";
        if(/trà|tea|matcha|nước|coffee|cafe|cà phê|juice|soda|drink|latte|sữa|sinh tố|smoothie/.test(name))return "bar";
        if(/bánh|food|món|cơm|phở|bún|mì|lẩu|thịt|nướng|chiên|soup|pizza|burger/.test(name))return "hot";
        return "expo";
      };
      function ensureSandbox(){
        const bid=state().business?.id;
        if(!sandbox||sandbox.bid!==bid){
          sandbox={bid,orders:clone(state().cache.orders||[]),
            tables:clone(state().cache.tables||[]),tickets:[],
            originalTickets:null,idempotency:new Map(),payments:new Map()};
        }
        return sandbox;
      }
      function demoTickets(){
        const sb=ensureSandbox();
        return [...sb.tickets,...(sb.originalTickets||[])];
      }
      function previewResponse(path,opt={}){
        if(!previewMode)return {handled:false};
        const sb=ensureSandbox(),method=(opt.method||"GET").toUpperCase();
        const tail=String(path).split("?")[0],payload=()=>{
          try{return JSON.parse(opt.body||"{}")}catch{throw new Error("Dữ liệu thử không hợp lệ")}
        };
        if(method==="GET"){
          if(/^\/businesses\/[^/]+\/orders$/.test(tail))return {handled:true,data:clone(sb.orders)};
          if(/^\/businesses\/[^/]+\/tables$/.test(tail))return {handled:true,data:clone(sb.tables)};
          if(/\/kds\/queue$/.test(tail)&&sb.originalTickets!==null){
            const branch=new URLSearchParams(path.split("?")[1]||"").get("branch_id");
            return {handled:true,data:{
              server_time:new Date().toISOString(),stations:{},transport:"sandbox",
              tickets:clone(demoTickets().filter(t=>!branch||t.branch_id===branch)),
              all_day:{},ready_for_expo:0,poll_after_seconds:5
            }};
          }
          return {handled:false};
        }
        if(method==="POST"&&/^\/businesses\/[^/]+\/orders$/.test(tail)){
          const body=payload(),key=String(body.idempotency_key||"");
          if(key&&sb.idempotency.has(key)){
            return {handled:true,data:clone(sb.idempotency.get(key))};
          }
          const products=state().cache.products||[],lineItems=[];
          for(const entry of body.lines||[]){
            const p=products.find(x=>x.id===entry.product_id);
            if(!p)throw Error("Không tìm thấy món trong dữ liệu dùng thử");
            const selections=(p.modifier_groups||[]).flatMap(g=>
              (g.options||[]).filter(o=>(entry.selected_options||[]).includes(o.id))
                .map(o=>({group_name:g.name,name:o.name,price_vnd:Number(o.price_vnd)||0})));
            const unit=(Number(p.price_vnd)||0)+selections.reduce((sum,m)=>sum+m.price_vnd,0);
            const qty=Math.max(1,Math.min(1000,Number(entry.quantity)||1));
            lineItems.push({id:fakeId(),product_id:p.id,name:p.name,
              quantity:qty,unit_price_vnd:unit,total_vnd:unit*qty,modifiers:selections,
              station:prepStation(p)});
          }
          if(!lineItems.length)throw Error("Hãy chọn ít nhất một món");
          const now=new Date().toISOString(),id=fakeId();
          const order={id,branch_id:body.branch_id||null,table_id:body.table_id||null,
            customer_id:body.customer_id||null,status:"open",paid_at:null,
            total_vnd:lineItems.reduce((s,x)=>s+x.total_vnd,0),
            created_at:now,note:String(body.note||""),items:lineItems};
          sb.orders.unshift(order);
          const lines=lineItems.map(x=>({
            id:fakeId(),product_id:x.product_id,name:x.name,quantity:x.quantity,
            station:x.station,modifiers:x.modifiers,status:"pending",
            runner_called_at:null
          }));
          sb.tickets.unshift({id:fakeId(),order_id:id,table_id:order.table_id,
            branch_id:order.branch_id,note:order.note,created_at:now,
            updated_at:now,revision:0,status:"pending",lines});
          const result={...order,kds_dispatch:{status:"sent",ticket_id:sb.tickets[0].id}};
          if(key)sb.idempotency.set(key,clone(result));
          return {handled:true,data:clone(result)};
        }
        const payment=tail.match(/^\/businesses\/[^/]+\/pos-payments\/([^/]+)$/);
        if(method==="POST"&&payment){
          const order=sb.orders.find(o=>o.id===payment[1]),body=payload();
          if(!order)throw Error("Không có đơn hàng này trong dữ liệu dùng thử");
          if(sb.payments.has(order.id))return {handled:true,data:clone(sb.payments.get(order.id))};
          if(order.status!=="open"||!body.confirmed)throw Error("Đơn không còn chờ thanh toán");
          if(Number(body.expected_total_vnd)!==Number(order.total_vnd))
            throw Error("Tổng tiền thử nghiệm đã thay đổi");
          const change=body.method==="cash"?Number(body.cash_received_vnd)-order.total_vnd:0;
          if(!Number.isFinite(change)||change<0)throw Error("Số tiền khách đưa chưa đủ");
          order.status="paid";order.paid_at=new Date().toISOString();
          const result={order:clone(order),payment:{method:body.method,
            amount_vnd:order.total_vnd,cash_received_vnd:body.cash_received_vnd||null,
            change_vnd:change,transfer_reference:body.transfer_reference||""}};
          sb.payments.set(order.id,clone(result));
          return {handled:true,data:clone(result)};
        }
        const progress=tail.match(/\/kds\/tickets\/([^/]+)\/lines\/([^/]+)\/(status|call-runner)$/);
        if(method==="POST"&&progress){
          const ticket=demoTickets().find(x=>x.id===progress[1]);
          const line=ticket?.lines.find(x=>x.id===progress[2]);
          if(!ticket||!line)throw Error("Không có món này trong phiếu thử nghiệm");
          const body=payload();
          if(Number(body.expected_revision)!==ticket.revision)
            throw Error("Phiếu đã cập nhật. Vui lòng thử lại");
          if(progress[3]==="call-runner"){
            if(line.status!=="ready")throw Error("Món chưa sẵn sàng");
            line.runner_called_at=new Date().toISOString();
          }else{
            const allowed={pending:["preparing","held"],preparing:["ready","held"],
              held:["preparing"],ready:["served"],served:[]};
            if(!allowed[line.status]?.includes(body.status))
              throw Error("Chuyển trạng thái không hợp lệ");
            line.status=body.status;
          }
          ticket.revision++;ticket.updated_at=new Date().toISOString();
          return {handled:true,data:clone(ticket)};
        }
        // Deny every other write, including settings, printing, admin and finance.
        throw Error(choose("Đây là bản dùng thử tương tác. Thao tác này không được mô phỏng để tránh sửa dữ liệu thật.",
          "Interactive sandbox: this operation is not simulated to protect real data."));
      }
      function previewRead(path,data){
        if(!previewMode||!/\/kds\/queue(?:\?|$)/.test(path))return data;
        const sb=ensureSandbox();
        if(sb.originalTickets===null)sb.originalTickets=clone(data?.tickets||[]);
        return {...data,tickets:clone(demoTickets())};
      }
      function togglePreviewTable(tableId){
        if(!previewMode||previewMode!=="host")return false;
        const sb=ensureSandbox(),table=sb.tables.find(x=>x.id===tableId);
        if(!table)return false;
        table.occupied=!table.occupied;
        state().cache.tables=clone(sb.tables);
        return true;
      }
      function previewNav(){
        if(!previewMode||!owner())return "";
        return '<div class="ezws-preview-bar" role="toolbar" aria-label="Xem thử tác vụ">'+
          '<span class="ezws-preview-label">👁 '+safe(choose("CHỈ XEM · KHÔNG GHI DỮ LIỆU","READ-ONLY PREVIEW"))+'</span>'+
          '<div class="ezws-preview-tabs">'+Object.keys(MODES).filter(id=>id!=="manager").map(id=>
            '<button type="button" data-ezws="preview" data-value="'+id+'" class="'+
            (previewMode===id?"active":"")+'" aria-pressed="'+(previewMode===id)+'">'+
            safe(modeLabel(id))+'</button>').join("")+'</div>'+
          '<button type="button" class="ezws-preview-fullscreen" data-ezws="fullscreen" title="'+
          safe(choose("Toàn màn hình","Fullscreen"))+'">⛶</button>'+
          '<button type="button" class="ezws-preview-exit" data-ezws="exit-preview">'+
          safe(choose("Thoát xem thử","Back to Admin"))+'</button></div>';
      }
      function openPreviewPicker(){
        if(!owner()||!active())return;
        const icons={order:"🧾",kitchen:"🍳",bar:"🥤",cashier:"💳",host:"🪑"};
        const hints={order:choose("Nhận món, tạo đơn","Take orders"),
          kitchen:choose("Xử lý món ăn","Prepare food"),
          bar:choose("Pha chế đồ uống","Prepare drinks"),
          cashier:choose("Thu tiền và in phiếu","Collect payments"),
          host:choose("Bàn, đón khách","Host & seating")};
        modal(choose("Xem thử màn hình theo tác vụ","Preview employee workstations"),
          '<div class="ezws-preview-picker"><p>'+
          choose("Xem trực tiếp từng màn hình của hệ thống. Chế độ này chỉ đọc, không tạo đơn hoặc sửa dữ liệu.",
            "See each real workspace. Preview is read-only and cannot alter data.")+
          '</p><div class="ezws-preview-choices">'+
          Object.keys(MODES).filter(id=>id!=="manager").map(id=>
          '<button type="button" class="ezws-preview-choice" data-ezws="preview" data-value="'+id+'">'+
          '<span aria-hidden="true">'+icons[id]+'</span><strong>'+safe(modeLabel(id))+
          '</strong><small>'+safe(hints[id])+'</small></button>').join("")+
          '</div></div>');
      }
      function preview(task){
        if(!owner()||!active()||!MODES[task]||task==="manager")return;
        closeModal?.();
        previewMode=task;temporary=false;drawerOpen=false;
        state().workstation=virtualProfile(task);
        onChanged(home());
        requestAnimationFrame(()=>{
          syncPreviewLayout();
          document.scrollingElement?.scrollTo({top:0,behavior:"instant"});
          for(const node of document.querySelectorAll(".app>.main,.app .content"))node.scrollTop=0;
          window.scrollTo(0,0);
        });
      }
      function exitPreview(){
        if(!previewMode)return;
        previewMode=null;temporary=true;drawerOpen=false;
        state().workstation=current;
        onChanged("overview");
        requestAnimationFrame(()=>{
          syncPreviewLayout();
          document.scrollingElement?.scrollTo({top:0,behavior:"instant"});
          window.scrollTo(0,0);
        });
      }
      function syncPreviewLayout(){
        const bar=document.querySelector(".ezws-preview-bar");
        const height=bar?Math.ceil(bar.getBoundingClientRect().height):0;
        document.body.style.setProperty("--ezws-preview-header-h",height+"px");
      }
      window.addEventListener("resize",()=>{if(previewMode)syncPreviewLayout()},{passive:true});
      async function fullscreen(){
        try{
          if(document.fullscreenElement)await document.exitFullscreen();
          else if(document.documentElement.requestFullscreen){
            await document.documentElement.requestFullscreen();
            document.body.classList.remove("ezws-immersive");
          }else throw Error("not supported");
        }catch{
          document.body.classList.toggle("ezws-immersive");
          toast(choose("Trình duyệt không hỗ trợ toàn màn hình. Đã bật chế độ tập trung; Safari có thể vẫn hiện thanh địa chỉ.",
            "Fullscreen unavailable; focused mode enabled, browser chrome may remain."));
        }
      }
      const menuList=(items)=>items.map(([tab,icon,title])=>
         '<button type="button" data-ezws="navigate" data-value="'+safe(tab)+'">'+safe(title)+'</button>'
      ).join("");
      function drawer(items=[]){
        if(!active())return "";
        const title=modeLabel(mode());
        return '<button type="button" class="ezws-open-menu" data-ezws="toggle"'+
          ' aria-haspopup="true" aria-controls="ezws-panel" aria-expanded="'+drawerOpen+'">'+
          '<span aria-hidden="true">☰</span><span>'+safe(title)+'</span></button>'+
          '<div class="ezws-drawer-shade" data-ezws="close" '+(drawerOpen?"":"hidden")+'></div>'+
          '<aside class="ezws-drawer" id="ezws-panel" role="navigation" aria-label="'+
          safe(choose("Điều hướng thiết bị","Device navigation"))+'" '+(drawerOpen?"":"hidden")+'>'+
          '<header><strong>EZ Thing · '+safe(title)+'</strong><button type="button" data-ezws="close" aria-label="Đóng">✕</button></header>'+
          '<div class="ezws-current"><small>'+safe(choose("Thiết bị","Terminal"))+'</small>'+
          '<b>'+safe(current.name||"Terminal")+'</b><span>'+safe(modeLabel(mode()))+'</span></div>'+
          (!focused()?'<div class="ezws-links">'+menuList(items)+'</div>':
           '<div class="ezws-links"><button type="button" data-ezws="navigate" data-value="'+home()+'">'+
           safe(modeLabel(mode()))+'</button></div>')+
          (owner()?'<div class="ezws-admin"><button type="button" data-ezws="settings">'+
            safe(choose("⚙ Phân công thiết bị","⚙ Configure workstations"))+'</button>'+
            (focused()?'<button type="button" data-ezws="manager">'+
               safe(choose("Mở giao diện quản lý","Open management area"))+'</button>':
               temporary&&mode()!=="manager"?'<button type="button" data-ezws="return">'+
               safe(choose("Trở lại tác vụ chính","Return to terminal"))+'</button>':"")+
            '</div>':"")+
          '<p class="ezws-caption">'+safe(choose(
             "Vai trò thiết bị chỉ điều khiển màn hình. Phân quyền thao tác dựa trên tài khoản nhân viên.",
             "Device mode controls display only. Staff account permissions govern API access."))+'</p></aside>';
      }
      function rerenderDrawer(){
        const root=document.querySelector(".ezws-drawer");
        if(!root)return;
        document.querySelectorAll(".ezws-drawer-shade,.ezws-drawer").forEach(node=>{
          node.hidden=!drawerOpen;
        });
        const button=document.querySelector(".ezws-open-menu");
        if(button)button.setAttribute("aria-expanded",String(drawerOpen));
      }
      function switchDrawer(open){drawerOpen=Boolean(open);rerenderDrawer()}
      function deviceFields(row){
        const modes=Object.entries(MODES).map(([code])=>'<option value="'+code+'" '+
          (row.mode===code?"selected":"")+'>'+safe(modeLabel(code))+'</option>').join("");
        const stations=[["all","Tất cả"],["kitchen","Bếp (nóng + lạnh)"],["hot","Bếp nóng"],
         ["cold","Bếp lạnh"],["bar","Pha chế"],["expo","Ra món"]];
        const branches=state().cache.branches||[];
        return '<article class="ezws-device-card" data-device-card="'+safe(row.id)+'">'+
          '<div class="ezws-device-title"><b>'+safe(row.name)+'</b><small>ID '+safe(row.client_key.slice(0,8))+'</small></div>'+
          '<div class="ezws-field"><label>'+choose("Chế độ màn hình","Screen mode")+'</label>'+
          '<select data-ezws-device="'+safe(row.id)+'" data-property="mode">'+modes+'</select></div>'+
          '<div class="ezws-field"><label>'+choose("Khu vực chế biến","Prep station")+'</label>'+
          '<select data-ezws-device="'+safe(row.id)+'" data-property="station">'+
          stations.map(([v,n])=>'<option value="'+v+'" '+(row.station===v?"selected":"")+">"+safe(n)+"</option>").join("")+'</select></div>'+
          '<div class="ezws-field"><label>'+choose("Chi nhánh","Branch")+'</label>'+
          '<select data-ezws-device="'+safe(row.id)+'" data-property="branch_id">'+
          '<option value="">'+choose("Tất cả chi nhánh","All branches")+'</option>'+
          branches.map(b=>'<option value="'+safe(b.id)+'" '+(row.branch_id===b.id?"selected":"")+">"+safe(b.name)+"</option>").join("")+
          '</select></div>'+
          '<div class="ezws-field"><label>'+choose("Tên thiết bị","Terminal name")+'</label>'+
          '<input data-ezws-device="'+safe(row.id)+'" data-property="name" maxlength="80" value="'+safe(row.name)+'"></div>'+
          '</article>';
      }
      async function showSettings(){
        if(!owner()||pending)return;
        switchDrawer(false);pending=true;
        try{
          const bid=state().business.id;
          const data=await api("/businesses/"+encodeURIComponent(bid)+"/workstations");
          if(bid!==state().business?.id)return;
          modal(choose("Phân công máy POS / Bếp / Bar","Workstation assignments"),
            '<div class="ezws-settings"><p>'+choose(
               "Mỗi thiết bị xuất hiện sau khi nhân viên mở EZ Thing tại máy đó. Quản lý gán chức năng tại đây; thiết bị cập nhật sau khi tải lại.",
               "Devices appear when staff first open EZ Thing. Assign a mode here; refresh the terminal to load changes.")+
            '</p><div class="ezws-preview-link"><button type="button" class="btn" data-ezws="preview-picker">👁 '+
            choose("Xem thử 5 màn hình nhân viên","Preview 5 employee screens")+'</button></div>'+
            '<div class="ezws-device-grid">'+
            (data.workstations.length?data.workstations.map(deviceFields).join(""):
             '<p>'+choose("Chưa có thiết bị nào","No terminals registered")+'</p>')+
            '</div><small>'+choose(
              "Lưu ý bảo mật: không chia sẻ tài khoản quản lý cho máy nhân viên. Phân quyền nhân sự là một lớp riêng.",
              "Security: never share manager credentials with staff terminals. Account permissions are separate.")+
            '</small></div>');
        }catch(error){toast(error.message,true)}
        finally{pending=false}
      }
      async function patchField(node){
        if(!owner()||pending)return;
        const id=node.dataset.ezwsDevice,prop=node.dataset.property;
        if(!["mode","station","branch_id","name"].includes(prop))return;
        const value=node.value;
        if(prop==="name"&&value.trim().length<2){toast("Tên thiết bị quá ngắn",true);return}
        pending=true;node.disabled=true;
        try{
          const bid=state().business.id;
          const updated=await api("/businesses/"+encodeURIComponent(bid)+"/workstations/"+encodeURIComponent(id),{
            method:"PATCH",body:JSON.stringify({[prop]:value})
          });
          if(bid!==state().business?.id)return;
          if(updated.id===current.id){applyProfile(updated);onChanged()}
          toast(choose("Đã lưu phân công","Assignment saved"));
          // Reset fields (e.g. default station) using authoritative server values.
          if(document.querySelector(".ezws-settings"))showSettingsSoon();
        }catch(error){toast(error.message,true)}
        finally{pending=false;node.disabled=false}
      }
      async function showSettingsSoon(){
        // Full refresh on next user opening avoids destroying focused form controls.
      }
      // Preview is display-only: block all app/KDS/POS mutations before handlers.
      document.addEventListener("click",event=>{
        if(!previewMode)return;
        if(event.target.closest("[data-ezws]"))return;
        if(event.target.closest("#page-content")||event.target.closest("#modal-root")){
          event.preventDefault();event.stopImmediatePropagation();
        }
      },true);
      document.addEventListener("submit",event=>{
        if(previewMode){event.preventDefault();event.stopImmediatePropagation()}
      },true);
      document.addEventListener("click",event=>{
        const button=event.target.closest("[data-ezws]");
        if(!button)return;
        event.preventDefault();
        const action=button.dataset.ezws;
        if(action==="toggle")switchDrawer(!drawerOpen);
        else if(action==="close")switchDrawer(false);
        else if(action==="settings")showSettings();
        else if(action==="preview-picker")openPreviewPicker();
        else if(action==="preview")preview(button.dataset.value);
        else if(action==="exit-preview")exitPreview();
        else if(action==="fullscreen")fullscreen();
        else if(action==="manager"&&owner()){
          temporary=true;drawerOpen=false;onChanged("overview");
        }else if(action==="return"&&owner()){
          temporary=false;drawerOpen=false;onChanged(home());
        }else if(action==="navigate"){
          const chosen=button.dataset.value;
          if(focused()&&chosen!==home())return;
          if(temporary&&owner())onChanged(chosen);
          else if(chosen===home()||mode()==="manager")onChanged(chosen);
          drawerOpen=false;
        }
      });
      document.addEventListener("change",event=>{
        const node=event.target.closest("[data-ezws-device]");
        if(node)patchField(node);
      });
      document.addEventListener("keydown",event=>{
        if(event.key==="Escape"&&drawerOpen){switchDrawer(false)}
      });
      return {load,mode,focused,home,drawer,previewNav,openPreviewPicker,
              previewOnly,exitPreview,fullscreen,syncPreviewLayout,modeLabel,isTemporary:()=>temporary,
              current:()=>current,owner,showSettings,
              allowNavigation:tab=>!focused()||tab===home(),
              applyDocument:()=>{
                document.body.dataset.ezWorkstation=focused()?mode():"manager";
                document.body.dataset.ezWorkstationActive=focused()?"true":"false";
                document.body.dataset.ezWorkstationPreview=previewOnly()?"true":"false";
              }};
    }
  };
})();
