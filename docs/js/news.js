(function () {
  const statusBanner = document.getElementById("news-status-banner");
  const dateSelect = document.getElementById("news-date-select");
  const filterVenture = document.getElementById("filter-venture");
  const filterType = document.getElementById("filter-type");
  const filterPriority = document.getElementById("filter-priority");
  const summaryEl = document.getElementById("news-summary");
  const recommendationEl = document.getElementById("news-recommendation");
  const venturesEl = document.getElementById("news-ventures");
  const emptyEl = document.getElementById("news-empty");
  const savedListEl = document.getElementById("news-saved-list");
  const reportView = document.getElementById("news-report-view");
  const savedView = document.getElementById("news-saved-view");
  const chatForm = document.getElementById("news-chat-form");
  const chatInput = document.getElementById("news-chat-input");
  const chatReply = document.getElementById("news-chat-reply");

  let meta = { ventures: [], opportunity_types: [] };
  let currentDate = null;
  let pollTimer = null;

  const PRIORITY_LABELS = {
    high: "🔥 HIGH PRIORITY",
    medium: "🟡 MEDIUM PRIORITY",
    low: "⚪ LOW PRIORITY",
  };

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
  }

  function formatDateLabel(iso) {
    try {
      const d = new Date(iso + "T12:00:00");
      return d.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });
    } catch (e) {
      return iso;
    }
  }

  function showStatus(text, kind) {
    statusBanner.textContent = text;
    statusBanner.classList.remove("hidden", "news-status-generating", "news-status-error");
    if (kind === "generating") statusBanner.classList.add("news-status-generating");
    if (kind === "error") statusBanner.classList.add("news-status-error");
  }

  function hideStatus() {
    statusBanner.classList.add("hidden");
  }

  function buildFilters() {
    filterVenture.innerHTML = "<option value=\"all\">All ventures</option>";
    meta.ventures.forEach((v) => {
      filterVenture.innerHTML += `<option value="${v.key}">${v.emoji} ${escapeHtml(v.label)}</option>`;
    });
    filterType.innerHTML = "<option value=\"all\">All types</option>";
    meta.opportunity_types.forEach((t) => {
      filterType.innerHTML += `<option value="${t.key}">${t.emoji} ${escapeHtml(t.label)}</option>`;
    });
  }

  async function loadMeta() {
    meta = await apiRequest("/api/news/meta");
    buildFilters();
  }

  async function loadDates() {
    const data = await apiRequest("/api/news/dates");
    const dates = data.dates || [];
    const status = await apiRequest("/api/news/status");
    const today = status.today;
    if (today && !dates.includes(today)) {
      dates.unshift(today);
    }
    dateSelect.innerHTML = "";
    dates.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = d === today ? `Today (${d})` : d;
      dateSelect.appendChild(opt);
    });
    if (!dates.length && today) {
      const opt = document.createElement("option");
      opt.value = today;
      opt.textContent = `Today (${today})`;
      dateSelect.appendChild(opt);
    }
    currentDate = dateSelect.value || today;
  }

  function deadlineHtml(opp) {
    if (!opp.deadline_date) {
      return "<p class=\"news-deadline news-deadline-none\">No deadline specified</p>";
    }
    let urgent = "";
    if (opp.deadline_urgent && opp.deadline_days_left != null) {
      urgent = `<span class="news-deadline-urgent">🔴 ${opp.deadline_days_left} DAYS LEFT</span> `;
    }
    return `<p class=\"news-deadline\">⏰ Deadline: <strong>${escapeHtml(opp.deadline_date)}</strong> ${urgent}</p>`;
  }

  function opportunityCardHtml(opp) {
    const applyUrl = opp.apply_url || opp.source_url;
    const state = opp.user_state || "none";
    const applied = state === "applied";
    const saved = state === "saved";
    const notRel = state === "not_relevant";

    let actions = "";
    if (applyUrl) {
      actions += `<a class=\"btn btn-primary btn-sm\" href=\"${escapeHtml(applyUrl)}\" target=\"_blank\" rel=\"noopener\">${escapeHtml(opp.apply_label || "Apply")}</a> ";
    }
    if (opp.source_url && opp.source_url !== applyUrl) {
      actions += `<a class=\"btn btn-secondary btn-sm\" href=\"${escapeHtml(opp.source_url)}\" target=\"_blank\" rel=\"noopener\">Read More</a> ";
    }
    if (opp.company_id) {
      actions += `<a class=\"btn btn-secondary btn-sm\" href=\"${pageUrl("company.html?id=" + opp.company_id)}\">Open Company</a> ";
    }
    actions += `<button type=\"button\" class=\"btn btn-secondary btn-sm news-save-btn\" data-id=\"${opp.id}\" data-saved=\"${saved}\">${saved ? "⭐ Saved" : "⭐ Save"}</button> ";
    actions += `<button type=\"button\" class=\"btn btn-secondary btn-sm news-applied-btn\" data-id=\"${opp.id}\" data-applied=\"${applied}\">${applied ? "Applied ✓" : "Mark Applied"}</button> ";
    actions += `<button type=\"button\" class=\"btn btn-secondary btn-sm news-timetable-btn\" data-id=\"${opp.id}\">Add to Timetable</button> ";
    if (!notRel) {
      actions += `<button type=\"button\" class=\"btn btn-secondary btn-sm news-notrel-btn\" data-id=\"${opp.id}\">Not Relevant</button>`;
    }

    return `
      <article class="news-opp-card card-inner" id="opp-${opp.id}" data-priority="${opp.priority}">
        <div class="news-opp-header">
          <span class="news-opp-priority">${PRIORITY_LABELS[opp.priority] || opp.priority}</span>
          <span class="news-opp-type">${escapeHtml(opp.opportunity_type_label || opp.opportunity_type)}</span>
        </div>
        <h3 class="news-opp-title">${escapeHtml(opp.title)}</h3>
        ${opp.summary ? `<p class="news-opp-summary">${escapeHtml(opp.summary)}</p>` : ""}
        ${opp.why_matters ? `<div class="news-why"><strong>Why this matters:</strong><p>${escapeHtml(opp.why_matters)}</p></div>` : ""}
        ${opp.eligibility ? `<p class="news-eligibility"><strong>Who can apply:</strong> ${escapeHtml(opp.eligibility)}</p>` : ""}
        ${opp.region ? `<p class="news-region"><strong>Location:</strong> ${escapeHtml(opp.region)}</p>` : ""}
        ${deadlineHtml(opp)}
        <p class="news-source"><strong>Source:</strong> ${escapeHtml(opp.source_name || "Web")}${opp.published_date ? " · " + escapeHtml(opp.published_date) : ""}</p>
        ${opp.uncertain ? "<p class=\"news-uncertain\">⚠️ Some details could not be fully verified — confirm on the official site.</p>" : ""}
        <div class="news-opp-actions">${actions}</div>
      </article>`;
  }

  function renderSummary(report) {
    const summary = report.summary || {};
    const byVenture = summary.by_venture || {};
    const total = summary.total || 0;
    const high = summary.high_priority || 0;

    let ventureLines = "";
    (report.ventures || meta.ventures).forEach((v) => {
      const key = v.key;
      const count = byVenture[key] || v.count || 0;
      const emoji = v.emoji || "";
      const label = v.label || key;
      ventureLines += `<li>${emoji} ${escapeHtml(label)} — <strong>${count}</strong></li>`;
    });

    const topTitles = (summary.top_titles || []).slice(0, 3);
    let topHtml = "";
    if (topTitles.length) {
      topHtml = "<h4>🔥 Most Important Today</h4><ul>" + topTitles.map((t) => `<li>${escapeHtml(t)}</li>`).join("") + "</ul>";
    }

    summaryEl.innerHTML = `
      <h2>Today's Opportunity Report</h2>
      <p class="news-report-date">${formatDateLabel(report.report_date)}</p>
      <p class="news-total-count"><strong>${total}</strong> opportunities found · <strong>${high}</strong> high priority</p>
      <ul class="news-venture-counts">${ventureLines}</ul>
      ${topHtml}`;
    summaryEl.classList.remove("hidden");
  }

  function renderRecommendation(text) {
    if (!text) {
      recommendationEl.classList.add("hidden");
      return;
    }
    recommendationEl.innerHTML = `<h2>🤖 AI Recommendation</h2><div class="news-recommendation-text">${escapeHtml(text)}</div>`;
    recommendationEl.classList.remove("hidden");
  }

  function renderVentures(report) {
    const opps = report.opportunities || [];
    if (!opps.length && report.status === "complete") {
      venturesEl.innerHTML = "";
      emptyEl.classList.remove("hidden");
      emptyEl.innerHTML = "<p>No major new opportunities found today for your filters. Try Regenerate or check back tomorrow.</p>";
      return;
    }
    emptyEl.classList.add("hidden");

    const grouped = {};
    meta.ventures.forEach((v) => {
      grouped[v.key] = { meta: v, items: [] };
    });
    opps.forEach((o) => {
      if (grouped[o.venture_key]) {
        grouped[o.venture_key].items.push(o);
      }
    });

    let html = "";
    Object.keys(grouped).forEach((key) => {
      const block = grouped[key];
      const items = block.items;
      const v = block.meta;
      html += `<section class="card news-venture-section">
        <h2 class="news-venture-heading">${v.emoji} ${escapeHtml(v.label)}</h2>
        <p class="text-muted">${items.length} opportunit${items.length === 1 ? "y" : "ies"}</p>`;
      if (!items.length) {
        html += "<p class=\"news-no-venture\">No major new opportunities found today.</p>";
      } else {
        html += items.map(opportunityCardHtml).join("");
      }
      html += "</section>";
    });
    venturesEl.innerHTML = html;
    bindOppButtons();
  }

  function bindOppButtons() {
    document.querySelectorAll(".news-save-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const saved = btn.dataset.saved === "true";
        await setState(id, saved ? "none" : "saved");
        await loadReport();
      });
    });
    document.querySelectorAll(".news-applied-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const applied = btn.dataset.applied === "true";
        await setState(id, applied ? "none" : "applied");
        await loadReport();
      });
    });
    document.querySelectorAll(".news-notrel-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await setState(btn.dataset.id, "not_relevant");
        await loadReport();
      });
    });
    document.querySelectorAll(".news-timetable-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await apiRequest(`/api/news/opportunities/${btn.dataset.id}/timetable`, { method: "POST", body: "{}" });
          showToast("Added to today's timetable");
        } catch (e) {
          showToast(e.message || "Failed");
        }
      });
    });
  }

  async function setState(id, status) {
    await apiRequest(`/api/news/opportunities/${id}/state`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    });
  }

  async function loadReport() {
    const params = new URLSearchParams({
      date: currentDate || dateSelect.value,
      venture: filterVenture.value,
      type: filterType.value,
      priority: filterPriority.value,
    });
    const report = await apiRequest(`/api/news/report?${params}`);

    if (report.status === "generating" || report.status === "pending") {
      showStatus("AI is searching for opportunities… This can take 1–3 minutes on first run.", "generating");
      startPoll();
    } else if (report.status === "failed") {
      showStatus("Report failed: " + (report.error_message || "Unknown error"), "error");
    } else {
      hideStatus();
      stopPoll();
    }

    if (report.status === "complete") {
      renderSummary(report);
      renderRecommendation(report.ai_recommendation);
      renderVentures(report);
    } else if (report.status !== "complete") {
      summaryEl.classList.add("hidden");
      recommendationEl.classList.add("hidden");
      venturesEl.innerHTML = "<div class=\"card\"><p class=\"text-muted\">Generating report…</p></div>";
    }

    const highlight = new URLSearchParams(window.location.search).get("opportunity");
    if (highlight) {
      const el = document.getElementById("opp-" + highlight);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("news-opp-highlight");
      }
    }
  }

  function startPoll() {
    stopPoll();
    pollTimer = setInterval(() => loadReport(), 8000);
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function loadSaved() {
    const data = await apiRequest("/api/news/saved");
    const opps = data.opportunities || [];
    if (!opps.length) {
      savedListEl.innerHTML = "<div class=\"card\"><p>No saved opportunities yet.</p></div>";
      return;
    }
    savedListEl.innerHTML = `<section class="card">${opps.map(opportunityCardHtml).join("")}</section>`;
    bindOppButtons();
  }

  dateSelect.addEventListener("change", () => {
    currentDate = dateSelect.value;
    loadReport();
  });

  filterVenture.addEventListener("change", loadReport);
  filterType.addEventListener("change", loadReport);
  filterPriority.addEventListener("change", loadReport);

  document.querySelectorAll(".news-view-tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".news-view-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const view = btn.dataset.view;
      if (view === "saved") {
        reportView.classList.add("hidden");
        savedView.classList.remove("hidden");
        loadSaved();
      } else {
        savedView.classList.add("hidden");
        reportView.classList.remove("hidden");
        loadReport();
      }
    });
  });

  document.getElementById("news-refresh-btn").addEventListener("click", async () => {
    showStatus("Regenerating today's report…", "generating");
    await apiRequest("/api/news/generate", { method: "POST", body: JSON.stringify({ async: true, force: true }) });
    startPoll();
    await loadReport();
  });

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    chatReply.classList.remove("hidden");
    chatReply.textContent = "Thinking…";
    try {
      const data = await apiRequest("/api/news/chat", {
        method: "POST",
        body: JSON.stringify({
          message,
          search: document.getElementById("news-chat-search").checked,
        }),
      });
      chatReply.textContent = data.reply || "";
    } catch (err) {
      chatReply.textContent = err.message || "Failed";
    }
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } catch (e) {
      /* ignore */
    }
    window.location.href = pageUrl("login.html");
  });

  if (typeof initMobileNav === "function") initMobileNav();

  (async function init() {
    try {
      await apiRequest("/api/me");
    } catch (e) {
      window.location.href = pageUrl("login.html");
      return;
    }
    await loadMeta();
    await loadDates();
    await apiRequest("/api/news/status");
    currentDate = dateSelect.value;
    await loadReport();
  })();
})();
