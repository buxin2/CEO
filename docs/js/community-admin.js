(function () {
  const communityId = getQueryParam("id");
  let dash = null;

  function togglePaidFields() {
    const paid = document.getElementById("settings-community-type").value === "paid";
    const box = document.getElementById("settings-paid-fields");
    if (box) box.classList.toggle("hidden", !paid);
  }

  function showTab(name) {
    document.querySelectorAll(".community-tab").forEach((el) => el.classList.add("hidden"));
    document.getElementById("tab-" + name).classList.remove("hidden");
    document.querySelectorAll(".community-admin-tabs button").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === name);
    });
  }

  async function loadDashboard() {
    dash = await apiRequest(`/api/communities/${communityId}`);
    const c = dash.community;
    const s = dash.stats;
    document.getElementById("community-title").textContent = c.name;
    document.getElementById("community-stats").textContent =
      `${s.total_members} members · ${s.active_members} active · ${s.posts} posts · ${s.products} products`;
    document.getElementById("tab-overview").innerHTML = `
      <h3 class="section-subtitle">Overview</h3>
      <p><strong>Members:</strong> ${s.total_members} (${s.active_members} active, ${s.pending_members} pending)</p>
      <p><strong>Posts:</strong> ${s.posts} · <strong>Comments:</strong> ${s.comments}</p>
      <p><strong>New members this week:</strong> ${s.new_members_week}</p>
      <p><strong>Products:</strong> ${s.products}</p>
      <p class="text-muted">Link: ${escapeHtml(dash.community_link)}</p>`;
    document.getElementById("settings-name").value = c.name;
    document.getElementById("settings-description").value = c.description || "";
    document.getElementById("settings-members-visible").checked = c.members_visible;
    document.getElementById("settings-community-type").value = c.community_type || "free";
    document.getElementById("settings-price").value = ((c.price_cents || 0) / 100).toFixed(2);
    document.getElementById("settings-billing").value = (c.billing_interval === "year" ? "month" : (c.billing_interval || "one_time"));
    const preview = document.getElementById("settings-image-preview");
    preview.innerHTML = c.image_url
      ? `<img src="${escapeHtml(c.image_url)}" alt="" style="max-width:180px;border-radius:12px;">`
      : "";
    togglePaidFields();
  }

  async function loadMembers() {
    const q = document.getElementById("member-search").value.trim();
    const url = `/api/communities/${communityId}/members` + (q ? `?search=${encodeURIComponent(q)}` : "");
    const data = await apiRequest(url);
    document.getElementById("members-admin-list").innerHTML = (data.members || []).map((m) => `
      <div class="member-row card-inner">
        <div><strong>${escapeHtml(m.full_name || m.username)}</strong> · ${escapeHtml(m.email)} · ${escapeHtml(m.status)}</div>
        <div class="flex gap-8">
          ${m.status === "pending" ? `<button class="btn btn-primary btn-sm" onclick="memberAction(${m.id},'approve')">Approve</button>` : ""}
          ${m.status === "active" ? `<button class="btn btn-secondary btn-sm" onclick="memberAction(${m.id},'suspend')">Suspend</button>` : ""}
          ${m.status === "suspended" ? `<button class="btn btn-primary btn-sm" onclick="memberAction(${m.id},'restore')">Restore</button>` : ""}
          <button class="btn btn-danger btn-sm" onclick="memberAction(${m.id},'remove')">Remove</button>
        </div>
      </div>`).join("") || "<p class=\"text-muted\">No members.</p>";
  }

  window.memberAction = async (id, action) => {
    if (action === "remove" && !confirm("Remove this member?")) return;
    await apiRequest(`/api/communities/${communityId}/members/${id}`, {
      method: "PUT",
      body: JSON.stringify({ action }),
    });
    await loadMembers();
    await loadDashboard();
  };

  async function loadPosts() {
    const data = await apiRequest(`/api/communities/${communityId}/posts`);
    document.getElementById("admin-posts-list").innerHTML = (data.posts || []).map((p) => `
      <div class="chat-message card-inner" style="margin-bottom:8px;">
        <div><strong>${escapeHtml(p.author_name)}</strong> <span class="text-muted">${escapeHtml(p.author_role)}</span></div>
        ${p.image_url ? `<img src="${escapeHtml(p.image_url)}" class="chat-image" alt="">` : ""}
        <div>${escapeHtml(p.content)}</div>
        <button class="btn btn-ghost btn-sm" onclick="deletePost(${p.id})">Delete</button>
      </div>`).join("") || "<p class=\"text-muted\">No posts yet.</p>";
  }

  window.deletePost = async (id) => {
    if (!confirm("Delete post?")) return;
    await apiRequest(`/api/communities/${communityId}/posts/${id}`, { method: "DELETE" });
    await loadPosts();
  };

  async function loadProducts() {
    const data = await apiRequest(`/api/communities/${communityId}/products`);
    document.getElementById("products-admin-list").innerHTML = (data.products || []).map((p) => `
      <div class="card-inner member-row">
        <div><strong>${escapeHtml(p.name)}</strong> · ${escapeHtml(p.price)} ${escapeHtml(p.currency)} · Qty ${p.quantity_available || 0} · ${escapeHtml(p.product_type)} · ${escapeHtml(p.status)}</div>
        <button class="btn btn-danger btn-sm" onclick="deleteProduct(${p.id})">Delete</button>
      </div>`).join("") || "<p class=\"text-muted\">No products.</p>";
  }

  window.deleteProduct = async (id) => {
    if (!confirm("Delete product?")) return;
    await apiRequest(`/api/communities/${communityId}/products/${id}`, { method: "DELETE" });
    await loadProducts();
  };

  async function loadScheduled() {
    const data = await apiRequest(`/api/communities/${communityId}/scheduled-messages`);
    document.getElementById("scheduled-list").innerHTML = (data.messages || []).map((m) => `
      <div class="card-inner"><strong>${escapeHtml(m.title || "Scheduled")}</strong> · ${escapeHtml(m.schedule_kind)} ${escapeHtml(m.schedule_time)}
      <p>${escapeHtml(m.message)}</p>
      <span class="text-muted">${m.is_active ? "Active" : "Paused"}</span>
      <button class="btn btn-danger btn-sm" onclick="deleteScheduled(${m.id})">Delete</button></div>`).join("") || "<p class=\"text-muted\">No scheduled messages.</p>";
  };

  window.deleteScheduled = async (id) => {
    if (!confirm("Delete scheduled message?")) return;
    await apiRequest(`/api/communities/${communityId}/scheduled-messages/${id}`, { method: "DELETE" });
    await loadScheduled();
  };

  document.querySelectorAll(".community-admin-tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      showTab(btn.dataset.tab);
      if (btn.dataset.tab === "members") loadMembers();
      if (btn.dataset.tab === "posts") loadPosts();
      if (btn.dataset.tab === "products") loadProducts();
      if (btn.dataset.tab === "scheduled") loadScheduled();
    });
  });

  document.getElementById("copy-link-btn").addEventListener("click", () => {
    if (!dash) return;
    navigator.clipboard.writeText(dash.community_link).then(() => showToast("Link copied"));
  });

  document.getElementById("open-community-btn").addEventListener("click", () => {
    if (!dash) return;
    window.open(dash.community_link, "_blank");
  });

  document.getElementById("admin-post-btn").addEventListener("click", async () => {
    const content = document.getElementById("admin-post-input").value.trim();
    if (!content) return;
    await apiRequest(`/api/communities/${communityId}/posts`, {
      method: "POST",
      body: JSON.stringify({ content, is_announcement: true }),
    });
    document.getElementById("admin-post-input").value = "";
    await loadPosts();
  });

  document.getElementById("admin-post-image-btn").addEventListener("click", () => {
    document.getElementById("admin-post-image-input").click();
  });

  document.getElementById("admin-post-image-input").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("image", file);
    fd.append("content", document.getElementById("admin-post-input").value.trim());
    fd.append("is_announcement", "1");
    const res = await fetch(apiUrl(`/api/communities/${communityId}/posts/image`), {
      method: "POST",
      credentials: "include",
      body: fd,
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      showToast(d.error || "Upload failed");
      return;
    }
    document.getElementById("admin-post-input").value = "";
    e.target.value = "";
    await loadPosts();
  });

  document.getElementById("settings-community-type").addEventListener("change", togglePaidFields);

  document.getElementById("community-settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const type = document.getElementById("settings-community-type").value;
    await apiRequest(`/api/communities/${communityId}`, {
      method: "PUT",
      body: JSON.stringify({
        name: document.getElementById("settings-name").value.trim(),
        description: document.getElementById("settings-description").value.trim(),
        members_visible: document.getElementById("settings-members-visible").checked,
        community_type: type,
        price: type === "paid" ? document.getElementById("settings-price").value.trim() : "0",
        currency: "USD",
        billing_interval: type === "paid" ? document.getElementById("settings-billing").value : "one_time",
      }),
    });
    const file = document.getElementById("settings-image").files[0];
    if (file) {
      const fd = new FormData();
      fd.append("image", file);
      const res = await fetch(apiUrl(`/api/communities/${communityId}/image`), {
        method: "POST",
        credentials: "include",
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showToast(data.error || "Could not upload image");
        return;
      }
      document.getElementById("settings-image").value = "";
    }
    showToast("Settings saved");
    await loadDashboard();
  });

  document.getElementById("add-product-btn").addEventListener("click", async () => {
    const name = prompt("Product name");
    if (!name) return;
    const price = prompt("Price (e.g. 49.99)") || "";
    const quantity = parseInt(prompt("Quantity / inventory", "100") || "0", 10);
    const product_type = prompt("Type: physical or digital", "physical") || "physical";
    await apiRequest(`/api/communities/${communityId}/products`, {
      method: "POST",
      body: JSON.stringify({ name, price, quantity_available: quantity, product_type }),
    });
    await loadProducts();
  });

  document.getElementById("add-scheduled-btn").addEventListener("click", async () => {
    const message = prompt("Message to send");
    if (!message) return;
    const schedule_kind = prompt("Schedule: once, daily, or weekly", "daily") || "daily";
    const schedule_time = prompt("Time HH:MM", "09:00") || "09:00";
    await apiRequest(`/api/communities/${communityId}/scheduled-messages`, {
      method: "POST",
      body: JSON.stringify({ message, schedule_kind, schedule_time, is_announcement: true }),
    });
    await loadScheduled();
  });

  document.getElementById("member-search").addEventListener("input", () => loadMembers());

  document.getElementById("delete-community-btn").addEventListener("click", async () => {
    if (!confirm("Delete this community? This cannot be undone.")) return;
    await apiRequest(`/api/communities/${communityId}`, { method: "DELETE" });
    window.location.href = pageUrl("communities.html");
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await apiRequest("/api/auth/logout", { method: "POST" }); } catch (e) {}
    window.location.href = pageUrl("login.html");
  });

  if (typeof initMobileNav === "function") initMobileNav();

  (async function init() {
    if (!communityId) {
      window.location.href = pageUrl("communities.html");
      return;
    }
    try {
      if (typeof wakeApiServer === "function") await wakeApiServer();
      await apiRequest("/api/me");
    } catch (e) {
      window.location.href = pageUrl("login.html");
      return;
    }
    await loadDashboard();
    showTab("overview");
  })();
})();
