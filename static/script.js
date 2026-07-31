// ============================================================
// Config
// ============================================================

const API = "/api";

const PROVIDER_COLORS = {
  Groq: "#F97316",
  Gemini: "#60A5FA",
  OpenRouter: "#C084FC",
};

const PROVIDER_INITIALS = {
  Groq: "Gq",
  Gemini: "Ge",
  OpenRouter: "Or",
};

// ============================================================
// State
// ============================================================

let state = {
  sessions: [],
  currentSessionId: null,
  providerModels: {},
  provider: "Groq",
  model: "",
  systemPrompt: "",
  allowSearch: false,
  isStreaming: false,
};

// ============================================================
// DOM refs
// ============================================================

const el = {
  sidebar: document.getElementById("sidebar"),
  app: document.querySelector(".app"),
  sessionsList: document.getElementById("sessionsList"),
  newChatBtn: document.getElementById("newChatBtn"),
  collapseBtn: document.getElementById("collapseBtn"),
  expandBtn: document.getElementById("expandBtn"),
  sessionTitle: document.getElementById("sessionTitle"),
  providerSelect: document.getElementById("providerSelect"),
  providerDot: document.getElementById("providerDot"),
  modelSelect: document.getElementById("modelSelect"),
  searchCheckbox: document.getElementById("searchCheckbox"),
  chatScroll: document.getElementById("chatScroll"),
  emptyState: document.getElementById("emptyState"),
  messages: document.getElementById("messages"),
  userInput: document.getElementById("userInput"),
  sendBtn: document.getElementById("sendBtn"),
  settingsBtn: document.getElementById("settingsBtn"),
  settingsOverlay: document.getElementById("settingsOverlay"),
  closeSettings: document.getElementById("closeSettings"),
  cancelSettings: document.getElementById("cancelSettings"),
  saveSettings: document.getElementById("saveSettings"),
  systemPromptInput: document.getElementById("systemPromptInput"),
};

marked.setOptions({ breaks: true, gfm: true });

// ============================================================
// Init
// ============================================================

async function init() {
  await loadModels();
  await loadSessions();
  bindEvents();
  autoResizeTextarea();

  if (state.sessions.length > 0) {
    await openSession(state.sessions[0].id);
  } else {
    showEmptyState();
  }
}

async function loadModels() {
  const res = await fetch(`${API}/models`);
  state.providerModels = await res.json();

  el.providerSelect.innerHTML = Object.keys(state.providerModels)
    .map((p) => `<option value="${p}">${p}</option>`)
    .join("");

  el.providerSelect.value = state.provider;
  populateModelSelect();
  updateProviderDot();
}

function populateModelSelect() {
  const models = state.providerModels[state.provider] || [];
  el.modelSelect.innerHTML = models.map((m) => `<option value="${m}">${m}</option>`).join("");
  if (!models.includes(state.model)) {
    state.model = models[0] || "";
  }
  el.modelSelect.value = state.model;
}

function updateProviderDot() {
  const color = PROVIDER_COLORS[state.provider] || "#5EEAD4";
  el.providerDot.style.background = color;
}

// ============================================================
// Sessions
// ============================================================

async function loadSessions() {
  const res = await fetch(`${API}/sessions`);
  state.sessions = await res.json();
  renderSessionsList();
}

function renderSessionsList() {
  el.sessionsList.innerHTML = state.sessions
    .map((s) => {
      const color = PROVIDER_COLORS[s.provider] || "#5EEAD4";
      const active = s.id === state.currentSessionId ? "active" : "";
      return `
        <div class="session-item ${active}" data-id="${s.id}">
          <span class="session-dot" style="background:${color}"></span>
          <span class="session-title">${escapeHtml(s.title || "New chat")}</span>
          <button class="session-delete" data-delete="${s.id}" title="Delete">✕</button>
        </div>`;
    })
    .join("");

  el.sessionsList.querySelectorAll(".session-item").forEach((node) => {
    node.addEventListener("click", (e) => {
      if (e.target.closest(".session-delete")) return;
      openSession(node.dataset.id);
    });
  });

  el.sessionsList.querySelectorAll(".session-delete").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await deleteSession(btn.dataset.delete);
    });
  });
}

async function createSession() {
  const res = await fetch(`${API}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: state.provider,
      model: state.model,
      system_prompt: state.systemPrompt,
    }),
  });
  const session = await res.json();
  state.sessions.unshift({ ...session, updated_at: Date.now() / 1000 });
  await openSession(session.id);
  renderSessionsList();
}

async function openSession(id) {
  state.currentSessionId = id;
  const res = await fetch(`${API}/sessions/${id}`);
  if (!res.ok) return;
  const data = await res.json();

  state.provider = data.session.provider;
  state.model = data.session.model;
  state.systemPrompt = data.session.system_prompt || "";

  el.providerSelect.value = state.provider;
  populateModelSelect();
  updateProviderDot();
  el.sessionTitle.textContent = data.session.title || "New chat";

  el.messages.innerHTML = "";
  if (data.messages.length === 0) {
    showEmptyState();
  } else {
    hideEmptyState();
    data.messages.forEach((m) => renderMessage(m.role, m.content, false));
  }

  renderSessionsList();
  scrollToBottom();
}

async function deleteSession(id) {
  await fetch(`${API}/sessions/${id}`, { method: "DELETE" });
  state.sessions = state.sessions.filter((s) => s.id !== id);
  if (state.currentSessionId === id) {
    state.currentSessionId = null;
    el.messages.innerHTML = "";
    el.sessionTitle.textContent = "New chat";
    if (state.sessions.length > 0) {
      await openSession(state.sessions[0].id);
    } else {
      showEmptyState();
    }
  }
  renderSessionsList();
}

function showEmptyState() {
  el.emptyState.style.display = "block";
}
function hideEmptyState() {
  el.emptyState.style.display = "none";
}

// ============================================================
// Messages / rendering
// ============================================================

function renderMessage(role, content, animate) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role === "user" ? "user" : "agent"}`;

  if (role === "user") {
    wrap.innerHTML = `
      <div class="avatar user-avatar">You</div>
      <div class="msg-body">
        <div class="bubble">${escapeHtml(content).replace(/\n/g, "<br>")}</div>
      </div>`;
  } else {
    const color = PROVIDER_COLORS[state.provider] || "#5EEAD4";
    const initials = PROVIDER_INITIALS[state.provider] || "Ag";
    wrap.innerHTML = `
      <div class="avatar agent-avatar" style="--provider-color:${color}">${initials}</div>
      <div class="msg-body">
        <div class="msg-meta">${state.provider} · ${escapeHtml(state.model)}</div>
        <div class="bubble">${renderMarkdown(content)}</div>
      </div>`;
  }

  el.messages.appendChild(wrap);
  enhanceCodeBlocks(wrap);
  return wrap;
}

function renderMarkdown(text) {
  try {
    return marked.parse(text || "");
  } catch (e) {
    return escapeHtml(text || "");
  }
}

function enhanceCodeBlocks(container) {
  container.querySelectorAll("pre code").forEach((block) => {
    try { hljs.highlightElement(block); } catch (e) {}

    const pre = block.parentElement;
    if (pre.parentElement.classList.contains("code-block")) return;

    const lang = (block.className.match(/language-(\w+)/) || [])[1] || "text";

    const wrapper = document.createElement("div");
    wrapper.className = "code-block";

    const header = document.createElement("div");
    header.className = "code-header";
    header.innerHTML = `<span>${lang}</span><button class="copy-btn">Copy</button>`;

    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(header);
    wrapper.appendChild(pre);

    header.querySelector(".copy-btn").addEventListener("click", (e) => {
      navigator.clipboard.writeText(block.textContent);
      e.target.textContent = "Copied";
      e.target.classList.add("copied");
      setTimeout(() => {
        e.target.textContent = "Copy";
        e.target.classList.remove("copied");
      }, 1500);
    });
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function scrollToBottom() {
  el.chatScroll.scrollTop = el.chatScroll.scrollHeight;
}

// ============================================================
// Sending messages (SSE streaming)
// ============================================================

async function sendMessage(text) {
  if (!text.trim() || state.isStreaming) return;

  if (!state.currentSessionId) {
    await createSession();
  }

  hideEmptyState();
  renderMessage("user", text, true);
  scrollToBottom();

  el.userInput.value = "";
  autoResizeTextarea();

  // Agent placeholder bubble
  const agentWrap = document.createElement("div");
  agentWrap.className = "msg agent";
  const color = PROVIDER_COLORS[state.provider] || "#5EEAD4";
  const initials = PROVIDER_INITIALS[state.provider] || "Ag";
  agentWrap.innerHTML = `
    <div class="avatar agent-avatar" style="--provider-color:${color}">${initials}</div>
    <div class="msg-body">
      <div class="msg-meta">${state.provider} · ${escapeHtml(state.model)}</div>
      <div class="bubble"><span class="tool-status" style="display:none" class="tool-badge"></span><span class="stream-text"></span><span class="cursor"></span></div>
    </div>`;
  el.messages.appendChild(agentWrap);
  scrollToBottom();

  const streamTextEl = agentWrap.querySelector(".stream-text");
  const cursorEl = agentWrap.querySelector(".cursor");
  const bubbleEl = agentWrap.querySelector(".bubble");

  state.isStreaming = true;
  updateSendBtn();

  let fullText = "";

  try {
    const res = await fetch(`${API}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: state.currentSessionId,
        message: text,
        provider: state.provider,
        model: state.model,
        system_prompt: state.systemPrompt,
        allow_search: state.allowSearch,
      }),
    });

    if (!res.body) throw new Error("Streaming not supported by this browser.");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();

      for (const chunk of chunks) {
        if (!chunk.startsWith("data: ")) continue;
        const payload = JSON.parse(chunk.slice(6));

        if (payload.type === "delta") {
          fullText += payload.text;
          streamTextEl.innerHTML = renderMarkdown(fullText);
          enhanceCodeBlocks(bubbleEl);
          scrollToBottom();
        } else if (payload.type === "tool") {
          const badge = document.createElement("div");
          badge.className = "tool-badge";
          badge.textContent = "Searching the web…";
          bubbleEl.insertBefore(badge, streamTextEl);
        } else if (payload.type === "title") {
          el.sessionTitle.textContent = payload.title;
          const s = state.sessions.find((s) => s.id === state.currentSessionId);
          if (s) s.title = payload.title;
          renderSessionsList();
        } else if (payload.type === "done") {
          fullText = payload.text || fullText;
          streamTextEl.innerHTML = renderMarkdown(fullText);
          enhanceCodeBlocks(bubbleEl);
          cursorEl.remove();
        } else if (payload.type === "error") {
          const errEl = document.createElement("div");
          errEl.className = "error-bubble";
          errEl.textContent = payload.error || "Something went wrong.";
          bubbleEl.appendChild(errEl);
          cursorEl.remove();
        }
      }
    }
  } catch (err) {
    const errEl = document.createElement("div");
    errEl.className = "error-bubble";
    errEl.textContent = `Connection error: ${err.message}`;
    bubbleEl.appendChild(errEl);
    cursorEl.remove();
  } finally {
    state.isStreaming = false;
    updateSendBtn();
    scrollToBottom();
    await loadSessions();
  }
}

function updateSendBtn() {
  el.sendBtn.disabled = state.isStreaming || !el.userInput.value.trim();
}

// ============================================================
// Textarea auto-resize
// ============================================================

function autoResizeTextarea() {
  el.userInput.style.height = "auto";
  el.userInput.style.height = Math.min(el.userInput.scrollHeight, 200) + "px";
}

// ============================================================
// Events
// ============================================================

function bindEvents() {
  el.newChatBtn.addEventListener("click", async () => {
    state.currentSessionId = null;
    el.messages.innerHTML = "";
    el.sessionTitle.textContent = "New chat";
    showEmptyState();
    renderSessionsList();
  });

  el.collapseBtn.addEventListener("click", () => {
    el.app.classList.add("sidebar-collapsed");
  });
  el.expandBtn.addEventListener("click", () => {
    el.app.classList.toggle("sidebar-collapsed");
  });

  el.providerSelect.addEventListener("change", () => {
    state.provider = el.providerSelect.value;
    populateModelSelect();
    updateProviderDot();
  });

  el.modelSelect.addEventListener("change", () => {
    state.model = el.modelSelect.value;
  });

  el.searchCheckbox.addEventListener("change", () => {
    state.allowSearch = el.searchCheckbox.checked;
  });

  el.userInput.addEventListener("input", () => {
    autoResizeTextarea();
    updateSendBtn();
  });

  el.userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(el.userInput.value);
    }
  });

  el.sendBtn.addEventListener("click", () => sendMessage(el.userInput.value));

  document.querySelectorAll(".suggestion").forEach((btn) => {
    btn.addEventListener("click", () => sendMessage(btn.dataset.text));
  });

  el.settingsBtn.addEventListener("click", () => {
    el.systemPromptInput.value = state.systemPrompt;
    el.settingsOverlay.classList.add("open");
  });
  el.closeSettings.addEventListener("click", closeSettingsModal);
  el.cancelSettings.addEventListener("click", closeSettingsModal);
  el.settingsOverlay.addEventListener("click", (e) => {
    if (e.target === el.settingsOverlay) closeSettingsModal();
  });
  el.saveSettings.addEventListener("click", () => {
    state.systemPrompt = el.systemPromptInput.value;
    closeSettingsModal();
  });
}

function closeSettingsModal() {
  el.settingsOverlay.classList.remove("open");
}

// ============================================================
// Go
// ============================================================

init();
