(function () {
  const TOKEN = getQueryParam("token");
  let communityInfo = null;
  let pollTimer = null;

  function formatContent(text) {
    const escaped = escapeHtml(text || "");
    return escaped.replace(/(https?:\/\/[^\s<]+)/gi, (url) => {
      const clean = url.replace(/[.,;:!?)]+$/, "");
      return `<a href="${clean}" target="_blank" rel="noopener noreferrer">${clean}</a>`;
    }).replace(/\n/g, "<br>");
  }

  async function loadInfo() {
    communityInfo = await fetch(apiUrl(`/api/public/community/${TOKEN}`), { credentials: "include" }).then((r) => r.json());
    if (communityInfo.error) throw new Error(communityInfo.error);
    document.getElementById("community-name-label").textContent = communityInfo.name;
    document.getElementById("community-desc-label").textContent = communityInfo.description || "";
    const fields = communityInfo.registration_fields || [];
    document.getElementById("register-fields").innerHTML = fields
      .filter((f) => f.key !== "password")
      .map((f) => `
        <div class="form-group">
          <label class="form-label">${escapeHtml(f.label)}</label>
          <input class="form-control reg-field" data-key="${escapeHtml(f.key)}" type="${f.type === "email" ? "email" : "text"}">
        </div>`).join("") +
      `<div class="form-group"><label class="form-label">Password</label>
       <input class="form-control" id="reg-password" type="password"></div>`;
  }

  async function tryMemberSession() {
    try {
      const me = await fetch(apiUrl("/api/community-auth/me"), { credentials: "include" });
      if (!me.ok) return false;
      const data = await me.json();
      if (!data.authenticated) return false;
      const membership = await fetch(apiUrl(`/api/public/community/${TOKEN}/membership`), { credentials: "include" });
      if (!membership.ok) return false;
      const m = await membership.json();
      if (m.status !== "active") {
        showToast("Your membership is " + m.status);
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
    document.getElementById("feed-title").textContent = communityInfo.name.toUpperCase();
    document.getElementById("member-label").textContent = user.full_name || user.username;
    loadPosts();
    loadProducts();
    pollTimer = setInterval(loadPosts, 5000);
  }

  async function loadPosts() {
    const data = await fetch(apiUrl(`/api/public/community/${TOKEN}/posts`), { credentials: "include" }).then((r) => r.json());
    const list = document.getElementById("posts-list");
    list.innerHTML = (data.posts || []).map((p) => `
      <article class="chat-message" style="margin-bottom:10px;">
        <div class="chat-message-header">
          <span class="chat-sender">${escapeHtml(p.author_name)}</span>
          <span class="chat-role">${escapeHtml(p.author_role)}</span>
        </div>
        ${p.is_announcement ? '<span class="badge">Announcement</span> ' : ""}
        ${p.image_url ? `<div class="chat-image-wrap"><img src="${escapeHtml(p.image_url)}" class="chat-image" alt=""></div>` : ""}
        <div class="chat-message-body">${formatContent(p.content)}</div>
        <button class="btn btn-ghost btn-sm" onclick="likePost(${p.id})">👍 ${p.likes || 0}</button>
      </article>`).join("") || "<p class=\"text-muted\">No posts yet.</p>";
  }

  window.likePost = async (id) => {
    await fetch(apiUrl(`/api/public/community/${TOKEN}/posts/${id}/like`), {
      method: "POST",
      credentials: "include",
    });
    await loadPosts();
  };

  async function loadProducts() {
    const data = await fetch(apiUrl(`/api/public/community/${TOKEN}/products`), { credentials: "include" }).then((r) => r.json());
    document.getElementById("products-panel").innerHTML = (data.products || []).map((p) => `
      <div class="card card-inner" style="margin-bottom:8px;">
        <h4>${escapeHtml(p.name)}</h4>
        <p>${escapeHtml(p.description)}</p>
        <p><strong>${escapeHtml(p.price)} ${escapeHtml(p.currency)}</strong> · ${escapeHtml(p.product_type)}</p>
        ${p.purchase_url ? `<a class="btn btn-primary btn-sm" href="${escapeHtml(p.purchase_url)}" target="_blank" rel="noopener">Buy / Purchase</a>` : "<span class=\"text-muted\">Checkout not configured</span>"}
      </div>`).join("") || "<p class=\"text-muted\">No products yet.</p>";
  }

  document.getElementById("show-register-btn").addEventListener("click", () => {
    document.getElementById("login-form").classList.add("hidden");
    document.getElementById("register-form").classList.remove("hidden");
  });
  document.getElementById("show-login-btn").addEventListener("click", () => {
    document.getElementById("register-form").classList.add("hidden");
    document.getElementById("login-form").classList.remove("hidden");
  });

  document.getElementById("login-btn").addEventListener("click", async () => {
    const res = await fetch(apiUrl("/api/community-auth/login"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: document.getElementById("login-user").value.trim(),
        password: document.getElementById("login-pass").value,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Login failed");
      return;
    }
    await tryMemberSession();
  });

  document.getElementById("register-btn").addEventListener("click", async () => {
    const payload = { password: document.getElementById("reg-password").value };
    document.querySelectorAll(".reg-field").forEach((el) => {
      payload[el.dataset.key] = el.value.trim();
    });
    const res = await fetch(apiUrl(`/api/community-auth/register/${TOKEN}`), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Registration failed");
      return;
    }
    if (data.status === "pending") {
      showToast("Registered — waiting for admin approval");
      return;
    }
    await tryMemberSession();
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
      }
    } catch (e) {
      document.getElementById("community-name-label").textContent = "Invalid link";
    }
  })();
})();
