(function () {
  const productId = getQueryParam("product_id");
  let membershipId = getQueryParam("membership_id");
  const communityToken = getQueryParam("token");
  const paymentRef = getQueryParam("payment_ref");
  const returnStatus = getQueryParam("status");
  let preview = null;
  let selectedMethod = "";
  let currentPaymentRef = paymentRef || "";
  let classInfo = null;
  let googleClientId = "";

  function cents(n) {
    return ((n || 0) / 100).toFixed(2);
  }

  function formatDesc(text) {
    const escaped = escapeHtml(text || "");
    return escaped.replace(/\n/g, "<br>");
  }

  function isPhoneBrowser() {
    const ua = navigator.userAgent || "";
    return /Android|iPhone|iPad|iPod|Mobile|webOS|BlackBerry|IEMobile|Opera Mini/i.test(ua)
      || ((navigator.maxTouchPoints || 0) > 1 && Math.min(window.innerWidth, window.innerHeight) < 900);
  }

  function classCheckoutNext() {
    const q = new URLSearchParams();
    if (communityToken) q.set("token", communityToken);
    if (membershipId) q.set("membership_id", membershipId);
    return "store-account.html?next=" + encodeURIComponent("checkout.html?" + q.toString());
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
    const res = typeof storeFetch === "function"
      ? await storeFetch("/api/checkout/preview?" + params.toString())
      : await fetch(apiUrl("/api/checkout/preview?" + params.toString()), { credentials: "include" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not load checkout");
    preview = data;
    renderPreview();
  }

  function renderPreview() {
    document.getElementById("checkout-loading").classList.add("hidden");
    document.getElementById("checkout-form").classList.remove("hidden");
    const t = preview.totals;
    const titleEl = document.getElementById("checkout-title");
    const summaryEl = document.getElementById("checkout-summary");
    let summary = "";
    if (preview.kind === "product") {
      if (titleEl) titleEl.classList.remove("hidden");
      if (summaryEl) summaryEl.classList.remove("hidden");
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
      const c = (preview && preview.community) || classInfo || {};
      classInfo = Object.assign({}, classInfo || {}, c);
      paintClassHero(classInfo, t);
      if (titleEl) titleEl.classList.add("hidden");
      if (summaryEl) summaryEl.classList.add("hidden");
      summary = "";
    }
    if (summaryEl) summaryEl.innerHTML = summary;
    const methods = preview.payment_methods || [];
    if (selectedMethod === "paypal") selectedMethod = "";
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
          <span class="pay-wallet-hint">${preview.kind === "product" ? "Pay now" : "Enroll"}</span>
        </button>
      </div>` : "";
    const bankHtml = methods.some((m) => m.id === "manual") ? `
      <button type="button" class="pay-bank-toggle" id="choose-bank">
        <strong>Bank / money transfer</strong>
        <span class="text-muted">Pay from your bank, then upload a receipt</span>
      </button>` : "";
    document.getElementById("payment-methods").innerHTML = paypalHtml + modemHtml + bankHtml;
    const payBtn = document.getElementById("pay-btn");
    if (payBtn) payBtn.textContent = preview.kind === "product" ? "Place order & pay" : "Enroll";
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
        if (selectedMethod !== "modem") {
          selectedMethod = "modem";
          toggleManualInstructions();
          toggleModemQuote();
          togglePaypalBox();
          return;
        }
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
    const show = selectedMethod === "modem" && quote && quote.amount;
    if (!el) return;
    el.classList.toggle("hidden", !show);
    const walletsBtn = document.getElementById("pay-wallets-btn");
    if (walletsBtn) walletsBtn.classList.toggle("is-selected", selectedMethod === "modem");
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
    const res = await (typeof storeFetch === "function" ? storeFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }) : fetch(apiUrl(url), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }));
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
    let msg = membershipId || communityToken
      ? "You're enrolled. Open the class to continue."
      : "Your payment was verified successfully.";
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

  function paintClassHero(c, totals) {
    const box = document.getElementById("class-hero");
    if (!box || !c) return;
    const titleEl = document.getElementById("checkout-title");
    if (titleEl) titleEl.classList.add("hidden");
    const price = totals
      ? cents(totals.total_cents) + " " + (totals.currency || "USD")
      : ("$" + ((c.price_cents || 0) / 100).toFixed(2) + " " + (c.currency || "USD"));
    const bill = (c.billing_interval || "one_time") === "month" ? " / month" : " total";
    box.innerHTML = `
      ${c.image_url ? `<img class="class-pay-cover" src="${escapeHtml(c.image_url)}" alt="${escapeHtml(c.name || "Class")}">` : ""}
      <div style="padding:22px 20px 0;">
        <p class="class-pay-kicker">Paid class</p>
        <h2 style="margin:0 0 8px;">${escapeHtml(c.name || "Class")}</h2>
        <p class="class-pay-fee">Total fee: ${escapeHtml(price)}${bill}</p>
        <p class="class-pay-kicker">What you will learn</p>
        <div class="class-pay-desc">${formatDesc(c.description || "Details will appear here.")}</div>
      </div>`;
    document.title = c.name || "Join class";
  }

  async function loadPublicClass() {
    if (!communityToken) return;
    const res = await fetch(apiUrl("/api/public/community/" + encodeURIComponent(communityToken)), { credentials: "include" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Class not found.");
    classInfo = data;
    paintClassHero(classInfo);
  }

  async function isStoreSignedIn() {
    try {
      const res = await storeFetch("/api/store/auth/me");
      if (res.ok) return true;
    } catch (e) {}
    try {
      const me = await fetch(apiUrl("/api/community-auth/me"), { credentials: "include" });
      if (!me.ok) return false;
      const data = await me.json();
      return !!(data && data.authenticated);
    } catch (e) {
      return false;
    }
  }

  async function joinIfNeeded() {
    if (!communityToken) return;
    const res = await storeFetch("/api/public/community/" + encodeURIComponent(communityToken) + "/join", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Could not join this class.");
    if (data.membership_id) membershipId = String(data.membership_id);
    if (data.status === "active" || data.needs_payment === false) {
      window.location.href = pageUrl("community.html?token=" + encodeURIComponent(communityToken));
      return false;
    }
    return true;
  }

  async function continueAfterSignIn() {
    showError("");
    document.getElementById("checkout-auth").classList.add("hidden");
    document.getElementById("checkout-loading").classList.remove("hidden");
    const stay = await joinIfNeeded();
    if (stay === false) return;
    if (!membershipId && !productId) throw new Error("Could not start class checkout.");
    await loadPreview();
  }

  async function signInWithGoogleCredential(credential) {
    const res = await storeFetch("/api/store/auth/google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: credential }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || "Google sign-in failed.");
    if (body.store_token) saveStoreToken(body.store_token);
    await continueAfterSignIn();
  }

  async function mountCheckoutGoogle() {
    const box = document.getElementById("checkout-google-btn");
    if (!box) return;
    const res = await storeFetch("/api/store/auth/google-config");
    const data = await res.json().catch(() => ({}));
    googleClientId = data.client_id || "";
    if (!googleClientId) {
      box.innerHTML = "<p class='text-muted'>Google sign-in is not configured.</p>";
      return;
    }
    if (isPhoneBrowser()) {
      box.innerHTML = `<a class="google-continue-btn" href="${escapeHtml(classCheckoutNext())}">Continue with Google</a>`;
      return;
    }
    if (!window.google || !window.google.accounts) {
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        script.async = true;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
    }
    window.google.accounts.id.initialize({
      client_id: googleClientId,
      callback: async (response) => {
        try {
          await signInWithGoogleCredential(response.credential);
        } catch (e) {
          showError(e.message);
        }
      },
    });
    window.google.accounts.id.renderButton(box, { theme: "outline", size: "large", width: 320 });
  }

  function showClassAuth() {
    document.getElementById("checkout-loading").classList.add("hidden");
    document.getElementById("checkout-form").classList.add("hidden");
    document.getElementById("checkout-auth").classList.remove("hidden");
    mountCheckoutGoogle().catch((e) => showError(e.message));
  }

  document.getElementById("chk-login-btn").addEventListener("click", async () => {
    showError("");
    try {
      const email = (document.getElementById("chk-login-email").value || "").trim();
      const password = document.getElementById("chk-login-pass").value || "";
      if (!email || !password) throw new Error("Enter your email and password.");
      const res = await storeFetch("/api/store/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Sign in failed.");
      if (data.store_token) saveStoreToken(data.store_token);
      await continueAfterSignIn();
    } catch (e) {
      showError(e.message);
    }
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
    if (!productId && !membershipId && !communityToken && !paymentRef) {
      showError("Missing checkout parameters.");
      return;
    }
    try {
      if (paymentRef && returnStatus === "return") {
        await verifyReturn();
        return;
      }
      if (communityToken || membershipId) {
        await loadPublicClass().catch(function () {});
        const signed = await isStoreSignedIn();
        if (!signed) {
          showClassAuth();
          return;
        }
        await continueAfterSignIn();
        return;
      }
      if (!productId && !membershipId) return;
      await loadPreview();
    } catch (e) {
      document.getElementById("checkout-loading").classList.add("hidden");
      showError(e.message);
    }
  })();
})();
