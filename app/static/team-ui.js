/* Tenant team management — role-aware view, with escaped display values. */
(function(){
"use strict";
window.EZTeamUI={
  render(data,E,branches=[]){
    const en=window.EZI18N?.language()==='en';
    const t=(vi,english)=>en?english:vi;
    if(!data)return '<section class="surface pad">'+t("Đang tải danh sách nhân sự...","Loading team...")+'</section>';
    const rows=data.members||[],pending=data.invitations||[];
    return `<section class="surface pad ez-team">
       <div class="section-header"><div><h2>👥 ${t('Nhân sự & phân quyền','Team & permissions')}</h2>
         <p>${t('Mỗi nhân viên có tài khoản riêng và được chỉ định đúng tác vụ, chi nhánh, trạm chế biến.',
                     'Each employee has an account and an assigned task, branch and prep station.')}</p></div>
       </div>
       <div class="ez-team-roles">
         <article><b>${t('Chủ doanh nghiệp','Owner')}</b><span>${t('Toàn quyền; billing, thương hiệu, nhân sự','Full access: billing, branding, team')}</span></article>
         <article><b>${t('Quản lý','Manager')}</b><span>${t('Đơn hàng, sản phẩm, kho, lịch và báo cáo','Orders, catalog, inventory, bookings, reports')}</span></article>
         <article><b>${t('Nhân viên','Staff')}</b><span>${t('Tạo đơn, ghi khách, xử lý công việc','Orders, customers and operational workflows')}</span></article>
       </div>
       <form id="team-invite-form" class="ez-team-invite">
         <label>${t('Email mời','Invite by email')}<input required type="email" name="email" maxlength="254" placeholder="staff@example.com" autocomplete="email"></label>
         <label>${t('Vai trò','Role')}<select name="role"><option value="staff">${t('Nhân viên','Staff')}</option><option value="manager">${t('Quản lý','Manager')}</option></select></label>
         <button class="btn" type="submit">+${t(' Tạo lời mời',' Create invitation')}</button>
       </form>
       <p class="subtle">${t('Lời mời có hiệu lực 48 giờ. Link chỉ hiển thị một lần; phải gửi riêng cho đúng người.',
                             'Invitations expire after 48 hours. Copy and privately share the one-time link.')}</p>
       <div class="ez-team-preview-launch">
         <div><strong>🖥 ${t('Xem thử từng màn hình nhân viên','Preview each employee screen')}</strong>
         <p>${t('Order · Bếp · Pha chế · Thu ngân · Lễ tân. Chỉ xem, không ghi đơn thật.','Order · Kitchen · Bar · Cashier · Host. Read-only, no actual transactions.')}</p></div>
         <button type="button" class="btn" data-ezws="preview-picker">${t('Xem 5 màn hình','Preview 5 screens')}</button></div>
       <h3>${t('Thành viên','Members')} (${rows.length})</h3>
       <div class="ez-team-list">${rows.map(m=>`<div class="ez-team-person">
         <div class="b-avatar">${E((m.name||'U')[0])}</div>
         <div class="ez-team-person-name"><strong>${E(m.name)}</strong><span>${E(m.email)}</span></div>
         <span class="pill ${m.role==='owner'?'blue':''}">${E(m.role)}</span>
         ${m.role==='staff'?`<div class="ez-team-duty" data-staff="${E(m.id)}">
           <label>${t('Tác vụ','Task')}
             <select data-team-duty="${E(m.id)}" aria-label="${t('Phân công tác vụ','Task assignment')}">
               ${[['order','Nhận order'],['kitchen','Bếp'],['bar','Pha chế'],['cashier','Thu ngân'],['host','Lễ tân']]
                 .map(([id,name])=>`<option value="${id}" ${(m.duty?.mode||'order')===id?'selected':''}>${t(name,id)}</option>`).join('')}
             </select></label>
           <label>${t('Chi nhánh','Branch')}<select data-team-duty-branch="${E(m.id)}">
             <option value="">${t('Tất cả chi nhánh','All branches')}</option>
             ${branches.map(b=>`<option value="${E(b.id)}" ${b.id===m.duty?.branch_id?'selected':''}>${E(b.name)}</option>`).join('')}
           </select></label>
           <label>${t('Trạm','Station')}<select data-team-duty-station="${E(m.id)}">
             ${[['all','Theo tác vụ'],['kitchen','Bếp (nóng + lạnh)'],['hot','Bếp nóng'],['cold','Bếp lạnh'],['expo','Ra món'],['bar','Quầy bar']]
               .map(([id,name])=>`<option value="${id}" ${(m.duty?.station||'all')===id?'selected':''}>${t(name,id)}</option>`).join('')}
           </select></label>
           <button type="button" class="btn sm" data-action="team-duty-save" data-value="${E(m.id)}">${t('Lưu phân công','Save assignment')}</button>
           <small>${m.duty?.assigned?t('Đã phân công','Assigned'):t('Chưa phân công: mặc định chỉ nhận order','Unassigned: order only')}</small>
         </div>`:''}
         ${m.role!=='owner'?`<select aria-label="${t('Phân quyền','Change role')}" data-team-role="${E(m.id)}">
           <option value="staff" ${m.role==='staff'?'selected':''}>${t('Nhân viên','Staff')}</option>
           <option value="manager" ${m.role==='manager'?'selected':''}>${t('Quản lý','Manager')}</option>
         </select><button class="btn secondary sm" data-action="team-remove" data-value="${E(m.id)}">${t('Xóa','Remove')}</button>`:''}
       </div>`).join('')}</div>
       <h3>${t('Lời mời đang chờ','Pending invitations')} (${pending.length})</h3>
       <div class="ez-team-list">${pending.map(i=>`<div class="ez-team-person">
         <div class="ez-team-person-name"><strong>${E(i.email)}</strong>
         <span>${E(i.role)} · ${E(new Date(i.expires_at).toLocaleDateString(en?'en-US':'vi-VN'))}</span></div>
         <button class="btn secondary sm" data-action="team-revoke" data-value="${E(i.id)}">${t('Thu hồi','Revoke')}</button>
       </div>`).join('')||`<p class="muted">${t('Không có lời mời đang chờ','No pending invitations')}</p>`}</div>
    </section>`;
  }
};
})();
