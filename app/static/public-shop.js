/* EZ Thing public tenant storefront: safe, read-only catalog and contact leads.
   All prices and public fields originate from the tenant-scoped API. */
(() => {
  "use strict";
  const root = document.getElementById("shop-root");
  const raw = location.pathname.split("/").filter(Boolean)[1] || "";
  const slug = /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(raw) ? raw : "";
  const E = x => String(x ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
  const V = x => new Intl.NumberFormat(lang === "en" ? "en-US" : "vi-VN").format(x) + "đ";
  const state = { data: null, sending: false, cart: new Map(), orderRequestId: null };
  let lang = "vi";
  try { lang = localStorage.getItem("ezthing_site_lang") === "en" ? "en" : "vi"; } catch (_) {}
  const T = (vi, en) => lang === "en" ? en : vi;

  async function fetchJSON(path, options = {}) {
    const abort = new AbortController(), timer = setTimeout(() => abort.abort(), 16000);
    try {
      const response = await fetch(path, {
        credentials: "omit", cache: "no-store", signal: abort.signal,
        ...options, headers: {"Content-Type":"application/json", ...(options.headers || {})}
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : T("Không thể tải dữ liệu", "Unable to load data"));
      return data;
    } finally { clearTimeout(timer); }
  }

  function button(label, action, value = "") {
    return `<button type="button" class="shop-button" data-action="${E(action)}" data-value="${E(value)}">${label}</button>`;
  }

  function countItems(){return [...state.cart.values()].reduce((sum,x)=>sum+x,0);}
  function phoneHref(phone) {
    const valid = String(phone || "").replace(/[^+0-9]/g, "");
    return valid.length >= 7 ? "tel:" + valid : "";
  }

  function render() {
    const data = state.data;
    if (!data) return;
    const brand = data.branding || {};
    const title = brand.display_name || data.name || "EZ Thing";
    document.title = title + " · EZ Thing";
    document.documentElement.lang = lang;
    document.documentElement.style.setProperty("--accent",
      /^#[0-9A-Fa-f]{6}$/.test(brand.accent_color || "") ? brand.accent_color : "#147D64");
    const phone = phoneHref(brand.phone);
    const products = data.products || [];
    const categories = new Set(products.map(p => p.category));
    const symbols = {fnb:"☕",retail:"🛍",online:"📦",services:"✦"};
    const symbol = symbols[data.industry] || "✦";
    root.innerHTML = `<header class="shop-header"><div class="shop-container shop-header-inner">
      <a class="shop-brand" href="#home">
        <span class="shop-logo">${brand.logo_url ? `<img src="${E(brand.logo_url)}" alt="${E(title)}">` : symbol}</span>
        <span><strong>${E(title)}</strong><small>POWERED BY EZ THING</small></span>
      </a><div class="shop-actions">
        <button class="shop-language" type="button" data-action="switch-language" aria-label="Switch language">
          ${lang === "en" ? "🇬🇧 EN" : "🇻🇳 VI"}
        </button>
        ${data.industry!=="services" ? button("🛒 "+T("Giỏ hàng", "Cart")+" ("+countItems()+")","cart") : ""}
        ${button(T("Liên hệ cửa hàng", "Contact store"),"contact")}
      </div></div></header>
      <main id="home" class="shop-container">
      <section class="shop-hero" aria-labelledby="shop-headline">
        <div class="shop-hero-bg" style="background-image:url('${E(brand.banner_image || "")}');background-position:${Math.max(0,Math.min(100,Number(brand.banner_position_x??50)))}% ${Math.max(0,Math.min(100,Number(brand.banner_position_y??50)))}%"></div>
        <div class="shop-hero-shade"></div>
        <div class="shop-hero-content">
          <div class="shop-eyebrow">EZ THING · ${E(data.industry.toUpperCase())}</div>
          <h1 id="shop-headline">${E(brand.hero_title || title)}</h1>
          <p>${E(brand.description || T("Khám phá sản phẩm và dịch vụ của cửa hàng.",
                                        "Explore products and services from this business."))}</p>
          ${button(T("Gửi yêu cầu tư vấn", "Request assistance"),"contact")}
        </div>
      </section>
      <section id="catalog" aria-label="${T('Danh mục','Catalog')}">
        <div class="shop-section-title"><div>
          <h2>${T("Sản phẩm & dịch vụ", "Products & services")}</h2>
          <p>${products.length} ${T("mặt hàng đang giới thiệu", "available listings")}
            · ${categories.size} ${T("danh mục", "categories")}</p></div>
        </div>
        <div class="shop-grid">${products.map(p => `<article class="shop-product">
          <div class="shop-product-photo" aria-hidden="true">${symbol}</div>
          <div class="shop-product-info">
            <span class="shop-category">${E(p.category)}</span>
            <h3>${E(p.name)}</h3>
            <div class="shop-product-bottom"><strong>${V(p.price_vnd)}</strong>
              ${p.available ? (data.industry==="services" ? button(T("Hỏi dịch vụ", "Enquire"), "contact", p.id)
              : button("＋ "+T("Thêm", "Add"),"cart-add",p.id)) :
                 `<span class="shop-out">${T("Tạm hết", "Unavailable")}</span>`}
            </div></div></article>`).join("") || `<p>${T("Cửa hàng đang cập nhật danh mục.", "Catalog coming soon.")}</p>`}</div>
      </section>
      <section class="shop-info-grid">
        <article class="shop-info"><h2>📍 ${T("Thông tin cửa hàng", "Business information")}</h2>
          <p>${E(brand.address || T("Liên hệ để nhận địa chỉ", "Contact for location"))}</p>
          <p>${E(brand.phone || T("Chưa cung cấp số điện thoại", "Phone not provided"))}</p>
          ${phone ? `<a href="${E(phone)}" class="shop-button secondary">${T("Gọi cửa hàng", "Call business")}</a>` : ""}
        </article>
        <article class="shop-info"><h2>💬 ${T("Tư vấn & đặt dịch vụ", "Request assistance")}</h2>
          <p>${T("Gửi yêu cầu để cửa hàng liên hệ lại và xác nhận. Website này không tự động thu tiền.",
                   "Send a message to request a callback and confirmation. No payment is collected on this website.")}</p>
          ${button(T("Gửi yêu cầu", "Send enquiry"),"contact")}
        </article>
      </section></main>
      <footer class="shop-container shop-footer">
        <span>${E(brand.footer_note || title)} · Powered by EZ Thing</span>
        <span>${T("Chưa tích hợp thanh toán trực tuyến", "No online checkout")}</span>
      </footer>
      <div class="shop-mobile-cta">${data.industry==="services"
        ? button(T("Liên hệ & đặt lịch", "Contact & book"),"contact")
        : button("🛒 "+T("Xem giỏ hàng", "View cart")+" ("+countItems()+")","cart")}</div>
      <div id="shop-modal"></div>`;
  }

  function closeModal() {
    const modal = document.getElementById("shop-modal");
    if (modal) modal.innerHTML = "";
    document.body.style.overflow = "";
  }

  function openContact(selected = "") {
    const data = state.data;
    if (!data) return;
    const products = data.products || [];
    const requestId = (crypto?.randomUUID?.() || "contact" + Date.now() + Math.random().toString(36).slice(2));
    const modal = document.getElementById("shop-modal");
    modal.innerHTML = `<div class="shop-overlay" data-overlay>
      <section class="shop-dialog" role="dialog" aria-modal="true" aria-labelledby="shop-contact-title">
        <header><h2 id="shop-contact-title">${T("Liên hệ cửa hàng", "Contact business")}</h2>
        <button class="shop-close" type="button" data-action="close">✕</button></header>
        <form class="shop-form" id="shop-contact-form" data-request-id="${E(requestId)}">
          <label>${T("Họ và tên", "Full name")}<input name="name" minlength="2" maxlength="100" required autocomplete="name"></label>
          <label>${T("Điện thoại", "Phone number")}<input name="phone" type="tel" inputmode="tel" minlength="7" maxlength="30" required autocomplete="tel"></label>
          <label>${T("Sản phẩm quan tâm", "Interested product")}
            <select name="product_id"><option value="">${T("Tư vấn chung", "General enquiry")}</option>
              ${products.filter(p=>p.available).map(p=>`<option value="${E(p.id)}" ${p.id===selected?"selected":""}>${E(p.name)}</option>`).join("")}
            </select></label>
          <label>${T("Nội dung yêu cầu", "Your message")}<textarea name="message" minlength="4" maxlength="500" required placeholder="${T("Tôi muốn biết thêm thông tin...","I'd like to know more...")}"></textarea></label>
          <p class="shop-note">${T("Cửa hàng sẽ liên hệ xác nhận. Không thanh toán hay giữ tiền tại website.",
                   "The merchant will confirm your enquiry. No money is charged or reserved.")}</p>
          <button class="shop-button" type="submit">${T("Gửi yêu cầu", "Send enquiry")}</button>
          <div id="shop-form-status" role="status" aria-live="polite"></div>
        </form>
      </section></div>`;
    document.body.style.overflow="hidden";
    modal.querySelector("[name=name]")?.focus();
  }

  function openCart() {
    const host=document.getElementById("shop-modal");
    if(!host||!state.data)return;
    const products=new Map((state.data.products||[]).map(p=>[p.id,p]));
    const entries=[...state.cart.entries()].filter(([id,qty])=>products.has(id)&&qty>0);
    const total=entries.reduce((sum,[id,qty])=>sum+products.get(id).price_vnd*qty,0);
    const online=state.data.industry==="online";
    host.innerHTML=`<div class="shop-overlay" data-overlay>
      <section class="shop-dialog" role="dialog" aria-modal="true" aria-label="${T('Giỏ hàng','Shopping cart')}">
        <header><h2>🛒 ${T("Giỏ hàng","Your cart")}</h2>
          <button class="shop-close" type="button" data-action="close">✕</button></header>
        <p class="shop-note">${T("Cửa hàng sẽ duyệt và liên hệ xác nhận đơn. Chưa thu tiền trực tuyến.",
          "The merchant must review and confirm your request. No online payment.")}</p>
        <div class="shop-cart-items">
          ${entries.map(([id,qty])=>`<div class="shop-cart-line">
            <div><strong>${E(products.get(id).name)}</strong>
              <small>${V(products.get(id).price_vnd)} × ${qty}</small></div>
            <div class="shop-cart-qty">
              <button type="button" data-action="cart-dec" data-value="${E(id)}" aria-label="${T('Giảm','Decrease')}">−</button>
              <span>${qty}</span>
              <button type="button" data-action="cart-inc" data-value="${E(id)}" aria-label="${T('Tăng','Increase')}">+</button>
            </div></div>`).join("")||`<p class="shop-note">${T('Giỏ hàng còn trống.','Your cart is empty.')}</p>`}
        </div>
        <div class="shop-cart-total"><strong>${T('Giá dự tính','Estimated subtotal')}</strong>
          <strong>${V(total)}</strong></div>
        ${entries.length?`<form class="shop-form" id="shop-order-form">
          <label>${T('Họ và tên','Full name')}
            <input name="customer_name" required minlength="2" maxlength="100" autocomplete="name"></label>
          <label>${T('Điện thoại','Phone number')}
            <input name="phone" type="tel" required minlength="7" maxlength="30" autocomplete="tel"></label>
          <label>${T(online?'Địa chỉ nhận hàng':'Địa chỉ (tùy chọn)',
                            online?'Delivery address':'Address (optional)')}
            <input name="address" maxlength="300" ${online?'required minlength="8"':''} autocomplete="street-address"></label>
          <label>${T('Ghi chú','Notes')}
            <textarea name="note" maxlength="180" placeholder="${T('Ví dụ: giao buổi sáng, ít đá...','For example: morning delivery...')}"></textarea></label>
          <button type="submit" class="shop-button">
            ${T('Gửi yêu cầu đặt hàng','Submit order request')}</button>
          <div id="shop-order-status" role="status" aria-live="polite"></div>
        </form>`:''}
      </section></div>`;
    document.body.style.overflow="hidden";
    host.querySelector('[data-action="close"]')?.focus();
  }

  async function sendOrder(form) {
    if(state.sending)return;
    const data=Object.fromEntries(new FormData(form).entries());
    const payload={
      request_id:state.orderRequestId||(state.orderRequestId=crypto?.randomUUID?.()||
        "order"+Date.now()+Math.random().toString(36).slice(2)),
      customer_name:data.customer_name,phone:data.phone,address:data.address||"",
      note:data.note||"",
      lines:[...state.cart.entries()].map(([product_id,quantity])=>({product_id,quantity}))
    };
    if(!payload.lines.length)return;
    state.sending=true;
    const button=form.querySelector('[type="submit"]');
    if(button)button.disabled=true;
    const error=document.getElementById("shop-order-status");
    try{
      const confirmation=await fetchJSON("/api/public/shops/"+encodeURIComponent(slug)+"/order-requests",{
        method:"POST",body:JSON.stringify(payload)
      });
      state.cart.clear();
      state.orderRequestId=null;
      render();
      const host=document.getElementById("shop-modal");
      host.innerHTML=`<div class="shop-overlay" data-overlay>
        <section class="shop-dialog" role="dialog" aria-modal="true" aria-label="${T('Đã nhận yêu cầu','Request received')}">
          <div style="text-align:center;padding:18px">
            <div style="font-size:43px;color:var(--accent)">✓</div>
            <h2>${T("Đã nhận yêu cầu đặt hàng","Order request received")}</h2>
            <p>${T("Mã yêu cầu","Request reference")}: #${E(confirmation.id.slice(0,8).toUpperCase())}</p>
            <p>${V(confirmation.total_vnd)}</p>
            <p class="shop-note">${T("Đơn đang chờ cửa hàng duyệt. Chưa thanh toán và chưa giữ tồn kho.",
              "Pending merchant review. No charge and no inventory reservation has occurred.")}</p>
            <button class="shop-button" data-action="close">${T("Hoàn tất","Done")}</button>
          </div>
        </section></div>`;
    }catch(err){
      if(error)error.textContent=err.name==="AbortError"
        ? T("Kết nối quá thời gian, vui lòng thử lại.","Request timed out. Please retry.")
        : err.message;
    }finally{
      state.sending=false;
      if(button)button.disabled=false;
    }
  }

  async function sendContact(form) {
    if (state.sending) return;
    state.sending=true;
    const button = form.querySelector('button[type="submit"]');
    if(button)button.disabled=true;
    const status = document.getElementById("shop-form-status");
    const data = Object.fromEntries(new FormData(form).entries());
    data.request_id = form.dataset.requestId;
    if(!data.product_id) data.product_id=null;
    try {
      await fetchJSON("/api/public/shops/"+encodeURIComponent(slug)+"/inquiries",{
        method:"POST", body:JSON.stringify(data)
      });
      form.innerHTML = `<div role="status" style="text-align:center;padding:22px 2px">
        <div style="font-size:40px">✓</div>
        <h3>${T("Đã gửi yêu cầu", "Enquiry sent")}</h3>
        <p>${T("Cửa hàng sẽ liên hệ bạn để xác nhận.", "The business will contact you to confirm.")}</p>
        <button type="button" class="shop-button" data-action="close">${T("Hoàn tất", "Done")}</button>
      </div>`;
    } catch (e) {
      if(status) status.textContent = e.name === "AbortError"
        ? T("Kết nối quá thời gian. Thử lại.", "Request timed out. Try again.")
        : e.message;
    } finally {
      state.sending=false;
      if(button) button.disabled=false;
    }
  }

  async function start(){
    if(!slug){root.innerHTML='<div class="shop-error"><h1>Địa chỉ không hợp lệ</h1></div>';return}
    try {
      state.data=await fetchJSON("/api/public/shops/"+encodeURIComponent(slug));
      render();
    } catch (e) {
      root.innerHTML=`<main class="shop-error"><h1>${T("Cửa hàng chưa sẵn sàng","Storefront unavailable")}</h1>
        <p>${E(e.message||T("Không thể mở cửa hàng lúc này","Unable to open this store"))}</p>
        <button class="shop-button" data-action="retry">${T("Thử lại","Retry")}</button></main>`;
    }
  }
  document.addEventListener("click", e=>{
    const button = e.target.closest("[data-action]");
    if(button){
      const action=button.dataset.action;
      if(action==="cart-add"){
        const id=button.dataset.value;
        const p=state.data?.products?.find(x=>x.id===id&&x.available);
        if(p&&(state.cart.has(id)||state.cart.size<15)){
          state.cart.set(id,Math.min(15,(state.cart.get(id)||0)+1));
          render();openCart();
        }
      }
      if(action==="cart")openCart();
      if(action==="cart-inc"||action==="cart-dec"){
        const id=button.dataset.value,quantity=(state.cart.get(id)||0)+(action==="cart-inc"?1:-1);
        if(quantity<1)state.cart.delete(id);
        else state.cart.set(id,Math.min(15,quantity));
        render();openCart();
      }
      if(action==="contact")openContact(button.dataset.value||"");
      if(action==="close")closeModal();
      if(action==="switch-language"){
        lang=lang==="vi"?"en":"vi";
        try{localStorage.setItem("ezthing_site_lang",lang)}catch(_){}
        render();
      }
      if(action==="retry")start();
    } else if(e.target.matches("[data-overlay]")) closeModal();
  });
  document.addEventListener("keydown", e=>{if(e.key==="Escape")closeModal()});
  document.addEventListener("submit", e=>{
    if(e.target.id==="shop-contact-form"){e.preventDefault();sendContact(e.target)}
    if(e.target.id==="shop-order-form"){e.preventDefault();sendOrder(e.target)}
  });
  start();
})();
