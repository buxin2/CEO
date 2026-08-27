(function () {
  const TOKEN = getQueryParam("token");
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  let communityInfo = null;
  let pollTimer = null;
  let googleClientId = "";

  function showError(msg) {
    const el = document.getElementById("account-error");
    if (!el) return;
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
  }

  function checkoutUrl(params) {
    const q = new URLSearchParams(params || {});
    q.set("token", TOKEN);
    return pageUrl("checkout.html?" + q.toString());
  }

  function storeAccountGoogleHref() {
    return "store-account.html?next=" + encodeURIComponent("community.html?token=" + TOKEN);
  }

  function isPhoneBrowser() {
    const ua = navigator.userAgent || "";
    return /Android|iPhone|iPad|iPod|Mobile|webOS|BlackBerry|IEMobile|Opera Mini/i.test(ua)
      || ((navigator.maxTouchPoints || 0) > 1 && Math.min(window.innerWidth, window.innerHeight) < 900);
  }

  function formatContent(text) {
    const escaped = escapeHtml(text || "");
    return escaped.replace(/(https?:\/\/[^\s<]+)/gi, (url) => {
      const clean = url.replace(/[.,;:!?)]+$/, "");
      return `<a href="${clean}" target="_blank" rel="noopener noreferrer">${clean}</a>`;
    }).replace(/\n/g, "<br>");
  }

  async function joinCommunity() {
    const res = await storeFetch("/api/public/community/" + encodeURIComponent(TOKEN) + "/join", { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Could not join this community.");
    return data;
  }

  async function enterAfterAuth(joinData) {
    if (joinData.needs_payment) {
      window.location.href = checkoutUrl({ membership_id: joinData.membership_id });
      return true;
    }
    await tryMemberSession();
    return true;
  }

  async function loadInfo() {
    communityInfo = await fetch(apiUrl(`/api/public/community/${TOKEN}`), { credentials: "include" }).then((r) => r.json());
    if (communityInfo.error) throw new Error(communityInfo.error);
    document.getElementById("community-name-label").textContent = communityInfo.name;
    document.getElementById("community-desc-label").textContent = communityInfo.description || "";
    const cover = document.getElementById("community-cover");
    if (communityInfo.image_url) {
      cover.src = communityInfo.image_url;
      cover.classList.remove("hidden");
    }
    const priceEl = document.getElementById("community-price-label");
    if ((communityInfo.community_type || "free") === "paid") {
      const price = ((communityInfo.price_cents || 0) / 100).toFixed(2) + " " + (communityInfo.currency || "USD");
      const bill = (communityInfo.billing_interval || "one_time") === "month" ? " monthly" : " one-time";
      priceEl.textContent = "Paid community · " + price + bill;
    } else {
      priceEl.textContent = "Free community";
    }
  }

  async function tryMemberSession() {
    try {
      const meStore = await storeFetch("/api/store/auth/me");
      if (meStore.ok) {
        const joinData = await joinCommunity();
        if (joinData.needs_payment) {
          window.location.href = checkoutUrl({ membership_id: joinData.membership_id });
          return false;
        }
      }
      const me = await fetch(apiUrl("/api/community-auth/me"), { credentials: "include" });
      if (!me.ok) return false;
      const data = await me.json();
      if (!data.authenticated) return false;
      const membership = await fetch(apiUrl(`/api/public/community/${TOKEN}/membership`), { credentials: "include" });
      if (!membership.ok) return false;
      const m = await membership.json();
      if (m.status === "pending_payment") {
        const banner = document.getElementById("renew-banner");
        banner.classList.remove("hidden");
        banner.innerHTML = `Your membership needs payment. <a href="${escapeHtml(checkoutUrl({ membership_id: m.id }))}">Pay to join</a>`;
        document.getElementById("auth-screen").classList.add("hidden");
        document.getElementById("feed-screen").classList.remove("hidden");
        document.getElementById("feed-title").textContent = (communityInfo.name || "Community").toUpperCase();
        document.getElementById("member-label").textContent = (data.user && (data.user.full_name || data.user.username)) || "";
        document.getElementById("feed-panel").classList.add("hidden");
        return true;
      }
      if (m.status !== "active") {
        showError("Your membership is " + m.status);
        return false;
      }
      showFeed(data.user, m);
      return true;
    } catch (e) {
      return false;
    }
  }

  function showFeed(user, membership) {
    document.getElementById("auth-screen").classList.add("hidden");
    document.getElementById("feed-screen").classList.remove("hidden");
    document.getElementById("feed-panel").classList.remove("hidden");
    document.getElementById("renew-banner").classList.add("hidden");
    document.getElementById("feed-title").textContent = communityInfo.name.toUpperCase();
    document.getElementById("member-label").textContent = user.full_name || user.username;
    loadPosts();
    loadProducts();
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(loadPosts, 8000);
  }

  async function loadPosts() {
    const res = await fetch(apiUrl(`/api/public/community/${TOKEN}/posts`), { credentials: "include" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return;
    document.getElementById("posts-list").innerHTML = (data.posts || []).map((p) => `
      <div class="chat-message">
        <div><strong>${escapeHtml(p.author_name || "")}</strong> <span class="text-muted">${escapeHtml(p.author_role || "")}</span></div>
        ${p.image_url ? `<div class="chat-image-wrap"><img src="${escapeHtml(p.image_url)}" class="chat-image" alt=""></div>` : ""}
        <div>${formatContent(p.content)}</div>
      </div>
    `).join("") || "<p class='text-muted'>No posts yet.</p>";
  }

  async function loadProducts() {
    const data = await fetch(apiUrl(`/api/public/community/${TOKEN}/products`), { credentials: "include" }).then((r) => r.json());
    document.getElementById("products-panel").innerHTML = (data.products || []).map((p) => `
      <div class="card card-inner" style="margin-bottom:8px;">
        ${p.image_url ? `<img src="${escapeHtml(p.image_url)}" alt="" style="max-width:120px;border-radius:8px;">` : ""}
        <strong>${escapeHtml(p.name)}</strong>
        <p class="text-muted">${escapeHtml(p.price || "")} ${escapeHtml(p.currency || "")}</p>
      </div>
    `).join("") || "<p class='text-muted'>No products yet.</p>";
  }

  async function mountGoogleButton() {
    const box = document.getElementById("google-signin-btn");
    if (!box) return;
    try {
      const res = await storeFetch("/api/store/auth/google-config");
      const data = await res.json().catch(() => ({}));
      googleClientId = data.client_id || "";
      if (!googleClientId) {
        const wrap = box.closest(".google-signin-wrap");
        const orEl = document.querySelector(".auth-or");
        if (wrap) wrap.remove();
        if (orEl) orEl.remove();
        return;
      }
      if (isPhoneBrowser()) {
        box.innerHTML = `<a class="google-continue-btn" href="${escapeHtml(storeAccountGoogleHref())}">Continue with Google</a>`;
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
          showError("");
          try {
            const res = await storeFetch("/api/store/auth/google", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ credential: response.credential }),
            });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(body.error || "Google sign-in failed.");
            if (body.store_token) saveStoreToken(body.store_token);
            await enterAfterAuth(await joinCommunity());
          } catch (e) {
            showError(e.message);
          }
        },
      });
      window.google.accounts.id.renderButton(box, { theme: "outline", size: "large", width: 320 });
    } catch (e) {}
  }

  document.getElementById("show-register-btn").addEventListener("click", () => {
    document.getElementById("login-form").classList.add("hidden");
    document.getElementById("register-form").classList.remove("hidden");
    showError("");
  });
  document.getElementById("show-login-btn").addEventListener("click", () => {
    document.getElementById("register-form").classList.add("hidden");
    document.getElementById("login-form").classList.remove("hidden");
    showError("");
  });

  document.getElementById("login-btn").addEventListener("click", async () => {
    showError("");
    try {
      const email = (document.getElementById("login-email").value || "").trim();
      const password = document.getElementById("login-pass").value || "";
      if (!email || !EMAIL_RE.test(email)) throw new Error("Enter a valid email.");
      if (!password) throw new Error("Enter your password.");
      const res = await storeFetch("/api/store/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Sign in failed.");
      if (data.store_token) saveStoreToken(data.store_token);
      await enterAfterAuth(await joinCommunity());
    } catch (e) {
      showError(e.message);
    }
  });

  document.getElementById("register-btn").addEventListener("click", async () => {
    showError("");
    try {
      const full_name = (document.getElementById("reg-name").value || "").trim();
      const email = (document.getElementById("reg-email").value || "").trim();
      const phone = (document.getElementById("reg-phone").value || "").trim();
      const password = document.getElementById("reg-password").value || "";
      if (!full_name) throw new Error("Enter your full name.");
      if (!email || !EMAIL_RE.test(email)) throw new Error("Enter a valid email.");
      if (!phone) throw new Error("Enter your phone number.");
      if (password.length < 6) throw new Error("Password must be at least 6 characters.");
      const res = await storeFetch("/api/store/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name, email, phone, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Could not create account.");
      if (data.store_token) saveStoreToken(data.store_token);
      await enterAfterAuth(await joinCommunity());
    } catch (e) {
      showError(e.message);
    }
  });

  document.getElementById("post-btn").addEventListener("click", async () => {
    const content = document.getElementById("post-input").value.trim();
    if (!content) return;
    await fetch(apiUrl(`/api/public/community/${TOKEN}/posts`), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    document.getElementById("post-input").value = "";
    await loadPosts();
  });

  document.getElementById("tab-feed-btn").addEventListener("click", () => {
    document.getElementById("feed-panel").classList.remove("hidden");
    document.getElementById("products-panel").classList.add("hidden");
  });
  document.getElementById("tab-products-btn").addEventListener("click", () => {
    document.getElementById("feed-panel").classList.add("hidden");
    document.getElementById("products-panel").classList.remove("hidden");
  });

  document.getElementById("logout-member-btn").addEventListener("click", async () => {
    await fetch(apiUrl("/api/community-auth/logout"), { method: "POST", credentials: "include" });
    await storeFetch("/api/store/auth/logout", { method: "POST" }).catch(() => {});
    saveStoreToken("");
    if (pollTimer) clearInterval(pollTimer);
    document.getElementById("feed-screen").classList.add("hidden");
    document.getElementById("auth-screen").classList.remove("hidden");
  });

  (async function init() {
    if (!TOKEN) return;
    try {
      await loadInfo();
      const ok = await tryMemberSession();
      if (!ok) {
        document.getElementById("auth-screen").classList.remove("hidden");
        await mountGoogleButton();
      }
    } catch (e) {
      showError(e.message);
    }
  })();
})();
