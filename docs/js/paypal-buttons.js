/* PayPal JS SDK — Smart Buttons (PayPal + debit/credit card on the page). */

(function (global) {
  let loading = null;

  function sdkSrc(clientId, currency) {
    const params = new URLSearchParams({
      "client-id": clientId,
      currency: currency || "USD",
      intent: "capture",
      components: "buttons",
      "enable-funding": "card,paylater",
    });
    return "https://www.paypal.com/sdk/js?" + params.toString();
  }

  function loadSdk(clientId, currency) {
    if (!clientId) return Promise.reject(new Error("PayPal is not configured."));
    if (global.paypal && global.__paypalSdkClientId === clientId && global.__paypalSdkCurrency === (currency || "USD")) {
      return Promise.resolve(global.paypal);
    }
    if (loading) return loading;
    const existing = document.getElementById("paypal-sdk");
    if (existing) existing.remove();
    loading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.id = "paypal-sdk";
      script.src = sdkSrc(clientId, currency);
      script.onload = function () {
        loading = null;
        if (!global.paypal) {
          reject(new Error("PayPal did not load."));
          return;
        }
        global.__paypalSdkClientId = clientId;
        global.__paypalSdkCurrency = currency || "USD";
        resolve(global.paypal);
      };
      script.onerror = function () {
        loading = null;
        reject(new Error("Could not load PayPal checkout."));
      };
      document.head.appendChild(script);
    });
    return loading;
  }

  function renderButtons(containerSelector, handlers) {
    handlers = handlers || {};
    const el = document.querySelector(containerSelector);
    if (!el) return Promise.resolve(null);
    el.innerHTML = "";
    return global.paypal.Buttons({
      style: {
        layout: "vertical",
        color: "gold",
        shape: "rect",
        label: "paypal",
      },
      createOrder: handlers.createOrder,
      onApprove: handlers.onApprove,
      onCancel: handlers.onCancel,
      onError: handlers.onError,
    }).render(containerSelector);
  }

  global.PaypalCheckoutUi = { loadSdk: loadSdk, renderButtons: renderButtons };
})(window);
