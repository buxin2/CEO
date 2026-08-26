(function () {
  let storeUrl = "";
  let categories = [];
  let editingId = null;

  function centsInput(el) {
    const v = el.value.trim();
    if (!v) return null;
    return v;
  }

  async function load() {
    const [prod, settings, cats] = await Promise.all([
      apiRequest("/api/admin/store/products"),
      apiRequest("/api/admin/store/settings"),
      apiRequest("/api/admin/store/categories"),
    ]);
    storeUrl = prod.store_url || settings.store_url || "";
    categories = cats.categories || [];
    document.getElementById("set-name").value = settings.store_name || "";
    document.getElementById("set-tagline").value = settings.tagline || "";
    document.getElementById("set-currency").value = settings.currency || "USD";
    document.getElementById("set-free-min").value = settings.free_shipping_min_cents || "";
    const a = prod.analytics || {};
    document.getElementById("store-stats").innerHTML = `
      <div class="summary-card"><div class="label">Total products</div><div class="value">${a.total_products || 0}</div></div>
      <div class="summary-card"><div class="label">Total orders</div><div class="value">${a.total_orders || 0}</div></div>
      <div class="summary-card"><div class="label">Paid sales</div><div class="value">${a.total_sales || 0}</div></div>
      <div class="summary-card"><div class="label">Revenue</div><div class="value">${((a.total_revenue_cents || 0) / 100).toFixed(2)}</div></div>
    `;
    document.getElementById("cat-list").innerHTML = categories.map((c) => `
      <span class="store-chip">${escapeHtml(c.name)}
        <button class="btn btn-ghost btn-sm" data-del-cat="${c.id}">×</button>
      </span>
    `).join("") || "<p class='text-muted'>No categories yet.</p>";
    document.querySelectorAll("[data-del-cat]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest("/api/admin/store/categories/" + btn.dataset.delCat, { method: "DELETE" });
        await load();
      });
    });
    const catSel = document.getElementById("p-category");
    catSel.innerHTML = `<option value="">None</option>` + categories.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");

    document.getElementById("product-list").innerHTML = (prod.products || []).map((p) => {
      const an = p.analytics || {};
      return `
      <div class="card" style="padding:16px;margin-bottom:12px;">
        <div style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap;">
          ${p.cover_image ? `<img src="${escapeHtml(p.cover_image)}" alt="" style="width:72px;height:72px;object-fit:cover;border-radius:8px;">` : ""}
          <div style="flex:1;">
            <h3>${escapeHtml(p.title)}</h3>
            <div class="text-muted">${escapeHtml(p.status)} · ${(p.unit_price_cents / 100).toFixed(2)} ${escapeHtml(p.currency)} · ${escapeHtml(p.availability)}</div>
            <div class="text-muted" style="font-size:13px;">Views ${an.views || 0} · Orders ${an.total_orders || 0} · Sold ${an.units_sold || 0} · Left ${an.units_remaining == null ? "∞" : an.units_remaining} · Revenue ${((an.revenue_cents || 0) / 100).toFixed(2)} · Pending ${an.pending_orders || 0}</div>
          </div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="btn btn-secondary btn-sm" data-copy="${escapeHtml(p.product_url)}">Copy Product Link</button>
            <button class="btn btn-secondary btn-sm" data-edit="${p.id}">Edit</button>
            <button class="btn btn-ghost btn-sm" data-del="${p.id}">Delete</button>
          </div>
        </div>
      </div>`;
    }).join("") || "<p class='text-muted'>No products yet. Click Add Product.</p>";

    document.querySelectorAll("[data-copy]").forEach((btn) => {
      btn.addEventListener("click", () => copyToClipboard(btn.dataset.copy).then(() => showToast("Product link copied")));
    });
    document.querySelectorAll("[data-edit]").forEach((btn) => {
      btn.addEventListener("click", () => openEdit(Number(btn.dataset.edit)));
    });
    document.querySelectorAll("[data-del]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this product?")) return;
        await apiRequest("/api/admin/store/products/" + btn.dataset.del, { method: "DELETE" });
        await load();
      });
    });
  }

  function openCreate() {
    editingId = null;
    document.getElementById("product-form").reset();
    document.getElementById("p-id").value = "";
    document.getElementById("p-images").innerHTML = "";
    document.getElementById("p-videos").innerHTML = "";
    document.getElementById("p-ship").checked = true;
    document.getElementById("product-modal-title").textContent = "Add product";
    openModal("product-modal");
  }

  async function openEdit(id) {
    const p = await apiRequest("/api/admin/store/products/" + id);
    editingId = id;
    document.getElementById("p-id").value = id;
    document.getElementById("p-title").value = p.title || "";
    document.getElementById("p-sku").value = p.sku || "";
    document.getElementById("p-category").value = p.category_id || "";
    document.getElementById("p-status").value = p.status || "draft";
    document.getElementById("p-type").value = p.product_type || "physical";
    document.getElementById("p-currency").value = p.currency || "USD";
    document.getElementById("p-price").value = ((p.price_cents || 0) / 100).toFixed(2);
    document.getElementById("p-sale").value = p.sale_price_cents != null ? (p.sale_price_cents / 100).toFixed(2) : "";
    document.getElementById("p-qty").value = p.quantity_available == null ? "" : p.quantity_available;
    document.getElementById("p-keywords").value = p.keywords || "";
    document.getElementById("p-short").value = p.short_description || "";
    document.getElementById("p-desc").value = p.description || "";
    document.getElementById("p-specs").value = p.specifications || "";
    document.getElementById("p-ship").checked = !!p.shipping_required;
    document.getElementById("p-free-ship").checked = !!p.free_shipping;
    document.getElementById("p-dig-url").value = p.digital_delivery_url || "";
    document.getElementById("p-dig-text").value = p.digital_delivery_text || "";
    document.getElementById("p-options").value = JSON.stringify(p.options || [], null, 2);
    document.getElementById("p-related").value = (p.related_ids || []).join(",");
    renderMedia(p);
    document.getElementById("product-modal-title").textContent = "Edit product";
    openModal("product-modal");
  }

  function renderMedia(p) {
    document.getElementById("p-images").innerHTML = (p.images || []).map((i) => `
      <div><img src="${escapeHtml(i.url)}" alt=""><button type="button" class="btn btn-ghost btn-sm" data-del-img="${i.id}">Remove</button></div>
    `).join("");
    document.getElementById("p-videos").innerHTML = (p.videos || []).map((v) => `
      <div class="text-muted">${escapeHtml(v.video_type)} · ${escapeHtml(v.url)} <button type="button" class="btn btn-ghost btn-sm" data-del-vid="${v.id}">Remove</button></div>
    `).join("");
    document.querySelectorAll("[data-del-img]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest("/api/admin/store/images/" + btn.dataset.delImg, { method: "DELETE" });
        const p2 = await apiRequest("/api/admin/store/products/" + editingId);
        renderMedia(p2);
      });
    });
    document.querySelectorAll("[data-del-vid]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest("/api/admin/store/videos/" + btn.dataset.delVid, { method: "DELETE" });
        const p2 = await apiRequest("/api/admin/store/products/" + editingId);
        renderMedia(p2);
      });
    });
  }

  function parseOptions() {
    const raw = document.getElementById("p-options").value.trim();
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return parsed.map((o) => ({
      name: o.name,
      values: (o.values || []).map((v) => (typeof v === "string" ? { label: v } : v)),
    }));
  }

  document.getElementById("add-product-btn").addEventListener("click", openCreate);
  document.getElementById("copy-store-link").addEventListener("click", () => {
    copyToClipboard(storeUrl).then(() => showToast("Store link copied"));
  });
  document.getElementById("save-settings").addEventListener("click", async () => {
    await apiRequest("/api/admin/store/settings", {
      method: "PUT",
      body: JSON.stringify({
        store_name: document.getElementById("set-name").value,
        tagline: document.getElementById("set-tagline").value,
        currency: document.getElementById("set-currency").value,
        free_shipping_min_cents: document.getElementById("set-free-min").value || null,
      }),
    });
    showToast("Store settings saved");
    await load();
  });
  document.getElementById("add-cat").addEventListener("click", async () => {
    const name = document.getElementById("new-cat").value.trim();
    if (!name) return;
    await apiRequest("/api/admin/store/categories", { method: "POST", body: JSON.stringify({ name }) });
    document.getElementById("new-cat").value = "";
    await load();
  });

  document.getElementById("product-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const err = document.getElementById("product-form-error");
    err.textContent = "";
    let options = [];
    try {
      options = parseOptions();
    } catch (e) {
      err.textContent = "Variations JSON is invalid.";
      return;
    }
    const related = document.getElementById("p-related").value.split(",").map((s) => parseInt(s.trim(), 10)).filter(Boolean);
    const payload = {
      title: document.getElementById("p-title").value,
      sku: document.getElementById("p-sku").value,
      category_id: document.getElementById("p-category").value ? Number(document.getElementById("p-category").value) : null,
      status: document.getElementById("p-status").value,
      product_type: document.getElementById("p-type").value,
      currency: document.getElementById("p-currency").value,
      price: document.getElementById("p-price").value,
      sale_price: document.getElementById("p-sale").value,
      quantity_available: document.getElementById("p-qty").value === "" ? null : Number(document.getElementById("p-qty").value),
      keywords: document.getElementById("p-keywords").value,
      short_description: document.getElementById("p-short").value,
      description: document.getElementById("p-desc").value,
      specifications: document.getElementById("p-specs").value,
      shipping_required: document.getElementById("p-ship").checked,
      free_shipping: document.getElementById("p-free-ship").checked,
      digital_delivery_url: document.getElementById("p-dig-url").value,
      digital_delivery_text: document.getElementById("p-dig-text").value,
      options: options,
      related_ids: related,
    };
    try {
      let saved;
      if (editingId) {
        saved = await apiRequest("/api/admin/store/products/" + editingId, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        saved = await apiRequest("/api/admin/store/products", { method: "POST", body: JSON.stringify(payload) });
        editingId = saved.id;
      }
      const imgFile = document.getElementById("p-image-file").files[0];
      if (imgFile) {
        const form = new FormData();
        form.append("file", imgFile);
        await fetch(apiUrl("/api/admin/store/products/" + saved.id + "/images"), { method: "POST", credentials: "include", body: form });
      }
      const vidFile = document.getElementById("p-video-file").files[0];
      if (vidFile) {
        const form = new FormData();
        form.append("file", vidFile);
        await fetch(apiUrl("/api/admin/store/products/" + saved.id + "/videos"), { method: "POST", credentials: "include", body: form });
      }
      closeModal("product-modal");
      showToast("Product saved");
      await load();
    } catch (e) {
      err.textContent = e.message;
    }
  });

  document.getElementById("add-image-url").addEventListener("click", async () => {
    if (!editingId) {
      showToast("Save the product first, then add media.");
      return;
    }
    const url = document.getElementById("p-image-url").value.trim();
    if (!url) return;
    const form = new FormData();
    form.append("url", url);
    await fetch(apiUrl("/api/admin/store/products/" + editingId + "/images"), { method: "POST", credentials: "include", body: form });
    const p = await apiRequest("/api/admin/store/products/" + editingId);
    renderMedia(p);
    document.getElementById("p-image-url").value = "";
  });
  document.getElementById("add-video-url").addEventListener("click", async () => {
    if (!editingId) {
      showToast("Save the product first, then add media.");
      return;
    }
    const url = document.getElementById("p-video-url").value.trim();
    if (!url) return;
    await apiRequest("/api/admin/store/products/" + editingId + "/videos", { method: "POST", body: JSON.stringify({ url }) });
    const p = await apiRequest("/api/admin/store/products/" + editingId);
    renderMedia(p);
    document.getElementById("p-video-url").value = "";
  });

  load().catch((e) => showToast(e.message));
})();
