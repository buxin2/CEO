(function () {
  let customers = [];
  const openId = parseInt(getQueryParam("id") || "", 10);

  function renderList() {
    const q = (document.getElementById("user-search").value || "").trim().toLowerCase();
    const rows = customers.filter((c) => {
      if (!q) return true;
      const hay = [c.full_name, c.email, c.phone].join(" ").toLowerCase();
      return hay.indexOf(q) >= 0;
    });
    document.getElementById("users-list").innerHTML = rows.map((c) => `
      <div class="card" style="padding:14px 16px;margin-bottom:10px;display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;">
        <div>
          <div><strong>${escapeHtml(c.full_name || "Customer")}</strong></div>
          <div class="text-muted">${escapeHtml(c.email || "")} · ${escapeHtml(c.phone || "")}${c.google ? " · Google" : ""}</div>
          <div class="text-muted">${c.order_count || 0} order(s)</div>
        </div>
        <button class="btn btn-secondary btn-sm" data-view="${c.id}">View</button>
      </div>
    `).join("") || "<p class='text-muted'>No store users yet.</p>";
    document.querySelectorAll("[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => openUser(parseInt(btn.dataset.view, 10)));
    });
  }

  async function openUser(id) {
    const data = await apiRequest("/api/admin/store/customers/" + id);
    const c = data.customer || {};
    const orders = data.orders || [];
    document.getElementById("user-modal-title").textContent = c.full_name || "User";
    document.getElementById("user-modal-body").innerHTML = `
      <p><strong>${escapeHtml(c.full_name || "")}</strong></p>
      <p>${escapeHtml(c.email || "")}</p>
      <p>${escapeHtml(c.phone || "")}</p>
      <p class="text-muted">Joined ${escapeHtml((c.created_at || "").slice(0, 10))} · ${c.order_count || 0} order(s)</p>
      <h4 style="margin-top:16px;">Set a new password</h4>
      <p class="text-muted">This password is saved to their account and shown in their account messages.</p>
      <input class="form-control" id="set-password" type="text" placeholder="New password (min 6 characters)" style="margin-bottom:8px;">
      <textarea class="form-control" id="set-password-note" rows="2" placeholder="Optional extra message"></textarea>
      <button class="btn btn-primary" id="save-password" style="margin-top:8px;">Save password &amp; notify</button>
      <h4 style="margin-top:20px;">Message this user</h4>
      <textarea class="form-control" id="user-message" rows="3" placeholder="They will see this after they sign in."></textarea>
      <button class="btn btn-secondary" id="send-message" style="margin-top:8px;">Send message</button>
      <h4 style="margin-top:20px;">Orders</h4>
      ${orders.length ? orders.map((o) => `
        <p>${escapeHtml(o.order_number || "")} · ${escapeHtml(o.product_summary || "")} · ${escapeHtml(o.order_status || "")}</p>
      `).join("") : "<p class='text-muted'>No orders yet.</p>"}
    `;
    document.getElementById("save-password").addEventListener("click", async () => {
      try {
        const password = (document.getElementById("set-password").value || "").trim();
        const message = document.getElementById("set-password-note").value || "";
        await apiRequest("/api/admin/store/customers/" + id + "/password", {
          method: "POST",
          body: JSON.stringify({ password, message }),
        });
        showToast("Password saved. They will see it in account messages.");
        document.getElementById("set-password").value = "";
      } catch (e) {
        showToast(e.message);
      }
    });
    document.getElementById("send-message").addEventListener("click", async () => {
      try {
        const body = document.getElementById("user-message").value || "";
        await apiRequest("/api/admin/store/customers/" + id + "/message", {
          method: "POST",
          body: JSON.stringify({ body }),
        });
        showToast("Message sent to their account.");
        document.getElementById("user-message").value = "";
      } catch (e) {
        showToast(e.message);
      }
    });
    openModal("user-modal");
  }

  async function load() {
    const data = await apiRequest("/api/admin/store/customers");
    customers = data.customers || [];
    renderList();
    if (openId) {
      const found = customers.find((c) => c.id === openId);
      if (found) openUser(openId).catch((e) => showToast(e.message));
    }
  }

  document.getElementById("user-search").addEventListener("input", renderList);
  load().catch((e) => showToast(e.message));
})();
