/* EZ Thing manual POS checkout, separated from the register cart renderer.
 * No gateway calls. Card/wallet remain disabled pending a verified provider.
 * The SaleOrder is created before manual collection and remains open on failure.
 */
(() => {
  "use strict";
  window.EZCashierCheckout = function init({api,E,V,toast,getBusiness,getTotal,createOrder,onPaid}) {
    const T=(vi,en)=>window.EZI18N?.language?.()==="en"?en:vi;
    const uid=()=>globalThis.crypto?.randomUUID?.()||
      "tender-"+Date.now().toString(36)+"-"+Math.random().toString(36).slice(2);
    let state={open:false,order:null,method:"cash",cash:"",reference:"",
      confirmed:false,requestId:uid(),busy:false,previewTotal:0};
    const fmt=n=>V(Number(n)||0);
    const due=()=>Number(state.order?.total_vnd??state.previewTotal)||0;
    const cash=()=>/^\d+$/.test(String(state.cash).trim())?Number(state.cash):NaN;
    const methods=[["cash","💵",T("Tiền mặt","Cash"),""],
      ["bank_transfer","🏦",T("Chuyển khoản","Bank transfer"),T("Thủ công","Manual")]];
    function valid(){
      if(!state.open||!state.confirmed||state.busy||!navigator.onLine)return false;
      return state.method==="bank_transfer"||
        (Number.isSafeInteger(cash())&&cash()>=due()&&cash()<=9_000_000_000_000);
    }
    function reset(){
      state={open:false,order:null,method:"cash",cash:"",reference:"",
        confirmed:false,requestId:uid(),busy:false,previewTotal:0};
      paint();
    }
    function begin(order=null){
      if(state.busy)return;
      state.open=true;state.order=order?{id:order.id,total_vnd:order.total_vnd}:null;
      state.previewTotal=order?Number(order.total_vnd):getTotal();
      state.method="cash";state.cash=String(state.previewTotal);
      state.reference="";state.confirmed=false;state.requestId=uid();
      paint();
    }
    function render(){
      if(!state.open)return "";
      const amount=due(),paid=cash();
      const options=[amount,Math.ceil(amount/50000)*50000,
        Math.ceil(amount/100000)*100000,Math.ceil(amount/200000)*200000]
        .filter((v,i,a)=>v<=9_000_000_000_000&&a.indexOf(v)===i);
      return '<div class="ezpay-backdrop" data-ezpay="close"></div>'+
        '<section class="ezpay-modal" role="dialog" aria-modal="true" aria-labelledby="ezpay-title">'+
        '<header class="ezpay-head"><div><small>EZ THING · CHECKOUT</small>'+
        '<h3 id="ezpay-title">'+T("Thanh toán","Payment")+'</h3>'+
        '<span>'+(state.order?"#"+E(state.order.id.slice(0,8).toUpperCase())+" · ":"")+
        T("Thu ngân tại quầy","Counter checkout")+'</span></div>'+
        '<button type="button" data-ezpay="close" aria-label="'+T("Đóng","Close")+'">✕</button></header>'+
        '<div class="ezpay-content"><div class="ezpay-total"><span>'+
        T("Số tiền cần thanh toán","Amount due")+'</span><strong>'+fmt(amount)+'</strong></div>'+
        '<h4>'+T("Chọn phương thức thanh toán","Payment method")+'</h4>'+
        '<div class="ezpay-methods">'+methods.map(([value,emoji,label,desc])=>
          '<button type="button" data-ezpay="method" data-value="'+value+'" class="'+
          (state.method===value?"selected":"")+'" aria-pressed="'+(state.method===value)+'">'+
          '<span>'+emoji+'</span><strong>'+label+'</strong><small>'+desc+'</small></button>').join("")+
        '<button type="button" disabled title="'+T("Chưa kết nối cổng thanh toán","Gateway not connected")+
        '"><span>💳</span><strong>'+T("Thẻ / Ví","Card / Wallet")+'</strong><small>'+
        T("Chưa kết nối","Unavailable")+'</small></button></div>'+
        (state.method==="cash"?
          '<div class="ezpay-inputs"><label>'+T("Tiền khách đưa (VND)","Cash tendered (VND)")+
          '<input data-ezpay-cash type="number" min="'+amount+'" max="9000000000000" inputmode="numeric" step="1" value="'+E(state.cash)+'"></label>'+
          '<div class="ezpay-quick">'+options.map(v=>'<button type="button" data-ezpay="quick" data-value="'+v+'">'+fmt(v)+'</button>').join("")+
          '</div><div class="ezpay-change"><span id="ezpay-change-label">'+
          ((Number.isSafeInteger(paid)&&paid>=amount)?T("Tiền thừa","Change due"):T("Còn thiếu","Amount missing"))+
          '</span><strong id="ezpay-change-amount">'+fmt(Number.isSafeInteger(paid)?Math.abs(paid-amount):amount)+'</strong></div></div>':
          '<div class="ezpay-bank"><p>⚠ '+T(
            "Chưa kết nối ngân hàng. Chỉ xác nhận nếu đã kiểm tra tiền vào tài khoản người bán.",
            "No bank connection. Confirm only after independently checking that funds arrived.")+
          '</p><label>'+T("Mã giao dịch ngân hàng (không bắt buộc)","Bank reference (optional)")+
          '<input data-ezpay-reference maxlength="120" value="'+E(state.reference)+
          '" placeholder="'+T("Mã giao dịch / ghi chú","Transaction reference / note")+'"></label></div>')+
        '<label class="ezpay-confirm"><input data-ezpay-confirm type="checkbox" '+
        (state.confirmed?"checked":"")+'><span>'+
        (state.method==="cash"?
          T("Tôi xác nhận đã nhận đủ tiền mặt.","I confirm receiving the cash in full."):
          T("Tôi đã kiểm tra tài khoản và xác nhận nhận đủ tiền chuyển khoản.",
            "I independently checked the bank account and confirm receipt."))+
        '</span></label>'+
        '<p class="ezpay-disclaimer">'+T(
          "Xác nhận sẽ khóa đơn, cập nhật doanh thu và tạo phiếu in nếu đã cấu hình máy in. Không tự đối soát ngân hàng.",
          "Confirmation closes this check, records revenue and queues printing if configured. No bank verification.")+
        '</p></div><footer class="ezpay-actions">'+
        '<button type="button" data-ezpay="close">'+T("Quay lại","Back")+'</button>'+
        '<button type="button" data-ezpay="confirm" id="ezpay-submit" '+(valid()?"":"disabled")+'>'+
        (state.busy?T("Đang xử lý...","Processing..."):T("Xác nhận đã nhận tiền","Confirm funds received"))+
        '<strong>'+fmt(amount)+'</strong></button></footer></section>';
    }
    function paint(){
      const host=document.getElementById("ezreg-payment-mount");
      if(host)host.innerHTML=render();
    }
    function sync(){
      const submit=document.getElementById("ezpay-submit");
      if(submit)submit.disabled=!valid();
      const label=document.getElementById("ezpay-change-label");
      const value=document.getElementById("ezpay-change-amount");
      if(state.method==="cash"){
        if(label)label.textContent=Number.isSafeInteger(cash())&&cash()>=due()?
          T("Tiền thừa","Change due"):T("Còn thiếu","Amount missing");
        if(value)value.textContent=fmt(Number.isSafeInteger(cash())?Math.abs(cash()-due()):due());
      }
      const confirm=document.querySelector("[data-ezpay-confirm]");
      if(confirm)confirm.checked=state.confirmed;
    }
    async function settle(){
      if(!valid())return;
      const originalTotal=due();
      if(!state.order){
        const created=await createOrder();
        if(!created)return;
        state.order={id:created.id,total_vnd:created.total_vnd};
        if(Number(created.total_vnd)!==originalTotal){
          state.cash=String(created.total_vnd);
          state.confirmed=false;
          paint();
          toast(T("Tổng tiền server khác dự kiến. Kiểm tra và xác nhận lại.",
            "Server total differs; review and reconfirm before collecting."),true);
          return;
        }
      }
      if(!valid())return;
      const payload={
        request_id:state.requestId,method:state.method,confirmed:true,
        expected_total_vnd:state.order.total_vnd,
        cash_received_vnd:state.method==="cash"?cash():null,
        transfer_reference:state.method==="bank_transfer"?state.reference.trim():""
      };
      state.busy=true;paint();
      try{
        const response=await api("/businesses/"+encodeURIComponent(getBusiness().id)+
          "/pos-payments/"+encodeURIComponent(state.order.id),{
          method:"POST",body:JSON.stringify(payload)
        });
        reset();
        // Settlement succeeded before any UI/network refresh.
        try{await onPaid(response)}catch(e){
          toast(T("Thanh toán đã lưu. Danh sách đơn chưa làm mới.",
            "Payment saved; order list refresh failed."),true);
        }
        toast(T("Đã ghi nhận thanh toán thành công","Payment recorded successfully"));
      }catch(error){
        // Keep requestId + order if network response is lost: retry is idempotent.
        toast(error.message||T("Không thể ghi nhận thanh toán","Payment could not be recorded"),true);
      }finally{state.busy=false;paint()}
    }
    document.addEventListener("click",event=>{
      const btn=event.target.closest("[data-ezpay]");
      if(!btn||!document.getElementById("ez-register")?.contains(btn))return;
      event.preventDefault();event.stopPropagation();
      const action=btn.dataset.ezpay;
      if(action==="close"){if(!state.busy)reset()}
      else if(action==="method"){
        state.method=btn.dataset.value;state.confirmed=false;paint();
      }else if(action==="quick"){
        state.cash=btn.dataset.value;state.confirmed=false;paint();
      }else if(action==="confirm")settle();
    },true);
    document.addEventListener("input",event=>{
      if(!document.getElementById("ez-register"))return;
      if(event.target.matches("[data-ezpay-cash]")){
        state.cash=event.target.value;state.confirmed=false;sync();
      }
      if(event.target.matches("[data-ezpay-reference]"))
        state.reference=event.target.value;
    },true);
    document.addEventListener("change",event=>{
      if(event.target.matches("[data-ezpay-confirm]")){
        state.confirmed=event.target.checked;sync();
      }
    },true);
    document.addEventListener("keydown",event=>{
      if(event.key==="Escape"&&state.open&&!state.busy){
        event.stopImmediatePropagation();reset();
      }
    },true);
    return {begin,render,paint,reset};
  };
})();
