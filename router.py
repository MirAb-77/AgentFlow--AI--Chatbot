"""
Smart Model Router.

Rule-based query classification that picks the most appropriate
provider/model for a given message -- a small, explainable stand-in
for the routing layer real multi-model gateways (OpenRouter, Martian,
etc.) run at much larger scale. Also holds the illustrative cost
table used to estimate spend per message for the analytics dashboard.

Pricing below is approximate, sourced mid-2026, and only meant to
demonstrate cost-aware routing -- always check each provider's
pricing page for current, exact rates.
"""

import re

# ============================================================
# Cost table: (provider, model) -> (usd per 1M input tok, usd per 1M output tok)
# ============================================================

COST_TABLE = {
    ("Groq", "llama-3.1-8b-instant"): (0.05, 0.08),
    ("Groq", "llama-3.3-70b-versatile"): (0.59, 0.79),
    ("Gemini", "gemini-2.5-flash"): (0.30, 2.50),
    ("Gemini", "gemini-3.6-flash"): (1.50, 7.50),
    ("OpenRouter", "openai/gpt-oss-20b:free"): (0.0, 0.0),
    ("OpenRouter", "nvidia/nemotron-3-super-120b-a12b:free"): (0.0, 0.0),
    ("OpenRouter", "qwen/qwen3.5-9b"): (0.20, 0.20),
}


def estimate_tokens(text):
    """Rough ~4-chars-per-token heuristic -- no tokenizer dependency needed."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_cost(provider, model, input_tokens, output_tokens):
    rate_in, rate_out = COST_TABLE.get((provider, model), (0.0, 0.0))
    cost = (input_tokens / 1_000_000) * rate_in + (output_tokens / 1_000_000) * rate_out
    return round(cost, 6)


# ============================================================
# Routing rules
# ============================================================

CODE_PATTERN = re.compile(
    r"```|\bfunction\b|\bclass\b|\bdef |\berror\b|\bdebug\b|\bexception\b|\bbug\b|"
    r"\bcompile\b|\bstack trace\b|\brefactor\b|\bwrite (a|some) (code|script|function)\b",
    re.I,
)
REASONING_PATTERN = re.compile(
    r"\bwhy\b|\bexplain\b|\banalyz|\bcompare\b|\bpros and cons\b|\btrade-?offs?\b|"
    r"\bwalk me through\b|\bin depth\b|\bstep by step\b|\bsummar",
    re.I,
)

ROUTES = [
    {
        "id": "code",
        "match": lambda text, words: bool(CODE_PATTERN.search(text)),
        "provider": "Groq",
        "model": "llama-3.3-70b-versatile",
        "reason": "Detected code or technical/debugging content — routed to a stronger coding-capable model.",
    },
    {
        "id": "reasoning",
        "match": lambda text, words: bool(REASONING_PATTERN.search(text)) or words > 60,
        "provider": "Gemini",
        "model": "gemini-2.5-flash",
        "reason": "Multi-step reasoning or a long, detailed request — routed to a model strong at structured reasoning.",
    },
    {
        "id": "quick",
        "match": lambda text, words: words <= 12,
        "provider": "Groq",
        "model": "llama-3.1-8b-instant",
        "reason": "Short, simple request — routed to the fastest, cheapest model for low latency.",
    },
]

FALLBACK_ROUTE = {
    "id": "general",
    "provider": "OpenRouter",
    "model": "qwen/qwen3.5-9b",
    "reason": "General-purpose request — routed to a balanced open model.",
}


def classify_and_route(message, provider_models):
    """
    Returns {"provider", "model", "reason", "route_id"} for the given message.
    Falls back safely if the chosen model isn't in provider_models (e.g. list changed).
    """
    text = (message or "").strip()
    word_count = len(text.split())

    chosen = FALLBACK_ROUTE
    for rule in ROUTES:
        if rule["match"](text, word_count):
            chosen = rule
            break

    provider, model = chosen["provider"], chosen["model"]

    # Safety net: make sure the picked model is actually still valid
    if model not in provider_models.get(provider, []):
        provider = next(iter(provider_models))
        model = provider_models[provider][0]

    return {
        "provider": provider,
        "model": model,
        "reason": chosen["reason"],
        "route_id": chosen["id"],
    }
