/* Compact, semantic merchant order cards. Keeps the existing action dispatcher. */
(() => {
  'use strict';
  function renderList(orders, { E, V, D, status, I }) {
    const cards = orders.map(o => {
      const shortId = E(String(o.id || '').slice(0, 8).toUpperCase());
      const id = E(o.id);
      const match = E([o.id, ...(o.items || []).map(item => item.name)].join(' ').toLocaleLowerCase('vi'));
      const products = E((o.items || []).map(item => item.name + ' ×' + item.quantity).join(', '));
      const age = Number.isFinite(new Date(o.created_at).getTime())
        ? Math.max(0, Math.floor((Date.now() - new Date(o.created_at).getTime()) / 60000)) : 0;
      const ageMarkup = o.status === 'open'
        ? `<span class='order-card-age'>${I('clock', 'sm')} Đơn mở ${age} phút</span>` : '';
      const actions = o.status === 'open'
        ? `<button type='button' class='btn sm order-card-pay' data-action='confirm-paid' data-value='${id}'>${I('check', 'sm')} Đã nhận tiền</button>`
          + `<button type='button' class='btn sm ghost order-card-cancel' data-action='cancel-order' data-value='${id}'>Hủy đơn</button>`
        : '';
      return `<article class='order-card' role='listitem' data-match='${match}' aria-label='Đơn hàng #${shortId}'>
        <div class='order-card-top'>
          <div class='order-card-identity'>
            <span class='order-card-label'>Mã đơn</span>
            <strong class='order-card-id'>#${shortId}</strong>
            <time class='order-card-time' datetime='${E(o.created_at || '')}'>${I('clock', 'sm')}${E(D(o.created_at))}</time>
            ${ageMarkup}
          </div>
          <div class='order-card-status'>${status(o.status)}</div>
        </div>
        <div class='order-card-products'>
          <span class='order-card-label'>Sản phẩm</span>
          <p>${products || '—'}</p>
        </div>
        <div class='order-card-totals'>
          <div class='order-card-money'><span class='order-card-label'>Giá trị</span><strong>${E(V(o.total_vnd))}</strong></div>
        </div>
        <div class='order-card-footer' aria-label='Thao tác đơn hàng'>
          <button type='button' class='btn sm secondary order-card-details' data-action='order-detail' data-value='${id}'>${I('receipt', 'sm')} Chi tiết</button>
          ${actions}
        </div>
      </article>`;
    }).join('');
    return `<div class='order-card-layout' role='region' aria-label='Danh sách đơn hàng'>
      <div class='order-card-list' id='order-rows' role='list'>${cards}</div>
    </div>`;
  }
  window.EZOrderCards = Object.freeze({ renderList });
})();
