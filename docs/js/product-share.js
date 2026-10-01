/* Product page URL + QR advertising poster (admin Products). */

(function (global) {
  const W = 1080;
  const H = 1680;
  const QR = 720;

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
    if (product && product.product_url) return product.product_url;
    const base = String(storeUrl || "").replace(/store\.html.*$/i, "");
    const slug = (product && product.slug) || "";
    if (base && slug) return base + "product.html?p=" + encodeURIComponent(slug);
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

  async function makeQrDataUrl(text) {
    if (global.QRCode && typeof global.QRCode.toDataURL === "function") {
      return global.QRCode.toDataURL(text, {
        width: QR,
        margin: 1,
        color: { dark: "#161311", light: "#fffaf2" },
        errorCorrectionLevel: "M",
      });
    }
    const src = "https://api.qrserver.com/v1/create-qr-code/?size=" + QR + "x" + QR + "&margin=8&data=" + encodeURIComponent(text);
    const img = await loadImage(src);
    if (!img) throw new Error("Could not generate QR code.");
    const c = document.createElement("canvas");
    c.width = QR;
    c.height = QR;
    c.getContext("2d").drawImage(img, 0, 0, QR, QR);
    return c.toDataURL("image/png");
  }

  async function drawPoster(product, storeUrl) {
    const url = productPageUrl(product, storeUrl);
    if (!url) throw new Error("Save the product first so it has a page link.");
    if (document.fonts && document.fonts.ready) {
      try { await document.fonts.ready; } catch (e) {}
    }
    const title = product.title || "Product";
    const price = formatPrice(product.unit_price_cents != null ? product.unit_price_cents : product.price_cents, product.currency);
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
    ctx.font = "600 28px Outfit, Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("SCAN THIS QR CODE", W / 2, 78);

    const photo = await loadImage(product.cover_image || ((product.images || [])[0] && product.images[0].url) || "");
    const photoH = 300;
    const photoY = 110;
    const photoX = 90;
    const photoW = W - 180;
    roundRect(ctx, photoX, photoY, photoW, photoH, 28);
    ctx.save();
    ctx.clip();
    ctx.fillStyle = "#2a221c";
    ctx.fillRect(photoX, photoY, photoW, photoH);
    if (photo) {
      const scale = Math.max(photoW / photo.width, photoH / photo.height);
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
    ctx.font = "600 54px 'Cormorant Garamond', Georgia, serif";
    ctx.textAlign = "center";
    const lines = wrapText(ctx, title, W - 140);
    lines.forEach((line, i) => {
      ctx.fillText(line, W / 2, 470 + i * 62);
    });

    ctx.fillStyle = "#e8c98a";
    ctx.font = "700 48px Outfit, Segoe UI, sans-serif";
    ctx.fillText(price, W / 2, 470 + lines.length * 62 + 18);

    const qrUrl = await makeQrDataUrl(url);
    const qrImg = await loadImage(qrUrl);
    const qrX = (W - QR) / 2;
    const qrY = 700;
    roundRect(ctx, qrX - 28, qrY - 28, QR + 56, QR + 56, 36);
    ctx.fillStyle = "#fffaf2";
    ctx.fill();
    if (qrImg) ctx.drawImage(qrImg, qrX, qrY, QR, QR);

    ctx.fillStyle = "#fffaf2";
    ctx.font = "600 36px Outfit, Segoe UI, sans-serif";
    ctx.fillText("Open the camera · scan to shop", W / 2, qrY + QR + 88);

    ctx.fillStyle = "rgba(255,250,242,0.72)";
    ctx.font = "400 22px Outfit, Segoe UI, sans-serif";
    const urlLines = wrapText(ctx, url, W - 120);
    urlLines.forEach((line, i) => {
      ctx.fillText(line, W / 2, qrY + QR + 130 + i * 30);
    });

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
    const url = productPageUrl(product, storeUrl);
    const price = formatPrice(product.unit_price_cents != null ? product.unit_price_cents : product.price_cents, product.currency);
    const body = [product.title || "Product", price, url, ""].join("\r\n");
    const slug = (product.slug || "product").replace(/[^\w-]+/g, "-");
    downloadBlob(slug + "-url.txt", new Blob([body], { type: "text/plain" }));
    return url;
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
    formatPrice,
    drawPoster,
    downloadUrlFile,
    downloadPoster,
  };
})(window);
