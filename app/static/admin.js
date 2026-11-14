(async()=>{
 'use strict';
 const target=document.getElementById('admin-root');
 try{
  const r=await fetch('/api/admin/summary',{credentials:'same-origin',cache:'no-store'});
  if(!r.ok)throw new Error('restricted');
  const d=await r.json();
  target.innerHTML='<div class="customer-logo" style="margin:auto">e.</div><h2>EZ Thing • Super Admin</h2><p>Thông tin tổng quan ở chế độ chỉ đọc. Chưa có thao tác quản lý tài khoản hoặc thanh toán thuê bao.</p><div class="receipt-id">Doanh nghiệp: '+Number(d.businesses)+' · Tài khoản: '+Number(d.users)+' · Đơn hàng: '+Number(d.orders)+'</div>';
 }catch{
  target.innerHTML='<div class="customer-logo" style="margin:auto">e.</div><h2>Quyền truy cập bị giới hạn</h2><p>Khu vực này chỉ dành cho tài khoản Super Admin được cho phép trên máy chủ. Phiên DEMO không có quyền truy cập. Đây chưa phải hệ thống quản trị SaaS hoàn chỉnh.</p><a href="/" class="info-link">← Về trang chủ</a>';
 }
})();