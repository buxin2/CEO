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
  };

  function href(path) {
    return typeof pageUrl === "function" ? pageUrl(path) : path;
  }

  function link(path, key, label, active) {
    const isActive = active === key ? " active" : "";
    return `<a class="sidebar-link${isActive}" href="${href(path)}" data-nav="${key}" title="${label}">${ICONS[key] || ICONS.grid}<span class="sidebar-link-text">${label}</span></a>`;
  }

  function renderSidebar(active) {
    return `
      <div class="sidebar-brand-row">
        <div class="sidebar-brand">My Management System</div>
        <button type="button" class="sidebar-collapse-btn" id="sidebar-collapse-btn" aria-label="Collapse sidebar">${ICONS.grid}</button>
      </div>
      <nav class="sidebar-nav">
        <div class="sidebar-group-label">Work</div>
        ${link("dashboard.html", "grid", "Dashboard", active)}
        ${link("dashboard.html#companies", "building", "Companies", active)}
        ${link("communities.html", "users", "Communities", active)}
        ${link("admin-store.html", "box", "Products", active)}
        ${link("admin-shipping.html", "truck", "Shipping", active)}
        ${link("excel-lists.html", "list", "Excel lists", active)}
        ${link("reports.html", "chart", "Reports", active)}
        <div class="sidebar-group-label">Store</div>
        ${link("admin-store-orders.html", "receipt", "Store Orders", active)}
        ${link("admin-store-users.html", "user", "Store Users", active)}
        <div class="sidebar-group-label">Personal</div>
        ${link("ai-assistant.html", "spark", "AI Assistant", active)}
        ${link("mentor.html", "brain", "Mentor", active)}
        ${link("ideas.html", "lamp", "My Ideas", active)}
        ${link("timetable.html", "cal", "My Timetable", active)}
        ${link("news.html", "news", "News", active)}
      </nav>
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

  window.mountAdminShell = function (active) {
    const savedTheme = (function () {
      try { return localStorage.getItem("ui-theme") || "light"; } catch (e) { return "light"; }
    })();
    applyTheme(savedTheme);

    const sidebar = document.getElementById("sidebar");
    if (sidebar) sidebar.innerHTML = renderSidebar(active);

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
    if (themeBtn) {
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
})();
