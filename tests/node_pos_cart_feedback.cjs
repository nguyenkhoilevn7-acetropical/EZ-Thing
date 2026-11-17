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
assert.match(register.render(),/ezreg-category-glyph/,
  "category rail must be touch-first and icon-led");
function click(action,value,button=productButton){
  button.dataset={ezreg:action,value};
  listeners.click({target:button,preventDefault(){},stopPropagation(){}});
}
click("product","tea");
assert.match(grid.innerHTML,/Trong giỏ: 1/,"tile must confirm item count");
assert.match(cart.innerHTML,/Chi tiết món/);
assert.match(cart.innerHTML,/Đơn giá/);
assert.match(cart.innerHTML,/TRA-01/);
assert.match(cart.innerHTML,/Tiền món/);
assert.match(cart.innerHTML,/Size \/ topping/);
assert.match(cart.innerHTML,/35\.000đ/);
assert.match(cart.innerHTML,/data-method="cash"/,"cash shortcut must be visible");
assert.match(cart.innerHTML,/data-method="bank_transfer"/,
  "transfer shortcut must be visible");
assert.match(cart.innerHTML,/Payment gateway not connected|Chưa kết nối cổng thanh toán/,
  "unsupported card gateway must stay disabled");
assert.match(notice.textContent,/Đã thêm Trà sữa trân châu/);
// A rapid unintended double tap must not produce a duplicate unit.
click("product","tea");
assert.match(grid.innerHTML,/Trong giỏ: 1/);
const lineId=cart.innerHTML.match(/data-line-id="([^"]+)"/)?.[1];
assert.ok(lineId,"cart must expose a stable line ID");
click("increase",lineId);
assert.match(grid.innerHTML,/Trong giỏ: 2/);
assert.match(cart.innerHTML,/70\.000đ/);
click("decrease",lineId);
assert.match(grid.innerHTML,/Trong giỏ: 1/);
click("remove",lineId);
assert.doesNotMatch(grid.innerHTML,/Trong giỏ: 1/);
assert.match(cart.innerHTML,/Chưa có món nào/);
click("flip-ticket","");
assert.match(nodes["ez-register"].outerHTML,/ezreg-ticket-left/,
  "layout toggle must put ticket on left without clearing draft");
assert.match(register.render(),/35\.000đ|Đơn đang tạo/);
console.log("PASS: POS add-to-cart feedback, rapid tap guard, quantity, remove, and detailed totals");
