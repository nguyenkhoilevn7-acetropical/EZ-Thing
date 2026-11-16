/* EZ Thing Operations V5 — one integrated tenant-aware management screen.
   All writes pass through the existing /api CSRF client; no fake payment/sends. */
(function(){
'use strict';
window.EZOperationsV5=function(deps){
  var current='', data={}, generation=0, busy=false, poll=null;
  var closingDay=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Ho_Chi_Minh'}), closingBranch='';
  var E=deps.E,V=deps.V, api=deps.api, toast=deps.toast;
  function state(){return deps.getState()}
  function business(){return state().business||{}}
  function bid(){return encodeURIComponent(business().id||'')}
  function url(path){return '/businesses/'+bid()+'/operations/'+path}
  function uuid(){return globalThis.crypto?.randomUUID?.()||'op-'+Date.now()+'-'+Math.random().toString(36).slice(2)}
  function tx(vi,en){return window.EZI18N?.language?.()==='en'?en:vi}
  function opt(id,label,selected){return '<option value="'+E(id)+'"'+(selected===id?' selected':'')+'>'+E(label)+'</option>'}
  function options(items,label){return (items||[]).map(x=>opt(x.id,label?label(x):x.name)).join('')}
  function field(label,name,input){return '<label class="v5-field"><span>'+label+'</span>'+input.replace(' data-field',' name="'+name+'"')+'</label>'}
  function input(name,placeholder,type){return '<input name="'+E(name)+'" type="'+E(type||'text')+'" placeholder="'+E(placeholder||'')+'" required>'}
  function select(name,opts){return '<select name="'+name+'" required>'+opts+'</select>'}
  function row(x,details,actions){
    return '<article class="v5-entry"><div class="v5-entry-head"><strong>'+E(x.title||x.name||x.id||'')+'</strong><span class="v5-chip">'+E(x.status||'')+'</span></div>'+
      '<p>'+details+'</p>'+(actions?'<div class="v5-actions">'+actions+'</div>':'')+'</article>';
  }
  function btn(action,id,text,status){return '<button type="button" data-v5-action="'+action+'" data-id="'+E(id)+'" data-status="'+E(status||'')+'">'+E(text)+'</button>'}
  function form(name,body,label){return '<form data-v5-form="'+name+'" class="v5-form">'+body+
    '<button class="v5-main" type="submit">'+E(label)+'</button></form>'}
  function box(title,hint,inner,full){return '<section class="v5-panel'+(full?' v5-full':'')+'"><div class="v5-head"><h3>'+E(title)+'</h3><p>'+E(hint)+'</p></div>'+inner+'</section>'}
  function list(name,details,actions){return (data[name]||[]).slice(0,20).map(x=>row(x,details(x),actions?actions(x):'')).join('')||
    '<p class="v5-empty">'+tx('Chưa có dữ liệu','No records yet')+'</p>'}
  function load(name,path){return api(path||url(name)).then(x=>{data[name]=x}).catch(e=>{data[name]=[];data[name+'Error']=e.message})}
  function balances(){return data.loyalty?.balances||[]}
  function entries(name){return Array.isArray(data[name])?data[name]:[]}
  function sections(){
    var cache=state().cache||{},product=cache.products||[],branches=cache.branches||[],
      customers=cache.customers||[], staff=entries('staff'), reservations=entries('reservations');
    var brOptions=options(branches),productOptions=options(product),people=options(customers);
    var tracked=product.filter(x=>x.track_stock),untracked=product.filter(x=>!x.track_stock);
    var output='',industry=business().industry,role=business().role;
    if(industry==='fnb'&&business().active_modules?.includes('tables')){
      output+=box(tx('Danh sách chờ bàn','Waitlist'),tx('Nhân viên xếp hàng; thông báo khách hiện thao tác thủ công.','Host queue; outbound notices are not enabled.'),
        form('waitlist',input('name','Tên khách')+input('phone','Điện thoại','tel')+
          '<div class="v5-formrow"><label>👥 '+tx('Số khách','Party size')+'<input name="party_size" type="number" min="1" max="20" value="2" required></label>'+
          '<label>'+tx('Chi nhánh','Branch')+select('branch_id',brOptions)+'</label></div>',
          tx('Thêm khách vào danh sách chờ','Add to waitlist'))+
        list('waitlist',x=>tx('Số khách','Guests')+': '+E(x.details.party_size)+' • '+E(x.details.phone||''),x=>
          x.status==='waiting'?btn('waitlist',x.id,tx('Báo sẵn bàn','Mark ready'),'ready')+
            btn('waitlist',x.id,tx('Hủy','Cancel'),'cancelled'):
          x.status==='ready'?btn('waitlist',x.id,tx('Nhận khách','Seat party'),'seated')+
            btn('waitlist',x.id,tx('Hủy','Cancel'),'cancelled'):''));
      if(role!=='staff'){
      output+=box(tx('Yêu cầu đặt cọc','Deposit requests'),
        tx('Chỉ tạo yêu cầu nội bộ. Không xác nhận đã thanh toán.','Internal requests only; no payment gateway charge.'),
        form('deposit',select('reservation_id',reservations.map(x=>opt(x.id,(x.customer_name||'')+' • '+x.scheduled_at?.slice(0,16))))+
          input('amount_vnd','Số tiền VND','number')+
          '<p class="v5-note">'+tx('Cần cổng thanh toán xác minh trước khi nhận cọc online.','Requires a verified gateway before collecting deposits online.')+'</p>',
          tx('Tạo yêu cầu cọc','Create deposit request'))+
        list('deposits',x=>V(x.details.amount_vnd||0)+' • '+tx('Chưa thu tiền','Not paid')));
      output+=box(tx('Định lượng nguyên liệu','Ingredient recipes'),
        tx('Món bán phải tắt theo dõi tồn; nguyên liệu phải bật tồn kho.','Menu item must be non-stock; ingredients must track inventory.'),
        form('recipe',select('finished_id',options(untracked))+
          '<div data-v5-ingredients><div class="v5-formrow" data-v5-ingredient>'+
          select('ingredient_id',options(tracked))+
          '<label>'+tx('Đơn vị tiêu hao','Usage units')+'<input type="number" name="quantity" min="1" max="100000" value="1" required></label></div></div>'+
          '<button type="button" data-v5-add-ingredient>'+tx('+ Thêm nguyên liệu','+ Add ingredient')+'</button>'+
          '<p class="v5-note">'+tx('Lưu thay toàn bộ công thức; tối đa 30 nguyên liệu.','Save replaces the full recipe; up to 30 ingredients.')+'</p>',
          tx('Lưu công thức','Save recipe'))+
        list('recipes',x=>E((x.details.ingredients||[]).map(i=>(product.find(p=>p.id===i.product_id)?.name||i.product_id)+' ×'+i.quantity).join(' · '))));
      }
    }
    if(role!=='staff'){
      output+=box(tx('Lịch ca nhân viên','Staff shifts'),
        tx('Lập ca, tránh trùng lịch theo nhân viên.','Schedule employees with conflict protection.'),
        form('shift',select('employee_id',options(staff))+
          '<div class="v5-formrow">'+select('branch_id',brOptions)+
          '<label>'+tx('Bắt đầu','Start')+'<input name="start_at" type="datetime-local" required></label>'+
          '<label>'+tx('Kết thúc','End')+'<input name="end_at" type="datetime-local" required></label></div>',
          tx('Tạo ca làm','Create shift'))+
        list('shifts',x=>E(x.scheduled_at?.slice(0,16)||'')+' → '+E(x.ends_at?.slice(0,16)||''),x=>
          x.status==='scheduled'?btn('shift-cancel',x.id,tx('Hủy ca','Cancel shift')):''));
      output+=box(tx('Nháp email / Zalo','Email / Zalo drafts'),
        tx('Lưu mẫu tin. Chưa gửi đến khách.','Create drafts; no messages are sent.'),
        form('notification',select('channel',opt('email','Email')+opt('zalo','Zalo'))+
          input('recipient','Email / tài khoản nhận')+
          '<textarea name="message" minlength="5" maxlength="600" placeholder="'+tx('Nội dung thông báo','Message')+'" required></textarea>',
          tx('Lưu nháp','Save draft'))+
        list('notifications',x=>E(x.details.channel||'')+' • '+E(x.details.recipient||'')+' • '+tx('Chưa gửi','Not sent')));
    }
    if(business().active_modules?.includes('products')){
      var inventory=data.inventory||{};
      var branchBalances=inventory.balances||[];
      output+=box(tx('Tồn kho từng chi nhánh','Per-branch inventory'),
        tx('Kích hoạt riêng khi đã đối chiếu tồn kho thực tế.','Activate only after physically reconciling initial stock.'),
        inventory.enabled?
        '<p class="v5-note">'+tx('Đang bật sổ tồn kho theo chi nhánh.','Per-location stock tracking is active.')+'</p>'+
        branchBalances.slice(0,35).map(x=>'<div class="v5-entry"><strong>'+
           E(product.find(p=>p.id===x.product_id)?.name||'Sản phẩm')+'</strong><p>'+
           E(branches.find(y=>y.id===x.branch_id)?.name||'Chi nhánh')+
           ' • '+E(x.quantity)+' '+tx('đơn vị','units')+'</p></div>').join(''):
        '<p class="v5-note">'+tx('Chưa bật kho riêng; Product.stock hiện là tồn toàn doanh nghiệp.',
          'Not enabled; Product.stock is currently business-wide.')+'</p>'+
        (role==='owner'&&business().active_modules?.includes('multi_branch')?
          btn('activate-inventory','',''+tx('Kích hoạt kho từng chi nhánh','Activate branch inventory')):''))+
      box(tx('Phiếu điều chuyển chi nhánh','Branch transfer requests'),
        inventory.enabled?
          tx('Khi xác nhận nhận hàng, số lượng chuyển giữa kho nguồn và kho đích; tổng tồn doanh nghiệp không đổi.',
             'Receiving updates source and destination stock, preserving business-wide total.'):
          tx('Đang dùng sổ kho chung. Hãy bật kho chi nhánh sau khi kiểm kê thực tế.',
             'Using shared stock. Enable branch inventory only after a physical count.'),
        role==='staff'?'':form('transfer',select('product_id',options(tracked))+
          '<div class="v5-formrow"><label>'+tx('Kho nguồn','From')+select('from_branch_id',brOptions)+'</label>'+
          '<label>'+tx('Kho đích','To')+select('to_branch_id',brOptions)+'</label></div>'+
          input('quantity','Số lượng chuyển','number'),tx('Tạo phiếu chuyển','Create transfer request'))+
        list('transfers',x=>E(x.details.quantity)+' '+tx('đơn vị','units')+' • '+
          E(branches.find(z=>z.id===x.details.from_branch_id)?.name||'')+' → '+
          E(branches.find(z=>z.id===x.details.to_branch_id)?.name||''),x=>
          role==='staff'?'':x.status==='requested'?
            btn('transfer',x.id,tx('Duyệt','Approve'),'approved')+
            btn('transfer',x.id,tx('Hủy','Cancel'),'cancelled'):
            x.status==='approved'?btn('transfer',x.id,tx('Đã nhận','Received'),'received'):''));
    }
    if(industry==='online'&&business().active_modules?.includes('fulfillment')){
      var deliveries=entries('deliveries');
      output+=box(tx('Theo dõi giao hàng nội bộ','Delivery tracking'),
        tx('Nhật ký vận chuyển nội bộ; không đồng bộ với hãng vận chuyển.','Internal events only; no carrier sync.'),
        form('delivery',select('item_id',deliveries.map(x=>opt(x.id,x.title+' · '+x.status)))+
          select('event',['picked_up','in_transit','delayed','delivery_attempt','delivered','failed']
            .map(x=>opt(x,x.replaceAll('_',' '))).join(''))+
          input('tracking_number','Mã vận đơn (nếu có)')+
          '<textarea name="note" maxlength="240" placeholder="'+tx('Diễn biến giao hàng','Delivery note')+'"></textarea>',
          tx('Ghi nhật ký giao','Record delivery event'))+
        list('deliveries',x=>E(x.details.tracking_number||'')+' • '+E((x.details.tracking_events||[]).length)+
          ' '+tx('sự kiện','events')));
    }
    if(role!=='staff'&&business().active_modules?.includes('orders')){
      var bal=balances(),points=bal.reduce((a,x)=>a+x.points,0);
      output+=box(tx('Khách hàng thân thiết','Loyalty points'),
        tx('1 điểm / 10.000đ đơn đã thanh toán; không quy đổi tiền tự động.','1 point per 10,000 VND paid; no automatic cash redemption.'),
        '<p class="v5-large">'+E(points)+' '+tx('điểm đang lưu','recorded points')+'</p>'+
        form('redeem',select('customer_id',customers.map(x=>opt(x.id,x.name+' • '+
          (bal.find(a=>a.customer_id===x.id)?.points||0)+' điểm')))+
          input('points','Số điểm đổi thưởng','number')+
          '<textarea name="note" minlength="4" maxlength="200" placeholder="'+tx('Lý do / quà tặng','Reward description')+'" required></textarea>',
          tx('Ghi nhận đổi thưởng','Record reward redemption'))+
        (data.loyalty?.transactions||[]).slice(0,15).map(x=>row(x,E(x.details.points)+' điểm')).join(''));
    }
    if(role!=='staff'&&business().active_modules?.includes('orders')){
      var close=data.cashierClose||{},paid=close.paid_at_day||{},
        source=close.created_at_day||{};
      output+=box(tx('Đối soát cuối ngày · xem trước','Daily closing · preview'),
        tx('Theo ngày nhận tiền. Phương thức do nhân viên xác nhận, chưa kiểm kê tiền mặt hoặc xác minh ngân hàng.','Uses paid-at time. Tender methods are manually declared, without cash counting or bank verification.'),
        form('close-preview',
          '<div class="v5-formrow"><label>'+tx('Ngày','Date')+
          '<input type="date" name="day" required value="'+E(closingDay)+'"></label>'+
          '<label>'+tx('Chi nhánh','Branch')+
          '<select name="branch_id">'+opt('',tx('Tất cả chi nhánh','All branches'),closingBranch)+
          branches.map(x=>opt(x.id,x.name,closingBranch)).join('')+'</select></label></div>',
          tx('Xem đối soát','View summary'))+
        '<div class="v5-figures">'+
        '<span>'+tx('Đơn nhận tiền trong ngày','Paid that day')+'<b>'+E(paid.count||0)+'</b></span>'+
        '<span>'+tx('Tổng tiền đánh dấu đã nhận','Marked received')+'<b>'+V(paid.amount_vnd||0)+'</b></span>'+
        '<span>'+tx('Đơn mới còn mở','New orders still open')+'<b>'+E(source.open_now||0)+'</b></span>'+
        '<span>'+tx('Đơn còn mở toàn chi nhánh','All outstanding orders')+'<b>'+E(close.outstanding_now_count||0)+'</b></span>'+
        '<span>'+tx('Tiền mặt khai báo','Manually recorded cash')+'<b>'+V(close.manual_cash_vnd||0)+'</b></span>'+
        '<span>'+tx('Chuyển khoản khai báo','Manually recorded transfers')+'<b>'+V(close.manual_bank_transfer_vnd||0)+'</b></span>'+
        '<span>'+tx('Chưa rõ phương thức (đơn cũ)','Unknown method (older checks)')+'<b>'+V(close.unknown_payment_method_vnd||0)+'</b></span></div>'+
        '<p class="v5-note">'+tx('⚠ Phương thức chỉ ghi nhận thủ công, chưa đối soát ngân hàng hay đếm tiền trong két. Không phải chốt ca chính thức.',
          '⚠ Tender types are self-reported, not bank-verified or cash-counted. Not a formal shift close.')+'</p>',true);
    }
    if(role!=='staff'&&business().active_modules?.includes('insights')){
      var fin=data.finance||{};
      output+=box(tx('Thu chi và lợi nhuận ước tính','Expenses and estimated profit'),
        tx('Giá vốn dùng giá hiện tại; chưa phải báo cáo kế toán.','COGS is based on current costs; not an accounting statement.'),
        '<div class="v5-figures"><span>'+tx('Doanh thu','Revenue')+'<b>'+V(fin.revenue_vnd||0)+'</b></span>'+
        '<span>'+tx('Giá vốn ước tính','Estimated COGS')+'<b>'+V(fin.estimated_cogs_vnd||0)+'</b></span>'+
        '<span>'+tx('Chi phí','Expenses')+'<b>'+V(fin.operating_expenses_vnd||0)+'</b></span>'+
        '<span>'+tx('Lợi nhuận ước tính','Estimated profit')+'<b>'+V(fin.estimated_profit_vnd||0)+'</b></span></div>'+
        form('expense',select('category',['rent','staff','utilities','ingredients','marketing','other']
          .map(x=>opt(x,x)).join(''))+input('amount_vnd','Số tiền VND','number')+
          '<textarea name="note" minlength="3" maxlength="200" placeholder="'+tx('Nội dung chi','Expense details')+'" required></textarea>',
          tx('Ghi chi phí','Record expense'))+
        (fin.expenses||[]).slice(0,10).map(x=>row(x,V(x.details.amount_vnd||0))).join(''));
    }
    return output;
  }
  function render(){return '<div id="ez-operations-v5" class="v5-wrap"><div class="v5-loading" role="status">'+
    tx('Đang tải Lễ tân & xếp bàn...','Loading Front Desk...')+'</div></div>'}
  function paint(){
    var root=document.getElementById('ez-operations-v5');
    if(!root||current!==business().id)return;
    var errors=Object.keys(data).filter(x=>x.endsWith('Error'));
    root.innerHTML='<header class="v5-intro"><h2>'+(business().industry==='fnb'?tx('Lễ tân & xếp bàn','Front Desk & Seating'):tx('Công cụ quản lý','Management Tools'))+'</h2>'+
      '<p>'+(business().industry==='fnb'?
        tx('Tiếp đón khách, danh sách chờ, yêu cầu đặt cọc. Các công cụ kho, nhân sự và thu chi nằm bên dưới. Chưa tự động gửi thông báo hoặc thu tiền.',
           'Host seating, waitlist and deposit requests. Inventory, staff and financial tools follow below. No automatic messaging or payment.')
        :tx('Các công cụ nội bộ của doanh nghiệp, ngoài quy trình bán hàng chính.','Business administration beyond the main sales workflow.'))+'</p>'+
      (business().industry==='fnb'?'<div class="v5-host-shortcuts"><button class="btn sm secondary" type="button" data-action="tab" data-value="reservations">📅 '+tx('Đặt bàn trước','Reservations')+'</button><button class="btn sm secondary" type="button" data-action="tab" data-value="tables">▦ '+tx('Sơ đồ bàn','Floorplan')+'</button><button class="btn sm secondary" type="button" data-action="tab" data-value="kitchen">☕ '+tx('Bếp & pha chế','Kitchen & Bar')+'</button></div>':'')+
      '<div class="v5-poll-status" id="v5-poll-status" aria-live="polite"></div>'+
      (errors.length?'<p class="v5-warning">'+tx('Một số dữ liệu chưa tải được.','Some data could not be loaded.')+'</p>':'')+
      '</header><div class="v5-grid">'+sections()+'</div>';
  }
  async function mount(){
    var b=business();if(!b.id)return;
    current=b.id;var serial=++generation;data={};
    var jobs=[];
    function add(key,path){jobs.push(load(key,path))}
    add('sync');add('transfers');if(b.active_modules?.includes('products'))add('inventory');if(b.role!=='staff'){add('staff');add('shifts');add('notifications')}
    if(b.industry==='fnb'&&b.active_modules.includes('tables')){
      add('waitlist');if(b.role!=='staff'){add('deposits');add('recipes')};add('reservations','/businesses/'+bid()+'/reservations');
    }
    if(b.industry==='online'&&b.active_modules.includes('fulfillment'))
      add('deliveries','/businesses/'+bid()+'/industry/delivery');
    if(b.role!=='staff'&&b.active_modules.includes('orders'))add('loyalty');
    if(b.role!=='staff'&&b.active_modules.includes('insights'))add('finance');
    if(b.role!=='staff'&&b.active_modules.includes('orders')){
      var params=new URLSearchParams({day:closingDay});
      if(closingBranch)params.set('branch_id',closingBranch);
      add('cashierClose','/businesses/'+bid()+'/cashier/close-preview?'+params);
    }
    await Promise.allSettled(jobs);
    if(serial!==generation||current!==business().id)return;
    paint();
    if(poll)clearInterval(poll);
    poll=setInterval(async function(){
      if(document.hidden||current!==business().id||state().tab!=='operations')return;
      try{
        var x=await api(url('sync')),el=document.getElementById('v5-poll-status');
        var editing=!!document.activeElement?.closest('#ez-operations-v5 form');
        if(x.version&&data.sync?.version&&x.version!==data.sync.version&&!editing){
          return mount(); // Only redraw when an actual tenant row changed.
        }
        data.sync=x;
        if(el)el.textContent=tx('Đồng bộ 15 giây/lần','15s sync')+
          ' • '+Object.entries(x.active_counts||{}).map(a=>a[0]+': '+a[1]).join(' · ');
      }catch(_){var e=document.getElementById('v5-poll-status');if(e)e.textContent=tx('Đang mất kết nối đồng bộ','Sync unavailable')}
    },15000);
  }
  async function mutate(kind,body,id,status){
    var path=kind,method='POST';
    if(kind==='recipe'){path='recipes/'+encodeURIComponent(body.finished_id);method='PUT';
      body={ingredients:body.ingredients};}
    if(kind==='waitlist')path=id?'waitlist/'+encodeURIComponent(id)+'/status':'waitlist';
    if(kind==='shift')path='shifts';
    if(kind==='transfer')path=id?'transfers/'+encodeURIComponent(id)+'/status':'transfers';
    if(kind==='shift-cancel')path='shifts/'+encodeURIComponent(id)+'/cancel';
    if(kind==='notification')path='notifications';
    if(kind==='redeem')path='loyalty/redeem';
    if(kind==='expense')path='expenses';
    if(kind==='deposit')path='deposits';
    if(kind==='delivery')path='deliveries/'+encodeURIComponent(body.item_id)+'/events';
    if(kind==='activate-inventory'){path='inventory/activate';body={confirmation:'ALLOCATE_ALL_TO_PRIMARY_BRANCH'};}
    if(id&&(kind==='waitlist'||kind==='transfer'))body={status:status};
    if(['waitlist','transfer','shift','notification','redeem','expense','deposit'].includes(kind)&&!id)body.request_id=uuid();
    for(var number of ['party_size','quantity','points','amount_vnd'])if(body[number]!=null)body[number]=Number(body[number]);
    for(var dateField of ['start_at','end_at'])if(body[dateField])body[dateField]=new Date(body[dateField]).toISOString();
    return api(url(path),{method:method,body:JSON.stringify(body)});
  }
  document.addEventListener('submit',function(ev){
    var form=ev.target.closest('form[data-v5-form]');
    if(!form||state().tab!=='operations')return;
    ev.preventDefault();ev.stopPropagation();if(busy)return;
    var kind=form.dataset.v5Form,button=form.querySelector('[type=submit]');
    var values=Object.fromEntries(new FormData(form));
    if(kind==='close-preview'){
      busy=true;if(button)button.disabled=true;
      closingDay=values.day;closingBranch=values.branch_id||'';
      var query=new URLSearchParams({day:closingDay});
      if(closingBranch)query.set('branch_id',closingBranch);
      load('cashierClose','/businesses/'+bid()+'/cashier/close-preview?'+query)
        .then(()=>paint()).finally(()=>{busy=false;if(button)button.disabled=false});
      return;
    }
    if(kind==='recipe')values.ingredients=Array.from(form.querySelectorAll('[data-v5-ingredient]')).map(row=>({
      product_id:row.querySelector('select[name=ingredient_id]').value,
      quantity:Number(row.querySelector('input[name=quantity]').value)
    }));
    busy=true;if(button)button.disabled=true;
    mutate(kind,values).then(function(){toast(tx('Đã lưu thành công','Saved'));return mount()})
      .catch(e=>toast(e.message,true)).finally(function(){busy=false;if(button)button.disabled=false});
  },true);
  document.addEventListener('click',function(ev){
    var add=ev.target.closest('button[data-v5-add-ingredient]');
    if(add&&state().tab==='operations'){
      ev.preventDefault();ev.stopPropagation();
      var wrap=add.closest('form')?.querySelector('[data-v5-ingredients]');
      var template=wrap?.querySelector('[data-v5-ingredient]');
      if(wrap&&template&&wrap.children.length<30){
        var copy=template.cloneNode(true);
        copy.querySelector('input[name=quantity]').value='1';
        wrap.append(copy);
      }
      return;
    }
    var button=ev.target.closest('button[data-v5-action]');
    if(!button||state().tab!=='operations')return;
    ev.preventDefault();ev.stopPropagation();if(busy||button.disabled)return;
    busy=true;button.disabled=true;
    var kind=button.dataset.v5Action;
    if(kind==='activate-inventory'&&!confirm(tx(
      'Xác nhận phân bổ toàn bộ tồn kho hiện có vào CHI NHÁNH CHÍNH? Kiểm kê và chuyển kho sau khi bật.',
      'Allocate ALL current stock to the PRIMARY branch? Reconcile physical quantities afterward.'))){
      busy=false;button.disabled=false;return;
    }
    mutate(kind,{},button.dataset.id,button.dataset.status)
      .then(function(){toast(tx('Đã cập nhật','Updated'));return mount()})
      .catch(e=>toast(e.message,true)).finally(function(){busy=false;button.disabled=false});
  },true);
  return {render:render,mount:mount,invalidate:function(){generation++;current='';data={};if(poll){clearInterval(poll);poll=null}}};
};
})();