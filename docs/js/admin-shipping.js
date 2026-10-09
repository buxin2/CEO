(function () {
  async function load() {
    const data = await apiRequest("/api/admin/shipping");
    const zones = data.zones || [];
    document.getElementById("zone-list").innerHTML = zones.length ? `
      <table class="ui-table zones-table">
        <thead><tr><th>Zone</th><th>Countries</th><th>Price (USD)</th><th></th></tr></thead>
        <tbody>
          ${zones.map((z) => `
            <tr>
              <td><strong>${escapeHtml(z.name)}</strong><div class="text-muted">FedEx</div></td>
              <td>
                <button type="button" class="btn btn-ghost btn-sm" data-toggle-countries="${escapeHtml(z.slug)}">${(z.countries || []).length} countries</button>
                <div class="countries-cell collapsed" id="countries-${escapeHtml(z.slug)}" title="${escapeHtml((z.countries || []).map((c) => c.name).join(", "))}">${(z.countries || []).map((c) => escapeHtml(c.name)).join(", ")}</div>
              </td>
              <td><input class="form-control" style="max-width:120px;" id="rate-${escapeHtml(z.slug)}" value="${((z.rate_cents || 0) / 100).toFixed(2)}" aria-label="${escapeHtml(z.name)} price"></td>
              <td><button class="btn btn-secondary btn-sm" data-save="${escapeHtml(z.slug)}">Save</button></td>
            </tr>`).join("")}
        </tbody>
      </table>` : "<p class='text-muted'>No zones configured.</p>";

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
    document.querySelectorAll("[data-toggle-countries]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const el = document.getElementById("countries-" + btn.getAttribute("data-toggle-countries"));
        if (el) el.classList.toggle("collapsed");
      });
    });
  }

  load().catch((e) => showToast(e.message));
})();
