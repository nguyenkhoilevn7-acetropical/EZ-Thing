/* Merchant publishing settings for a REAL tenant. Never auto-publish. */
(() => {
"use strict";
window.EZPublishingUI = {
 render(site,leads,E,owner,orders=[]){
   const en=window.EZI18N?.language()==='en';
   const t=(vi,english)=>en?english:vi;
   const status=site?.published?t('Đang công khai','Published'):t('Chưa xuất bản','Not published');
   return `<section class="surface pad ez-publishing">
     <div class="panel-title"><div><h3>🌐 ${t('Website khách hàng riêng','Your public storefront')}</h3>
       <p class="subtle">${t('Trang giới thiệu sản phẩm và nhận yêu cầu tư vấn dành riêng cho doanh nghiệp của bạn.',
        'An independent public product catalog and contact page for your business.')}</p>
     </div><span class="pill ${site?.published?'green':''}">${E(status)}</span></div>
     ${owner?`<form id="site-publish-form" class="ez-publish-form">
       <div class="formfield"><label>${t('Địa chỉ website (slug)','Website address (slug)')}</label>
         <div class="ez-slug-input"><span>/shop/</span><input name="slug" required
           pattern="[a-z0-9]+(-[a-z0-9]+)*" minlength="3" maxlength="60"
           value="${E(site?.slug||'')}" autocapitalize="off" spellcheck="false"></div>
       </div>
       <label class="ez-publish-checkbox"><input name="published" type="checkbox" ${site?.published?'checked':''}>
         ${t('Cho phép công khai website và nhận yêu cầu liên hệ','Publish website and accept contact requests')}
       </label>
       <div class="ez-publish-actions"><button class="btn" type="submit">${t('Lưu và áp dụng','Save settings')}</button>
       ${site?.public_url?`<a class="btn secondary" href="${E(site.public_url)}" target="_blank" rel="noopener noreferrer">
         ${t('Mở website khách ↗','Open storefront ↗')}</a>`:''}</div>
       <p class="subtle">${t('Chưa có thanh toán online; không trừ tiền tự động. Chỉ website được bật công khai mới hiển thị cho khách.',
       'No online payments or automatic charges. Only explicitly published storefronts can be accessed by visitors.')}</p>
     </form>`:`<p class="muted">${t('Chủ doanh nghiệp quản lý việc xuất bản website.',
                         'Only the owner can publish or unpublish this website.')}</p>`}
   </section>
   <section class="surface pad ez-public-leads">
     <div class="panel-title"><div><h3>🛒 ${t('Yêu cầu đặt hàng','Customer order requests')}</h3>
       <p class="subtle">${t('Đơn chỉ trừ kho sau khi quản lý duyệt. Không có thanh toán tự động.',
         'Inventory moves only on merchant approval. No automatic payment.')}</p>
     </div><span class="pill">${(orders||[]).filter(x=>x.status==='pending').length} ${t('đang chờ','pending')}</span></div>
     <div class="ez-lead-list">${(orders||[]).map(o=>`<article class="ez-lead-item">
       <div>
         <strong>#${E(String(o.id||'').slice(0,8).toUpperCase())} · ${E(o.customer_name)}</strong>
         <span>${E(o.phone)} · ${E(new Date(o.created_at).toLocaleString(en?'en-US':'vi-VN'))}</span>
         <p>${(o.items||[]).map(i=>E(i.name)+' × '+Number(i.quantity)).join(' · ')}</p>
         <p>${E(o.address||'')} ${E(o.note||'')}</p>
         <strong>${new Intl.NumberFormat(en?'en-US':'vi-VN').format(Number(o.total_vnd)||0)}đ</strong>
       </div>
       <div class="ez-lead-actions"><span class="pill">${E(o.status)}</span>
       ${o.status==='pending'?`<button type="button" class="btn sm" data-action="public-order-review"
          data-value="${E(o.id)}|accept">${t('Duyệt đơn','Approve')}</button>
         <button type="button" class="btn sm secondary" data-action="public-order-review"
          data-value="${E(o.id)}|reject">${t('Từ chối','Reject')}</button>`:
        o.sale_order_id?`<small class="subtle">#${E(o.sale_order_id.slice(0,8))}</small>`:''}
       </div>
     </article>`).join('')||`<p class="muted">${t('Chưa có yêu cầu đặt hàng.','No order requests yet.')}</p>`}</div>
   </section>
   <section class="surface pad ez-public-leads">
    <div class="panel-title"><h3>💬 ${t('Yêu cầu từ website','Website enquiries')}</h3>
      <span class="pill">${(leads||[]).length}</span></div>
    <div class="ez-lead-list">${(leads||[]).map(lead=>`<article class="ez-lead-item">
      <div><strong>${E(lead.name)}</strong><span>${E(lead.phone)} · ${E(new Date(lead.created_at).toLocaleString(en?'en-US':'vi-VN'))}</span>
        <p>${E(lead.message)}</p></div>
      <div class="ez-lead-actions"><span class="pill">${E(lead.status)}</span>
        ${lead.status==='new'?`<button class="btn sm secondary" data-action="lead-next" data-value="${E(lead.id)}|contacted">
          ${t('Đã liên hệ','Contacted')}</button>`:''}
        ${lead.status==='contacted'?`<button class="btn sm secondary" data-action="lead-next" data-value="${E(lead.id)}|closed">
          ${t('Đóng yêu cầu','Close')}</button>`:''}
      </div></article>`).join('') || `<p class="muted">${t('Chưa có yêu cầu liên hệ.','No new enquiries yet.')}</p>`}</div>
    <p class="subtle">${t('Chỉ dùng thông tin khách hàng để liên hệ theo yêu cầu; không chia sẻ với bên thứ ba.',
                           'Use visitor details only to respond to their enquiry.')}</p>
   </section>`;
 }
};
})();
