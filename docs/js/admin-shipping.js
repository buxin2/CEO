(function () {
  async function load() {
    const data = await apiRequest("/api/admin/shipping");
    const zones = data.zones || [];
    document.getElementById("zone-list").innerHTML = zones.map((z) => `
      <div class="card" style="padding:16px;margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start;">
          <div>
            <h3>${escapeHtml(z.name)}</h3>
            <p class="text-muted">FedEx · ${(z.countries || []).length} countries</p>
          </div>
          <div style="display:flex;gap:8px;align-items:center;">
            <span>USD</span>
            <input class="form-control" style="max-width:120px;" id="rate-${escapeHtml(z.slug)}" value="${((z.rate_cents || 0) / 100).toFixed(2)}">
            <button class="btn btn-secondary btn-sm" data-save="${escapeHtml(z.slug)}">Save price</button>
          </div>
        </div>
        <p style="margin-top:10px;font-size:13px;">${(z.countries || []).map((c) => escapeHtml(c.name)).join(", ")}</p>
      </div>
    `).join("") || "<p class='text-muted'>No zones configured.</p>";

    document.querySelectorAll("[data-save]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const slug = btn.dataset.save;
        await apiRequest("/api/admin/shipping/zones/" + encodeURIComponent(slug), {
          method: "PUT",
          body: JSON.stringify({ rate: document.getElementById("rate-" + slug).value }),
        });
        showToast("FedEx price saved");
        await load();
      });
    });
  }

  load().catch((e) => showToast(e.message));
})();
