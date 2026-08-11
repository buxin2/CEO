(function () {
  const messagesEl = document.getElementById("mentor-chat-messages");
  const input = document.getElementById("mentor-chat-input");
  const form = document.getElementById("mentor-chat-form");
  const checkinsEl = document.getElementById("mentor-checkins");
  let dashboard = null;
  let pollTimer = null;
  let processing = false;

  function escapeHtml(t) {
    const d = document.createElement("div");
    d.textContent = t || "";
    return d.innerHTML;
  }

  function formatAssistantHtml(text) {
    return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }

  function renderMessages(messages) {
    if (!messages || !messages.length) {
      messagesEl.innerHTML = `<div class="mentor-chat-welcome"><p>🧠 Your Mentor knows your companies, timetable, earnings, and opportunities.</p>
        <p>Ask: <em>What should I do now?</em> or tell me what you finished.</p></div>`;
      return;
    }
    messagesEl.innerHTML = messages
      .map((m) => {
        const isUser = m.role === "user";
        const isProactive = m.role === "proactive";
        const label = isUser ? "You" : isProactive ? "🧠 Mentor" : "🧠 Mentor";
        const cls = isUser ? "mentor-msg-user" : "mentor-msg-mentor";
        let actions = "";
        if (!isUser && window.speechSynthesis) {
          actions = `<button type="button" class="btn btn-ghost btn-sm mentor-play-btn" data-text="${escapeHtml(m.content)}">🔊 Listen</button>`;
        }
        return `<div class="mentor-msg ${cls}"><div class="mentor-msg-label">${label}</div>
          <div class="mentor-msg-body">${formatAssistantHtml(m.content)}</div>${actions}</div>`;
      })
      .join("");
    messagesEl.querySelectorAll(".mentor-play-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (window.AiVoice) AiVoice.speak(btn.getAttribute("data-text"));
      });
    });
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderRightNow(d) {
    const el = document.getElementById("mentor-right-now");
    const focus = d.right_now;
    if (!focus) {
      el.innerHTML = `<h2 class="section-title">🔥 Right now</h2><p class="text-muted">No active timetable block. Click <strong>What should I do now?</strong></p>`;
      return;
    }
    const mins = focus.minutes_remaining || 0;
    el.innerHTML = `
      <h2 class="section-title">🔥 Right now</h2>
      <p class="mentor-focus-title">${escapeHtml(focus.title)}</p>
      <p class="mentor-focus-time">${focus.start_time} – ${focus.end_time}</p>
      <p class="mentor-focus-mins">${mins} min remaining</p>
      <a class="btn btn-primary btn-sm" href="timetable.html">Open Timetable</a>`;
  }

  function renderDashboard(d) {
    dashboard = d;
    document.getElementById("mentor-now-label").textContent =
      `${d.now.weekday} ${d.now.date} · ${d.now.time}`;

    renderRightNow(d);

    const next = d.next_up;
    document.getElementById("mentor-next-text").textContent = next
      ? `${next.title} (${next.start_time}–${next.end_time})`
      : "Nothing else scheduled — ask Mentor for the next priority.";

    const probs = d.problems || [];
    document.getElementById("mentor-problems-list").innerHTML = probs.length
      ? probs.map((p) => `<div class="mentor-problem-row"><strong>${escapeHtml(p.title)}</strong>
        <span class="text-muted"> · ${escapeHtml(p.status)}</span></div>`).join("")
      : "<p class=\"text-muted\">No active problems.</p>";

    const companies = d.companies_summary || [];
    document.getElementById("mentor-business-summary").innerHTML = companies.length
      ? companies.slice(0, 4).map((c) =>
          `<div class="mentor-company-row"><a href="company.html?id=${c.id}">${escapeHtml(c.name)}</a>
          <span class="text-muted"> tasks ${c.week_task_stats?.completed || 0}/${c.week_task_stats?.total || 0}</span></div>`
        ).join("")
      : "<p class=\"text-muted\">No companies.</p>";

    const opps = d.opportunities || [];
    document.getElementById("mentor-opportunities-list").innerHTML = opps.length
      ? opps.slice(0, 3).map((o) =>
          `<div><a href="news.html">${escapeHtml(o.title)}</a></div>`
        ).join("")
      : "<p class=\"text-muted\">No opportunities loaded today.</p>";

    document.getElementById("mentor-advice-text").textContent = d.advice || "—";

    renderMessages(d.messages);
    renderCheckins(d.pending_checkins);
  }

  function renderCheckins(items) {
    if (!items || !items.length) {
      checkinsEl.innerHTML = "";
      return;
    }
    checkinsEl.innerHTML = items
      .filter((c) => c.status === "sent" || c.status === "pending")
      .map((c) => `
      <div class="mentor-checkin-card card-inner">
        <p>${formatAssistantHtml(c.message)}</p>
        <div class="mentor-checkin-btns">
          <button type="button" class="btn btn-primary btn-sm" data-id="${c.id}" data-type="completed">Yes, Done</button>
          <button type="button" class="btn btn-secondary btn-sm" data-id="${c.id}" data-type="partial">Partially</button>
          <button type="button" class="btn btn-secondary btn-sm" data-id="${c.id}" data-type="not_yet">Not Yet</button>
          <button type="button" class="btn btn-secondary btn-sm" data-id="${c.id}" data-type="need_help">Need Help</button>
        </div>
      </div>`).join("");

    checkinsEl.querySelectorAll("button[data-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await apiRequest(`/api/mentor/check-ins/${btn.dataset.id}/respond`, {
          method: "POST",
          body: JSON.stringify({ response_type: btn.dataset.type }),
        });
        await loadDashboard();
      });
    });
  }

  async function loadDashboard() {
    const d = await apiRequest("/api/mentor/dashboard", { retries: 10, retryDelayMs: 2000 });
    renderDashboard(d);
  }

  async function sendMessage(text, speakReply) {
    if (!text || processing) return;
    processing = true;
    try {
      const data = await apiRequest("/api/mentor/chat", {
        method: "POST",
        body: JSON.stringify({ message: text }),
        retries: 10,
        retryDelayMs: 2000,
      });
      const reply = data.reply || "";
      if (speakReply && window.AiVoice && reply) {
        AiVoice.speak(reply);
      }
      await loadDashboard();
    } catch (e) {
      showToast(e.message || "Failed");
    } finally {
      processing = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    sendMessage(text, false);
  });

  document.getElementById("mentor-what-now-btn").addEventListener("click", async () => {
    try {
      const data = await apiRequest("/api/mentor/what-now", { method: "POST", body: "{}" });
      const title = data.title || "Focus on your top priority";
      const why = data.why || "";
      sendMessage(`What should I do now? I think the answer is: ${title}. ${why}`, false);
    } catch (e) {
      showToast(e.message);
    }
  });

  document.querySelectorAll("#mentor-quick-actions button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = btn.getAttribute("data-prompt");
      if (p) sendMessage(p, false);
    });
  });

  document.getElementById("mentor-speak-btn").addEventListener("click", () => {
    if (!window.AiVoice || !AiVoice.startListening) return;
    AiVoice.startListening(input, (err) => showToast(err || "Voice failed"));
  });

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } catch (e) { /* ignore */ }
    window.location.href = pageUrl("login.html");
  });

  if (typeof initMobileNav === "function") initMobileNav();

  (async function init() {
    try {
      if (typeof wakeApiServer === "function") await wakeApiServer();
      await apiRequest("/api/me");
    } catch (e) {
      window.location.href = pageUrl("login.html");
      return;
    }
    await loadDashboard();
    pollTimer = setInterval(loadDashboard, 45000);
  })();
})();
