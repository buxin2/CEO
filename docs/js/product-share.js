/* Product page URL + QR advertising poster (admin Products). */

(function (global) {
  const W = 1080;
  const H = 1920;
  const QR = 400;

  function roundRect(ctx, x, y, w, h, r) {
    const rad = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rad, y);
    ctx.arcTo(x + w, y, x + w, y + h, rad);
    ctx.arcTo(x + w, y + h, x, y + h, rad);
    ctx.arcTo(x, y + h, x, y, rad);
    ctx.arcTo(x, y, x + w, y, rad);
    ctx.closePath();
  }

  function wrapText(ctx, text, maxWidth) {
    const words = String(text || "").split(/\s+/);
    const lines = [];
    let line = "";
    words.forEach((word) => {
      const test = line ? line + " " + word : word;
      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);
        line = word;
      } else {
        line = test;
      }
    });
    if (line) lines.push(line);
    return lines.slice(0, 3);
  }

  function wrapChars(ctx, text, maxWidth, maxLines) {
    const s = String(text || "");
    const lines = [];
    let line = "";
    for (let i = 0; i < s.length; i++) {
      const test = line + s[i];
      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);
        line = s[i];
        if (lines.length >= (maxLines || 2) - 1) {
          line = s.slice(i);
          break;
        }
      } else {
        line = test;
      }
    }
    if (line) lines.push(line);
    return lines.slice(0, maxLines || 2);
  }

  function formatPrice(cents, currency) {
    const n = (Number(cents) || 0) / 100;
    const cur = currency || "USD";
    try {
      return new Intl.NumberFormat("en-US", { style: "currency", currency: cur }).format(n);
    } catch (e) {
      return n.toFixed(2) + " " + cur;
    }
  }

  function productPageUrl(product, storeUrl) {
    if (global.StoreShort) return StoreShort.shortUrl(product, storeUrl);
    if (product && product.product_url) return product.product_url;
    const base = String(storeUrl || "").replace(/store\.html.*$/i, "");
    const slug = (product && product.slug) || "";
    if (base && slug) return base + "product.html?p=" + encodeURIComponent(slug);
    return "";
  }

  function longPageUrl(product, storeUrl) {
    if (product && product.product_url) return product.product_url;
    const base = String(storeUrl || "").replace(/store\.html.*$/i, "");
    const slug = (product && product.slug) || "";
    if (base && slug) return base + "product.html?p=" + encodeURIComponent(slug);
    return "";
  }

  function donatePageUrl(product, storeUrl) {
    if (product && product.donate_url) return product.donate_url;
    if (global.StoreShort) return StoreShort.donateUrl(product, storeUrl);
    const base = String(storeUrl || "").replace(/store\.html.*$/i, "");
    const slug = (product && product.slug) || "";
    const code = (product && (product.short_code || "")) || "";
    if (base && (code || slug)) {
      return base + "donate.html" + (code ? "?c=" + encodeURIComponent(code) : "") + (slug ? (code ? "&" : "?") + "p=" + encodeURIComponent(slug) : "");
    }
    return "";
  }

  function displayUrl(url) {
    return String(url || "").replace(/^https:\/\//i, "");
  }

  function whatsappLabel() {
    const raw = (global.APP_CONFIG && APP_CONFIG.WHATSAPP_NUMBER) || "";
    const d = String(raw).replace(/\D/g, "");
    if (d.length === 12 && d.indexOf("91") === 0) {
      return "WhatsApp +91 " + d.slice(2, 7) + " " + d.slice(7);
    }
    if (d.length === 10) return "WhatsApp +91 " + d.slice(0, 5) + " " + d.slice(5);
    if (d) return "WhatsApp +" + d;
    return "";
  }

  function loadImage(src) {
    return new Promise((resolve) => {
      if (!src) {
        resolve(null);
        return;
      }
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = src.indexOf("data:") === 0 ? src : src;
    });
  }

  async function makeQrDataUrl(text, size) {
    const px = size || QR;
    if (global.QRCode && typeof global.QRCode.toDataURL === "function") {
      return global.QRCode.toDataURL(text, {
        width: px,
        margin: 1,
        color: { dark: "#161311", light: "#fffaf2" },
        errorCorrectionLevel: "M",
      });
    }
    const src = "https://api.qrserver.com/v1/create-qr-code/?size=" + px + "x" + px + "&margin=8&data=" + encodeURIComponent(text);
    const img = await loadImage(src);
    if (!img) throw new Error("Could not generate QR code.");
    const c = document.createElement("canvas");
    c.width = px;
    c.height = px;
    c.getContext("2d").drawImage(img, 0, 0, px, px);
    return c.toDataURL("image/png");
  }

  function drawQrCard(ctx, qrImg, x, y, size, label) {
    const pad = 22;
    roundRect(ctx, x - pad, y - pad - 48, size + pad * 2, size + pad * 2 + 48, 28);
    ctx.fillStyle = "#fffaf2";
    ctx.fill();
    ctx.fillStyle = "#161311";
    ctx.font = "700 28px Outfit, Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(label, x + size / 2, y - 12);
    if (qrImg) ctx.drawImage(qrImg, x, y, size, size);
  }

  async function drawPoster(product, storeUrl) {
    const shopUrl = productPageUrl(product, storeUrl);
    const giveUrl = donatePageUrl(product, storeUrl);
    if (!shopUrl) throw new Error("Save the product first so it has a page link.");
    if (document.fonts && document.fonts.ready) {
      try { await document.fonts.ready; } catch (e) {}
    }
    const title = product.title || "Product";
    const price = formatPrice(product.unit_price_cents != null ? product.unit_price_cents : product.price_cents, product.currency);
    const wa = whatsappLabel();
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");

    const bg = ctx.createLinearGradient(0, 0, W, H);
    bg.addColorStop(0, "#1a1512");
    bg.addColorStop(0.45, "#241c16");
    bg.addColorStop(1, "#3a2a1c");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = "rgba(232,201,138,0.12)";
    ctx.beginPath();
    ctx.arc(W * 0.85, 80, 260, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#e8c98a";
    ctx.font = "600 26px Outfit, Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("SCAN TO SHOP OR GIVE", W / 2, 64);

    const photo = await loadImage(product.cover_image || ((product.images || [])[0] && product.images[0].url) || "");
    const photoH = 300;
    const photoY = 88;
    const photoX = 90;
    const photoW = W - 180;
    roundRect(ctx, photoX, photoY, photoW, photoH, 28);
    ctx.save();
    ctx.clip();
    ctx.fillStyle = "#fffaf2";
    ctx.fillRect(photoX, photoY, photoW, photoH);
    if (photo) {
      const scale = Math.min(photoW / photo.width, photoH / photo.height);
      const dw = photo.width * scale;
      const dh = photo.height * scale;
      ctx.drawImage(photo, photoX + (photoW - dw) / 2, photoY + (photoH - dh) / 2, dw, dh);
    }
    ctx.restore();
    ctx.strokeStyle = "rgba(232,201,138,0.45)";
    ctx.lineWidth = 3;
    roundRect(ctx, photoX, photoY, photoW, photoH, 28);
    ctx.stroke();

    ctx.fillStyle = "#fffaf2";
    ctx.font = "600 46px 'Cormorant Garamond', Georgia, serif";
    ctx.textAlign = "center";
    const lines = wrapText(ctx, title, W - 140);
    let y = 430;
    lines.forEach((line) => {
      ctx.fillText(line, W / 2, y);
      y += 50;
    });

    ctx.fillStyle = "#e8c98a";
    ctx.font = "700 42px Outfit, Segoe UI, sans-serif";
    ctx.fillText(price, W / 2, y + 6);
    y += 50;
    if (wa) {
      ctx.fillStyle = "#fffaf2";
      ctx.font = "600 28px Outfit, Segoe UI, sans-serif";
      ctx.fillText(wa, W / 2, y + 6);
      y += 42;
    }

    const shopQr = await makeQrDataUrl(shopUrl, QR);
    const giveQr = giveUrl ? await makeQrDataUrl(giveUrl, QR) : null;
    const shopImg = await loadImage(shopQr);
    const giveImg = giveQr ? await loadImage(giveQr) : null;
    const gap = 48;
    const pairW = giveImg ? QR * 2 + gap : QR;
    const leftX = (W - pairW) / 2;
    const qrY = Math.min(Math.max(y + 56, 620), 820);
    drawQrCard(ctx, shopImg, leftX, qrY, QR, "SHOP");
    if (giveImg) drawQrCard(ctx, giveImg, leftX + QR + gap, qrY, QR, "GIVE");

    let textY = qrY + QR + 56;
    ctx.textAlign = "center";
    ctx.fillStyle = "#fffaf2";
    ctx.font = "600 26px Outfit, Segoe UI, sans-serif";
    ctx.fillText("Shop link", W / 2, textY);
    textY += 36;
    ctx.fillStyle = "#e8c98a";
    ctx.font = "700 28px Outfit, Segoe UI, sans-serif";
    wrapChars(ctx, displayUrl(shopUrl), W - 100, 2).forEach((line) => {
      ctx.fillText(line, W / 2, textY);
      textY += 34;
    });
    if (giveUrl) {
      textY += 18;
      ctx.fillStyle = "#fffaf2";
      ctx.font = "600 26px Outfit, Segoe UI, sans-serif";
      ctx.fillText("Give / donate link", W / 2, textY);
      textY += 36;
      ctx.fillStyle = "#e8c98a";
      ctx.font = "700 26px Outfit, Segoe UI, sans-serif";
      wrapChars(ctx, displayUrl(giveUrl), W - 100, 3).forEach((line) => {
        ctx.fillText(line, W / 2, textY);
        textY += 32;
      });
    }
    ctx.fillStyle = "rgba(255,250,242,0.7)";
    ctx.font = "500 24px Outfit, Segoe UI, sans-serif";
    ctx.fillText("Message on WhatsApp if you want to talk first", W / 2, Math.min(textY + 40, H - 48));

    return canvas;
  }

  function downloadBlob(filename, blob) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  function downloadUrlFile(product, storeUrl) {
    const short = productPageUrl(product, storeUrl);
    const long = longPageUrl(product, storeUrl);
    const give = donatePageUrl(product, storeUrl);
    const price = formatPrice(product.unit_price_cents != null ? product.unit_price_cents : product.price_cents, product.currency);
    const body = [
      product.title || "Product",
      price,
      whatsappLabel(),
      "Shop short: " + short,
      "Shop full: " + long,
      give ? "Give / donate: " + give : "",
      "",
    ].filter(Boolean).join("\r\n");
    const slug = (product.slug || "product").replace(/[^\w-]+/g, "-");
    downloadBlob(slug + "-url.txt", new Blob([body], { type: "text/plain" }));
    return short;
  }

  async function downloadPoster(product, storeUrl) {
    const canvas = await drawPoster(product, storeUrl);
    const slug = (product.slug || "product").replace(/[^\w-]+/g, "-");
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error("Could not build the QR image."));
          return;
        }
        downloadBlob(slug + "-qr.png", blob);
        resolve(canvas);
      }, "image/png");
    });
  }

  global.ProductShare = {
    productPageUrl,
    longPageUrl,
    donatePageUrl,
    formatPrice,
    drawPoster,
    downloadUrlFile,
    downloadPoster,
  };
})(window);
