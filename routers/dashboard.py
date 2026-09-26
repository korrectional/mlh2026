"""
Dashboard Inspector — routes.

Flow:
  1. User pastes Moodle dashboard HTML → /dashboard/inspect
  2. Backend parses it → returns list of assignments with due dates
  3. User clicks "Study Points" or "Generate Quiz" for an assignment
  4. Gemini generates the content → returned as HTML snippets via HTMX
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from pathlib import Path

from services.moodle_scraper import parse_dashboard, extract_assignment_detail
from services.gemini import ask_gemini, ask_gemini_structured
from services.moodle_browser import open_moodle, grab_active_page

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Direct Jinja2 (same setup as main.py)
from jinja2 import Environment, FileSystemLoader
_jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")),
    cache_size=0,
    auto_reload=True,
)


async def render_template(name: str, request: Request, **extra) -> HTMLResponse:
    """Render a Jinja2 template and return an HTMLResponse."""
    template = _jinja_env.get_template(name)
    context = {"request": request, **extra}
    return HTMLResponse(template.render(**context))


# ── Page ───────────────────────────────────────────────────────────────

MOODLE_URL = "https://moodle-courses2527.wolfware.ncsu.edu/my/"


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return await render_template("dashboard.html", request=request)


# ── Open Moodle in browser ───────────────────────────────────────────

@router.get("/open-moodle", response_class=HTMLResponse)
async def open_moodle():
    """Redirect the browser to the NCSU Moodle dashboard."""
    return HTMLResponse(f'''
    <!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <title>Opening Moodle...</title>
    <meta http-equiv="refresh" content="0;url={MOODLE_URL}">
    <style>body {{ font-family: sans-serif; padding: 2em; text-align: center; }}</style>
    </head><body>
    <p>🔗 Opening Moodle dashboard...</p>
    <p><a href="{MOODLE_URL}">Click here if not redirected</a></p>
    </body></html>
    ''')


# ── Bookmarklet (future) ─────────────────────────────────────────────

@router.get("/bookmarklet", response_class=HTMLResponse)
async def bookmarklet_page():
    """Page with a bookmarklet for one-click Moodle scraping."""
    bookmarklet_js = (
        "javascript:(function(){"
        "var html=document.documentElement.outerHTML;"
        "var x=new XMLHttpRequest();"
        "x.open('POST','http://127.0.0.1:8000/dashboard/bookmarklet-capture',true);"
        "x.setRequestHeader('Content-Type','application/x-www-form-urlencoded');"
        "x.send('html='+encodeURIComponent(html));"
        "alert('Sent to Dashboard Inspector!');"
        "})()"
    )
    return HTMLResponse(f'''
    <!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <title>Dashboard Inspector Bookmarklet</title>
    </head><body style="font-family: sans-serif; max-width: 600px; margin: 2em auto; line-height: 1.6;">
    <h1>📋 Bookmarklet</h1>
    <p>Drag this link to your bookmarks bar:</p>
    <p>
        <a href="{bookmarklet_js}"
           style="display: inline-block; padding: 12px 24px; background: #2563eb; color: white;
                  text-decoration: none; border-radius: 8px; font-weight: bold;">
           📥 Send to Dashboard Inspector
        </a>
    </p>
    <p>Then, when you're on your Moodle dashboard, click the bookmarklet.</p>
    <p><a href="/dashboard/">← Back to Dashboard Inspector</a></p>
    </body></html>
    ''')


# ── Open & grab (pyautogui flow) ───────────────────────────────────────

@router.post("/fetch", response_class=HTMLResponse)
async def fetch_moodle():
    """Open Moodle dashboard in the user's browser."""
    try:
        open_moodle()
        return '''
        <div class="p-4 bg-green-50 border border-green-200 rounded-lg text-sm">
            <p class="font-semibold text-green-800">🌐 Moodle opened in your browser</p>
            <p class="text-green-700 mt-1">Log into WolfWare, then switch back here and click <strong>"Grab it!"</strong></p>
        </div>
        '''
    except Exception as e:
        return f'''
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg text-sm">
            <p class="font-semibold text-red-800">❌ Could not open browser</p>
            <p class="text-red-700 mt-1">{e}</p>
        </div>
        '''


@router.post("/grab", response_class=HTMLResponse)
async def grab_moodle():
    """
    Grab the HTML from the user's active browser tab using pyautogui.
    The user should be on the Moodle dashboard tab when this runs.
    """
    try:
        html = grab_active_page()

        if not html or len(html) < 100:
            return '''
            <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm">
                <p class="font-semibold text-yellow-800">😕 Didn't get much content</p>
                <p class="text-yellow-700 mt-1">
                    Make sure you were on the <strong>Moodle dashboard tab</strong>
                    when the grab happened. Try again.
                </p>
            </div>
            '''

        # Parse the grabbed HTML
        assignments = parse_dashboard(html)

        if not assignments:
            return '''
            <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm">
                <p class="font-semibold text-yellow-800">📋 Page grabbed but no assignments found</p>
                <p class="text-yellow-700 mt-1">
                    Got {} chars of HTML but couldn't find any assignments.
                    Make sure you're on the <strong>Moodle Dashboard → Timeline</strong> view.
                </p>
            </div>
            '''.format(len(html))

        # Render assignment cards (same as inspect endpoint output)
        sorted_assignments = sorted(
            assignments,
            key=lambda a: (0 if a.get("overdue") else 1, a.get("due_date", "")),
        )

        cards_html = ""
        for i, a in enumerate(sorted_assignments):
            overdue_badge = (
                '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">Overdue</span>'
                if a.get("overdue") else ""
            )
            due = a.get("due_date", "No date") or "No date"
            course = a.get("course", "") or "Unknown course"
            title = a.get("title", "Untitled")
            url = a.get("url", "")

            cards_html += f'''
            <div class="bg-white rounded-xl border p-5 hover:shadow-md transition assignment-card"
                 x-data="{{ open: false }}" id="assignment-{i}">

                <div class="flex items-start justify-between gap-4">
                    <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-2 flex-wrap">
                            <h3 class="text-base font-semibold text-gray-900 truncate">{title}</h3>
                            {overdue_badge}
                        </div>
                        <p class="text-sm text-gray-500 mt-0.5">
                            <span class="inline-flex items-center gap-1">📚 {course}</span>
                            <span class="mx-2">·</span>
                            <span class="inline-flex items-center gap-1">📅 {due}</span>
                        </p>
                    </div>
                </div>

                <div class="mt-3 flex gap-2 flex-wrap">
                    <button hx-post="/dashboard/study-points" hx-target="#assignment-{i} .results-area"
                            hx-vals='{{ "assignment": "{title}", "course": "{course}", "due_date": "{due}" }}'
                            class="px-3 py-1.5 text-xs font-medium rounded-lg bg-brand-50 text-brand-700 hover:bg-brand-100 border border-brand-200 transition">
                        📚 Study Points
                    </button>
                    <button hx-post="/dashboard/quiz" hx-target="#assignment-{i} .results-area"
                            hx-vals='{{ "assignment": "{title}", "course": "{course}", "due_date": "{due}" }}'
                            class="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-50 text-green-700 hover:bg-green-100 border border-green-200 transition">
                        📝 Generate Quiz
                    </button>
                </div>

                <div class="results-area mt-3"></div>
            </div>
            '''

        return f'''
        <div class="space-y-4">
            <div class="flex items-center justify-between">
                <h2 class="text-lg font-bold text-gray-900">
                    📋 Found {len(assignments)} assignment{'s' if len(assignments) != 1 else ''}
                </h2>
                <span class="text-xs text-gray-400">Grabbed from your browser</span>
            </div>
            {cards_html}
        </div>
        '''

    except Exception as e:
        return f'''
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg text-sm">
            <p class="font-semibold text-red-800">❌ Grab failed</p>
            <p class="text-red-700 mt-1">{e}</p>
            <p class="text-red-600 text-xs mt-2">Make sure no other app is stealing focus during the grab.</p>
        </div>
        '''


@router.post("/bookmarklet-capture")
async def bookmarklet_capture(html: str = Form("...")):
    """Receive HTML from the bookmarklet and redirect back to the dashboard."""
    from fastapi.responses import RedirectResponse
    # Store in session or return to dashboard with results
    # For now, redirect back to dashboard
    return HTMLResponse('''
    <!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <title>Received!</title>
    <style>body {{ font-family: sans-serif; padding: 2em; text-align: center; }}</style>
    </head><body>
    <p>✅ Dashboard HTML captured! Go back to the Dashboard Inspector.</p>
    <p><a href="/dashboard/">← Back to Dashboard Inspector</a></p>
    </body></html>
    ''')

@router.get("/debug/sample", response_class=HTMLResponse)
async def debug_sample():
    """Load the sample Moodle dashboard HTML and parse it — no Gemini needed."""
    sample_path = Path(__file__).resolve().parent.parent / "tests" / "sample_moodle_dashboard.html"
    html = sample_path.read_text(encoding="utf-8")
    assignments = parse_dashboard(html)

    if not assignments:
        return "<p class='text-red-600'>Sample HTML didn't parse any assignments.</p>"

    rows = ""
    for i, a in enumerate(assignments):
        overdue = '🔥 Overdue' if a.get('overdue') else '✅ On time'
        course = a.get('course', 'N/A')
        due = a.get('due_date', 'N/A')
        title = a.get('title', 'Untitled')
        rows += f"""
        <tr class="{"bg-red-50" if a.get('overdue') else ""}">
            <td class="px-3 py-2 text-sm font-medium">{title}</td>
            <td class="px-3 py-2 text-sm text-gray-600">{course}</td>
            <td class="px-3 py-2 text-sm text-gray-600">{due}</td>
            <td class="px-3 py-2 text-sm">{overdue}</td>
        </tr>"""

    return f"""
    <div class="text-sm">
        <p class="font-semibold mb-2">📋 Parsed {len(assignments)} assignments</p>
        <table class="w-full border-collapse">
            <thead>
                <tr class="bg-gray-100 text-left">
                    <th class="px-3 py-2 text-xs font-semibold text-gray-600">Title</th>
                    <th class="px-3 py-2 text-xs font-semibold text-gray-600">Course</th>
                    <th class="px-3 py-2 text-xs font-semibold text-gray-600">Due</th>
                    <th class="px-3 py-2 text-xs font-semibold text-gray-600">Status</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
                {rows}
            </tbody>
        </table>
    </div>
    """


# ── Raw scrape (JSON) — for testing without Gemini ───────────────────

# ── Debug: return raw sample HTML ──────────────────────────────────

@router.get("/debug/sample-raw", response_class=HTMLResponse)
async def debug_sample_raw():
    """Return the raw sample Moodle dashboard HTML."""
    sample_path = Path(__file__).resolve().parent.parent / "tests" / "sample_moodle_dashboard.html"
    return sample_path.read_text(encoding="utf-8")


@router.post("/scrape-only", response_class=HTMLResponse)
async def scrape_only(dashboard_html: str = Form(...)):
    """Parse dashboard HTML and return results — no Gemini calls."""
    assignments = parse_dashboard(dashboard_html)

    if not assignments:
        return "<p class='p-4 text-yellow-700 bg-yellow-50 rounded'>No assignments found. Try a different view or copy more of the page.</p>"

    rows = ""
    for a in assignments:
        overdue_badge = '🔥' if a.get('overdue') else ''
        rows += f"""
        <tr class="{"bg-red-50/50" if a.get('overdue') else ""}">
            <td class="px-3 py-2 text-sm font-medium">{a.get('title', '')} {overdue_badge}</td>
            <td class="px-3 py-2 text-sm text-gray-600">{a.get('course', '')}</td>
            <td class="px-3 py-2 text-sm text-gray-600">{a.get('due_date', '')}</td>
            <td class="px-3 py-2 text-sm">
                <a href="{a.get('url', '#')}" target="_blank" class="text-brand-600 hover:underline text-xs">Open ↗</a>
            </td>
        </tr>"""

    return f"""
    <div class="p-4 bg-gray-50 rounded-lg border text-sm">
        <p class="font-semibold mb-2">✅ {len(assignments)} assignment{'s' if len(assignments) != 1 else ''} parsed</p>
        <table class="w-full border-collapse">
            <thead>
                <tr class="bg-gray-100 text-left">
                    <th class="px-3 py-1.5 text-xs font-semibold text-gray-500 uppercase">Assignment</th>
                    <th class="px-3 py-1.5 text-xs font-semibold text-gray-500 uppercase">Course</th>
                    <th class="px-3 py-1.5 text-xs font-semibold text-gray-500 uppercase">Due</th>
                    <th class="px-3 py-1.5 text-xs font-semibold text-gray-500 uppercase">Link</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
                {rows}
            </tbody>
        </table>
    </div>
    """


# ── Inspect dashboard HTML ─────────────────────────────────────────────

@router.post("/inspect", response_class=HTMLResponse)
async def inspect_dashboard(dashboard_html: str = Form(...)):
    """Parse Moodle dashboard HTML and return assignment cards."""
    assignments = parse_dashboard(dashboard_html)

    if not assignments:
        return """
        <div class="p-6 bg-yellow-50 border border-yellow-200 rounded-xl text-center">
            <p class="text-yellow-800 font-medium text-lg">😕 No assignments found</p>
            <p class="text-yellow-700 text-sm mt-1">
                Couldn't parse any assignments from that HTML.
                Make sure you're copying from the <strong>Moodle Dashboard → Timeline</strong> view.
            </p>
            <details class="mt-3 text-left text-sm text-yellow-700">
                <summary class="cursor-pointer font-medium">Tips</summary>
                <ul class="list-disc list-inside mt-2 space-y-1">
                    <li>Log into <strong>WolfWare</strong> and go to your Dashboard</li>
                    <li>Open DevTools (<kbd>F12</kbd>) → <code>Elements</code> tab</li>
                    <li>Right-click <code>&lt;body&gt;</code> → <strong>Copy → Copy OuterHTML</strong></li>
                    <li>Make sure the <strong>Timeline</strong> block is visible</li>
                </ul>
            </details>
        </div>
        """

    # Sort: overdue first, then by due date approximation
    sorted_assignments = sorted(
        assignments,
        key=lambda a: (0 if a.get("overdue") else 1, a.get("due_date", "")),
    )

    cards_html = ""
    for i, a in enumerate(sorted_assignments):
        overdue_badge = (
            '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">Overdue</span>'
            if a.get("overdue") else ""
        )
        due = a.get("due_date", "No date") or "No date"
        course = a.get("course", "") or "Unknown course"
        title = a.get("title", "Untitled")
        url = a.get("url", "")

        cards_html += f"""
        <div class="bg-white rounded-xl border p-5 hover:shadow-md transition assignment-card"
             x-data="{{ open: false }}" id="assignment-{i}">

            <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2 flex-wrap">
                        <h3 class="text-base font-semibold text-gray-900 truncate">{title}</h3>
                        {overdue_badge}
                    </div>
                    <p class="text-sm text-gray-500 mt-0.5">
                        <span class="inline-flex items-center gap-1">📚 {course}</span>
                        <span class="mx-2">·</span>
                        <span class="inline-flex items-center gap-1">📅 {due}</span>
                    </p>
                </div>
            </div>

            <div class="mt-3 flex gap-2 flex-wrap">
                <button hx-post="/dashboard/study-points" hx-target="#assignment-{i} .results-area"
                        hx-vals='{{"assignment": "{_escape_json(title)}", "course": "{_escape_json(course)}", "due_date": "{_escape_json(due)}", "description": "{_escape_json(a.get('description', ''))}"}}'
                        hx-indicator="#spinner-{i}"
                        class="px-3 py-1.5 text-xs font-medium rounded-lg bg-brand-50 text-brand-700 hover:bg-brand-100 border border-brand-200 transition">
                    📚 Study Points
                </button>
                <button hx-post="/dashboard/quiz" hx-target="#assignment-{i} .results-area"
                        hx-vals='{{"assignment": "{_escape_json(title)}", "course": "{_escape_json(course)}", "due_date": "{_escape_json(due)}", "description": "{_escape_json(a.get('description', ''))}"}}'
                        hx-indicator="#spinner-{i}"
                        class="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-50 text-green-700 hover:bg-green-100 border border-green-200 transition">
                    📝 Generate Quiz
                </button>
                <div id="spinner-{i}" class="htmx-indicator">
                    <div class="w-4 h-4 border-2 border-brand-200 border-t-brand-600 rounded-full animate-spin"></div>
                </div>
            </div>

            <div class="results-area mt-3"></div>
        </div>
        """

    return f"""
    <div class="space-y-4">
        <div class="flex items-center justify-between">
            <h2 class="text-lg font-bold text-gray-900">
                📋 Found {len(assignments)} assignment{'s' if len(assignments) != 1 else ''}
            </h2>
        </div>
        {cards_html}
    </div>
    """


# ── Study points for a single assignment ──────────────────────────────

@router.post("/study-points", response_class=HTMLResponse)
async def study_points(
    assignment: str = Form(...),
    course: str = Form(""),
    due_date: str = Form(""),
    description: str = Form(""),
):
    """Generate study points for a specific assignment via Gemini."""
    context_parts = [f"Assignment: {assignment}"]
    if course:
        context_parts.append(f"Course: {course}")
    if due_date:
        context_parts.append(f"Due: {due_date}")
    if description:
        context_parts.append(f"Description: {description}")

    context = "\n".join(context_parts)

    prompt = (
        f"I'm a student preparing for this assignment: '{assignment}'.\n"
        f"Generate a concise list of key topics I should study to complete it successfully.\n"
        f"Focus on concepts, techniques, and areas I should review.\n"
        f"Format as a clean markdown bullet list with brief explanations."
    )

    result = await ask_gemini_structured(
        prompt=prompt,
        context=context,
        system_prompt=(
            "You are a helpful study assistant. Give concise, actionable study advice. "
            "Do NOT do the assignment for the student. Focus on what they should LEARN."
        ),
    )

    return f"""
    <div class="p-4 bg-brand-50 border border-brand-200 rounded-lg text-sm mt-3">
        <p class="font-semibold text-brand-800 mb-2">📚 Study Points</p>
        <div class="text-gray-700 prose prose-sm max-w-none">
            {_render_markdown(result)}
        </div>
    </div>
    """


# ── Quiz for a single assignment ──────────────────────────────────────

@router.post("/quiz", response_class=HTMLResponse)
async def generate_quiz(
    assignment: str = Form(...),
    course: str = Form(""),
    due_date: str = Form(""),
    description: str = Form(""),
):
    """Generate a practice quiz for a specific assignment via Gemini."""
    context_parts = [f"Assignment: {assignment}"]
    if course:
        context_parts.append(f"Course: {course}")
    if due_date:
        context_parts.append(f"Due: {due_date}")
    if description:
        context_parts.append(f"Description: {description}")

    context = "\n".join(context_parts)

    prompt = (
        f"Create a short practice quiz for the assignment: '{assignment}'.\n"
        f"Include 3-5 questions covering the key concepts.\n"
        f"For each question:\n"
        f"- Q: the question\n"
        f"- A: the correct answer\n"
        f"- E: a brief explanation of why it's correct\n\n"
        f"Use this format:\n"
        f"### Question 1\n"
        f"**Q:** ...\n"
        f"**A:** ...\n"
        f"**E:** ..."
    )

    result = await ask_gemini_structured(
        prompt=prompt,
        context=context,
        system_prompt=(
            "You are a tutor creating practice quizzes. "
            "Make questions that test understanding, not just recall. "
            "Always include explanations for the correct answers."
        ),
    )

    return f"""
    <div class="p-4 bg-green-50 border border-green-200 rounded-lg text-sm mt-3">
        <p class="font-semibold text-green-800 mb-2">📝 Practice Quiz</p>
        <div class="text-gray-700 prose prose-sm max-w-none quiz-content">
            {_render_markdown(result)}
        </div>
    </div>
    """


# ── Helpers ────────────────────────────────────────────────────────────

def _escape_json(s: str) -> str:
    """Escape a string for embedding in an HTMX hx-vals JSON value."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")
    escaped = escaped.replace("\n", " ").replace("\r", "")
    return escaped


def _render_markdown(text: str) -> str:
    """
    Minimal markdown-to-HTML renderer.
    Handles: **bold**, headings, bullet lists, paragraphs, code.
    For production, consider using `markdown` library.
    """
    import html as html_mod

    lines = text.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Headings
        if stripped.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h4 class='font-semibold mt-3 mb-1'>{_inline_html(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3 class='font-bold mt-3 mb-1'>{_inline_html(stripped[3:])}</h3>")
        elif stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2 class='font-bold mt-3 mb-1'>{_inline_html(stripped[2:])}</h2>")

        # Bullet list
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_lines.append("<ul class='list-disc list-inside space-y-1 my-2'>")
                in_list = True
            html_lines.append(f"<li>{_inline_html(stripped[2:])}</li>")

        # Numbered list
        elif stripped and stripped[0].isdigit() and ". " in stripped[:4]:
            if not in_list:
                html_lines.append("<ol class='list-decimal list-inside space-y-1 my-2'>")
                in_list = True
            text_part = stripped.split(". ", 1)[1] if ". " in stripped else stripped
            html_lines.append(f"<li>{_inline_html(text_part)}</li>")

        # Empty line = paragraph break
        elif not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("")

        # Regular paragraph
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p class='my-1'>{_inline_html(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _inline_html(text: str) -> str:
    """Convert inline markdown (**bold**, `code`) to HTML."""
    import html as html_mod

    escaped = html_mod.escape(text)

    # **bold**
    import re
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    # `code`
    escaped = re.sub(r"`(.+?)`", r"<code class='bg-gray-100 px-1 rounded text-xs'>\1</code>", escaped)

    return escaped