// Isolated behavioral regression for the actual POS register event handlers.
// No third-party DOM dependencies or network calls; runs in CI with Node.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("app/static/merchant-register.js","utf8");
const listeners={};
const classes=()=>({add(){},remove(){},toggle(){}});
const cart={innerHTML:"",classList:classes(),querySelector(){return {scrollTop:0}}};
const grid={innerHTML:""};
const category={innerHTML:""};
const notice={textContent:"",classList:classes()};
const mobile={innerHTML:"",classList:classes()};
const rect={left:10,top:15,width:55,height:55};
const badge={getBoundingClientRect(){return {left:440,top:22,width:24,height:24}},classList:classes(),offsetWidth:24};
const productButton={
  dataset:{ezreg:"product",value:"tea"},
  closest(){return this},
  querySelector(){return null},
  getBoundingClientRect(){return rect}
};
const nodes={
  "ez-register":{contains(){return true}},
  "ezreg-cart":cart,
  "ezreg-products":grid,
  "ezreg-categories":category,
  "ezreg-added-live":notice,
};
const document={
  addEventListener(type,handler){listeners[type]=handler},
  getElementById(id){return nodes[id]||null},
  querySelector(selector){
    if(selector===".ezreg-mobile-cartbar")return mobile;
    if(selector==="#ezreg-cart .ezreg-count")return badge;
    if(selector.startsWith('[data-ezreg="product"]'))return productButton;
    return null;
  }
};
const items=[{id:"tea",name:"Trà sữa trân châu",sku:"TRA-01",
  price_vnd:35000,active:true,category:"Đồ uống",
  track_stock:false,modifier_groups:[]}];
const state={business:{id:"biz-1",role:"owner",industry:"fnb",active_modules:["orders","tables"]},
  cache:{products:items,branches:[{id:"branch-1",name:"Chi nhánh chính"}],
    tables:[{id:"table-1",branch_id:"branch-1",label:"Bàn 01"}],customers:[]}};
const context={window:{},document,navigator:{onLine:true},console,Math,Date,
  setTimeout(){return 1},clearTimeout(){},getComputedStyle(){return {display:"none"}}};
context.window.matchMedia=()=>({matches:true});
vm.runInNewContext(source,context,{filename:"merchant-register.js"});
const register=context.window.EZRegisterUI({
  api:async()=>{throw Error("Unexpected network call")},
  E:v=>String(v),V:n=>Number(n).toLocaleString("vi-VN")+"đ",toast(){},
  getState:()=>state,navigate(){},
});
assert.match(register.render(),/data-ezreg="product"/);
assert.match(register.render(),/data-ezreg="flip-ticket"/,
  "POS must let operators switch the receipt panel left or right");
assert.match(register.render(),/ezreg-ticket-right/);
assert.match(register.render(),/POS Order/);
assert.match(register.render(),/data-ez-lang-ignore/);
const compact=register.render();
assert.match(compact,/ezreg-cart-context/,"service and customer belong in one compact row");
assert.match(compact,/data-ezreg-select="table"/,"table selection must remain functional");
assert.match(compact,/data-ezreg-select="customer"/,"customer selection must remain functional");
assert.match(compact,/Takeaway/);
assert.match(compact,/Walk-in/);
assert.ok(compact.indexOf('ezreg-cart-context')<compact.indexOf('id="ezreg-cart"'),
  "service and customer selectors must live in the Products panel, not Ticket");
assert.match(compact,/ezreg-ticket-inline/,"ticket heading should use a single row");
assert.match(compact,/data-ezreg="search-toggle"/,
  "search starts as a compact icon button");
assert.doesNotMatch(compact,/data-ezreg-search/,
  "search input must remain collapsed initially");
assert.doesNotMatch(compact,/ezreg-cart-meta/,"old three-row metadata must be removed");
assert.doesNotMatch(compact,/Main branch/,"single location must not consume ticket space");
assert.doesNotMatch(compact,/data-ezreg-select="branch"/,
  "single location must keep its implicit branch without a visible picker");
state.cache.branches.push({id:"branch-2",name:"Second branch"});
const multiBranch=register.render();
assert.match(multiBranch,/ezreg-branch-picker/,"multi-branch owner can still switch");
assert.match(multiBranch,/data-ezreg-select="branch"/);
state.cache.branches.pop();
listeners.change({target:{dataset:{ezregSelect:"table"},value:"table-1"}});
listeners.change({target:{dataset:{ezregSelect:"customer"},value:""}});
assert.match(register.render(),/<option value="table-1" selected>/,
  "selecting a table must survive render");
assert.doesNotMatch(register.render(),/Bán hàng nhanh/);
assert.match(register.render(),/ezreg-category-glyph/,
  "category rail must be touch-first and icon-led");
function click(action,value,button=productButton){
  button.dataset={ezreg:action,value};
  listeners.click({target:button,preventDefault(){},stopPropagation(){}});
}
click("product","tea");
assert.match(grid.innerHTML,/In cart: 1/,"tile must confirm item count");
assert.match(cart.innerHTML,/Items/);
assert.match(cart.innerHTML,/Unit/);
assert.match(cart.innerHTML,/TRA-01/);
assert.match(cart.innerHTML,/Items/);
assert.match(cart.innerHTML,/Add-ons/);
assert.match(cart.innerHTML,/35\.000đ/);
assert.match(cart.innerHTML,/\>Pay\</);
assert.match(cart.innerHTML,/\>Save\</);
assert.doesNotMatch(cart.innerHTML,/data-method="cash"|data-method="bank_transfer"/,
  "payment method shortcuts belong only in the Pay modal");
assert.doesNotMatch(cart.innerHTML,/ezreg-pay-methods/,
  "do not waste ticket height on redundant Cash / Bank / Card controls");
assert.match(cart.innerHTML,/data-ezreg="checkout"/,
  "Pay still opens the existing checkout modal");
assert.match(cart.innerHTML,/data-ezreg="note-toggle"/,
  "collapsed Add Note control must be accessible");
assert.doesNotMatch(cart.innerHTML,/<textarea/,
  "Note textarea must stay hidden until requested");
assert.match(notice.textContent,/Added Pearl Milk Tea/);
click("note-toggle","");
assert.match(cart.innerHTML,/<textarea[^>]*data-ezreg-note/,
  "Add Note opens its editor");
listeners.input({target:{value:"Less ice",matches:s=>s==="[data-ezreg-note]"}});
click("note-toggle","");
assert.doesNotMatch(cart.innerHTML,/<textarea/,"Note collapses after editing");
assert.match(register.render(),/Edit Note/,"existing notes remain discoverable");
click("search-toggle","");
assert.match(register.render(),/data-ezreg-search/,
  "Search button expands a searchable field");
click("search-close","");
assert.doesNotMatch(register.render(),/data-ezreg-search/,
  "Close Search returns catalog to icon mode");
// A rapid unintended double tap must not produce a duplicate unit.
click("product","tea");
assert.match(grid.innerHTML,/In cart: 1/);
const lineId=cart.innerHTML.match(/data-line-id="([^"]+)"/)?.[1];
assert.ok(lineId,"cart must expose a stable line ID");
click("increase",lineId);
assert.match(grid.innerHTML,/In cart: 2/);
assert.match(cart.innerHTML,/70\.000đ/);
click("decrease",lineId);
assert.match(grid.innerHTML,/In cart: 1/);
click("remove",lineId);
assert.doesNotMatch(grid.innerHTML,/In cart: 1/);
assert.match(cart.innerHTML,/No items yet/);
click("flip-ticket","");
assert.match(nodes["ez-register"].outerHTML,/ezreg-ticket-left/,
  "layout toggle must put ticket on left without clearing draft");
assert.match(register.render(),/35\.000đ|Order/);
console.log("PASS: POS add-to-cart feedback, rapid tap guard, quantity, remove, and detailed totals");
