/* Paperless guest wallet. No guest names, email, phone or password required.
   The receipt bearer comes only from location.hash, never an HTTP URL path. */
(() => {
  'use strict';
  const root=document.getElementById('wallet-content');
  const status=document.getElementById('wallet-status');
  if(!root||!status)return;
  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,ch=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[ch]));
  const money=value=>new Intl.NumberFormat('vi-VN').format(Number(value)||0)+'đ';
  const date=value=>new Date(value).toLocaleString('vi-VN',{
    year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'
  });
  let wallet={receipts:[],member:null,balances:[]},config={};
  let notice='',loading=false;
  async function request(path,method='GET',payload){
    const res=await fetch('/api'+path,{
      method,credentials:'same-origin',cache:'no-store',
      headers:{'Content-Type':'application/json'},
      body:payload===undefined?undefined:JSON.stringify(payload)
    });
    let body={};try{body=await res.json()}catch{}
    if(!res.ok)throw new Error(body.detail||'Request failed');
    return body;
  }
  function card(receipt){
    const items=(receipt.items||[]).map(item=>
      '<div class="wallet-item"><div><b>'+escapeHtml(item.name)+'</b> ×'+
      Number(item.quantity||0)+(item.modifiers?.length?
        '<small>'+item.modifiers.map(v=>escapeHtml(v.group_name||'')+
          ' '+escapeHtml(v.name||'')).join(' · ')+'</small>':'')+
      '</div><b>'+money(item.total_vnd)+'</b></div>').join('');
    return '<details class="wallet-receipt"><summary class="wallet-row" style="cursor:pointer">'+
      '<span><strong>#'+escapeHtml(receipt.order_number)+'</strong><small class="wallet-sub" style="display:block">'+
      escapeHtml(receipt.business_name)+' · '+escapeHtml(date(receipt.date))+'</small></span>'+
      '<span class="wallet-pill">✓ Paid</span></summary>'+
      '<div class="wallet-items">'+items+'</div>'+
      '<div class="wallet-row wallet-total"><span>Total</span><strong>'+money(receipt.total_vnd)+'</strong></div>'+
      '<p class="wallet-sub">'+escapeHtml(receipt.branch||'')+' · Purchase receipt (not VAT invoice)</p>'+
      '<div class="wallet-actions wallet-no-print"><button type="button" class="wallet-btn secondary" data-wallet-action="print">Print / Save PDF</button></div></details>';
  }
  function memberSection(){
    const m=wallet.member;
    if(!m){
      return '<section class="wallet-card wallet-no-print"><h2>⭐ Become a Member</h2>'+
        '<p>Keep receipts across devices and collect reward points. Optional — your guest receipts work without signing up.</p>'+
        (config.member_login_available?
          '<div id="wallet-google-button"></div>':
          '<p class="wallet-sub">Google member sign-in is not yet configured for this store.</p>')+
        '</section>';
    }
    if(!m.profile_complete){
      return '<section class="wallet-card wallet-no-print"><h2>Finish Member Registration</h2>'+
        '<p>Signed in as '+escapeHtml(m.email)+'. Just your name and phone number.</p>'+
        '<form id="wallet-profile-form">'+
        '<label class="wallet-field">Full Name<input name="name" maxlength="100" required minlength="2" autocomplete="name" value="'+escapeHtml(m.name)+'"></label>'+
        '<label class="wallet-field">Phone<input name="phone" maxlength="30" minlength="8" required autocomplete="tel" inputmode="tel" value="'+escapeHtml(m.phone)+'"></label>'+
        '<button class="wallet-btn" type="submit">Join Now</button></form>'+
        '<div class="wallet-actions"><button type="button" class="wallet-btn secondary" data-wallet-action="logout">Sign Out</button></div></section>';
    }
    return '<section class="wallet-card wallet-no-print"><div class="wallet-row">'+
      '<div><h2>⭐ Member Wallet</h2><p>'+escapeHtml(m.name)+' · '+escapeHtml(m.email)+'</p>'+
      '<span class="wallet-pill">Member #'+escapeHtml(m.id)+'</span></div></div>'+
      '<img class="wallet-member-qr" alt="Your Member QR Code" src="/api/wallet/member-qr">'+
      (wallet.balances.length?
        wallet.balances.map(b=>'<div class="wallet-row" style="border-top:1px solid #e4eeeb;padding:8px 0"><span>'+
          escapeHtml(b.business_name)+'</span><strong class="wallet-points">'+
          Number(b.points||0)+' points</strong></div>').join(''):
        '<p>Scan your digital receipt to start collecting points.</p>')+
      '<div class="wallet-actions"><button type="button" class="wallet-btn secondary" data-wallet-action="logout">Sign Out</button></div></section>';
  }
  function paint(){
    status.textContent=notice;
    const receipts=wallet.receipts||[];
    root.innerHTML=(notice&&notice.startsWith('Error')?
      '<div class="wallet-error">'+escapeHtml(notice)+'</div>':'')+
      memberSection()+
      '<section class="wallet-card"><div class="wallet-row"><h2>Purchase History</h2>'+
      '<span class="wallet-pill">'+receipts.length+' receipts</span></div>'+
      (receipts.length?'<div class="wallet-list">'+receipts.map(card).join('')+'</div>':
        '<p>No saved receipts yet. Scan the QR code shown after your next purchase to save one here.</p>')+
      '</section>'+
      (!wallet.member?'<div class="wallet-actions wallet-no-print"><button type="button" class="wallet-btn secondary" data-wallet-action="forget">Forget this device</button></div>':'');
    renderGoogle();
  }
  async function refresh(){
    wallet=await request('/wallet/me');
    paint();
  }
  function renderGoogle(){
    if(!config.member_login_available||wallet.member)return;
    const node=document.getElementById('wallet-google-button');
    if(!node||!window.google?.accounts?.id)return;
    window.google.accounts.id.initialize({
      client_id:config.google_client_id,
      callback:async payload=>{
        if(loading)return;
        loading=true;
        notice='Signing in…';status.textContent=notice;
        try{
          await request('/wallet/google','POST',{credential:payload.credential});
          notice='';await refresh();
        }catch(err){notice='Error: '+err.message;paint()}
        finally{loading=false}
      }
    });
    window.google.accounts.id.renderButton(node,{
      theme:'outline',size:'large',text:'continue_with',shape:'pill',width:260
    });
  }
  function setupGoogle(){
    if(!config.member_login_available)return;
    if(window.google?.accounts?.id){renderGoogle();return}
    const script=document.createElement('script');
    script.src='https://accounts.google.com/gsi/client';
    script.async=true;script.defer=true;
    script.onload=renderGoogle;
    script.onerror=()=>{notice='Google Sign-In could not load';status.textContent=notice};
    document.head.append(script);
  }
  root.addEventListener('submit',async event=>{
    if(event.target.id!=='wallet-profile-form')return;
    event.preventDefault();
    const form=event.target;
    const payload={name:form.elements.name.value.trim(),
                   phone:form.elements.phone.value.trim()};
    if(loading)return;
    loading=true;notice='Saving Member…';status.textContent=notice;
    try{
      await request('/wallet/profile','POST',payload);
      notice='Member registration complete ✓';await refresh();
    }catch(err){notice='Error: '+err.message;paint()}
    finally{loading=false}
  });
  root.addEventListener('click',async event=>{
    const action=event.target.closest('[data-wallet-action]')?.dataset.walletAction;
    if(!action)return;
    if(action==='print'){window.print();return}
    if(loading)return;
    if(action==='forget'&&!confirm('Forget guest receipts on this device? Saved member receipts stay in your account.'))return;
    loading=true;
    try{
      await request(action==='logout'?'/wallet/logout':'/wallet/forget-device','POST',{});
      notice=action==='logout'?'Signed out.':'Device receipt access cleared.';
      await refresh();
    }catch(err){notice='Error: '+err.message;paint()}
    finally{loading=false}
  });
  (async()=>{
    // URL fragments never reach the server, and are cleared before calling the API.
    const raw=location.hash.replace(/^#/,'');
    const token=/^[A-Za-z0-9_-]{30,120}$/.test(raw)?raw:null;
    if(location.hash)history.replaceState(null,'','/wallet');
    try{
      config=await request('/wallet/config');
      if(token){
        notice='Saving your receipt…';status.textContent=notice;
        const claimed=await request('/wallet/claim','POST',{token});
        notice=claimed.already_saved?'Receipt already in this wallet.':'Receipt saved ✓';
      }
      await refresh();
      setupGoogle();
    }catch(err){
      notice='Error: '+err.message;
      try{await refresh()}catch{paint()}
      setupGoogle();
    }
  })();
})();
