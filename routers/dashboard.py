"""Dashboard Inspector router — stub for branch."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard_page():
    """Placeholder — branch will render full template."""
    return "<h1>Dashboard Inspector — under construction</h1>"


@router.post("/inspect")
async def inspect_dashboard(request: Request):
    """Placeholder — branch will parse Moodle HTML and return study points."""
    form = await request.form()
    html = form.get("dashboard_html", "")
    return HTMLResponse(f"""
        <div class="p-4 bg-blue-50 rounded border">
            <p>Received {len(html)} chars of dashboard HTML.</p>
            <p>Assignment parsing not yet implemented.</p>
        </div>
    """)


@router.post("/quiz")
async def dashboard_quiz():
    """Placeholder — branch will generate a quiz for a specific assignment."""
    return HTMLResponse("<p>Quiz generation not yet implemented.</p>")