(function () {
  const messagesEl = document.getElementById("mentor-chat-messages");
  const input = document.getElementById("mentor-chat-input");
  const form = document.getElementById("mentor-chat-form");
  const checkinsEl = document.getElementById("mentor-checkins");
  let dashboard = null;
  let pollTimer = null;
  let processing = false;
  let timezoneOptions = [];
  let activeTimezoneId = "";
  let clockTimer = null;
  let timerAccum = 0;
  let timerStart = null;
  let timerInterval = null;

  function normalizeTimezoneId(tz) {
    const aliases = { "Asia/Calcutta": "Asia/Kolkata" };
    return aliases[tz] || tz;
  }

  // Used if /api/mentor/timezones is unavailable (e.g. old backend deploy)
  const FALLBACK_TIMEZONE_COUNTRIES = [
    {
      name: "India",
      cities: [
        { name: "Mumbai", timezone_id: "Asia/Kolkata", label: "Mumbai (IST)" },
        { name: "Delhi", timezone_id: "Asia/Kolkata", label: "Delhi (IST)" },
        { name: "Kolkata", timezone_id: "Asia/Kolkata", label: "Kolkata (IST)" },
        { name: "Chennai", timezone_id: "Asia/Kolkata", label: "Chennai (IST)" },
        { name: "Bangalore", timezone_id: "Asia/Kolkata", label: "Bangalore (IST)" },
        { name: "Hyderabad", timezone_id: "Asia/Kolkata", label: "Hyderabad (IST)" },
        { name: "Ahmedabad", timezone_id: "Asia/Kolkata", label: "Ahmedabad (IST)" },
        { name: "Pune", timezone_id: "Asia/Kolkata", label: "Pune (IST)" },
      ],
    },
  ];

  function formatTimeInZone(tz) {
    if (!tz) return "--:--:--";
    try {
      return new Intl.DateTimeFormat("en-IN", {
        timeZone: tz,
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      }).format(new Date());
    } catch (e) {
      return "--:--:--";
    }
  }

  function formatDateInZone(tz) {
    if (!tz) return "";
    try {
      return new Intl.DateTimeFormat("en-GB", {
        timeZone: tz,
        weekday: "long",
        year: "numeric",
        month: "short",
        day: "numeric",
      }).format(new Date());
    } catch (e) {
      return "";
    }
  }

  function formatTimerMs(ms) {
    const total = Math.floor(ms / 1000);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
  }

  function populateCountries() {
    const sel = document.getElementById("mentor-timezone-country");
    if (!sel) return;
    sel.innerHTML = timezoneOptions
      .map((c) => `<option value="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`)
      .join("");
    syncCitiesForSelectedCountry();
  }

  function syncCitiesForSelectedCountry() {
    const countrySel = document.getElementById("mentor-timezone-country");
    if (!countrySel || !countrySel.value) return;
    populateCities(countrySel.value);
  }

  function populateCities(countryName) {
    const sel = document.getElementById("mentor-timezone-city");
    if (!sel) return;
    const country = timezoneOptions.find((c) => c.name === countryName);
    if (!country) {
      sel.innerHTML = "";
      return;
    }
    sel.innerHTML = country.cities
      .map(
        (city) =>
          `<option value="${escapeHtml(city.name)}" data-tz="${escapeHtml(city.timezone_id)}">${escapeHtml(city.label)}</option>`
      )
      .join("");
  }

  function selectedCityTimezone() {
    const citySel = document.getElementById("mentor-timezone-city");
    const opt = citySel && citySel.selectedOptions[0];
    return opt ? opt.getAttribute("data-tz") || "" : "";
  }

  function applyLocationSettings(settings) {
    if (!settings) settings = {};
    const countrySel = document.getElementById("mentor-timezone-country");
    const citySel = document.getElementById("mentor-timezone-city");
    if (settings.timezone_country && countrySel) {
      countrySel.value = settings.timezone_country;
    }
    syncCitiesForSelectedCountry();
    if (settings.timezone_city && citySel) {
      citySel.value = settings.timezone_city;
    }
    activeTimezoneId =
      settings.timezone_id || selectedCityTimezone() || activeTimezoneId || "";
    const locLabel = document.getElementById("mentor-location-label");
    if (locLabel) {
      locLabel.textContent = settings.timezone_id
        ? `Mentor uses local time for ${settings.timezone_city || "your city"}, ${settings.timezone_country || "your country"}.`
        : "Select your country and city, then click Save location.";
    }
    startLiveClock();
  }

  function findBrowserLocation() {
    const browserTz = normalizeTimezoneId(
      Intl.DateTimeFormat().resolvedOptions().timeZone || ""
    );
    if (!browserTz) return null;
    for (const country of timezoneOptions) {
      for (const city of country.cities) {
        if (normalizeTimezoneId(city.timezone_id) === browserTz) {
          return {
            country: country.name,
            city: city.name,
            timezone_id: city.timezone_id,
          };
        }
      }
    }
    return null;
  }

  function applyLocationToDropdowns(match) {
    if (!match) return;
    const countrySel = document.getElementById("mentor-timezone-country");
    const citySel = document.getElementById("mentor-timezone-city");
    if (countrySel) countrySel.value = match.country;
    syncCitiesForSelectedCountry();
    if (citySel) citySel.value = match.city;
    activeTimezoneId = match.timezone_id;
    startLiveClock();
  }

  async function maybeAutoSaveLocation() {
    const saved = dashboard && dashboard.settings && dashboard.settings.timezone_id;
    if (saved) return;
    const match = findBrowserLocation();
    if (!match) {
      syncCitiesForSelectedCountry();
      return;
    }
    applyLocationToDropdowns(match);
    try {
      await apiRequest("/api/mentor/settings", {
        method: "PUT",
        body: JSON.stringify({
          timezone_country: match.country,
          timezone_city: match.city,
          timezone_id: match.timezone_id,
        }),
      });
      showToast("Location set to " + match.city + ", " + match.country);
    } catch (e) {
      /* user can save manually */
    }
  }

  function startLiveClock() {
    if (clockTimer) clearInterval(clockTimer);
    const clockEl = document.getElementById("mentor-live-clock");
    const headerLabel = document.getElementById("mentor-now-label");
    const tick = () => {
      const tz = activeTimezoneId;
      if (!tz) {
        if (clockEl) clockEl.textContent = "Set location";
        return;
      }
      const timeStr = formatTimeInZone(tz);
      const dateStr = formatDateInZone(tz);
      if (clockEl) clockEl.textContent = timeStr;
      if (headerLabel) headerLabel.textContent = `${dateStr} · ${timeStr}`;
    };
    tick();
    clockTimer = setInterval(tick, 1000);
  }

  function suggestBrowserTimezone() {
    const match = findBrowserLocation();
    if (match) applyLocationToDropdowns(match);
  }

  async function loadTimezoneOptions() {
    try {
      const data = await apiRequest("/api/mentor/timezones");
      timezoneOptions = data.countries || [];
    } catch (e) {
      timezoneOptions = FALLBACK_TIMEZONE_COUNTRIES;
    }
    if (!timezoneOptions.length) {
      timezoneOptions = FALLBACK_TIMEZONE_COUNTRIES;
    }
    populateCountries();
    suggestBrowserTimezone();
  }

  function startTaskTimer() {
    if (timerInterval) return;
    timerStart = Date.now();
    timerInterval = setInterval(() => {
      const elapsed = timerAccum + (Date.now() - timerStart);
      document.getElementById("mentor-timer-display").textContent = formatTimerMs(elapsed);
    }, 200);
    document.getElementById("mentor-timer-start").disabled = true;
    document.getElementById("mentor-timer-stop").disabled = false;
  }

  function stopTaskTimer() {
    if (!timerInterval) return;
    timerAccum += Date.now() - timerStart;
    timerStart = null;
    clearInterval(timerInterval);
    timerInterval = null;
    document.getElementById("mentor-timer-display").textContent = formatTimerMs(timerAccum);
    document.getElementById("mentor-timer-start").disabled = false;
    document.getElementById("mentor-timer-stop").disabled = true;
  }

  function resetTaskTimer() {
    stopTaskTimer();
    timerAccum = 0;
    document.getElementById("mentor-timer-display").textContent = "00:00:00";
  }

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
    const name = d.display_name || "";
    document.getElementById("mentor-greeting-label").textContent = name
      ? `Speaking with you, ${name}`
      : "";
    const nameInput = document.getElementById("mentor-display-name");
    if (nameInput && name) nameInput.value = name;

    if (d.now && d.now.timezone_id) {
      activeTimezoneId = d.now.timezone_id;
    }
    applyLocationSettings(d.settings || {});

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

  document.getElementById("mentor-save-location-btn").addEventListener("click", async () => {
    const country = document.getElementById("mentor-timezone-country").value;
    const city = document.getElementById("mentor-timezone-city").value;
    const tz = selectedCityTimezone();
    if (!country || !city || !tz) {
      showToast("Please select a country and city first");
      return;
    }
    try {
      await apiRequest("/api/mentor/settings", {
        method: "PUT",
        body: JSON.stringify({
          timezone_country: country,
          timezone_city: city,
          timezone_id: tz,
        }),
      });
      activeTimezoneId = tz;
      showToast("Location saved — Mentor now uses your local time");
      await loadDashboard();
    } catch (e) {
      showToast(e.message || "Failed to save location");
    }
  });

  document.getElementById("mentor-timezone-country").addEventListener("change", () => {
    syncCitiesForSelectedCountry();
    activeTimezoneId = selectedCityTimezone();
    startLiveClock();
  });

  document.getElementById("mentor-timezone-city").addEventListener("change", () => {
    activeTimezoneId = selectedCityTimezone();
    startLiveClock();
  });

  document.getElementById("mentor-timer-start").addEventListener("click", startTaskTimer);
  document.getElementById("mentor-timer-stop").addEventListener("click", stopTaskTimer);
  document.getElementById("mentor-timer-reset").addEventListener("click", resetTaskTimer);

  document.getElementById("mentor-save-name-btn").addEventListener("click", async () => {
    const name = document.getElementById("mentor-display-name").value.trim();
    try {
      await apiRequest("/api/ai/profile", {
        method: "PUT",
        body: JSON.stringify({ display_name: name }),
      });
      showToast("Name saved — Mentor will call you " + name);
      await loadDashboard();
    } catch (e) {
      showToast(e.message || "Failed to save name");
    }
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
    await loadTimezoneOptions();
    await loadDashboard();
    await maybeAutoSaveLocation();
    await loadDashboard();
    pollTimer = setInterval(loadDashboard, 45000);
  })();
})();
