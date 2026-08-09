(function () {
  const STORAGE_KEY = "ceo_ai_chat_history";
  const messagesEl = document.getElementById("ai-chat-messages");
  const form = document.getElementById("ai-chat-form");
  const input = document.getElementById("ai-chat-input");
  const sendBtn = document.getElementById("ai-send-btn");
  const thinkingEl = document.getElementById("ai-thinking");
  const thinkingTextEl = document.getElementById("ai-thinking-text");
  const serverStatusEl = document.getElementById("ai-server-status");
  const configWarning = document.getElementById("ai-config-warning");
  const speakBtn = document.getElementById("ai-speak-btn");
  const speakDoneBtn = document.getElementById("ai-speak-done-btn");
  const voiceStatusEl = document.getElementById("ai-voice-status");

  let history = [];
  let processing = false;
  let serverReady = false;
  let wakePromise = null;
  let aiMode = "chat";

  const MODE_PLACEHOLDERS = {
    chat: "Talk to your AI mentor — life, career, ideas… (no app changes in this mode)",
    manage: "Create or update something: e.g. Create company AiDoBot, list my employees…",
  };

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function formatAssistantHtml(text) {
    const escaped = escapeHtml(text);
    return escaped
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^[-*] (.+)$/gm, "• $1")
      .replace(/\n/g, "<br>");
  }

  function loadHistory() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  const HISTORY_ERROR_PREFIX = "I couldn't complete that request:";
  const MAX_HISTORY_FOR_API = 8;
  const MAX_HISTORY_CHARS = 1200;

  function isSmallTalk(text) {
    const t = (text || "").trim();
    if (!t) return true;
    if (/^(hi|hello|hey|yo|good\s+(morning|afternoon|evening)|thanks|thank\s+you|ok|okay)[\s!.?]*$/i.test(t)) {
      return true;
    }
    const actionWords = ["create", "add", "delete", "company", "employee", "task", "product", "service"];
    if (t.length < 48 && t.split(/\s+/).length <= 4) {
      const lower = t.toLowerCase();
      return !actionWords.some((w) => lower.includes(w));
    }
    return false;
  }

  function setAiMode(mode) {
    aiMode = mode === "manage" ? "manage" : "chat";
    const chatBtn = document.getElementById("ai-mode-chat");
    const manageBtn = document.getElementById("ai-mode-manage");
    if (chatBtn) chatBtn.classList.toggle("active", aiMode === "chat");
    if (manageBtn) manageBtn.classList.toggle("active", aiMode === "manage");
    if (input) input.placeholder = MODE_PLACEHOLDERS[aiMode] || MODE_PLACEHOLDERS.chat;
    try {
      sessionStorage.setItem("ceo_ai_mode", aiMode);
    } catch (e) {
      /* ignore */
    }
  }

  function loadAiMode() {
    try {
      const saved = sessionStorage.getItem("ceo_ai_mode");
      if (saved === "manage" || saved === "chat") return saved;
    } catch (e) {
      /* ignore */
    }
    return "chat";
  }

  function historyForApi(text, priorHistory) {
    if (aiMode === "chat") {
      return sanitizeHistoryForApi(priorHistory);
    }
    if (isSmallTalk(text)) return [];
    return sanitizeHistoryForApi(priorHistory);
  }

  function sanitizeHistoryForApi(items) {
    const cleaned = [];
    items.forEach((item) => {
      if (item.role !== "user" && item.role !== "assistant") return;
      let content = (item.content || "").trim();
      if (!content) return;
      if (content.startsWith(HISTORY_ERROR_PREFIX)) return;
      if (content.length > MAX_HISTORY_CHARS) {
        content = content.slice(0, MAX_HISTORY_CHARS) + "… [truncated]";
      }
      cleaned.push({ role: item.role, content });
    });
    if (cleaned.length > MAX_HISTORY_FOR_API) {
      return cleaned.slice(-MAX_HISTORY_FOR_API);
    }
    return cleaned;
  }

  function clearChat() {
    history = [];
    sessionStorage.removeItem(STORAGE_KEY);
    messagesEl.innerHTML = `
      <div class="ai-chat-welcome">
        <p>Examples you can type naturally:</p>
        <ul>
          <li>Create a company called BuXin Healthcare with John as manager and Sarah in marketing.</li>
          <li>Give John three tasks this week: contact hospitals, prepare the report, follow up with suppliers.</li>
          <li>What companies do I have? Who hasn't completed their tasks this week?</li>
        </ul>
      </div>`;
    showToast("Chat cleared");
    input.focus();
  }

  function saveHistory() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch (e) {
      /* ignore quota errors */
    }
  }

  function removeWelcome() {
    const welcome = messagesEl.querySelector(".ai-chat-welcome");
    if (welcome) welcome.remove();
  }

  function appendMessage(role, content) {
    removeWelcome();
    const wrap = document.createElement("div");
    wrap.className =
      "ai-chat-bubble " +
      (role === "user" ? "ai-chat-bubble-user" : "ai-chat-bubble-assistant");

    const labelRow = document.createElement("div");
    labelRow.className = "ai-chat-label-row";

    const label = document.createElement("div");
    label.className = "ai-chat-label";
    label.textContent = role === "user" ? "You" : "AI Assistant";
    labelRow.appendChild(label);

    if (role === "assistant") {
      labelRow.appendChild(
        window.AiVoice ? AiVoice.createPlayButton(content) : createFallbackPlay(content)
      );
    }

    const body = document.createElement("div");
    body.className = "ai-chat-body";
    if (role === "user") {
      body.textContent = content;
    } else {
      body.innerHTML = formatAssistantHtml(content);
    }

    wrap.appendChild(labelRow);
    wrap.appendChild(body);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function createFallbackPlay(text) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ai-voice-play-btn";
    btn.textContent = "▶ Listen";
    btn.addEventListener("click", () => showToast("Voice module not loaded. Refresh the page."));
    return btn;
  }

  function renderHistory() {
    history.forEach((item) => {
      if (item.role === "user" || item.role === "assistant") {
        appendMessage(item.role, item.content);
      }
    });
  }

  function setVoiceUiState(listening) {
    if (!speakBtn || !speakDoneBtn || !voiceStatusEl) return;
    speakBtn.classList.toggle("listening", listening);
    speakBtn.textContent = listening ? "🎤 Listening…" : "🎤 Speak";
    speakDoneBtn.classList.toggle("hidden", !listening);
    voiceStatusEl.classList.toggle("hidden", !listening);
    if (listening) {
      sendBtn.disabled = true;
    } else if (!processing && serverReady) {
      sendBtn.disabled = false;
    }
  }

  function setVoiceButtonsEnabled(enabled) {
    const on = enabled && !processing;
    if (speakBtn) speakBtn.disabled = !on || (window.AiVoice && AiVoice.isListening());
    if (speakDoneBtn) speakDoneBtn.disabled = !on;
  }

  function setProcessing(active, message) {
    processing = active;
    sendBtn.disabled = active || !serverReady;
    input.disabled = active;
    setVoiceButtonsEnabled(!active && serverReady);
    if (active && window.AiVoice) {
      AiVoice.stopListening();
      setVoiceUiState(false);
    }
    thinkingEl.classList.toggle("hidden", !active);
    thinkingEl.setAttribute("aria-hidden", active ? "false" : "true");
    if (thinkingTextEl) {
      thinkingTextEl.textContent = message || "AI is working...";
    }
  }

  function setServerStatus(state, text) {
    if (!serverStatusEl) return;
    serverStatusEl.textContent = text;
    serverStatusEl.className = "ai-server-status ai-server-status-" + state;
  }

  function startServerWake() {
    if (wakePromise) return wakePromise;

    serverReady = false;
    sendBtn.disabled = true;
    setServerStatus("waking", "Connecting to server… (Render may take up to a minute to wake up)");

    wakePromise = wakeApiServer((attempt, total) => {
      setServerStatus(
        "waking",
        "Waking up server… attempt " + attempt + " of " + total + " (free tier cold start)"
      );
    })
      .then(() => {
        serverReady = true;
        setServerStatus("ready", "Server connected — you can chat now.");
        setVoiceButtonsEnabled(true);
        if (!processing) {
          sendBtn.disabled = false;
        }
        return checkStatus();
      })
      .catch(() => {
        setServerStatus(
          "error",
          "Server is still starting. You can send a message — we will keep retrying automatically."
        );
        serverReady = true;
        setVoiceButtonsEnabled(true);
        if (!processing) {
          sendBtn.disabled = false;
        }
      });

    return wakePromise;
  }

  function canRecordVoice() {
    if (window.AiVoice && typeof AiVoice.recordingSupported === "function") {
      return AiVoice.recordingSupported();
    }
    return !!(
      navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia &&
      window.MediaRecorder
    );
  }

  function patchAiVoiceApi() {
    if (!window.AiVoice) return;
    if (typeof AiVoice.recordingSupported !== "function") {
      AiVoice.recordingSupported = function () {
        return !!(
          navigator.mediaDevices &&
          navigator.mediaDevices.getUserMedia &&
          window.MediaRecorder
        );
      };
    }
    if (typeof AiVoice.finishListening !== "function") {
      AiVoice.finishListening = async function (inputEl) {
        AiVoice.stopListening();
        return (inputEl && inputEl.value || "").trim();
      };
    }
  }

  async function startSpeak() {
    if (processing) return;
    patchAiVoiceApi();
    if (!window.AiVoice) {
      showToast("Voice module not loaded. Hard refresh the page (Ctrl+F5).");
      return;
    }

    if (!canRecordVoice()) {
      showToast("Voice recording is not supported in this browser. Try Chrome or Edge.");
      return;
    }

    AiVoice.stopSpeaking();
    setVoiceUiState(true);
    input.focus();

    const started = await AiVoice.startListening(input, (msg) => {
      setVoiceUiState(false);
      showToast(msg);
    });

    if (!started) {
      setVoiceUiState(false);
    }
  }

  async function finishSpeakAndSend() {
    patchAiVoiceApi();
    if (!window.AiVoice) return;
    if (processing) return;

    setVoiceUiState(false);
    if (thinkingTextEl) thinkingTextEl.textContent = "Transcribing speech...";
    thinkingEl.classList.remove("hidden");
    if (speakDoneBtn) speakDoneBtn.disabled = true;

    const text = await AiVoice.finishListening(input, null, (msg) => {
      showToast(msg);
    });

    thinkingEl.classList.add("hidden");
    setVoiceButtonsEnabled(true);

    if (text) {
      sendMessage(text);
    } else {
      showToast("No speech detected. Tap Speak and try again.");
    }
  }

  async function ensureServerReady() {
    if (serverReady) return;
    if (wakePromise) {
      await wakePromise;
      return;
    }
    await startServerWake();
  }

  async function checkStatus() {
    try {
      const status = await apiRequest("/api/ai/status", {
        retries: 8,
        retryDelayMs: 2000,
      });
      if (!status.configured) {
        configWarning.textContent =
          "AI is not configured. Add a Groq API key below or set GROQ_API_KEY on Render as a fallback.";
        configWarning.classList.add("visible");
      } else {
        configWarning.classList.remove("visible");
      }
      renderCurrentApi(status);
    } catch (e) {
      /* auth redirect handled by apiRequest */
    }
  }

  let groqKeys = [];

  function statusLabel(key) {
    if (key.is_active) return "Active";
    return "Inactive";
  }

  function testStatusBadge(key) {
    const s = key.last_test_status;
    if (s === "ok") return '<span class="groq-status-ok">🟢 API Working</span>';
    if (s === "auth_error") return '<span class="groq-status-warn">⚠️ Authentication Error</span>';
    if (s === "rate_limit") return '<span class="groq-status-warn">⚠️ Rate limit</span>';
    if (s === "quota") return '<span class="groq-status-warn">⚠️ Quota issue</span>';
    if (s === "failed") return '<span class="groq-status-fail">🔴 API Failed</span>';
    return "";
  }

  function formatWhen(iso) {
    if (!iso) return "Never";
    const d = new Date(iso);
    return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }

  function renderCurrentApi(status) {
    const el = document.getElementById("groq-current-api");
    if (!status.configured) {
      el.innerHTML = `<p class="text-muted">No active Groq API. Add a key below to enable the AI Assistant.</p>`;
      return;
    }
    const name = status.active_key_name || (status.source === "environment" ? "Environment variable" : "Active API");
    const model = status.model || "";
    el.innerHTML = `
      <div class="groq-current-label">Current AI API</div>
      <div class="groq-current-name">🟢 <strong>${escapeHtml(name)}</strong></div>
      <div class="text-muted">Status: Active · Provider: Groq</div>
      ${model ? `<div class="text-muted">Model: ${escapeHtml(model)}</div>` : ""}
      ${status.source === "environment" ? `<div class="text-muted">Using Render environment variable (add a saved key to switch without redeploying).</div>` : ""}`;
  }

  function renderGroqKeysList() {
    const list = document.getElementById("groq-keys-list");
    if (!groqKeys.length) {
      list.innerHTML = `<p class="text-muted">No saved API keys yet. Click <strong>+ Add Groq API</strong> to store keys securely on the server.</p>`;
      return;
    }
    list.innerHTML = groqKeys.map((k) => `
      <div class="groq-key-card ${k.is_active ? "active" : ""}">
        <div class="groq-key-card-head">
          <strong>${escapeHtml(k.name)}</strong>
          <span class="badge ${k.is_active ? "badge-status-completed" : ""}">${statusLabel(k)}</span>
        </div>
        <div class="groq-key-meta text-muted">
          Provider: Groq · Key: ${escapeHtml(k.masked_key || "••••••••")}
          ${k.model ? ` · Model: ${escapeHtml(k.model)}` : ""}
        </div>
        ${k.description ? `<div class="groq-key-desc">${escapeHtml(k.description)}</div>` : ""}
        <div class="groq-key-meta text-muted">Last tested: ${formatWhen(k.last_tested_at)} · Last used: ${formatWhen(k.last_used_at)}</div>
        <div class="groq-key-test">${testStatusBadge(k)} ${k.last_test_message ? `<span class="text-muted">${escapeHtml(k.last_test_message)}</span>` : ""}</div>
        <div class="groq-key-actions flex gap-8 flex-wrap">
          ${k.is_active
            ? '<button type="button" class="btn btn-secondary btn-sm" disabled>Currently Active</button>'
            : `<button type="button" class="btn btn-primary btn-sm" onclick="activateGroqKey(${k.id})">Use This API</button>`}
          <button type="button" class="btn btn-secondary btn-sm" onclick="testGroqKey(${k.id})">Test</button>
          <button type="button" class="btn btn-secondary btn-sm" onclick="openEditGroqKey(${k.id})">Edit</button>
          <button type="button" class="btn btn-danger btn-sm" onclick="deleteGroqKey(${k.id})">Delete</button>
        </div>
      </div>
    `).join("");
  }

  async function loadGroqKeys() {
    try {
      const data = await apiRequest("/api/ai/groq-keys", {
        retries: 8,
        retryDelayMs: 2000,
      });
      groqKeys = data.keys || [];
      renderGroqKeysList();
    } catch (e) {
      document.getElementById("groq-keys-list").innerHTML = `<p>${escapeHtml(e.message)}</p>`;
    }
  }

  window.activateGroqKey = async function (id) {
    try {
      await apiRequest(`/api/ai/groq-keys/${id}/activate`, { method: "POST" });
      showToast("Active Groq API updated");
      await loadGroqKeys();
      await checkStatus();
    } catch (e) {
      showToast(e.message);
    }
  };

  window.testGroqKey = async function (id) {
    try {
      showToast("Testing API...");
      const res = await apiRequest(`/api/ai/groq-keys/${id}/test`, { method: "POST" });
      showToast(res.message || "Test complete");
      await loadGroqKeys();
    } catch (e) {
      showToast(e.message);
    }
  };

  window.openEditGroqKey = function (id) {
    const k = groqKeys.find((x) => x.id === id);
    if (!k) return;
    document.getElementById("edit-groq-key-id").value = k.id;
    document.getElementById("edit-groq-key-name").value = k.name;
    document.getElementById("edit-groq-key-value").value = "";
    document.getElementById("edit-groq-key-model").value = k.model || "";
    document.getElementById("edit-groq-key-description").value = k.description || "";
    document.getElementById("edit-groq-key-error").classList.remove("visible");
    openModal("edit-groq-key-modal");
  };

  window.deleteGroqKey = async function (id) {
    const k = groqKeys.find((x) => x.id === id);
    if (!k) return;
    if (!confirm(`Delete API "${k.name}"? This cannot be undone.`)) return;
    try {
      await apiRequest(`/api/ai/groq-keys/${id}`, { method: "DELETE" });
      showToast("API deleted");
      await loadGroqKeys();
      await checkStatus();
    } catch (e) {
      showToast(e.message);
    }
  };

  document.getElementById("open-add-groq-key-btn").addEventListener("click", () => {
    document.getElementById("add-groq-key-form").reset();
    document.getElementById("add-groq-key-error").classList.remove("visible");
    openModal("add-groq-key-modal");
  });

  document.getElementById("add-groq-key-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("add-groq-key-error");
    err.classList.remove("visible");
    try {
      await apiRequest("/api/ai/groq-keys", {
        method: "POST",
        body: JSON.stringify({
          name: document.getElementById("groq-key-name").value.trim(),
          api_key: document.getElementById("groq-key-value").value.trim(),
          model: document.getElementById("groq-key-model").value.trim(),
          description: document.getElementById("groq-key-description").value.trim(),
        }),
      });
      closeModal("add-groq-key-modal");
      showToast("Groq API saved");
      await loadGroqKeys();
      await checkStatus();
    } catch (ex) {
      err.textContent = ex.message;
      err.classList.add("visible");
    }
  });

  document.getElementById("edit-groq-key-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = document.getElementById("edit-groq-key-error");
    err.classList.remove("visible");
    const id = document.getElementById("edit-groq-key-id").value;
    const payload = {
      name: document.getElementById("edit-groq-key-name").value.trim(),
      model: document.getElementById("edit-groq-key-model").value.trim(),
      description: document.getElementById("edit-groq-key-description").value.trim(),
    };
    const newKey = document.getElementById("edit-groq-key-value").value.trim();
    if (newKey) payload.api_key = newKey;
    try {
      await apiRequest(`/api/ai/groq-keys/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      closeModal("edit-groq-key-modal");
      showToast("API updated");
      await loadGroqKeys();
      await checkStatus();
    } catch (ex) {
      err.textContent = ex.message;
      err.classList.add("visible");
    }
  });

  async function sendMessage(text) {
    if (!text || processing) return;

    appendMessage("user", text);
    history.push({ role: "user", content: text });
    saveHistory();

    input.value = "";
    setProcessing(true, "Connecting to server...");

    try {
      await ensureServerReady();
      setProcessing(true, "AI is working...");

      const data = await apiRequest("/api/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          mode: aiMode,
          history: historyForApi(text, history.slice(0, -1)),
        }),
        retries: 20,
        retryDelayMs: 2500,
        onRetry: (attempt, total, reason) => {
          const label =
            reason === "server_sleeping" || reason === "network"
              ? "Waking up server…"
              : "Retrying…";
          setProcessing(true, label + " attempt " + attempt + " of " + total);
        },
      });

      const reply = (data.reply || "").trim() || "Done.";
      appendMessage("assistant", reply);
      history.push({ role: "assistant", content: reply });
      saveHistory();
    } catch (err) {
      const errText = err.message || "Something went wrong.";
      appendMessage("assistant", "I couldn't complete that request: " + errText);
      /* Do not save errors to history — they waste Groq tokens on the next message */
      saveHistory();
    } finally {
      setProcessing(false);
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(input.value.trim());
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
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

  document.getElementById("clear-ai-chat-btn").addEventListener("click", clearChat);

  if (speakBtn) {
    speakBtn.addEventListener("click", () => {
      if (window.AiVoice && AiVoice.isListening()) return;
      startSpeak();
    });
  }

  if (speakDoneBtn) {
    speakDoneBtn.addEventListener("click", () => finishSpeakAndSend());
  }

  patchAiVoiceApi();
  setAiMode(loadAiMode());

  document.getElementById("ai-mode-chat").addEventListener("click", () => setAiMode("chat"));
  document.getElementById("ai-mode-manage").addEventListener("click", () => setAiMode("manage"));

  setVoiceButtonsEnabled(true);

  if (typeof initMobileNav === "function") {
    initMobileNav();
  }

  history = sanitizeHistoryForApi(loadHistory());
  if (history.length) {
    renderHistory();
  }

  startServerWake().then(() => loadGroqKeys());
  input.focus();
})();
