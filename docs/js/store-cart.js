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

function storeAccountHref(nextPath) {
  const next = nextPath || (location.pathname.split("/").pop() || "store.html") + (location.search || "");
  return "store-account.html?next=" + encodeURIComponent(next);
}

async function getStoreCustomer() {
  try {
    const res = await storeFetch("/api/store/auth/me");
    if (!res.ok) return null;
    const data = await res.json();
    const customer = data.customer || null;
    if (customer) customer.unread_notices = data.unread_notices || 0;
    return customer;
  } catch (e) {
    return null;
  }
}

async function mountStoreAccountNav() {
  const inner = document.querySelector(".store-topbar-inner");
  if (!inner || document.getElementById("store-account-nav")) return;
  const customer = await getStoreCustomer();
  const nav = document.createElement("div");
  nav.id = "store-account-nav";
  nav.className = "store-account-nav";
  if (customer) {
    nav.innerHTML = `<a href="store-account.html">Account${customer.unread_notices ? `<span class="notice-badge">${customer.unread_notices}</span>` : ""}</a><a href="store-account.html">Orders</a>`;
  } else {
    nav.innerHTML = `<a class="store-signin-link" href="${storeAccountHref()}">Sign in</a>`;
  }
  const cart = inner.querySelector(".store-cart-link");
  if (cart) inner.insertBefore(nav, cart);
  else inner.appendChild(nav);
}

document.addEventListener("DOMContentLoaded", function () {
  updateStoreCartBadge();
  mountStoreAccountNav();
});
