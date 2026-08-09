(function () {
  let currentDate = new Date();
  let dashboardData = null;
  let companies = [];
  let activeView = "today";
  let editingDate = null;

  const CATEGORY_OPTIONS = [
    "work", "business", "development", "meal", "break", "exercise",
    "personal", "planning", "sleep", "communication", "meeting", "learning", "travel",
  ];

  const LINK_OPTIONS = [
    { value: "none", label: "None" },
    { value: "company", label: "Company dashboard" },
    { value: "company_group", label: "Company group" },
    { value: "company_tasks", label: "Company tasks" },
    { value: "company_earnings", label: "Company earnings" },
    { value: "dashboard", label: "Main dashboard" },
    { value: "ai_assistant", label: "AI Assistant" },
  ];

  function isoDate(d) {
    return d.toISOString().slice(0, 10);
  }

  function formatLongDate(iso) {
    const d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  }

  function timeToInput(t) {
    return (t || "09:00").slice(0, 5);
  }

  function needsCompany(linkType) {
    return ["company", "company_group", "company_tasks", "company_earnings"].includes(linkType);
  }

  async function loadCompanies() {
    try {
      companies = await apiRequest("/api/companies");
    } catch (e) {
      companies = [];
    }
    const opts = companies.map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
    document.getElementById("item-company-id").innerHTML = opts;
    document.getElementById("edit-item-company-id").innerHTML = opts;
  }

  function fillSelectOptions(selectEl, options, selected) {
    selectEl.innerHTML = options.map((o) =>
      `<option value="${o.value}" ${o.value === selected ? "selected" : ""}>${escapeHtml(o.label)}</option>`
    ).join("");
  }

  async function loadDashboard(dateIso) {
    dashboardData = await apiRequest(`/api/planner/dashboard?date=${encodeURIComponent(dateIso)}`);
    document.getElementById("personal-notes").value = dashboardData.personal_notes || "";
    document.getElementById("timetable-date-label").textContent = formatLongDate(dashboardData.date);
    renderGoalsInline(dashboardData.goals);
    renderProgress(dashboardData.timetable.progress);
    renderTimeline(document.getElementById("timetable-timeline"), dashboardData.timetable.items, dashboardData.date);
    renderDailySummary(dashboardData.timetable.summary);
    editingDate = dashboardData.date;
  }

  function renderProgress(prog) {
    const p = prog || { total: 0, completed: 0, completion_pct: 0 };
    document.getElementById("progress-label").textContent = `${p.completed} / ${p.total} completed (${p.completion_pct}%)`;
    const fill = document.getElementById("progress-fill");
    fill.style.width = p.completion_pct + "%";
    fill.classList.toggle("success", p.completion_pct >= 100);
  }

  function renderGoalsInline(goals) {
    const el = document.getElementById("goals-inline");
    const monthName = new Date(dashboardData.date + "T12:00:00").toLocaleDateString("en-US", { month: "long" });
    el.innerHTML = `
      <div class="goal-panel card">
        <h3 class="section-title">&#127919; ${monthName} Goals</h3>
        ${renderGoalList(goals.monthly, "monthly")}
        <button type="button" class="btn btn-ghost btn-sm" onclick="addGoalPrompt('monthly')">+ Add goal</button>
      </div>
      <div class="goal-panel card">
        <h3 class="section-title">&#127919; This Week</h3>
        ${renderGoalList(goals.weekly, "weekly")}
        <button type="button" class="btn btn-ghost btn-sm" onclick="addGoalPrompt('weekly')">+ Add goal</button>
      </div>
      <div class="goal-panel card">
        <h3 class="section-title">&#127919; Today</h3>
        ${renderGoalList(goals.daily, "daily")}
        <button type="button" class="btn btn-ghost btn-sm" onclick="addGoalPrompt('daily')">+ Add goal</button>
      </div>`;
  }

  function renderGoalList(list, scope) {
    if (!list || !list.length) {
      return `<p class="text-muted">No goals yet.</p>`;
    }
    return `<ul class="goal-list">${list.map((g) => `
      <li class="goal-row ${g.completed ? "done" : ""}">
        <label>
          <input type="checkbox" ${g.completed ? "checked" : ""} onchange="toggleGoal(${g.id}, this.checked)">
          <span>${escapeHtml(g.title)}</span>
        </label>
        <button type="button" class="btn btn-ghost btn-sm" onclick="deleteGoal(${g.id})">Delete</button>
      </li>`).join("")}</ul>`;
  }

  function renderTimeline(container, items, dateIso) {
    if (!items || !items.length) {
      container.innerHTML = `<div class="empty-state"><p>No timetable items yet. Use <strong>AI: Create Schedule</strong> or add items manually.</p></div>`;
      return;
    }
    container.innerHTML = items.map((item) => renderSlot(item, dateIso)).join("");
  }

  function renderSlot(item, dateIso) {
    const pri = item.priority || "medium";
    const linkBtn = item.link_url
      ? `<a class="btn btn-secondary btn-sm" href="${escapeHtml(item.link_url)}">${escapeHtml(item.link_label || "Open")}</a>`
      : "";
    return `
      <div class="timetable-slot ${item.completed ? "completed" : ""} priority-${pri}">
        <div class="timetable-time">${escapeHtml(item.start_time)} – ${escapeHtml(item.end_time)}</div>
        <div class="timetable-body">
          <div class="timetable-title-row">
            <label class="timetable-check">
              <input type="checkbox" ${item.completed ? "checked" : ""} onchange="toggleItemComplete(${item.id}, this.checked)">
              <strong>${escapeHtml(item.title)}</strong>
              <span class="badge badge-priority-${pri}">${pri}</span>
            </label>
            <div class="flex gap-8">
              <button type="button" class="btn btn-ghost btn-sm" onclick="openEditItem(${item.id})">Edit</button>
              <button type="button" class="btn btn-danger btn-sm" onclick="deleteItem(${item.id})">Delete</button>
            </div>
          </div>
          ${item.description ? `<p class="timetable-desc">${escapeHtml(item.description)}</p>` : ""}
          ${linkBtn ? `<div class="timetable-actions">${linkBtn}</div>` : ""}
        </div>
      </div>`;
  }

  function renderDailySummary(summary) {
    const card = document.getElementById("daily-summary-card");
    const body = document.getElementById("daily-summary-body");
    if (!summary || !summary.progress || summary.progress.total === 0) {
      card.classList.add("hidden");
      return;
    }
    card.classList.remove("hidden");
    const done = (summary.completed_titles || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("");
    const notDone = (summary.not_completed_titles || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("");
    body.innerHTML = `
      <p><strong>Progress:</strong> ${summary.progress.completed} / ${summary.progress.total} activities</p>
      ${done ? `<p><strong>Completed:</strong></p><ul>${done}</ul>` : ""}
      ${notDone ? `<p><strong>Not completed:</strong></p><ul>${notDone}</ul>` : ""}`;
  }

  async function loadTomorrow() {
    const tomorrow = dashboardData ? dashboardData.tomorrow : isoDate(new Date(Date.now() + 86400000));
    const data = await apiRequest(`/api/planner/timetable?date=${tomorrow}`);
    renderTimeline(document.getElementById("tomorrow-timeline"), data.items, tomorrow);
  }

  async function loadWeek() {
    const data = await apiRequest(`/api/planner/timetable?view=week&date=${dashboardData.date}`);
    const el = document.getElementById("week-overview");
    const days = data.days || {};
    const keys = Object.keys(days).sort();
    if (!keys.length) {
      el.innerHTML = "<p class=\"text-muted\">No items scheduled this week yet.</p>";
      return;
    }
    el.innerHTML = keys.map((day) => `
      <div class="card week-day-card">
        <h3 class="section-title">${formatLongDate(day)}</h3>
        <div class="timetable-timeline compact">${days[day].map((i) => renderSlot(i, day)).join("")}</div>
      </div>`).join("");
  }

  function renderGoalsFull() {
    const g = dashboardData.goals;
    document.getElementById("goals-full-view").innerHTML = `
      <div class="goal-panel card"><h3>Monthly</h3>${renderGoalList(g.monthly, "monthly")}</div>
      <div class="goal-panel card"><h3>Weekly</h3>${renderGoalList(g.weekly, "weekly")}</div>
      <div class="goal-panel card"><h3>Daily</h3>${renderGoalList(g.daily, "daily")}</div>`;
  }

  window.addGoalPrompt = async function (scope) {
    const title = prompt("Goal:");
    if (!title || !title.trim()) return;
    await apiRequest("/api/planner/goals", {
      method: "POST",
      body: JSON.stringify({ scope, title: title.trim(), date: dashboardData.date }),
    });
    await loadDashboard(dashboardData.date);
    if (activeView === "goals") renderGoalsFull();
  };

  window.toggleGoal = async function (id, completed) {
    await apiRequest(`/api/planner/goals/${id}`, {
      method: "PUT",
      body: JSON.stringify({ completed }),
    });
    await loadDashboard(dashboardData.date);
  };

  window.deleteGoal = async function (id) {
    if (!confirm("Delete this goal?")) return;
    await apiRequest(`/api/planner/goals/${id}`, { method: "DELETE" });
    await loadDashboard(dashboardData.date);
    if (activeView === "goals") renderGoalsFull();
  };

  window.toggleItemComplete = async function (id, completed) {
    await apiRequest(`/api/planner/timetable/${id}`, {
      method: "PUT",
      body: JSON.stringify({ completed }),
    });
    await loadDashboard(dashboardData.date);
  };

  window.openEditItem = function (id) {
    const item = dashboardData.timetable.items.find((i) => i.id === id);
    if (!item) return;
    document.getElementById("edit-item-id").value = item.id;
    document.getElementById("edit-item-start").value = timeToInput(item.start_time);
    document.getElementById("edit-item-end").value = timeToInput(item.end_time);
    document.getElementById("edit-item-title").value = item.title;
    document.getElementById("edit-item-description").value = item.description || "";
    document.getElementById("edit-item-priority").value = item.priority;
    fillSelectOptions(
      document.getElementById("edit-item-category"),
      CATEGORY_OPTIONS.map((c) => ({ value: c, label: c })),
      item.category
    );
    fillSelectOptions(document.getElementById("edit-item-link-type"), LINK_OPTIONS, item.link_type);
    document.getElementById("edit-item-link-label").value = item.link_label || "";
    document.getElementById("edit-item-company-wrap").classList.toggle("hidden", !needsCompany(item.link_type));
    if (item.link_company_id) {
      document.getElementById("edit-item-company-id").value = item.link_company_id;
    }
    document.getElementById("edit-item-error").classList.remove("visible");
    openModal("edit-item-modal");
  };

  window.deleteItem = async function (id) {
    if (!confirm("Delete this timetable item?")) return;
    await apiRequest(`/api/planner/timetable/${id}`, { method: "DELETE" });
    await loadDashboard(dashboardData.date);
    showToast("Item deleted");
  };

  function setupLinkTypeToggle(selectId, wrapId) {
    document.getElementById(selectId).addEventListener("change", (e) => {
      document.getElementById(wrapId).classList.toggle("hidden", !needsCompany(e.target.value));
    });
  }

  document.querySelectorAll(".timetable-tab").forEach((tab) => {
    tab.addEventListener("click", async () => {
      document.querySelectorAll(".timetable-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      activeView = tab.dataset.view;
      document.querySelectorAll(".timetable-view").forEach((v) => v.classList.add("hidden"));
      if (activeView === "today") {
        document.getElementById("view-today").classList.remove("hidden");
      } else if (activeView === "tomorrow") {
        document.getElementById("view-tomorrow").classList.remove("hidden");
        await loadTomorrow();
      } else if (activeView === "week") {
        document.getElementById("view-week").classList.remove("hidden");
        await loadWeek();
      } else {
        document.getElementById("view-goals").classList.remove("hidden");
        renderGoalsFull();
      }
    });
  });

  document.getElementById("save-notes-btn").addEventListener("click", async () => {
    const notes = document.getElementById("personal-notes").value;
    await apiRequest("/api/planner/settings", {
      method: "PUT",
      body: JSON.stringify({ personal_notes: notes }),
    });
    showToast("Notes saved for AI");
  });

  document.getElementById("add-item-btn").addEventListener("click", () => {
    fillSelectOptions(
      document.getElementById("item-category"),
      CATEGORY_OPTIONS.map((c) => ({ value: c, label: c })),
      "work"
    );
    document.getElementById("item-company-wrap").classList.add("hidden");
    openModal("add-item-modal");
  });

  document.getElementById("add-item-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("add-item-error");
    err.classList.remove("visible");
    const linkType = document.getElementById("item-link-type").value;
    const payload = {
      plan_date: editingDate,
      start_time: document.getElementById("item-start").value.slice(0, 5),
      end_time: document.getElementById("item-end").value.slice(0, 5),
      title: document.getElementById("item-title").value.trim(),
      description: document.getElementById("item-description").value.trim(),
      priority: document.getElementById("item-priority").value,
      category: document.getElementById("item-category").value,
      link_type: linkType,
      link_label: document.getElementById("item-link-label").value.trim(),
    };
    if (needsCompany(linkType)) {
      payload.link_company_id = Number(document.getElementById("item-company-id").value);
    }
    try {
      await apiRequest("/api/planner/timetable", { method: "POST", body: JSON.stringify(payload) });
      closeModal("add-item-modal");
      document.getElementById("add-item-form").reset();
      await loadDashboard(editingDate);
      showToast("Item added");
    } catch (ex) {
      err.textContent = ex.message;
      err.classList.add("visible");
    }
  });

  document.getElementById("edit-item-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("edit-item-error");
    err.classList.remove("visible");
    const id = document.getElementById("edit-item-id").value;
    const linkType = document.getElementById("edit-item-link-type").value;
    const payload = {
      start_time: document.getElementById("edit-item-start").value.slice(0, 5),
      end_time: document.getElementById("edit-item-end").value.slice(0, 5),
      title: document.getElementById("edit-item-title").value.trim(),
      description: document.getElementById("edit-item-description").value.trim(),
      priority: document.getElementById("edit-item-priority").value,
      category: document.getElementById("edit-item-category").value,
      link_type: linkType,
      link_label: document.getElementById("edit-item-link-label").value.trim(),
    };
    if (needsCompany(linkType)) {
      payload.link_company_id = Number(document.getElementById("edit-item-company-id").value);
    }
    try {
      await apiRequest(`/api/planner/timetable/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      closeModal("edit-item-modal");
      await loadDashboard(editingDate);
      showToast("Item updated");
    } catch (ex) {
      err.textContent = ex.message;
      err.classList.add("visible");
    }
  });

  document.getElementById("ai-generate-btn").addEventListener("click", async () => {
    const replace = dashboardData.timetable.items.length > 0;
    if (replace && !confirm("Replace today's timetable with a new AI-generated schedule?")) return;
    try {
      showToast("AI is building your schedule...");
      const res = await apiRequest("/api/planner/generate", {
        method: "POST",
        body: JSON.stringify({
          date: dashboardData.date,
          replace: replace,
          confirmed: replace,
        }),
        retries: 10,
        retryDelayMs: 2000,
      });
      if (res.needs_confirmation) {
        if (confirm(res.message)) {
          await apiRequest("/api/planner/generate", {
            method: "POST",
            body: JSON.stringify({ date: dashboardData.date, replace: true, confirmed: true }),
          });
        }
      }
      await loadDashboard(dashboardData.date);
      showToast("Timetable generated");
    } catch (ex) {
      showToast(ex.message);
    }
  });

  document.getElementById("what-next-btn").addEventListener("click", async () => {
    try {
      const now = new Date();
      const res = await apiRequest("/api/planner/what-next", {
        method: "POST",
        body: JSON.stringify({
          date: dashboardData.date,
          current_time: now.toTimeString().slice(0, 5),
        }),
      });
      const box = document.getElementById("ai-suggestion-box");
      document.getElementById("ai-suggestion-text").textContent = res.suggestion;
      box.classList.remove("hidden");
    } catch (ex) {
      showToast(ex.message);
    }
  });

  document.getElementById("reset-timetable-btn").addEventListener("click", async () => {
    if (!confirm("Clear all timetable items for today?")) return;
    await apiRequest("/api/planner/timetable/reset", {
      method: "POST",
      body: JSON.stringify({ date: dashboardData.date, confirmed: true }),
    });
    await loadDashboard(dashboardData.date);
    showToast("Timetable reset");
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } catch (e) { /* ignore */ }
    window.location.href = pageUrl("login.html");
  });

  setupLinkTypeToggle("item-link-type", "item-company-wrap");
  setupLinkTypeToggle("edit-item-link-type", "edit-item-company-wrap");

  fillSelectOptions(document.getElementById("item-link-type"), LINK_OPTIONS, "none");
  fillSelectOptions(document.getElementById("edit-item-link-type"), LINK_OPTIONS, "none");

  (async function init() {
    if (typeof initMobileNav === "function") initMobileNav();
    try {
      if (typeof wakeApiServer === "function") {
        await wakeApiServer();
      }
      await apiRequest("/api/me");
    } catch (e) {
      window.location.href = pageUrl("login.html");
      return;
    }
    await loadCompanies();
    try {
      await loadDashboard(isoDate(currentDate));
    } catch (ex) {
      showToast(ex.message || "Could not load timetable");
    }
  })();
})();
