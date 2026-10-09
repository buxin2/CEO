function localTodayIso() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return d.getFullYear() + "-" + m + "-" + day;
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
  const days = (progress && progress.days) || [];
  if (current && current.mode === "pending") return { mode: "pending", date: null };
  if (current && current.mode === "day" && current.date && days.some((d) => d.date === current.date)) {
    return { mode: "day", date: current.date };
  }
  if (days.some((d) => d.date === todayIso)) return { mode: "day", date: todayIso };
  if (days.length) return { mode: "day", date: days[days.length - 1].date };
  return { mode: "day", date: todayIso };
}

function workDayTabsHtml(progress, view, todayIso) {
  const days = (progress && progress.days) || [];
  const pending = (progress && progress.pending) || 0;
  const dayBtns = days.map((d) => {
    const active = view.mode === "day" && view.date === d.date;
    const count = d.pending ? d.pending + " left" : (d.done ? d.done + " done" : d.given);
    return `<button type="button" class="filter-tab ${active ? "active" : ""}" data-work-view="day" data-work-date="${d.date}">${escapeHtml(workDayLabel(d.date, todayIso))}<span class="work-tab-count">${escapeHtml(String(count))}</span></button>`;
  }).join("");
  return `
    <div class="filter-tabs work-day-tabs">
      ${dayBtns}
      <button type="button" class="filter-tab ${view.mode === "pending" ? "active" : ""}" data-work-view="pending">Pending<span class="work-tab-count">${pending}</span></button>
    </div>`;
}

function workFilterRows(rows, view, todayIso) {
  const list = rows || [];
  if (view.mode === "pending") {
    return list.filter((r) => r.status !== "done");
  }
  const day = view.date || todayIso;
  return list.filter((r) => r.assigned_date === day);
}

function workRowCardHtml(row, todayIso, options) {
  const r = row || {};
  const editable = options && options.editable;
  const fields = Object.keys(r.fields || {}).map((k) => (workSkipField(k) ? "" : workFieldHtml(k, r.fields[k]))).join("");
  const dayBadge = r.assigned_date === todayIso ? "Today" : workDayLabel(r.assigned_date, todayIso);
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
  return workDayLabel(view.date || todayIso, todayIso) + " tasks";
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
