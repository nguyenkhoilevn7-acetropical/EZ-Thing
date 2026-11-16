/* EZ Thing tenant prep-station routing configuration.
 * Product override > category routing > built-in category suggestion.
 * A setting controls auto-dispatch; manual fire remains an exception path.
 */
(() => {
  "use strict";
  window.EZKDSRouting = function init({api,E,toast,getState}) {
    const T=(vi,en)=>window.EZI18N?.language?.()==="en"?en:vi;
    const stations={bar:T("Pha chế / Bar","Bar / beverages"),
      hot:T("Bếp nóng","Hot kitchen"),cold:T("Bếp lạnh","Cold kitchen"),
      expo:T("Ra món / Phân trạm","Expo / triage"),
      skip:T("Không cần chế biến","No preparation")};
    let config=null,productCache=null,tenantId=null,busy=false,generation=0;
    const state=()=>getState();
    const bid=()=>state().business?.id;
    const canManage=()=>["owner","manager"].includes(state().business?.role);
    const key=category=>String(category||"").trim().toLocaleLowerCase("vi").replace(/\s+/g," ");
    const list=()=>state().cache?.products?.length?state().cache.products:(productCache||[]);
    const url=path=>"/businesses/"+encodeURIComponent(bid())+"/kds"+path;
    function selectors(selected=""){
      return '<option value=""'+(!selected?' selected':'')+'>'+
        T("Theo danh mục / tự nhận diện","Use category/default")+'</option>'+
        Object.entries(stations).map(([id,name])=>
          '<option value="'+id+'"'+(selected===id?' selected':'')+'>'+E(name)+'</option>').join("");
    }
    function badges(){
      if(!config)return "";
      const custom=config.category_routes||{},overrides=config.routes||{};
      const cat=Object.entries(custom).map(([c,v])=>
        '<span class="ezroute-badge">'+E(c)+' → '+E(stations[v]||v)+'</span>').join("");
      const product=Object.entries(overrides).map(([id,v])=>{
        const p=list().find(x=>x.id===id);
        return p?'<span class="ezroute-badge">'+E(p.name)+' → '+E(stations[v]||v)+'</span>':"";
      }).join("");
      return (cat||product)?'<div class="ezroute-summaries">'+
        (cat?'<p><strong>'+T("Danh mục đã cấu hình","Category routes")+'</strong></p>'+cat:"")+
        (product?'<p><strong>'+T("Sản phẩm ghi đè","Product overrides")+'</strong></p>'+product:"")+
        '</div>':"";
    }
    function render(){
      if(!canManage())return '<p class="ezroute-staff-hint">'+T(
        "Đơn mới đã được gửi đến trạm theo cấu hình quản lý.",
        "New orders route to the stations chosen by management.")+'</p>';
      const items=list();
      const categories=[...new Set(items.map(p=>String(p.category||"Khác").trim()))]
        .sort((a,b)=>a.localeCompare(b,"vi"));
      const catOptions=categories.map(c=>'<option value="'+E(c)+'">'+E(c)+'</option>').join("");
      const itemOptions=items.map(p=>'<option value="'+E(p.id)+'">'+
        E(p.name)+' · '+E(p.category||"Khác")+'</option>').join("");
      const automatic=config?.settings?.auto_dispatch!==false;
      return '<details class="ezroute-panel"><summary>⚙ '+
        T("Cấu hình tự động phân trạm","Automatic station routing")+
        '<span class="ezroute-state '+(automatic?"on":"off")+'">'+
        (automatic?T("ĐANG BẬT","ON"):T("TẮT","OFF"))+'</span></summary>'+
        '<div class="ezroute-intro"><strong>'+
        T("Đơn mới tự chuyển đến bếp hoặc quầy pha chế khi được lưu/duyệt.",
          "New checks route to the kitchen or bar as soon as they are saved/accepted.")+
        '</strong><p>'+T("Ưu tiên: Trạm riêng từng món → Danh mục → Gợi ý. Chọn Không cần chế biến để loại sản phẩm khỏi phiếu KDS.",
        "Priority: item override → category → suggestion. Set No preparation to exclude products from KDS.")+
        '</p></div>'+
        '<div class="ezroute-grid">'+
        '<form data-ezroute-form="settings" class="ezroute-card"><h4>'+
        T("1. Gửi đơn tự động","1. Automatic dispatch")+'</h4>'+
        '<label class="ezroute-switch"><input type="checkbox" name="auto_dispatch" '+
        (automatic?"checked":"")+'><span>'+T(
          "Tự chuyển món tới trạm sau khi lưu POS hoặc duyệt đơn website",
          "Automatically route POS saves and accepted website checks")+'</span></label>'+
        '<button type="submit" class="btn sm">'+T("Lưu chế độ","Save mode")+'</button></form>'+
        '<form data-ezroute-form="category" class="ezroute-card"><h4>'+
        T("2. Cấu hình theo danh mục","2. Category routing")+'</h4>'+
        '<label>'+T("Danh mục","Category")+'<select name="category" required>'+catOptions+'</select></label>'+
        '<label>'+T("Khu vực tiếp nhận","Destination")+'<select name="station">'+
        selectors(config?.category_routes?.[key(categories[0])]||"")+'</select></label>'+
        '<button type="submit" class="btn sm">'+T("Lưu danh mục","Save category")+'</button></form>'+
        '<form data-ezroute-form="product" class="ezroute-card"><h4>'+
        T("3. Ngoại lệ theo sản phẩm","3. Product exception")+'</h4>'+
        '<label>'+T("Sản phẩm","Product")+'<select name="product_id" required>'+itemOptions+'</select></label>'+
        '<label>'+T("Khu vực tiếp nhận","Destination")+'<select name="station">'+
        selectors(config?.routes?.[items[0]?.id]||"")+'</select></label>'+
        '<button type="submit" class="btn sm">'+T("Lưu sản phẩm","Save item")+'</button></form>'+
        '</div>'+badges()+
        '<p class="ezroute-disclaimer">'+T(
          "Thay đổi chỉ áp dụng cho đơn mới. Phiếu đã vào KDS giữ nguyên trạm cũ. Máy in cần được cấu hình theo từng trạm.",
          "Changes apply to future checks only; existing KDS tickets keep their original routing. Printers require matching station setup.")+
        '</p></details>';
    }
    function paint(){
      const root=document.getElementById("ez-kds-routing");
      if(!root)return;
      const expanded=Boolean(root.querySelector("details[open]"));
      root.innerHTML=render();
      const details=root.querySelector("details");
      if(details)details.open=expanded;
    }
    async function load(){
      if(!canManage()||!bid())return;
      const expected=bid(),serial=++generation;
      const [next,products]=await Promise.all([
        api(url("/routes")),
        api("/businesses/"+encodeURIComponent(expected)+"/products"),
      ]);
      if(serial!==generation||bid()!==expected)return;
      tenantId=expected;config=next;productCache=products;paint();
    }
    function mount(){tenantId=bid();load().catch(e=>toast(e.message,true))}
    function invalidate(){generation++;config=null;productCache=null;tenantId=null;busy=false}
    async function submit(form){
      if(busy||!canManage()||!bid())return;
      busy=true;
      const submitButton=form.querySelector('[type="submit"]');
      if(submitButton)submitButton.disabled=true;
      const kind=form.dataset.ezrouteForm;
      const data=Object.fromEntries(new FormData(form));
      try{
        if(kind==="settings"){
          await api(url("/settings"),{method:"PUT",body:JSON.stringify({
            auto_dispatch:Boolean(form.querySelector('[name="auto_dispatch"]').checked)
          })});
        }else if(kind==="category"){
          if(!data.category)return;
          await api(url("/category-routes"),{
            method:data.station?"PUT":"DELETE",
            body:JSON.stringify({category:data.category,...(data.station?{station:data.station}:{})})
          });
        }else if(kind==="product"){
          if(!data.product_id)return;
          if(!data.station){
            await api(url("/routes/"+encodeURIComponent(data.product_id)),{method:"DELETE"});
          }else await api(url("/routes"),{method:"PUT",
            body:JSON.stringify({product_id:data.product_id,station:data.station})});
        }
        await load();
        toast(T("Đã lưu phân trạm. Áp dụng cho các đơn tiếp theo.",
          "Routing saved; it applies to future orders."));
      }catch(error){toast(error.message||T("Lỗi lưu cấu hình","Unable to save routing"),true)}
      finally{busy=false;if(submitButton?.isConnected)submitButton.disabled=false}
    }
    document.addEventListener("submit",event=>{
      const form=event.target.closest("#ez-kds-routing [data-ezroute-form]");
      if(!form)return;
      event.preventDefault();event.stopImmediatePropagation();submit(form);
    },true);
    document.addEventListener("change",event=>{
      const select=event.target.closest("#ez-kds-routing [data-ezroute-form='product'] [name='product_id']");
      if(select){
        const value=config?.routes?.[select.value]||"";
        const target=select.closest("form")?.querySelector('[name="station"]');
        if(target)target.value=value;
      }
      const cat=event.target.closest("#ez-kds-routing [data-ezroute-form='category'] [name='category']");
      if(cat){
        const value=config?.category_routes?.[key(cat.value)]||"";
        const target=cat.closest("form")?.querySelector('[name="station"]');
        if(target)target.value=value;
      }
    },true);
    return {render,mount,invalidate};
  };
})();
