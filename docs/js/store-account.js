(function () {
  const nextUrl = getQueryParam("next") || "store.html";
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function showError(msg) {
    const el = document.getElementById("account-error");
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
    el.classList.toggle("visible", !!msg);
    if (msg) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function safeNext(url) {
    const raw = (url || "store.html").trim();
    if (!raw || raw.indexOf("http") === 0 || raw.indexOf("//") === 0) return "store.html";
    return raw;
  }

  let googleClientId = null;
  let googleClientIdLoaded = false;

  function googleHtml() {
    return `<div class="google-signin-wrap"><div id="google-signin-btn"></div></div>`;
  }

  function googleDivider(label) {
    return `<div class="auth-or"><span>${label || "or"}</span></div>`;
  }

  function isPhoneBrowser() {
    const ua = navigator.userAgent || "";
    return /Android|iPhone|iPad|iPod|Mobile|webOS|BlackBerry|IEMobile|Opera Mini/i.test(ua)
      || ((navigator.maxTouchPoints || 0) > 1 && Math.min(window.innerWidth, window.innerHeight) < 900);
  }

  function googleRedirectUri() {
    const url = new URL("store-account.html", window.location.href);
    url.search = "";
    url.hash = "";
    return url.href;
  }

  function b64url(buffer) {
    const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function randomB64(len) {
    const arr = new Uint8Array(len);
    crypto.getRandomValues(arr);
    return b64url(arr);
  }

  function stripGoogleReturn() {
    const url = new URL(window.location.href);
    ["code", "state", "scope", "authuser", "prompt", "hd", "session_state", "error", "error_description"].forEach((key) => {
      url.searchParams.delete(key);
    });
    url.hash = "";
    history.replaceState(null, "", url.pathname + (url.search || "") + url.hash);
  }

  function clearGoogleOauthScratch() {
    ["google_nonce", "google_pkce", "google_state", "google_next", "google_redirect"].forEach((key) => {
      try { localStorage.removeItem(key); } catch (e) {}
      try { sessionStorage.removeItem(key); } catch (e) {}
    });
  }

  async function completeGoogleSignIn(credential) {
    const nonce = localStorage.getItem("google_nonce") || sessionStorage.getItem("google_nonce") || "";
    const res = await storeFetch("/api/store/auth/google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: credential, nonce: nonce || undefined }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Google sign-in failed.");
    if (data.store_token) saveStoreToken(data.store_token);
    const next = localStorage.getItem("google_next") || sessionStorage.getItem("google_next") || nextUrl;
    clearGoogleOauthScratch();
    window.location.replace(safeNext(next));
  }

  async function consumeGoogleReturn() {
    const qs = new URLSearchParams(window.location.search);
    const hash = new URLSearchParams((window.location.hash || "").replace(/^#/, ""));
    const err = qs.get("error") || hash.get("error");
    if (err) {
      stripGoogleReturn();
      clearGoogleOauthScratch();
      throw new Error("Google sign-in was cancelled. Try again.");
    }
    const code = qs.get("code") || hash.get("code") || "";
    const idToken = hash.get("id_token") || qs.get("id_token") || "";
    if (!code && !idToken) return false;
    const expectedState = localStorage.getItem("google_state") || "";
    const gotState = qs.get("state") || hash.get("state") || "";
    if (code && expectedState && gotState && expectedState !== gotState) {
      stripGoogleReturn();
      clearGoogleOauthScratch();
      throw new Error("Google sign-in expired. Try again.");
    }
    const redirectUri = localStorage.getItem("google_redirect") || googleRedirectUri();
    const verifier = localStorage.getItem("google_pkce") || "";
    const next = localStorage.getItem("google_next") || sessionStorage.getItem("google_next") || nextUrl;
    stripGoogleReturn();
    if (code) {
      const res = await storeFetch("/api/store/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: code,
          redirect_uri: redirectUri,
          code_verifier: verifier,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Google sign-in failed.");
      if (data.store_token) saveStoreToken(data.store_token);
      clearGoogleOauthScratch();
      window.location.replace(safeNext(next));
      return true;
    }
    await completeGoogleSignIn(idToken);
    return true;
  }

  async function startGoogleRedirect(clientId) {
    const nonce = randomB64(16);
    const state = randomB64(16);
    localStorage.setItem("google_nonce", nonce);
    localStorage.setItem("google_state", state);
    localStorage.setItem("google_next", nextUrl);
    localStorage.setItem("google_redirect", googleRedirectUri());
    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: googleRedirectUri(),
      response_type: "code",
      scope: "openid email profile",
      nonce: nonce,
      state: state,
      prompt: "select_account",
    });
    window.location.href = "https://accounts.google.com/o/oauth2/v2/auth?" + params.toString();
  }

  function phoneGoogleButtonHtml() {
    return `<button type="button" class="google-continue-btn" id="google-continue-btn">
      <svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 8 3.1l5.7-5.7C34.2 6.1 29.4 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.3-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 16 19 12 24 12c3.1 0 5.8 1.2 8 3.1l5.7-5.7C34.2 6.1 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 10-2 13.6-5.2l-6.3-5.3C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.6 39.6 16.3 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-1.1 3.2-3.5 5.8-6.6 7.2l6.3 5.3C37.3 38.2 44 33 44 24c0-1.2-.1-2.3-.4-3.5z"/></svg>
      Continue with Google
    </button>`;
  }

  function loadGsi() {
    if (window.google && window.google.accounts && window.google.accounts.id) {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const existing = document.getElementById("google-gsi");
      if (existing) {
        existing.addEventListener("load", () => resolve());
        existing.addEventListener("error", () => reject(new Error("Could not load Google sign-in.")));
        return;
      }
      const script = document.createElement("script");
      script.id = "google-gsi";
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Could not load Google sign-in."));
      document.head.appendChild(script);
    });
  }

  async function mountGoogleButton() {
    const box = document.getElementById("google-signin-btn");
    if (!box) return;
    try {
      if (!googleClientIdLoaded) {
        const res = await storeFetch("/api/store/auth/google-config");
        const data = await res.json().catch(() => ({}));
        googleClientId = data.client_id || "";
        googleClientIdLoaded = true;
      }
      if (!googleClientId) {
        const wrap = box.closest(".google-signin-wrap");
        const orEl = document.querySelector(".auth-or");
        if (wrap) wrap.remove();
        if (orEl) orEl.remove();
        return;
      }
      if (isPhoneBrowser()) {
        box.innerHTML = phoneGoogleButtonHtml();
        const btn = document.getElementById("google-continue-btn");
        if (btn) btn.addEventListener("click", () => {
          startGoogleRedirect(googleClientId).catch((e) => showError(e.message));
        });
        return;
      }
      await loadGsi();
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async (response) => {
          showError("");
          try {
            await completeGoogleSignIn(response.credential);
          } catch (e) {
            showError(e.message);
          }
        },
      });
      box.innerHTML = "";
      window.google.accounts.id.renderButton(box, {
        theme: "outline",
        size: "large",
        type: "standard",
        text: "continue_with",
        shape: "rectangular",
        width: Math.min(Math.max(box.parentElement.offsetWidth || 320, 240), 400),
      });
    } catch (e) {
      box.innerHTML = "";
    }
  }

  async function me() {
    const res = await storeFetch("/api/store/auth/me");
    if (res.status === 401) return null;
    const data = await res.json().catch(() => ({}));
    return data.customer || null;
  }

  function tabsHtml(active) {
    const tabs = [
      { id: "email", label: "Sign in" },
      { id: "phone", label: "Phone" },
      { id: "register", label: "Create account" },
      { id: "help", label: "Forgot password" },
    ];
    return `<div class="store-auth-tabs">${tabs.map((t) =>
      `<button type="button" class="btn ${active === t.id ? "btn-primary" : "btn-secondary"}" data-tab="${t.id}">${t.label}</button>`
    ).join("")}</div>`;
  }

  function renderLoggedOut(tab) {
    tab = tab || "email";
    let form = "";
    if (tab === "phone") {
      form = `
        <h2>Sign in with phone</h2>
        <p class="text-muted">Use the phone number on your account and your password.</p>
        <form id="auth-form" novalidate>
          <div class="form-group"><label class="form-label">Phone number</label><input class="form-control" id="auth-phone" inputmode="tel" autocomplete="tel"></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-control" id="auth-password" type="password" autocomplete="current-password"></div>
          <button class="btn btn-primary btn-block" type="submit">Sign in</button>
        </form>
        ${googleDivider("or continue with Google")}
        ${googleHtml()}`;
    } else if (tab === "register") {
      form = `
        <h2>Create your account</h2>
        <p class="text-muted">You need an account before buying. Use a real email so we can help if you forget your password.</p>
        <form id="auth-form" novalidate>
          <div class="form-group"><label class="form-label">Full name</label><input class="form-control" id="auth-name" autocomplete="name"></div>
          <div class="form-group"><label class="form-label">Email</label><input class="form-control" id="auth-email" type="email" autocomplete="email" inputmode="email"></div>
          <div class="form-group"><label class="form-label">Phone number</label><input class="form-control" id="auth-phone" inputmode="tel" autocomplete="tel"></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-control" id="auth-password" type="password" autocomplete="new-password"><p class="text-muted" style="margin-top:6px;">At least 6 characters.</p></div>
          <button class="btn btn-primary btn-block" type="submit">Create account</button>
        </form>
        ${googleDivider("or continue with Google")}
        ${googleHtml()}`;
    } else if (tab === "help") {
      form = `
        <h2>Forgot password?</h2>
        <p class="text-muted">Send this to the store admin. They can set a new password for you. After they do, sign in with that password — you will also see it in your account messages.</p>
        <form id="auth-form" novalidate>
          <div class="form-group"><label class="form-label">Your name</label><input class="form-control" id="help-name"></div>
          <div class="form-group"><label class="form-label">Email</label><input class="form-control" id="help-email" type="email" inputmode="email"></div>
          <div class="form-group"><label class="form-label">Phone number</label><input class="form-control" id="help-phone" inputmode="tel"></div>
          <div class="form-group"><label class="form-label">Message</label><textarea class="form-control" id="help-message" rows="4" placeholder="I forgot my password. My email / phone is…"></textarea></div>
          <button class="btn btn-primary btn-block" type="submit">Send to admin</button>
        </form>`;
    } else {
      form = `
        <h2>Sign in</h2>
        <p class="text-muted">Continue with Google, or use your email and password.</p>
        ${googleHtml()}
        ${googleDivider("or email")}
        <form id="auth-form" novalidate>
          <div class="form-group"><label class="form-label">Email</label><input class="form-control" id="auth-email" type="email" autocomplete="email" inputmode="email"></div>
          <div class="form-group"><label class="form-label">Password</label><input class="form-control" id="auth-password" type="password" autocomplete="current-password"></div>
          <button class="btn btn-primary btn-block" type="submit">Sign in</button>
        </form>`;
    }
    document.getElementById("account-root").innerHTML = `<div class="card store-account-card">${tabsHtml(tab)}${form}</div>`;
    document.querySelectorAll("[data-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        showError("");
        renderLoggedOut(btn.getAttribute("data-tab"));
      });
    });
    document.getElementById("auth-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      showError("");
      try {
        if (tab === "help") {
          const name = (document.getElementById("help-name").value || "").trim();
          const email = (document.getElementById("help-email").value || "").trim();
          const phone = (document.getElementById("help-phone").value || "").trim();
          const message = (document.getElementById("help-message").value || "").trim();
          if (!name) throw new Error("Enter your name.");
          if (!email && !phone) throw new Error("Add your email or phone number so we can find your account.");
          if (email && !EMAIL_RE.test(email)) throw new Error("Enter a valid email address.");
          if (message.length < 8) throw new Error("Tell us what you need help with (at least a short sentence).");
          const res = await storeFetch("/api/store/auth/help", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ full_name: name, email, phone, message }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.error || "Could not send.");
          showToast("Sent to admin. They will set a new password for you.");
          renderLoggedOut("email");
          showError("");
          return;
        }
        if (tab === "register") {
          const name = (document.getElementById("auth-name").value || "").trim();
          const email = (document.getElementById("auth-email").value || "").trim();
          const phone = (document.getElementById("auth-phone").value || "").trim();
          const password = document.getElementById("auth-password").value || "";
          if (!name) throw new Error("Enter your full name.");
          if (!email) throw new Error("Enter your email.");
          if (!EMAIL_RE.test(email)) throw new Error("Enter a valid email address.");
          if (!phone) throw new Error("Enter your phone number.");
          if (password.length < 6) throw new Error("Password must be at least 6 characters.");
        } else if (tab === "phone") {
          const phone = (document.getElementById("auth-phone").value || "").trim();
          const password = document.getElementById("auth-password").value || "";
          if (!phone) throw new Error("Enter your phone number.");
          if (!password) throw new Error("Enter your password.");
        } else {
          const email = (document.getElementById("auth-email").value || "").trim();
          const password = document.getElementById("auth-password").value || "";
          if (!email) throw new Error("Enter your email.");
          if (!EMAIL_RE.test(email)) throw new Error("Enter a valid email address.");
          if (!password) throw new Error("Enter your password.");
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
        if (data.store_token) saveStoreToken(data.store_token);
        window.location.href = safeNext(nextUrl);
      } catch (e) {
        showError(e.message);
      }
    });
    mountGoogleButton();
  }

  function orderUrl(o) {
    return "store-order.html?order=" + encodeURIComponent(o.order_number) + "&token=" + encodeURIComponent(o.access_token || "");
  }

  async function renderLoggedIn(customer) {
    const [ordersRes, noticesRes] = await Promise.all([
      storeFetch("/api/store/account/orders"),
      storeFetch("/api/store/account/notices"),
    ]);
    const orderData = await ordersRes.json().catch(() => ({}));
    const noticeData = await noticesRes.json().catch(() => ({}));
    const orders = orderData.orders || [];
    const notices = noticeData.notices || [];
    document.getElementById("account-root").innerHTML = `
      <div class="card store-account-card" style="margin-bottom:16px;">
        <h2>Hello, ${escapeHtml(customer.full_name || "there")}</h2>
        <p class="text-muted">${escapeHtml(customer.email)}${customer.phone ? " · " + escapeHtml(customer.phone) : ""}${customer.google ? " · Google" : ""}</p>
        <div class="store-account-actions">
          <a class="btn btn-primary" href="${escapeHtml(safeNext(nextUrl === "store-account.html" ? "store.html" : nextUrl))}">Continue shopping</a>
          <button type="button" class="btn btn-secondary" id="sign-out-btn">Sign out</button>
        </div>
      </div>
      ${notices.length ? `
      <div class="card store-account-card" style="margin-bottom:16px;">
        <h3>Messages</h3>
        <p class="text-muted">If admin set a new password for you, it will show here.</p>
        ${notices.map((n) => `
          <div class="store-notice ${n.read ? "" : "is-unread"}">
            <strong>${escapeHtml(n.title || "Message")}</strong>
            <pre class="store-notice-body">${escapeHtml(n.body || "")}</pre>
          </div>`).join("")}
      </div>` : ""}
      ${!customer.phone ? `
      <div class="card store-account-card" style="margin-bottom:16px;">
        <h3>Add your phone number</h3>
        <p class="text-muted">Needed for delivery and WhatsApp help.</p>
        <form id="phone-form" novalidate>
          <div class="form-group"><label class="form-label">Phone number</label><input class="form-control" id="add-phone" inputmode="tel"></div>
          <button class="btn btn-primary btn-block" type="submit">Save phone</button>
        </form>
      </div>` : ""}
      ${customer.has_password ? `
      <div class="card store-account-card" style="margin-bottom:16px;">
        <h3>Change password</h3>
        <p class="text-muted">Enter the password you use now (including one admin gave you), then choose a new one.</p>
        <form id="password-form" novalidate>
          <div class="form-group"><label class="form-label">Current password</label><input class="form-control" id="pw-current" type="password" autocomplete="current-password"></div>
          <div class="form-group"><label class="form-label">New password</label><input class="form-control" id="pw-new" type="password" autocomplete="new-password"></div>
          <button class="btn btn-primary btn-block" type="submit">Save new password</button>
        </form>
      </div>` : `<p class="text-muted" style="margin-bottom:16px;">You sign in with Google. You do not need a password unless admin sets one for you.</p>`}
      <h3>Your orders</h3>
      ${orders.length ? orders.map((o) => `
        <a class="card store-order-link" href="${escapeHtml(orderUrl(o))}">
          <div><strong>${escapeHtml(o.product_summary || o.order_number)}</strong></div>
          <div class="text-muted">${escapeHtml(o.order_number)} · ${escapeHtml(o.order_status || "")} · ${money(o.total_cents, o.currency)}</div>
        </a>`).join("") : "<p class='text-muted'>No purchases yet. When you buy a product, it will show here.</p>"}
    `;
    document.getElementById("sign-out-btn").addEventListener("click", async () => {
      await storeFetch("/api/store/auth/logout", { method: "POST" });
      saveStoreToken("");
      window.location.href = "store-account.html";
    });
    if (notices.some((n) => !n.read)) {
      storeFetch("/api/store/account/notices/read-all", { method: "POST" }).catch(() => {});
    }
    const phoneForm = document.getElementById("phone-form");
    if (phoneForm) {
      phoneForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        showError("");
        try {
          const phone = (document.getElementById("add-phone").value || "").trim();
          if (!phone) throw new Error("Enter your phone number.");
          const res = await storeFetch("/api/store/account/phone", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.error || "Could not save phone.");
          showToast("Phone number saved.");
          await renderLoggedIn(data.customer || customer);
        } catch (e) {
          showError(e.message);
        }
      });
    }
    const pwForm = document.getElementById("password-form");
    if (pwForm) {
      pwForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        showError("");
        const current = document.getElementById("pw-current").value || "";
        const next = document.getElementById("pw-new").value || "";
        try {
          if (!current) throw new Error("Enter the password you use now.");
          if (next.length < 6) throw new Error("New password must be at least 6 characters.");
          const res = await storeFetch("/api/store/account/password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ current_password: current, new_password: next }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(data.error || "Could not change password.");
          document.getElementById("pw-current").value = "";
          document.getElementById("pw-new").value = "";
          showToast("Password updated. Use the new password next time you sign in.");
        } catch (e) {
          showError(e.message);
        }
      });
    }
  }

  (async function init() {
    try {
      const returning = await consumeGoogleReturn();
      if (returning) return;
      const customer = await me();
      if (customer) await renderLoggedIn(customer);
      else renderLoggedOut(getQueryParam("tab") || "email");
    } catch (e) {
      renderLoggedOut("email");
      if (e && e.message) showError(e.message);
    }
  })();
})();
