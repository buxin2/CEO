/* Company group chat */

const GROUP_TOKEN = getQueryParam("token");
const GROUP_STORAGE_KEY = GROUP_TOKEN ? `ceo_group_emp_${GROUP_TOKEN}` : "";

const state = {
  groupToken: GROUP_TOKEN,
  employeeToken: "",
  employeeName: "",
  employeeRole: "",
  isAdmin: false,
  companyId: null,
  companyName: "",
  groupName: "",
  messages: [],
  myReactions: {},
  replyTo: null,
  pollTimer: null,
  lastMessageId: 0,
  threadParentId: null,
};

function employeeSessionKey() {
  return GROUP_STORAGE_KEY;
}

function loadEmployeeSession() {
  if (!GROUP_STORAGE_KEY) return "";
  return sessionStorage.getItem(GROUP_STORAGE_KEY) || "";
}

function saveEmployeeSession(token) {
  if (GROUP_STORAGE_KEY && token) {
    sessionStorage.setItem(GROUP_STORAGE_KEY, token);
  }
}

function clearEmployeeSession() {
  if (GROUP_STORAGE_KEY) sessionStorage.removeItem(GROUP_STORAGE_KEY);
}

function extractYoutubeId(url) {
  const patterns = [
    /youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
    /youtu\.be\/([a-zA-Z0-9_-]{11})/,
    /youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
    /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/,
  ];
  for (const p of patterns) {
    const m = url.match(p);
    if (m) return m[1];
  }
  return null;
}

function formatMessageContent(text) {
  const escaped = escapeHtml(text);
  const withBreaks = escaped.replace(/\n/g, "<br>");
  const urlPattern = /(https?:\/\/[^\s<]+)/gi;
  return withBreaks.replace(urlPattern, (url) => {
    const clean = url.replace(/[.,;:!?)]+$/, "");
    const suffix = url.slice(clean.length);
    const yt = extractYoutubeId(clean);
    if (yt) {
      return (
        `<div class="chat-video-wrap"><iframe src="https://www.youtube.com/embed/${yt}" title="Video" allowfullscreen loading="lazy"></iframe></div>` +
        suffix
      );
    }
    return `<a href="${clean}" target="_blank" rel="noopener noreferrer">${clean}</a>${suffix}`;
  });
}

function formatChatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

async function initGroupPage() {
  if (!GROUP_TOKEN) {
    document.getElementById("group-root").innerHTML =
      '<div class="empty-state"><p>Invalid group link.</p></div>';
    return;
  }

  try {
    const me = await fetch(apiUrl("/api/me"), { credentials: "include" });
    if (me.ok) {
      state.isAdmin = true;
      await initAdminGroup();
      return;
    }
  } catch (e) {
    /* not admin */
  }

  const saved = loadEmployeeSession();
  if (saved) {
    state.employeeToken = saved;
    try {
      await enterGroup(saved);
      return;
    } catch (e) {
      clearEmployeeSession();
    }
  }

  await showEntryScreen();
}

async function showEntryScreen() {
  document.getElementById("entry-screen").classList.remove("hidden");
  document.getElementById("chat-screen").classList.add("hidden");
  document.getElementById("entry-form").classList.remove("hidden");
  document.getElementById("join-request-form").classList.add("hidden");

  const list = document.getElementById("employee-select-list");
  list.innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';

  try {
    const data = await groupApiRequest(`/api/public/group/${GROUP_TOKEN}`, "");
    state.companyName = data.company_name;
    state.groupName = data.company_name + " Group";

    document.getElementById("entry-title").textContent = data.company_name;
    document.getElementById("entry-subtitle").textContent = "Select your name to enter the group";

    if (!data.employees.length) {
      list.innerHTML = "<p class=\"text-muted\">No employees listed yet. Ask your admin to add you.</p>";
      return;
    }

    list.innerHTML = data.employees.map((e) => `
      <label class="employee-select-item">
        <input type="radio" name="employee-pick" value="${escapeHtml(e.unique_token)}">
        <span class="employee-select-name">${escapeHtml(e.name)}</span>
        ${e.position ? `<span class="employee-select-role">${escapeHtml(e.position)}</span>` : ""}
      </label>
    `).join("");
  } catch (err) {
    list.innerHTML = `<div class="empty-state"><p>${escapeHtml(err.message)}</p></div>`;
  }
}

async function enterGroup(employeeToken) {
  const data = await groupApiRequest(`/api/public/group/${GROUP_TOKEN}/enter`, "", {
    method: "POST",
    body: JSON.stringify({ employee_token: employeeToken }),
  });
  state.employeeToken = employeeToken;
  state.employeeName = data.employee.name;
  state.employeeRole = data.employee.position || "";
  saveEmployeeSession(employeeToken);
  showChatScreen(data.company_name, data.group_name);
}

async function initAdminGroup() {
  const companyId = getQueryParam("company_id");
  if (!companyId) {
    await showEntryScreen();
    return;
  }
  state.companyId = companyId;
  const g = await apiRequest(`/api/companies/${companyId}/group`);
  if (g.group_token !== GROUP_TOKEN) {
    await showEntryScreen();
    return;
  }
  state.companyName = g.company_name;
  state.groupName = g.group_name;
  showChatScreen(g.company_name, g.group_name);
}

function showChatScreen(companyName, groupName) {
  document.getElementById("entry-screen").classList.add("hidden");
  document.getElementById("chat-screen").classList.remove("hidden");
  document.getElementById("chat-company-name").textContent = companyName.toUpperCase();
  document.getElementById("chat-group-label").textContent = groupName;
  if (state.isAdmin) {
    document.getElementById("admin-badge").classList.remove("hidden");
    document.getElementById("leave-group-btn").classList.add("hidden");
    document.getElementById("open-my-tasks-btn").classList.add("hidden");
  } else {
    document.getElementById("user-badge").textContent = state.employeeName;
    document.getElementById("leave-group-btn").classList.remove("hidden");
  }
  loadMessages(true);
  startPolling();
}

function startPolling() {
  stopPolling();
  state.pollTimer = setInterval(() => loadMessages(false), 3000);
}

function stopPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = null;
}

async function loadMessages(initial) {
  try {
    let url;
    if (state.isAdmin && state.companyId) {
      url = `/api/companies/${state.companyId}/group/messages`;
      if (!initial && state.lastMessageId) url += `?after_id=${state.lastMessageId}`;
      if (state.threadParentId) url += (url.includes("?") ? "&" : "?") + `parent_id=${state.threadParentId}`;
      const data = await apiRequest(url);
      mergeMessages(data.messages, initial);
    } else {
      url = `/api/public/group/${GROUP_TOKEN}/messages?employee_token=${encodeURIComponent(state.employeeToken)}`;
      if (!initial && state.lastMessageId) url += `&after_id=${state.lastMessageId}`;
      if (state.threadParentId) url += `&parent_id=${state.threadParentId}`;
      const data = await groupApiRequest(url, state.employeeToken);
      state.myReactions = data.my_reactions || {};
      mergeMessages(data.messages, initial);
    }
  } catch (e) {
    if (initial) {
      document.getElementById("messages-list").innerHTML =
        `<div class="empty-state"><p>${escapeHtml(e.message)}</p></div>`;
    }
  }
}

function mergeMessages(newMsgs, initial) {
  if (!newMsgs || !newMsgs.length) {
    if (initial && state.messages.length === 0) {
      document.getElementById("messages-list").innerHTML =
        '<div class="empty-state chat-empty"><p>No messages yet. Start the conversation!</p></div>';
    }
    return;
  }

  const ids = new Set(state.messages.map((m) => m.id));
  newMsgs.forEach((m) => {
    if (!ids.has(m.id)) {
      state.messages.push(m);
      if (m.id > state.lastMessageId) state.lastMessageId = m.id;
    } else {
      const idx = state.messages.findIndex((x) => x.id === m.id);
      if (idx >= 0) state.messages[idx] = m;
    }
  });

  if (!state.threadParentId) {
    state.messages = state.messages.filter((m) => !m.parent_id);
  }

  renderMessages();
}

function renderMessages() {
  const list = document.getElementById("messages-list");
  const msgs = state.threadParentId
    ? state.messages.filter((m) => m.parent_id === state.threadParentId || m.id === state.threadParentId)
    : state.messages.filter((m) => !m.parent_id);

  if (!msgs.length) {
    list.innerHTML = '<div class="empty-state chat-empty"><p>No messages yet.</p></div>';
    return;
  }

  const sorted = [...msgs].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  list.innerHTML = sorted.map(renderMessageCard).join("");

  if (!state.threadParentId) {
    const el = document.getElementById("messages-scroll");
    el.scrollTop = el.scrollHeight;
  }
}

function renderMessageCard(m) {
  if (m.id === state.threadParentId && m.parent_id) return "";

  const myReaction = state.myReactions[m.id] || "";
  const likeClass = myReaction === "like" ? "active" : "";
  const dislikeClass = myReaction === "dislike" ? "active" : "";

  const parentQuote = m.parent_preview
    ? `<div class="chat-reply-quote"><strong>${escapeHtml(m.parent_preview.sender_name)}</strong> ${escapeHtml(m.parent_preview.content)}</div>`
    : "";

  const deleteBtn = state.isAdmin
    ? `<button type="button" class="btn btn-ghost btn-sm chat-delete-btn" onclick="confirmDeleteMessage(${m.id})">Delete</button>`
    : "";

  return `
    <article class="chat-message" id="msg-${m.id}">
      <div class="chat-message-header">
        <span class="chat-sender">${escapeHtml(m.sender_name)}</span>
        <span class="chat-role">${escapeHtml(m.sender_role)}</span>
        <span class="chat-time">${formatChatTime(m.created_at)}</span>
      </div>
      ${parentQuote}
      <div class="chat-message-body">${formatMessageContent(m.content)}</div>
      <div class="chat-message-actions">
        <button type="button" class="chat-react-btn ${likeClass}" onclick="reactMessage(${m.id}, 'like')">👍 ${m.likes || 0}</button>
        <button type="button" class="chat-react-btn ${dislikeClass}" onclick="reactMessage(${m.id}, 'dislike')">👎 ${m.dislikes || 0}</button>
        <button type="button" class="chat-action-btn" onclick="startReply(${m.id}, '${escapeHtml(m.sender_name).replace(/'/g, "\\'")}')">Reply</button>
        ${m.reply_count > 0 ? `<button type="button" class="chat-action-btn" onclick="openThread(${m.id})">💬 ${m.reply_count}</button>` : ""}
        ${deleteBtn}
      </div>
    </article>`;
}

function startReply(id, name) {
  state.replyTo = { id, name };
  document.getElementById("reply-banner").classList.remove("hidden");
  document.getElementById("reply-banner-text").textContent = `Replying to ${name}`;
  document.getElementById("message-input").focus();
}

function cancelReply() {
  state.replyTo = null;
  document.getElementById("reply-banner").classList.add("hidden");
}

async function openThread(parentId) {
  state.threadParentId = parentId;
  state.messages = [];
  state.lastMessageId = 0;
  document.getElementById("thread-banner").classList.remove("hidden");
  document.getElementById("thread-banner-text").textContent = "Viewing replies";
  await loadMessages(true);
}

function closeThread() {
  state.threadParentId = null;
  state.messages = [];
  state.lastMessageId = 0;
  document.getElementById("thread-banner").classList.add("hidden");
  loadMessages(true);
}

async function sendMessage() {
  const input = document.getElementById("message-input");
  const content = input.value.trim();
  if (!content) return;

  const payload = { content };
  if (state.replyTo) payload.parent_id = state.replyTo.id;

  try {
    if (state.isAdmin && state.companyId) {
      await apiRequest(`/api/companies/${state.companyId}/group/messages`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } else {
      await groupApiRequest(`/api/public/group/${GROUP_TOKEN}/messages`, state.employeeToken, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }
    input.value = "";
    cancelReply();
    state.lastMessageId = 0;
    state.messages = [];
    await loadMessages(true);
  } catch (e) {
    showToast(e.message);
  }
}

async function reactMessage(messageId, reaction) {
  if (state.isAdmin) return;
  const current = state.myReactions[messageId];
  const next = current === reaction ? null : reaction;
  try {
    await groupApiRequest(
      `/api/public/group/${GROUP_TOKEN}/messages/${messageId}/react`,
      state.employeeToken,
      { method: "POST", body: JSON.stringify({ reaction: next }) }
    );
    if (next) state.myReactions[messageId] = next;
    else delete state.myReactions[messageId];
    await loadMessages(true);
  } catch (e) {
    showToast(e.message);
  }
}

async function confirmDeleteMessage(id) {
  if (!confirm("Delete this message?")) return;
  try {
    await apiRequest(`/api/group/messages/${id}`, { method: "DELETE" });
    state.messages = state.messages.filter((m) => m.id !== id);
    renderMessages();
    showToast("Message deleted");
  } catch (e) {
    showToast(e.message);
  }
}

async function openMembersModal() {
  openModal("members-modal");
  const body = document.getElementById("members-list");
  body.innerHTML = '<span class="spinner"></span>';
  try {
    let data;
    if (state.isAdmin && state.companyId) {
      data = await apiRequest(`/api/companies/${state.companyId}/group/members`);
    } else {
      data = await groupApiRequest(
        `/api/public/group/${GROUP_TOKEN}/members?employee_token=${encodeURIComponent(state.employeeToken)}`,
        state.employeeToken
      );
    }
    document.getElementById("members-count-label").textContent = `${data.count} Members`;
    body.innerHTML = data.members.map((m) => `
      <div class="member-row">
        <span><strong>${escapeHtml(m.name)}</strong> — ${escapeHtml(m.position)}</span>
        ${state.isAdmin ? `<button class="btn btn-danger btn-sm" onclick="removeMember(${m.employee_id})">Remove</button>` : ""}
      </div>
    `).join("") || "<p>No members yet.</p>";
  } catch (e) {
    body.innerHTML = `<p>${escapeHtml(e.message)}</p>`;
  }
}

async function removeMember(employeeId) {
  if (!confirm("Remove this member from the group? Their employee record and tasks will not be deleted.")) return;
  try {
    await apiRequest(`/api/companies/${state.companyId}/group/members/${employeeId}`, { method: "DELETE" });
    openMembersModal();
    showToast("Member removed from group");
  } catch (e) {
    showToast(e.message);
  }
}

async function openMyTasks() {
  openModal("my-tasks-modal");
  const body = document.getElementById("my-tasks-body");
  body.innerHTML = '<span class="spinner"></span>';
  try {
    const data = await groupApiRequest(
      `/api/public/group/${GROUP_TOKEN}/my-tasks?employee_token=${encodeURIComponent(state.employeeToken)}`,
      state.employeeToken
    );
    const weekLabel = formatDateRange(data.week.week_start, data.week.week_end);
    document.getElementById("my-tasks-week").textContent = weekLabel;
    const stats = data.stats;
    document.getElementById("my-tasks-progress").textContent =
      `Progress: ${stats.completed} / ${stats.total} completed`;

    body.innerHTML = data.tasks.length
      ? data.tasks.map((t) => `
        <div class="my-task-row">
          <button type="button" class="task-checkbox-btn ${t.status === "completed" ? "checked" : ""}"
            onclick="toggleMyTask(${t.id}, '${t.status}')">${t.status === "completed" ? "✓" : ""}</button>
          <span class="${t.status === "completed" ? "completed" : ""}">${escapeHtml(t.title)}</span>
        </div>
      `).join("")
      : "<p>You don't have any tasks for this week.</p>";
  } catch (e) {
    body.innerHTML = `<p>${escapeHtml(e.message)}</p>`;
  }
}

async function toggleMyTask(taskId, status) {
  const action = status === "completed" ? "uncomplete" : "complete";
  try {
    await fetch(apiUrl(`/api/public/tasks/${state.employeeToken}/${taskId}/${action}`), {
      method: "POST",
      credentials: "include",
    });
    openMyTasks();
  } catch (e) {
    showToast(e.message);
  }
}

function showJoinRequestForm() {
  document.getElementById("entry-form").classList.add("hidden");
  document.getElementById("join-request-form").classList.remove("hidden");
}

function hideJoinRequestForm() {
  document.getElementById("join-request-form").classList.add("hidden");
  document.getElementById("entry-form").classList.remove("hidden");
}

document.addEventListener("DOMContentLoaded", () => {
  if (!document.getElementById("group-root")) return;

  document.getElementById("enter-group-btn").addEventListener("click", async () => {
    const picked = document.querySelector('input[name="employee-pick"]:checked');
    if (!picked) {
      showToast("Please select your name");
      return;
    }
    try {
      await enterGroup(picked.value);
    } catch (e) {
      showToast(e.message);
    }
  });

  document.getElementById("show-join-request-btn").addEventListener("click", showJoinRequestForm);
  document.getElementById("cancel-join-request-btn").addEventListener("click", hideJoinRequestForm);

  document.getElementById("submit-join-request-btn").addEventListener("click", async () => {
    const name = document.getElementById("join-name").value.trim();
    const role = document.getElementById("join-role").value.trim();
    if (!name) {
      showToast("Please enter your name");
      return;
    }
    try {
      await groupApiRequest(`/api/public/group/${GROUP_TOKEN}/join-request`, "", {
        method: "POST",
        body: JSON.stringify({ name, role }),
      });
      showToast("Request sent to admin");
      hideJoinRequestForm();
    } catch (e) {
      showToast(e.message);
    }
  });

  document.getElementById("send-message-btn").addEventListener("click", sendMessage);
  document.getElementById("message-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  document.getElementById("cancel-reply-btn").addEventListener("click", cancelReply);
  document.getElementById("close-thread-btn").addEventListener("click", closeThread);
  document.getElementById("open-members-btn").addEventListener("click", openMembersModal);
  document.getElementById("open-my-tasks-btn").addEventListener("click", openMyTasks);
  document.getElementById("leave-group-btn").addEventListener("click", () => {
    clearEmployeeSession();
    stopPolling();
    state.employeeToken = "";
    state.messages = [];
    showEntryScreen();
  });

  initGroupPage();
});
