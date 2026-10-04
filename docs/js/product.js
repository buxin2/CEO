(function () {
  const slug = getQueryParam("p") || getQueryParam("slug");
  const preview = getQueryParam("preview");
  let product = null;
  let mediaIndex = 0;
  let media = [];

  function selectedOptions() {
    const opts = {};
    (product.options || []).forEach((opt) => {
      if (!(opt.values || []).length) return;
      const el = document.querySelector('[data-option="' + opt.name.replace(/"/g, "") + '"]');
      if (el && el.value) opts[opt.name] = el.value;
    });
    return opts;
  }

  function qty() {
    const select = document.getElementById("qty-select");
    if (select && select.value !== "custom") {
      return Math.max(1, parseInt(select.value, 10) || 1);
    }
    const custom = document.getElementById("qty-input");
    return Math.max(1, Math.min(999, parseInt((custom && custom.value) || "1", 10) || 1));
  }

  function syncQtyCustom() {
    const select = document.getElementById("qty-select");
    const custom = document.getElementById("qty-input");
    if (!select || !custom) return;
    const isCustom = select.value === "custom";
    custom.classList.toggle("hidden", !isCustom);
    if (isCustom) {
      const n = parseInt(custom.value, 10);
      if (!n || n < 11) custom.value = "11";
      custom.focus();
      custom.select();
    }
  }

  function extraCents() {
    let extra = 0;
    const selected = selectedOptions();
    (product.options || []).forEach((opt) => {
      const val = (opt.values || []).find((v) => v.label === selected[opt.name]);
      if (val) extra += val.extra_cents || 0;
    });
    return extra;
  }

  function renderPrice() {
    const price = money((product.unit_price_cents || 0) + extraCents(), product.currency);
    const el = document.getElementById("live-price");
    if (el) el.textContent = price;
    const sticky = document.getElementById("sticky-price");
    if (sticky) sticky.textContent = price;
  }

  function setMedia(i) {
    if (!media.length) return;
    mediaIndex = (i + media.length) % media.length;
    const item = media[mediaIndex];
    const main = document.getElementById("gallery-main");
    if (!item || !main) return;
    if (item.kind === "image") {
      main.innerHTML = `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.alt || product.title)}"><button class="sf-nav-btn prev" type="button" aria-label="Previous">‹</button><button class="sf-nav-btn next" type="button" aria-label="Next">›</button>`;
      main.querySelector("img").onclick = () => {
        const overlay = document.createElement("div");
        overlay.className = "zoom-overlay";
        overlay.innerHTML = `<img src="${escapeHtml(item.url)}" alt="">`;
        overlay.onclick = () => overlay.remove();
        document.body.appendChild(overlay);
      };
    } else if (item.embed && (item.type === "youtube" || item.type === "vimeo")) {
      main.innerHTML = `<iframe src="${escapeHtml(StoreStatic.autoplayEmbed(item))}" allow="autoplay; accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; playsinline" allowfullscreen></iframe><button class="sf-nav-btn prev" type="button">‹</button><button class="sf-nav-btn next" type="button">›</button>`;
    } else {
      main.innerHTML = `<video src="${escapeHtml(item.url)}" data-sf-autoplay autoplay muted loop playsinline webkit-playsinline controls></video><button class="sf-nav-btn prev" type="button">‹</button><button class="sf-nav-btn next" type="button">›</button>`;
      StoreStatic.kickPlay(main.querySelector("video"));
    }
    const prev = main.querySelector(".prev");
    const next = main.querySelector(".next");
    if (prev) prev.onclick = (ev) => { ev.stopPropagation(); setMedia(mediaIndex - 1); };
    if (next) next.onclick = (ev) => { ev.stopPropagation(); setMedia(mediaIndex + 1); };
    document.querySelectorAll(".sf-thumbs [data-i]").forEach((el) => {
      el.classList.toggle("active", Number(el.dataset.i) === mediaIndex);
    });
  }

  function cartPayload() {
    return {
      product_id: product.id,
      title: product.title,
      slug: product.slug,
      cover_image: product.cover_image,
      quantity: qty(),
      options: selectedOptions(),
      currency: product.currency,
    };
  }

  function buyNow() {
    const payload = cartPayload();
    saveStoreCart([payload]);
    const params = new URLSearchParams();
    params.set("buy", "1");
    params.set("product_id", String(payload.product_id));
    params.set("qty", String(payload.quantity || 1));
    if (payload.options && Object.keys(payload.options).length) {
      params.set("options", JSON.stringify(payload.options));
    }
    window.location.href = "store-checkout.html?" + params.toString();
  }

  function addCart() {
    addToStoreCart(cartPayload());
    showToast("Added to cart");
  }

  function bindSwipe(el) {
    let x0 = null;
    el.addEventListener("touchstart", (e) => {
      x0 = e.changedTouches[0].screenX;
    }, { passive: true });
    el.addEventListener("touchend", (e) => {
      if (x0 == null) return;
      const dx = e.changedTouches[0].screenX - x0;
      x0 = null;
      if (dx > 40) setMedia(mediaIndex - 1);
      if (dx < -40) setMedia(mediaIndex + 1);
    }, { passive: true });
  }

  function render() {
    const store = product.store || {};
    StoreStatic.applyBrand(store);
    document.title = product.title;
    document.getElementById("meta-desc").setAttribute("content", product.short_description || product.title);
    document.getElementById("og-title").setAttribute("content", product.title);
    document.getElementById("og-desc").setAttribute("content", (product.short_description || "") + " · " + money(product.unit_price_cents, product.currency));
    if (product.cover_image) document.getElementById("og-image").setAttribute("content", product.cover_image);

    media = StoreStatic.mediaList(product);

    const optionHtml = (product.options || []).filter((opt) => (opt.values || []).length).map((opt) => `
      <div class="option-group">
        <label>${escapeHtml(opt.name)}</label>
        <select class="form-control" data-option="${escapeHtml(opt.name)}">
          ${(opt.values || []).map((v) => `<option value="${escapeHtml(v.label)}">${escapeHtml(v.label)}${v.extra_cents ? " (+" + money(v.extra_cents, product.currency) + ")" : ""}</option>`).join("")}
        </select>
      </div>
    `).join("");

    const oos = !product.in_stock;
    const related = (product.related || []).map((p) => `
      <a class="sf-card" href="product.html?p=${encodeURIComponent(p.slug)}">
        <div class="sf-card-media"><img src="${escapeHtml(p.cover_image || "")}" alt=""></div>
        <div class="sf-card-body">
          <h3>${escapeHtml(p.title)}</h3>
          <div class="sf-price">${money(p.unit_price_cents, p.currency)}</div>
        </div>
      </a>
    `).join("");

    const videosHtml = (product.videos || []).map((v) => {
      const item = StoreStatic.mediaList({ videos: [v], images: [] }).find((m) => m.kind === "video");
      if (!item) return "";
      if (item.embed) {
        return `<div class="video-embed"><iframe src="${escapeHtml(StoreStatic.autoplayEmbed(item))}" allowfullscreen allow="autoplay; accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; playsinline"></iframe></div>`;
      }
      return `<div class="sf-video-block"><video src="${escapeHtml(item.url)}" data-sf-autoplay autoplay muted loop playsinline webkit-playsinline controls></video></div>`;
    }).join("");

    const thumbs = media.map((m, i) => {
      if (m.kind === "image") return `<img data-i="${i}" src="${escapeHtml(m.url)}" alt="">`;
      return `<button data-i="${i}" type="button">▶</button>`;
    }).join("");

    document.getElementById("product-root").innerHTML = `
      <div class="sf-product">
        <div class="sf-gallery">
          <div class="sf-gallery-main" id="gallery-main"></div>
          <div class="sf-thumbs" id="thumbs">${thumbs}</div>
        </div>
        <div class="sf-buy">
          <div class="sf-muted">${escapeHtml(product.category_name || "")} ${product.sku ? "· " + escapeHtml(product.sku) : ""}</div>
          <h1>${escapeHtml(product.title)}</h1>
          <p class="sf-muted">${escapeHtml(product.short_description || "")}</p>
          <div class="sf-price" id="live-price">${money(product.unit_price_cents, product.currency)}</div>
          ${product.sale_price_cents != null ? `<div class="was">${money(product.price_cents, product.currency)}</div>` : ""}
          <div class="sf-avail ${oos ? "oos" : ""}">${escapeHtml(product.availability || "")}</div>
          ${optionHtml}
          <div class="sf-qty qty-row">
            <label for="qty-select">Qty</label>
            <select class="form-control" id="qty-select" ${oos ? "disabled" : ""}>
              ${[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => `<option value="${n}">${n}</option>`).join("")}
              <option value="custom">Custom</option>
            </select>
            <input class="form-control hidden" id="qty-input" type="number" min="11" max="999" inputmode="numeric" placeholder="11+" ${oos ? "disabled" : ""}>
          </div>
          <div class="sf-actions">
            <button class="sf-btn sf-btn-primary sf-btn-block" id="buy-now" ${oos ? "disabled" : ""}>Buy now</button>
            <button class="sf-btn sf-btn-ghost sf-btn-block" id="add-cart" style="color:inherit;background:#fff;box-shadow:inset 0 0 0 1px rgba(22,19,17,.12)" ${oos ? "disabled" : ""}>Add to cart</button>
          </div>
          <p class="sf-muted" style="margin-top:14px;">
            ${product.shipping_required ? "Ships worldwide where available. Pay with card, PayPal, or Wave at checkout." : "Pay with card, PayPal, or Wave at checkout."}
          </p>
        </div>
      </div>
      <section class="sf-section">
        <h2>Description</h2>
        <div class="sf-prose product-desc">${StoreStatic.richText(product.description)}</div>
      </section>
      ${product.specifications ? `<section class="sf-section"><h2>Specifications</h2><div class="sf-prose">${StoreStatic.richText(product.specifications)}</div></section>` : ""}
      ${videosHtml ? `<section class="sf-section" id="videos"><h2>Videos</h2>${videosHtml}</section>` : ""}
      ${product.shipping_required ? `<section class="sf-section">
        <h2>Shipping & payment</h2>
        <div class="sf-prose">
          <p>Checkout adds FedEx shipping for your country. Pay with PayPal or Wave / AfriMoney / QMoney.</p>
        </div>
      </section>` : ""}
      ${related ? `<section class="sf-section"><h2>You may also like</h2><div class="sf-grid">${related}</div></section>` : ""}
    `;

    document.getElementById("thumbs").querySelectorAll("[data-i]").forEach((el) => {
      el.addEventListener("click", () => setMedia(Number(el.dataset.i)));
    });
    document.querySelectorAll("[data-option]").forEach((el) => el.addEventListener("change", renderPrice));
    const qtySelect = document.getElementById("qty-select");
    if (qtySelect) qtySelect.addEventListener("change", syncQtyCustom);
    document.getElementById("buy-now").addEventListener("click", buyNow);
    document.getElementById("add-cart").addEventListener("click", addCart);
    const sticky = document.getElementById("sticky-buy");
    sticky.classList.remove("hidden");
    sticky.innerHTML = `<button class="sf-btn sf-btn-primary" id="sticky-buy-btn" ${oos ? "disabled" : ""}>Buy now · <span id="sticky-price">${money(product.unit_price_cents, product.currency)}</span></button>`;
    document.getElementById("sticky-buy-btn").addEventListener("click", buyNow);
    setMedia(0);
    bindSwipe(document.getElementById("gallery-main"));
    StoreStatic.bindAutoplayOnView(document.getElementById("product-root"));
  }

  if (!slug) {
    document.getElementById("product-root").innerHTML = "<p class=\"sf-empty\">Product not found.</p>";
    return;
  }

  StoreStatic.onProductLive = function (live) {
    if (!live || !live.id) return;
    product = live;
    window.STORE_CONTACT_PRODUCT = { title: product.title, url: location.href };
    render();
  };

  StoreStatic.loadProduct(slug, preview).then((p) => {
    if (!p) {
      document.getElementById("product-root").innerHTML = "<p class=\"sf-empty\">Opening product… if this stays empty, the catalog file has no matching item.</p>";
      return;
    }
    product = p;
    window.STORE_CONTACT_PRODUCT = { title: product.title, url: location.href };
    render();
  }).catch((e) => {
    document.getElementById("product-root").innerHTML = `<p class="sf-empty">${escapeHtml(e.message)}</p>`;
  });
})();
