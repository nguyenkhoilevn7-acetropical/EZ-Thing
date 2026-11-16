/* EZ Thing operational printouts. Preview works without installed hardware. */
(() => {
  'use strict';
  function init({api,E,modal,closeModal,toast,getState}) {
    const labels = {
      prebill:'Phiếu tạm tính',
      receipt:'Bản sao thanh toán',
      packing:'Phiếu kiểm đồ',
      cup_label:'Tem dán ly'
    };
    let current=null, requestSerial=0;
    const getBid=()=>getState().business?.id;
    const getOrder=id=>(getState().cache.orderDashboard?.orders||
      getState().cache.orders||[]).find(x=>x.id===id);
    const types=order=>{
      const options=order.status==='paid'?['receipt','packing']:
        order.status==='open'?['prebill','packing']:[];
      if(getState().business?.industry==='fnb'&&options.length)options.push('cup_label');
      return options;
    };
    const uuid=()=>globalThis.crypto?.randomUUID?.()||
      'print-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
    async function open(orderId,kind) {
      const order=getOrder(orderId);
      if(!order)return toast('Không tìm thấy đơn hàng để in',true);
      const options=types(order);
      if(!options.length)return toast('Đơn đã hủy không thể in chứng từ',true);
      const selected=options.includes(kind)?kind:options[0];
      const bid=getBid(),serial=++requestSerial;
      let result;
      try {
        result=await api('/businesses/'+encodeURIComponent(bid)+
          '/printers/documents/'+encodeURIComponent(orderId)+
          '/preview?kind='+encodeURIComponent(selected));
      }catch(error){toast(error.message,true);return}
      if(serial!==requestSerial||bid!==getBid())return;
      current={...result,requestId:
        current?.order_id===orderId&&current.kind===selected?current.requestId:uuid()};
      const buttons=options.map(key=>
        '<button type="button" class="btn sm '+(key===selected?'':'secondary')+
        '" data-ezdoc-action="kind" data-kind="'+E(key)+'" aria-pressed="'+
        (key===selected)+'">'+E(labels[key])+'</button>').join('');
      const devices=result.available_devices||[];
      const deviceOptions=devices.map(p=>
        '<option value="'+E(p.id)+'">'+E(p.name)+' · '+E(p.station)+'</option>').join('');
      const text=(result.documents||[]).map(x=>x.content).join('\n\n--- NEXT LABEL ---\n\n');
      const pane='<div class="ez-doc-modal" id="ez-print-document">'+
        '<p class="subtle">Đơn #'+E(orderId.slice(0,8).toUpperCase())+
        ' · Chứng từ vận hành, không phải hóa đơn điện tử thuế.</p>'+
        '<div class="ez-doc-kind">'+buttons+'</div>'+
        '<div class="ez-doc-summary">'+(result.documents||[]).length+' phiếu · Bản xem trước</div>'+
        '<pre class="ez-doc-receipt" id="ez-document-print-content">'+E(text)+'</pre>'+
        '<div class="ez-doc-controls"><label>Máy in đích<select id="ez-document-printer" '+
          (devices.length?'':'disabled')+'>'+deviceOptions+'</select></label>'+
        (devices.length?'':'<p class="subtle">Chưa có máy phù hợp. Có thể in bằng trình duyệt trước.</p>')+
        '</div><div class="modal-footer">'+
        '<button type="button" class="btn secondary" data-ezdoc-action="close">Đóng</button>'+
        '<button type="button" class="btn secondary" data-ezdoc-action="browser">In trình duyệt</button>'+
        '<button type="button" class="btn" data-ezdoc-action="send" '+
        (devices.length?'':'disabled')+'>Gửi đến máy in</button>'+
        '</div></div>';
      const existing=document.getElementById('ez-print-document');
      if(existing)existing.outerHTML=pane;
      else modal('In chứng từ #'+orderId.slice(0,8).toUpperCase(),pane,true);
    }
    async function send(button) {
      if(!current||button.disabled)return;
      const deviceId=document.getElementById('ez-document-printer')?.value;
      if(!deviceId)return toast('Chưa có máy in phù hợp',true);
      button.disabled=true;
      try {
        const bid=getBid();
        const result=await api('/businesses/'+encodeURIComponent(bid)+
          '/printers/documents/'+encodeURIComponent(current.order_id)+'/print',{
          method:'POST',body:JSON.stringify({
            kind:current.kind,device_id:deviceId,request_id:current.requestId
          })
        });
        toast('Đã xếp hàng '+result.document_count+' phiếu; vui lòng kiểm tra máy in.');
        closeModal();current=null;
      }catch(error){toast(error.message,true);button.disabled=false}
    }
    document.addEventListener('click',event=>{
      const button=event.target.closest('button[data-ezdoc-action]');
      if(!button||!document.getElementById('ez-print-document')?.contains(button))return;
      event.preventDefault();
      const action=button.dataset.ezdocAction;
      if(action==='kind'&&current)open(current.order_id,button.dataset.kind);
      else if(action==='send')send(button);
      else if(action==='browser')window.print();
      else if(action==='close'){current=null;closeModal()}
    });
    return {open};
  }
  window.EZPrintDocuments=init;
})();
