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
- 🎭 **Any persona** — define the agent's behavior per chat session with a custom system prompt
- 💬 **Real conversation memory** — full chat history is sent to the agent every turn, so it remembers context
- 🗂️ **Persistent chat sessions** — stored server-side in SQLite; a sidebar lets you switch between past conversations, just like ChatGPT
- ⚡ **Live token streaming** — responses appear word-by-word via Server-Sent Events

---

## 🏗️ Technical Architecture

```
┌───────────────────────────────────────────────┐
│  Custom Website (HTML / CSS / JS)              │
│  Sidebar sessions · Streaming chat · Markdown  │
└───────────────────┬─────────────────────────────┘
                     │ fetch() + SSE
┌────────────────────▼──────────────────────────┐
│  FastAPI Backend                               │
│  Sessions API · /chat/stream · SQLite storage  │
└────────────────────┬──────────────────────────┘
                     │
┌────────────────────▼──────────────────────────┐
│  LangGraph ReAct Agent                         │
│  LLM (Groq / Gemini / OpenRouter) ⇄ Tools      │
└─────────────────────────────────────────────────┘
```

| Layer | Tech |
|---|---|
| 🎨 Frontend | Vanilla HTML/CSS/JS (served by FastAPI), marked.js, highlight.js |
| ⚙️ Backend | FastAPI + Pydantic + Uvicorn + SQLite |
| 🧩 Agent Framework | LangGraph (`create_react_agent`), streamed via `stream_mode="messages"` |
| 🔌 LLM Providers | Groq, Google Gemini, OpenRouter |
| 🌐 Search Tool | Tavily |
| 🔗 Orchestration | LangChain |

---

## ✨ Features

- ✅ **Multi-provider LLM support** — Groq, Gemini, OpenRouter, selectable per session
- ✅ **Multi-turn memory** — the agent sees the full conversation, not just the latest message
- ✅ **Multiple chat sessions** — sidebar history, switch between conversations, delete old ones
- ✅ **Streaming responses** — tokens appear live as the model generates them
- ✅ **Markdown + syntax-highlighted code** — with one-click copy buttons on every code block
- ✅ **Web-search-augmented answers** — toggle real-time search on/off per message
- ✅ **Custom system prompts** — reshape agent persona per chat session
- ✅ **One process to run** — FastAPI serves both the API and the website

---

## 📁 Project Structure

```
.
├── ai_agent.py         # LangGraph ReAct agent, multi-turn state, streaming
├── backend.py          # FastAPI service: sessions, SQLite, SSE /chat/stream
├── static/
│   ├── index.html      # Website markup
│   ├── style.css        # Design system (dark theme, provider color-coding)
│   └── script.js        # Chat UI logic + SSE streaming client
├── chat_history.db      # SQLite DB (auto-created on first run)
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

1. Click **+ New chat**, or just start typing — a session is created automatically
2. Pick a **provider** and **model** from the top bar
3. Toggle **Web search** if you want real-time answers
4. Open **⚙ Agent settings** to set a custom system prompt for that session
5. Type your message and hit **Enter** (Shift+Enter for a new line)
6. Switch between past conversations any time via the sidebar

---

## 🛣️ Roadmap

- [ ] Rename sessions from the UI
- [ ] File / image upload support
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
