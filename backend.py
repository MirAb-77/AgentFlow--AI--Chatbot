import json
import os
import sqlite3
import time
import traceback
import uuid
from contextlib import contextmanager

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ai_agent import get_response_from_ai_agent, stream_response_from_ai_agent
import rag
import router as smart_router


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "chat_history.db"))
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB per file
ALLOWED_EXTENSIONS = {"pdf", "txt", "md", "csv", "json", "py", "js", "ts", "html", "css"}


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


def _column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


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
                trace TEXT,
                usage TEXT,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doc_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens_est INTEGER NOT NULL DEFAULT 0,
                output_tokens_est INTEGER NOT NULL DEFAULT 0,
                cost_est REAL NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                routed INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)

        # Migrations for DBs created before these columns existed
        if not _column_exists(conn, "messages", "trace"):
            conn.execute("ALTER TABLE messages ADD COLUMN trace TEXT")
        if not _column_exists(conn, "messages", "usage"):
            conn.execute("ALTER TABLE messages ADD COLUMN usage TEXT")


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
    auto_route: bool = False


class RenameRequest(BaseModel):
    title: str


# ============================================================
# App
# ============================================================

app = FastAPI(title="LangGraph AI Agent", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            "SELECT role, content, trace, usage, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()

        documents = conn.execute(
            "SELECT id, filename, chunk_count, created_at FROM documents WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()

        out_messages = []
        for m in messages:
            row = dict(m)
            for field in ("trace", "usage"):
                if row.get(field):
                    try:
                        row[field] = json.loads(row[field])
                    except Exception:
                        row[field] = None
            out_messages.append(row)

        return {
            "session": dict(session),
            "messages": out_messages,
            "documents": [dict(d) for d in documents],
        }


@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, req: RenameRequest):
    with get_db() as conn:
        conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (req.title.strip()[:80] or "New chat", session_id))
    return {"success": True}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM doc_chunks WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM documents WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM usage_events WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return {"success": True}


# ============================================================
# Document Endpoints (RAG)
# ============================================================

@app.post("/api/sessions/{session_id}/documents")
async def upload_document(session_id: str, file: UploadFile = File(...)):
    with get_db() as conn:
        session = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            return JSONResponse(status_code=404, content={"error": "Session not found"})

    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"},
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        return JSONResponse(status_code=400, content={"error": "File too large (8 MB limit)."})

    try:
        text = rag.extract_text(file.filename, raw_bytes)
        chunks = rag.chunk_text(text)

        if not chunks:
            return JSONResponse(status_code=400, content={"error": "No extractable text found in this file."})

        embeddings = rag.embed_documents(chunks)

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": f"Failed to process file: {str(e)}"})

    doc_id = str(uuid.uuid4())
    now = time.time()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO documents (id, session_id, filename, chunk_count, created_at) VALUES (?, ?, ?, ?, ?)",
            (doc_id, session_id, file.filename, len(chunks), now),
        )
        for chunk, emb in zip(chunks, embeddings):
            conn.execute(
                "INSERT INTO doc_chunks (document_id, session_id, filename, chunk_text, embedding) VALUES (?, ?, ?, ?, ?)",
                (doc_id, session_id, file.filename, chunk, json.dumps(emb)),
            )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))

    return {"id": doc_id, "filename": file.filename, "chunk_count": len(chunks)}


@app.get("/api/sessions/{session_id}/documents")
def list_documents(session_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, filename, chunk_count, created_at FROM documents WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


@app.delete("/api/sessions/{session_id}/documents/{document_id}")
def delete_document(session_id: str, document_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM doc_chunks WHERE document_id = ? AND session_id = ?", (document_id, session_id))
        conn.execute("DELETE FROM documents WHERE id = ? AND session_id = ?", (document_id, session_id))
    return {"success": True}


def _make_document_search_fn(session_id):
    """Returns a closure the agent can call as a tool to search this session's uploaded docs."""

    def search_documents(query: str) -> str:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT filename, chunk_text, embedding FROM doc_chunks WHERE session_id = ?",
                (session_id,),
            ).fetchall()

        if not rows:
            return "No documents have been uploaded to this conversation yet."

        query_embedding = rag.embed_query(query)
        ranked = rag.rank_chunks(query_embedding, rows)
        return rag.format_context(ranked)

    return search_documents


def _session_has_documents(session_id):
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM documents WHERE session_id = ?", (session_id,)).fetchone()
        return row["c"] > 0


# ============================================================
# Chat -- Streaming (used by the website)
# ============================================================

def _sse(event_type, payload):
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n"


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    provider = req.provider
    model = req.model
    route_info = None

    if req.auto_route:
        route_info = smart_router.classify_and_route(req.message, PROVIDER_MODELS)
        provider = route_info["provider"]
        model = route_info["model"]
    else:
        if provider not in PROVIDER_MODELS:
            return JSONResponse(status_code=400, content={"error": f"Unsupported provider: {provider}"})
        if model not in PROVIDER_MODELS[provider]:
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid model '{model}' for provider '{provider}'"},
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
                (new_title, provider, model, now, req.session_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET provider = ?, model = ?, updated_at = ? WHERE id = ?",
                (provider, model, now, req.session_id),
            )

    history.append({"role": "user", "content": req.message})
    system_prompt = req.system_prompt or session["system_prompt"] or DEFAULT_SYSTEM_PROMPT

    document_search_fn = _make_document_search_fn(req.session_id) if _session_has_documents(req.session_id) else None

    def event_generator():
        full_text = ""
        trace_events = []
        start_time = time.perf_counter()

        try:
            if new_title:
                yield _sse("title", {"title": new_title})

            if route_info:
                trace_events.append({
                    "type": "route",
                    "provider": route_info["provider"],
                    "model": route_info["model"],
                    "reason": route_info["reason"],
                })
                yield _sse("route", {
                    "provider": route_info["provider"],
                    "model": route_info["model"],
                    "reason": route_info["reason"],
                })

            for event in stream_response_from_ai_agent(
                llm_id=model,
                history=history,
                allow_search=req.allow_search,
                system_prompt=system_prompt,
                provider=provider,
                document_search_fn=document_search_fn,
            ):
                if event["type"] == "delta":
                    full_text += event["text"]
                    yield _sse("delta", {"text": event["text"]})

                elif event["type"] == "tool_call":
                    trace_events.append({"type": "tool_call", "name": event["name"], "query": event.get("query")})
                    yield _sse("tool_call", {"name": event["name"], "query": event.get("query")})

                elif event["type"] == "tool_result":
                    trace_events.append({"type": "tool_result", "name": event["name"], "result": event.get("result")})
                    yield _sse("tool_result", {"name": event["name"], "result": event.get("result")})

                elif event["type"] == "done":
                    full_text = event["text"] or full_text

            if not full_text.strip():
                full_text = "I couldn't generate a response. Please try again."

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            input_text = system_prompt + " ".join(h["content"] for h in history)
            input_tokens = smart_router.estimate_tokens(input_text)
            output_tokens = smart_router.estimate_tokens(full_text)
            cost_est = smart_router.estimate_cost(provider, model, input_tokens, output_tokens)

            usage_dict = {
                "provider": provider,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cost": cost_est,
                "latency_ms": latency_ms,
                "routed": bool(route_info),
            }

            with get_db() as conn:
                conn.execute(
                    """INSERT INTO messages (session_id, role, content, trace, usage, created_at)
                       VALUES (?, 'assistant', ?, ?, ?, ?)""",
                    (
                        req.session_id,
                        full_text,
                        json.dumps(trace_events) if trace_events else None,
                        json.dumps(usage_dict),
                        time.time(),
                    ),
                )
                conn.execute(
                    """INSERT INTO usage_events
                       (session_id, provider, model, input_tokens_est, output_tokens_est, cost_est, latency_ms, routed, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        req.session_id, provider, model, input_tokens, output_tokens,
                        cost_est, latency_ms, 1 if route_info else 0, time.time(),
                    ),
                )

            yield _sse("usage", usage_dict)
            yield _sse("done", {"text": full_text, "trace": trace_events})

        except Exception as e:
            traceback.print_exc()
            yield _sse("error", {"error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============================================================
# Chat -- Non-streaming fallback (Swagger / API testing)
# ============================================================

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    provider, model = req.provider, req.model

    if req.auto_route:
        route_info = smart_router.classify_and_route(req.message, PROVIDER_MODELS)
        provider, model = route_info["provider"], route_info["model"]
    elif provider not in PROVIDER_MODELS or model not in PROVIDER_MODELS.get(provider, []):
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid provider/model"})

    document_search_fn = _make_document_search_fn(req.session_id) if _session_has_documents(req.session_id) else None

    try:
        response = get_response_from_ai_agent(
            llm_id=model,
            history=[{"role": "user", "content": req.message}],
            allow_search=req.allow_search,
            system_prompt=req.system_prompt or DEFAULT_SYSTEM_PROMPT,
            provider=provider,
            document_search_fn=document_search_fn,
        )
        return {"success": True, "response": response, "provider": provider, "model": model}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# ============================================================
# Analytics
# ============================================================

@app.get("/api/analytics/summary")
def analytics_summary():
    with get_db() as conn:
        totals = conn.execute("""
            SELECT
                COUNT(*) as messages,
                COALESCE(SUM(input_tokens_est + output_tokens_est), 0) as tokens,
                COALESCE(SUM(cost_est), 0) as cost,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COALESCE(SUM(routed), 0) as routed_messages
            FROM usage_events
        """).fetchone()

        by_provider = conn.execute("""
            SELECT provider, model,
                COUNT(*) as messages,
                COALESCE(SUM(input_tokens_est + output_tokens_est), 0) as tokens,
                COALESCE(SUM(cost_est), 0) as cost,
                COALESCE(AVG(latency_ms), 0) as avg_latency
            FROM usage_events
            GROUP BY provider, model
            ORDER BY messages DESC
        """).fetchall()

        by_day = conn.execute("""
            SELECT date(created_at, 'unixepoch') as day,
                COUNT(*) as messages,
                COALESCE(SUM(cost_est), 0) as cost,
                COALESCE(SUM(input_tokens_est + output_tokens_est), 0) as tokens
            FROM usage_events
            GROUP BY day
            ORDER BY day ASC
        """).fetchall()

        session_count = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]
        document_count = conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()["c"]

    return {
        "totals": dict(totals),
        "by_provider": [dict(r) for r in by_provider],
        "by_day": [dict(r) for r in by_day][-30:],
        "session_count": session_count,
        "document_count": document_count,
    }


# ============================================================
# Serve the website (must be mounted last)
# ============================================================

if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9999)
