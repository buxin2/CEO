(function () {
  requireAuth();

  const statuses = ["pending_payment", "paid", "processing", "shipped", "delivered", "cancelled", "refunded"];

  function cents(n) {
    return ((n || 0) / 100).toFixed(2);
  }

  async function loadOrders() {
    const data = await apiRequest("/api/admin/orders");
    document.getElementById("orders-list").innerHTML = (data.orders || []).map((o) => `
      <div class="card card-inner" style="margin-bottom:8px;">
        <div><strong>${escapeHtml(o.order_number)}</strong> · ${escapeHtml(o.product_name)} · Qty ${o.quantity}</div>
        <div>${escapeHtml(o.customer_name)} · ${cents(o.total_cents)} ${escapeHtml(o.currency)} · Payment: ${escapeHtml(o.payment_status)}</div>
        <label>Order status
          <select class="form-control order-status" data-id="${o.id}">
            ${statuses.map((s) => `<option value="${s}" ${o.order_status === s ? "selected" : ""}>${s}</option>`).join("")}
          </select>
        </label>
        ${o.delivery && Object.keys(o.delivery).length ? `<pre>${escapeHtml(JSON.stringify(o.delivery, null, 2))}</pre>` : ""}
      </div>`).join("") || "<p class=\"text-muted\">No orders yet.</p>";

    document.querySelectorAll(".order-status").forEach((sel) => {
      sel.addEventListener("change", async () => {
        await apiRequest(`/api/admin/orders/${sel.dataset.id}`, {
          method: "PUT",
          body: JSON.stringify({ order_status: sel.value }),
        });
        showToast("Order updated");
      });
    });
  }

  loadOrders();
})();
