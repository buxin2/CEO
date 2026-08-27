(function () {
  const statuses = ["pending_payment", "paid", "processing", "packed", "shipped", "delivered", "cancelled", "refunded"];
  let orders = [];

  function matchesSearch(o, q) {
    if (!q) return true;
    const hay = [
      o.order_number, o.customer_name, o.customer_email, o.customer_phone,
      o.product_summary, o.ship_country, o.payment_method, o.payment_status, o.order_status,
    ].join(" ").toLowerCase();
    return hay.indexOf(q) >= 0;
  }

  function renderList() {
    const q = (document.getElementById("order-search").value || "").trim().toLowerCase();
    const rows = orders.filter((o) => matchesSearch(o, q));
    document.getElementById("orders-list").innerHTML = rows.map((o) => `
      <div class="card" style="padding:14px 16px;margin-bottom:10px;display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;">
        <div>
          <div><strong>${escapeHtml(o.product_summary || "Store order")}</strong></div>
          <div class="text-muted">${escapeHtml(o.customer_name || "Customer")} · ${escapeHtml(o.order_number || "")} · ${escapeHtml(o.order_status || "")}</div>
        </div>
        <button class="btn btn-secondary btn-sm" data-view="${o.id}">View</button>
      </div>
    `).join("") || "<p class='text-muted'>No matching store orders.</p>";

    document.querySelectorAll("[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => openOrder(parseInt(btn.dataset.view, 10)));
    });
  }

  function receiptHtml(o) {
    const url = o.receipt_url || "";
    if (!url) return "<p class='text-muted'>No payment receipt uploaded.</p>";
    const lower = url.toLowerCase();
    const isImg = [".png", ".jpg", ".jpeg", ".gif", ".webp"].some((ext) => lower.indexOf(ext) >= 0) || lower.indexOf("image") >= 0;
    return `
      <p><a class="btn btn-secondary btn-sm" href="${escapeHtml(url)}" target="_blank" rel="noopener">Open receipt</a></p>
      ${isImg ? `<p style="margin-top:8px;"><a href="${escapeHtml(url)}" target="_blank" rel="noopener"><img src="${escapeHtml(url)}" alt="Payment receipt" style="max-width:100%;border-radius:12px;border:1px solid var(--color-border);"></a></p>` : ""}
    `;
  }

  function openOrder(id) {
    const o = orders.find((row) => row.id === id);
    if (!o) return;
    document.getElementById("order-modal-title").textContent = o.order_number || "Order";
    document.getElementById("order-modal-body").innerHTML = `
      <p><strong>${escapeHtml(o.product_summary || "")}</strong></p>
      <p>${escapeHtml(o.customer_name)} · ${escapeHtml(o.customer_email)} · ${escapeHtml(o.customer_phone)}</p>
      <p class="text-muted">${o.requires_shipping
        ? `${escapeHtml(o.ship_address || "")}, ${escapeHtml(o.ship_city || "")}, ${escapeHtml(o.ship_region || "")}, ${escapeHtml(o.ship_country || "")} ${escapeHtml(o.ship_postal || "")}`
        : "Digital — no shipping address"}</p>
      <p>Product ${(o.subtotal_cents / 100).toFixed(2)} · Shipping ${(o.shipping_cents / 100).toFixed(2)} · Discount ${(o.discount_cents / 100).toFixed(2)}</p>
      <p><strong>Total ${(o.total_cents / 100).toFixed(2)} ${escapeHtml(o.currency)}</strong></p>
      ${o.shipping_carrier ? `<p class="text-muted">${escapeHtml(o.shipping_carrier)} · ${escapeHtml(o.shipping_zone || "")}</p>` : ""}
      <p>Payment: ${escapeHtml(o.payment_method)} · ${escapeHtml(o.payment_status)} · Ref ${escapeHtml(o.payment_reference || "")}</p>
      <h4 style="margin-top:16px;">Payment receipt</h4>
      ${receiptHtml(o)}
      <label class="form-label" style="margin-top:16px;">Order status</label>
      <select class="form-control" id="modal-status">
        ${statuses.map((s) => `<option value="${s}" ${o.order_status === s ? "selected" : ""}>${s}</option>`).join("")}
      </select>
      <div class="form-grid admin-product-form" style="margin-top:8px;">
        <input class="form-control" id="modal-courier" placeholder="Courier" value="${escapeHtml(o.courier || "")}">
        <input class="form-control" id="modal-track" placeholder="Tracking number" value="${escapeHtml(o.tracking_number || "")}">
        <input class="form-control" id="modal-turl" placeholder="Tracking URL" value="${escapeHtml(o.tracking_url || "")}">
      </div>
      <button class="btn btn-primary" id="modal-save" style="margin-top:12px;">Save</button>
    `;
    document.getElementById("modal-status").addEventListener("change", async () => {
      await apiRequest("/api/admin/store/orders/" + o.id, {
        method: "PUT",
        body: JSON.stringify({ order_status: document.getElementById("modal-status").value }),
      });
      o.order_status = document.getElementById("modal-status").value;
      showToast("Status updated");
      renderList();
    });
    document.getElementById("modal-save").addEventListener("click", async () => {
      await apiRequest("/api/admin/store/orders/" + o.id, {
        method: "PUT",
        body: JSON.stringify({
          courier: document.getElementById("modal-courier").value,
          tracking_number: document.getElementById("modal-track").value,
          tracking_url: document.getElementById("modal-turl").value,
        }),
      });
      o.courier = document.getElementById("modal-courier").value;
      o.tracking_number = document.getElementById("modal-track").value;
      o.tracking_url = document.getElementById("modal-turl").value;
      showToast("Tracking saved");
    });
    openModal("order-modal");
  }

  async function loadHelp() {
    const box = document.getElementById("help-list");
    if (!box) return;
    const data = await apiRequest("/api/admin/store/account-help");
    const rows = data.requests || [];
    const pending = rows.filter((r) => r.status !== "done");
    const shown = pending.length ? pending : rows.slice(0, 5);
    if (!rows.length) {
      box.innerHTML = "";
      return;
    }
    box.innerHTML = `<h2>Account help</h2>` + shown.map((r) => `
      <div class="card" style="padding:14px 16px;margin-bottom:10px;">
        <div><strong>${escapeHtml(r.full_name || "Customer")}</strong> · ${escapeHtml(r.status || "pending")}</div>
        <div class="text-muted">${escapeHtml(r.email || "")} · ${escapeHtml(r.phone || "")}</div>
        <p style="margin:8px 0 0;">${escapeHtml(r.message || "")}</p>
        ${r.customer ? `<p class="text-muted">Matched account: ${escapeHtml(r.customer.email || "")} · <a href="admin-store-users.html?id=${r.customer.id}">Open user</a></p>` : "<p class='text-muted'>No matching store account for this email/phone.</p>"}
        ${r.status === "done" ? "" : `<button class="btn btn-secondary btn-sm" data-help="${r.id}" style="margin-top:8px;">Mark done</button>`}
      </div>
    `).join("");
    box.querySelectorAll("[data-help]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest("/api/admin/store/account-help/" + btn.getAttribute("data-help"), {
          method: "PUT",
          body: JSON.stringify({ status: "done" }),
        });
        showToast("Marked done");
        loadHelp().catch((e) => showToast(e.message));
      });
    });
  }

  async function load() {
    const data = await apiRequest("/api/admin/store/orders");
    orders = data.orders || [];
    renderList();
  }

  document.getElementById("order-search").addEventListener("input", renderList);
  load().catch((e) => showToast(e.message));
  loadHelp().catch((e) => showToast(e.message));
})();
