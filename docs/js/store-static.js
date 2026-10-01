/* Public store catalog: GitHub Pages JSON first, live API later. Media is always a public URL. */

(function (global) {
  const CACHE_KEY = "mms_store_catalog_v1";
  const FILE = "data/store-catalog.json";

  function clone(data) {
    return JSON.parse(JSON.stringify(data || { store: {}, categories: [], products: [] }));
  }

  function fromCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data || !Array.isArray(data.products)) return null;
      return data;
    } catch (e) {
      return null;
    }
  }

  function saveCache(data) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    } catch (e) {}
  }

  async function fromFile() {
    const url = new URL(FILE, window.location.href).href + "?v=2";
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error("catalog");
    return res.json();
  }

  function mergePreferRicher(a, b) {
    if (!a) return b;
    if (!b) return a;
    const aN = (a.products || []).length;
    const bN = (b.products || []).length;
    if (bN > aN) return b;
    if (aN > bN) return a;
    const aMedia = (a.products || []).reduce((n, p) => n + ((p.images || []).length) + ((p.videos || []).length), 0);
    const bMedia = (b.products || []).reduce((n, p) => n + ((p.images || []).length) + ((p.videos || []).length), 0);
    return bMedia >= aMedia ? b : a;
  }

  async function loadInstant() {
    const cached = fromCache();
    try {
      const file = await fromFile();
      const data = mergePreferRicher(file, cached);
      if (data) saveCache(data);
      return clone(data || file);
    } catch (e) {
      if (cached) return clone(cached);
      return { store: { store_name: "Store", tagline: "" }, categories: [], products: [] };
    }
  }

  async function refreshLive() {
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 9000) : null;
    try {
      const res = await fetch(apiUrl("/api/store"), ctrl ? { signal: ctrl.signal } : {});
      const data = await res.json();
      if (!res.ok || !data || !Array.isArray(data.products)) return null;
      const slim = {
        store: data.store || {},
        categories: data.categories || [],
        products: data.products || [],
      };
      saveCache(slim);
      return slim;
    } catch (e) {
      return null;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  async function loadProduct(slug, preview) {
    const catalog = await loadInstant();
    let product = (catalog.products || []).find((p) => p.slug === slug) || null;
    if (product) {
      product = Object.assign({}, product, { store: catalog.store || {}, related: relatedOf(catalog, product) });
    }
    refreshProduct(slug, preview).then((live) => {
      if (!live || typeof global.StoreStatic.onProductLive !== "function") return;
      global.StoreStatic.onProductLive(live);
    });
    return product;
  }

  async function refreshProduct(slug, preview) {
    try {
      const qs = preview ? ("?preview=" + encodeURIComponent(preview)) : "";
      const res = await fetch(apiUrl("/api/store/products/" + encodeURIComponent(slug) + qs), { credentials: "include" });
      const data = await res.json();
      if (!res.ok) return null;
      return data;
    } catch (e) {
      return null;
    }
  }

  function relatedOf(catalog, product) {
    return (catalog.products || []).filter((p) => p.id !== product.id && p.status === "active").slice(0, 4);
  }

  function filterProducts(catalog, search, category) {
    const q = (search || "").trim().toLowerCase();
    return (catalog.products || []).filter((p) => {
      if (p.status && p.status !== "active") return false;
      if (category) {
        const want = String(category).toLowerCase();
        const nameSlug = String(p.category_name || "").toLowerCase().replace(/\s+/g, "-");
        const idOk = String(p.category_id || "") === String(category);
        if (!idOk && nameSlug !== want && String(p.category_name || "").toLowerCase() !== want) return false;
      }
      if (!q) return true;
      const blob = [p.title, p.short_description, p.keywords, p.sku].join(" ").toLowerCase();
      return blob.indexOf(q) !== -1;
    });
  }

  function youtubeId(url) {
    const m = String(url || "").match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|shorts\/))([\w-]{11})/);
    return m ? m[1] : "";
  }

  function vimeoId(url) {
    const m = String(url || "").match(/vimeo\.com\/(?:video\/)?(\d+)/);
    return m ? m[1] : "";
  }

  function mediaList(product) {
    const items = [];
    (product.images || []).forEach((i) => {
      if (i && i.url) items.push({ kind: "image", url: i.url, alt: i.alt_text || product.title || "" });
    });
    if (!items.length && product.cover_image) {
      items.push({ kind: "image", url: product.cover_image, alt: product.title || "" });
    }
    (product.videos || []).forEach((v) => {
      const url = v.url || v.embed_url || "";
      if (!url) return;
      const yt = youtubeId(url) || youtubeId(v.embed_url);
      const vim = vimeoId(url) || vimeoId(v.embed_url);
      if (yt || v.video_type === "youtube") {
        const id = yt || youtubeId(v.embed_url);
        items.push({
          kind: "video",
          type: "youtube",
          url: url,
          embed: "https://www.youtube.com/embed/" + id + "?rel=0&playsinline=1",
        });
      } else if (vim || v.video_type === "vimeo") {
        items.push({
          kind: "video",
          type: "vimeo",
          url: url,
          embed: "https://player.vimeo.com/video/" + vim,
        });
      } else {
        items.push({ kind: "video", type: "file", url: v.embed_url || url, embed: "" });
      }
    });
    return items;
  }

  function firstVideo(product) {
    return mediaList(product).find((m) => m.kind === "video") || null;
  }

  function autoplayEmbed(item) {
    if (!item) return "";
    if (item.type === "youtube") {
      const id = youtubeId(item.embed) || youtubeId(item.url);
      if (!id) return item.embed || "";
      return "https://www.youtube.com/embed/" + id + "?autoplay=1&mute=1&playsinline=1&rel=0&loop=1&playlist=" + id;
    }
    if (item.type === "vimeo") {
      const base = item.embed || "";
      return base + (base.indexOf("?") >= 0 ? "&" : "?") + "autoplay=1&muted=1&loop=1&background=1";
    }
    return item.embed || "";
  }

  function kickPlay(el) {
    if (!el) return;
    if (el.tagName === "VIDEO") {
      el.muted = true;
      el.defaultMuted = true;
      el.playsInline = true;
      el.setAttribute("playsinline", "");
      el.setAttribute("muted", "");
      const play = el.play();
      if (play && play.catch) play.catch(function () {});
    }
  }

  function bindAutoplayOnView(root) {
    const scope = root || document;
    const nodes = scope.querySelectorAll("video[data-sf-autoplay]");
    nodes.forEach(kickPlay);
    if (!("IntersectionObserver" in window)) return;
    if (scope._sfAutoplayIo) scope._sfAutoplayIo.disconnect();
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        const el = entry.target;
        if (el.tagName !== "VIDEO") return;
        if (entry.isIntersecting && entry.intersectionRatio >= 0.35) kickPlay(el);
        else if (!entry.isIntersecting) el.pause();
      });
    }, { threshold: [0, 0.35, 0.6] });
    nodes.forEach(function (n) { io.observe(n); });
    scope._sfAutoplayIo = io;
  }

  function richText(html) {
    const raw = (html || "").trim();
    if (!raw) return "<p class=\"sf-muted\">No description yet.</p>";
    if (/<[a-z][\s\S]*>/i.test(raw)) return raw;
    return "<p>" + escapeHtml(raw).replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>") + "</p>";
  }

  function applyBrand(store) {
    const name = (store && store.store_name) || "Store";
    const tag = (store && store.tagline) || "";
    const brandName = document.getElementById("sf-brand-name");
    const brandTag = document.getElementById("sf-brand-tag");
    const titleEl = document.getElementById("hero-title");
    const tagEl = document.getElementById("hero-tagline");
    if (brandName) brandName.textContent = name;
    if (brandTag) {
      brandTag.textContent = tag;
      brandTag.hidden = !tag;
    }
    if (titleEl) titleEl.textContent = name;
    if (tagEl && tag) tagEl.textContent = tag;
    document.title = name;
    const mark = document.getElementById("sf-brand-mark");
    if (mark) mark.textContent = (name.trim()[0] || "S").toUpperCase();
  }

  global.StoreStatic = {
    loadInstant,
    refreshLive,
    loadProduct,
    refreshProduct,
    filterProducts,
    mediaList,
    firstVideo,
    autoplayEmbed,
    kickPlay,
    bindAutoplayOnView,
    richText,
    applyBrand,
    saveCache,
    relatedOf,
    onProductLive: null,
  };
})(window);
