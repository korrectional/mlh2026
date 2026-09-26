"""
Gemini API client — shared across all three tools.

Uses the google-genai SDK (newer generation).
Set GEMINI_API_KEY in .env to enable real AI responses.
"""

from __future__ import annotations

from utils.helpers import GEMINI_API_KEY

# Lazy import so the app can start without the SDK installed
_genai = None
_client = None


def _get_client():
    global _genai, _client
    if _client is not None:
        return _client
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai as _genai
        _client = _genai.Client(api_key=GEMINI_API_KEY)
        return _client
    except ImportError:
        return None


DEFAULT_MODEL = "gemini-2.0-flash"


async def ask_gemini(
    prompt: str,
    context: str = "",
    system_prompt: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Send a prompt to Gemini and return the response text.

    Args:
        prompt: The main instruction / user question.
        context: Optional background context (e.g. assignment text, notes).
        system_prompt: Optional system-level instruction.
        model: Gemini model name (default: gemini-2.0-flash).

    Returns:
        Response text string, or an error/fallback message.
    """
    client = _get_client()
    if not client:
        return _stub_response(prompt, context)

    try:
        full_prompt = _build_prompt(prompt, context, system_prompt)

        response = await client.aio.models.generate_content(
            model=model,
            contents=full_prompt,
        )
        return response.text or "[Gemini returned empty response]"

    except Exception as exc:
        return f"[Gemini error: {exc}]"


async def ask_gemini_structured(
    prompt: str,
    context: str = "",
    system_prompt: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Like ask_gemini, but adds a JSON-structure instruction to the prompt
    for tools that need parseable output (e.g. quizzes).
    """
    structure_hint = (
        "\n\nIMPORTANT: Respond with valid structured content "
        "(e.g. numbered lists, clear sections). "
        "Use markdown headings for sections."
    )
    return await ask_gemini(
        prompt=prompt + structure_hint,
        context=context,
        system_prompt=system_prompt,
        model=model,
    )


# ── Internals ──────────────────────────────────────────────────────────

def _build_prompt(prompt: str, context: str, system_prompt: str | None) -> str:
    parts = []
    if system_prompt:
        parts.append(f"[System]\n{system_prompt}\n")
    if context:
        parts.append(f"[Context]\n{context}\n")
    parts.append(f"[Instruction]\n{prompt}")
    return "\n".join(parts)


def _stub_response(prompt: str, context: str) -> str:
    """Return a placeholder when no API key or SDK is configured."""
    msg = []
    if not GEMINI_API_KEY:
        msg.append("⚠️  **Gemini API key not configured.**")
        msg.append("Copy `.env.example` to `.env` and set `GEMINI_API_KEY`.")
    else:
        msg.append("⚠️  **Gemini SDK not available.**")
        msg.append("Run: `pip install google-genai`")

    if context:
        msg.append(f"\n\n**Context received:** {context[:200]}...")
    msg.append(f"\n**Prompt:** {prompt[:200]}...")
    return "\n\n".join(msg)