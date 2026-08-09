(function () {
  const STORAGE_KEY = "ceo_ai_chat_history";
  const messagesEl = document.getElementById("ai-chat-messages");
  const form = document.getElementById("ai-chat-form");
  const input = document.getElementById("ai-chat-input");
  const sendBtn = document.getElementById("ai-send-btn");
  const thinkingEl = document.getElementById("ai-thinking");
  const configWarning = document.getElementById("ai-config-warning");

  let history = [];
  let processing = false;

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

    const label = document.createElement("div");
    label.className = "ai-chat-label";
    label.textContent = role === "user" ? "You" : "AI Assistant";

    const body = document.createElement("div");
    body.className = "ai-chat-body";
    if (role === "user") {
      body.textContent = content;
    } else {
      body.innerHTML = formatAssistantHtml(content);
    }

    wrap.appendChild(label);
    wrap.appendChild(body);
    messagesEl.appendChild(wrap);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderHistory() {
    history.forEach((item) => {
      if (item.role === "user" || item.role === "assistant") {
        appendMessage(item.role, item.content);
      }
    });
  }

  function setProcessing(active) {
    processing = active;
    sendBtn.disabled = active;
    input.disabled = active;
    thinkingEl.classList.toggle("hidden", !active);
    thinkingEl.setAttribute("aria-hidden", active ? "false" : "true");
  }

  async function checkStatus() {
    try {
      const status = await apiRequest("/api/ai/status");
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
      const data = await apiRequest("/api/ai/groq-keys");
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
    setProcessing(true);

    try {
      const data = await apiRequest("/api/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          history: history.slice(0, -1),
        }),
      });

      const reply = (data.reply || "").trim() || "Done.";
      appendMessage("assistant", reply);
      history.push({ role: "assistant", content: reply });
      saveHistory();
    } catch (err) {
      const errText = err.message || "Something went wrong.";
      appendMessage("assistant", "I couldn't complete that request: " + errText);
      history.push({
        role: "assistant",
        content: "I couldn't complete that request: " + errText,
      });
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

  if (typeof initMobileNav === "function") {
    initMobileNav();
  }

  history = loadHistory();
  if (history.length) {
    renderHistory();
  }

  checkStatus();
  loadGroqKeys();
  input.focus();
})();
