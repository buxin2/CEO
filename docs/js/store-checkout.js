(function () {
  const paymentRef = getQueryParam("payment_ref");
  const returnStatus = getQueryParam("status");
  let preview = null;
  let selectedMethod = "manual";
  let currentPaymentRef = paymentRef || "";
  const UNAVAILABLE = "FedEx shipping is currently unavailable for this destination.";

  function showError(msg) {
    const el = document.getElementById("checkout-error");
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
    if (msg) el.scrollIntoView({ behavior: "smooth", block: "center" });
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

  function destinationCountries() {
    const merged = {};
    const lists = [
      window.ISO_DESTINATION_COUNTRIES,
      preview && preview.destination_countries,
    ];
    lists.forEach((raw) => {
      (raw || []).forEach((c) => {
        const code = String((c && (c.code || c.country_code)) || "").trim().toUpperCase();
        const name = String((c && (c.name || c.country_name)) || "").trim();
        if (code && name) merged[code] = { code, name };
      });
    });
    return Object.keys(merged).map((k) => merged[k]).sort((a, b) => a.name.localeCompare(b.name, "en"));
  }

  function countryOptionsHtml(selected) {
    return destinationCountries().map((c) => {
      const sel = c.code === selected ? " selected" : "";
      return `<option value="${escapeHtml(c.code)}"${sel}>${escapeHtml(c.name)}</option>`;
    }).join("");
  }

  function filterCountryOptions() {
    const q = ((document.getElementById("ship-country-filter") || {}).value || "").trim().toLowerCase();
    const select = document.getElementById("ship-country");
    if (!select) return;
    const selected = select.value;
    const list = destinationCountries().filter((c) => {
      if (!q) return true;
      return c.name.toLowerCase().indexOf(q) >= 0 || c.code.toLowerCase().indexOf(q) >= 0;
    });
    select.innerHTML = `<option value="">Select country</option>` + list.map((c) => {
      const sel = c.code === selected ? " selected" : "";
      return `<option value="${escapeHtml(c.code)}"${sel}>${escapeHtml(c.name)}</option>`;
    }).join("");
  }

  function needsShipping() {
    return !!(preview && preview.shipping && preview.shipping.requires_shipping);
  }

  function snapshotIds() {
    return ["cust-name", "cust-email", "cust-phone", "ship-country", "ship-region", "ship-city", "ship-address", "ship-postal", "coupon-code", "ship-country-filter"];
  }

  function formSnapshot() {
    const snap = {};
    snapshotIds().forEach((id) => {
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
    const country = (document.getElementById("ship-country") || {}).value || snap["ship-country"] || "";
    const res = await storeFetch("/api/store/checkout/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: items,
        coupon_code: (document.getElementById("coupon-code") || {}).value || snap["coupon-code"] || "",
        country: country,
        delivery: { country: country },
      }),
    });
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      throw new Error("Checkout is temporarily unavailable. Please try again.");
    }
    if (!res.ok) throw new Error(data.error || "Could not calculate totals");
    preview = data;
    render();
    restoreSnapshot(snap);
    const filter = document.getElementById("ship-country-filter");
    if (filter && filter.value) filterCountryOptions();
  }

  function render() {
    const t = preview.totals;
    const ship = preview.shipping || {};
    const needsShip = ship.requires_shipping;
    const methods = preview.payment_methods || [];
    if (!methods.find((m) => m.id === selectedMethod)) selectedMethod = (methods[0] || {}).id || "manual";
    const shipOk = !needsShip || ship.available === true;
    const shipLabel = shipOk && needsShip
      ? money(t.shipping_cents, t.currency)
      : (needsShip ? "—" : money(0, t.currency));
    const totalLabel = shipOk ? money(t.total_cents, t.currency) : money(t.subtotal_cents - t.discount_cents, t.currency);

    document.getElementById("checkout-root").innerHTML = `
      <form id="checkout-form" class="card" style="padding:20px;">
        <h2>Customer information</h2>
        <div class="form-group"><label class="form-label">Full name</label><input class="form-control" id="cust-name" required></div>
        <div class="form-group"><label class="form-label">Email</label><input class="form-control" id="cust-email" type="email" required></div>
        <div class="form-group"><label class="form-label">Phone</label><input class="form-control" id="cust-phone" required></div>
        ${needsShip ? `
        <h2>Shipping address</h2>
        <div class="form-group">
          <label class="form-label">Shipping country</label>
          <input class="form-control" id="ship-country-filter" placeholder="Search country" autocomplete="off" style="margin-bottom:8px;">
          <select class="form-control" id="ship-country" required>
            <option value="">Select country</option>
            ${countryOptionsHtml("")}
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
        <p id="modem-gmd-note" class="text-muted hidden" style="margin-top:8px;"></p>
        <div id="manual-box" class="hidden card card-inner" style="margin-top:12px;"></div>
        <div id="receipt-section" class="hidden" style="margin-top:12px;">
          <label class="form-label">Payment receipt</label>
          <input type="file" id="receipt-file" accept="image/*">
          <p class="text-muted" style="margin-top:6px;">Attach your transfer receipt, then click Place order &amp; pay. The order and receipt are submitted together.</p>
        </div>
        <button type="submit" class="btn btn-primary btn-block" id="pay-btn" style="margin-top:16px;">Place order & pay</button>
      </form>
      <aside class="checkout-totals">
        <h3>Order summary</h3>
        ${(preview.items || []).map((i) => `
          <div class="row"><span>${escapeHtml(i.title)} × ${i.quantity}</span><span>${money(i.line_total_cents, t.currency)}</span></div>
        `).join("")}
        <div class="row"><span>Product</span><span>${money(t.subtotal_cents, t.currency)}</span></div>
        <div class="row"><span>Discount</span><span>− ${money(t.discount_cents, t.currency)}</span></div>
        <div class="row"><span>FedEx Shipping</span><span id="sum-shipping">${shipLabel}</span></div>
        <div class="row total"><span>Total</span><span id="sum-total">${totalLabel}</span></div>
        <div id="modem-gmd-row" class="row hidden"><span>Modem Pay (Dalasi)</span><span id="modem-gmd-amount"></span></div>
        <p id="sum-note" class="${shipOk ? "text-muted" : "form-error"}" style="margin-top:8px;">${escapeHtml(ship.note || "")}</p>
      </aside>
    `;

    const countryEl = document.getElementById("ship-country");
    if (countryEl) countryEl.addEventListener("change", () => loadPreview().catch((e) => showError(e.message)));
    const countryFilter = document.getElementById("ship-country-filter");
    if (countryFilter) countryFilter.addEventListener("input", filterCountryOptions);
    document.getElementById("apply-coupon").addEventListener("click", () => loadPreview().catch((e) => showError(e.message)));
    document.querySelectorAll("input[name=paymethod]").forEach((el) => {
      el.addEventListener("change", () => {
        selectedMethod = el.value;
        toggleManualPanel();
      });
    });
    toggleManualPanel();
    document.getElementById("checkout-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try {
        await startCheckout();
      } catch (e) {
        showError(e.message);
      }
    });
  }

  function formatGmd(n) {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(n) || 0) + " GMD";
  }

  function toggleModemQuote() {
    const quote = preview && preview.modem_gmd;
    const note = document.getElementById("modem-gmd-note");
    const row = document.getElementById("modem-gmd-row");
    const amt = document.getElementById("modem-gmd-amount");
    const show = selectedMethod === "modem" && quote && quote.amount;
    if (note) {
      note.classList.toggle("hidden", !show);
      if (show) {
        const rate = Number(quote.rate || 0).toFixed(2);
        note.textContent = "Modem Pay charges " + formatGmd(quote.amount)
          + " (converted from " + money(quote.original_cents, quote.original_currency)
          + " at 1 USD = " + rate + " GMD). Whole dalasi only.";
      }
    }
    if (row) row.classList.toggle("hidden", !show);
    if (amt && show) amt.textContent = formatGmd(quote.amount);
  }

  function toggleManualPanel() {
    toggleModemQuote();
    if (selectedMethod === "manual") {
      renderManual(preview.manual_instructions);
    } else {
      const box = document.getElementById("manual-box");
      const rec = document.getElementById("receipt-section");
      if (box) box.classList.add("hidden");
      if (rec) rec.classList.add("hidden");
    }
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
    if (needsShipping() && !(preview.shipping && preview.shipping.available)) {
      throw new Error("Select a shipping country first so FedEx shipping can be added.");
    }
    if (selectedMethod === "manual") {
      const file = (document.getElementById("receipt-file") || {}).files;
      if (!file || !file[0]) {
        throw new Error("Attach your payment receipt, then click Place order & pay.");
      }
    }
    const payBtn = document.getElementById("pay-btn");
    if (payBtn) {
      payBtn.disabled = true;
      payBtn.textContent = "Please wait…";
    }
    try {
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
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = data.error;
        const text = typeof err === "string" ? err : (err && err.message) || "Checkout failed";
        throw new Error(text);
      }
      currentPaymentRef = data.payment.payment_reference;
      if (data.payment.status === "succeeded") {
        saveStoreCart([]);
        window.location.href = data.order_url || ("store-order.html?order=" + encodeURIComponent(data.order.order_number));
        return;
      }
      if (selectedMethod === "modem" || selectedMethod === "paypal") {
        const link = data.payment && data.payment.payment_link;
        if (link) {
          window.location.href = link;
          return;
        }
        throw new Error(selectedMethod === "modem"
          ? "Modem Pay could not open a payment page. Please try PayPal or bank transfer."
          : "PayPal could not open a payment page. Please try again.");
      }
      if (selectedMethod === "manual") {
        try {
          await submitReceipt(currentPaymentRef);
        } catch (e) {
          throw new Error((e && e.message ? e.message : "Receipt upload failed") + " The order was created — open Store Orders to check it.");
        }
        saveStoreCart([]);
        showToast("Order placed and receipt submitted.");
        if (data.order_url) {
          window.location.href = data.order_url;
          return;
        }
      }
    } finally {
      if (payBtn) {
        payBtn.disabled = false;
        payBtn.textContent = "Place order & pay";
      }
    }
  }

  async function submitReceipt(paymentRefValue) {
    const ref = paymentRefValue || currentPaymentRef;
    if (!ref) throw new Error("Checkout did not start.");
    const file = (document.getElementById("receipt-file") || {}).files[0];
    if (!file) throw new Error("Attach your payment receipt.");
    const form = new FormData();
    form.append("receipt", file);
    const res = await storeFetch("/api/store/checkout/receipt/" + encodeURIComponent(ref), {
      method: "POST",
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Receipt upload failed");
    return data;
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
