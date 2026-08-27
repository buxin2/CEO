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
    const el = document.getElementById("live-price");
    if (el) el.textContent = money((product.unit_price_cents || 0) + extraCents(), product.currency);
  }

  function setMedia(i) {
    mediaIndex = (i + media.length) % media.length;
    const item = media[mediaIndex];
    const main = document.getElementById("gallery-main");
    if (!item) return;
    if (item.kind === "image") {
      main.innerHTML = `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(product.title)}">`;
      main.onclick = () => {
        const overlay = document.createElement("div");
        overlay.className = "zoom-overlay";
        overlay.innerHTML = `<img src="${escapeHtml(item.url)}" alt="">`;
        overlay.onclick = () => overlay.remove();
        document.body.appendChild(overlay);
      };
    } else if (item.embed && (item.type === "youtube" || item.type === "vimeo")) {
      main.innerHTML = `<div class="video-embed" style="padding-bottom:56.25%;position:relative;height:auto;min-height:280px;"><iframe src="${escapeHtml(item.embed)}" allowfullscreen allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"></iframe></div>`;
      main.onclick = null;
    } else {
      main.innerHTML = `<video src="${escapeHtml(item.url)}" controls></video>`;
      main.onclick = null;
    }
    document.querySelectorAll(".product-thumbs [data-i]").forEach((el) => {
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

  function render() {
    const store = product.store || {};
    document.getElementById("store-brand").textContent = store.store_name || "Store";
    document.title = product.title;
    document.getElementById("meta-desc").setAttribute("content", product.short_description || product.title);
    document.getElementById("og-title").setAttribute("content", product.title);
    document.getElementById("og-desc").setAttribute("content", (product.short_description || "") + " · " + money(product.unit_price_cents, product.currency));
    if (product.cover_image) document.getElementById("og-image").setAttribute("content", product.cover_image);

    media = (product.images || []).map((i) => ({ kind: "image", url: i.url }));
    (product.videos || []).forEach((v) => media.push({ kind: "video", url: v.url, embed: v.embed_url, type: v.video_type }));

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
      <a class="store-card" href="product.html?p=${encodeURIComponent(p.slug)}">
        <img class="store-card-image" src="${escapeHtml(p.cover_image || "")}" alt="">
        <div class="store-card-body">
          <h3>${escapeHtml(p.title)}</h3>
          <div class="store-price">${money(p.unit_price_cents, p.currency)}</div>
        </div>
      </a>
    `).join("");

    const videosHtml = (product.videos || []).map((v) => {
      if (v.video_type === "youtube" || v.video_type === "vimeo") {
        return `<div class="video-embed"><iframe src="${escapeHtml(v.embed_url)}" allowfullscreen allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"></iframe></div>`;
      }
      return `<video src="${escapeHtml(v.url)}" controls style="width:100%;border-radius:12px;"></video>`;
    }).join("");

    document.getElementById("product-root").innerHTML = `
      <div class="product-layout">
        <div>
          <div class="product-gallery-main" id="gallery-main"></div>
          <div class="product-thumbs" id="thumbs">
            ${media.map((m, i) => m.kind === "image"
              ? `<img data-i="${i}" src="${escapeHtml(m.url)}" alt="">`
              : `<button data-i="${i}" type="button">Video</button>`
            ).join("")}
          </div>
        </div>
        <div class="product-buy-box">
          <div class="text-muted" style="font-size:12px;">${escapeHtml(product.category_name || "")} ${product.sku ? "· SKU " + escapeHtml(product.sku) : ""}</div>
          <h1>${escapeHtml(product.title)}</h1>
          <p class="text-muted">${escapeHtml(product.short_description || "")}</p>
          <div class="store-price" id="live-price">${money(product.unit_price_cents, product.currency)}</div>
          ${product.sale_price_cents != null ? `<div class="was">${money(product.price_cents, product.currency)}</div>` : ""}
          <div class="store-avail ${oos ? "oos" : ""}">${escapeHtml(product.availability)}</div>
          ${optionHtml}
          <div class="qty-row">
            <label for="qty-select">Quantity</label>
            <select class="form-control" id="qty-select" ${oos ? "disabled" : ""}>
              ${[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => `<option value="${n}">${n}</option>`).join("")}
              <option value="custom">Custom</option>
            </select>
            <input class="form-control hidden" id="qty-input" type="number" min="11" max="999" inputmode="numeric" placeholder="11+" ${oos ? "disabled" : ""}>
          </div>
          <div class="buy-actions">
            <button class="btn btn-primary btn-block" id="buy-now" ${oos ? "disabled" : ""}>Buy now</button>
            <button class="btn btn-secondary btn-block" id="add-cart" ${oos ? "disabled" : ""}>Add to cart</button>
          </div>
          <p class="text-muted" style="margin-top:12px;font-size:13px;">
            ${product.shipping_required ? "Physical product — shipping is calculated at checkout based on your country." : "Digital product — no shipping required. Access is provided after payment."}
          </p>
        </div>
      </div>
      <section class="product-section">
        <h2>Description</h2>
        <div class="product-desc">${product.description || "<p class='text-muted'>No description yet.</p>"}</div>
      </section>
      ${product.specifications ? `<section class="product-section"><h2>Specifications</h2><div class="product-desc">${product.specifications}</div></section>` : ""}
      ${videosHtml ? `<section class="product-section"><h2>Videos</h2>${videosHtml}</section>` : ""}
      <section class="product-section">
        <h2>Shipping & payment</h2>
        <div class="product-desc">
          <p>Pay securely with the payment methods available at checkout (PayPal, mobile payment, or bank transfer where configured).</p>
          <p>Shipping rates are set by destination. If delivery is not available to your country, checkout will tell you before you pay.</p>
        </div>
      </section>
      ${related ? `<section class="product-section"><h2>Related products</h2><div class="store-grid">${related}</div></section>` : ""}
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
    sticky.innerHTML = `<button class="btn btn-primary btn-block" id="sticky-buy-btn" ${oos ? "disabled" : ""}>Buy now · <span id="sticky-price">${money(product.unit_price_cents, product.currency)}</span></button>`;
    document.getElementById("sticky-buy-btn").addEventListener("click", buyNow);
    setMedia(0);
  }

  (async function init() {
    if (!slug) {
      document.getElementById("product-root").innerHTML = "<p>Product not found.</p>";
      return;
    }
    const qs = preview ? ("?preview=" + encodeURIComponent(preview)) : "";
    const res = await storeFetch("/api/store/products/" + encodeURIComponent(slug) + qs);
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("product-root").innerHTML = `<p>${escapeHtml(data.error || "Product not found.")}</p>`;
      return;
    }
    product = data;
    window.STORE_CONTACT_PRODUCT = {
      title: product.title,
      url: location.href,
    };
    render();
  })().catch((e) => {
    document.getElementById("product-root").innerHTML = `<p>${escapeHtml(e.message)}</p>`;
  });
})();
