<div align="center">

# 🤖 Personal Agentic AI Chatbot

### A production-ready, multi-LLM chatbot agent powered by LangGraph, FastAPI & Streamlit

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-ReAct%20Agent-1C3C3C?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](#-license)

**Groq · OpenAI · Meta Llama · Mistral · Tavily**

</div>

---

## 📖 Overview

**Personal Agentic AI Chatbot** is a reusable agent framework — not a single-purpose bot. It exposes one API endpoint that lets you plug in:

- 🧠 **Any LLM** — swap between Groq (Llama 3.3, Mixtral) and OpenAI (GPT-4o-mini) per request
- 🔍 **Optional live web search** — via Tavily, using the ReAct (reason → act → observe) pattern
- 🎭 **Any persona** — define the agent's behavior on the fly with a custom system prompt

Think of it as infrastructure for spinning up different chatbot personalities on demand, with a clean UI on top.

---

## 🏗️ Technical Architecture

```
┌─────────────────────────────────────────────┐
│  Phase 3 — Streamlit UI                      │
│  User Interaction                            │
└───────────────────┬───────────────────────────┘
                     │ HTTP POST
┌────────────────────▼──────────────────────────┐
│  Phase 2 — FastAPI Backend                     │
│  Payload → Pydantic Validation → Response      │
└────────────────────┬──────────────────────────┘
                     │
┌────────────────────▼──────────────────────────┐
│  Phase 1 — LangGraph ReAct Agent               │
│  LLM  ⇄  Tools (Tavily Search)                 │
└─────────────────────────────────────────────────┘
```

| Layer | Tech |
|---|---|
| 🎨 Frontend | Streamlit |
| ⚙️ Backend | FastAPI + Pydantic + Uvicorn |
| 🧩 Agent Framework | LangGraph (`create_react_agent`) |
| 🔌 LLM Providers | Groq, OpenAI |
| 🌐 Search Tool | Tavily |
| 🔗 Orchestration | LangChain |

---

## ✨ Features

- ✅ **Multi-provider LLM support** — Groq & OpenAI, selectable at runtime
- ✅ **Web-search-augmented answers** — toggle real-time search on/off
- ✅ **Custom system prompts** — reshape agent persona without code changes
- ✅ **Clean REST API** — Swagger/OpenAPI docs out of the box via FastAPI
- ✅ **Simple web UI** — no frontend framework overhead, just Streamlit

---

## 📁 Project Structure

```
.
├── ai_agent.py       # Phase 1 — LLM setup + LangGraph ReAct agent
├── backend.py        # Phase 2 — FastAPI service + Pydantic schema
├── frontend.py        # Phase 3 — Streamlit UI
├── requirements.txt   # pip dependencies
├── Pipfile             # pipenv dependencies
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

<details>
<summary><b>🔧 Using Conda</b></summary>

```bash
conda create --name myenv python=3.11
conda activate myenv
pip install -r requirements.txt
```
</details>

### 3️⃣ Add your API keys

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
```

### 4️⃣ Run the app

> ⚠️ **Run the backend in a separate terminal before starting the frontend.**

```bash
# Terminal 1 — start the backend
python backend.py

# Terminal 2 — start the frontend
streamlit run frontend.py
```

Visit `http://localhost:8501` for the chat UI, or `http://127.0.0.1:9999/docs` for the Swagger API docs.

---

## 🎮 Usage

1. Define your agent's persona in the **system prompt** box
2. Pick a **provider** (Groq / OpenAI) and **model**
3. Toggle **Allow Web Search** if you want real-time answers
4. Type your query and hit **Ask Agent!**

---

## 🛣️ Roadmap

- [ ] Multi-turn conversation memory (LangGraph checkpointer)
- [ ] Streaming responses
- [ ] Additional tool integrations
- [ ] Auth & rate limiting on the API

---

## 📜 License

Distributed under the MIT License.

---

<div align="center">

Made with ❤️ by [**Abdullah Imran**](https://github.com/MirAb-77)

</div>
