/* Floating WhatsApp + email help on the public store. */

(function () {
  const TOPICS = [
    { id: "product", label: "Question about a product" },
    { id: "order", label: "Order or payment problem" },
    { id: "shipping", label: "Shipping or delivery" },
    { id: "account", label: "Account or password" },
    { id: "other", label: "Something else" },
  ];

  function cfg() {
    return window.APP_CONFIG || {};
  }

  function productLine() {
    const p = window.STORE_CONTACT_PRODUCT;
    if (!p || !p.title) return "";
    const url = p.url || location.href;
    return "Product: " + p.title + (url ? "\nLink: " + url : "");
  }

  function messageFor(topicLabel) {
    const bits = [
      "Hello, I need help from the store.",
      "Problem: " + topicLabel,
    ];
    const product = productLine();
    if (product) bits.push(product);
    bits.push("Page: " + location.href);
    return bits.join("\n");
  }

  function openWhatsApp(text) {
    const num = String(cfg().WHATSAPP_NUMBER || "").replace(/\D/g, "");
    if (!num) return;
    window.open("https://wa.me/" + num + "?text=" + encodeURIComponent(text), "_blank", "noopener");
  }

  function openEmail(text) {
    const email = cfg().CONTACT_EMAIL || "";
    if (!email) return;
    const subject = "Store help";
    window.location.href = "mailto:" + encodeURIComponent(email) + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(text);
  }

  function closePanel() {
    const panel = document.getElementById("store-help-panel");
    if (panel) panel.classList.add("hidden");
  }

  function openPanel(channel) {
    const panel = document.getElementById("store-help-panel");
    const title = document.getElementById("store-help-title");
    const list = document.getElementById("store-help-topics");
    if (!panel || !list) return;
    title.textContent = channel === "email"
      ? "Email us — what is the problem?"
      : "WhatsApp — what is the problem?";
    list.innerHTML = TOPICS.map((t) =>
      `<button type="button" class="store-help-topic" data-topic="${t.id}">${t.label}</button>`
    ).join("");
    if (window.STORE_CONTACT_PRODUCT && window.STORE_CONTACT_PRODUCT.title) {
      list.insertAdjacentHTML("afterbegin",
        `<button type="button" class="store-help-topic" data-topic="this-product">This product: ${escapeHtml(window.STORE_CONTACT_PRODUCT.title)}</button>`
      );
    }
    list.querySelectorAll(".store-help-topic").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-topic");
        const label = id === "this-product"
          ? "Question about this product"
          : (TOPICS.find((t) => t.id === id) || {}).label || "Help";
        const text = messageFor(label);
        closePanel();
        if (channel === "email") openEmail(text);
        else openWhatsApp(text);
      });
    });
    panel.classList.remove("hidden");
  }

  function mount() {
    if (document.getElementById("store-help-dock")) return;
    const dock = document.createElement("div");
    dock.id = "store-help-dock";
    dock.innerHTML = `
      <button type="button" class="store-help-fab store-help-wa" id="store-help-wa" title="WhatsApp">WhatsApp</button>
      <button type="button" class="store-help-fab store-help-mail" id="store-help-mail" title="Email">Email</button>
      <div id="store-help-panel" class="store-help-panel hidden">
        <div class="store-help-panel-head">
          <strong id="store-help-title">What is the problem?</strong>
          <button type="button" class="store-help-close" id="store-help-close" aria-label="Close">&times;</button>
        </div>
        <p class="text-muted" style="margin:0 0 10px;font-size:13px;">Pick a topic. We will open a message to us with the details.</p>
        <div id="store-help-topics"></div>
      </div>
    `;
    document.body.appendChild(dock);
    document.getElementById("store-help-wa").addEventListener("click", () => openPanel("whatsapp"));
    document.getElementById("store-help-mail").addEventListener("click", () => openPanel("email"));
    document.getElementById("store-help-close").addEventListener("click", closePanel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
