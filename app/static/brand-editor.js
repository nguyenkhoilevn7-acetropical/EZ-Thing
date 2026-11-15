(()=>{'use strict';
const $=id=>document.getElementById(id);
const form=$('brand-form');
const keys=['display_name','description','phone','address','banner_preset','hero_title','banner_url','logo_url','accent_color','layout_style','footer_note','banner_position_x','banner_position_y','logo_position_x','logo_position_y'];
const names={coffee:'Cà phê',dining:'Nhà hàng',retail:'Bán lẻ',online:'Bán hàng online',wellness:'Wellness'};
let businesses=[],config=null,csrf='',plans={};
const selectedFiles={banner:null,logo:null},objectUrls={banner:'',logo:''};
let imageRequest=0,lastImage='',dragging=null;
const allowedTypes=new Set(['image/jpeg','image/png','image/webp']);
const clamp=n=>Math.max(0,Math.min(100,Math.round(Number(n)||0)));
function localPhoto(kind){return objectUrls[kind]||''}
function clearLocal(kind){
 if(objectUrls[kind])URL.revokeObjectURL(objectUrls[kind]);
 objectUrls[kind]='';selectedFiles[kind]=null;
 const input=$('brand-'+kind+'-file');if(input)input.value='';
}
function mediaCaption(kind,caption){$(kind+'-upload-status').textContent=caption}
function candidate(kind,values){
 const field=kind+'_url',base=config.branding;
 const url=(values[field]||'').trim();
 if(localPhoto(kind))return localPhoto(kind);
 if(url&&url.startsWith('https://images.unsplash.com/photo-'))return url;
 if(kind==='banner'){
   if(base.banner_uploaded&&!url)return base.banner_image;
   return url||config.presets[values.banner_preset]||base.banner_image;
 }
 if(base.logo_uploaded&&!url)return base.logo_image;
 return url||base.logo_image||'';
}
function updatePosition(kind,x,y){
 form.elements.namedItem(kind+'_position_x').value=String(clamp(x));
 form.elements.namedItem(kind+'_position_y').value=String(clamp(y));
 updatePreview();
}
function readPosition(kind,axis){
 return clamp(form.elements.namedItem(kind+'_position_'+axis).value||50);
}

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
 const target=$('brand-stage'),candidateUrl=url||'/assets/storefront-fallback.svg';
 if(lastImage===candidateUrl)return;
 lastImage=candidateUrl;const requestId=++imageRequest;
 const image=new Image();
 image.onload=()=>{if(requestId===imageRequest)target.style.backgroundImage='url("'+candidateUrl+'")'};
 image.onerror=()=>{if(requestId===imageRequest)target.style.backgroundImage='url("/assets/storefront-fallback.svg")'};
 image.src=candidateUrl;
}
function updatePreview(){
 if(!config)return;
 const values=Object.fromEntries(new FormData(form).entries());
 const base=config.branding;
 const display=values.display_name||base.display_name;
 $('stage-title').textContent=values.hero_title||display;
 $('stage-text').textContent=values.description||'Thương hiệu riêng của bạn.';
 document.body.style.setProperty('--green',values.accent_color||base.accent_color||'#147D64');
 const banner=candidate('banner',values);
 previewImage(banner);
 const x=readPosition('banner','x'),y=readPosition('banner','y');
 $('brand-stage').style.backgroundPosition=x+'% '+y+'%';
 $('banner-inline').style.backgroundImage='url("'+(banner||'/assets/storefront-fallback.svg')+'")';
 $('banner-inline').style.backgroundPosition=x+'% '+y+'%';
 $('banner-coordinates').textContent=x+'% / '+y+'%';
 const logo=candidate('logo',values),logoImg=$('stage-logo');
 if(logo){
   if(logoImg.dataset.current!==logo){logoImg.dataset.current=logo;logoImg.src=logo;}
   logoImg.hidden=false;
   $('logo-inline').style.backgroundImage='url("'+logo+'")';
 }else{
   logoImg.hidden=true;logoImg.removeAttribute('src');logoImg.dataset.current='';
   $('logo-inline').style.backgroundImage='none';
 }
 const lx=readPosition('logo','x'),ly=readPosition('logo','y');
 logoImg.style.objectPosition=lx+'% '+ly+'%';
 $('logo-inline').style.backgroundPosition=lx+'% '+ly+'%';
 $('logo-coordinates').textContent=lx+'% / '+ly+'%';
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
 for(const kind of ['banner','logo']){
   const enabled=editable.has(kind+'_url');
   $('brand-'+kind+'-file').disabled=!enabled;
   const mediaField=document.querySelector('[data-media-kind="'+kind+'"]');
   mediaField.classList.toggle('is-locked',!enabled);
   mediaField.querySelector('[data-remove-media]').disabled=!enabled;
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
  for(const kind of ['banner','logo']){
   clearLocal(kind);
   mediaCaption(kind,data.branding[kind+'_uploaded']?'✓ Ảnh đã tải lên và lưu trong doanh nghiệp.':'Chọn ảnh để xem trước trước khi lưu.');
  }
  lastImage='';
  populatePresets();
  for(const key of keys){const control=form.elements.namedItem(key);if(control)control.value=data.branding[key]||''}
  updateControls();updatePreview();renderPlanCards();
  status('Đã tải cấu hình riêng của doanh nghiệp. Các thay đổi chưa lưu sẽ không được công bố.');
  history.replaceState(null,'','/app/storefront-design?bid='+encodeURIComponent(bid));
 }catch(error){status(error.message,true)}
}
for(const kind of ['banner','logo']){
 const input=$('brand-'+kind+'-file');
 input.addEventListener('change',()=>{
   const file=input.files?.[0];if(!file)return;
   if(!allowedTypes.has(file.type)||file.size>6*1024*1024||file.size===0){
     input.value='';status('Ảnh phải là JPEG, PNG hoặc WebP, dung lượng không quá 6 MB.',true);return;
   }
   clearLocal(kind);
   selectedFiles[kind]=file;objectUrls[kind]=URL.createObjectURL(file);
   mediaCaption(kind,'✓ '+file.name+' — đang xem trước; nhấn Lưu thay đổi để lưu ảnh.');
   updatePreview();
 });
 document.querySelector('[data-remove-media="'+kind+'"]').addEventListener('click',async()=>{
   if(selectedFiles[kind]){
     clearLocal(kind);mediaCaption(kind,'Đã hủy ảnh mới chưa lưu.');updatePreview();return;
   }
   if(!config?.branding[kind+'_uploaded'])return;
   try{
     const bid=$('business-choice').value;
     config=await request('/businesses/'+encodeURIComponent(bid)+'/storefront-media/'+kind,{
       method:'DELETE',headers:{'x-csrf-token':csrf}});
     mediaCaption(kind,'Đã bỏ ảnh tải lên, trở về ảnh URL/mẫu.');
     lastImage='';updatePreview();status('Đã xóa ảnh '+kind+' của doanh nghiệp.');
   }catch(error){status(error.message,true)}
 });
}
for(const kind of ['banner','logo']){
 const target=$(kind==='banner'?'brand-stage':'brand-logo-stage');
 target.addEventListener('pointerdown',event=>{
   if(event.button!==0||!config?.editable_fields?.includes(kind+'_position_x'))return;
   dragging={kind,id:event.pointerId,x:event.clientX,y:event.clientY,
     firstX:readPosition(kind,'x'),firstY:readPosition(kind,'y')};
   target.setPointerCapture(event.pointerId);
   event.preventDefault();
 });
 target.addEventListener('pointermove',event=>{
   if(!dragging||dragging.kind!==kind||dragging.id!==event.pointerId)return;
   const rect=target.getBoundingClientRect();
   updatePosition(kind,dragging.firstX-(event.clientX-dragging.x)/rect.width*100,
     dragging.firstY-(event.clientY-dragging.y)/rect.height*100);
 });
 const end=event=>{if(dragging?.kind===kind&&dragging.id===event.pointerId)dragging=null;};
 target.addEventListener('pointerup',end);target.addEventListener('pointercancel',end);
 target.addEventListener('lostpointercapture',()=>{dragging=null});
 document.querySelector('[data-reset-position="'+kind+'"]').addEventListener('click',()=>updatePosition(kind,50,50));
}
form.addEventListener('input',updatePreview);
form.addEventListener('change',updatePreview);
form.addEventListener('submit',async event=>{
 event.preventDefault();
 if(!config)return;
 const button=$('save');button.disabled=true;
 try{
  const bid=$('business-choice').value;
  for(const kind of ['banner','logo']){
   if(!selectedFiles[kind])continue;
   const upload=new FormData();upload.append('file',selectedFiles[kind]);
   config=await request('/businesses/'+encodeURIComponent(bid)+'/storefront-media/'+kind,{
     method:'PUT',headers:{'x-csrf-token':csrf},body:upload});
   form.elements.namedItem(kind+'_url').value='';
   clearLocal(kind);mediaCaption(kind,'✓ Ảnh đã lưu trong hệ thống.');
  }
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