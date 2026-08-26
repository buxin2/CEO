(function () {
  let catalog = [];
  let categories = [];
  let activeCategory = getQueryParam("category") || "";
  let searchTimer = null;

  function productHref(p) {
    return "product.html?p=" + encodeURIComponent(p.slug);
  }

  function renderCategories() {
    const bar = document.getElementById("category-bar");
    const chips = [{ name: "All", slug: "" }].concat(categories);
    bar.innerHTML = chips.map((c) => `
      <button class="store-chip ${activeCategory === (c.slug || "") ? "active" : ""}" data-slug="${escapeHtml(c.slug || "")}">
        ${escapeHtml(c.name)}
      </button>
    `).join("");
    bar.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeCategory = btn.dataset.slug || "";
        load();
      });
    });
  }

  function renderProducts(products) {
    const grid = document.getElementById("product-grid");
    if (!products.length) {
      grid.innerHTML = "<p class=\"text-muted\">No products found.</p>";
      return;
    }
    grid.innerHTML = products.map((p) => `
      <a class="store-card" href="${productHref(p)}">
        <img class="store-card-image" src="${escapeHtml(p.cover_image || "")}" alt="${escapeHtml(p.title)}" onerror="this.style.background='#e5e5e8';this.removeAttribute('src')">
        <div class="store-card-body">
          <div class="text-muted" style="font-size:12px;">${escapeHtml(p.category_name || "")}</div>
          <h3>${escapeHtml(p.title)}</h3>
          <p class="text-muted" style="font-size:13px;">${escapeHtml(p.short_description || "")}</p>
          <div class="store-price">${money(p.unit_price_cents, p.currency)}${p.sale_price_cents != null ? `<span class="was">${money(p.price_cents, p.currency)}</span>` : ""}</div>
          <div class="store-avail ${p.in_stock ? "" : "oos"}">${escapeHtml(p.availability)}</div>
          <span class="btn btn-primary btn-sm" style="margin-top:auto;">View product</span>
        </div>
      </a>
    `).join("");
  }

  async function load() {
    const params = new URLSearchParams();
    const q = document.getElementById("store-search").value.trim();
    if (q) params.set("search", q);
    if (activeCategory) params.set("category", activeCategory);
    const res = await storeFetch("/api/store?" + params.toString());
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("store-error").textContent = data.error || "Could not load store.";
      document.getElementById("store-error").classList.remove("hidden");
      return;
    }
    catalog = data.products || [];
    categories = data.categories || [];
    const store = data.store || {};
    document.getElementById("store-brand").innerHTML = escapeHtml(store.store_name || "Store") +
      (store.tagline ? `<small>${escapeHtml(store.tagline)}</small>` : "");
    document.getElementById("hero-title").textContent = store.store_name || "Store";
    if (store.tagline) document.getElementById("hero-tagline").textContent = store.tagline;
    document.title = (store.store_name || "Store");
    renderCategories();
    renderProducts(catalog);
  }

  document.getElementById("store-search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(load, 250);
  });

  load().catch((e) => {
    document.getElementById("store-error").textContent = e.message;
    document.getElementById("store-error").classList.remove("hidden");
  });
})();
