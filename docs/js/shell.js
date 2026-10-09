(function () {
  const ICONS = {
    grid: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
    building: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M4 21h16M14 21v-8h6v8M8 8h2M8 12h2M8 16h2"/></svg>',
    users: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    box: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.3 7 12 12l8.7-5M12 22V12"/></svg>',
    truck: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11h2"/><path d="M15 18h4l3-5v-3h-7v8z"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/></svg>',
    receipt: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2-3-2z"/><path d="M8 10h8M8 14h6"/></svg>',
    user: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a8 8 0 0 1 16 0v1"/></svg>',
    spark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v4M12 17v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M3 12h4M17 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/></svg>',
    brain: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5a4 4 0 0 0-7 3 4 4 0 0 0 0 8v3h7M12 5a4 4 0 0 1 7 3 4 4 0 0 1 0 8v3h-7"/><path d="M12 5v16"/></svg>',
    lamp: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18h6M10 22h4M12 2a7 7 0 0 1 4 12c-.7.7-1 1.5-1 2.5V18H9v-1.5c0-1-.3-1.8-1-2.5A7 7 0 0 1 12 2z"/></svg>',
    cal: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
    news: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h12v16H4z"/><path d="M16 8h4v12a2 2 0 0 1-2 2H6"/><path d="M7 8h6M7 12h6M7 16h4"/></svg>',
    list: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
    chart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V4M4 20h16"/><path d="M8 16v-5M12 16V8M16 16v-8"/></svg>',
    logout: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></svg>',
    card: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg>',
    chevron: '<svg class="nav-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>',
  };

  function href(path) {
    return typeof pageUrl === "function" ? pageUrl(path) : path;
  }

  function currentPage() {
    const file = (location.pathname.split("/").pop() || "dashboard.html").split("?")[0] || "dashboard.html";
    const view = new URLSearchParams(location.search).get("view") || "";
    const hash = (location.hash || "").replace("#", "");
    return { file, view, hash, search: location.search || "" };
  }

  function itemMatches(item, loc) {
    const keys = item.match || (item.href ? [item.href] : []);
    return keys.some((raw) => {
      const [pathPart, hashPart] = String(raw).split("#");
      const [file, qs] = pathPart.split("?");
      if (file && file !== loc.file) return false;
      if (qs) {
        const want = new URLSearchParams(qs).get("view") || "";
        if ((loc.view || "") !== want) return false;
      } else if (file === "ai-assistant.html" && loc.file === "ai-assistant.html") {
        if (item.id === "ai-chat" && loc.view) return false;
      } else if (file === "communities.html" && loc.file === "communities.html") {
        if (item.id === "communities-all" && loc.view === "members") return false;
        if (item.id === "community-members" && loc.view !== "members") return false;
      } else if (file === "dashboard.html" && loc.file === "dashboard.html") {
        if (hashPart === "companies") return loc.hash === "companies";
        if (item.id === "dashboard") return loc.hash !== "companies";
      }
      if (hashPart) return loc.hash === hashPart;
      return true;
    });
  }

  function collectActive(loc) {
    const active = {};
    (window.NAV_GROUPS || []).forEach((group) => {
      (group.items || []).forEach((item) => {
        if (item.children) {
          item.children.forEach((child) => {
            if (itemMatches(child, loc)) {
              active[child.id] = true;
              active[item.id] = true;
              active[group.id] = true;
            }
          });
        } else if (itemMatches(item, loc)) {
          active[item.id] = true;
          active[group.id] = true;
        }
      });
    });
    return active;
  }

  function loadOpen() {
    try {
      const raw = JSON.parse(localStorage.getItem("ui-nav-open") || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (e) {
      return [];
    }
  }

  function saveOpen(ids) {
    try { localStorage.setItem("ui-nav-open", JSON.stringify(ids)); } catch (e) {}
  }

  function linkHtml(item, active, extraClass) {
    const on = active[item.id] ? " active" : "";
    return `<a class="sidebar-link${on}${extraClass ? " " + extraClass : ""}" href="${href(item.href)}" data-nav="${item.id}" title="${item.label}">${ICONS[item.icon] || ""}<span class="sidebar-link-text">${item.label}</span></a>`;
  }

  function renderSidebar(active, openIds) {
    const groups = window.NAV_GROUPS || [];
    const nav = groups.map((group) => {
      const items = (group.items || []).map((item) => {
        if (item.children) {
          const isOpen = openIds.indexOf(item.id) >= 0 || !!active[item.id];
          const parentOn = active[item.id] ? " active-parent" : "";
          const kids = item.children.map((c) => linkHtml(c, active, "nav-sublink")).join("");
          return `<div class="nav-drop${isOpen ? " open" : ""}${parentOn}" data-drop="${item.id}">
            <button type="button" class="sidebar-link nav-drop-btn" aria-expanded="${isOpen}" title="${item.label}">
              ${ICONS[item.icon] || ICONS.grid}<span class="sidebar-link-text">${item.label}</span>${ICONS.chevron}
            </button>
            <div class="nav-sub">${kids}</div>
          </div>`;
        }
        return linkHtml(item, active);
      }).join("");
      return `<div class="sidebar-group-label">${group.label}</div>${items}`;
    }).join("");

    return `
      <div class="sidebar-brand-row">
        <div class="sidebar-brand">My Management System</div>
        <button type="button" class="sidebar-collapse-btn" id="sidebar-collapse-btn" aria-label="Collapse sidebar">${ICONS.grid}</button>
      </div>
      <nav class="sidebar-nav">${nav}</nav>
      <div class="sidebar-footer">
        <div class="sidebar-user">
          <span class="ui-avatar" id="sidebar-avatar">A</span>
          <span class="sidebar-link-text"><strong id="sidebar-user-name">Admin</strong><span class="text-muted" style="display:block;font-size:12px;">Signed in</span></span>
        </div>
        <button class="sidebar-link" id="logout-btn" type="button">${ICONS.logout}<span class="sidebar-link-text">Logout</span></button>
      </div>`;
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("ui-theme", theme); } catch (e) {}
    const btn = document.getElementById("theme-toggle-btn");
    if (btn) btn.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
  }

  function ensureChrome() {
    if (!document.getElementById("sidebar-backdrop")) {
      const bd = document.createElement("div");
      bd.className = "sidebar-backdrop";
      bd.id = "sidebar-backdrop";
      document.body.insertBefore(bd, document.body.firstChild);
    }
    if (!document.querySelector(".mobile-navbar")) {
      const bar = document.createElement("div");
      bar.className = "mobile-navbar";
      bar.innerHTML = `<button class="hamburger-btn" id="mobile-nav-toggle" aria-label="Open menu">☰</button>
        <div class="brand">My Management System</div>
        <button type="button" class="icon-btn" id="theme-toggle-btn" aria-label="Toggle color theme">◐</button>`;
      document.body.insertBefore(bar, document.body.firstChild);
    } else if (!document.getElementById("theme-toggle-btn")) {
      const nav = document.querySelector(".mobile-navbar");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "icon-btn";
      btn.id = "theme-toggle-btn";
      btn.setAttribute("aria-label", "Toggle color theme");
      btn.textContent = "◐";
      nav.appendChild(btn);
    }
    if (!document.getElementById("sidebar")) {
      const shell = document.querySelector(".app-shell") || document.body;
      const aside = document.createElement("aside");
      aside.className = "sidebar";
      aside.id = "sidebar";
      shell.insertBefore(aside, shell.firstChild);
    }
  }

  window.mountAdminShell = function (force) {
    if (document.body.dataset.adminShell === "1" && !force) return;
    document.body.dataset.adminShell = "1";
    ensureChrome();

    const savedTheme = (function () {
      try { return localStorage.getItem("ui-theme") || "light"; } catch (e) { return "light"; }
    })();
    applyTheme(savedTheme);

    const loc = currentPage();
    const active = collectActive(loc);
    let openIds = loadOpen();
    Object.keys(active).forEach((id) => {
      if (openIds.indexOf(id) < 0) openIds.push(id);
    });

    const sidebar = document.getElementById("sidebar");
    sidebar.innerHTML = renderSidebar(active, openIds);

    sidebar.querySelectorAll(".nav-drop-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const wrap = btn.closest(".nav-drop");
        wrap.classList.toggle("open");
        btn.setAttribute("aria-expanded", wrap.classList.contains("open") ? "true" : "false");
        const ids = Array.from(sidebar.querySelectorAll(".nav-drop.open")).map((el) => el.getAttribute("data-drop"));
        saveOpen(ids);
      });
    });

    try {
      if (localStorage.getItem("ui-sidebar") === "collapsed") {
        document.body.classList.add("sidebar-collapsed");
      }
    } catch (e) {}

    const collapse = document.getElementById("sidebar-collapse-btn");
    if (collapse) {
      collapse.addEventListener("click", () => {
        document.body.classList.toggle("sidebar-collapsed");
        try {
          localStorage.setItem("ui-sidebar", document.body.classList.contains("sidebar-collapsed") ? "collapsed" : "open");
        } catch (e) {}
      });
    }

    const themeBtn = document.getElementById("theme-toggle-btn");
    if (themeBtn && !themeBtn.dataset.bound) {
      themeBtn.dataset.bound = "1";
      themeBtn.addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        applyTheme(next);
      });
    }

    const logout = document.getElementById("logout-btn");
    if (logout && !logout.dataset.bound) {
      logout.dataset.bound = "1";
      logout.addEventListener("click", handleLogout);
    }

    apiRequest("/api/me").then((me) => {
      const name = (me && (me.name || me.email)) || "Admin";
      const el = document.getElementById("sidebar-user-name");
      if (el) el.textContent = String(name).split("@")[0];
      const av = document.getElementById("sidebar-avatar");
      if (av) av.textContent = String(name).charAt(0).toUpperCase();
    }).catch(() => {});
  };

  window.uiInitials = function (name) {
    const parts = String(name || "?").trim().split(/\s+/);
    return ((parts[0] || "?").charAt(0) + (parts[1] ? parts[1].charAt(0) : "")).toUpperCase();
  };

  window.uiPeopleLabel = function (n) {
    const count = Number(n) || 0;
    return count === 1 ? "1 person" : count + " people";
  };

  window.uiStatusChip = function (kind, label) {
    return `<span class="status-chip ${kind}">${label}</span>`;
  };

  window.uiEmptyState = function (text, actionHtml) {
    return `<div class="empty-lite"><p>${text}</p>${actionHtml || ""}</div>`;
  };

  function boot() {
    if (!document.getElementById("sidebar") && !document.querySelector(".app-shell")) return;
    window.mountAdminShell();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
  window.addEventListener("hashchange", () => window.mountAdminShell(true));
})();
