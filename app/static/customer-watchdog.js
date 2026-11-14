/* Recovery UI for unresponsive customer demo bootstrap. Keep independent of customer.js. */
(()=>{
'use strict';
const root=()=>document.getElementById('customer-root');
function recover(){
 const host=root();
 if(!host || !host.querySelector('.customer-loading'))return;
 host.innerHTML='<main class="closed-message" style="padding:48px 20px;text-align:center">'
  +'<span class="customer-logo" aria-hidden="true">e.</span>'
  +'<h2>Demo chưa tải xong / Demo did not finish loading</h2>'
  +'<p>Không thể kết nối hoặc tải dữ liệu thử nghiệm. Vui lòng thử lại. / Unable to finish connecting to the demo.</p>'
  +'<button id="demo-retry" class="info-link" type="button">Thử lại / Retry</button>'
  +' <a class="info-link" href="/">Trang chủ / Home</a></main>';
 host.querySelector('#demo-retry')?.addEventListener('click',()=>location.reload());
}
function hint(){
 const loading=root()?.querySelector('.customer-loading');
 if(!loading || loading.querySelector('[data-demo-hint]'))return;
 const note=document.createElement('small');
 note.dataset.demoHint='1';
 note.textContent='Đang kết nối với bản DEMO / Connecting to demo...';
 note.style.display='block';
 note.style.marginLeft='12px';
 loading.appendChild(note);
}
window.addEventListener('load',()=>{
 window.setTimeout(hint,8000);
 window.setTimeout(recover,55000);
},{once:true});
window.addEventListener('error',(event)=>{
 const target=event.target;
 if(target instanceof HTMLScriptElement && /\/assets\/customer\.js(?:\?|$)/.test(target.src))recover();
},true);
})();
