(function () {
  let storeUrl = "";
  let categories = [];
  let editingId = null;
  let pendingImages = [];
  let pendingVideos = [];
  let productsById = {};
  let shareProduct = null;

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
    productsById = {};
    (prod.products || []).forEach((p) => { productsById[p.id] = p; });

    const grid = document.getElementById("product-list");
    grid.classList.add("company-grid");
    grid.innerHTML = (prod.products || []).map((p) => {
      const an = p.analytics || {};
      return `
      <div class="ui-card company-card">
        ${p.cover_image ? `<img src="${escapeHtml(p.cover_image)}" alt="" style="width:100%;height:140px;object-fit:cover;border-radius:12px;">` : ""}
        <div class="entity-card-title">${escapeHtml(p.title)}</div>
        <div class="text-muted">${escapeHtml(p.status)} · ${(p.unit_price_cents / 100).toFixed(2)} ${escapeHtml(p.currency)}</div>
        <div class="text-muted" style="font-size:12px;">${an.views || 0} views · ${an.total_orders || 0} orders</div>
        <div class="flex gap-8 flex-wrap">
          <button class="btn btn-secondary btn-sm" data-copy="${escapeHtml(p.product_url || "")}">Copy link</button>
          <a class="btn btn-secondary btn-sm" href="${escapeHtml(p.product_url || "store.html")}" target="_blank" rel="noopener">Open</a>
          <button class="btn btn-primary btn-sm" data-edit="${p.id}">Edit</button>
        </div>
        <div class="flex gap-8 flex-wrap">
          <button class="btn btn-ghost btn-sm" data-donate="${p.id}">Donate link</button>
          <button class="btn btn-ghost btn-sm" data-qr="${p.id}">QR poster</button>
          <button class="btn btn-ghost btn-sm" data-del="${p.id}">Delete</button>
        </div>
      </div>`;
    }).join("") || "<p class='text-muted'>No products yet. Click Add Product.</p>";

    document.querySelectorAll("[data-copy]").forEach((btn) => {
      btn.addEventListener("click", () => copyToClipboard(btn.dataset.copy).then(() => showToast("Product URL copied")));
    });
    document.querySelectorAll("[data-donate]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const p = productsById[Number(btn.dataset.donate)];
        if (!p) return;
        const url = p.donate_url || (window.StoreShort && StoreShort.donateUrl(p, storeUrl)) || "";
        copyToClipboard(url).then(() => showToast("Donate link copied"));
      });
    });
    document.querySelectorAll("[data-dl-url]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const p = productsById[Number(btn.dataset.dlUrl)];
        if (!p) return;
        ProductShare.downloadUrlFile(p, storeUrl);
        showToast("Product URL file downloaded");
      });
    });
    document.querySelectorAll("[data-qr]").forEach((btn) => {
      btn.addEventListener("click", () => openShare(productsById[Number(btn.dataset.qr)]));
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
    pendingImages = [];
    pendingVideos = [];
    document.getElementById("product-form").reset();
    document.getElementById("p-id").value = "";
    document.getElementById("p-images").innerHTML = "";
    document.getElementById("p-videos").innerHTML = "";
    document.getElementById("p-image-live").classList.add("hidden");
    document.getElementById("p-video-live").classList.add("hidden");
    document.getElementById("p-ship").checked = false;
    document.getElementById("p-weight").value = "";
    syncShipFields();
    document.getElementById("product-modal-title").textContent = "Add product";
    fillShareBox(null);
    openModal("product-modal");
  }

  async function openEdit(id) {
    const p = await apiRequest("/api/admin/store/products/" + id);
    editingId = id;
    document.getElementById("p-id").value = id;
    document.getElementById("p-title").value = p.title || "";
    document.getElementById("p-sku").value = p.sku || "";
    document.getElementById("p-short-code").value = p.short_code || "";
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
    syncShipFields();
    document.getElementById("p-weight").value = p.weight_kg != null ? p.weight_kg : "";
    document.getElementById("p-length").value = p.length_cm != null ? p.length_cm : "";
    document.getElementById("p-width").value = p.width_cm != null ? p.width_cm : "";
    document.getElementById("p-height").value = p.height_cm != null ? p.height_cm : "";
    document.getElementById("p-dig-url").value = p.digital_delivery_url || "";
    document.getElementById("p-dig-text").value = p.digital_delivery_text || "";
    document.getElementById("p-options").value = JSON.stringify(p.options || [], null, 2);
    document.getElementById("p-related").value = (p.related_ids || []).join(",");
    pendingImages = [];
    pendingVideos = [];
    renderMedia(p);
    fillShareBox(p);
    document.getElementById("product-modal-title").textContent = "Edit product";
    openModal("product-modal");
  }

  function renderMedia(p) {
    const savedImgs = (p && p.images) ? p.images : [];
    const savedVids = (p && p.videos) ? p.videos : [];
    document.getElementById("p-images").innerHTML =
      savedImgs.map((i) => `
        <div><img src="${escapeHtml(i.url)}" alt=""><button type="button" class="btn btn-ghost btn-sm" data-del-img="${i.id}">Remove</button></div>
      `).join("") +
      pendingImages.map((url, idx) => `
        <div><img src="${escapeHtml(url)}" alt=""><button type="button" class="btn btn-ghost btn-sm" data-drop-pending-img="${idx}">Remove</button></div>
      `).join("");
    document.getElementById("p-videos").innerHTML =
      savedVids.map((v) => `
        <div class="text-muted">${escapeHtml(v.video_type)} · ${escapeHtml(v.url)} <button type="button" class="btn btn-ghost btn-sm" data-del-vid="${v.id}">Remove</button></div>
      `).join("") +
      pendingVideos.map((url, idx) => `
        <div class="text-muted">pending · ${escapeHtml(url)} <button type="button" class="btn btn-ghost btn-sm" data-drop-pending-vid="${idx}">Remove</button></div>
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
    document.querySelectorAll("[data-drop-pending-img]").forEach((btn) => {
      btn.addEventListener("click", () => {
        pendingImages.splice(Number(btn.dataset.dropPendingImg), 1);
        renderMedia(p);
      });
    });
    document.querySelectorAll("[data-drop-pending-vid]").forEach((btn) => {
      btn.addEventListener("click", () => {
        pendingVideos.splice(Number(btn.dataset.dropPendingVid), 1);
        renderMedia(p);
      });
    });
  }

  function openShare(p) {
    if (!p) return;
    shareProduct = p;
    const url = ProductShare.productPageUrl(p, storeUrl);
    document.getElementById("qr-share-url").value = url;
    document.getElementById("qr-share-status").textContent = "Designing QR poster…";
    const preview = document.getElementById("qr-share-preview");
    preview.getContext("2d").clearRect(0, 0, preview.width, preview.height);
    openModal("qr-share-modal");
    ProductShare.drawPoster(p, storeUrl).then((canvas) => {
      preview.width = canvas.width;
      preview.height = canvas.height;
      preview.getContext("2d").drawImage(canvas, 0, 0);
      document.getElementById("qr-share-status").textContent = "Shop QR on the left, donate QR on the right. Download this image to advertise.";
    }).catch((e) => {
      document.getElementById("qr-share-status").textContent = e.message;
    });
  }

  function fillShareBox(p) {
    const box = document.getElementById("p-share-box");
    const input = document.getElementById("p-page-url");
    if (!box || !input) return;
    if (!p || !p.slug) {
      box.classList.add("hidden");
      return;
    }
    shareProduct = p;
    input.value = ProductShare.productPageUrl(p, storeUrl);
    const donate = document.getElementById("p-donate-url");
    if (donate) donate.value = p.donate_url || (window.StoreShort && StoreShort.donateUrl(p, storeUrl)) || "";
    box.classList.remove("hidden");
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

  function syncShipFields() {
    const on = !!(document.getElementById("p-ship") || {}).checked;
    const digital = (document.getElementById("p-type") || {}).value === "digital";
    const box = document.getElementById("p-ship-fields");
    const ship = document.getElementById("p-ship");
    if (digital && ship) {
      ship.checked = false;
      ship.disabled = true;
    } else if (ship) {
      ship.disabled = false;
    }
    if (box) box.classList.toggle("hidden", digital || !on);
  }

  document.getElementById("p-ship").addEventListener("change", syncShipFields);
  document.getElementById("p-type").addEventListener("change", syncShipFields);

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
      short_code: document.getElementById("p-short-code").value.trim().toLowerCase(),
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
      weight_kg: document.getElementById("p-weight").value,
      length_cm: document.getElementById("p-length").value,
      width_cm: document.getElementById("p-width").value,
      height_cm: document.getElementById("p-height").value,
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
      for (const url of pendingImages) {
        const form = new FormData();
        form.append("url", url);
        await fetch(apiUrl("/api/admin/store/products/" + saved.id + "/images"), { method: "POST", credentials: "include", body: form });
      }
      for (const url of pendingVideos) {
        await apiRequest("/api/admin/store/products/" + saved.id + "/videos", { method: "POST", body: JSON.stringify({ url }) });
      }
      pendingImages = [];
      pendingVideos = [];
      if (window.StoreStatic) StoreStatic.refreshLive();
      fillShareBox(saved);
      showToast("Product saved");
      await load();
    } catch (e) {
      err.textContent = e.message;
    }
  });

  document.getElementById("p-image-url").addEventListener("input", () => {
    const url = document.getElementById("p-image-url").value.trim();
    const img = document.getElementById("p-image-live");
    if (!url) {
      img.classList.add("hidden");
      img.removeAttribute("src");
      return;
    }
    img.src = url;
    img.classList.remove("hidden");
  });
  document.getElementById("p-video-url").addEventListener("input", () => {
    const url = document.getElementById("p-video-url").value.trim();
    const vid = document.getElementById("p-video-live");
    if (!url || url.indexOf("youtube") !== -1 || url.indexOf("vimeo") !== -1 || url.indexOf("youtu.be") !== -1) {
      vid.classList.add("hidden");
      vid.removeAttribute("src");
      return;
    }
    vid.src = url;
    vid.classList.remove("hidden");
  });
  document.getElementById("p-image-file").addEventListener("change", () => {
    const file = document.getElementById("p-image-file").files[0];
    const img = document.getElementById("p-image-live");
    if (!file) return;
    img.src = URL.createObjectURL(file);
    img.classList.remove("hidden");
  });

  document.getElementById("add-image-url").addEventListener("click", async () => {
    const url = document.getElementById("p-image-url").value.trim();
    if (!url) return;
    if (!editingId) {
      pendingImages.push(url);
      renderMedia({ images: [], videos: [] });
      document.getElementById("p-image-url").value = "";
      showToast("Image link queued — it will save with the product.");
      return;
    }
    const form = new FormData();
    form.append("url", url);
    await fetch(apiUrl("/api/admin/store/products/" + editingId + "/images"), { method: "POST", credentials: "include", body: form });
    const p = await apiRequest("/api/admin/store/products/" + editingId);
    renderMedia(p);
    document.getElementById("p-image-url").value = "";
    if (window.StoreStatic) StoreStatic.refreshLive();
  });
  document.getElementById("add-video-url").addEventListener("click", async () => {
    const url = document.getElementById("p-video-url").value.trim();
    if (!url) return;
    if (!editingId) {
      pendingVideos.push(url);
      renderMedia({ images: [], videos: [] });
      document.getElementById("p-video-url").value = "";
      showToast("Video link queued — it will save with the product.");
      return;
    }
    await apiRequest("/api/admin/store/products/" + editingId + "/videos", { method: "POST", body: JSON.stringify({ url }) });
    const p = await apiRequest("/api/admin/store/products/" + editingId);
    renderMedia(p);
    document.getElementById("p-video-url").value = "";
    if (window.StoreStatic) StoreStatic.refreshLive();
  });

  document.getElementById("p-copy-url").addEventListener("click", () => {
    const url = document.getElementById("p-page-url").value;
    if (!url) return;
    copyToClipboard(url).then(() => showToast("Product URL copied"));
  });
  document.getElementById("p-copy-donate").addEventListener("click", () => {
    const url = document.getElementById("p-donate-url").value;
    if (!url) return;
    copyToClipboard(url).then(() => showToast("Donate link copied"));
  });
  document.getElementById("p-dl-url").addEventListener("click", () => {
    if (!shareProduct) return;
    ProductShare.downloadUrlFile(shareProduct, storeUrl);
    showToast("Product URL file downloaded");
  });
  document.getElementById("p-qr").addEventListener("click", () => openShare(shareProduct));
  document.getElementById("qr-copy-url").addEventListener("click", () => {
    copyToClipboard(document.getElementById("qr-share-url").value).then(() => showToast("Product URL copied"));
  });
  document.getElementById("qr-dl-url").addEventListener("click", () => {
    if (!shareProduct) return;
    ProductShare.downloadUrlFile(shareProduct, storeUrl);
    showToast("Product URL file downloaded");
  });
  document.getElementById("qr-dl-poster").addEventListener("click", async () => {
    if (!shareProduct) return;
    try {
      await ProductShare.downloadPoster(shareProduct, storeUrl);
      showToast("QR poster downloaded");
    } catch (e) {
      showToast(e.message);
    }
  });

  document.getElementById("export-catalog").addEventListener("click", async () => {
    const live = window.StoreStatic ? await StoreStatic.refreshLive() : null;
    const data = live || { store: {}, categories: [], products: [] };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "store-catalog.json";
    a.click();
    showToast("Saved snapshot. Replace docs/data/store-catalog.json and push so phones see it with no backend.");
  });

  load().catch((e) => showToast(e.message));
})();
