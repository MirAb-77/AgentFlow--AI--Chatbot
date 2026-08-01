from dotenv import load_dotenv
load_dotenv()

import json
import os

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from langgraph.prebuilt import create_react_agent

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage


# ============================================================
# API KEYS
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is missing.")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY is missing.")
if not TAVILY_API_KEY:
    print("WARNING: TAVILY_API_KEY is missing.")
if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY is missing.")


DEFAULT_SYSTEM_PROMPT = (
    "You are a smart, helpful and friendly AI assistant. "
    "Answer the user's questions clearly and accurately. "
    "If the user has uploaded documents, prefer searching them with "
    "search_documents before answering questions that might relate to their content."
)


# ============================================================
# LLM FACTORY
# ============================================================

def _build_llm(provider, llm_id):

    if provider == "Groq":
        return ChatGroq(
            model=llm_id,
            groq_api_key=GROQ_API_KEY,
            temperature=0.2,
            streaming=True,
        )

    elif provider == "Gemini":
        return ChatGoogleGenerativeAI(
            model=llm_id,
            google_api_key=GEMINI_API_KEY,
            temperature=0.2,
        )

    elif provider == "OpenRouter":
        return ChatOpenAI(
            model=llm_id,
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.2,
            streaming=True,
            default_headers={
                "HTTP-Referer": "http://localhost:9999",
                "X-Title": "LangGraph AI Agent",
            },
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}")


# ============================================================
# TOOLS
# ============================================================

class DocSearchArgs(BaseModel):
    query: str = Field(description="What to search for within the user's uploaded documents")


def _build_tools(allow_search, document_search_fn):
    tools = []

    if allow_search:
        tools.append(TavilySearchResults(max_results=3))

    if document_search_fn is not None:
        tools.append(
            StructuredTool.from_function(
                func=document_search_fn,
                name="search_documents",
                description=(
                    "Search the user's uploaded documents for relevant passages. "
                    "Use this whenever the question could be answered by content "
                    "the user has uploaded to this conversation."
                ),
                args_schema=DocSearchArgs,
            )
        )

    return tools


def _build_agent(provider, llm_id, system_prompt, allow_search, document_search_fn=None):
    llm = _build_llm(provider, llm_id)
    tools = _build_tools(allow_search, document_search_fn)
    prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT

    try:
        # Current LangGraph API (0.3+)
        return create_react_agent(model=llm, tools=tools, prompt=prompt)
    except TypeError:
        # Older LangGraph API (pre-0.3) used state_modifier instead of prompt
        return create_react_agent(model=llm, tools=tools, state_modifier=prompt)


def _history_to_state(history):
    """
    history: list of {"role": "user"|"assistant", "content": str}
    Converts full conversation history into LangGraph agent state,
    giving the agent real multi-turn memory.
    """
    messages = []
    for turn in history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        role = "assistant" if role == "assistant" else "user"
        messages.append({"role": role, "content": content})
    return {"messages": messages}


def _extract_text(content):
    """Normalizes provider-specific content shapes (string vs block list) into plain text."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if text:
                    parts.append(str(text))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)

    return str(content) if content else ""


# ============================================================
# NON-STREAMING (used by /api/chat fallback + tools/testing)
# ============================================================

def get_response_from_ai_agent(llm_id, history, allow_search, system_prompt, provider, document_search_fn=None):
    agent = _build_agent(provider, llm_id, system_prompt, allow_search, document_search_fn)
    state = _history_to_state(history)

    response = agent.invoke(state)
    messages = response.get("messages", [])
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]

    if not ai_messages:
        raise Exception("No AI response was generated.")

    return _extract_text(ai_messages[-1].content)


# ============================================================
# STREAMING (used by /api/chat/stream)
# ============================================================

def stream_response_from_ai_agent(llm_id, history, allow_search, system_prompt, provider, document_search_fn=None):
    """
    Yields dicts as the agent works, producing a full reasoning trace:
      {"type": "delta", "text": "..."}
          -- a chunk of the answer as it's generated

      {"type": "tool_call", "name": "...", "query": "..."}
          -- the agent decided to call a tool (web search / document search)
             with the given query/args

      {"type": "tool_result", "name": "...", "result": "..."}
          -- the tool finished and returned this content back to the agent

      {"type": "done", "text": "...", "used_tool": bool}
          -- final full answer text
    """
    agent = _build_agent(provider, llm_id, system_prompt, allow_search, document_search_fn)
    state = _history_to_state(history)

    full_text = ""
    used_tool = False

    # Tool calls stream in as fragments (id -> accumulated name/args json string)
    pending_calls = {}
    emitted_call_ids = set()

    for chunk, metadata in agent.stream(state, stream_mode="messages"):

        if isinstance(chunk, AIMessageChunk):
            tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
            for tc in tool_call_chunks:
                tc_id = tc.get("id") or "0"
                entry = pending_calls.setdefault(tc_id, {"name": "", "args": ""})
                if tc.get("name"):
                    entry["name"] += tc["name"]
                if tc.get("args"):
                    entry["args"] += tc["args"]

            delta = _extract_text(chunk.content)
            if delta:
                full_text += delta
                yield {"type": "delta", "text": delta}

        elif isinstance(chunk, ToolMessage):
            used_tool = True
            tool_name = chunk.name or "tool"

            # Find the matching pending call (first not-yet-emitted one)
            query_text = None
            for tc_id, entry in pending_calls.items():
                if tc_id in emitted_call_ids:
                    continue
                emitted_call_ids.add(tc_id)
                try:
                    parsed_args = json.loads(entry.get("args") or "{}")
                    query_text = parsed_args.get("query") or next(iter(parsed_args.values()), None)
                except Exception:
                    query_text = entry.get("args") or None
                break

            yield {"type": "tool_call", "name": tool_name, "query": query_text}

            result_text = _extract_text(chunk.content)
            yield {"type": "tool_result", "name": tool_name, "result": result_text[:1500]}

    yield {"type": "done", "text": full_text, "used_tool": used_tool}