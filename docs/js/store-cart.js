/* Shared cart + money helpers for the public store */

const STORE_CART_KEY = "mms_store_cart";

function money(cents, currency) {
  const n = (Number(cents) || 0) / 100;
  const cur = currency || "USD";
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: cur }).format(n);
  } catch (e) {
    return n.toFixed(2) + " " + cur;
  }
}

function getStoreCart() {
  try {
    return JSON.parse(localStorage.getItem(STORE_CART_KEY) || "[]");
  } catch (e) {
    return [];
  }
}

function saveStoreCart(items) {
  localStorage.setItem(STORE_CART_KEY, JSON.stringify(items || []));
  updateStoreCartBadge();
}

function cartItemKey(item) {
  return item.product_id + "::" + JSON.stringify(item.options || {});
}

function addToStoreCart(item) {
  const cart = getStoreCart();
  const key = cartItemKey(item);
  const existing = cart.find((c) => cartItemKey(c) === key);
  if (existing) {
    existing.quantity += item.quantity || 1;
  } else {
    cart.push(item);
  }
  saveStoreCart(cart);
}

function updateStoreCartBadge() {
  const el = document.getElementById("store-cart-count");
  if (!el) return;
  const count = getStoreCart().reduce((s, i) => s + (i.quantity || 0), 0);
  el.textContent = count;
  el.style.display = count ? "flex" : "none";
}

function storeFetch(path, options) {
  return fetch(apiUrl(path), Object.assign({ credentials: "include" }, options || {}));
}

document.addEventListener("DOMContentLoaded", updateStoreCartBadge);
