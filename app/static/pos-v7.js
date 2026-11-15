/* EZ Thing V7 — edit existing open POS checks without rerendering the page shell. */
(() => {
 "use strict";
 let deps;
 let ticket=null;
 const uid=()=>globalThis.crypto?.randomUUID?.()||'request-'+Date.now()+'-'+Math.random().toString(36).slice(2);
 const E=v=>deps.E(v==null?'':v);
 const V=v=>deps.V(v||0);
 const T=(vi,en)=>window.EZI18N?.language?.()==='en'?en:vi;
 const business=()=>deps.getBusiness();
 const products=()=>deps.getProducts().filter(x=>x.active);
 const product=id=>products().find(x=>x.id===id);
 const uri=path=>'/businesses/'+encodeURIComponent(business().id)+'/pos/'+path;
 const role=()=>business()?.role||'staff';
 const canDiscount=()=>['owner','manager'].includes(role());
 const lineRow=(item={})=>{
   const options=products().map(p=>'<option value="'+E(p.id)+'"'+(p.id===item.product_id?' selected':'')+' data-price="'+p.price_vnd+'">'+E(p.name)+' · '+V(p.price_vnd)+'</option>').join('');
   return '<div class="v7-line"><select name="product_id" aria-label="'+T('Sản phẩm','Product')+'">'+options+'</select>'
     +'<input name="quantity" type="number" min="1" max="1000" required value="'+(item.quantity||1)+'" aria-label="'+T('Số lượng','Quantity')+'">'
     +'<button type="button" class="btn sm secondary" data-pos7-action="remove-line">'+T('Xóa','Remove')+'</button>'
     +'<div class="m6-pos-slot"></div></div>';
 };
 function fillLine(row,item){
   if(!row)return;
   deps.modifiers?.updateLine(row);
   for(const modifier of item.modifiers||[]){
     const input=[...row.querySelectorAll('[data-pos-modifier]')].find(el=>el.value===modifier.option_id);
     if(input)input.checked=true;
   }
 }
 function chosen(row){
   return deps.modifiers?.selectedLine(row)||[];
 }
 function extra(row){
   return deps.modifiers?.lineExtra(row)||0;
 }
 function estimate(form){
   const subtotal=[...form.querySelectorAll('.v7-line')].reduce((sum,row)=>{
     const p=product(row.querySelector('[name=product_id]')?.value);
     const qty=Number(row.querySelector('[name=quantity]')?.value||0);
     return sum+((p?.price_vnd||0)+extra(row))*qty;
   },0);
   const discount=Number(form.querySelector('[name=discount_vnd]')?.value||0);
   const tip=Number(form.querySelector('[name=tip_vnd]')?.value||0);
   const total=subtotal-discount+tip;
   const output=form.querySelector('#pos-v7-total');
   if(output)output.textContent=V(total);
   const warning=form.querySelector('#pos-v7-warning');
   if(warning)warning.textContent=discount>subtotal?T('Giảm giá vượt tiền món','Discount exceeds subtotal'):'';
 }
 async function load(oid){
   const bid=business()?.id;
   if(!bid)throw Error('No business selected');
   ticket=await deps.api('/businesses/'+encodeURIComponent(bid)+'/pos/orders/'+encodeURIComponent(oid));
   if(ticket.status!=='open')throw Error(T('Đơn không còn cho phép sửa','Check is no longer editable'));
   return ticket;
 }
 function renderEditor(){
   if(!ticket)return;
   const all=products();
   const lines=ticket.items||[];
   const markup='<form id="pos-v7-editor" class="v7-editor" data-order-id="'+E(ticket.id)+'">'
     +'<p class="subtle">'+T('Chỉ sửa được đơn chưa thanh toán và chưa chuyển bếp/giao vận. Khi lưu, tất cả món được định giá lại theo menu hiện tại.','Only open, unsubmitted tickets can be edited. Saving reprices all items using the current menu.')+'</p>'
     +'<div class="v7-lines">'+lines.map(lineRow).join('')+'</div>'
     +'<button type="button" class="btn sm secondary" data-pos7-action="add-line">＋ '+T('Thêm món','Add item')+'</button>'
     +'<div class="v7-adjustments"><label>'+T('Giảm giá (đ)','Discount (VND)')+'<input type="number" name="discount_vnd" min="0" max="2000000000" value="'+ticket.discount_vnd+'" '+(canDiscount()?'':'disabled')+'></label>'
     +'<label>'+T('Tiền tip (đ)','Tip (VND)')+'<input type="number" name="tip_vnd" min="0" max="2000000000" value="'+ticket.tip_vnd+'" '+(canDiscount()?'':'disabled')+'></label></div>'
     +'<label class="v7-note">'+T('Ghi chú','Note')+'<textarea name="note" maxlength="300" rows="2">'+E(ticket.note||'')+'</textarea></label>'
     +'<div class="v7-total"><strong>'+T('Tạm tính mới','Estimated total')+'</strong><strong id="pos-v7-total"></strong></div>'
     +'<p id="pos-v7-warning" class="v7-error" role="status"></p>'
     +'<p class="subtle">'+T('Không thay đổi hóa đơn đã thanh toán. Hoàn tiền/tách-gộp hóa đơn cần quy trình riêng.','Paid checks are immutable. Refund and split/merge require separate workflows.')+'</p>'
     +'<div class="modal-footer"><button type="button" class="btn secondary" data-action="close-modal">'+T('Đóng','Close')+'</button>'
     +'<button class="btn" type="submit">'+T('Lưu thay đổi','Save changes')+'</button></div></form>';
   deps.modal(T('Chỉnh sửa đơn #','Edit check #')+ticket.id.slice(0,8).toUpperCase(),markup,true);
   const rows=[...document.querySelectorAll('#pos-v7-editor .v7-line')];
   rows.forEach((row,i)=>fillLine(row,lines[i]));
   estimate(document.querySelector('#pos-v7-editor'));
 }
 async function openEditor(oid){
   await load(oid);
   if(!products().length)throw Error(T('Không có sản phẩm đang bán','No active products'));
   renderEditor();
 }
 async function openMove(oid){
   await load(oid);
   if(!canDiscount())throw Error(T('Cần quyền quản lý','Manager role required'));
   const tables=deps.getTables().filter(t=>t.branch_id===ticket.branch_id);
   const options='<option value="">'+T('Mang đi / không gắn bàn','Takeaway / no table')+'</option>'
     +tables.map(t=>'<option value="'+E(t.id)+'"'+(t.id===ticket.table_id?' selected':'')+'>'
       +E(t.label)+(t.occupied?' · '+T('Đang phục vụ','Occupied'):'')+'</option>').join('');
   deps.modal(T('Chuyển bàn #','Move check #')+ticket.id.slice(0,8).toUpperCase(),
     '<form id="pos-v7-move"><p class="subtle">'+T('Chuyển bàn trong cùng chi nhánh. Bàn có đơn khác vẫn giữ các hóa đơn tách biệt; không tự gộp.','Move within the same branch. An occupied table keeps independent checks; nothing is merged.')+'</p>'
     +'<div class="formfield"><label>'+T('Bàn mới','Destination table')+'</label><select name="table_id">'+options+'</select></div>'
     +'<div class="modal-footer"><button class="btn secondary" type="button" data-action="close-modal">'+T('Đóng','Close')+'</button>'
     +'<button class="btn" type="submit">'+T('Xác nhận chuyển bàn','Confirm move')+'</button></div></form>');
 }
 async function submitEditor(form){
   if(!ticket||!form.querySelector('.v7-line'))throw Error(T('Đơn phải có ít nhất một món','Check needs at least one item'));
   const btn=form.querySelector('[type=submit]');
   if(btn.disabled)return;
   btn.disabled=true;
   try{
     const lines=[...form.querySelectorAll('.v7-line')].map(row=>({
       product_id:row.querySelector('[name=product_id]').value,
       quantity:Number(row.querySelector('[name=quantity]').value),
       selected_options:chosen(row)
     }));
     const result=await deps.api(uri('orders/'+encodeURIComponent(ticket.id)),{
       method:'PUT',body:JSON.stringify({
         request_id:form.dataset.requestId||(form.dataset.requestId=uid()),
         expected_revision:ticket.revision,lines,
         discount_vnd:Number(form.querySelector('[name=discount_vnd]').value||0),
         tip_vnd:Number(form.querySelector('[name=tip_vnd]').value||0),
         note:form.querySelector('[name=note]').value
       })
     });
     ticket=result;
     deps.closeModal();
     await deps.invalidateAndRefresh();
     deps.toast(T('Đã cập nhật đơn và đối soát kho','Check updated and inventory reconciled'));
   }catch(err){
     deps.toast(err.message||'Unable to update check',true);
     if(btn)btn.disabled=false;
   }
 }
 async function submitMove(form){
   const button=form.querySelector('[type=submit]');
   if(button.disabled)return;
   button.disabled=true;
   try{
     const result=await deps.api(uri('orders/'+encodeURIComponent(ticket.id)+'/move-table'),{
       method:'POST',body:JSON.stringify({
         request_id:form.dataset.requestId||(form.dataset.requestId=uid()),
         expected_revision:ticket.revision,table_id:form.querySelector('[name=table_id]').value||null
       })
     });
     ticket=result;
     deps.closeModal();
     await deps.invalidateAndRefresh();
     deps.toast(T('Đã chuyển bàn','Check moved'));
   }catch(err){
     deps.toast(err.message||'Unable to move check',true);
     button.disabled=false;
   }
 }
 function init(options){deps=options;return {openEditor,openMove};}
 document.addEventListener('click',e=>{
   const b=e.target.closest('[data-pos7-action]');
   if(!b)return;
   const form=b.closest('#pos-v7-editor');
   if(!form)return;
   e.preventDefault();
   const op=b.dataset.pos7Action;
   if(op==='add-line'){
     const list=form.querySelector('.v7-lines');
     list.insertAdjacentHTML('beforeend',lineRow({product_id:products()[0]?.id}));
     fillLine(list.lastElementChild,{});
   }else if(op==='remove-line'){
     if(form.querySelectorAll('.v7-line').length<=1){
       deps.toast(T('Đơn cần ít nhất một món','Check needs at least one item'),true);return;
     }
     b.closest('.v7-line')?.remove();
   }
   estimate(form);
 });
 document.addEventListener('change',e=>{
   const row=e.target.closest('#pos-v7-editor .v7-line');
   if(row&&e.target.matches('[name=product_id]'))fillLine(row,{});
   const form=e.target.closest('#pos-v7-editor');
   if(form)estimate(form);
 },true);
 document.addEventListener('input',e=>{
   const form=e.target.closest('#pos-v7-editor');
   if(form)estimate(form);
 },true);
 document.addEventListener('submit',e=>{
   if(e.target.id==='pos-v7-editor'){
     e.preventDefault();e.stopImmediatePropagation();
     submitEditor(e.target);
   }
   if(e.target.id==='pos-v7-move'){
     e.preventDefault();e.stopImmediatePropagation();
     submitMove(e.target);
   }
 },true);
 window.EZPOSV7={init};
})();
