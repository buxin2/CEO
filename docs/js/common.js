/* Shared helpers used across admin pages */

function apiUrl(path) {
  const base = getApiBaseUrl();
  const normalized = path.startsWith("/") ? path : "/" + path;
  return base + normalized;
}

function pageUrl(path) {
  const normalized = path.startsWith("/") ? path.slice(1) : path;
  return normalized;
}

function getApiBaseUrl() {
  const base = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "";
  if (!base) {
    console.error("APP_CONFIG.API_BASE_URL is missing. Check js/config.js on GitHub Pages.");
  }
  return base.replace(/\/$/, "");
}

async function fetchWithRetry(url, options, retryConfig = {}) {
  const retries = typeof retryConfig.retries === "number" ? retryConfig.retries : 2;
  const retryDelayMs = typeof retryConfig.retryDelayMs === "number" ? retryConfig.retryDelayMs : 1500;
  const onRetry = retryConfig.onRetry;
  const retryStatuses = retryConfig.retryStatuses || [502, 503, 504];
  let lastError;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, options);
      if (retryStatuses.includes(response.status) && attempt < retries) {
        if (onRetry) onRetry(attempt + 1, retries + 1, "server_sleeping");
        await new Promise((r) => setTimeout(r, retryDelayMs));
        continue;
      }
      return response;
    } catch (err) {
      lastError = err;
      if (attempt < retries) {
        if (onRetry) onRetry(attempt + 1, retries + 1, "network");
        await new Promise((r) => setTimeout(r, retryDelayMs));
      }
    }
  }
  throw lastError || new Error("Request failed");
}

function taskLinkForToken(token) {
  return new URL(pageUrl("task.html?token=" + encodeURIComponent(token)), window.location.href).href;
}

function groupLinkForToken(token) {
  return new URL(pageUrl("group.html?token=" + encodeURIComponent(token)), window.location.href).href;
}

function groupAdminPageUrl(token, companyId) {
  const query =
    "group.html?token=" +
    encodeURIComponent(token) +
    "&company_id=" +
    encodeURIComponent(companyId);
  return new URL(pageUrl(query), window.location.href).href;
}

async function groupApiRequest(url, employeeToken, options = {}) {
  const retries = options.retries;
  const retryDelayMs = options.retryDelayMs;
  const onRetry = options.onRetry;
  const opts = Object.assign({ credentials: "include", headers: {} }, options);
  delete opts.retries;
  delete opts.retryDelayMs;
  delete opts.onRetry;
  if (employeeToken) {
    opts.headers["X-Employee-Token"] = employeeToken;
  }
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetchWithRetry(apiUrl(url), opts, { retries, retryDelayMs, onRetry });
  } catch (e) {
    throw new Error("Cannot reach the API server. Wait a moment and try again.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    data = null;
  }

  if (!response.ok) {
    const message = (data && data.error) ? data.error : "Something went wrong. Please try again.";
    throw new Error(message);
  }

  return data;
}

async function apiRequest(url, options = {}) {
  const retries = options.retries;
  const retryDelayMs = options.retryDelayMs;
  const onRetry = options.onRetry;
  const opts = Object.assign({ credentials: "include", headers: {} }, options);
  delete opts.retries;
  delete opts.retryDelayMs;
  delete opts.onRetry;
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetchWithRetry(apiUrl(url), opts, { retries, retryDelayMs, onRetry });
  } catch (e) {
    throw new Error(
      "Cannot reach the API server. If this is your first login, wait 30 seconds for Render to wake up, then try again."
    );
  }

  if (response.status === 401) {
    window.location.href = pageUrl("login.html");
    throw new Error("Not authenticated");
  }

  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    data = null;
  }

  if (!response.ok) {
    const message = (data && data.error) ? data.error : "Something went wrong. Please try again.";
    throw new Error(message);
  }

  return data;
}

/** Ping Render until the API responds (free tier cold start can take ~60s). */
async function wakeApiServer(onProgress) {
  return apiRequest("/api/health", {
    retries: 25,
    retryDelayMs: 2500,
    onRetry: (attempt, total) => {
      if (onProgress) onProgress(attempt, total);
    },
  });
}

function showToast(message) {
  let toast = document.getElementById("global-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "global-toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(toast._hideTimer);
  toast._hideTimer = setTimeout(() => {
    toast.classList.remove("visible");
  }, 2200);
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("open");
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("open");
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDateRange(startIso, endIso) {
  const start = new Date(startIso + "T00:00:00");
  const end = new Date(endIso + "T00:00:00");
  const opts = { month: "long", day: "numeric" };
  const startStr = start.toLocaleDateString("en-US", opts);
  const endStr = end.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  return `${startStr} \u2013 ${endStr}`;
}

function formatShortDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function formatCurrency(amount) {
  const n = Number(amount) || 0;
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

function formatDisplayDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  const el = document.createElement("textarea");
  el.value = text;
  el.style.position = "fixed";
  el.style.opacity = "0";
  document.body.appendChild(el);
  el.select();
  document.execCommand("copy");
  document.body.removeChild(el);
  return Promise.resolve();
}

function initMobileNav() {
  const toggle = document.getElementById("mobile-nav-toggle");
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");
  if (!toggle || !sidebar) return;

  toggle.addEventListener("click", () => {
    sidebar.classList.toggle("mobile-open");
    if (backdrop) backdrop.classList.toggle("visible");
  });

  if (backdrop) {
    backdrop.addEventListener("click", () => {
      sidebar.classList.remove("mobile-open");
      backdrop.classList.remove("visible");
    });
  }
}

async function handleLogout() {
  try {
    const data = await apiRequest("/api/logout", { method: "POST" });
    window.location.href = data.redirect || pageUrl("login.html");
  } catch (e) {
    window.location.href = pageUrl("login.html");
  }
}

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

document.addEventListener("DOMContentLoaded", () => {
  initMobileNav();
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", handleLogout);
  }
});
