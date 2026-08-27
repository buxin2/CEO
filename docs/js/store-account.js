(function () {
  const nextUrl = getQueryParam("next") || "store.html";

  function showError(msg) {
    const el = document.getElementById("account-error");
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
  }

  function safeNext(url) {
    const raw = (url || "store.html").trim();
    if (!raw || raw.indexOf("http") === 0 || raw.indexOf("//") === 0) return "store.html";
    return raw;
  }

  async function me() {
    const res = await storeFetch("/api/store/auth/me");
    if (res.status === 401) return null;
    const data = await res.json().catch(() => ({}));
    return data.customer || null;
  }

  function tabsHtml(active) {
    return `
      <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
        <button type="button" class="btn ${active === "email" ? "btn-primary" : "btn-secondary"} btn-sm" data-tab="email">Email &amp; password</button>
        <button type="button" class="btn ${active === "phone" ? "btn-primary" : "btn-secondary"} btn-sm" data-tab="phone">Phone number</button>
        <button type="button" class="btn ${active === "register" ? "btn-primary" : "btn-secondary"} btn-sm" data-tab="register">Create account</button>
        <button type="button" class="btn ${active === "help" ? "btn-primary" : "btn-secondary"} btn-sm" data-tab="help">Forgot password</button>
      </div>`;
  }

  function renderLoggedOut(tab) {
    tab = tab || "email";
    let form = "";
    if (tab === "phone") {
      form = `
        <h2>Sign in with phone</h2>
        <p class="text-muted">Use the phone number on your account and your password.</p>
        <form id="auth-form">
          <div class="form-group"><label class="form-label">Phone number</label><input class="form-control" id="auth-phone" required></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-control" id="auth-password" type="password" required></div>
          <button class="btn btn-primary btn-block" type="submit">Sign in</button>
        </form>`;
    } else if (tab === "register") {
      form = `
        <h2>Create your account</h2>
        <p class="text-muted">You need an account before buying. Sign in next time with email or phone.</p>
        <form id="auth-form">
          <div class="form-group"><label class="form-label">Full name</label><input class="form-control" id="auth-name" required></div>
          <div class="form-group"><label class="form-label">Email</label><input class="form-control" id="auth-email" type="email" required></div>
          <div class="form-group"><label class="form-label">Phone number</label><input class="form-control" id="auth-phone" required></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-control" id="auth-password" type="password" minlength="6" required></div>
          <button class="btn btn-primary btn-block" type="submit">Create account &amp; continue</button>
        </form>`;
    } else if (tab === "help") {
      form = `
        <h2>Forgot password?</h2>
        <p class="text-muted">Fill this form. It is sent to the store admin, who can help you get back in.</p>
        <form id="auth-form">
          <div class="form-group"><label class="form-label">Your name</label><input class="form-control" id="help-name" required></div>
          <div class="form-group"><label class="form-label">Email</label><input class="form-control" id="help-email" type="email"></div>
          <div class="form-group"><label class="form-label">Phone number</label><input class="form-control" id="help-phone"></div>
          <div class="form-group"><label class="form-label">Message</label><textarea class="form-control" id="help-message" rows="4" required placeholder="I forgot my password. My email / phone is…"></textarea></div>
          <button class="btn btn-primary btn-block" type="submit">Send to admin</button>
        </form>`;
    } else {
      form = `
        <h2>Sign in with email</h2>
        <p class="text-muted">Use your email and password. You can also sign in with your phone number.</p>
        <form id="auth-form">
          <div class="form-group"><label class="form-label">Email</label><input class="form-control" id="auth-email" type="email" required></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-control" id="auth-password" type="password" required></div>
          <button class="btn btn-primary btn-block" type="submit">Sign in</button>
        </form>`;
    }
    document.getElementById("account-root").innerHTML = `<div class="card" style="padding:20px;">${tabsHtml(tab)}${form}</div>`;
    document.querySelectorAll("[data-tab]").forEach((btn) => {
      btn.addEventListener("click", () => renderLoggedOut(btn.getAttribute("data-tab")));
    });
    document.getElementById("auth-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      showError("");
      try {
        if (tab === "help") {
          const res = await storeFetch("/api/store/auth/help", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              full_name: document.getElementById("help-name").value.trim(),
              email: document.getElementById("help-email").value.trim(),
              phone: document.getElementById("help-phone").value.trim(),
              message: document.getElementById("help-message").value.trim(),
            }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.error || "Could not send.");
          showToast("Sent to admin. We will help you from there.");
          renderLoggedOut("email");
          return;
        }
        const path = tab === "register" ? "/api/store/auth/register" : "/api/store/auth/login";
        const body = tab === "register"
          ? {
              full_name: document.getElementById("auth-name").value.trim(),
              email: document.getElementById("auth-email").value.trim(),
              phone: document.getElementById("auth-phone").value.trim(),
              password: document.getElementById("auth-password").value,
            }
          : tab === "phone"
            ? {
                phone: document.getElementById("auth-phone").value.trim(),
                password: document.getElementById("auth-password").value,
              }
            : {
                email: document.getElementById("auth-email").value.trim(),
                password: document.getElementById("auth-password").value,
              };
        const res = await storeFetch(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || "Could not sign in.");
        window.location.href = safeNext(nextUrl);
      } catch (e) {
        showError(e.message);
      }
    });
  }

  function orderUrl(o) {
    return "store-order.html?order=" + encodeURIComponent(o.order_number) + "&token=" + encodeURIComponent(o.access_token || "");
  }

  async function renderLoggedIn(customer) {
    const res = await storeFetch("/api/store/account/orders");
    const data = await res.json().catch(() => ({}));
    const orders = data.orders || [];
    document.getElementById("account-root").innerHTML = `
      <div class="card" style="padding:20px;margin-bottom:16px;">
        <h2>Hello, ${escapeHtml(customer.full_name || "there")}</h2>
        <p class="text-muted">${escapeHtml(customer.email)} · ${escapeHtml(customer.phone)}</p>
        <p><a class="btn btn-primary" href="${escapeHtml(safeNext(nextUrl === "store-account.html" ? "store.html" : nextUrl))}">Continue shopping</a>
        <button type="button" class="btn btn-secondary" id="sign-out-btn">Sign out</button></p>
      </div>
      <h3>Your orders</h3>
      ${orders.length ? orders.map((o) => `
        <a class="card" href="${escapeHtml(orderUrl(o))}" style="display:block;padding:14px 16px;margin-bottom:10px;text-decoration:none;">
          <div><strong>${escapeHtml(o.product_summary || o.order_number)}</strong></div>
          <div class="text-muted">${escapeHtml(o.order_number)} · ${escapeHtml(o.order_status || "")} · ${money(o.total_cents, o.currency)}</div>
        </a>`).join("") : "<p class='text-muted'>No purchases yet. When you buy a product, it will show here.</p>"}
    `;
    document.getElementById("sign-out-btn").addEventListener("click", async () => {
      await storeFetch("/api/store/auth/logout", { method: "POST" });
      window.location.href = "store-account.html";
    });
  }

  (async function init() {
    try {
      const customer = await me();
      if (customer) await renderLoggedIn(customer);
      else renderLoggedOut(getQueryParam("tab") || "email");
    } catch (e) {
      renderLoggedOut("email");
    }
  })();
})();
