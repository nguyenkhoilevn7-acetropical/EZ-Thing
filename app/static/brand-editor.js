(()=>{'use strict';
const $=id=>document.getElementById(id);
const form=$('brand-form');
const keys=['display_name','description','phone','address','banner_preset','hero_title','banner_url','logo_url','accent_color','layout_style','footer_note'];
const names={coffee:'Cà phê',dining:'Nhà hàng',retail:'Bán lẻ',online:'Bán hàng online',wellness:'Wellness'};
let businesses=[],config=null,csrf='',plans={};
function status(message,error=false){const el=$('feedback');el.textContent=message;el.classList.toggle('error',error)}
async function request(path,options={}){
 const response=await fetch('/api'+path,{credentials:'same-origin',cache:'no-store',...options,headers:{'Accept-Language':window.EZI18N?.language()||'vi',...(options.headers||{})}});
 let data={};try{data=await response.json()}catch{}
 if(!response.ok){const detail=typeof data.detail==='string'?data.detail:typeof data.detail?.message==='string'?data.detail.message:'Yêu cầu thất bại';throw Error(detail)}
 return data;
}
function selectBusiness(){
 const id=$('business-choice');id.textContent='';
 for(const business of businesses){
  const option=document.createElement('option');
  option.value=business.id;option.textContent=business.name+' · '+business.plan;id.append(option);
 }
 const requested=new URLSearchParams(location.search).get('bid');
 if(requested&&businesses.some(x=>x.id===requested))id.value=requested;
}
function previewImage(url){
 const target=$('brand-stage');
 const urlOk=typeof url==='string'&&url.startsWith('https://images.unsplash.com/photo-');
 const candidate=urlOk?url:'/assets/storefront-fallback.svg';
 const image=new Image();
 image.onload=()=>{target.style.backgroundImage='url("'+candidate+'")'};
 image.onerror=()=>{target.style.backgroundImage='url("/assets/storefront-fallback.svg")'};
 image.src=candidate;
}
function updatePreview(){
 if(!config)return;
 const values=Object.fromEntries(new FormData(form).entries());
 const base=config.branding;
 const display=values.display_name||base.display_name;
 const heading=values.hero_title||display;
 const description=values.description||'Thương hiệu riêng của bạn.';
 $('stage-title').textContent=heading;
 $('stage-text').textContent=description;
 const accent=values.accent_color||base.accent_color||'#147D64';
 document.body.style.setProperty('--green',accent);
 const image=values.banner_url?.trim()||config.presets[values.banner_preset||base.banner_preset];
 previewImage(image||base.banner_image);
}
function renderPlanCards(){
 const container=$('plan-list');container.textContent='';
 const lang=window.EZI18N?.language()||'vi';
 for(const name of ['BASIC','PLUS','PRO']){
  const plan=plans[name];if(!plan)continue;
  const card=document.createElement('article');card.className='plan-tier'+(config?.plan===name?' current':'');
  const head=document.createElement('div');head.className='plan-tier-head';
  const title=document.createElement('strong');title.textContent=name+(config?.plan===name?' · Đang sử dụng':'');
  const price=document.createElement('small');
  price.textContent=new Intl.NumberFormat(lang==='en'?'en-US':'vi-VN').format(plan.price_vnd)+' đ / tháng*';
  head.append(title,price);
  const list=document.createElement('ul');
  const rows=plan.branding?.[lang]||plan.branding?.vi||[];
  for(const text of rows){const li=document.createElement('li');li.textContent=text;list.append(li)}
  card.append(head,list);container.append(card);
 }
}
function updateControls(){
 const editable=new Set(config.editable_fields||[]);
 for(const key of keys){
  const control=form.elements.namedItem(key);if(!control)continue;
  control.disabled=!editable.has(key);
  control.closest('.field')?.classList.toggle('is-locked',!editable.has(key));
 }
 $('current-plan').textContent=config.plan+' · PILOT';
 $('open-preview').href=config.preview_url;
}
function populatePresets(){
 const select=$('banner-preset');select.textContent='';
 for(const [id] of Object.entries(config.presets)){
  const option=document.createElement('option');option.value=id;option.textContent=names[id]||id;
  select.append(option);
 }
}
async function loadBusiness(){
 status('Đang tải thương hiệu...');
 const bid=$('business-choice').value;
 if(!bid)return;
 try{
  const data=await request('/businesses/'+encodeURIComponent(bid)+'/storefront');
  config=data;
  populatePresets();
  for(const key of keys){const control=form.elements.namedItem(key);if(control)control.value=data.branding[key]||''}
  updateControls();updatePreview();renderPlanCards();
  status('Đã tải cấu hình riêng của doanh nghiệp. Các thay đổi chưa lưu sẽ không được công bố.');
  history.replaceState(null,'','/app/storefront-design?bid='+encodeURIComponent(bid));
 }catch(error){status(error.message,true)}
}
form.addEventListener('input',updatePreview);
form.addEventListener('change',updatePreview);
form.addEventListener('submit',async event=>{
 event.preventDefault();
 if(!config)return;
 const button=$('save');button.disabled=true;
 try{
  const bid=$('business-choice').value;
  const body=Object.fromEntries(new FormData(form).entries());
  const data=await request('/businesses/'+encodeURIComponent(bid)+'/storefront',{
   method:'PATCH',headers:{'Content-Type':'application/json','x-csrf-token':csrf},body:JSON.stringify(body)
  });
  config=data;
  const current=businesses.find(x=>x.id===bid);
  if(current)current.name=data.branding.display_name;
  const selected=$('business-choice').selectedOptions[0];
  if(selected)selected.textContent=data.branding.display_name+' · '+data.plan;
  updateControls();updatePreview();renderPlanCards();
  status('Đã lưu thành công! Mở trang xem trước để kiểm tra thay đổi.');
 }catch(error){status(error.message,true)}finally{button.disabled=false}
});
$('business-choice').addEventListener('change',loadBusiness);
document.addEventListener('ezthing:language-changed',renderPlanCards);
async function init(){
 try{
  const me=await request('/auth/me');csrf=me.csrf_token;
  const [biz,meta]=await Promise.all([request('/businesses'),request('/storefront/plans')]);
  businesses=biz;plans=meta.plans;
  if(!businesses.length){status('Bạn chưa có doanh nghiệp. Hãy tạo doanh nghiệp trong khu quản lý.');form.hidden=true;return}
  selectBusiness();await loadBusiness();
 }catch(error){status(error.message+' · Hãy đăng nhập từ /app trước.',true);form.hidden=true}
}
init();
})();