(function () {
  async function load() {
    const data = await apiRequest("/api/admin/shipping");
    document.getElementById("country-list").innerHTML = (data.countries || []).map((c) => `
      <div class="card" style="padding:16px;margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;">
          <div>
            <h3>${escapeHtml(c.country_name)} ${c.country_code ? "(" + escapeHtml(c.country_code) + ")" : ""}</h3>
            <p>${(c.rate_cents / 100).toFixed(2)} ${escapeHtml(c.currency)} · ${c.is_enabled ? "Enabled" : "Disabled"} ${c.free_shipping ? "· Free shipping" : ""}</p>
          </div>
          <div>
            <button class="btn btn-secondary btn-sm" data-toggle="${c.id}" data-on="${c.is_enabled ? "0" : "1"}">${c.is_enabled ? "Disable" : "Enable"}</button>
            <button class="btn btn-ghost btn-sm" data-del="${c.id}">Delete</button>
          </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
          <input class="form-control" style="max-width:140px;" id="rate-${c.id}" value="${(c.rate_cents / 100).toFixed(2)}">
          <button class="btn btn-secondary btn-sm" data-save-rate="${c.id}">Save rate</button>
        </div>
        <h4 style="margin-top:12px;">Regional rates</h4>
        ${(c.regions || []).map((r) => `
          <div style="display:flex;gap:8px;align-items:center;margin:4px 0;">
            <span>${escapeHtml(r.region_name)} — ${(r.rate_cents / 100).toFixed(2)}</span>
            <button class="btn btn-ghost btn-sm" data-del-region="${r.id}">Remove</button>
          </div>
        `).join("") || "<p class='text-muted'>No regional overrides. Country rate is used.</p>"}
        <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">
          <input class="form-control" id="reg-name-${c.id}" placeholder="Delhi" style="max-width:160px;">
          <input class="form-control" id="reg-rate-${c.id}" placeholder="7" style="max-width:100px;">
          <button class="btn btn-secondary btn-sm" data-add-region="${c.id}">Add region</button>
        </div>
      </div>
    `).join("") || "<p class='text-muted'>No countries yet. Add India, The Gambia, etc.</p>";

    document.querySelectorAll("[data-toggle]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest("/api/admin/shipping/countries/" + btn.dataset.toggle, {
          method: "PUT",
          body: JSON.stringify({ is_enabled: btn.dataset.on === "1" }),
        });
        await load();
      });
    });
    document.querySelectorAll("[data-del]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this country?")) return;
        await apiRequest("/api/admin/shipping/countries/" + btn.dataset.del, { method: "DELETE" });
        await load();
      });
    });
    document.querySelectorAll("[data-save-rate]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest("/api/admin/shipping/countries/" + btn.dataset.saveRate, {
          method: "PUT",
          body: JSON.stringify({ rate: document.getElementById("rate-" + btn.dataset.saveRate).value }),
        });
        showToast("Rate saved");
        await load();
      });
    });
    document.querySelectorAll("[data-add-region]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest("/api/admin/shipping/countries/" + btn.dataset.addRegion + "/regions", {
          method: "POST",
          body: JSON.stringify({
            region_name: document.getElementById("reg-name-" + btn.dataset.addRegion).value,
            rate: document.getElementById("reg-rate-" + btn.dataset.addRegion).value,
          }),
        });
        await load();
      });
    });
    document.querySelectorAll("[data-del-region]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest("/api/admin/shipping/regions/" + btn.dataset.delRegion, { method: "DELETE" });
        await load();
      });
    });
  }

  document.getElementById("add-country").addEventListener("click", async () => {
    await apiRequest("/api/admin/shipping/countries", {
      method: "POST",
      body: JSON.stringify({
        country_name: document.getElementById("c-name").value,
        country_code: document.getElementById("c-code").value,
        rate: document.getElementById("c-rate").value,
        currency: document.getElementById("c-cur").value,
        is_enabled: document.getElementById("c-enabled").checked,
        free_shipping: document.getElementById("c-free").checked,
        free_shipping_min: document.getElementById("c-free-min").value || null,
      }),
    });
    document.getElementById("c-name").value = "";
    await load();
  });

  load().catch((e) => showToast(e.message));
})();
