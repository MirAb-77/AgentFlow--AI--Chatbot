<div align="center">

# 🤖 Personal Agentic AI Chatbot

### A production-ready, multi-provider chat agent with a custom website UI

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-ReAct%20Agent-1C3C3C?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-Persistence-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](#-license)

**Groq · Gemini · OpenRouter · Tavily**

</div>

---

## 📖 Overview

**Personal Agentic AI Chatbot** is a reusable agent framework with its own ChatGPT-style website — not a single-purpose bot. It gives you:

- 🧠 **Any LLM** — swap between Groq, Google Gemini, and OpenRouter (which itself proxies dozens of models) per session
- 🔍 **Optional live web search** — via Tavily, using the ReAct (reason → act → observe) pattern
- 📎 **Chat with your own documents (RAG)** — upload a PDF/text file and the agent retrieves relevant passages via embeddings + cosine similarity before answering
- 🧭 **Live Reasoning Trace** — watch the agent's actual thought process in real time: which tool it called, what it searched for, what came back — not just the final answer
- 🧠 **Smart Model Router** — flip on Auto-route and a classifier picks the best provider/model per message, cost/latency-aware, with its reasoning shown in the trace
- 📊 **Usage analytics dashboard** — estimated tokens, cost, and latency tracked per message and rolled up into charts
- 🎭 **Any persona** — define the agent's behavior per chat session with a custom system prompt
- 💬 **Real conversation memory** — full chat history is sent to the agent every turn, so it remembers context
- 🗂️ **Persistent chat sessions** — stored server-side in SQLite; a sidebar lets you switch between past conversations, just like ChatGPT
- ⚡ **Live token streaming** — responses appear word-by-word via Server-Sent Events

---

## 🌟 What makes this different

Most portfolio chatbots are an input box wired to an LLM. This one exposes and extends the *agentic* part:

### 🧭 Live Reasoning Trace
Every time the agent decides to use a tool — web search or your uploaded documents — you see it happen, live, in an expandable timeline above the answer: the exact query it ran, and the raw result that came back, before the model turns that into prose. This isn't a fake "thinking…" spinner; it's the actual LangGraph tool-calling stream (`stream_mode="messages"`) parsed into structured events (`tool_call` → `tool_result` → `delta`) and persisted per-message, so the trace is still there when you reopen a session later.

### 📎 Retrieval-Augmented Generation (RAG) on your own files
Upload a PDF or text file to any conversation and the agent gains a `search_documents` tool: your file is chunked, embedded (Google's `text-embedding-004`), and stored — no external vector database required, just SQLite + cosine similarity in `rag.py`. Ask a question that touches the file's content, and you'll watch the Reasoning Trace show the agent choosing to search your documents instead of (or alongside) the web. This is the single most common real-world GenAI use case, implemented end-to-end.

### 🧠 Smart Model Router
Flip on **Auto-route** and the app stops asking you to pick a model — a rule-based classifier in `router.py` reads each message (code markers, reasoning cues, length) and picks the provider/model itself: fast/cheap Groq for a quick question, Gemini for multi-step reasoning, a balanced OpenRouter model as the general fallback. The decision — and *why* it was made — shows up as the first entry in the Reasoning Trace, so routing isn't a black box either. This mirrors the cost/latency/quality tradeoff logic real multi-model gateways run in production.

### 📊 Usage Analytics Dashboard
Every message is logged with estimated input/output tokens, estimated cost (against each provider's real published per-model rates), and latency. The `/analytics.html` dashboard rolls this up into cost-by-provider and daily-activity charts, hand-rolled in SVG/CSS — no charting library dependency. It's the FinOps instinct real production LLM apps need: knowing what a feature costs before the bill arrives.

---

## 🏗️ Technical Architecture

```
┌───────────────────────────────────────────────┐
│  Custom Website (HTML / CSS / JS)              │
│  Landing · Sidebar sessions · Chat · Analytics │
└───────────────────┬─────────────────────────────┘
                     │ fetch() + SSE
┌────────────────────▼──────────────────────────┐
│  FastAPI Backend                               │
│  Sessions · Documents · Router · Analytics API │
│  /chat/stream · SQLite storage                 │
└────────────────────┬──────────────────────────┘
                     │
┌────────────────────▼──────────────────────────┐
│  LangGraph ReAct Agent                         │
│  LLM (Groq / Gemini / OpenRouter) ⇄ Tools      │
│  Web search (Tavily) · Document search (RAG)   │
└─────────────────────────────────────────────────┘
```

| Layer | Tech |
|---|---|
| 🎨 Frontend | Vanilla HTML/CSS/JS (served by FastAPI), marked.js, highlight.js |
| ⚙️ Backend | FastAPI + Pydantic + Uvicorn + SQLite |
| 🧩 Agent Framework | LangGraph (`create_react_agent`), streamed via `stream_mode="messages"` |
| 🔌 LLM Providers | Groq, Google Gemini, OpenRouter |
| 🌐 Tools | Tavily (web search), custom RAG tool (`search_documents`) |
| 🧭 Routing | Rule-based classifier in `router.py` |
| 🔗 Orchestration | LangChain |

---

## ✨ Features

- ✅ **Multi-provider LLM support** — Groq, Gemini, OpenRouter, selectable per session
- ✅ **Multi-turn memory** — the agent sees the full conversation, not just the latest message
- ✅ **Multiple chat sessions** — sidebar history, switch between conversations, delete old ones
- ✅ **Streaming responses** — tokens appear live as the model generates them
- ✅ **Live Reasoning Trace** — expandable, per-message timeline of every tool call and result
- ✅ **RAG on uploaded documents** — chat with your own PDFs/text files, chunked + embedded + retrieved
- ✅ **Smart Model Router** — optional auto-routing picks the best provider/model per query
- ✅ **Usage analytics dashboard** — token, cost, and latency tracking with charts
- ✅ **Markdown + syntax-highlighted code** — with one-click copy buttons on every code block
- ✅ **Web-search-augmented answers** — toggle real-time search on/off per message
- ✅ **Custom system prompts** — reshape agent persona per chat session
- ✅ **One process to run** — FastAPI serves the API, the landing page, and the chat app

---

## 📁 Project Structure

```
.
├── ai_agent.py         # LangGraph ReAct agent, multi-turn state, streaming, reasoning trace
├── backend.py          # FastAPI service: sessions, documents, routing, analytics, SSE
├── rag.py               # Chunking, embeddings, cosine-similarity retrieval (RAG)
├── router.py             # Smart Model Router: query classification + cost table
├── static/
│   ├── index.html      # Landing / home page
│   ├── chat.html        # The chat app itself
│   ├── analytics.html    # Usage analytics dashboard
│   ├── style.css        # Shared design system (dark theme, provider color-coding)
│   ├── landing.css      # Landing-page-specific styles
│   ├── analytics.css     # Analytics dashboard styles
│   ├── script.js        # Chat UI logic, SSE streaming, reasoning trace, document upload
│   ├── landing.js       # Scroll-reveal animation for the landing page
│   └── analytics.js      # Fetches and renders the analytics dashboard
├── chat_history.db      # SQLite DB (auto-created on first run)
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── Pipfile
├── .env.example
└── README.md
```

---

## 🚀 Getting Started

### 1️⃣ Clone the repo

```bash
git clone https://github.com/MirAb-77/<repo-name>.git
cd <repo-name>
```

### 2️⃣ Set up your environment

<details>
<summary><b>🔧 Using Pipenv</b></summary>

```bash
pip install pipenv
pipenv install
pipenv shell
```
</details>

<details>
<summary><b>🔧 Using pip + venv</b></summary>

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
</details>

### 3️⃣ Add your API keys

Copy `.env.example` to `.env` and fill in your real keys:

```env
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
TAVILY_API_KEY=your_tavily_key
OPENROUTER_API_KEY=your_openrouter_key
```

> `OPENROUTER_API_KEY` is only required if you plan to use the OpenRouter provider.

### 4️⃣ Run the app

```bash
python backend.py
```

That's it — **one process**. Open **http://127.0.0.1:9999** in your browser for the chat website, or **http://127.0.0.1:9999/docs** for the Swagger API docs.

---

## 🎮 Usage

1. Land on **http://127.0.0.1:9999** — the home page introduces the agent and links to the app
2. Click **Launch app** to enter the chat UI, or go straight to `/chat.html`
3. Click **+ New chat**, or just start typing — a session is created automatically
4. Pick a **provider** and **model** from the top bar
5. Toggle **Web search** if you want real-time answers
6. Open **⚙ Agent settings** to set a custom system prompt for that session
7. Click **📎** to upload a document — the agent can now search it via `search_documents`, visible live in the Reasoning Trace
8. Flip on **🧭 Auto-route** to let the router pick the provider/model per message instead of choosing manually
9. Type your message and hit **Enter** (Shift+Enter for a new line)
10. Switch between past conversations any time via the sidebar
11. Open **📊 Analytics** in the sidebar to see token/cost/latency stats across every conversation

> **Note:** document embeddings use the Gemini API (`GEMINI_API_KEY`), so uploads work even if your active chat session is set to Groq or OpenRouter — the embedding call is separate from the chat model.

---

## ☁️ Deployment

The app is a single FastAPI process that also serves the static frontend — deploy it anywhere that runs a long-lived Python process (avoid pure serverless/edge functions, since SQLite needs a persistent disk).

### Option A — Docker (any host)

```bash
docker build -t agent-chatbot .
docker run -d \
  -p 9999:9999 \
  --env-file .env \
  -v agent_data:/app/data \
  --name agent-chatbot \
  agent-chatbot
```

The `-v agent_data:/app/data` volume is what keeps `chat_history.db` across container restarts — without it, every redeploy wipes your chat history.

### Option B — Render.com (simplest managed option)

1. Push this repo to GitHub
2. On Render: **New → Web Service** → connect the repo
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `uvicorn backend:app --host 0.0.0.0 --port $PORT`
5. Add your `GROQ_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`, `OPENROUTER_API_KEY` under **Environment**
6. Add a **Persistent Disk** (e.g. 1GB, mounted at `/app/data`), and set env var `DB_PATH=/app/data/chat_history.db` — otherwise the free tier's ephemeral filesystem will erase chat history on every restart/deploy

### Option C — Railway

Same idea as Render: connect the repo, set the same env vars, add a **Volume** mounted at `/app/data`, set `DB_PATH=/app/data/chat_history.db`, and Railway auto-detects the start command from the Dockerfile.

### Option D — A plain VPS (DigitalOcean, Hetzner, etc.)

```bash
git clone <your-repo> && cd <your-repo>
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real keys
# run behind a process manager so it survives reboots/crashes:
pip install gunicorn
gunicorn backend:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:9999
```

Put **Caddy** or **nginx** in front for HTTPS and a real domain — Caddy is the least setup (`caddy reverse-proxy --from yourdomain.com --to localhost:9999` handles TLS automatically).

### Production notes

- **CORS is wide open** (`allow_origins=["*"]`) in `backend.py` — fine for personal use, but lock it down to your actual domain before sharing the link publicly
- **No auth** — anyone with the URL can create sessions and burn your API credits. Add a simple API key check or basic auth in front if you're deploying somewhere public
- **Rate limits** — Groq/Gemini/OpenRouter free tiers all cap requests; monitor usage if this gets real traffic
- **Cost/token figures are estimates** — computed from a ~4-chars-per-token heuristic and a static pricing table in `router.py`, not each provider's actual usage metering. Good for relative comparisons, not for billing reconciliation
- Keep `.env` out of git — it's already covered by `.dockerignore`, add it to `.gitignore` too if you haven't

---

## 🛣️ Roadmap

- [ ] Rename sessions from the UI
- [x] File upload + RAG (done — see "What makes this different")
- [x] Smart model routing (done — see "What makes this different")
- [x] Usage analytics dashboard (done — see "What makes this different")
- [ ] Image upload / vision support
- [ ] Auth & multi-user support
- [ ] Rate limiting on the API
- [ ] Export a conversation as Markdown/PDF

---

## 📜 License

Distributed under the MIT License.

---

<div align="center">

Made with ❤️ by [**Abdullah Imran**](https://github.com/MirAb-77)

</div>
