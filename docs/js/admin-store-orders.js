(function () {
  const statuses = ["pending_payment", "paid", "processing", "packed", "shipped", "delivered", "cancelled", "refunded"];

  async function load() {
    const data = await apiRequest("/api/admin/store/orders");
    document.getElementById("orders-list").innerHTML = (data.orders || []).map((o) => `
      <div class="card" style="padding:16px;margin-bottom:12px;">
        <div><strong>${escapeHtml(o.order_number)}</strong> · ${escapeHtml(o.product_summary || "")}</div>
        <div>${escapeHtml(o.customer_name)} · ${escapeHtml(o.customer_email)} · ${escapeHtml(o.customer_phone)}</div>
        <div class="text-muted">
          ${o.requires_shipping ? `${escapeHtml(o.ship_address)}, ${escapeHtml(o.ship_city)}, ${escapeHtml(o.ship_region)}, ${escapeHtml(o.ship_country)} ${escapeHtml(o.ship_postal)}` : "Digital — no shipping address"}
        </div>
        <div>Subtotal ${(o.subtotal_cents / 100).toFixed(2)} · Discount ${(o.discount_cents / 100).toFixed(2)} · Shipping ${(o.shipping_cents / 100).toFixed(2)} · <strong>Total ${(o.total_cents / 100).toFixed(2)} ${escapeHtml(o.currency)}</strong></div>
        <div>Payment: ${escapeHtml(o.payment_method)} · ${escapeHtml(o.payment_status)} · Ref ${escapeHtml(o.payment_reference || "")}</div>
        <label>Order status
          <select class="form-control" data-status="${o.id}">
            ${statuses.map((s) => `<option value="${s}" ${o.order_status === s ? "selected" : ""}>${s}</option>`).join("")}
          </select>
        </label>
        <div class="form-grid admin-product-form" style="margin-top:8px;">
          <input class="form-control" data-courier="${o.id}" placeholder="Courier" value="${escapeHtml(o.courier || "")}">
          <input class="form-control" data-track="${o.id}" placeholder="Tracking number" value="${escapeHtml(o.tracking_number || "")}">
          <input class="form-control" data-turl="${o.id}" placeholder="Tracking URL" value="${escapeHtml(o.tracking_url || "")}">
        </div>
        <button class="btn btn-secondary btn-sm" data-save="${o.id}" style="margin-top:8px;">Save tracking</button>
      </div>
    `).join("") || "<p class='text-muted'>No store orders yet.</p>";

    document.querySelectorAll("[data-status]").forEach((sel) => {
      sel.addEventListener("change", async () => {
        await apiRequest("/api/admin/store/orders/" + sel.dataset.status, {
          method: "PUT",
          body: JSON.stringify({ order_status: sel.value }),
        });
        showToast("Status updated");
      });
    });
    document.querySelectorAll("[data-save]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.save;
        await apiRequest("/api/admin/store/orders/" + id, {
          method: "PUT",
          body: JSON.stringify({
            courier: document.querySelector(`[data-courier="${id}"]`).value,
            tracking_number: document.querySelector(`[data-track="${id}"]`).value,
            tracking_url: document.querySelector(`[data-turl="${id}"]`).value,
          }),
        });
        showToast("Tracking saved");
      });
    });
  }

  load().catch((e) => showToast(e.message));
})();
