(function () {
  function togglePaidFields() {
    const paid = document.getElementById("new-community-type").value === "paid";
    document.getElementById("new-community-paid-fields").classList.toggle("hidden", !paid);
    document.getElementById("new-community-price").required = paid;
  }

  function communityPriceLabel(c) {
    if ((c.community_type || "free") !== "paid") return "Free";
    const amount = ((c.price_cents || 0) / 100).toFixed(2) + " " + (c.currency || "USD");
    if ((c.billing_interval || "one_time") === "month") return amount + " / month";
    return amount + " one-time";
  }

  async function load() {
    const data = await apiRequest("/api/communities");
    const list = document.getElementById("communities-list");
    const rows = data.communities || [];
    if (!rows.length) {
      list.innerHTML = `<div class="empty-state card"><p>No communities yet. Click <strong>+ Create Community</strong>.</p></div>`;
      return;
    }
    list.innerHTML = rows.map((c) => {
      const link = (c.community_token && typeof communityLinkForToken === "function")
        ? communityLinkForToken(c.community_token)
        : (c.community_link || "");
      return `
      <div class="card company-card">
        <a href="community-admin.html?id=${c.id}" style="color:inherit;text-decoration:none;">
          ${c.image_url ? `<img src="${escapeHtml(c.image_url)}" alt="" style="width:100%;height:140px;object-fit:cover;border-radius:12px;margin-bottom:10px;">` : ""}
          <h3>${escapeHtml(c.name)}</h3>
          <p class="text-muted">${escapeHtml((c.description || "").slice(0, 120))}</p>
          <p class="text-muted">${escapeHtml(communityPriceLabel(c))}</p>
        </a>
        <div class="flex gap-8" style="margin-top:12px;">
          <button type="button" class="btn btn-secondary btn-sm" data-copy-community="${escapeHtml(link)}">Copy link</button>
          <a class="btn btn-primary btn-sm" href="community-admin.html?id=${c.id}">Open</a>
        </div>
      </div>`;
    }).join("");
    list.querySelectorAll("[data-copy-community]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const url = btn.getAttribute("data-copy-community") || "";
        if (!url) {
          showToast("Community link is not ready yet");
          return;
        }
        copyToClipboard(url).then(() => showToast("Community link copied")).catch(() => {
          showToast("Could not copy. Open the community and copy from there.");
        });
      });
    });
  }

  document.getElementById("create-community-btn").addEventListener("click", () => {
    document.getElementById("create-community-form").reset();
    document.getElementById("create-community-error").classList.remove("visible");
    togglePaidFields();
    openModal("create-community-modal");
  });

  document.getElementById("new-community-type").addEventListener("change", togglePaidFields);

  document.getElementById("create-community-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("create-community-error");
    err.classList.remove("visible");
    const type = document.getElementById("new-community-type").value;
    const image = document.getElementById("new-community-image").files[0];
    if (!image) {
      err.textContent = "Add a community image.";
      err.classList.add("visible");
      return;
    }
    if (type === "paid") {
      const price = parseFloat(document.getElementById("new-community-price").value || "0");
      if (!(price > 0)) {
        err.textContent = "Enter a price for a paid community.";
        err.classList.add("visible");
        return;
      }
    }
    const fd = new FormData();
    fd.append("name", document.getElementById("new-community-name").value.trim());
    fd.append("description", document.getElementById("new-community-description").value.trim());
    fd.append("community_type", type);
    fd.append("currency", "USD");
    fd.append("billing_interval", type === "paid" ? document.getElementById("new-community-billing").value : "one_time");
    fd.append("price", type === "paid" ? document.getElementById("new-community-price").value.trim() : "0");
    fd.append("image", image);
    try {
      const res = await fetch(apiUrl("/api/communities"), {
        method: "POST",
        credentials: "include",
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || "Could not create community.");
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
