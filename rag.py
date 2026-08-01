"""
Lightweight RAG (Retrieval-Augmented Generation) module.

No external vector DB — chunks and their embeddings are stored directly
in SQLite (embeddings as JSON-encoded float arrays), and retrieval is a
simple in-memory cosine-similarity ranking. This keeps the project
dependency-light while still demonstrating the core RAG pattern:
chunk -> embed -> store -> retrieve -> inject into the agent as a tool.
"""

import io
import json
import os

import numpy as np
from langchain_google_genai import GoogleGenerativeAIEmbeddings

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBED_MODEL = "models/text-embedding-004"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
TOP_K = 4

_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = GoogleGenerativeAIEmbeddings(model=EMBED_MODEL, google_api_key=GEMINI_API_KEY)
    return _embedder


def extract_text(filename, raw_bytes):
    """Extracts plain text from an uploaded file's raw bytes."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    # Treat everything else (.txt, .md, .csv, code files, etc.) as plain text
    return raw_bytes.decode("utf-8", errors="ignore")


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Splits text into overlapping chunks so retrieval keeps local context."""
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end == n:
            break
        start = end - overlap

    return chunks


def embed_documents(texts):
    if not texts:
        return []
    return get_embedder().embed_documents(texts)


def embed_query(text):
    return get_embedder().embed_query(text)


def cosine_similarity(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def rank_chunks(query_embedding, chunk_rows, k=TOP_K):
    """
    chunk_rows: iterable of sqlite3.Row-like objects with 'embedding' (JSON str),
                'chunk_text', and 'filename' fields.
    Returns the top-k rows sorted by similarity, each with a 'score' added.
    """
    scored = []
    for row in chunk_rows:
        try:
            emb = json.loads(row["embedding"])
        except Exception:
            continue
        score = cosine_similarity(query_embedding, emb)
        scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]


def format_context(scored_rows):
    """Formats top chunks into a single string to hand back to the agent."""
    if not scored_rows:
        return "No relevant content found in the uploaded documents."

    parts = []
    for score, row in scored_rows:
        parts.append(f"[Source: {row['filename']} · relevance {score:.2f}]\n{row['chunk_text']}")
    return "\n\n---\n\n".join(parts)
