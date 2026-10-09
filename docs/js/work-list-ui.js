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

function workMergedProgress(rows, lists, api, todayIso) {
  const today = workDateKey(todayIso) || localTodayIso();
  const list = rows || [];
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
    if (!day) return;
    if (!by[day]) by[day] = { date: day, given: 0, done: 0, pending: 0 };
    by[day].given += 1;
    if (isDone) by[day].done += 1;
    else by[day].pending += 1;
  });
  let days = Object.keys(by).sort().map((d) => ({
    date: d,
    weekday: workDayLabel(d, today),
    given: by[d].given,
    done: by[d].done,
    pending: by[d].pending,
    is_today: d === today,
    is_yesterday: false,
  }));
  if (!days.length && fromApi.days && fromApi.days.length) {
    days = fromApi.days.map((d) => Object.assign({}, d, { date: workDateKey(d.date) }));
  }
  const listTotal = meta.reduce((s, w) => s + Number(w.total_rows || 0), 0);
  const listRemaining = meta.reduce((s, w) => s + Number(w.remaining || 0), 0);
  const given = list.length || Number(fromApi.given) || 0;
  const total = Number(fromApi.total) || listTotal || given;
  const remaining = Number(fromApi.remaining) || listRemaining;
  const sheetPct = total ? Math.round((100 * done) / total) : 0;
  const givenPct = given ? Math.round((100 * done) / given) : 0;
  const previousPending = list.filter((r) => {
    const day = workDateKey(r.assigned_date);
    return day && day < today && !workIsDone(r);
  }).length;
  return {
    total: total,
    remaining: remaining,
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

function workDayLabel(iso, todayIso) {
  if (!iso) return "";
  if (iso === todayIso) return "Today";
  const day = new Date(iso + "T12:00:00");
  const today = new Date((todayIso || "") + "T12:00:00");
  const names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  if (!Number.isNaN(today.getTime())) {
    const diff = Math.round((today - day) / 86400000);
    if (diff === 1) return "Yesterday";
  }
  return names[day.getDay()] + " " + day.getDate();
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

function workProgressHtml(progress) {
  const p = progress || {};
  const sheet = p.sheet_pct || 0;
  const given = p.given_pct || 0;
  return `
    <div class="work-analysis-card">
      <h3 class="section-title">Progress</h3>
      <p class="text-muted">${p.done || 0} done · ${p.pending || 0} pending · ${p.given || 0} given · ${p.remaining || 0} still in the sheet · ${p.total || 0} total</p>
      <div class="progress-label"><span>Of all tasks in the Excel</span><span>${sheet}%</span></div>
      <div class="progress-track"><div class="progress-fill ${sheet >= 100 ? "success" : ""}" style="width:${sheet}%"></div></div>
      <div class="progress-label" style="margin-top:10px;"><span>Of tasks already given</span><span>${given}%</span></div>
      <div class="progress-track"><div class="progress-fill ${given >= 100 ? "success" : ""}" style="width:${given}%"></div></div>
    </div>`;
}

function workDefaultView(progress, todayIso, current) {
  const today = workDateKey(todayIso) || localTodayIso();
  const days = (progress && progress.days) || [];
  if (current && current.mode === "pending") return { mode: "pending", date: null };
  if (current && current.mode === "previous") return { mode: "previous", date: null };
  if (current && current.mode === "day" && current.date && days.some((d) => workDateKey(d.date) === workDateKey(current.date))) {
    return { mode: "day", date: workDateKey(current.date) };
  }
  if (days.some((d) => workDateKey(d.date) === today)) return { mode: "day", date: today };
  if (days.length) return { mode: "day", date: workDateKey(days[days.length - 1].date) };
  return { mode: "day", date: today };
}

function workDayTabsHtml(progress, view, todayIso) {
  const today = workDateKey(todayIso) || localTodayIso();
  const days = ((progress && progress.days) || []).slice().sort((a, b) => String(b.date).localeCompare(String(a.date)));
  const pending = (progress && progress.pending) || 0;
  const previousPending = (progress && progress.previous_pending) || 0;
  const hasPast = days.some((d) => workDateKey(d.date) && workDateKey(d.date) !== today);
  const prevBtn = (hasPast || previousPending)
    ? `<button type="button" class="filter-tab ${view.mode === "previous" ? "active" : ""}" data-work-view="previous">Previous<span class="work-tab-count">${previousPending} left</span></button>`
    : "";
  const dayBtns = days.map((d) => {
    const date = workDateKey(d.date);
    const active = view.mode === "day" && workDateKey(view.date) === date;
    const count = d.pending ? d.pending + " left" : (d.done ? d.done + " done" : d.given);
    return `<button type="button" class="filter-tab ${active ? "active" : ""}" data-work-view="day" data-work-date="${date}">${escapeHtml(workDayLabel(date, today))}<span class="work-tab-count">${escapeHtml(String(count))}</span></button>`;
  }).join("");
  return `
    <div class="filter-tabs work-day-tabs">
      ${prevBtn}
      ${dayBtns}
      <button type="button" class="filter-tab ${view.mode === "pending" ? "active" : ""}" data-work-view="pending">Pending<span class="work-tab-count">${pending}</span></button>
    </div>`;
}

function workFilterRows(rows, view, todayIso) {
  const list = rows || [];
  const today = workDateKey(todayIso) || localTodayIso();
  if (view.mode === "pending") {
    return list.filter((r) => !workIsDone(r));
  }
  if (view.mode === "previous") {
    return list.filter((r) => {
      const day = workDateKey(r.assigned_date);
      return day && day < today && !workIsDone(r);
    });
  }
  const day = workDateKey(view.date || today);
  return list.filter((r) => workDateKey(r.assigned_date) === day);
}

function workRowCardHtml(row, todayIso, options) {
  const r = row || {};
  const editable = options && options.editable;
  const fields = Object.keys(r.fields || {}).map((k) => (workSkipField(k) ? "" : workFieldHtml(k, r.fields[k]))).join("");
  const dayKey = workDateKey(r.assigned_date);
  const today = workDateKey(todayIso);
  const dayBadge = dayKey === today ? "Today" : workDayLabel(dayKey, today);
  const notesBlock = editable
    ? `<label class="form-label" style="margin-top:12px;">Notes of what you did</label>
       <textarea class="form-control" id="work-notes-${r.id}" rows="2" placeholder="Write what you completed">${escapeHtml(r.notes || "")}</textarea>
       <div class="flex gap-8" style="margin-top:8px;">
         <button type="button" class="btn btn-secondary btn-sm" data-save-work="${r.id}">Save notes</button>
         <button type="button" class="btn btn-primary btn-sm" data-done-work="${r.id}" data-status="${r.status}">${r.status === "done" ? "Undo done" : "Mark done"}</button>
       </div>`
    : (r.notes ? `<p class="text-muted" style="margin-top:10px;">${escapeHtml(r.notes)}</p>` : "");
  return `
    <div class="work-row-card ${r.status === "done" ? "done" : ""}">
      <div class="work-row-head">
        <strong>#${r.row_number} ${escapeHtml(r.title)}</strong>
        <span class="badge">${escapeHtml(dayBadge)} · ${escapeHtml(r.status || "pending")}</span>
      </div>
      <div class="work-row-fields">${fields}</div>
      ${notesBlock}
    </div>`;
}

function workHeading(view, todayIso) {
  if (view.mode === "pending") return "Pending tasks";
  if (view.mode === "previous") return "Previous unfinished tasks";
  return workDayLabel(view.date || todayIso, todayIso) + " tasks";
}

function workEmptyMessage(view) {
  if (view.mode === "pending") return "<p class=\"text-muted\">No pending Excel tasks.</p>";
  if (view.mode === "previous") return "<p class=\"text-muted\">No unfinished tasks from previous days.</p>";
  return "<p class=\"text-muted\">No Excel tasks for this day.</p>";
}

function bindWorkDayTabs(root, onChange) {
  if (!root) return;
  root.querySelectorAll("[data-work-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      onChange({
        mode: btn.getAttribute("data-work-view"),
        date: btn.getAttribute("data-work-date") || null,
      });
    });
  });
}
