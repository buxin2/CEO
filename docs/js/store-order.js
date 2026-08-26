(function () {
  const orderNumber = getQueryParam("order");
  const token = getQueryParam("token");

  (async function init() {
    const root = document.getElementById("order-root");
    if (!orderNumber || !token) {
      root.innerHTML = "<p>Order link is missing.</p>";
      return;
    }
    const res = await storeFetch("/api/store/orders/" + encodeURIComponent(orderNumber) + "?token=" + encodeURIComponent(token));
    const o = await res.json();
    if (!res.ok) {
      root.innerHTML = `<p>${escapeHtml(o.error || "Order not found.")}</p>`;
      return;
    }
    const paid = o.payment_status === "succeeded" || o.order_status === "paid" || o.order_status === "processing" || o.order_status === "packed" || o.order_status === "shipped" || o.order_status === "delivered";
    const digital = (o.digital_delivery || []).map((d) => `
      <p><strong>${escapeHtml(d.title || "Digital access")}</strong></p>
      ${d.url ? `<p><a href="${escapeHtml(d.url)}" target="_blank" rel="noopener">Open / download</a></p>` : ""}
      ${d.text ? `<pre style="text-align:left;white-space:pre-wrap;">${escapeHtml(d.text)}</pre>` : ""}
    `).join("");
    root.innerHTML = `
      <h1>${paid ? "Order confirmed 🎉" : "Order received"}</h1>
      <p class="text-muted">${paid ? "Thank you for your order." : "Your order is waiting for payment confirmation."}</p>
      <p style="margin:16px 0;"><strong>Order ${escapeHtml(o.order_number)}</strong></p>
      <p>${escapeHtml(o.product_summary || "")}</p>
      <p>Total: <strong>${money(o.total_cents, o.currency)}</strong></p>
      ${o.requires_shipping ? `<p>Shipping to ${escapeHtml(o.ship_city ? o.ship_city + ", " : "")}${escapeHtml(o.ship_country)}</p>` : "<p>Digital delivery — no shipping.</p>"}
      <p>Status: ${escapeHtml(o.order_status)} · Payment: ${escapeHtml(o.payment_status)}</p>
      ${o.courier || o.tracking_number ? `
        <div style="margin-top:16px;text-align:left;">
          <h3>Tracking</h3>
          <p>${escapeHtml(o.courier || "")} ${escapeHtml(o.tracking_number || "")}</p>
          ${o.tracking_url ? `<p><a href="${escapeHtml(o.tracking_url)}" target="_blank" rel="noopener">Track shipment</a></p>` : ""}
        </div>` : ""}
      ${digital}
      <p style="margin-top:24px;"><a class="btn btn-primary" href="store.html">Continue shopping</a></p>
    `;
  })().catch((e) => {
    document.getElementById("order-root").innerHTML = `<p>${escapeHtml(e.message)}</p>`;
  });
})();
