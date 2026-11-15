/* EZ Thing V6 — reusable merchant POS modifiers (sizes, toppings, inventory links). */
(() => {
  "use strict";
  let deps;
  let draft = null;
  const uid = () => (globalThis.crypto?.randomUUID?.() || "m"+Date.now()+Math.random().toString(36).slice(2));
  const get = () => deps.getBusiness();
  const E = v => deps.E(v ?? "");
  const fmt = amount => deps.V(amount || 0);
  const t = (vi,en) => window.EZI18N?.language?.()==="en" ? en : vi;
  const product = id => deps.getProducts().find(x=>x.id===id);
  const button = (act,label,g="",o="") =>
    '<button type="button" class="btn sm secondary" data-m6-action="'+act+'" data-group="'+E(g)+'" data-option="'+E(o)+'">'+label+'</button>';
  function newOption(name=""){
    return {id:uid(),name,price_vnd:0,inventory_product_id:null,inventory_quantity:1};
  }
  function newGroup(kind){
    return kind==="size"
      ? {id:uid(),name:"Size",min_select:1,max_select:1,options:[newOption("M"),newOption("L")]}
      : {id:uid(),name:"Topping",min_select:0,max_select:2,options:[newOption("Trân châu"),newOption("Thạch")]};
  }
  function collect(){
    if(!draft)return;
    document.querySelectorAll('#ez-modifier-form [data-m6-group-index]').forEach(el=>{
      const group=draft.groups[Number(el.dataset.m6GroupIndex)];
      if(!group)return;
      group.name=el.querySelector('[data-m6-group-name]')?.value.trim()||"";
      group.min_select=Number(el.querySelector('[data-m6-min]')?.value||0);
      group.max_select=Number(el.querySelector('[data-m6-max]')?.value||1);
      el.querySelectorAll('[data-m6-option-index]').forEach(opt=>{
        const entry=group.options[Number(opt.dataset.m6OptionIndex)];
        if(!entry)return;
        entry.name=opt.querySelector('[data-m6-option-name]')?.value.trim()||"";
        entry.price_vnd=Number(opt.querySelector('[data-m6-price]')?.value||0);
        entry.inventory_product_id=opt.querySelector('[data-m6-ingredient]')?.value||null;
        entry.inventory_quantity=Number(opt.querySelector('[data-m6-ingredient-qty]')?.value||1);
      });
    });
  }
  function draw(){
    if(!draft)return;
    const inv=deps.getProducts().filter(p=>p.track_stock&&p.active&&p.id!==draft.productId);
    const html='<form id="ez-modifier-form" class="m6-editor">'
      +'<p class="subtle">'+t('Tạo nhóm lựa chọn cho từng sản phẩm; giá phụ thu được tính trên máy chủ.','Create product options; surcharges are calculated on the server.')+'</p>'
      +draft.groups.map((g,gi)=>'<section class="m6-group" data-m6-group-index="'+gi+'">'
        +'<div class="m6-head"><strong>'+t('Nhóm lựa chọn','Modifier group')+' '+(gi+1)+'</strong>'
        +button('remove-group',t('Xóa nhóm','Remove'),gi)+'</div>'
        +'<div class="m6-grid"><label>'+t('Tên nhóm','Group name')+'<input data-m6-group-name required maxlength="90" value="'+E(g.name)+'"></label>'
        +'<label>'+t('Chọn ít nhất','Minimum')+'<input data-m6-min type="number" required min="0" max="20" value="'+g.min_select+'"></label>'
        +'<label>'+t('Chọn tối đa','Maximum')+'<input data-m6-max type="number" required min="1" max="'+g.options.length+'" value="'+g.max_select+'"></label></div>'
        +'<div class="m6-options">'+g.options.map((o,oi)=>'<div class="m6-option" data-m6-option-index="'+oi+'">'
          +'<label>'+t('Tên lựa chọn','Option')+'<input data-m6-option-name required maxlength="90" value="'+E(o.name)+'"></label>'
          +'<label>'+t('Phụ thu (đ)','Extra price (VND)')+'<input data-m6-price type="number" min="0" max="2000000000" required value="'+o.price_vnd+'"></label>'
          +'<label>'+t('Trừ kho nguyên liệu (tùy chọn)','Ingredient stock (optional)')+'<select data-m6-ingredient><option value="">'+t('Không liên kết','Not linked')+'</option>'
          +inv.map(p=>'<option value="'+E(p.id)+'"'+(p.id===o.inventory_product_id?' selected':'')+'>'+E(p.name)+'</option>').join('')+'</select></label>'
          +'<label>'+t('Định lượng tồn kho','Units deducted')+'<input data-m6-ingredient-qty type="number" min="1" max="1000" required value="'+o.inventory_quantity+'"></label>'
          +button('remove-option','✕',gi,oi)
          +'</div>').join('')+'</div>'
        +button('add-option','＋ '+t('Thêm lựa chọn','Add option'),gi)
        +'</section>').join('')
      +'<div class="m6-add">'+button('add-size','＋ Size')+button('add-topping','＋ Topping')+'</div>'
      +'<div class="subtle">'+t('Ví dụ: Trà Sữa 35.000đ + Trân châu 5.000đ = 40.000đ. Nguyên liệu được trừ kho nếu được liên kết.','Example: Milk tea 35,000 + pearls 5,000 = 40,000 VND. Linked ingredients reduce stock.')+'</div>'
      +'<div class="modal-footer"><button type="button" class="btn secondary" data-action="close-modal">'+t('Hủy','Cancel')+'</button><button class="btn" type="submit">'+t('Lưu Size / Topping','Save options')+'</button></div>'
      +'</form>';
    deps.modal(t("Tùy chỉnh sản phẩm: ","Product options: ")+(product(draft.productId)?.name||""),html,true);
  }
  async function openEditor(productId){
    if(!get()?.id||!product(productId))return;
    const result=await deps.api('/businesses/'+encodeURIComponent(get().id)+'/products/'+encodeURIComponent(productId)+'/modifiers');
    draft={productId, businessId:get().id, revision:result.revision, groups:result.groups||[]};
    draw();
  }
  async function save(form){
    if(!draft||get()?.id!==draft.businessId)return;
    collect();
    const submit=form.querySelector('[type=submit]');
    if(submit)submit.disabled=true;
    try{
      const result=await deps.api('/businesses/'+encodeURIComponent(draft.businessId)+'/products/'+encodeURIComponent(draft.productId)+'/modifiers',{
        method:'PUT',body:JSON.stringify({expected_revision:draft.revision,groups:draft.groups})
      });
      draft.revision=result.revision;
      draft=null;
      deps.closeModal();
      await deps.refresh();
      deps.toast(t('Đã lưu nhóm Size / Topping','Saved product options'));
    }catch(err){
      deps.toast(err.message||t('Không thể lưu','Unable to save'),true);
      if(submit)submit.disabled=false;
    }
  }
  function lineOptions(p){
    if(!p?.modifier_groups?.length)return '';
    return '<div class="m6-pos-groups">'+p.modifier_groups.map(g=>
      '<fieldset class="m6-pos-group" data-pos-group="'+E(g.id)+'" data-pos-min="'+g.min_select+'" data-pos-max="'+g.max_select+'">'
      +'<legend>'+E(g.name)+' <small>'+(g.min_select?t('Bắt buộc','Required')+' · ':'')+(g.max_select===1?t('Chọn 1','Choose 1'):t('Tối đa','Up to')+' '+g.max_select)+'</small></legend>'
      +(g.min_select===0&&g.max_select===1?'<label><input type="radio" name="pos_'+E(g.id)+'_'+uid()+'" value="" checked> '+t('Không chọn','None')+'</label>':'')
      +g.options.map(o=>'<label><input data-pos-modifier type="'+(g.max_select===1?'radio':'checkbox')+'" '
        +'name="posgroup_'+E(g.id)+'" value="'+E(o.id)+'"> '+E(o.name)+' <small>'+(o.price_vnd?'+'+fmt(o.price_vnd):t('Miễn phí','Free'))+'</small></label>').join('')
      +'</fieldset>').join('')+'</div>';
  }
  function updateLine(row){
    const p=product(row.querySelector('select[name=product_id]')?.value);
    const slot=row.querySelector('.m6-pos-slot');
    if(slot)slot.innerHTML=lineOptions(p);
  }
  function selectedLine(row){
    return [...row.querySelectorAll('[data-pos-modifier]:checked')].map(x=>x.value);
  }
  function lineExtra(row){
    const p=product(row.querySelector('select[name=product_id]')?.value);
    const selected=selectedLine(row);
    return (p?.modifier_groups||[]).flatMap(g=>g.options)
      .filter(o=>selected.includes(o.id)).reduce((sum,o)=>sum+o.price_vnd,0);
  }
  function init(options){deps=options;return {openEditor,updateLine,selectedLine,lineExtra};}
  document.addEventListener('click',e=>{
    const button=e.target.closest('[data-m6-action]');
    if(!button||!draft)return;
    e.preventDefault();
    collect();
    const action=button.dataset.m6Action,gi=Number(button.dataset.group),oi=Number(button.dataset.option);
    if(action==='add-size'||action==='add-topping'){
      if(draft.groups.length>=8){deps.toast(t('Tối đa 8 nhóm','Maximum 8 groups'),true);return;}
      draft.groups.push(newGroup(action==='add-size'?'size':'topping'));
    }else if(action==='remove-group'){
      draft.groups.splice(gi,1);
    }else if(action==='add-option'){
      if(draft.groups[gi].options.length>=20){deps.toast(t('Tối đa 20 lựa chọn','Maximum 20 options'),true);return;}
      draft.groups[gi].options.push(newOption());
    }else if(action==='remove-option'){
      const group=draft.groups[gi];
      if(group.options.length<=1){deps.toast(t('Nhóm cần ít nhất 1 lựa chọn','Keep at least one option'),true);return;}
      group.options.splice(oi,1);
      group.max_select=Math.min(group.max_select,group.options.length);
      group.min_select=Math.min(group.min_select,group.max_select);
    }
    draw();
  });
  document.addEventListener('submit',e=>{
    if(e.target.id==='ez-modifier-form'){
      e.preventDefault();e.stopImmediatePropagation();save(e.target);
    }
  },true);
  document.addEventListener('change',e=>{
    const el=e.target;
    if(!el.matches('[data-pos-modifier]')||el.type!=='checkbox'||!el.checked)return;
    const group=el.closest('[data-pos-group]');
    if(!group)return;
    const inputs=[...group.querySelectorAll('[data-pos-modifier]:checked')];
    if(inputs.length>Number(group.dataset.posMax)){
      el.checked=false;
      deps?.toast(t('Đã đạt số topping tối đa','Maximum toppings selected'),true);
    }
  },true);
  window.EZMerchantModifiers={init};
})();
