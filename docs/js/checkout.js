(function () {
  const productId = getQueryParam("product_id");
  const membershipId = getQueryParam("membership_id");
  const communityToken = getQueryParam("token");
  const paymentRef = getQueryParam("payment_ref");
  const returnStatus = getQueryParam("status");
  let preview = null;
  let selectedMethod = "";
  let currentPaymentRef = paymentRef || "";

  function cents(n) {
    return ((n || 0) / 100).toFixed(2);
  }

  function hasMethod(id) {
    return !!(preview && (preview.payment_methods || []).some((m) => m.id === id));
  }

  function showError(msg) {
    const el = document.getElementById("checkout-error");
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  async function loadPreview() {
    const params = new URLSearchParams();
    if (productId) params.set("product_id", productId);
    if (membershipId) params.set("membership_id", membershipId);
    const coupon = document.getElementById("coupon-code").value.trim();
    if (coupon) params.set("coupon_code", coupon);
    if (productId) params.set("quantity", getQueryParam("quantity") || "1");
    const res = await fetch(apiUrl("/api/checkout/preview?" + params.toString()), { credentials: "include" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not load checkout");
    preview = data;
    renderPreview();
  }

  function renderPreview() {
    document.getElementById("checkout-loading").classList.add("hidden");
    document.getElementById("checkout-form").classList.remove("hidden");
    const t = preview.totals;
    let summary = "";
    if (preview.kind === "product") {
      const p = preview.product;
      summary = `
        <img src="${escapeHtml(p.image_url)}" alt="" style="max-width:120px;border-radius:8px;margin-bottom:8px;">
        <h3>${escapeHtml(p.name)}</h3>
        <p>Qty: ${t.quantity} × ${cents(t.unit_price_cents)} ${escapeHtml(t.currency)}</p>
        <p>Subtotal: ${cents(t.subtotal_cents)} ${escapeHtml(t.currency)}</p>
        ${t.fee_cents ? `<p>Fees: ${cents(t.fee_cents)}</p>` : ""}
        ${t.discount_cents ? `<p>Discount: -${cents(t.discount_cents)}</p>` : ""}
        <p><strong>Total: ${cents(t.total_cents)} ${escapeHtml(t.currency)}</strong></p>`;
      if (p.product_type === "physical") {
        document.getElementById("delivery-section").classList.remove("hidden");
      }
    } else {
      const c = preview.community;
      summary = `
        <h3>${escapeHtml(c.name)}</h3>
        <p>Community membership</p>
        <p><strong>Total: ${cents(t.total_cents)} ${escapeHtml(t.currency)}</strong></p>`;
    }
    document.getElementById("checkout-summary").innerHTML = summary;
    const methods = preview.payment_methods || [];
    if (selectedMethod === "paypal" || selectedMethod === "modem") selectedMethod = "";
    const paypalHtml = methods.some((m) => m.id === "paypal") ? `
      <div class="pay-section" id="paypal-section">
        <h3 class="pay-section-title">PayPal payment</h3>
      </div>` : "";
    const modemHtml = methods.some((m) => m.id === "modem") ? `
      <div class="pay-section">
        <h3 class="pay-section-title">Mobile money</h3>
        <p id="modem-gmd-note" class="text-muted hidden"></p>
        <button type="button" class="pay-wallets-card" id="pay-wallets-btn">
          <span class="pay-wallets-logos">
            <span class="pay-logo-tile wave"><img src="img/wallets/wave.jpg" alt="Wave"></span>
            <span class="pay-logo-tile afrimoney"><img src="img/wallets/afrimoney.png" alt="AfriMoney"></span>
            <span class="pay-logo-tile qmoney"><img src="img/wallets/qmoney.jpg" alt="QMoney"></span>
          </span>
          <span class="pay-wallets-caption">Wave · AfriMoney · QMoney</span>
          <span class="pay-wallet-hint">Pay now</span>
        </button>
      </div>` : "";
    const bankHtml = methods.some((m) => m.id === "manual") ? `
      <button type="button" class="pay-bank-toggle" id="choose-bank">
        <strong>Bank / money transfer</strong>
        <span class="text-muted">Pay from your bank, then upload a receipt</span>
      </button>` : "";
    document.getElementById("payment-methods").innerHTML = paypalHtml + modemHtml + bankHtml;
    const paypalBox = document.getElementById("paypal-box");
    if (paypalBox) {
      paypalBox.classList.toggle("hidden", !methods.some((m) => m.id === "paypal"));
      const section = document.getElementById("paypal-section");
      if (section && paypalBox.parentNode) {
        section.appendChild(paypalBox);
        paypalBox.classList.remove("hidden");
      }
    }
    const walletsBtn = document.getElementById("pay-wallets-btn");
    if (walletsBtn) {
      walletsBtn.addEventListener("click", async () => {
        showError("");
        walletsBtn.disabled = true;
        try {
          selectedMethod = "modem";
          await startCheckout({ paymentMethod: "modem" });
        } catch (e) {
          showError(e.message);
        } finally {
          walletsBtn.disabled = false;
        }
      });
    }
    const chooseBank = document.getElementById("choose-bank");
    if (chooseBank) {
      chooseBank.addEventListener("click", () => {
        selectedMethod = selectedMethod === "manual" ? "" : "manual";
        toggleManualInstructions();
        toggleModemQuote();
        togglePaypalBox();
      });
    }
    toggleManualInstructions();
    toggleModemQuote();
    togglePaypalBox();
  }

  function togglePaypalBox() {
    const payBtn = document.getElementById("pay-btn");
    const chooseBank = document.getElementById("choose-bank");
    if (payBtn) payBtn.classList.toggle("hidden", selectedMethod !== "manual");
    if (chooseBank) chooseBank.classList.toggle("is-open", selectedMethod === "manual");
    if (hasMethod("paypal")) mountPaypalButtons();
  }

  let paypalMountToken = 0;

  async function mountPaypalButtons() {
    const box = document.getElementById("paypal-button-container");
    if (!box || !hasMethod("paypal")) return;
    const cfg = preview && preview.paypal_sdk;
    if (!window.PaypalCheckoutUi || !cfg || !cfg.client_id) {
      if (box) box.innerHTML = "<p class='form-error'>PayPal is not configured.</p>";
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
          const data = await startCheckout({ paymentMethod: "paypal", forPaypalButtons: true });
          const orderId = data && data.payment && data.payment.provider_payment_id;
          if (!orderId) throw new Error("PayPal did not start. Please try again.");
          return orderId;
        },
        onApprove: async function (data) {
          const res = await fetch(apiUrl("/api/checkout/verify/" + encodeURIComponent(currentPaymentRef)), {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paypal_order_id: data.orderID }),
          });
          const body = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(body.error || "PayPal capture failed.");
          showSuccess(body);
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
      showError(e.message || "Could not open card / PayPal checkout.");
    }
  }

  function toggleModemQuote() {
    const el = document.getElementById("modem-gmd-note");
    const quote = preview && preview.modem_gmd;
    const show = hasMethod("modem") && quote && quote.amount;
    if (!el) return;
    el.classList.toggle("hidden", !show);
    if (show) {
      const gmd = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(quote.amount);
      el.textContent = "You will pay " + gmd + " GMD with Wave, AfriMoney, or QMoney (1 USD = "
        + Number(quote.rate || 0).toFixed(2) + " GMD).";
    }
  }

  function toggleManualInstructions() {
    const box = document.getElementById("manual-instructions");
    if (selectedMethod !== "manual") {
      box.classList.add("hidden");
      return;
    }
    box.classList.remove("hidden");
    box.innerHTML = "<p class=\"text-muted\">Payment instructions will appear after you start checkout.</p>";
  }

  function renderManualInstructions(instr) {
    if (!instr) return;
    const html = Object.values(instr).map((block) => `
      <h4>${escapeHtml(block.title || "")}</h4>
      <ul>${(block.fields || []).map((f) => `<li><strong>${escapeHtml(f.label)}:</strong> ${escapeHtml(f.value)}</li>`).join("")}</ul>
    `).join("");
    document.getElementById("manual-instructions").innerHTML = html;
    document.getElementById("receipt-section").classList.remove("hidden");
  }

  async function startCheckout(opts) {
    opts = opts || {};
    const method = opts.paymentMethod || selectedMethod;
    const network = opts.walletNetwork || "";
    const forPaypalButtons = !!opts.forPaypalButtons;
    const body = {
      coupon_code: document.getElementById("coupon-code").value.trim() || undefined,
      payment_method: method,
      wallet_network: network || undefined,
      customer: {
        full_name: document.getElementById("customer-name").value.trim(),
        phone: document.getElementById("customer-phone").value.trim(),
      },
    };
    let url = "/api/checkout/product";
    if (membershipId) {
      url = "/api/checkout/membership";
      body.membership_id = parseInt(membershipId, 10);
    } else {
      body.product_id = parseInt(productId, 10);
      body.quantity = parseInt(getQueryParam("quantity") || "1", 10);
    }
    const res = await fetch(apiUrl(url), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Checkout failed");
    currentPaymentRef = data.payment.payment_reference;
    if (data.manual_instructions) renderManualInstructions(data.manual_instructions);
    if (data.payment.status === "succeeded") {
      return showSuccess(data);
    }
    if (forPaypalButtons) return data;
    if (method === "modem") {
      if (data.payment.payment_link) {
        window.location.href = data.payment.payment_link;
        return;
      }
    }
    if (method === "paypal" && data.payment.payment_link) {
      window.location.href = data.payment.payment_link;
      return data;
    }
    if (method === "manual") {
      showToast("Complete payment externally, then upload your receipt below.");
    }
    return data;
  }

  async function showSuccess(data) {
    document.getElementById("checkout-form").classList.add("hidden");
    document.getElementById("checkout-success").classList.remove("hidden");
    let msg = "Your payment was verified successfully.";
    if (data.order && data.order.product_type === "digital") {
      msg += " Check your digital access below.";
      if (data.order.digital_delivery_url) {
        msg += ` <a href="${escapeHtml(data.order.digital_delivery_url)}" target="_blank" rel="noopener">Open digital product</a>`;
      }
      if (data.order.digital_delivery_text) {
        msg += `<pre>${escapeHtml(data.order.digital_delivery_text)}</pre>`;
      }
    }
    document.getElementById("success-message").innerHTML = msg;
    const continueUrl = communityToken ? pageUrl("community.html?token=" + encodeURIComponent(communityToken)) : pageUrl("community.html");
    document.getElementById("success-continue").href = continueUrl;
  }

  document.getElementById("apply-coupon-btn").addEventListener("click", () => loadPreview().catch((e) => showError(e.message)));
  document.getElementById("pay-btn").addEventListener("click", async () => {
    if (selectedMethod !== "manual") return;
    try {
      await startCheckout({ paymentMethod: "manual" });
    } catch (e) {
      showError(e.message);
    }
  });

  document.getElementById("submit-receipt-btn").addEventListener("click", async () => {
    if (!currentPaymentRef) {
      showError("Start checkout first.");
      return;
    }
    const file = document.getElementById("receipt-file").files[0];
    const form = new FormData();
    if (file) form.append("receipt", file);
    const res = await fetch(apiUrl("/api/checkout/receipt/" + encodeURIComponent(currentPaymentRef)), {
      method: "POST",
      credentials: "include",
      body: form,
    });
    const data = await res.json();
    if (!res.ok) {
      showError(data.error || "Upload failed");
      return;
    }
    showToast("Receipt submitted — waiting for admin approval.");
  });

  async function verifyReturn() {
    if (!paymentRef || returnStatus !== "return") return;
    const paypalOrderId = getQueryParam("token") || getQueryParam("PayerID");
    const res = await fetch(apiUrl("/api/checkout/verify/" + encodeURIComponent(paymentRef)), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paypal_order_id: paypalOrderId }),
    });
    const data = await res.json();
    if (res.ok && data.payment && data.payment.status === "succeeded") {
      showSuccess(data);
    }
  }

  (async function init() {
    if (!productId && !membershipId && !paymentRef) {
      showError("Missing checkout parameters.");
      return;
    }
  try {
      if (paymentRef && returnStatus === "return") {
        await verifyReturn();
        return;
      }
      if (!productId && !membershipId) return;
      await loadPreview();
    } catch (e) {
      showError(e.message);
    }
  })();
})();
