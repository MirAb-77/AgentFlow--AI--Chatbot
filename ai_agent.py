from dotenv import load_dotenv
load_dotenv()

import os

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from langchain_community.tools.tavily_search import TavilySearchResults

from langgraph.prebuilt import create_react_agent

from langchain_core.messages import AIMessage, AIMessageChunk


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
    "Answer the user's questions clearly and accurately."
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


def _build_agent(provider, llm_id, system_prompt, allow_search):
    llm = _build_llm(provider, llm_id)

    tools = [TavilySearchResults(max_results=2)] if allow_search else []

    prompt = system_prompt.strip() if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT

    return create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=prompt,
    )


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
# NON-STREAMING (used by /chat fallback + tools/testing)
# ============================================================

def get_response_from_ai_agent(llm_id, history, allow_search, system_prompt, provider):
    agent = _build_agent(provider, llm_id, system_prompt, allow_search)
    state = _history_to_state(history)

    response = agent.invoke(state)
    messages = response.get("messages", [])
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]

    if not ai_messages:
        raise Exception("No AI response was generated.")

    return _extract_text(ai_messages[-1].content)


# ============================================================
# STREAMING (used by /chat/stream)
# ============================================================

def stream_response_from_ai_agent(llm_id, history, allow_search, system_prompt, provider):
    """
    Yields dicts as the agent works:
      {"type": "delta", "text": "..."}   -- a chunk of the answer
      {"type": "tool", "name": "..."}     -- the agent used a tool (e.g. web search)
      {"type": "done", "text": "...", "used_tool": bool}  -- final full text
    """
    agent = _build_agent(provider, llm_id, system_prompt, allow_search)
    state = _history_to_state(history)

    full_text = ""
    used_tool = False

    for chunk, metadata in agent.stream(state, stream_mode="messages"):
        if isinstance(chunk, AIMessageChunk):
            delta = _extract_text(chunk.content)
            if delta:
                full_text += delta
                yield {"type": "delta", "text": delta}
        else:
            # Tool call or tool result chunk moving through the graph
            if not used_tool:
                used_tool = True
                yield {"type": "tool", "name": "web_search"}

    yield {"type": "done", "text": full_text, "used_tool": used_tool}
