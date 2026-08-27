(function () {
  requireAuth();
  let settings = null;

  function cents(n) {
    return ((n || 0) / 100).toFixed(2);
  }

  function showErr(msg) {
    const el = document.getElementById("pay-settings-error");
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
  }

  function showOk(msg) {
    const el = document.getElementById("pay-settings-ok");
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
  }

  function paintMode() {
    const live = settings && settings.mode === "live";
    document.getElementById("mode-live").className = "btn " + (live ? "btn-primary" : "btn-secondary");
    document.getElementById("mode-test").className = "btn " + (live ? "btn-secondary" : "btn-primary");
    document.getElementById("mode-label").textContent = live
      ? "Currently: LIVE — real charges."
      : "Currently: TEST — PayPal sandbox + test Wave secret if saved.";
  }

  function fillPlaceholders() {
    const map = [
      ["paypal-client-id", settings.paypal_client_id_masked],
      ["paypal-secret", settings.paypal_secret_masked],
      ["paypal-sandbox-id", settings.paypal_sandbox_client_id_masked],
      ["paypal-sandbox-secret", settings.paypal_sandbox_secret_masked],
      ["modem-public", settings.modem_public_masked],
      ["modem-secret", settings.modem_secret_masked],
      ["modem-test-secret", settings.modem_test_secret_masked],
      ["modem-webhook", settings.modem_webhook_masked],
    ];
    map.forEach(([id, masked]) => {
      const el = document.getElementById(id);
      if (el) el.placeholder = masked ? "Saved " + masked : "Not set";
      if (el) el.value = "";
    });
    document.getElementById("brand-name").value = settings.brand_name || "Store";
    document.getElementById("test-note").textContent = settings.test_note || "";
  }

  async function loadSettings() {
    settings = await apiRequest("/api/admin/payment-settings");
    paintMode();
    fillPlaceholders();
  }

  async function save(payload) {
    showErr("");
    showOk("");
    settings = await apiRequest("/api/admin/payment-settings", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    paintMode();
    fillPlaceholders();
    showOk("Saved.");
  }

  document.getElementById("mode-live").addEventListener("click", () => save({ mode: "live" }).catch((e) => showErr(e.message)));
  document.getElementById("mode-test").addEventListener("click", () => save({ mode: "test" }).catch((e) => showErr(e.message)));

  document.getElementById("paypal-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await save({
        brand_name: document.getElementById("brand-name").value.trim(),
        paypal_client_id: document.getElementById("paypal-client-id").value.trim(),
        paypal_secret: document.getElementById("paypal-secret").value.trim(),
        paypal_sandbox_client_id: document.getElementById("paypal-sandbox-id").value.trim(),
        paypal_sandbox_secret: document.getElementById("paypal-sandbox-secret").value.trim(),
      });
    } catch (e) {
      showErr(e.message);
    }
  });

  document.getElementById("modem-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      await save({
        modem_public_key: document.getElementById("modem-public").value.trim(),
        modem_secret: document.getElementById("modem-secret").value.trim(),
        modem_test_secret: document.getElementById("modem-test-secret").value.trim(),
        modem_webhook_secret: document.getElementById("modem-webhook").value.trim(),
      });
    } catch (e) {
      showErr(e.message);
    }
  });

  async function ping(provider) {
    document.getElementById("test-result").textContent = "Checking keys…";
    try {
      const data = await apiRequest("/api/admin/payment-settings/ping", {
        method: "POST",
        body: JSON.stringify({ provider }),
      });
      document.getElementById("test-result").textContent = data.message || "OK";
      if (data.payment_link) {
        document.getElementById("test-result").innerHTML +=
          ` <a href="${escapeHtml(data.payment_link)}" target="_blank" rel="noopener">Open Wave test page</a>`;
      }
    } catch (e) {
      document.getElementById("test-result").textContent = e.message;
    }
  }

  async function testPay(provider) {
    document.getElementById("test-result").textContent = "Starting test checkout…";
    try {
      const data = await apiRequest("/api/admin/payments/test", {
        method: "POST",
        body: JSON.stringify({ provider }),
      });
      const pay = data.payment || {};
      const link = pay.payment_link;
      if (link) {
        document.getElementById("test-result").innerHTML =
          "Test payment " + escapeHtml(pay.payment_reference) + " — opening checkout.";
        window.open(link, "_blank", "noopener");
        return;
      }
      document.getElementById("test-result").textContent =
        "Created " + (pay.payment_reference || "payment") + " but no checkout link was returned.";
    } catch (e) {
      document.getElementById("test-result").textContent = e.message;
    }
  }

  document.getElementById("ping-paypal").addEventListener("click", () => ping("paypal"));
  document.getElementById("ping-modem").addEventListener("click", () => ping("modem"));
  document.getElementById("test-paypal").addEventListener("click", () => testPay("paypal"));
  document.getElementById("test-modem").addEventListener("click", () => testPay("modem"));

  async function loadPayments() {
    const data = await apiRequest("/api/admin/payments");
    const s = data.summary || {};
    document.getElementById("payments-summary").innerHTML = `
      <p><strong>Total:</strong> ${s.total} · <strong>Successful:</strong> ${s.succeeded} ·
      <strong>Pending:</strong> ${s.pending} · <strong>Manual pending:</strong> ${s.manual_pending} ·
      <strong>Revenue:</strong> ${cents(s.revenue_cents)}</p>`;
    document.getElementById("payments-list").innerHTML = (data.payments || []).map((p) => `
      <div class="card card-inner" style="margin-bottom:8px;">
        <div><strong>${escapeHtml(p.payment_reference)}</strong> · ${escapeHtml(p.payment_kind)} · ${escapeHtml(p.status)}</div>
        <div>${cents(p.total_cents)} ${escapeHtml(p.currency)} · ${escapeHtml(p.provider)} · ${escapeHtml(p.customer_name || p.customer_email || "")}</div>
        ${p.receipt_url ? `<a href="${escapeHtml(p.receipt_url)}" target="_blank" rel="noopener">View receipt</a>` : ""}
        ${p.status === "manual_pending" ? `
          <button class="btn btn-primary btn-sm" onclick="approvePayment(${p.id})">Approve</button>
          <button class="btn btn-secondary btn-sm" onclick="rejectPayment(${p.id})">Reject</button>` : ""}
      </div>`).join("") || "<p class=\"text-muted\">No payments yet.</p>";
  }

  window.approvePayment = async (id) => {
    await apiRequest(`/api/admin/payments/${id}/approve`, { method: "POST", body: JSON.stringify({}) });
    await loadPayments();
  };
  window.rejectPayment = async (id) => {
    const note = prompt("Rejection reason (optional)") || "";
    await apiRequest(`/api/admin/payments/${id}/reject`, { method: "POST", body: JSON.stringify({ note }) });
    await loadPayments();
  };

  async function maybeVerifyReturn() {
    const params = new URLSearchParams(location.search);
    const ref = params.get("payment_ref");
    const status = params.get("status");
    if (!ref || status !== "return") return;
    try {
      const data = await apiRequest("/api/checkout/verify/" + encodeURIComponent(ref), {
        method: "POST",
        body: JSON.stringify({ paypal_order_id: params.get("token") || "" }),
      });
      const st = (data.payment && data.payment.status) || "";
      document.getElementById("test-result").textContent = "Test return: " + st;
    } catch (e) {
      document.getElementById("test-result").textContent = e.message;
    }
  }

  loadSettings().catch((e) => showErr(e.message));
  loadPayments().catch((e) => showErr(e.message));
  maybeVerifyReturn();
})();
