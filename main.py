"""
MLH 2026 — AI Toolkit App

FastAPI server serving the localhost frontend + API routes.
Three tools: Lecture Note-Taker, Study Buddy, Dashboard Inspector.
"""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from routers import lecture, study_buddy, dashboard
from utils.helpers import GEMINI_API_KEY

# ── App ────────────────────────────────────────────────────────────────
app = FastAPI(title="MLH Toolkit", version="0.1.0")

# ── Static files & templates ────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
STATIC_DIR = str(BASE_DIR / "static")
TEMPLATES_DIR = str(BASE_DIR / "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Template rendering (direct Jinja2, bypass Starlette Jinja2Templates) ──
from jinja2 import Environment, FileSystemLoader
_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    cache_size=0,
    auto_reload=True,
)


async def render_template(name: str, request: Request, **extra) -> str:
    """Render a Jinja2 template with the given context."""
    template = _jinja_env.get_template(name)
    context = {"request": request, **extra}
    return template.render(**context)


# ── Routers ─────────────────────────────────────────────────────────────
app.include_router(lecture.router)
app.include_router(study_buddy.router)
app.include_router(dashboard.router)


# ── Home ────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    html = await render_template("index.html", request=request)
    return HTMLResponse(html)


# ── Startup health check ────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    if not GEMINI_API_KEY:
        print("⚠️  GEMINI_API_KEY not set — AI features will return stubs.")
        print("   Copy .env.example to .env and add your key.")
    else:
        print(f"✅ Gemini API key found ({GEMINI_API_KEY[:8]}...)")

    # Verify templates load
    for t in ["index.html", "base.html", "lecture.html", "study-buddy.html", "dashboard.html"]:
        try:
            _jinja_env.get_template(t)
            print(f"   ✅ Template: {t}")
        except Exception as e:
            print(f"   ❌ Template: {t} — {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)