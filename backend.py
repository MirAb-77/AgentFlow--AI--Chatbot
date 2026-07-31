import json
import os
import sqlite3
import time
import traceback
import uuid
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ai_agent import get_response_from_ai_agent, stream_response_from_ai_agent


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "chat_history.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")


# ============================================================
# Allowed Providers / Models
# ============================================================

GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
GEMINI_MODELS = ["gemini-3.6-flash", "gemini-2.5-flash"]
OPENROUTER_MODELS = [
    "openai/gpt-oss-20b:free",
    "qwen/qwen3.5-9b",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

PROVIDER_MODELS = {
    "Groq": GROQ_MODELS,
    "Gemini": GEMINI_MODELS,
    "OpenRouter": OPENROUTER_MODELS,
}

DEFAULT_SYSTEM_PROMPT = (
    "You are a smart, helpful and friendly AI assistant. "
    "Answer the user's questions clearly and accurately."
)


# ============================================================
# Database
# ============================================================

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New chat',
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                system_prompt TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)


init_db()


# ============================================================
# Schemas
# ============================================================

class NewSessionRequest(BaseModel):
    provider: str = "Groq"
    model: str = "llama-3.3-70b-versatile"
    system_prompt: str = ""


class ChatRequest(BaseModel):
    session_id: str
    message: str
    provider: str
    model: str
    system_prompt: str = ""
    allow_search: bool = False


class RenameRequest(BaseModel):
    title: str


# ============================================================
# App
# ============================================================

app = FastAPI(title="LangGraph AI Agent", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Model / Provider Info
# ============================================================

@app.get("/api/models")
def get_models():
    return PROVIDER_MODELS


# ============================================================
# Session Endpoints
# ============================================================

@app.get("/api/sessions")
def list_sessions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, provider, model, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/sessions")
def create_session(req: NewSessionRequest):
    session_id = str(uuid.uuid4())
    now = time.time()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO sessions (id, title, provider, model, system_prompt, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, "New chat", req.provider, req.model, req.system_prompt, now, now),
        )
    return {"id": session_id, "title": "New chat", "provider": req.provider, "model": req.model}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    with get_db() as conn:
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            return JSONResponse(status_code=404, content={"error": "Session not found"})
        messages = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return {"session": dict(session), "messages": [dict(m) for m in messages]}


@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, req: RenameRequest):
    with get_db() as conn:
        conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (req.title.strip()[:80] or "New chat", session_id))
    return {"success": True}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return {"success": True}


# ============================================================
# Chat -- Streaming (used by the website)
# ============================================================

def _sse(event_type, payload):
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    if req.provider not in PROVIDER_MODELS:
        return JSONResponse(status_code=400, content={"error": f"Unsupported provider: {req.provider}"})
    if req.model not in PROVIDER_MODELS[req.provider]:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid model '{req.model}' for provider '{req.provider}'"},
        )

    with get_db() as conn:
        session = conn.execute("SELECT * FROM sessions WHERE id = ?", (req.session_id,)).fetchone()
        if not session:
            return JSONResponse(status_code=404, content={"error": "Session not found"})

        history_rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (req.session_id,),
        ).fetchall()
        history = [{"role": r["role"], "content": r["content"]} for r in history_rows]

        now = time.time()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
            (req.session_id, req.message, now),
        )

        is_first_message = len(history) == 0
        new_title = req.message.strip()[:60] if is_first_message else None

        if new_title:
            conn.execute(
                "UPDATE sessions SET title = ?, provider = ?, model = ?, updated_at = ? WHERE id = ?",
                (new_title, req.provider, req.model, now, req.session_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET provider = ?, model = ?, updated_at = ? WHERE id = ?",
                (req.provider, req.model, now, req.session_id),
            )

    history.append({"role": "user", "content": req.message})
    system_prompt = req.system_prompt or session["system_prompt"] or DEFAULT_SYSTEM_PROMPT

    def event_generator():
        full_text = ""
        try:
            if new_title:
                yield _sse("title", {"title": new_title})

            for event in stream_response_from_ai_agent(
                llm_id=req.model,
                history=history,
                allow_search=req.allow_search,
                system_prompt=system_prompt,
                provider=req.provider,
            ):
                if event["type"] == "delta":
                    full_text += event["text"]
                    yield _sse("delta", {"text": event["text"]})
                elif event["type"] == "tool":
                    yield _sse("tool", {"name": event.get("name", "tool")})
                elif event["type"] == "done":
                    full_text = event["text"] or full_text

            if not full_text.strip():
                full_text = "I couldn't generate a response. Please try again."

            with get_db() as conn:
                conn.execute(
                    "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                    (req.session_id, full_text, time.time()),
                )

            yield _sse("done", {"text": full_text})

        except Exception as e:
            traceback.print_exc()
            yield _sse("error", {"error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============================================================
# Chat -- Non-streaming fallback (Swagger / API testing)
# ============================================================

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    if req.provider not in PROVIDER_MODELS or req.model not in PROVIDER_MODELS.get(req.provider, []):
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid provider/model"})

    try:
        response = get_response_from_ai_agent(
            llm_id=req.model,
            history=[{"role": "user", "content": req.message}],
            allow_search=req.allow_search,
            system_prompt=req.system_prompt or DEFAULT_SYSTEM_PROMPT,
            provider=req.provider,
        )
        return {"success": True, "response": response}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# ============================================================
# Serve the website (must be mounted last)
# ============================================================

if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9999)
