(function () {
  requireAuth();

  function cents(n) {
    return ((n || 0) / 100).toFixed(2);
  }

  async function loadPayments() {
    const data = await apiRequest("/api/admin/payments");
    const s = data.summary || {};
    document.getElementById("payments-summary").innerHTML = `
      <p><strong>Total:</strong> ${s.total} · <strong>Successful:</strong> ${s.succeeded} ·
      <strong>Pending:</strong> ${s.pending} · <strong>Manual pending:</strong> ${s.manual_pending} ·
      <strong>Revenue:</strong> ${cents(s.revenue_cents)}</p>`;
    document.getElementById("payments-list").innerHTML = (data.payments || []).map((p) => `
      <div class="card card-inner" style="margin-bottom:8px;">
        <div><strong>${escapeHtml(p.payment_reference)}</strong> · ${escapeHtml(p.payment_kind)} · ${escapeHtml(p.status)}</div>
        <div>${cents(p.total_cents)} ${escapeHtml(p.currency)} · ${escapeHtml(p.provider)} · ${escapeHtml(p.customer_name || p.customer_email || "")}</div>
        ${p.receipt_url ? `<a href="${escapeHtml(p.receipt_url)}" target="_blank" rel="noopener">View receipt</a>` : ""}
        ${p.status === "manual_pending" ? `
          <button class="btn btn-primary btn-sm" onclick="approvePayment(${p.id})">Approve</button>
          <button class="btn btn-secondary btn-sm" onclick="rejectPayment(${p.id})">Reject</button>` : ""}
      </div>`).join("") || "<p class=\"text-muted\">No payments yet.</p>";
  }

  window.approvePayment = async (id) => {
    await apiRequest(`/api/admin/payments/${id}/approve`, { method: "POST", body: JSON.stringify({}) });
    await loadPayments();
  };
  window.rejectPayment = async (id) => {
    const note = prompt("Rejection reason (optional)") || "";
    await apiRequest(`/api/admin/payments/${id}/reject`, { method: "POST", body: JSON.stringify({ note }) });
    await loadPayments();
  };

  loadPayments();
})();
