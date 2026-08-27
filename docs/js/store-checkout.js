(function () {
  const paymentRef = getQueryParam("payment_ref");
  const returnStatus = getQueryParam("status");
  let preview = null;
  let selectedMethod = "";
  let currentPaymentRef = paymentRef || "";
  const UNAVAILABLE = "FedEx shipping is currently unavailable for this destination.";

  function hasMethod(id) {
    return !!(preview && (preview.payment_methods || []).some((m) => m.id === id));
  }

  function walletLogoSvg(network) {
    if (network === "wave") {
      return `<svg viewBox="0 0 64 32" aria-hidden="true"><path fill="#fff" d="M4 20c6-10 12-10 18 0 6-10 12-10 18 0 6-10 12-10 18 0v6H4v-6z"/><circle fill="#fff" cx="18" cy="10" r="5"/><circle fill="#00b4c8" cx="20" cy="10" r="2"/></svg>`;
    }
    if (network === "afrimoney") {
      return `<svg viewBox="0 0 64 32" aria-hidden="true"><text x="32" y="22" text-anchor="middle" fill="#fff" font-size="14" font-family="Arial,sans-serif" font-weight="700">Afri</text></svg>`;
    }
    return `<svg viewBox="0 0 64 32" aria-hidden="true"><text x="32" y="23" text-anchor="middle" fill="#fff" font-size="18" font-family="Arial,sans-serif" font-weight="800">Q</text></svg>`;
  }

  function paypalSectionHtml() {
    if (!hasMethod("paypal")) return "";
    return `
      <div class="pay-section" id="paypal-box">
        <h3 class="pay-section-title">PayPal payment</h3>
        <div id="paypal-button-container"></div>
      </div>`;
  }

  function walletSectionHtml() {
    if (!hasMethod("modem")) return "";
    const wallets = [
      { network: "wave", name: "Wave", cls: "wave" },
      { network: "afrimoney", name: "AfriMoney", cls: "afrimoney" },
      { network: "qmoney", name: "QMoney", cls: "qmoney" },
    ];
    return `
      <div class="pay-section">
        <h3 class="pay-section-title">Mobile money</h3>
        <p id="modem-gmd-note" class="text-muted hidden"></p>
        <div class="pay-wallet-grid">
          ${wallets.map((w) => `
            <button type="button" class="pay-wallet-btn pay-wallet-${w.cls}" data-wallet="${w.network}">
              <span class="pay-wallet-logo">${walletLogoSvg(w.network)}</span>
              <span class="pay-wallet-name">${escapeHtml(w.name)}</span>
              <span class="pay-wallet-hint">Pay now</span>
            </button>
          `).join("")}
        </div>
      </div>`;
  }

  function bankSectionHtml() {
    if (!hasMethod("manual")) return "";
    return `
      <div class="pay-section">
        <button type="button" class="pay-bank-toggle" id="choose-bank">
          <strong>Bank / money transfer</strong>
          <span class="text-muted">Pay from your bank, then upload a receipt and place the order</span>
        </button>
        <div id="manual-box" class="hidden card card-inner" style="margin-top:12px;"></div>
        <div id="receipt-section" class="hidden" style="margin-top:12px;">
          <label class="form-label">Payment receipt</label>
          <input type="file" id="receipt-file" accept="image/*">
          <p class="text-muted" style="margin-top:6px;">Attach your transfer receipt, then click Place order &amp; pay.</p>
        </div>
        <button type="submit" class="btn btn-primary btn-block hidden" id="pay-btn" style="margin-top:16px;">Place order &amp; pay</button>
      </div>`;
  }

  let storeCustomer = null;

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
    if (storeCustomer) {
      ["cust-name", "cust-email", "cust-phone"].forEach((id, i) => {
        const el = document.getElementById(id);
        const val = [storeCustomer.full_name, storeCustomer.email, storeCustomer.phone][i];
        if (el && val && !snap[id]) el.value = val;
      });
    }
    const filter = document.getElementById("ship-country-filter");
    if (filter && filter.value) filterCountryOptions();
  }

  function render() {
    const t = preview.totals;
    const ship = preview.shipping || {};
    const needsShip = ship.requires_shipping;
    const methods = preview.payment_methods || [];
    if (selectedMethod === "paypal" || selectedMethod === "modem") selectedMethod = "";
    if (selectedMethod && !methods.find((m) => m.id === selectedMethod)) selectedMethod = "";
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
        <h2>Payment</h2>
        ${paypalSectionHtml()}
        ${walletSectionHtml()}
        ${bankSectionHtml()}
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
        <div id="modem-gmd-row" class="row hidden"><span>Mobile money (Dalasi)</span><span id="modem-gmd-amount"></span></div>
        <p id="sum-note" class="${shipOk ? "text-muted" : "form-error"}" style="margin-top:8px;">${escapeHtml(ship.note || "")}</p>
      </aside>
    `;

    const countryEl = document.getElementById("ship-country");
    if (countryEl) countryEl.addEventListener("change", () => loadPreview().catch((e) => showError(e.message)));
    const countryFilter = document.getElementById("ship-country-filter");
    if (countryFilter) countryFilter.addEventListener("input", filterCountryOptions);
    document.getElementById("apply-coupon").addEventListener("click", () => loadPreview().catch((e) => showError(e.message)));
    const chooseBank = document.getElementById("choose-bank");
    if (chooseBank) {
      chooseBank.addEventListener("click", () => {
        selectedMethod = selectedMethod === "manual" ? "" : "manual";
        toggleManualPanel();
      });
    }
    document.querySelectorAll("[data-wallet]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        showError("");
        btn.disabled = true;
        try {
          await startCheckout({ paymentMethod: "modem", walletNetwork: btn.getAttribute("data-wallet") });
        } catch (e) {
          showError(e.message);
        } finally {
          btn.disabled = false;
        }
      });
    });
    toggleManualPanel();
    document.getElementById("checkout-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (selectedMethod !== "manual") return;
      try {
        await startCheckout({ paymentMethod: "manual" });
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
    const show = hasMethod("modem") && quote && quote.amount;
    if (note) {
      note.classList.toggle("hidden", !show);
      if (show) {
        const rate = Number(quote.rate || 0).toFixed(2);
        note.textContent = "You will pay " + formatGmd(quote.amount)
          + " with Wave, AfriMoney, or QMoney"
          + " (converted from " + money(quote.original_cents, quote.original_currency)
          + " at 1 USD = " + rate + " GMD).";
      }
    }
    if (row) row.classList.toggle("hidden", !show);
    if (amt && show) amt.textContent = formatGmd(quote.amount);
  }

  function toggleManualPanel() {
    toggleModemQuote();
    const payBtn = document.getElementById("pay-btn");
    const chooseBank = document.getElementById("choose-bank");
    if (payBtn) payBtn.classList.toggle("hidden", selectedMethod !== "manual");
    if (chooseBank) chooseBank.classList.toggle("is-open", selectedMethod === "manual");
    if (selectedMethod === "manual") {
      renderManual(preview.manual_instructions);
    } else {
      const box = document.getElementById("manual-box");
      const rec = document.getElementById("receipt-section");
      if (box) box.classList.add("hidden");
      if (rec) rec.classList.add("hidden");
    }
    if (hasMethod("paypal")) mountPaypalButtons();
  }

  function renderManual(instr) {
    const box = document.getElementById("manual-box");
    const rec = document.getElementById("receipt-section");
    if (!box || !rec) return;
    box.classList.remove("hidden");
    rec.classList.remove("hidden");
    if (!instr) {
      box.innerHTML = "<p>Follow the payment instructions, then upload your receipt.</p>";
      return;
    }
    box.innerHTML = Object.values(instr).map((block) => `
      <h4>${escapeHtml(block.title || "Payment instructions")}</h4>
      <ul>${(block.fields || []).map((f) => `<li><strong>${escapeHtml(f.label)}:</strong> ${escapeHtml(f.value)}</li>`).join("")}</ul>
    `).join("");
  }

  function checkoutPayload() {
    return {
      items: cartItems(),
      coupon_code: document.getElementById("coupon-code").value.trim() || undefined,
      customer: {
        full_name: document.getElementById("cust-name").value.trim(),
        email: document.getElementById("cust-email").value.trim(),
        phone: document.getElementById("cust-phone").value.trim(),
      },
      delivery: delivery(),
    };
  }

  let paypalMountToken = 0;

  async function mountPaypalButtons() {
    const box = document.getElementById("paypal-button-container");
    if (!box || !hasMethod("paypal")) return;
    if (!window.PaypalCheckoutUi) {
      box.innerHTML = "<p class='form-error'>PayPal checkout failed to load. Refresh the page.</p>";
      return;
    }
    const cfg = preview && preview.paypal_sdk;
    if (!cfg || !cfg.client_id) {
      box.innerHTML = "<p class='form-error'>PayPal is not configured on the server.</p>";
      return;
    }
    const token = ++paypalMountToken;
    box.innerHTML = "<p class='text-muted'>Loading PayPal…</p>";
    try {
      await PaypalCheckoutUi.loadSdk(cfg.client_id, cfg.currency || (preview.totals && preview.totals.currency) || "USD");
      if (token !== paypalMountToken) return;
      await PaypalCheckoutUi.renderButtons("#paypal-button-container", {
        createOrder: async function () {
          showError("");
          if (needsShipping() && !(preview.shipping && preview.shipping.available)) {
            throw new Error("Select a shipping country first so FedEx shipping can be added.");
          }
          const form = document.getElementById("checkout-form");
          if (form && !form.reportValidity()) {
            throw new Error("Fill in your name, email, phone, and shipping details before paying.");
          }
          const res = await storeFetch("/api/store/checkout", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(Object.assign(checkoutPayload(), { payment_method: "paypal" })),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            const err = data.error;
            throw new Error(typeof err === "string" ? err : "Checkout failed");
          }
          currentPaymentRef = data.payment.payment_reference;
          const orderId = data.payment && data.payment.provider_payment_id;
          if (!orderId) throw new Error("PayPal did not start. Please try again.");
          return orderId;
        },
        onApprove: async function (data) {
          const res = await storeFetch("/api/store/checkout/verify/" + encodeURIComponent(currentPaymentRef), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paypal_order_id: data.orderID }),
          });
          const body = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(body.error || "PayPal capture failed.");
          saveStoreCart([]);
          window.location.href = body.order_url || ("store-order.html?order=" + encodeURIComponent((body.order || {}).order_number || ""));
        },
        onCancel: function () {
          showError("Payment was cancelled. You can pay with PayPal again.");
        },
        onError: function (err) {
          showError((err && err.message) || "PayPal could not complete this payment.");
        },
      });
    } catch (e) {
      if (token !== paypalMountToken) return;
      showError(e.message || "Could not open PayPal checkout.");
    }
  }

  async function startCheckout(opts) {
    opts = opts || {};
    const method = opts.paymentMethod || selectedMethod;
    const network = opts.walletNetwork || "";
    showError("");
    const form = document.getElementById("checkout-form");
    if (form && !form.reportValidity()) {
      throw new Error("Fill in your name, email, phone, and shipping details before paying.");
    }
    if (needsShipping() && !(preview.shipping && preview.shipping.available)) {
      throw new Error("Select a shipping country first so FedEx shipping can be added.");
    }
    if (method === "manual") {
      const file = (document.getElementById("receipt-file") || {}).files;
      if (!file || !file[0]) {
        throw new Error("Attach your payment receipt, then click Place order & pay.");
      }
    }
    const payBtn = document.getElementById("pay-btn");
    if (payBtn && method === "manual") {
      payBtn.disabled = true;
      payBtn.textContent = "Please wait…";
    }
    try {
      const res = await storeFetch("/api/store/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign(checkoutPayload(), {
          payment_method: method,
          wallet_network: network || undefined,
        })),
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
      if (method === "modem") {
        const link = data.payment && data.payment.payment_link;
        if (link) {
          window.location.href = link;
          return;
        }
        throw new Error("Mobile money checkout did not open. Please try PayPal or bank transfer.");
      }
      if (method === "manual") {
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
      if (payBtn && method === "manual") {
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

  function showSignInGate() {
    const next = "store-checkout.html" + (location.search || "");
    showRootMessage(`
      <div class="card" style="padding:24px;max-width:520px;margin:0 auto;">
        <h2>Sign in to buy</h2>
        <p>Create an account or sign in with your email and password, or with your phone number. Then you can complete this order, and see your purchases anytime you come back.</p>
        <p><a class="btn btn-primary btn-block" href="${storeAccountHref(next)}">Sign in or create account</a></p>
        <p class="text-muted" style="margin-top:12px;"><a href="store.html">Back to store</a></p>
      </div>`);
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
      storeCustomer = await getStoreCustomer();
      if (!storeCustomer) {
        showSignInGate();
        return;
      }
      await loadPreview();
    } catch (e) {
      showError(e.message);
      showRootMessage(`<p>${escapeHtml(e.message || "Could not load checkout.")}</p><p><a href="store.html">Back to store</a></p>`);
    }
  })();
})();
