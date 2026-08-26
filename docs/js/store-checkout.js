(function () {
  const paymentRef = getQueryParam("payment_ref");
  const returnStatus = getQueryParam("status");
  let preview = null;
  let selectedMethod = "manual";
  let currentPaymentRef = paymentRef || "";
  let countries = [];

  function showError(msg) {
    const el = document.getElementById("checkout-error");
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
  }

  function showRootMessage(html) {
    document.getElementById("checkout-root").innerHTML = html;
  }

  function queryItems() {
    const pid = parseInt(getQueryParam("product_id") || "", 10);
    if (!pid) return [];
    let options = {};
    try {
      const raw = getQueryParam("options");
      if (raw) options = JSON.parse(raw);
    } catch (e) {
      options = {};
    }
    return [{
      product_id: pid,
      quantity: Math.max(1, parseInt(getQueryParam("qty") || getQueryParam("quantity") || "1", 10) || 1),
      options: options,
    }];
  }

  function cartItems() {
    const fromCart = getStoreCart().map((i) => ({
      product_id: i.product_id,
      quantity: i.quantity,
      options: i.options || {},
    })).filter((i) => i.product_id);
    const fromQuery = queryItems();
    if (fromQuery.length && !fromCart.length) return fromQuery;
    if (fromQuery.length && getQueryParam("buy")) return fromQuery;
    return fromCart.length ? fromCart : fromQuery;
  }

  function delivery() {
    return {
      country: (document.getElementById("ship-country") || {}).value || "",
      region: (document.getElementById("ship-region") || {}).value || "",
      city: (document.getElementById("ship-city") || {}).value || "",
      address: (document.getElementById("ship-address") || {}).value || "",
      postal: (document.getElementById("ship-postal") || {}).value || "",
    };
  }

  function formSnapshot() {
    const ids = ["cust-name", "cust-email", "cust-phone", "ship-country", "ship-region", "ship-city", "ship-address", "ship-postal", "coupon-code"];
    const snap = {};
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) snap[id] = el.value;
    });
    return snap;
  }

  function restoreSnapshot(snap) {
    Object.keys(snap || {}).forEach((id) => {
      const el = document.getElementById(id);
      if (el && snap[id] != null) el.value = snap[id];
    });
  }

  async function loadPreview() {
    const snap = formSnapshot();
    const items = cartItems();
    if (!items.length) {
      showRootMessage("<p>Your cart is empty. <a href='store.html'>Browse products</a></p>");
      return;
    }
    const body = {
      items: items,
      coupon_code: (document.getElementById("coupon-code") || {}).value || "",
      delivery: delivery(),
      country: delivery().country,
      region: delivery().region,
    };
    const res = await storeFetch("/api/store/checkout/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      throw new Error("Checkout is temporarily unavailable. Please try again.");
    }
    if (!res.ok) throw new Error(data.error || "Could not calculate totals");
    preview = data;
    if (Array.isArray(data.shipping_countries) && data.shipping_countries.length) {
      countries = data.shipping_countries;
    }
    render();
    restoreSnapshot(snap);
  }

  function render() {
    const t = preview.totals;
    const ship = preview.shipping || {};
    const needsShip = ship.requires_shipping;
    const methods = preview.payment_methods || [];
    if (!methods.find((m) => m.id === selectedMethod)) selectedMethod = (methods[0] || {}).id || "manual";

    document.getElementById("checkout-root").innerHTML = `
      <form id="checkout-form" class="card" style="padding:20px;">
        <h2>Customer information</h2>
        <div class="form-group"><label class="form-label">Full name</label><input class="form-control" id="cust-name" required></div>
        <div class="form-group"><label class="form-label">Email</label><input class="form-control" id="cust-email" type="email" required></div>
        <div class="form-group"><label class="form-label">Phone</label><input class="form-control" id="cust-phone" required></div>
        ${needsShip ? `
        <h2>Delivery</h2>
        <div class="form-group">
          <label class="form-label">Country</label>
          <select class="form-control" id="ship-country">
            <option value="">Select country</option>
            ${countries.map((c) => `<option value="${escapeHtml(c.country_name)}">${escapeHtml(c.country_name)}</option>`).join("")}
          </select>
        </div>
        <div class="form-group"><label class="form-label">State / Region / Province</label><input class="form-control" id="ship-region"></div>
        <div class="form-group"><label class="form-label">City</label><input class="form-control" id="ship-city"></div>
        <div class="form-group"><label class="form-label">Address</label><textarea class="form-control" id="ship-address"></textarea></div>
        <div class="form-group"><label class="form-label">Postal / ZIP</label><input class="form-control" id="ship-postal"></div>
        ` : `<p class="text-muted">Digital order — no shipping address required.</p><input type="hidden" id="ship-country">`}
        <div class="form-group">
          <label class="form-label">Coupon code</label>
          <div style="display:flex;gap:8px;">
            <input class="form-control" id="coupon-code">
            <button type="button" class="btn btn-secondary" id="apply-coupon">Apply</button>
          </div>
        </div>
        <h2>Payment method</h2>
        <div id="payment-methods">
          ${methods.map((m) => `
            <label style="display:block;margin-bottom:8px;">
              <input type="radio" name="paymethod" value="${escapeHtml(m.id)}" ${m.id === selectedMethod ? "checked" : ""}>
              ${escapeHtml(m.label)}
            </label>`).join("")}
        </div>
        <div id="manual-box" class="hidden card card-inner" style="margin-top:12px;"></div>
        <div id="receipt-section" class="hidden" style="margin-top:12px;">
          <label class="form-label">Upload payment receipt</label>
          <input type="file" id="receipt-file" accept="image/*">
          <button type="button" class="btn btn-secondary" id="submit-receipt" style="margin-top:8px;">Submit receipt</button>
        </div>
        <button type="submit" class="btn btn-primary btn-block" id="pay-btn" style="margin-top:16px;" ${ship.available === false ? "disabled" : ""}>Place order & pay</button>
      </form>
      <aside class="checkout-totals">
        <h3>Order summary</h3>
        ${(preview.items || []).map((i) => `
          <div class="row"><span>${escapeHtml(i.title)} × ${i.quantity}</span><span>${money(i.line_total_cents, t.currency)}</span></div>
        `).join("")}
        <div class="row"><span>Subtotal</span><span>${money(t.subtotal_cents, t.currency)}</span></div>
        <div class="row"><span>Discount</span><span>− ${money(t.discount_cents, t.currency)}</span></div>
        <div class="row"><span>Shipping</span><span>${ship.available === false ? "—" : money(t.shipping_cents, t.currency)}</span></div>
        <div class="row total"><span>Total</span><span>${money(t.total_cents, t.currency)}</span></div>
        ${ship.note ? `<p class="${ship.available === false ? "form-error" : "text-muted"}" style="margin-top:8px;">${escapeHtml(ship.note)}</p>` : ""}
      </aside>
    `;

    ["ship-country", "ship-region"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", () => loadPreview().catch((e) => showError(e.message)));
    });
    document.getElementById("apply-coupon").addEventListener("click", () => loadPreview().catch((e) => showError(e.message)));
    document.querySelectorAll("input[name=paymethod]").forEach((el) => {
      el.addEventListener("change", () => { selectedMethod = el.value; });
    });
    document.getElementById("checkout-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        await startCheckout();
      } catch (e) {
        showError(e.message);
      }
    });
    const rec = document.getElementById("submit-receipt");
    if (rec) rec.addEventListener("click", submitReceipt);
  }

  function renderManual(instr) {
    const box = document.getElementById("manual-box");
    box.classList.remove("hidden");
    document.getElementById("receipt-section").classList.remove("hidden");
    if (!instr) {
      box.innerHTML = "<p>Follow the payment instructions, then upload your receipt.</p>";
      return;
    }
    box.innerHTML = Object.values(instr).map((block) => `
      <h4>${escapeHtml(block.title || "Payment instructions")}</h4>
      <ul>${(block.fields || []).map((f) => `<li><strong>${escapeHtml(f.label)}:</strong> ${escapeHtml(f.value)}</li>`).join("")}</ul>
    `).join("");
  }

  async function startCheckout() {
    showError("");
    const res = await storeFetch("/api/store/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: cartItems(),
        coupon_code: document.getElementById("coupon-code").value.trim() || undefined,
        payment_method: selectedMethod,
        customer: {
          full_name: document.getElementById("cust-name").value.trim(),
          email: document.getElementById("cust-email").value.trim(),
          phone: document.getElementById("cust-phone").value.trim(),
        },
        delivery: delivery(),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Checkout failed");
    currentPaymentRef = data.payment.payment_reference;
    if (data.payment.status === "succeeded") {
      saveStoreCart([]);
      window.location.href = data.order_url || ("store-order.html?order=" + encodeURIComponent(data.order.order_number));
      return;
    }
    if ((selectedMethod === "modem" || selectedMethod === "paypal") && data.payment.payment_link) {
      window.location.href = data.payment.payment_link;
      return;
    }
    if (selectedMethod === "manual") {
      renderManual(data.manual_instructions);
      showToast("Complete the transfer, then upload your receipt.");
    }
  }

  async function submitReceipt() {
    if (!currentPaymentRef) {
      showError("Start checkout first.");
      return;
    }
    const file = document.getElementById("receipt-file").files[0];
    const form = new FormData();
    if (file) form.append("receipt", file);
    const res = await storeFetch("/api/store/checkout/receipt/" + encodeURIComponent(currentPaymentRef), {
      method: "POST",
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    showToast("Receipt submitted. Your order is pending payment approval.");
    if (data.order_url) {
      setTimeout(() => { window.location.href = data.order_url; }, 800);
    }
  }

  async function verifyReturn() {
    const res = await storeFetch("/api/store/checkout/verify/" + encodeURIComponent(paymentRef), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paypal_order_id: getQueryParam("token") || getQueryParam("PayerID") }),
    });
    const data = await res.json();
    if (res.ok && data.payment && data.payment.status === "succeeded") {
      saveStoreCart([]);
      window.location.href = data.order_url;
      return true;
    }
    if (data.order_url) {
      window.location.href = data.order_url;
      return true;
    }
    return false;
  }

  (async function init() {
    try {
      if (paymentRef && returnStatus === "return") {
        await verifyReturn();
        return;
      }
      if (paymentRef) {
        const res = await storeFetch("/api/store/checkout/payment/" + encodeURIComponent(paymentRef));
        const data = await res.json();
        if (res.ok && data.payment && data.payment.status === "succeeded" && data.order_url) {
          window.location.href = data.order_url;
          return;
        }
      }
      await loadPreview();
    } catch (e) {
      showError(e.message);
      showRootMessage(`<p>${escapeHtml(e.message || "Could not load checkout.")}</p><p><a href="store.html">Back to store</a></p>`);
    }
  })();
})();
