/* Paperless POS: display a one-time receipt QR after payment.
   Tenant settings + member list share the existing authenticated back office. */
(() => {
  'use strict';
  const E=v=>String(v??'').replace(/[&<>"']/g,c=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
  let context=null;
  const close=()=>document.getElementById('ez-paperless-layer')?.remove();
  async function open({api,bid,orderId,toast}){
    if(document.body.dataset.ezWorkstationPreview==='true'){
      toast('Demo workstation: QR receipts require a real paid order.',true);return;
    }
    if(!navigator.onLine){toast('Connect to the internet to create the receipt QR',true);return}
    try{
      const result=await api('/businesses/'+encodeURIComponent(bid)+
        '/paperless/'+encodeURIComponent(orderId)+'/share',{method:'POST'});
      close();
      const layer=document.createElement('div');
      layer.id='ez-paperless-layer';
      layer.className='ez-paperless-backdrop';
      layer.setAttribute('role','presentation');
      layer.innerHTML='<section class="ez-paperless-dialog" role="dialog" aria-modal="true" aria-label="Digital receipt">'+
        '<div class="ez-paperless-head"><span>✓ PAYMENT CONFIRMED</span>'+
        '<button type="button" data-paperless="close" aria-label="Close digital receipt">✕</button></div>'+
        '<h2>Paperless Receipt</h2>'+
        '<p>Order #'+E(result.order_number)+'</p>'+
        '<img class="ez-paperless-qr" alt="Scan to save your purchase receipt" src="data:image/png;base64,'+
          E(result.qr_png_base64)+'">'+
        '<strong>Scan to get your receipt</strong>'+
        '<p>Show this QR to the customer. No paper, app or account required.</p>'+
        '<small>QR valid for '+Math.ceil(result.valid_for_seconds/60)+' minutes · One wallet only</small>'+
        '<div class="ez-paperless-actions">'+
        '<button type="button" class="ez-paperless-primary" data-paperless="copy">Copy Link</button>'+
        '<button type="button" data-paperless="close">Done</button></div></section>';
      layer.dataset.url=result.url;
      document.body.appendChild(layer);
    }catch(err){toast(err.message||'Unable to create digital receipt QR',true)}
  }
  function renderAdmin(){
    return '<section class="ez-paperless-admin" id="ez-paperless-admin">'+
      '<div class="ez-paperless-admin-head"><div><span>EZ THING · PAPERLESS</span>'+
      '<h2>Members & Digital Receipts</h2><p>Manage paper receipts and loyalty for this business only.</p></div>'+
      '<a href="/wallet" target="_blank" rel="noopener">Customer Wallet ↗</a></div>'+
      '<div id="ez-paperless-admin-body"><p>Loading member settings…</p></div></section>';
  }
  async function loadAdmin({api,bid,toast}){
    const root=document.getElementById('ez-paperless-admin-body');
    if(!root)return;
    context={api,bid,toast};
    try{
      const [settings,members]=await Promise.all([
        api('/businesses/'+encodeURIComponent(bid)+'/paperless/settings'),
        api('/businesses/'+encodeURIComponent(bid)+'/paperless/members')
      ]);
      root.innerHTML='<div class="ez-paperless-admin-grid">'+
        '<form class="ez-paperless-box" id="ez-paperless-settings">'+
        '<h3>Paperless Settings</h3>'+
        '<label class="ez-paperless-setting"><span>Paperless by default <small>Do not auto-print customer receipts. Kitchen/labels unaffected.</small></span>'+
        '<input type="checkbox" name="paperless_enabled" '+(settings.paperless_enabled?'checked':'')+'></label>'+
        '<label class="ez-paperless-setting"><span>Enable Loyalty Points <small>Points only for registered or linked customers.</small></span>'+
        '<input type="checkbox" name="loyalty_enabled" '+(settings.loyalty_enabled?'checked':'')+'></label>'+
        '<label class="ez-paperless-rate">Spend (VND) per 1 point'+
        '<input type="number" name="spend_vnd_per_point" min="1000" max="1000000" step="1000" required value="'+
        Number(settings.spend_vnd_per_point||10000)+'"></label>'+
        '<button type="submit">Save Settings</button></form>'+
        '<section class="ez-paperless-box"><h3>Members <span>'+members.length+'</span></h3>'+
        '<div class="ez-paperless-member-list">'+
        (members.length?members.map(m=>'<article><div><b>'+E(m.name)+'</b><small>'+
            E(m.phone)+' · '+E(m.member_code)+'</small></div><strong>'+Number(m.points||0)+' pt</strong></article>').join(''):
          '<p>No members yet. Customers can join from their receipt wallet using Google.</p>')+
        '</div></section></div>';
    }catch(err){
      root.innerHTML='<p class="ez-paperless-error">'+E(err.message||'Unable to load member settings')+'</p>';
    }
  }
  document.addEventListener('submit',async ev=>{
    if(ev.target.id!=='ez-paperless-settings'||!context)return;
    ev.preventDefault();
    const form=ev.target,btn=form.querySelector('[type="submit"]');
    btn.disabled=true;
    try{
      const values={
        paperless_enabled:form.elements.paperless_enabled.checked,
        loyalty_enabled:form.elements.loyalty_enabled.checked,
        spend_vnd_per_point:Number(form.elements.spend_vnd_per_point.value)
      };
      await context.api('/businesses/'+encodeURIComponent(context.bid)+'/paperless/settings',{
        method:'PUT',body:JSON.stringify(values)});
      context.toast('Paperless & Loyalty settings saved');
    }catch(err){context.toast(err.message,true)}
    finally{btn.disabled=false}
  });
  document.addEventListener('click',ev=>{
    const action=ev.target.closest('[data-paperless]')?.dataset.paperless;
    if(!action)return;
    if(action==='close'){close();return}
    if(action==='copy'){
      const value=document.getElementById('ez-paperless-layer')?.dataset.url;
      if(value)navigator.clipboard?.writeText(value).then(()=>{
        ev.target.textContent='Copied ✓';
      }).catch(()=>{ev.target.textContent='Copy unavailable'});
    }
  },true);
  document.addEventListener('keydown',ev=>{
    if(ev.key==='Escape')close();
  });
  window.EZPaperlessPOS={open,close,renderAdmin,loadAdmin};
})();
