(()=>{'use strict';
const $=id=>document.getElementById(id);
const safeText=(id,value)=>{const el=$(id);if(el)el.textContent=String(value??'')};
const fmt=amount=>new Intl.NumberFormat(window.EZI18N?.locale()||'vi-VN').format(amount||0)+' đ';
const fallback='/assets/storefront-fallback.svg';
const id=location.pathname.split('/').pop();
async function run(){
  const root=$('preview-error');
  try{
    const r=await fetch('/api/businesses/'+encodeURIComponent(id)+'/storefront-preview',{
      credentials:'same-origin',cache:'no-store',
      headers:{'Accept-Language':window.EZI18N?.language()||'vi'}
    });
    if(!r.ok)throw Error('Không thể mở bản xem trước. Hãy đăng nhập bằng tài khoản chủ doanh nghiệp.');
    const data=await r.json();
    if(!data.preview_only)throw Error('Đây không phải bản xem trước');
    const brand=data.business.branding;
    const accent=brand.accent_color||'#147D64';
    document.body.style.setProperty('--accent',accent);
    document.body.classList.add('layout-'+brand.layout_style);
    safeText('brand-name',brand.display_name);
    safeText('store-title',brand.hero_title||brand.display_name);
    safeText('store-description',brand.description||'Trải nghiệm thương hiệu của bạn.');
    safeText('footer-name',brand.display_name);
    safeText('footer-address',brand.address);
    safeText('footer-phone',brand.phone);
    safeText('footer-note',brand.footer_note);
    const hero=$('store-hero');
    // The API validates this against the approved image CDN.
    const image=new Image();
    image.onload=()=>{hero.style.backgroundImage='url("'+brand.banner_image+'")'};
    image.onerror=()=>{hero.style.backgroundImage='url("'+fallback+'")'};
    image.src=brand.banner_image||fallback;
    const mark=$('brand-mark');
    if(brand.logo_url){
      const logo=new Image();logo.alt='Logo';logo.onload=()=>{mark.textContent='';mark.appendChild(logo)};
      logo.onerror=()=>{mark.textContent=(brand.display_name||'EZ').slice(0,2).toUpperCase()};
      logo.src=brand.logo_url;
    }else mark.textContent=(brand.display_name||'EZ').slice(0,2).toUpperCase();
    document.title=brand.display_name+' · EZ Thing preview';
    const grid=$('product-grid');
    if(!data.products.length){const empty=document.createElement('p');empty.className='empty-products';empty.textContent='Chưa có sản phẩm. Vào mục Sản phẩm trong khu quản lý để thêm.';grid.appendChild(empty)}
    for(const p of data.products){
      const card=document.createElement('article');card.className='preview-product';
      const art=document.createElement('div');art.className='product-art';art.textContent='🍽️';
      const body=document.createElement('div');
      const h=document.createElement('h3');h.textContent=p.name;h.dataset.ezLangIgnore='';
      const cat=document.createElement('p');cat.textContent=p.category||'';cat.dataset.ezLangIgnore='';
      const price=document.createElement('strong');price.textContent=fmt(p.price_vnd);
      body.append(h,cat,price);card.append(art,body);grid.appendChild(card);
    }
  }catch(e){root.textContent=e.message;root.hidden=false}
}
run();
})();
