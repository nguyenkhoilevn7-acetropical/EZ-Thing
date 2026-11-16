/* EZ Thing Register — dedicated fast-sale workspace, not a back-office order form.
   Products/prices/modifiers are previews only; POST /orders remains authoritative.
   No automatic payment inference, offline writes, or client-side stock mutation. */
(() => {
  "use strict";
  window.EZRegisterUI = function init({api,E,V,toast,getState,navigate,onCreated,onPaid,onPrint}) {
    const uid=()=>globalThis.crypto?.randomUUID?.()||
      "pos-"+Date.now().toString(36)+"-"+Math.random().toString(36).slice(2);
    const t=(vi,en)=>window.EZI18N?.language?.()==="en"?en:vi;
    const defaultState=()=>({
      bid:"",category:"all",search:"",branch:"",table:"",customer:"",note:"",
      cart:[],mobileCart:false,optionProduct:"",optionId:"",optionQty:1,
      optionIds:[],busy:false,requestId:uid(),last:null
    });
    let s=defaultState();
    const business=()=>getState().business||{};
    const products=()=>getState().cache.products||[];
    const branches=()=>getState().cache.branches||[];
    const tables=()=>getState().cache.tables||[];
    const customers=()=>getState().cache.customers||[];
    const byId=id=>products().find(x=>x.id===id);
    const validProducts=()=>products().filter(p=>p.active!==false);
    const positive=n=>Math.max(1,Math.min(1000,Math.round(Number(n)||1)));
    const glyph=p=>{
      const name=(p.name+" "+(p.category||"")).toLocaleLowerCase("vi");
      if(/trà|tea|matcha|milk|sữa|nước|drink|juice|soda|coffee|cafe|cà phê/.test(name))
        return /cà phê|coffee|cafe/.test(name)?"☕":/milk|sữa/.test(name)?"🧋":"🥤";
      if(/bánh|cake|dessert|pastry|cookie/.test(name))return "🍰";
      if(/món|food|cơm|bún|phở|mì|noodle|curry/.test(name))return "🍲";
      if(/fruit|trái cây|quả/.test(name))return "🍊";
      if(/spa|dịch vụ|service|massage/.test(name))return "✳";
      return "📦";
    };
    const fmt=number=>V(Number(number)||0);
    const price=p=>Math.max(0,Number(p?.price_vnd)||0);
    const option=p=>((p?.modifier_groups||[]).flatMap(g=>g.options||[]));
    const modifierPrice=(p,ids)=>option(p).filter(o=>ids.includes(o.id))
      .reduce((sum,o)=>sum+(Number(o.price_vnd)||0),0);
    const category=p=>String(p.category||t("Khác","Other")).trim()||t("Khác","Other");
    const belongs=()=>s.bid===business().id;
    const checkout=window.EZCashierCheckout?.({api,E,V,toast,getBusiness:business,
      getTotal:total,createOrder:create,onPaid:async result=>{
        if(s.last?.id===result.order.id){s.last.paid=true;s.last.payment=result.payment}
        else s.last={id:result.order.id,total_vnd:result.order.total_vnd,
          paid:true,payment:result.payment,kitchenSent:false};
        // Confirmed tender must update the register before async dashboard refresh.
        paint();
        if(onPaid)await onPaid();
        paint();
      }});
    const available=p=>p?.active!==false&&(!p?.track_stock||Number(p.stock)>0);
    const selectionsValid=(p,ids)=>{
      if(!p)return false;
      for(const g of p.modifier_groups||[]){
        const chosen=(g.options||[]).filter(o=>ids.includes(o.id)).length;
        if(chosen<Number(g.min_select)||chosen>Number(g.max_select))return false;
      }
      return true;
    };
    function initTenant(){
      if(belongs())return;
      s=defaultState();
      checkout?.reset();
      s.bid=business().id;
      s.branch=getState().workstation?.branch_id||branches()[0]?.id||"";
    }
    function total(){return s.cart.reduce((sum,line)=>{
      const p=byId(line.productId);
      return sum+(price(p)+modifierPrice(p,line.optionIds))*line.quantity;
    },0)}
    const totalQty=()=>s.cart.reduce((sum,line)=>sum+line.quantity,0);
    const categoryList=()=>["all",...new Set(validProducts().map(category))];
    function visibleProducts(){
      const query=s.search.trim().toLocaleLowerCase("vi");
      return validProducts().filter(p=>(s.category==="all"||category(p)===s.category)
        &&(!query||(p.name+" "+p.sku+" "+category(p)).toLocaleLowerCase("vi").includes(query)));
    }
    const optionText=(p,ids)=>{
      const tags=[];
      (p?.modifier_groups||[]).forEach(g=>(g.options||[]).forEach(o=>{
        if(ids.includes(o.id))tags.push(o.name);
      }));
      return tags.join(" · ");
    };
    function iconBlock(p){
      // No uploaded product media exists in the current Product model.
      // These category glyphs are labeled placeholders, not claimed photos.
      const url=p.image_url||'';
      const trusted=url.startsWith('/api/businesses/'+encodeURIComponent(s.bid)+'/products/');
      return '<span class="ezreg-visual" aria-hidden="true">'+
        (trusted?'<img src="'+E(url)+'" alt="" loading="lazy" decoding="async">':glyph(p))+'</span>';
    }
    function categoriesHtml(){
      return categoryList().map(cat=>{
        const count=cat==="all"?validProducts().length:
          validProducts().filter(p=>category(p)===cat).length;
        return '<button type="button" data-ezreg="category" data-value="'+E(cat)+
          '" class="ezreg-category '+(s.category===cat?"active":"")+
          '" aria-pressed="'+(s.category===cat)+'">'+
          (cat==="all"?t("Tất cả","All"):E(cat))+
          '<span>'+count+'</span></button>';
      }).join("");
    }
    function productHtml(p){
      const soldOut=!available(p);
      return '<button type="button" class="ezreg-product '+(soldOut?"sold-out":"")+
        '" data-ezreg="product" data-value="'+E(p.id)+'" '+(soldOut?"disabled":"")+
        ' aria-label="'+E(p.name+" "+fmt(price(p)))+'">'+
        '<span class="ezreg-product-top">'+iconBlock(p)+
        (p.track_stock?'<span class="ezreg-stock '+(Number(p.stock)<=5?"low":"")+
        '">'+(soldOut?t("Hết hàng","Out of stock"):t("Còn ","Stock ")+E(p.stock))+'</span>':
        '<span class="ezreg-stock neutral">'+t("Sẵn bán","Available")+'</span>')+
        '</span><span class="ezreg-product-name">'+E(p.name)+'</span>'+
        '<span class="ezreg-product-sub">'+E(category(p))+'</span>'+
        '<span class="ezreg-product-bottom"><strong>'+fmt(price(p))+'</strong>'+
        '<span class="ezreg-product-plus" aria-hidden="true">+</span></span></button>';
    }
    function catalogHtml(){
      const list=visibleProducts();
      return list.length?list.map(productHtml).join(""):
        '<div class="ezreg-empty-search">'+
        '<strong>'+t("Không tìm thấy sản phẩm","No products found")+'</strong>'+
        '<p>'+t("Thử tên, mã SKU hoặc danh mục khác.","Try another name, SKU or category.")+'</p></div>';
    }
    function cartLineHtml(line){
      const p=byId(line.productId);
      if(!p)return "";
      return '<article class="ezreg-cart-line" data-line-id="'+E(line.id)+'">'+
        '<div class="ezreg-cart-icon">'+glyph(p)+'</div>'+
        '<div class="ezreg-cart-description"><strong>'+E(p.name)+'</strong>'+
        (line.optionIds.length?'<small>'+E(optionText(p,line.optionIds))+'</small>':
          '<small>'+E(category(p))+'</small>')+
        '<div class="ezreg-line-actions"><button type="button" data-ezreg="decrease" data-value="'+E(line.id)+
        '" aria-label="'+t("Giảm số lượng","Decrease")+'">−</button>'+
        '<b>'+line.quantity+'</b><button type="button" data-ezreg="increase" data-value="'+E(line.id)+
        '" aria-label="'+t("Tăng số lượng","Increase")+'">+</button>'+
        ((p.modifier_groups||[]).length?'<button type="button" class="ezreg-edit-line" data-ezreg="edit" data-value="'+E(line.id)+
        '">'+t("Tùy chọn","Options")+'</button>':"")+'</div></div>'+
        '<div class="ezreg-line-side"><strong>'+fmt((price(p)+modifierPrice(p,line.optionIds))*line.quantity)+'</strong>'+
        '<button type="button" data-ezreg="remove" data-value="'+E(line.id)+
        '" aria-label="'+t("Xóa món","Remove item")+'">✕</button></div></article>';
    }
    function cartInnerHtml(){
      const activeTables=tables().filter(x=>x.branch_id===s.branch);
      const hasTables=business().active_modules?.includes("tables");
      return '<div class="ezreg-cart-head"><div><span class="ezreg-kicker">'+
        t("ĐƠN BÁN HÀNG","CURRENT CHECK")+'</span><h3>'+
        t("Giỏ hàng","Cart")+' <span class="ezreg-count">'+totalQty()+'</span></h3></div>'+
        '<button type="button" class="ezreg-cart-close" data-ezreg="cart-close" aria-label="'+
        t("Đóng giỏ hàng","Close cart")+'">✕</button></div>'+
        '<div class="ezreg-cart-meta"><label>'+t("Chi nhánh","Branch")+
        '<select data-ezreg-select="branch" aria-label="'+t("Chọn chi nhánh","Select branch")+'">'+
        branches().map(b=>'<option value="'+E(b.id)+'"'+(b.id===s.branch?" selected":"")+">"+
          E(b.name)+'</option>').join("")+'</select></label>'+
        (hasTables?'<label>'+t("Hình thức / bàn","Service / table")+
          '<select data-ezreg-select="table" aria-label="'+t("Chọn bàn","Select table")+'">'+
          '<option value="">'+t("Mang đi / Giao hàng","Takeaway / delivery")+'</option>'+
          activeTables.map(tab=>'<option value="'+E(tab.id)+'"'+
          (s.table===tab.id?" selected":"")+">"+E(tab.label)+
          (tab.occupied?" · "+t("Đang dùng","Occupied"):"")+"</option>").join("")+
          '</select></label>':"")+
        '<label>'+t("Khách hàng","Customer")+'<select data-ezreg-select="customer">'+
        '<option value="">'+t("Khách lẻ","Walk-in")+'</option>'+
        customers().map(c=>'<option value="'+E(c.id)+'"'+
          (s.customer===c.id?" selected":"")+">"+E(c.name)+"</option>").join("")+
        '</select></label></div>'+
        '<div class="ezreg-cart-items">'+(s.cart.length?s.cart.map(cartLineHtml).join(""):
          '<div class="ezreg-cart-empty"><span>🧾</span><strong>'+
          t("Chưa có món nào","No items yet")+'</strong><p>'+
          t("Chạm sản phẩm bên trái để thêm nhanh vào đơn.","Tap any item to add it to this check.")+
          '</p></div>')+'</div>'+
        '<label class="ezreg-note-label">'+t("Ghi chú cho đơn","Order note")+
        '<textarea data-ezreg-note maxlength="300" rows="2" placeholder="'+
        t("Ví dụ: Ít đá, giao trước 15:00...","For example: Less ice, pickup at 3 PM...")+'">'+
        E(s.note)+'</textarea></label>'+
        '<div class="ezreg-cart-footer"><div class="ezreg-subtotal"><span>'+
        t("Tạm tính","Estimated subtotal")+'</span><strong>'+fmt(total())+'</strong></div>'+
        '<div class="ezreg-finance-hint">'+t("Giá cuối cùng được xác nhận trên máy chủ. Chưa thu tiền.",
        "Final prices are verified on the server. No payment collected.")+'</div>'+
        '<button type="button" class="ezreg-create ezreg-pay-primary" data-ezreg="checkout" '+
        (!s.cart.length||s.busy||!navigator.onLine?"disabled":"")+'>'+
        (s.busy?t("Đang xử lý...","Processing..."):
          t("Thanh toán","Checkout"))+
        '<span>'+fmt(total())+'</span></button>'+
        '<button type="button" class="ezreg-save-check" data-ezreg="create" '+
        (!s.cart.length||s.busy||!navigator.onLine?"disabled":"")+'>'+t("Lưu đơn · Chưa thu tiền","Save check · Unpaid")+'</button>'+
        '<div class="ezreg-secondary-actions"><button type="button" data-ezreg="clear" '+
        (!s.cart.length?"disabled":"")+'>'+t("Xóa giỏ hàng","Clear cart")+'</button>'+
        '<button type="button" data-ezreg="orders">'+t("Xem đơn đã tạo","View orders")+'</button></div></div>';
    }
    function lastHtml(){
      const o=s.last;
      if(!o)return "";
      const role=business().role;
      return '<section class="ezreg-last" aria-live="polite"><span class="ezreg-last-icon">✓</span>'+
        '<div><strong>'+t("Đơn đã lưu thành công","Order saved")+
        ' #'+E(o.id.slice(0,8).toUpperCase())+'</strong>'+
        '<p>'+fmt(o.total_vnd)+' · '+(o.paid?t("Đã ghi nhận tiền","Payment confirmed"):
          t("Chưa xác nhận nhận tiền","Payment not yet confirmed"))+
        (o.paid&&o.payment?.method==="cash"?' · '+t("Tiền thừa ","Change ")+fmt(o.payment.change_vnd):"")+
        (o.paid&&o.payment?.method==="bank_transfer"?' · '+t("Chuyển khoản thủ công","Manual transfer"):"")+
        '</p><div class="ezreg-last-actions">'+
        (business().industry==="fnb"&&o.kdsStatus==="sent"?'<span>'+
          t("✓ Đã tự chuyển đến trạm chế biến","✓ Automatically sent to prep stations")+'</span>':"")+
        (business().industry==="fnb"&&o.kdsStatus==="no_prep"?'<span>'+
          t("✓ Không có món cần chế biến","✓ No preparation needed")+'</span>':"")+
        (business().industry==="fnb"&&o.kdsStatus==="manual"?
          '<button type="button" data-ezreg="send-kitchen">'+
          t("Gửi bếp thủ công","Send manually")+'</button>':"")+
        (!o.paid?'<button type="button" data-ezreg="paid">'+
          t("Thanh toán đơn này","Take payment")+'</button>':
          '<button type="button" data-ezreg="print">'+t("🖨 In phiếu thanh toán","🖨 Print receipt")+'</button>')+
        '<button type="button" data-ezreg="orders">'+t("Danh sách đơn","Order list")+
        '</button></div></div></section>';
    }
    function render(){
      initTenant();
      const stock=validProducts();
      return '<section class="ezreg" id="ez-register" aria-label="'+
        t("Màn hình bán hàng POS","POS register")+'">'+
        '<div class="ezreg-header"><div><span class="ezreg-kicker">EZ THING · POINT OF SALE</span>'+
        '<h2>'+t("Bán hàng nhanh","Quick sale")+'</h2><p>'+
        t("Chọn món, tùy chỉnh, tạo đơn trong một màn hình.",
          "Select items, customize and create checks in one workspace.")+'</p></div>'+
        '<div class="ezreg-header-actions"><span class="ezreg-online" role="status">'+
        (navigator.onLine?t("● Đang kết nối","● Online"):t("● Mất kết nối","● Offline"))+'</span>'+
        '<button type="button" data-ezreg="orders">'+t("Đơn hàng →","Orders →")+
        '</button></div></div>'+lastHtml()+
        '<div class="ezreg-layout"><section class="ezreg-catalog">'+
        '<div class="ezreg-catalog-head"><div><h3>'+t("Thực đơn & sản phẩm","Menu & products")+
        '</h3><span>'+stock.length+' '+t("mặt hàng","items")+'</span></div>'+
        '<label class="ezreg-search"><span>⌕</span><input type="search" data-ezreg-search '+
        'placeholder="'+t("Tìm tên món, mã SKU...","Search items or SKU...")+
        '" value="'+E(s.search)+'" aria-label="'+t("Tìm sản phẩm","Search products")+
        '"></label></div>'+
        '<div class="ezreg-categories" id="ezreg-categories">'+categoriesHtml()+'</div>'+
        '<div class="ezreg-products" id="ezreg-products">'+catalogHtml()+'</div>'+
        '</section><aside class="ezreg-cart '+(s.mobileCart?"mobile-open":"")+
        '" id="ezreg-cart" aria-label="'+t("Đơn hàng hiện tại","Current check")+'">'+
        cartInnerHtml()+'</aside></div>'+
        '<button class="ezreg-mobile-cartbar" data-ezreg="cart-toggle" type="button">'+
        '<span>🛒 '+totalQty()+' '+t("món","items")+'</span><strong>'+fmt(total())+
        '</strong><span>'+t("Xem giỏ ↑","View cart ↑")+'</span></button>'+
        '<div class="ezreg-cart-backdrop '+(s.mobileCart?"visible":"")+
        '" data-ezreg="cart-close"></div>'+
        '<div id="ezreg-option-mount"></div><div id="ezreg-payment-mount">'+(checkout?.render()||"")+'</div></section>';
    }
    function paint(){
      const node=document.getElementById("ez-register");
      if(!node||!belongs())return;
      const focusedSearch=document.activeElement?.matches("[data-ezreg-search]");
      const start=focusedSearch?document.activeElement.selectionStart:null;
      node.outerHTML=render();
      if(focusedSearch){
        const field=document.querySelector("#ez-register [data-ezreg-search]");
        if(field){field.focus();if(start!==null)field.setSelectionRange(start,start)}
      }
      if(s.optionProduct)paintOptions();
    }
    function paintCatalog(){
      const categories=document.getElementById("ezreg-categories");
      const grid=document.getElementById("ezreg-products");
      if(categories)categories.innerHTML=categoriesHtml();
      if(grid)grid.innerHTML=catalogHtml();
    }
    function syncCart(){
      const element=document.getElementById("ezreg-cart");
      if(!element)return;
      element.innerHTML=cartInnerHtml();
      element.classList.toggle("mobile-open",s.mobileCart);
      const bar=document.querySelector(".ezreg-mobile-cartbar");
      if(bar)bar.innerHTML='<span>🛒 '+totalQty()+' '+t("món","items")+'</span>'+
        '<strong>'+fmt(total())+'</strong><span>'+t("Xem giỏ ↑","View cart ↑")+'</span>';
      document.querySelector(".ezreg-cart-backdrop")?.classList.toggle("visible",s.mobileCart);
    }
    function validOptionCount(p,chosen){
      return (p.modifier_groups||[]).every(g=>{
        const n=(g.options||[]).filter(o=>chosen.includes(o.id)).length;
        return n>=Number(g.min_select)&&n<=Number(g.max_select);
      });
    }
    function optionsHtml(){
      const p=byId(s.optionProduct);
      if(!p)return "";
      const groups=(p.modifier_groups||[]);
      const allowed=validOptionCount(p,s.optionIds);
      const unit=price(p)+modifierPrice(p,s.optionIds);
      return '<div class="ezreg-option-backdrop" data-ezreg="option-close"></div>'+
        '<div class="ezreg-option-dialog" role="dialog" aria-modal="true" aria-labelledby="ezreg-option-title">'+
        '<div class="ezreg-option-title"><div>'+iconBlock(p)+
        '<div><span class="ezreg-kicker">'+E(category(p))+'</span><h3 id="ezreg-option-title">'+
        E(p.name)+'</h3><strong>'+fmt(price(p))+'</strong></div></div>'+
        '<button type="button" data-ezreg="option-close" aria-label="'+t("Đóng","Close")+'">✕</button></div>'+
        '<div class="ezreg-options-body">'+groups.map(g=>{
          const max=Number(g.max_select)||1;
          const min=Number(g.min_select)||0;
          const selected=(g.options||[]).filter(o=>s.optionIds.includes(o.id)).length;
          return '<fieldset class="ezreg-option-group" data-group="'+E(g.id)+'" data-min="'+min+'" data-max="'+max+'">'+
            '<legend><strong>'+E(g.name)+'</strong><small>'+
            (min?t("Bắt buộc","Required")+' · '+t("Chọn ít nhất ","Select at least ")+min:
            t("Tùy chọn","Optional"))+' · '+t("Tối đa ","Max ")+max+
            ' · '+selected+'/'+max+'</small></legend>'+
            '<div class="ezreg-options">'+(g.options||[]).map(o=>{
              const checked=s.optionIds.includes(o.id);
              return '<button type="button" data-ezreg="option" data-group="'+E(g.id)+
                '" data-value="'+E(o.id)+'" aria-pressed="'+checked+
                '" class="ezreg-option '+(checked?"selected":"")+'">'+
                '<span class="ezreg-choice-icon">'+(checked?"✓":"+")+'</span>'+
                '<span>'+E(o.name)+'</span><small>'+
                (o.price_vnd?'+'+fmt(o.price_vnd):t("Miễn phí","Free"))+
                '</small></button>';
            }).join("")+'</div></fieldset>';
        }).join("")+'</div>'+
        '<div class="ezreg-option-footer"><div class="ezreg-option-qty"><button type="button" data-ezreg="option-qty-down" aria-label="'+
        t("Giảm số lượng","Decrease quantity")+'">−</button><b>'+s.optionQty+
        '</b><button type="button" data-ezreg="option-qty-up" aria-label="'+
        t("Tăng số lượng","Increase quantity")+'">+</button></div>'+
        '<button type="button" data-ezreg="option-save" '+(allowed?"":"disabled")+
        '>'+((allowed?t("Thêm vào đơn","Add to check"):t("Chọn đủ tùy chọn bắt buộc","Select required options")))+
        '<strong>'+fmt(unit*s.optionQty)+'</strong></button></div></div>';
    }
    function paintOptions(){
      const mount=document.getElementById("ezreg-option-mount");
      if(mount)mount.innerHTML=s.optionProduct?optionsHtml():"";
    }
    function openProduct(pid,editId=""){
      const p=byId(pid);
      if(!p||!available(p))return toast(t("Sản phẩm không còn bán","Item unavailable"),true);
      const item=s.cart.find(x=>x.id===editId);
      if(!item&&s.cart.length>=50)return toast(t("Đơn tối đa 50 dòng","Maximum 50 lines"),true);
      if(!(p.modifier_groups||[]).length&&!editId){
        addLine(pid,[],1);
        return;
      }
      s.optionProduct=pid;s.optionId=editId;
      s.optionIds=item?[...item.optionIds]:[];
      s.optionQty=item?item.quantity:1;
      paintOptions();
      document.getElementById("ezreg-option-title")?.scrollIntoView({block:"nearest"});
    }
    function addLine(pid,ids,quantity){
      const product=byId(pid);
      if(!product||!available(product))return;
      if(!validOptionCount(product,ids))
        return toast(t("Hãy chọn đủ Size/Topping bắt buộc","Select required modifiers"),true);
      const signature=JSON.stringify([...ids].sort());
      const match=s.cart.find(x=>x.productId===pid&&JSON.stringify([...x.optionIds].sort())===signature);
      if(match){match.quantity=Math.min(1000,match.quantity+quantity)}
      else{
        if(s.cart.length>=50)return toast(t("Tối đa 50 dòng trên một đơn","Maximum 50 lines per check"),true);
        s.cart.push({id:uid(),productId:pid,quantity,optionIds:[...ids]});
      }
      s.last=null;
      syncCart();
    }
    function saveOptions(){
      const p=byId(s.optionProduct);
      if(!p||!validOptionCount(p,s.optionIds)){
        toast(t("Vui lòng chọn đủ tùy chọn bắt buộc","Please complete required choices"),true);
        return;
      }
      if(s.optionId){
        const item=s.cart.find(x=>x.id===s.optionId);
        if(item){item.optionIds=[...s.optionIds];item.quantity=s.optionQty}
      }else addLine(s.optionProduct,s.optionIds,s.optionQty);
      s.optionProduct="";s.optionId="";s.optionIds=[];
      paintOptions();syncCart();
    }
    function toggleOption(groupId,optionId){
      const p=byId(s.optionProduct);
      const group=p?.modifier_groups?.find(g=>g.id===groupId);
      if(!group)return;
      const selected=new Set(s.optionIds);
      const inGroup=(group.options||[]).map(o=>o.id);
      if(selected.has(optionId))selected.delete(optionId);
      else{
        if(Number(group.max_select)===1)inGroup.forEach(id=>selected.delete(id));
        else if(inGroup.filter(id=>selected.has(id)).length>=Number(group.max_select)){
          toast(t("Đã đạt số lượng tùy chọn tối đa","Maximum options selected"),true);
          return;
        }
        selected.add(optionId);
      }
      s.optionIds=[...selected];
      paintOptions();
    }
    function changeQty(id,diff){
      const line=s.cart.find(x=>x.id===id);
      if(!line)return;
      if(line.quantity+diff<1)s.cart=s.cart.filter(x=>x.id!==id);
      else line.quantity=Math.min(1000,line.quantity+diff);
      s.last=null;syncCart();
    }
    function ensureValid(){
      if(!s.cart.length)throw Error(t("Chưa chọn sản phẩm","No products in cart"));
      if(s.cart.length>50)throw Error(t("Giỏ hàng quá 50 dòng","Too many lines"));
      if(!branches().find(b=>b.id===s.branch))throw Error(t("Chọn chi nhánh trước","Select a branch"));
      if(s.table&&!tables().some(x=>x.id===s.table&&x.branch_id===s.branch))
        throw Error(t("Bàn không thuộc chi nhánh đã chọn","Table is in another branch"));
      if(s.customer&&!customers().some(x=>x.id===s.customer))
        throw Error(t("Khách hàng không hợp lệ","Customer not found"));
      for(const line of s.cart){
        const p=byId(line.productId);
        if(!p||!available(p))throw Error(t("Có sản phẩm đã ngừng bán","Unavailable product in cart"));
        if(!validOptionCount(p,line.optionIds))
          throw Error(t("Thiếu lựa chọn bắt buộc cho ","Missing required options for ")+p.name);
        if(line.quantity<1||line.quantity>1000)throw Error(t("Số lượng không hợp lệ","Invalid quantity"));
      }
      if(!navigator.onLine)throw Error(t("Cần kết nối Internet để lưu đơn","Internet required to save checks"));
    }
    async function create(){
      if(s.busy)return;
      try{ensureValid()}catch(err){toast(err.message,true);return}
      const bid=s.bid;
      const body={
        idempotency_key:s.requestId,
        branch_id:s.branch,table_id:s.table||null,customer_id:s.customer||null,
        note:s.note.trim().slice(0,300),
        lines:s.cart.map(x=>({
          product_id:x.productId,quantity:x.quantity,selected_options:[...x.optionIds]
        }))
      };
      s.busy=true;syncCart();
      try{
        const order=await api("/businesses/"+encodeURIComponent(bid)+"/orders",{
          method:"POST",body:JSON.stringify(body)
        });
        if(bid!==business().id)return;
        s.cart=[];s.note="";s.optionProduct="";s.mobileCart=false;
        s.requestId=uid();
        s.last={id:order.id,total_vnd:order.total_vnd,paid:false,
          kdsStatus:order.kds_dispatch?.status||null};
        toast(t("Đã tạo đơn #","Created order #")+order.id.slice(0,8).toUpperCase());
        if(onCreated){try{await onCreated(order)}catch(error){toast(t("Đã lưu đơn nhưng chưa tải lại danh sách","Order saved, refresh failed"),true)}}
        paint();
        return order;
      }catch(error){
        // Do not generate a fresh request id on network timeout: the backend
        // may have committed even if its response was lost.
        toast(error.message||t("Không thể lưu đơn","Unable to save order"),true);
        return null;
      }finally{s.busy=false;syncCart()}
    }
    async function sendKitchen(){
      if(!s.last||s.busy||business().industry!=="fnb"||s.last.kdsStatus!=="manual")return;
      s.busy=true;
      try{
        await api("/businesses/"+encodeURIComponent(s.bid)+"/kds/fire",{
          method:"POST",body:JSON.stringify({order_id:s.last.id})
        });
        s.last.kdsStatus="sent";
        toast(t("Đã gửi bếp & pha chế","Sent to kitchen & bar"));
        if(onCreated)await onCreated(null);
      }catch(err){toast(err.message,true)}
      finally{s.busy=false;paint()}
    }
    async function markPaid(){
      if(!s.last||s.busy||s.last.paid)return;
      checkout?.begin(s.last);
    }
    function mount(){initTenant();paintCatalog()}
    function open(preTable=""){
      initTenant();
      const tab=tables().find(x=>x.id===preTable);
      if(tab){s.branch=tab.branch_id;s.table=tab.id}
      navigate("pos");
    }
    function closeDraft(){
      if(!s.cart.length||confirm(t("Xóa toàn bộ món khỏi giỏ hiện tại?","Clear this cart?"))){
        s.cart=[];s.requestId=uid();s.last=null;syncCart();
      }
    }
    document.addEventListener("click",event=>{
      const button=event.target.closest("[data-ezreg]");
      if(!button||!document.getElementById("ez-register")?.contains(button))return;
      event.preventDefault();event.stopPropagation();
      const action=button.dataset.ezreg,value=button.dataset.value;
      if(action==="category"){s.category=value;paintCatalog()}
      else if(action==="product")openProduct(value);
      else if(action==="increase")changeQty(value,1);
      else if(action==="decrease")changeQty(value,-1);
      else if(action==="remove"){s.cart=s.cart.filter(x=>x.id!==value);s.last=null;syncCart()}
      else if(action==="edit"){const line=s.cart.find(x=>x.id===value);if(line)openProduct(line.productId,line.id)}
      else if(action==="option")toggleOption(button.dataset.group,value);
      else if(action==="option-qty-up"){s.optionQty=Math.min(1000,s.optionQty+1);paintOptions()}
      else if(action==="option-qty-down"){s.optionQty=Math.max(1,s.optionQty-1);paintOptions()}
      else if(action==="option-save")saveOptions();
      else if(action==="option-close"){s.optionProduct="";s.optionId="";paintOptions()}
      else if(action==="cart-toggle"){s.mobileCart=true;syncCart()}
      else if(action==="cart-close"){s.mobileCart=false;syncCart()}
      else if(action==="clear")closeDraft();
      else if(action==="create")create();
      else if(action==="checkout"){
        try{ensureValid();checkout?.begin()}catch(err){toast(err.message,true)}
      }
      else if(action==="orders")navigate("orders");
      else if(action==="send-kitchen")sendKitchen();
      else if(action==="paid")markPaid();
      else if(action==="print"&&s.last?.paid)onPrint?.(s.last.id);
    },true);
    document.addEventListener("input",event=>{
      if(!document.getElementById("ez-register"))return;
      if(event.target.matches("[data-ezreg-search]")){
        s.search=event.target.value;paintCatalog();
      }
      if(event.target.matches("[data-ezreg-note]"))s.note=event.target.value;
    },true);
    document.addEventListener("change",event=>{
      if(!document.getElementById("ez-register"))return;
      const el=event.target,field=el.dataset.ezregSelect;
      if(field==="branch"){
        s.branch=el.value;
        if(!tables().some(x=>x.id===s.table&&x.branch_id===s.branch))s.table="";
        syncCart();
      }else if(field==="table")s.table=el.value;
      else if(field==="customer")s.customer=el.value;
    },true);
    document.addEventListener("keydown",event=>{
      if(!document.getElementById("ez-register"))return;
      if(event.key==="Escape"){
        if(s.optionProduct){s.optionProduct="";s.optionId="";paintOptions()}
        else if(s.mobileCart){s.mobileCart=false;syncCart()}
      }
      if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"){
        event.preventDefault();document.querySelector("[data-ezreg-search]")?.focus()
      }
    });
    function openPayment(order){
      initTenant();
      if(!order||order.status==="paid"||order.paid)return;
      checkout?.begin(order);
      navigate("pos");
    }
    return {render,mount,open,openPayment};
  };
})();
