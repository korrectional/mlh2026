"""
MLH 2026 — AI Toolkit App

FastAPI server serving the localhost frontend + API routes.
Three tools: Lecture Note-Taker, Study Buddy, Dashboard Inspector.
"""

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from routers import lecture, study_buddy, dashboard
from utils.helpers import GEMINI_API_KEY

# ── App ────────────────────────────────────────────────────────────────
app = FastAPI(title="MLH Toolkit", version="0.1.0")

# ── Static files & templates ────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ── Routers ─────────────────────────────────────────────────────────────
app.include_router(lecture.router)
app.include_router(study_buddy.router)
app.include_router(dashboard.router)


# ── Home ────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Startup health check ────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    if not GEMINI_API_KEY:
        print("⚠️  GEMINI_API_KEY not set — AI features will return stubs.")
        print("   Copy .env.example to .env and add your key.")
    else:
        print(f"✅ Gemini API key found ({GEMINI_API_KEY[:8]}...)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)