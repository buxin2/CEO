(function () {
  const SUGGESTED = [5, 10, 25, 50, 100];
  let product = null;
  let preview = null;
  let amount = 10;
  let selectedMethod = "paypal";
  let currentRef = "";

  function hasMethod(id) {
    return !!(preview && (preview.payment_methods || []).some((m) => m.id === id));
  }

  function cents() {
    return Math.round(Number(amount || 0) * 100);
  }

  function wakeNow() {
    if (typeof wakeApiServer === "function") {
      wakeApiServer().catch(function () {});
    }
  }

  function findProduct(catalog) {
    const slug = getQueryParam("p") || getQueryParam("slug") || "";
    const code = getQueryParam("c") || "";
    const list = (catalog && catalog.products) || [];
    if (slug) {
      const hit = list.find((p) => p.slug === slug);
      if (hit) return hit;
    }
    if (code && window.StoreShort) return StoreShort.findProduct(catalog, code);
    if (list.length === 1) return list[0];
    return null;
  }

  function paintThanks(status) {
    document.getElementById("donate-root").innerHTML = `
      <section class="sf-donate-card">
        <p class="sf-kicker">Thank you</p>
        <h1 class="sf-display">Your gift is received.</h1>
        <p class="sf-muted">You helped keep ${escapeHtml((product && product.title) || "this work")} moving. ${status ? "Status: " + escapeHtml(status) + "." : ""}</p>
        <a class="sf-btn sf-btn-primary" href="store.html">Back to the shop</a>
      </section>`;
  }

  function paint() {
    if (!product) {
      document.getElementById("donate-root").innerHTML = "<p class=\"sf-empty\">This give page was not found.</p>";
      return;
    }
    const img = product.cover_image || ((product.images || [])[0] && product.images[0].url) || "";
    const title = product.title || "this product";
    document.title = "Give · " + title;
    const productLink = document.getElementById("donate-product-link");
    if (productLink) productLink.href = "product.html?p=" + encodeURIComponent(product.slug);
    StoreStatic.applyBrand({ store_name: "Give", tagline: title });

    document.getElementById("donate-root").innerHTML = `
      <article class="sf-donate-hero">
        ${img ? `<img src="${escapeHtml(img)}" alt="${escapeHtml(title)}">` : ""}
        <div>
          <p class="sf-kicker">Give any amount</p>
          <h1 class="sf-display">${escapeHtml(title)}</h1>
          <p>This exists because people choose to keep it alive. Give what you can — even a small amount says this work matters.</p>
          <p class="sf-muted">No address. Name is optional. Pay with card, PayPal, Wave, or bank.</p>
        </div>
      </article>
      <section class="sf-donate-card">
        <label class="sf-muted" for="donate-name">Your name (optional)</label>
        <input class="form-control" id="donate-name" placeholder="If you want it on the thank-you">
        <p class="sf-muted" style="margin-top:16px;">Choose an amount in USD</p>
        <div class="sf-donate-amounts" id="donate-amounts">
          ${SUGGESTED.map((n) => `<button type="button" class="sf-chip ${n === amount ? "active" : ""}" data-amt="${n}">$${n}</button>`).join("")}
          <button type="button" class="sf-chip" data-amt="custom">Other</button>
        </div>
        <input class="form-control hidden" id="donate-custom" type="number" min="1" step="1" inputmode="decimal" placeholder="Any amount from $1">
        <p id="donate-error" class="sf-error hidden" style="margin-top:12px;"></p>
        <div id="donate-pay"></div>
        <p class="sf-muted" id="donate-wake" style="margin-top:14px;">Preparing a secure payment…</p>
      </section>
    `;
    document.getElementById("donate-amounts").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-amt]");
      if (!btn) return;
      document.querySelectorAll("#donate-amounts .sf-chip").forEach((el) => el.classList.remove("active"));
      btn.classList.add("active");
      const custom = document.getElementById("donate-custom");
      if (btn.dataset.amt === "custom") {
        custom.classList.remove("hidden");
        custom.focus();
        amount = Number(custom.value) || 1;
      } else {
        custom.classList.add("hidden");
        amount = Number(btn.dataset.amt);
      }
    });
    document.getElementById("donate-custom").addEventListener("input", () => {
      amount = Number(document.getElementById("donate-custom").value) || 0;
    });
    paintPay();
  }

  function showErr(msg) {
    const el = document.getElementById("donate-error");
    if (!el) return;
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
  }

  function paintPay() {
    const box = document.getElementById("donate-pay");
    if (!box) return;
    const paypal = hasMethod("paypal");
    const modem = hasMethod("modem");
    const manual = hasMethod("manual");
    box.innerHTML = `
      ${paypal ? `<div class="pay-section"><h3 class="pay-section-title">Card or PayPal</h3><div id="paypal-button-container"></div></div>` : ""}
      ${modem ? `
        <div class="pay-section">
          <h3 class="pay-section-title">Mobile money</h3>
          <button type="button" class="pay-wallets-card" id="donate-wave">
            <span class="pay-wallets-logos">
              <span class="pay-logo-tile wave"><img src="img/wallets/wave.jpg" alt="Wave"></span>
              <span class="pay-logo-tile afrimoney"><img src="img/wallets/afrimoney.png" alt="AfriMoney"></span>
              <span class="pay-logo-tile qmoney"><img src="img/wallets/qmoney.jpg" alt="QMoney"></span>
            </span>
            <span class="pay-wallets-caption">Wave · AfriMoney · QMoney</span>
          </button>
        </div>` : ""}
      ${manual ? `
        <div class="pay-section">
          <button type="button" class="pay-bank-toggle" id="donate-bank"><strong>Bank / money transfer</strong></button>
          <div id="manual-box" class="hidden card card-inner" style="margin-top:12px;"></div>
          <div id="receipt-section" class="hidden" style="margin-top:12px;">
            <label class="form-label">Receipt (optional after you transfer)</label>
            <input type="file" id="receipt-file" accept="image/*">
            <button type="button" class="sf-btn sf-btn-primary sf-btn-block" id="donate-bank-go" style="margin-top:10px;">Send donation details</button>
          </div>
        </div>` : ""}
    `;
    if (paypal) mountPaypal();
    const wave = document.getElementById("donate-wave");
    if (wave) wave.addEventListener("click", () => startDonate("modem").catch((e) => showErr(e.message)));
    const bank = document.getElementById("donate-bank");
    if (bank) bank.addEventListener("click", () => {
      selectedMethod = "manual";
      startDonate("manual").catch((e) => showErr(e.message));
    });
  }

  function donor() {
    return { full_name: (document.getElementById("donate-name") || {}).value || "" };
  }

  async function startDonate(method) {
    showErr("");
    if (cents() < 100) {
      showErr("Give at least $1.");
      return null;
    }
    selectedMethod = method;
    const res = await fetch(apiUrl("/api/donate"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_id: product.id,
        slug: product.slug,
        amount_cents: cents(),
        payment_method: method,
        customer: donor(),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not start the donation.");
    const pay = data.payment || {};
    currentRef = pay.payment_reference || "";
    if (method === "modem" && pay.payment_link) {
      window.open(pay.payment_link, "_blank", "noopener");
    }
    if (method === "manual") {
      const box = document.getElementById("manual-box");
      const rec = document.getElementById("receipt-section");
      if (box) {
        box.classList.remove("hidden");
        const instr = data.manual_instructions;
        box.innerHTML = instr
          ? Object.values(instr).map((block) => `
              <h4>${escapeHtml(block.title || "Bank details")}</h4>
              <ul>${(block.fields || []).map((f) => `<li><strong>${escapeHtml(f.label)}:</strong> ${escapeHtml(f.value)}</li>`).join("")}</ul>
            `).join("")
          : "<p>Transfer any amount, then upload a receipt if you have one.</p>";
      }
      if (rec) rec.classList.remove("hidden");
      const go = document.getElementById("donate-bank-go");
      if (go) go.onclick = uploadReceipt;
    }
    return pay;
  }

  async function uploadReceipt() {
    if (!currentRef) await startDonate("manual");
    const file = (document.getElementById("receipt-file") || {}).files && document.getElementById("receipt-file").files[0];
    const form = new FormData();
    if (file) form.append("receipt", file);
    const res = await fetch(apiUrl("/api/donate/receipt/" + encodeURIComponent(currentRef)), {
      method: "POST",
      credentials: "include",
      body: form,
    });
    const data = await res.json();
    if (!res.ok) {
      showErr(data.error || "Could not save the receipt.");
      return;
    }
    paintThanks((data.payment && data.payment.status) || "pending");
  }

  async function mountPaypal() {
    const box = document.getElementById("paypal-button-container");
    if (!box || !window.PaypalCheckoutUi) return;
    const cfg = preview && preview.paypal_sdk;
    if (!cfg || !cfg.client_id) {
      box.innerHTML = "<p class='sf-muted'>PayPal will appear once the server is ready.</p>";
      return;
    }
    try {
      await PaypalCheckoutUi.loadSdk(cfg.client_id, cfg.currency || "USD");
      await PaypalCheckoutUi.renderButtons("#paypal-button-container", {
        createOrder: async function () {
          try {
            const pay = await startDonate("paypal");
            if (!pay || !pay.provider_payment_id) throw new Error("PayPal did not start.");
            return pay.provider_payment_id;
          } catch (err) {
            showErr(err.message);
            throw err;
          }
        },
        onApprove: async function (approveData) {
          const body = await fetch(apiUrl("/api/donate/verify/" + encodeURIComponent(currentRef)), {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ paypal_order_id: approveData.orderID }),
          }).then((r) => r.json());
          paintThanks((body.payment && body.payment.status) || "succeeded");
        },
        onError: function (err) {
          showErr((err && err.message) || "PayPal could not complete this gift.");
        },
      });
    } catch (e) {
      box.innerHTML = "<p class='sf-muted'>" + escapeHtml(e.message) + "</p>";
    }
  }

  async function loadLivePay() {
    if (!product) return;
    try {
      const res = await fetch(apiUrl("/api/donate/preview?slug=" + encodeURIComponent(product.slug)), { credentials: "include" });
      const data = await res.json();
      if (res.ok) {
        preview = data;
        const wake = document.getElementById("donate-wake");
        if (wake) wake.textContent = "You can give now.";
        paintPay();
      }
    } catch (e) {}
  }

  async function maybeReturn() {
    const ref = getQueryParam("payment_ref");
    const status = getQueryParam("status");
    if (!ref || status !== "return") return false;
    try {
      const body = await fetch(apiUrl("/api/donate/verify/" + encodeURIComponent(ref)), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paypal_order_id: getQueryParam("token") || "" }),
      }).then((r) => r.json());
      product = product || { title: "this work", slug: getQueryParam("p") || "" };
      paintThanks((body.payment && body.payment.status) || "received");
      return true;
    } catch (e) {
      return false;
    }
  }

  wakeNow();
  StoreStatic.loadInstant().then(async (catalog) => {
    product = findProduct(catalog);
    if (await maybeReturn()) return;
    paint();
    loadLivePay();
  });
  StoreStatic.refreshLive().then((live) => {
    if (!live) return;
    const found = findProduct(live);
    if (found) product = found;
    loadLivePay();
  });
})();
