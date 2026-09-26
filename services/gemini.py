import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Shared Gemini client stub — each branch will flesh this out
async def ask_gemini(prompt: str, context: str = "") -> str:
    """Send a prompt to Gemini and return the response text."""
    if not GEMINI_API_KEY:
        return "[Gemini API key not configured — set GEMINI_API_KEY in .env]"
    # TODO: branch will replace with actual genai SDK call
    return f"Stub response for: {prompt[:60]}..."