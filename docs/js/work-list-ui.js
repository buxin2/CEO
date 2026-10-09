function localTodayIso() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return d.getFullYear() + "-" + m + "-" + day;
}

function workDateKey(value) {
  if (!value) return "";
  return String(value).slice(0, 10);
}

function workIsDone(row) {
  return String((row && row.status) || "").toLowerCase() === "done";
}

function workAssignedRows(rows) {
  return (rows || []).filter((r) => workDateKey(r.assigned_date));
}

function workWeekdayName(iso) {
  const day = new Date(workDateKey(iso) + "T12:00:00");
  if (Number.isNaN(day.getTime())) return "";
  return ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][day.getDay()];
}

function workShortDate(iso) {
  const day = new Date(workDateKey(iso) + "T12:00:00");
  if (Number.isNaN(day.getTime())) return "";
  return day.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function workDayLabel(iso, todayIso) {
  const key = workDateKey(iso);
  if (!key) return "";
  if (key === todayIso) return "Today";
  const day = new Date(key + "T12:00:00");
  const today = new Date((todayIso || "") + "T12:00:00");
  if (!Number.isNaN(today.getTime())) {
    const diff = Math.round((today - day) / 86400000);
    if (diff === 1) return "Yesterday";
  }
  return workWeekdayName(key);
}

function workDayTitle(iso, todayIso) {
  const key = workDateKey(iso);
  const extra = key === todayIso ? " · Today" : (workDayLabel(key, todayIso) === "Yesterday" ? " · Yesterday" : "");
  return workWeekdayName(key) + extra + " · " + workShortDate(key);
}

function workMergedProgress(rows, lists, api, todayIso) {
  const today = workDateKey(todayIso) || localTodayIso();
  const list = workAssignedRows(rows);
  const meta = lists || [];
  const fromApi = api || {};
  const by = {};
  let done = 0;
  let pending = 0;
  list.forEach((r) => {
    const isDone = workIsDone(r);
    if (isDone) done += 1;
    else pending += 1;
    const day = workDateKey(r.assigned_date);
    if (!by[day]) by[day] = { date: day, given: 0, done: 0, pending: 0 };
    by[day].given += 1;
    if (isDone) by[day].done += 1;
    else by[day].pending += 1;
  });
  let days = Object.keys(by).sort().map((d) => ({
    date: d,
    weekday: workWeekdayName(d),
    given: by[d].given,
    done: by[d].done,
    pending: by[d].pending,
    is_today: d === today,
  }));
  if (!days.length && fromApi.days && fromApi.days.length) {
    days = fromApi.days.map((d) => Object.assign({}, d, { date: workDateKey(d.date) }));
  }
  const listTotal = meta.reduce((s, w) => s + Number(w.total_rows || 0), 0);
  const listRemaining = meta.reduce((s, w) => s + Number(w.remaining || 0), 0);
  const given = list.length;
  const total = Number(fromApi.total) || listTotal || given;
  const remaining = Number(fromApi.remaining);
  const stillInSheet = Number.isFinite(remaining) ? remaining : listRemaining;
  const sheetPct = total ? Math.round((100 * done) / total) : 0;
  const givenPct = given ? Math.round((100 * done) / given) : 0;
  const previousPending = list.filter((r) => workDateKey(r.assigned_date) < today && !workIsDone(r)).length;
  return {
    total: total,
    remaining: stillInSheet,
    given: given,
    done: done,
    pending: pending,
    sheet_pct: sheetPct,
    given_pct: givenPct,
    daily_quota: (meta[0] && meta[0].daily_quota) || fromApi.daily_quota || 5,
    days: days,
    previous_pending: previousPending,
  };
}

function workSkipField(key) {
  const k = String(key || "").trim().toLowerCase();
  return k === "#" || k === "no" || k === "id" || k === "assigned team member";
}

function workFieldHtml(key, val) {
  const text = String(val || "").trim();
  if (!text) return "";
  const k = String(key || "").toLowerCase();
  let body = escapeHtml(text);
  if (k.indexOf("website") >= 0 || /^https?:\/\//i.test(text)) {
    const href = /^https?:\/\//i.test(text) ? text : "https://" + text;
    body = `<a href="${escapeHtml(href)}" target="_blank" rel="noopener">${escapeHtml(text)}</a>`;
  } else if (k.indexOf("email") >= 0 && text.indexOf("@") >= 0) {
    body = `<a href="mailto:${escapeHtml(text)}">${escapeHtml(text)}</a>`;
  }
  return `<div class="work-row-field"><label>${escapeHtml(key)}</label><div>${body}</div></div>`;
}

function workDefaultView(progress, todayIso, current) {
  const today = workDateKey(todayIso) || localTodayIso();
  const status = (current && current.status) || "all";
  if (current && current.mode === "previous") return { mode: "previous", date: null, status: "open" };
  if (current && (current.mode === "today" || current.mode === "day")) {
    const date = workDateKey(current.date) || today;
    return { mode: "day", date: date, status: status };
  }
  return { mode: "day", date: today, status: "all" };
}

function workFilterRows(rows, view, todayIso) {
  const today = workDateKey(todayIso) || localTodayIso();
  let list = workAssignedRows(rows);
  if (view.mode === "previous") {
    return list.filter((r) => workDateKey(r.assigned_date) < today && !workIsDone(r));
  }
  const day = workDateKey(view.date || today);
  list = list.filter((r) => workDateKey(r.assigned_date) === day);
  if (view.status === "open") return list.filter((r) => !workIsDone(r));
  if (view.status === "done") return list.filter((r) => workIsDone(r));
  return list;
}

function workProgressHtml(progress) {
  const p = progress || {};
  const givenPct = p.given_pct || 0;
  return `
    <div class="work-stat-grid">
      <div class="work-stat"><span>Given</span><strong>${p.given || 0}</strong></div>
      <div class="work-stat"><span>Completed</span><strong>${p.done || 0}</strong></div>
      <div class="work-stat"><span>Not done</span><strong>${p.pending || 0}</strong></div>
      <div class="work-stat"><span>In sheet</span><strong>${p.remaining || 0}</strong></div>
    </div>
    <div class="progress-label"><span>Completed of given work</span><span>${givenPct}%</span></div>
    <div class="progress-track"><div class="progress-fill ${givenPct >= 100 ? "success" : ""}" style="width:${givenPct}%"></div></div>`;
}

function workDeskHtml(progress, view, todayIso, rows) {
  const today = workDateKey(todayIso) || localTodayIso();
  const days = ((progress && progress.days) || []).slice().sort((a, b) => String(b.date).localeCompare(String(a.date)));
  const previousPending = (progress && progress.previous_pending) || 0;
  const dayBtns = days.map((d) => {
    const date = workDateKey(d.date);
    const active = view.mode === "day" && workDateKey(view.date) === date;
    const tag = date === today ? "Today" : (workDayLabel(date, today) === "Yesterday" ? "Yesterday" : workWeekdayName(date));
    return `<button type="button" class="work-day-chip ${active ? "active" : ""}" data-work-view="day" data-work-date="${date}">
      <span class="work-day-chip-name">${escapeHtml(tag)}</span>
      <span class="work-day-chip-date">${escapeHtml(workShortDate(date))}</span>
      <span class="work-day-chip-count">${d.done}/${d.given} done</span>
    </button>`;
  }).join("");
  const prevActive = view.mode === "previous";
  const slice = workFilterRows(rows, Object.assign({}, view, { status: "all" }), today);
  const openCount = slice.filter((r) => !workIsDone(r)).length;
  const doneCount = slice.filter((r) => workIsDone(r)).length;
  const statusPills = view.mode === "previous"
    ? ""
    : `<div class="work-status-pills">
        <button type="button" class="filter-tab ${view.status === "all" ? "active" : ""}" data-work-status="all">All ${slice.length}</button>
        <button type="button" class="filter-tab ${view.status === "open" ? "active" : ""}" data-work-status="open">Not done ${openCount}</button>
        <button type="button" class="filter-tab ${view.status === "done" ? "active" : ""}" data-work-status="done">Completed ${doneCount}</button>
      </div>`;
  const heading = view.mode === "previous"
    ? "Previous leftover"
    : workDayTitle(view.date || today, today);
  const hint = view.mode === "previous"
    ? "Unfinished work from earlier days. Finish these, then continue with today."
    : "Only this day's work. Completed and not done stay on this day.";
  return `
    <div class="work-desk">
      ${workProgressHtml(progress)}
      <p class="work-desk-label">Days</p>
      <div class="work-day-strip">
        <button type="button" class="work-day-chip work-day-chip-prev ${prevActive ? "active" : ""}" data-work-view="previous">
          <span class="work-day-chip-name">Previous</span>
          <span class="work-day-chip-date">Leftover</span>
          <span class="work-day-chip-count">${previousPending} left</span>
        </button>
        ${dayBtns}
      </div>
      <h3 class="work-desk-heading">${escapeHtml(heading)}</h3>
      <p class="text-muted work-desk-hint">${escapeHtml(hint)}</p>
      ${statusPills}
    </div>`;
}

function workHeading(view, todayIso) {
  if (view.mode === "previous") return "Previous leftover";
  return workDayTitle(view.date || todayIso, todayIso);
}

function workEmptyMessage(view) {
  if (view.mode === "previous") return "<p class=\"text-muted\">No leftover work from previous days.</p>";
  if (view.status === "done") return "<p class=\"text-muted\">No completed work on this day.</p>";
  if (view.status === "open") return "<p class=\"text-muted\">No unfinished work on this day.</p>";
  return "<p class=\"text-muted\">No work on this day.</p>";
}

function workRowCardHtml(row, todayIso, options) {
  const r = row || {};
  const editable = options && options.editable;
  const editing = options && options.editing;
  const fields = Object.keys(r.fields || {}).map((k) => (workSkipField(k) ? "" : workFieldHtml(k, r.fields[k]))).join("");
  const dayKey = workDateKey(r.assigned_date);
  const today = workDateKey(todayIso);
  const done = workIsDone(r);
  let notesBlock = "";
  if (editable) {
    notesBlock = `<label class="form-label" style="margin-top:12px;">Notes of what you did</label>
       <textarea class="form-control" id="work-notes-${r.id}" rows="2" placeholder="Write what you completed">${escapeHtml(r.notes || "")}</textarea>
       <div class="flex gap-8" style="margin-top:8px;">
         <button type="button" class="btn btn-secondary btn-sm" data-save-work="${r.id}">Save notes</button>
         <button type="button" class="btn btn-primary btn-sm" data-done-work="${r.id}" data-status="${r.status}">${done ? "Mark not done" : "Mark done"}</button>
       </div>`;
  } else if (editing) {
    notesBlock = `${r.notes ? `<div class="work-notes-box">${escapeHtml(r.notes)}</div>` : ""}
      <label class="form-label" style="margin-top:12px;">This work is</label>
      <select class="form-control" data-admin-status="${r.id}">
        <option value="pending" ${done ? "" : "selected"}>Not done</option>
        <option value="done" ${done ? "selected" : ""}>Completed</option>
      </select>`;
  } else if (r.notes) {
    notesBlock = `<div class="work-notes-box">${escapeHtml(r.notes)}</div>`;
  }
  return `
    <div class="work-row-card ${done ? "is-done" : "is-open"}">
      <div class="work-row-head">
        <strong>#${r.row_number} ${escapeHtml(r.title)}</strong>
        <span class="work-status-badge ${done ? "is-done" : "is-open"}">${done ? "Completed" : "Not done"}</span>
      </div>
      <div class="work-row-day">${escapeHtml(workDayTitle(dayKey, today))}</div>
      <div class="work-row-fields">${fields}</div>
      ${notesBlock}
    </div>`;
}

function bindWorkAdminEdits(root, workListId, rows, onUpdated) {
  if (!root) return;
  root.querySelectorAll("[data-admin-status]").forEach((sel) => {
    sel.addEventListener("change", async () => {
      const id = Number(sel.getAttribute("data-admin-status"));
      const status = sel.value;
      try {
        await apiRequest("/api/work-lists/" + workListId + "/rows/" + id, {
          method: "PUT",
          body: JSON.stringify({ status }),
        });
        const row = (rows || []).find((r) => Number(r.id) === id);
        if (row) row.status = status;
        if (typeof showToast === "function") showToast(status === "done" ? "Marked completed" : "Marked not done");
        if (onUpdated) onUpdated();
      } catch (err) {
        if (typeof showToast === "function") showToast(err.message);
      }
    });
  });
}

function bindWorkDayTabs(root, onChange, current) {
  if (!root) return;
  root.querySelectorAll("[data-work-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-work-view");
      onChange({
        mode: mode,
        date: btn.getAttribute("data-work-date") || null,
        status: mode === "previous" ? "open" : ((current && current.status) || "all"),
      });
    });
  });
  root.querySelectorAll("[data-work-status]").forEach((btn) => {
    btn.addEventListener("click", () => {
      onChange(Object.assign({}, current || {}, { status: btn.getAttribute("data-work-status") }));
    });
  });
}
