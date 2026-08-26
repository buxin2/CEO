(function () {
  let ideas = [];
  let selectedId = null;
  let newIdeaMode = false;

  function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  }

  function relativeDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 86400000;
    if (diff < 1) return "Updated today";
    if (diff < 2) return "Updated yesterday";
    return "Updated " + formatDate(iso);
  }

  async function loadIdeas() {
    const q = document.getElementById("ideas-search").value.trim();
    const url = "/api/ideas" + (q ? "?search=" + encodeURIComponent(q) : "");
    const data = await apiRequest(url);
    ideas = data.ideas || [];
    renderList();
  }

  function renderList() {
    const el = document.getElementById("ideas-list");
    el.innerHTML = ideas.map((i) => `
      <div class="ideas-list-item ${selectedId === i.id ? "active" : ""}" data-id="${i.id}">
        <h4>${escapeHtml(i.title)}</h4>
        <p class="text-muted" style="font-size:12px;margin:0;">${escapeHtml(i.preview || "")}</p>
        <p class="text-muted" style="font-size:11px;margin:4px 0 0;">${escapeHtml(i.status)} · ${relativeDate(i.updated_at)}</p>
      </div>`).join("") || "<p class=\"text-muted\">No ideas yet.</p>";
    el.querySelectorAll(".ideas-list-item").forEach((node) => {
      node.addEventListener("click", () => openIdea(parseInt(node.dataset.id, 10)));
    });
  }

  function renderStructured(idea) {
    const s = idea.structured || {};
    const sections = [
      { key: "concept", label: "💡 Concept" },
      { key: "goal", label: "🎯 Goal" },
      { key: "target_users", label: "👥 Target Users" },
      { key: "target_market", label: "🌍 Target Market" },
      { key: "business_model", label: "💰 Business Model" },
    ];
    let html = "";
    if (idea.narrative_summary) {
      html += `<h4>🧠 Summary</h4><div style="margin-bottom:12px;">${formatMd(idea.narrative_summary)}</div>`;
    }
    sections.forEach(({ key, label }) => {
      if (s[key]) html += `<h4>${label}</h4><p>${escapeHtml(s[key])}</p>`;
    });
    const lists = [
      ["requirements", "⚙️ Requirements"],
      ["decisions", "✅ Decisions"],
      ["problems", "⚠️ Problems"],
      ["open_questions", "❓ Open Questions"],
      ["goals", "🎯 Goals"],
      ["next_steps", "🚀 Next Steps"],
    ];
    lists.forEach(([key, label]) => {
      const items = s[key] || [];
      if (!items.length) return;
      html += `<h4>${label}</h4><ul>`;
      items.forEach((item) => {
        if (key === "decisions" && item && item.text) {
          html += `<li>${escapeHtml(item.text)}</li>`;
        } else if (key === "next_steps" && item && item.text) {
          html += `<li>${item.done ? "☑" : "☐"} ${escapeHtml(item.text)}</li>`;
        } else if (typeof item === "string") {
          html += `<li>${escapeHtml(item)}</li>`;
        }
      });
      html += "</ul>";
    });
    if (idea.links && idea.links.length) {
      html += "<h4>🔗 Related</h4><ul>";
      idea.links.forEach((lnk) => {
        html += `<li>${escapeHtml(lnk.link_type)}: ${escapeHtml(lnk.label || String(lnk.link_id))}</li>`;
      });
      html += "</ul>";
    }
    document.getElementById("idea-summary-panel").innerHTML = html || "<p class=\"text-muted\">Discuss with AI to build the idea summary.</p>";
  }

  function formatMd(text) {
    return escapeHtml(text || "").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br>");
  }

  function renderMessages(messages) {
    const box = document.getElementById("ideas-chat-messages");
    box.innerHTML = (messages || []).map((m) => `
      <div class="ai-chat-bubble ai-chat-bubble-${m.role === "user" ? "user" : "assistant"}">
        <div class="ai-chat-label">${m.role === "user" ? "You" : "AI"}</div>
        <div>${formatMd(m.content)}</div>
        ${m.role === "assistant" && window.AiVoice ? "" : ""}
      </div>`).join("");
    box.scrollTop = box.scrollHeight;
    if (window.AiVoice) {
      box.querySelectorAll(".ai-chat-bubble-assistant").forEach((bubble, idx) => {
        const msgs = messages.filter((m) => m.role === "assistant");
        const content = msgs[idx] && msgs[idx].content;
        if (content) {
          const row = document.createElement("div");
          row.className = "ai-chat-label-row";
          row.appendChild(AiVoice.createPlayButton(content));
          bubble.appendChild(row);
        }
      });
    }
  }

  function renderTimeline(events) {
    document.getElementById("idea-timeline").innerHTML = (events || []).map((e) => `
      <div style="margin-bottom:8px;font-size:13px;">
        <strong>${formatDate(e.created_at)}</strong> — ${escapeHtml(e.description)}
      </div>`).join("") || "<p class=\"text-muted\">No timeline events yet.</p>";
  }

  function showDetail(idea) {
    document.getElementById("ideas-empty").classList.add("hidden");
    document.getElementById("ideas-detail").classList.remove("hidden");
    document.getElementById("idea-title-label").textContent = idea.title;
    document.getElementById("idea-meta-label").innerHTML =
      `Created: ${formatDate(idea.created_at)} · Last updated: ${formatDate(idea.updated_at)} · Status: ${escapeHtml(idea.status)}`;
    document.getElementById("idea-status-select").value = idea.status === "archived" ? "on_hold" : idea.status;
    document.getElementById("idea-priority-select").value = idea.priority || "medium";
    renderStructured(idea);
    renderTimeline(idea.events);
    renderMessages(idea.messages);
  }

  async function openIdea(id) {
    newIdeaMode = false;
    selectedId = id;
    renderList();
    const idea = await apiRequest(`/api/ideas/${id}`);
    idea.messages = idea.messages || (await apiRequest(`/api/ideas/${id}/messages`)).messages;
    showDetail(idea);
  }

  async function sendMessage(text) {
    const message = (text || document.getElementById("ideas-chat-input").value).trim();
    if (!message) return;
    document.getElementById("ideas-chat-input").value = "";

    const body = { message };
    if (newIdeaMode || !selectedId) {
      body.create_new = true;
    } else {
      body.idea_id = selectedId;
    }

    const data = await apiRequest("/api/ideas/chat", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (data.created) {
      selectedId = data.idea.id;
      newIdeaMode = false;
      await loadIdeas();
    }
    showDetail(data.idea);
    if (data.idea.messages) {
      renderMessages(data.idea.messages);
    }
  }

  document.getElementById("new-idea-btn").addEventListener("click", () => {
    selectedId = null;
    newIdeaMode = true;
    renderList();
    document.getElementById("ideas-empty").classList.add("hidden");
    document.getElementById("ideas-detail").classList.remove("hidden");
    document.getElementById("idea-title-label").textContent = "New Idea";
    document.getElementById("idea-meta-label").textContent = "Describe your idea to AI — no form required.";
    document.getElementById("idea-summary-panel").innerHTML = "";
    document.getElementById("idea-timeline").innerHTML = "";
    document.getElementById("ideas-chat-messages").innerHTML = "";
    document.getElementById("ideas-chat-input").focus();
  });

  document.getElementById("ideas-send-btn").addEventListener("click", () => sendMessage());
  document.getElementById("ideas-search").addEventListener("input", () => loadIdeas());

  document.getElementById("idea-status-select").addEventListener("change", async (e) => {
    if (!selectedId) return;
    await apiRequest(`/api/ideas/${selectedId}`, {
      method: "PUT",
      body: JSON.stringify({ status: e.target.value }),
    });
    await loadIdeas();
  });

  document.getElementById("idea-priority-select").addEventListener("change", async (e) => {
    if (!selectedId) return;
    await apiRequest(`/api/ideas/${selectedId}`, {
      method: "PUT",
      body: JSON.stringify({ priority: e.target.value }),
    });
    await loadIdeas();
  });

  document.getElementById("archive-idea-btn").addEventListener("click", async () => {
    if (!selectedId) return;
    await apiRequest(`/api/ideas/${selectedId}/archive`, { method: "POST" });
    selectedId = null;
    document.getElementById("ideas-detail").classList.add("hidden");
    document.getElementById("ideas-empty").classList.remove("hidden");
    await loadIdeas();
  });

  document.getElementById("delete-idea-btn").addEventListener("click", async () => {
    if (!selectedId || !confirm("Permanently delete this idea?")) return;
    await apiRequest(`/api/ideas/${selectedId}`, { method: "DELETE" });
    selectedId = null;
    document.getElementById("ideas-detail").classList.add("hidden");
    document.getElementById("ideas-empty").classList.remove("hidden");
    await loadIdeas();
  });

  document.querySelectorAll(".idea-action").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!selectedId) return;
      const action = btn.dataset.action;
      const data = await apiRequest(`/api/ideas/${selectedId}/action/${action}`, { method: "POST", body: "{}" });
      showDetail({ ...data.idea, messages: data.messages });
      showToast("AI action complete");
    });
  });

  if (window.AiVoice) {
    document.getElementById("ideas-speak-btn").addEventListener("click", () => {
      const input = document.getElementById("ideas-chat-input");
      AiVoice.startListening(input, (err) => showToast(err || "Voice failed"));
    });
  }

  (async function init() {
    try {
      if (typeof wakeApiServer === "function") await wakeApiServer();
      await apiRequest("/api/me");
    } catch (e) {
      window.location.href = pageUrl("login.html");
      return;
    }
    await loadIdeas();
    if (typeof initMobileNav === "function") initMobileNav();
  })();
})();
