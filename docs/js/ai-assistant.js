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
          "AI is not configured on the server. Add GROQ_API_KEY in Render environment variables.";
        configWarning.classList.add("visible");
      }
    } catch (e) {
      /* auth redirect handled by apiRequest */
    }
  }

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
  input.focus();
})();
