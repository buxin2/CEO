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
    document.getElementById("users-list").innerHTML = rows.length ? `<table class="ui-table"><thead><tr>
      <th>Name</th><th>Contact</th><th>Orders</th><th></th></tr></thead><tbody>
      ${rows.map((c) => `
      <tr>
        <td><strong>${escapeHtml(c.full_name || "Customer")}</strong></td>
        <td>${escapeHtml(c.email || "")}<div class="text-muted">${escapeHtml(c.phone || "")}${c.google ? " · Google" : ""}</div></td>
        <td>${c.order_count || 0}</td>
        <td>
          <button class="btn btn-secondary btn-sm" data-view="${c.id}">View</button>
          <button class="btn btn-secondary btn-sm" data-reset="${c.id}">Reset password</button>
          <button class="btn btn-danger btn-sm" data-delete="${c.id}">Delete</button>
        </td>
      </tr>`).join("")}
    </tbody></table>` : "<p class='text-muted'>No store users yet.</p>";
    document.querySelectorAll("[data-view]").forEach((btn) => {
      btn.addEventListener("click", () => openUser(parseInt(btn.dataset.view, 10)));
    });
    document.querySelectorAll("[data-delete]").forEach((btn) => {
      btn.addEventListener("click", () => deleteUser(parseInt(btn.dataset.delete, 10)));
    });
    document.querySelectorAll("[data-reset]").forEach((btn) => {
      btn.addEventListener("click", () => openUser(parseInt(btn.dataset.reset, 10)));
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
      <button class="btn btn-danger" id="delete-user" style="margin-top:20px;">Delete user</button>
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
    document.getElementById("delete-user").addEventListener("click", () => deleteUser(id, true));
    openModal("user-modal");
  }

  async function deleteUser(id, fromModal) {
    const c = customers.find((row) => row.id === id);
    const label = (c && (c.full_name || c.email)) || "this user";
    if (!confirm("Delete " + label + "? Their orders stay in Store Orders, unlinked. This cannot be undone.")) return;
    try {
      await apiRequest("/api/admin/store/customers/" + id, { method: "DELETE" });
      customers = customers.filter((row) => row.id !== id);
      if (fromModal) closeModal("user-modal");
      renderList();
      showToast("User deleted");
    } catch (e) {
      showToast(e.message);
    }
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
  document.getElementById("clear-users-btn").addEventListener("click", async () => {
    if (!confirm("Delete ALL store users? Orders stay in Store Orders. This cannot be undone.")) return;
    try {
      await apiRequest("/api/admin/store/customers/clear", { method: "POST" });
      closeModal("user-modal");
      showToast("All store users cleared");
      await load();
    } catch (e) {
      showToast(e.message);
    }
  });
  load().catch((e) => showToast(e.message));
})();
