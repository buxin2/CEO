(function () {
  requireAuth();

  const statuses = ["pending_payment", "paid", "processing", "shipped", "delivered", "cancelled", "refunded"];
  let orders = [];

  function cents(n) {
    return ((n || 0) / 100).toFixed(2);
  }

  function render() {
    const q = ((document.getElementById("order-search") || {}).value || "").trim().toLowerCase();
    const st = ((document.getElementById("order-status-filter") || {}).value || "");
    const rows = orders.filter((o) => {
      if (st && o.order_status !== st) return false;
      if (!q) return true;
      const hay = [o.order_number, o.product_name, o.customer_name].join(" ").toLowerCase();
      return hay.indexOf(q) >= 0;
    });
    document.getElementById("orders-list").innerHTML = rows.length ? `<table class="ui-table"><thead><tr>
      <th>Order</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody>
      ${rows.map((o) => `
        <tr>
          <td><strong>${escapeHtml(o.order_number)}</strong><div class="text-muted">${escapeHtml(o.product_name)} · Qty ${o.quantity}</div></td>
          <td>${escapeHtml(o.customer_name)}</td>
          <td>${cents(o.total_cents)} ${escapeHtml(o.currency)}</td>
          <td>
            <select class="form-control order-status" data-id="${o.id}" aria-label="Order status">
              ${statuses.map((s) => `<option value="${s}" ${o.order_status === s ? "selected" : ""}>${s}</option>`).join("")}
            </select>
          </td>
        </tr>`).join("")}
    </tbody></table>` : "<p class=\"text-muted\">No orders yet.</p>";

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

  async function loadOrders() {
    const data = await apiRequest("/api/admin/orders");
    orders = data.orders || [];
    render();
  }

  const search = document.getElementById("order-search");
  const filter = document.getElementById("order-status-filter");
  if (search) search.addEventListener("input", render);
  if (filter) filter.addEventListener("change", render);

  loadOrders();
})();
