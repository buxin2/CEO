(function () {
  async function load() {
    const data = await apiRequest("/api/communities");
    const list = document.getElementById("communities-list");
    const rows = data.communities || [];
    if (!rows.length) {
      list.innerHTML = `<div class="empty-state card"><p>No communities yet. Click <strong>+ Create Community</strong>.</p></div>`;
      return;
    }
    list.innerHTML = rows.map((c) => `
      <a class="card company-card" href="community-admin.html?id=${c.id}">
        <h3>${escapeHtml(c.name)}</h3>
        <p class="text-muted">Open dashboard →</p>
      </a>`).join("");
  }

  document.getElementById("create-community-btn").addEventListener("click", () => {
    document.getElementById("create-community-form").reset();
    document.getElementById("create-community-error").classList.remove("visible");
    openModal("create-community-modal");
  });

  document.getElementById("create-community-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("create-community-error");
    err.classList.remove("visible");
    try {
      await apiRequest("/api/communities", {
        method: "POST",
        body: JSON.stringify({ name: document.getElementById("new-community-name").value.trim() }),
      });
      closeModal("create-community-modal");
      await load();
      showToast("Community created");
    } catch (ex) {
      err.textContent = ex.message;
      err.classList.add("visible");
    }
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await apiRequest("/api/auth/logout", { method: "POST" }); } catch (e) {}
    window.location.href = pageUrl("login.html");
  });

  if (typeof initMobileNav === "function") initMobileNav();

  (async function init() {
    try {
      if (typeof wakeApiServer === "function") await wakeApiServer();
      await apiRequest("/api/me");
    } catch (e) {
      window.location.href = pageUrl("login.html");
      return;
    }
    await load();
  })();
})();
