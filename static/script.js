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

const TOOL_LABELS = {
  tavily_search_results_json: "Searched the web",
  search_documents: "Searched your documents",
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
  autoRoute: false,
  isStreaming: false,
  documents: [],
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
  autoRouteCheckbox: document.getElementById("autoRouteCheckbox"),
  providerSelectWrap: document.getElementById("providerSelectWrap"),
  modelSelectWrap: document.getElementById("modelSelectWrap"),
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
  attachBtn: document.getElementById("attachBtn"),
  fileInput: document.getElementById("fileInput"),
  docsBtn: document.getElementById("docsBtn"),
  docsCount: document.getElementById("docsCount"),
  docsOverlay: document.getElementById("docsOverlay"),
  closeDocs: document.getElementById("closeDocs"),
  closeDocsBtn: document.getElementById("closeDocsBtn"),
  uploadTriggerBtn: document.getElementById("uploadTriggerBtn"),
  docsList: document.getElementById("docsList"),
  docsEmpty: document.getElementById("docsEmpty"),
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
  state.documents = data.documents || [];

  el.providerSelect.value = state.provider;
  populateModelSelect();
  updateProviderDot();
  el.sessionTitle.textContent = data.session.title || "New chat";

  el.messages.innerHTML = "";
  if (data.messages.length === 0) {
    showEmptyState();
  } else {
    hideEmptyState();
    data.messages.forEach((m) => renderMessage(m.role, m.content, m.trace, m.usage));
  }

  renderSessionsList();
  renderDocsBadge();
  scrollToBottom();
}

async function deleteSession(id) {
  await fetch(`${API}/sessions/${id}`, { method: "DELETE" });
  state.sessions = state.sessions.filter((s) => s.id !== id);
  if (state.currentSessionId === id) {
    state.currentSessionId = null;
    state.documents = [];
    el.messages.innerHTML = "";
    el.sessionTitle.textContent = "New chat";
    renderDocsBadge();
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
// Documents (RAG)
// ============================================================

function renderDocsBadge() {
  el.docsCount.textContent = state.documents.length;
  el.docsBtn.classList.toggle("has-docs", state.documents.length > 0);
}

function renderDocsList() {
  if (state.documents.length === 0) {
    el.docsList.innerHTML = `<div class="docs-empty">No documents uploaded to this chat yet.</div>`;
    return;
  }
  el.docsList.innerHTML = state.documents
    .map(
      (d) => `
      <div class="doc-item" data-id="${d.id}">
        <span class="doc-icon">📄</span>
        <div class="doc-info">
          <div class="doc-name">${escapeHtml(d.filename)}</div>
          <div class="doc-meta">${d.chunk_count} chunk${d.chunk_count === 1 ? "" : "s"}</div>
        </div>
        <button class="doc-remove" data-remove="${d.id}" title="Remove">✕</button>
      </div>`
    )
    .join("");

  el.docsList.querySelectorAll(".doc-remove").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`${API}/sessions/${state.currentSessionId}/documents/${btn.dataset.remove}`, {
        method: "DELETE",
      });
      state.documents = state.documents.filter((d) => d.id !== btn.dataset.remove);
      renderDocsList();
      renderDocsBadge();
    });
  });
}

async function uploadFile(file) {
  if (!state.currentSessionId) {
    await createSession();
  }

  const formData = new FormData();
  formData.append("file", file);

  const uploadingNote = document.createElement("div");
  uploadingNote.className = "docs-empty";
  uploadingNote.textContent = `Processing ${file.name}…`;
  el.docsList.prepend(uploadingNote);

  try {
    const res = await fetch(`${API}/sessions/${state.currentSessionId}/documents`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "Upload failed.");
      return;
    }

    state.documents.push(data);
    renderDocsBadge();
    renderDocsList();
  } catch (err) {
    alert(`Upload failed: ${err.message}`);
  } finally {
    uploadingNote.remove();
  }
}

// ============================================================
// Messages / rendering
// ============================================================

function renderMessage(role, content, trace, usage) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role === "user" ? "user" : "agent"}`;

  if (role === "user") {
    wrap.innerHTML = `
      <div class="avatar user-avatar">You</div>
      <div class="msg-body">
        <div class="bubble">${escapeHtml(content).replace(/\n/g, "<br>")}</div>
      </div>`;
    el.messages.appendChild(wrap);
    return wrap;
  }

  const msgProvider = (usage && usage.provider) || state.provider;
  const msgModel = (usage && usage.model) || state.model;
  const color = PROVIDER_COLORS[msgProvider] || "#5EEAD4";
  const initials = PROVIDER_INITIALS[msgProvider] || "Ag";

  wrap.innerHTML = `
    <div class="avatar agent-avatar" style="--provider-color:${color}">${initials}</div>
    <div class="msg-body">
      <div class="msg-meta">${escapeHtml(msgProvider)} · ${escapeHtml(msgModel)}</div>
      <div class="trace-slot"></div>
      <div class="bubble">${renderMarkdown(content)}</div>
      <div class="usage-slot"></div>
    </div>`;

  el.messages.appendChild(wrap);

  if (trace && trace.length > 0) {
    const slot = wrap.querySelector(".trace-slot");
    slot.appendChild(buildTracePanel(trace, false));
  }
  if (usage) {
    wrap.querySelector(".usage-slot").appendChild(buildUsageFooter(usage));
  }

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
// Reasoning trace panel
// ============================================================

function buildTracePanel(steps, live) {
  const panel = document.createElement("div");
  panel.className = "trace-panel";

  const stepCount = steps.filter((s) => s.type === "tool_call").length;

  panel.innerHTML = `
    <button class="trace-toggle" type="button">
      ${live ? '<span class="trace-live-dot"></span>' : "🧭"}
      <span class="trace-toggle-label">${live ? "Thinking…" : `Reasoning · ${stepCount} step${stepCount === 1 ? "" : "s"}`}</span>
      <span class="trace-caret">▾</span>
    </button>
    <div class="trace-steps"></div>
  `;

  if (live) panel.classList.add("open");

  const stepsEl = panel.querySelector(".trace-steps");
  steps.forEach((s) => stepsEl.appendChild(buildTraceStep(s)));

  panel.querySelector(".trace-toggle").addEventListener("click", () => {
    panel.classList.toggle("open");
  });

  return panel;
}

function buildTraceStep(step) {
  const div = document.createElement("div");

  if (step.type === "route") {
    div.className = "trace-step route";
    div.innerHTML = `
      <div class="trace-icon">🧭</div>
      <div class="trace-content">
        <div class="trace-label">Routed to ${escapeHtml(step.provider)} · ${escapeHtml(step.model)}</div>
        <div class="trace-detail">${escapeHtml(step.reason || "")}</div>
      </div>`;
  } else if (step.type === "tool_call") {
    div.className = "trace-step call";
    const label = TOOL_LABELS[step.name] || `Called ${step.name}`;
    div.innerHTML = `
      <div class="trace-icon">🔍</div>
      <div class="trace-content">
        <div class="trace-label">${escapeHtml(label)}</div>
        <div class="trace-detail">${escapeHtml(step.query || "…")}</div>
      </div>`;
  } else if (step.type === "tool_result") {
    div.className = "trace-step result";
    div.innerHTML = `
      <div class="trace-icon">📄</div>
      <div class="trace-content">
        <div class="trace-label">Result</div>
        <div class="trace-detail">${escapeHtml((step.result || "").slice(0, 600))}</div>
      </div>`;
  }

  return div;
}

function buildUsageFooter(usage) {
  const div = document.createElement("div");
  div.className = "msg-usage";
  const routedTag = usage.routed ? `<span class="usage-routed">🧭 auto-routed</span><span class="usage-sep">·</span>` : "";
  const costStr = usage.cost < 0.0001 && usage.cost > 0 ? "<$0.0001" : `$${usage.cost.toFixed(4)}`;
  div.innerHTML = `
    ${routedTag}
    <span>~${usage.total_tokens.toLocaleString()} tok</span>
    <span class="usage-sep">·</span>
    <span>${costStr}</span>
    <span class="usage-sep">·</span>
    <span>${usage.latency_ms}ms</span>
  `;
  return div;
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
  renderMessage("user", text, null);
  scrollToBottom();

  el.userInput.value = "";
  autoResizeTextarea();

  // Agent placeholder message
  const agentWrap = document.createElement("div");
  agentWrap.className = "msg agent";
  const initialProvider = state.autoRoute ? null : state.provider;
  const color = initialProvider ? (PROVIDER_COLORS[initialProvider] || "#5EEAD4") : "var(--ember)";
  const initials = initialProvider ? (PROVIDER_INITIALS[initialProvider] || "Ag") : "🧭";
  const metaText = initialProvider ? `${state.provider} · ${state.model}` : "Routing…";

  agentWrap.innerHTML = `
    <div class="avatar agent-avatar" style="--provider-color:${color}">${initials}</div>
    <div class="msg-body">
      <div class="msg-meta">${escapeHtml(metaText)}</div>
      <div class="trace-slot"></div>
      <div class="bubble"><span class="stream-text"></span><span class="cursor"></span></div>
      <div class="usage-slot"></div>
    </div>`;
  el.messages.appendChild(agentWrap);
  scrollToBottom();

  const avatarEl = agentWrap.querySelector(".avatar");
  const metaEl = agentWrap.querySelector(".msg-meta");
  const traceSlot = agentWrap.querySelector(".trace-slot");
  const usageSlot = agentWrap.querySelector(".usage-slot");
  const streamTextEl = agentWrap.querySelector(".stream-text");
  const cursorEl = agentWrap.querySelector(".cursor");
  const bubbleEl = agentWrap.querySelector(".bubble");

  const liveTraceSteps = [];
  let tracePanel = null;

  function ensureTracePanel() {
    if (!tracePanel) {
      tracePanel = buildTracePanel(liveTraceSteps, true);
      traceSlot.appendChild(tracePanel);
    }
    return tracePanel;
  }

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
        auto_route: state.autoRoute,
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

        } else if (payload.type === "route") {
          const panel = ensureTracePanel();
          const step = { type: "route", provider: payload.provider, model: payload.model, reason: payload.reason };
          liveTraceSteps.unshift(step);
          panel.querySelector(".trace-steps").prepend(buildTraceStep(step));

          const rColor = PROVIDER_COLORS[payload.provider] || "#5EEAD4";
          const rInitials = PROVIDER_INITIALS[payload.provider] || "Ag";
          avatarEl.style.setProperty("--provider-color", rColor);
          avatarEl.textContent = rInitials;
          metaEl.textContent = `${payload.provider} · ${payload.model} (auto-routed)`;
          scrollToBottom();

        } else if (payload.type === "tool_call") {
          const panel = ensureTracePanel();
          const step = { type: "tool_call", name: payload.name, query: payload.query };
          liveTraceSteps.push(step);
          panel.querySelector(".trace-steps").appendChild(buildTraceStep(step));
          const count = liveTraceSteps.filter((s) => s.type === "tool_call").length;
          panel.querySelector(".trace-toggle-label").textContent = `Working · ${count} step${count === 1 ? "" : "s"}`;
          scrollToBottom();

        } else if (payload.type === "tool_result") {
          const panel = ensureTracePanel();
          const step = { type: "tool_result", name: payload.name, result: payload.result };
          liveTraceSteps.push(step);
          panel.querySelector(".trace-steps").appendChild(buildTraceStep(step));
          scrollToBottom();

        } else if (payload.type === "usage") {
          usageSlot.appendChild(buildUsageFooter(payload));

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

          if (tracePanel) {
            const count = liveTraceSteps.filter((s) => s.type === "tool_call").length;
            tracePanel.classList.remove("open");
            tracePanel.querySelector(".trace-toggle").innerHTML = `
              🧭 <span class="trace-toggle-label">Reasoning · ${count} step${count === 1 ? "" : "s"}</span>
              <span class="trace-caret">▾</span>`;
            tracePanel.querySelector(".trace-toggle").addEventListener("click", () => {
              tracePanel.classList.toggle("open");
            });
          }

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
    state.documents = [];
    el.messages.innerHTML = "";
    el.sessionTitle.textContent = "New chat";
    showEmptyState();
    renderSessionsList();
    renderDocsBadge();
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

  el.autoRouteCheckbox.addEventListener("change", () => {
    state.autoRoute = el.autoRouteCheckbox.checked;
    el.providerSelectWrap.classList.toggle("disabled", state.autoRoute);
    el.modelSelectWrap.classList.toggle("disabled", state.autoRoute);
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

  // Documents
  el.attachBtn.addEventListener("click", () => el.fileInput.click());
  el.uploadTriggerBtn.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", async () => {
    if (el.fileInput.files.length > 0) {
      await uploadFile(el.fileInput.files[0]);
      el.fileInput.value = "";
    }
  });

  el.docsBtn.addEventListener("click", () => {
    renderDocsList();
    el.docsOverlay.classList.add("open");
  });
  el.closeDocs.addEventListener("click", closeDocsModal);
  el.closeDocsBtn.addEventListener("click", closeDocsModal);
  el.docsOverlay.addEventListener("click", (e) => {
    if (e.target === el.docsOverlay) closeDocsModal();
  });
}

function closeSettingsModal() {
  el.settingsOverlay.classList.remove("open");
}
function closeDocsModal() {
  el.docsOverlay.classList.remove("open");
}

// ============================================================
// Go
// ============================================================

init();
