/* Billing views are presentation-only. The server owns plan prices and state. */
(function () {
  "use strict";
  window.EZBillingUI = {
    render(data, E, V) {
      if (!data) return '<div class="surface pad"><p>Đang tải gói dịch vụ / Loading billing...</p></div>';
      const en = window.EZI18N?.language() === "en";
      const t = (vi, eng) => en ? eng : vi;
      const statusMap = {
        trialing: t("Đang dùng thử", "Free trial active"),
        trial_expired: t("Dùng thử đã kết thúc", "Trial ended"),
        active: t("Gói đang hoạt động", "Subscription active"),
        expired: t("Gói đã hết hạn", "Subscription expired"),
        pilot: "Pilot", demo: "DEMO",
      };
      const badge = statusMap[data.status] || E(data.status);
      const trial = data.status === "trialing" || data.status === "trial_expired";
      const plans = Array.isArray(data.plans) ? data.plans : [];
      const locked = data.requires_payment;
      const rows = Array.isArray(data.transactions) ? data.transactions : [];
      return `<section class="billing-head surface pad">
        <div class="billing-head-top"><div>
          <span class="pill ${locked ? "red" : "blue"}">${E(badge)}</span>
          <h2>${t("Gói & thanh toán", "Subscription & billing")}</h2>
          <p class="muted">${trial ?
             t("Trải nghiệm 7 ngày miễn phí. Không cần thẻ và không tự động trừ tiền.",
               "7-day free trial. No card required and no automatic charges.") :
             t("Theo dõi gói đăng ký và lịch sử giao dịch.", "View subscription and transaction history.")}</p>
        </div><div class="billing-count">
          <strong>${data.days_remaining == null ? "—" : E(data.days_remaining)}</strong>
          <span>${trial ? t("ngày thử còn lại", "trial days remaining") :
                 t("ngày sử dụng còn lại", "days remaining")}</span>
        </div></div>
        <p>${locked ? t("Hệ thống tạm khóa các nghiệp vụ. Dữ liệu được giữ nguyên; chọn gói và thanh toán để tiếp tục.",
                          "Business operations are paused. Your data is retained; choose a plan and pay to resume.") :
          t("Bạn có thể chọn gói sau khi trải nghiệm. Không thu phí khi chưa xác thực thanh toán.",
            "Choose a plan after trying the product. No charge until payment verification.")}</p>
        <div class="billing-meta">
          <span>${t("Gói đã thanh toán", "Paid plan")}: <b>${E(data.plan || t("Chưa chọn", "Not chosen"))}</b></span>
          <span>${t("Hết hạn", "Expires")}: <b>${E(data.period_end || data.trial_ends_at ?
             new Date(data.period_end || data.trial_ends_at).toLocaleDateString(en ? "en-US" : "vi-VN") : "—")}</b></span>
          <span>${t("Tự động gia hạn", "Auto renewal")}: <b>${t("Không", "Off")}</b></span>
        </div>
      </section>
      <section class="surface pad billing-plans">
        <div class="panel-title"><h3>${t("Chọn gói sau khi dùng thử", "Choose your plan")}</h3>
          <span class="pill">${t("Thanh toán từng kỳ 30 ngày", "30-day prepaid terms")}</span></div>
        <div class="billing-grid">
          ${plans.map(p => `<article class="billing-plan">
            <span class="pill">${E(p.code)}</span>
            <h3>${V(p.amount_vnd)} <small>/ 30 ${t("ngày", "days")}</small></h3>
            <p>${E(({BASIC:t("Bán hàng & quản lý cơ bản","Core sales & operations"),
               PLUS:t("Kho nâng cao & phân tích","Inventory and analytics"),
               PRO:t("Đa chi nhánh & quản trị","Multi-location and administration")})[p.code] || p.code)}</p>
            <button class="btn wide ${data.plan===p.code && data.status==="active" ? "secondary" : ""}"
              type="button" data-action="billing-pay" data-value="${E(p.code)}"
              ${!data.checkout_ready || data.status==="active" ? "disabled" : ""}>
              ${data.status==="active" ? t("Gói đã kích hoạt", "Plan active") : t("Chọn & thanh toán", "Select & pay")}
            </button>
          </article>`).join("")}
        </div>
        <div class="billing-payment">
          <div><strong>${t("Phương thức thanh toán", "Payment method")}</strong>
            <p class="subtle">${t("Thanh toán trên trang VNPAY bảo mật. EZ Thing không nhận số thẻ hoặc CVV.",
              "Secure VNPAY hosted checkout. EZ Thing never accepts card numbers or CVV.")}</p></div>
          <select id="billing-channel" aria-label="${t("Phương thức thanh toán","Payment channel")}">
            <option value="card">💳 ${t("Thẻ Visa / Mastercard / JCB", "Visa / Mastercard / JCB")}</option>
            <option value="bank">🏦 ${t("ATM / Ngân hàng nội địa", "Domestic card / Banking")}</option>
            <option value="qr">▣ VNPAY-QR</option>
          </select>
        </div>
        <div class="billing-cards">
          <span>💳 <b>${t("Thẻ đã lưu", "Saved cards")}</b>: ${t("Chưa có", "None")}</span>
          <button class="btn secondary sm" type="button" data-action="billing-card-info">
            + ${t("Thêm thẻ", "Add card")}</button>
        </div>
        ${!data.checkout_ready ? `<p class="billing-warning" role="status">
          ${t("Cổng thanh toán chưa được cấu hình. Chưa thể trả tiền hoặc lưu thẻ ở môi trường này.",
             "Payment gateway is not configured. Payment and card vault are not available yet.")}
        </p>` : `<p class="subtle">${t("Thanh toán thử nghiệm VNPAY Sandbox — không dùng thẻ thật.",
               "VNPAY Sandbox test payments only — do not use real cards.")}</p>`}
      </section>
      <section class="surface pad billing-history">
        <div class="panel-title"><h3>${t("Lịch sử giao dịch", "Payment history")}</h3>
          <button type="button" class="btn secondary sm" data-action="billing-refresh">
            ↻ ${t("Kiểm tra thanh toán", "Refresh payment status")}
          </button>
        </div>
        ${rows.length ? `<div class="table-wrap"><table class="data-table"><thead>
          <tr><th>${t("Mã giao dịch", "Reference")}</th><th>${t("Gói", "Plan")}</th>
          <th>${t("Số tiền", "Amount")}</th><th>${t("Trạng thái", "Status")}</th></tr></thead><tbody>
          ${rows.map(row=>`<tr><td>${E(row.reference)}</td><td>${E(row.plan)}</td>
          <td>${V(row.amount_vnd)}</td><td>${E(row.status)}</td></tr>`).join("")}
        </tbody></table></div>` : `<p class="muted">${t("Chưa có giao dịch nào.","No transactions yet.")}</p>`}
        <p class="subtle">${t("Đây là lịch sử thanh toán dịch vụ, chưa phải hóa đơn thuế điện tử.",
          "This is the payment history, not a legally issued tax invoice.")}</p>
      </section>`;
    }
  };
})();
