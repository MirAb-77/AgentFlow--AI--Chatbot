# Personal Agentic AI Chatbot

A multi-provider, tool-using LangGraph agent exposed through a FastAPI backend and a custom, dependency-light frontend. Supports three interchangeable LLM providers, retrieval-augmented generation over user-uploaded documents, live web search, per-message reasoning trace introspection, rule-based model routing, and per-message usage/cost accounting — all persisted in SQLite behind a single-process deployment.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.10-1C3C3C?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-storage-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](#license)

---

## 📷 Screenshots

**Landing page — hero + live provider-routing diagram**
![Landing hero](docs/screenshots/landing-hero.png)

**Landing page — process breakdown and capability grid**
![Landing features](docs/screenshots/landing-features.png)

**Chat interface — empty state, provider/model selection, auto-route toggle**
![Chat empty state](docs/screenshots/chat-empty.png)

**Chat interface — active conversation with per-message usage footer (`~654 tok · $0.0005 · 2056ms`)**
![Chat conversation](docs/screenshots/chat-conversation.png)

**Analytics dashboard — token/cost/latency aggregation by provider and by day**
![Analytics dashboard](docs/screenshots/analytics-dashboard.png)

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Frontend (static/, served by FastAPI StaticFiles)         │
│ index.html (landing) · chat.html (app) · analytics.html   │
│ script.js — fetch() + ReadableStream SSE consumer          │
└───────────────────────────┬──────────────────────────────┘
                             │ HTTP / SSE (text/event-stream)
┌───────────────────────────▼──────────────────────────────┐
│ backend.py — FastAPI application                          │
│  ├─ Session CRUD (SQLite: sessions, messages)              │
│  ├─ Document CRUD (SQLite: documents, doc_chunks)           │
│  ├─ POST /api/chat/stream — SSE event generator             │
│  ├─ GET  /api/analytics/summary — aggregate SQL queries      │
│  └─ router.py — rule-based provider/model classifier         │
└───────────────────────────┬──────────────────────────────┘
                             │
┌───────────────────────────▼──────────────────────────────┐
│ ai_agent.py — LangGraph ReAct agent construction            │
│  ├─ create_react_agent(model, tools, prompt=...)             │
│  ├─ agent.stream(state, stream_mode="messages")                │
│  │    → yields AIMessageChunk (deltas) + ToolMessage (results)│
│  └─ tools: TavilySearchResults · StructuredTool(search_documents)│
└───────────────────────────┬──────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   ChatGroq             ChatGoogleGenerativeAI   ChatOpenAI
   (Groq API)            (Gemini API)             (OpenRouter,
                                                    base_url override)
```

### Request lifecycle (`POST /api/chat/stream`)

1. Client posts `{session_id, message, provider, model, system_prompt, allow_search, auto_route}`.
2. If `auto_route=true`, `router.classify_and_route()` overrides `provider`/`model` via regex-based intent classification (see [Routing](#-routing-logic)); the decision is emitted as an SSE `route` event and prepended to the trace log.
3. Full message history is pulled from SQLite (`messages` table, ordered by `id`) and converted to LangGraph state via `_history_to_state()`.
4. If the session has rows in `documents`, a closure `search_documents(query: str) -> str` is bound as a `StructuredTool` and appended to the agent's tool list.
5. `agent.stream(state, stream_mode="messages")` is iterated. Each yielded `(chunk, metadata)` tuple is inspected:
   - `AIMessageChunk` with `.content` → forwarded as an SSE `delta` event, accumulated into `full_text`.
   - `AIMessageChunk` with `.tool_call_chunks` → accumulated by tool-call `id` into a pending-calls dict (tool-call arguments arrive fragmented across multiple chunks and must be concatenated before JSON-parsing).
   - `ToolMessage` → signals a tool call resolved; the corresponding pending call is matched, its `query` argument extracted, and `tool_call` + `tool_result` SSE events are emitted.
6. On stream completion: latency is measured (`time.perf_counter()` delta), token counts are estimated (`len(text) // 4`), cost is computed against the static table in `router.py`, and the assistant message — content, trace (JSON), usage (JSON) — is written to SQLite in one transaction, alongside a row in `usage_events` for analytics aggregation.
7. Final `usage` and `done` SSE events are emitted.

---

## 🧩 Core modules

| File | Responsibility |
|---|---|
| `ai_agent.py` | LLM factory (`_build_llm`), tool factory (`_build_tools`), agent factory (`_build_agent`), history→state conversion, streaming/non-streaming agent invocation, content-block normalization across providers (Gemini returns list-of-dict content blocks; Groq/OpenRouter return plain strings) |
| `backend.py` | FastAPI app, SQLite schema + migrations, all REST/SSE endpoints, SSE event serialization, per-request document-search-tool binding |
| `rag.py` | Text extraction (`pypdf` for PDF, UTF-8 decode otherwise), fixed-window chunking with overlap, Gemini embedding calls (`text-embedding-004`), cosine similarity ranking (`numpy`) |
| `router.py` | Regex-based query classifier, `(provider, model) → (cost_in, cost_out)` pricing table, token estimation, cost estimation |
| `static/script.js` | SSE client (manual `ReadableStream` parsing — `EventSource` isn't used because it can't send a POST body), session/document/trace state management, DOM rendering |

---

## ⚙️ Backend internals

### Database schema (SQLite, `chat_history.db`)

```sql
sessions(id TEXT PK, title, provider, model, system_prompt, created_at, updated_at)
messages(id INTEGER PK, session_id, role, content, trace TEXT, usage TEXT, created_at)
documents(id TEXT PK, session_id, filename, chunk_count, created_at)
doc_chunks(id INTEGER PK, document_id, session_id, filename, chunk_text, embedding TEXT)
usage_events(id INTEGER PK, session_id, provider, model,
             input_tokens_est, output_tokens_est, cost_est, latency_ms, routed, created_at)
```

`trace` and `usage` are JSON-serialized columns — chosen over normalized tables because they're written once, read once per message render, and never queried/filtered independently of their parent message. `embedding` is a JSON-serialized `float` array (not a native vector type — SQLite has none by default), decoded and compared via `numpy` at query time rather than at the database layer, which is the deliberate cost/complexity tradeoff of skipping a dedicated vector store.

Schema migrations are handled inline via `PRAGMA table_info()` checks + conditional `ALTER TABLE ADD COLUMN` on startup (`_column_exists()` in `backend.py`), rather than a migration framework — appropriate for a single-table-family SQLite app, not appropriate if this schema grows further.

### Retrieval (`rag.py`)

- Chunking: fixed 900-character windows, 150-character overlap, no semantic/sentence-boundary awareness (`chunk_text()`).
- Embedding: `GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")`, called regardless of the active chat provider — document embeddings always go through Gemini, independent of whether the conversation itself is on Groq/Gemini/OpenRouter.
- Retrieval: brute-force cosine similarity over all chunks belonging to a session (`rank_chunks()`), top-*k*=4. No ANN index — acceptable at the scale of a single user's uploaded documents, not acceptable past a few thousand chunks per session.

### Routing logic (`router.py`)

Classification is three ordered regex/length checks, first match wins:

1. `CODE_PATTERN` — triple backticks, `function`/`class`/`def`/`error`/`debug`/`exception`/`bug`/`compile`/`stack trace`/`refactor` → routes to `Groq / llama-3.3-70b-versatile`.
2. `REASONING_PATTERN` (`why`/`explain`/`analyz*`/`compare`/`pros and cons`/`trade-?offs?`/`step by step`/`summar*`) **or** word count > 60 → routes to `Gemini / gemini-2.5-flash`.
3. Word count ≤ 12 → `Groq / llama-3.1-8b-instant`.
4. Fallback → `OpenRouter / qwen/qwen3.5-9b`.

This is intentionally a rule-based classifier, not a learned or LLM-based one — zero added latency, zero added cost, fully deterministic and auditable, at the cost of being a coarser signal than an actual complexity-scoring model would provide.

### Cost estimation

Token counts are a `len(text) // 4` heuristic — no tokenizer dependency (`tiktoken`, provider-specific tokenizers) is loaded. This is accurate to within the usual ±15–20% margin for English prose and meaningfully wrong for code-heavy or non-English text. The `COST_TABLE` in `router.py` is a static, manually-maintained `(provider, model) → (usd_per_1M_input, usd_per_1M_output)` dict sourced from provider pricing pages at time of writing — it does not call any pricing API and will drift as providers change rates.

---

## 🖥️ Frontend internals

No build step, no framework, no bundler. Three static HTML entry points share `style.css` (design tokens: CSS custom properties for color/spacing/typography) and load page-specific CSS/JS:

- `index.html` + `landing.css` + `landing.js` — marketing/explainer page, `IntersectionObserver`-driven scroll reveals, CSS-animated SVG connector lines in the hero diagram.
- `chat.html` + `script.js` — the application. State lives in a single in-memory `state` object (no framework reactivity); DOM updates are direct `innerHTML`/`querySelector` mutations.
- `analytics.html` + `analytics.css` + `analytics.js` — fetches `/api/analytics/summary` once, renders stat cards and two hand-rolled charts (`div`-based horizontal bars for cost-by-provider, flexbox column bars for daily activity) with no charting library.

### SSE consumption

`EventSource` is not used, because the request requires a JSON POST body (`EventSource` only supports GET). Instead, `fetch()` returns a `ReadableStream`, manually decoded and split on `\n\n` frame boundaries:

```js
const reader = res.body.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const chunks = buffer.split("\n\n");
  buffer = chunks.pop();          // last (possibly incomplete) frame stays buffered
  for (const chunk of chunks) { /* parse `data: {...}` */ }
}
```

### Markdown/code rendering

`marked.js` parses response text to HTML on every delta (re-parsed from scratch per token batch, not incrementally — acceptable at typical response lengths, would need diffing at much larger outputs). `highlight.js` runs on each `<pre><code>` block after parse; a `MutationObserver`-free approach is used — code blocks are re-scanned and copy buttons re-attached via `enhanceCodeBlocks()` after every markdown re-render.

---

## 🔌 API reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/models` | Returns `{provider: [model, ...]}` map |
| `GET` | `/api/sessions` | List sessions, ordered by `updated_at DESC` |
| `POST` | `/api/sessions` | Create session `{provider, model, system_prompt}` |
| `GET` | `/api/sessions/{id}` | Session detail + full message history + documents |
| `PATCH` | `/api/sessions/{id}` | Rename (`{title}`) |
| `DELETE` | `/api/sessions/{id}` | Cascades to messages, documents, doc_chunks |
| `POST` | `/api/sessions/{id}/documents` | Multipart file upload → chunk → embed → store |
| `GET` | `/api/sessions/{id}/documents` | List documents for session |
| `DELETE` | `/api/sessions/{id}/documents/{doc_id}` | Remove document + its chunks |
| `POST` | `/api/chat` | Non-streaming chat (single-turn, no persistence — Swagger/testing use) |
| `POST` | `/api/chat/stream` | SSE streaming chat, full pipeline described above |
| `GET` | `/api/analytics/summary` | Aggregate totals + provider/model breakdown + 30-day daily series |

SSE event types emitted by `/api/chat/stream`: `title`, `route`, `delta`, `tool_call`, `tool_result`, `usage`, `done`, `error`.

---

## 🚀 Setup

```bash
git clone https://github.com/MirAb-77/<repo-name>.git
cd <repo-name>
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # fill in GROQ_API_KEY, GEMINI_API_KEY, TAVILY_API_KEY, OPENROUTER_API_KEY
python backend.py
```

Single process, single port (`9999`): serves the REST/SSE API, the landing page, the chat app, and the analytics dashboard. `GEMINI_API_KEY` is required even for Groq/OpenRouter-only conversations, since document embedding always calls the Gemini API independently of the active chat provider.

### Dependency pinning note

`langgraph` is pinned exactly (`==1.2.10` in both `requirements.txt` and `Pipfile`) rather than left open — the `create_react_agent()` keyword interface changed between minor versions (`state_modifier` → `prompt`), and an unpinned install silently breaks the agent construction call. `ai_agent.py`'s `_build_agent()` additionally wraps the call in a `try/except TypeError` fallback between the two interfaces as defense in depth.

---

## ☁️ Deployment

Any host running a persistent process works; avoid pure serverless/edge runtimes since SQLite requires a writable, persistent filesystem path (`DB_PATH` env var, defaults to `./chat_history.db`).

```bash
# Docker
docker build -t agent-chatbot .
docker run -d -p 9999:9999 --env-file .env -v agent_data:/app/data --name agent-chatbot agent-chatbot
```

Render/Railway: connect the repo, set the four provider env vars, attach a persistent volume at `/app/data`, set `DB_PATH=/app/data/chat_history.db`. Without the volume, ephemeral-filesystem platforms wipe chat history on every restart/redeploy.

**Known gaps before public deployment:** `CORS` is `allow_origins=["*"]`; there is no authentication on any endpoint; there is no rate limiting. Fine for local/personal use, not fine for an unauthenticated public URL.

---

## 🧭 Design tradeoffs (explicit)

- **No vector database.** Embeddings are stored as JSON text in SQLite and compared with brute-force `numpy` cosine similarity. Correct choice at single-user, single-session scale; wrong choice past a few thousand chunks or multi-tenant concurrent load.
- **No token-accurate cost accounting.** Character-count heuristic, not a real tokenizer. Directionally useful, not billing-accurate — stated explicitly in the analytics UI itself.
- **Rule-based router, not a learned one.** Deterministic and free, but a fixed set of regex patterns will misclassify anything outside the patterns it was written to catch.
- **JSON columns instead of normalized trace/usage tables.** Simpler queries, no joins needed for the one access pattern that exists (render-by-message-id); would need revisiting if trace data needed independent querying/filtering.
- **No conversation-level model pinning under auto-route.** Each auto-routed message is classified independently; a session can bounce between providers turn to turn, which is intentional (cost/latency optimized per-message) but means model identity isn't stable within one conversation the way manual selection guarantees.

---

## 📄 License

MIT.

---

Built by [Abdullah Imran](https://github.com/MirAb-77)
