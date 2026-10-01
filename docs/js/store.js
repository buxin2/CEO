(function () {
  let catalog = { store: {}, categories: [], products: [] };
  let activeCategory = getQueryParam("category") || "";
  let searchTimer = null;

  function productHref(p) {
    return "product.html?p=" + encodeURIComponent(p.slug);
  }

  function mediaUrl(p) {
    return p.cover_image || ((p.images || [])[0] && (p.images || [])[0].url) || "";
  }

  function renderHero(featured) {
    const hero = document.getElementById("store-hero");
    if (!featured) {
      hero.classList.add("hidden");
      return;
    }
    const video = StoreStatic.firstVideo(featured);
    const img = mediaUrl(featured);
    let media = "";
    if (video && video.type === "file") {
      media = `<video class="sf-hero-media" src="${escapeHtml(video.url)}" poster="${escapeHtml(img)}" autoplay muted loop playsinline></video>`;
    } else if (img) {
      media = `<div class="sf-hero-media"><img src="${escapeHtml(img)}" alt="${escapeHtml(featured.title)}"></div>`;
    }
    hero.classList.remove("hidden");
    hero.innerHTML = `
      ${media}
      <div class="sf-hero-scrim"></div>
      <div class="sf-hero-copy">
        <div class="sf-kicker">Featured</div>
        <h1>${escapeHtml(featured.title)}</h1>
        <p>${escapeHtml(featured.short_description || "")}</p>
        <div class="sf-hero-actions">
          <a class="sf-btn sf-btn-primary" href="${productHref(featured)}">View product · ${money(featured.unit_price_cents, featured.currency)}</a>
          ${video ? `<a class="sf-btn sf-btn-ghost" href="${productHref(featured)}#videos">Watch video</a>` : ""}
        </div>
      </div>
    `;
  }

  function renderCategories() {
    const bar = document.getElementById("category-bar");
    const chips = [{ name: "All", slug: "" }].concat(catalog.categories || []);
    if (chips.length <= 1) {
      bar.innerHTML = "";
      return;
    }
    bar.innerHTML = chips.map((c) => `
      <button type="button" class="sf-chip ${activeCategory === (c.slug || "") ? "active" : ""}" data-slug="${escapeHtml(c.slug || "")}">
        ${escapeHtml(c.name)}
      </button>
    `).join("");
    bar.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeCategory = btn.dataset.slug || "";
        paint();
      });
    });
  }

  function cardHtml(p) {
    const img = mediaUrl(p);
    const video = StoreStatic.firstVideo(p);
    const media = img
      ? `<img src="${escapeHtml(img)}" alt="${escapeHtml(p.title)}" loading="lazy" onerror="this.style.opacity='.35'">`
      : "";
    return `
      <a class="sf-card" href="${productHref(p)}">
        <div class="sf-card-media">
          ${media}
          ${video ? `<span class="sf-play" aria-hidden="true">▶</span>` : ""}
        </div>
        <div class="sf-card-body">
          <div class="sf-muted">${escapeHtml(p.category_name || p.sku || "")}</div>
          <h3>${escapeHtml(p.title)}</h3>
          <p class="sf-muted">${escapeHtml(p.short_description || "")}</p>
          <div class="sf-price">${money(p.unit_price_cents, p.currency)}${p.sale_price_cents != null ? `<span class="was">${money(p.price_cents, p.currency)}</span>` : ""}</div>
          <div class="sf-avail ${p.in_stock ? "" : "oos"}">${escapeHtml(p.availability || "")}</div>
        </div>
      </a>
    `;
  }

  function paint() {
    StoreStatic.applyBrand(catalog.store || {});
    renderCategories();
    const q = document.getElementById("store-search").value;
    const products = StoreStatic.filterProducts(catalog, q, activeCategory);
    const grid = document.getElementById("product-grid");
    if (!products.length) {
      document.getElementById("store-hero").classList.add("hidden");
      grid.innerHTML = "<div class=\"sf-empty\">No products yet. Images and videos show as soon as you add their links.</div>";
      return;
    }
    renderHero(products[0]);
    grid.innerHTML = products.map(cardHtml).join("");
  }

  function apply(data) {
    if (!data) return;
    catalog = data;
    document.getElementById("store-error").classList.add("hidden");
    paint();
  }

  document.getElementById("store-search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(paint, 160);
  });

  StoreStatic.loadInstant().then(apply).catch(() => {
    document.getElementById("product-grid").innerHTML = "<div class=\"sf-empty\">Could not open the store file.</div>";
  });
  StoreStatic.refreshLive().then((live) => {
    if (live && (live.products || []).length) apply(live);
  });
})();
