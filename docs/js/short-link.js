/* Short GitHub Pages paths like /CEO/mrj → product.html?p=slug */

(function (global) {
  const RESERVED = {
    store: 1, product: 1, login: 1, dashboard: 1, index: 1, css: 1, js: 1, data: 1,
    payments: 1, checkout: 1, communities: 1, community: 1, docs: 1, api: 1,
    "admin-store": 1, "store-account": 1, "store-checkout": 1, "store-order": 1,
    orders: 1, news: 1, ideas: 1, mentor: 1, company: 1, group: 1, task: 1,
    timetable: 1, "ai-assistant": 1, go: 1, p: 1,
  };

  function clean(code) {
    return String(code || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "").slice(0, 16);
  }

  function shortCode(product) {
    const custom = clean(product && product.short_code);
    if (custom && !RESERVED[custom]) return custom;
    const sku = String((product && product.sku) || "").toLowerCase();
    const letters = (sku.match(/^[a-z]+/) || [""])[0];
    if (letters && letters.length >= 2 && !RESERVED[letters]) return letters;
    const fromSlug = clean((product && product.slug || "").split("-")[0]);
    if (fromSlug && !RESERVED[fromSlug]) return fromSlug.slice(0, 8);
    return "p" + String((product && product.id) || "");
  }

  function siteBase(storeUrl) {
    let base = String(storeUrl || "").replace(/store\.html.*$/i, "");
    if (!base && global.location) {
      const parts = location.pathname.split("/").filter(Boolean);
      if (parts.length && parts[0] !== "CEO" && location.hostname.indexOf("github.io") >= 0) {
        base = location.origin + "/";
      } else if (parts[0] === "CEO") {
        base = location.origin + "/CEO/";
      } else {
        base = location.origin + location.pathname.replace(/[^/]*$/, "");
      }
    }
    if (base && base.slice(-1) !== "/") base += "/";
    return base;
  }

  function shortUrl(product, storeUrl) {
    const base = siteBase(storeUrl);
    const code = shortCode(product);
    return base + code;
  }

  function pathCode() {
    const parts = location.pathname.split("/").filter(Boolean);
    let last = parts[parts.length - 1] || "";
    if (last.indexOf(".") >= 0) last = last.replace(/\.html$/i, "");
    if (RESERVED[last.toLowerCase()] || last === "404") return "";
    return clean(last);
  }

  function findProduct(catalog, code) {
    const want = clean(code);
    if (!want) return null;
    const list = (catalog && catalog.products) || [];
    return list.find((p) => shortCode(p) === want || clean(p.short_code) === want) || null;
  }

  async function go(code) {
    const want = clean(code || pathCode());
    if (!want) return false;
    try {
      const res = await fetch("data/store-catalog.json?v=3", { cache: "no-cache" });
      const catalog = await res.json();
      const product = findProduct(catalog, want);
      if (!product || !product.slug) return false;
      location.replace("product.html?p=" + encodeURIComponent(product.slug));
      return true;
    } catch (e) {
      return false;
    }
  }

  global.StoreShort = { RESERVED, clean, shortCode, siteBase, shortUrl, pathCode, findProduct, go };
})(window);
