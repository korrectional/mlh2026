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

from services.moodle_scraper import parse_dashboard, extract_assignment_detail, enrich_assignments_with_descriptions
from services.gemini import ask_gemini, ask_gemini_structured
from services.moodle_browser import open_dashboard_and_grab, grab_moodle_page, grab_assignment_descriptions

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

@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return await render_template("dashboard.html", request=request)


# ── Debug: load sample HTML ──────────────────────────────────────────

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


# ── Grab (pyautogui flow) ──────────────────────────────────────────────

@router.post("/grab", response_class=HTMLResponse)
async def grab_moodle():
    """
    Open a new tab, navigate to Moodle, wait for load, then grab the HTML
    via pyautogui keyboard shortcuts.
    """
    from services.moodle_browser import open_dashboard_and_grab as _grab
    try:
        html = _grab(url="https://moodle-courses2527.wolfware.ncsu.edu/my/")

        if not html or len(html) < 100:
            return '''
            <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm">
                <p class="font-semibold text-yellow-800">😕 Didn't get much content</p>
                <p class="text-yellow-700 mt-1">
                    The page might not have loaded in time, or you need to
                    log into Moodle first. Try again.
                </p>
            </div>'''

        # Parse the grabbed HTML
        assignments = parse_dashboard(html)

        # 🔍 Enrich each assignment: visit the individual assignment page
        #    via PyAutoGUI and grab the full description text for AI context.
        #    This data is hidden from the user but sent to Gemini.
        if assignments:
            try:
                assignments = grab_assignment_descriptions(assignments, load_wait=2)
                assignments = enrich_assignments_with_descriptions(assignments)
                _print_descriptions(assignments)
            except Exception as e:
                print(f"  ⚠️  Assignment description enrichment failed: {e}")

        if not assignments:
            return '''
            <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm">
                <p class="font-semibold text-yellow-800">📋 Page grabbed but no assignments found</p>
                <p class="text-yellow-700 mt-1">
                    Got {} chars of page content but couldn't find any assignments.
                    Make sure you're on the <strong>Moodle Dashboard → Timeline</strong> view.
                </p>
            </div>'''.format(len(html))

        # Render assignment cards
        sorted_assignments = sorted(
            assignments,
            key=lambda a: (0 if a.get("overdue") else 1, _parse_date(a.get("due_date", ""))),
        )

        cards_html = ""
        for i, a in enumerate(sorted_assignments):
            overdue_badge = (
                '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">Overdue</span>'
                if a.get("overdue") else ""
            )
            due = _fmt_date(a.get("due_date", ""))
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
                            hx-vals='{{ "assignment": "{_escape_json(title)}", "course": "{_escape_json(course)}", "due_date": "{_escape_json(_fmt_date(a.get('due_date', '')))}", "description": "{_escape_json(a.get('description', ''))}" }}'
                            class="px-3 py-1.5 text-xs font-medium rounded-lg bg-brand-50 text-brand-700 hover:bg-brand-100 border border-brand-200 transition">
                        📚 Study Points
                    </button>
                    <button hx-post="/dashboard/quiz" hx-target="#assignment-{i} .results-area"
                            hx-vals='{{ "assignment": "{_escape_json(title)}", "course": "{_escape_json(course)}", "due_date": "{_escape_json(_fmt_date(a.get('due_date', '')))}", "description": "{_escape_json(a.get('description', ''))}" }}'
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
        {_CONSOLE_DUMP}
        '''

    except Exception as e:
        return f'''
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg text-sm">
            <p class="font-semibold text-red-800">❌ Grab failed</p>
            <p class="text-red-700 mt-1">{e}</p>
            <p class="text-red-600 text-xs mt-2">Make sure no other app is stealing focus during the grab.</p>
        </div>
        '''


# ── Raw scrape — for testing without Gemini ─────────────────────────

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
            <td class="px-3 py-2 text-sm font-medium">{f'<a href="{a.get("url", "")}" target="_blank" class="hover:text-brand-600 transition">{a.get("title", "")}</a>' if a.get('url') else a.get('title', '')} {overdue_badge}</td>
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

    # Sort: overdue first, then by parsed date
    sorted_assignments = sorted(
        assignments,
        key=lambda a: (0 if a.get("overdue") else 1, _parse_date(a.get("due_date", ""))),
    )

    cards_html = ""
    for i, a in enumerate(sorted_assignments):
        overdue_badge = (
            '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">Overdue</span>'
            if a.get("overdue") else ""
        )
        due = _fmt_date(a.get("due_date", ""))
        course = a.get("course", "") or "Unknown course"
        title = a.get("title", "Untitled")
        url = a.get("url", "")

        cards_html += f"""
        <div class="bg-white rounded-xl border p-5 hover:shadow-md transition assignment-card"
             x-data="{{ open: false }}" id="assignment-{i}">

            <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2 flex-wrap">
                        <h3 class="text-base font-semibold text-gray-900 truncate">{f'<a href="{url}" target="_blank" class="hover:text-brand-600 transition">{title}</a>' if url else title}</h3>
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
                {"""<button hx-post="/dashboard/grab-instructions" hx-target="#assignment-{i} .results-area"
                        hx-vals='{{"url": "{_escape_json(url)}", "title": "{_escape_json(title)}"}}'
                        hx-indicator="#spinner-{i}"
                        class="px-3 py-1.5 text-xs font-medium rounded-lg bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 transition">
                    📥 Grab Instructions
                </button>""" if url else ""}
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


# ── Grab instructions from an assignment page ──────────────────────────

import re as _re
from bs4 import BeautifulSoup


def _extract_instructions(html: str) -> dict:
    """
    Parse an assignment detail page for instructions, Google Doc links,
    and other useful content.

    Returns a dict with:
      - instructions: plain text of the assignment description
      - doc_links: list of Google Doc URLs found
      - other_links: list of other external links
    """
    soup = BeautifulSoup(html, "html.parser")

    # Look for the main content area (Moodle assignment description)
    description_el = soup.select_one(
        ".no-overflow, #intro, [data-region='assignment-info'], "
        ".activity-description, .generalbox, .box.py-3"
    )
    instructions = description_el.get_text("\n", strip=True) if description_el else ""

    # Fallback: grab all visible text from the page
    if not instructions or len(instructions) < 50:
        body = soup.find("body")
        if body:
            # Remove script, style, nav, header, footer noise
            for tag in body.select("script, style, nav, header, footer, .navbar, .footer, .breadcrumb"):
                tag.decompose()
            instructions = body.get_text("\n", strip=True)
            # Truncate to first 8000 chars
            instructions = instructions[:8000]

    # Find all links
    doc_links = []
    other_links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(strip=True)
        if "docs.google.com" in href or "google.com/document" in href:
            doc_links.append({"url": href, "text": text or "Google Doc"})
        elif href.startswith("http") and "moodle" not in href and "wolfware" not in href:
            other_links.append({"url": href, "text": text or href[:60]})

    return {
        "instructions": instructions[:5000],
        "doc_links": doc_links[:10],
        "other_links": other_links[:10],
    }


@router.post("/grab-instructions", response_class=HTMLResponse)
async def grab_instructions(
    url: str = Form(...),
    title: str = Form(""),
):
    """
    Navigate to an assignment URL via PyAutoGUI, grab the page content,
    and extract instructions / Google Doc links.
    """
    try:
        html = grab_moodle_page(url, load_wait=4)

        if not html or len(html) < 100:
            return f'''
            <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm mt-3">
                <p class="font-semibold text-yellow-800">😕 Didn't get much content</p>
                <p class="text-yellow-700 mt-1">
                    The assignment page might not have loaded in time.
                    Try again and make sure your browser is focused.
                </p>
            </div>
            '''

        parsed = _extract_instructions(html)
        instructions = parsed["instructions"]
        doc_links = parsed["doc_links"]
        other_links = parsed["other_links"]

        if not instructions and not doc_links:
            return f'''
            <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm mt-3">
                <p class="font-semibold text-yellow-800">📄 Page grabbed but no instructions found</p>
                <p class="text-yellow-700 mt-1">
                    Grabbed {len(html)} characters but couldn't extract specific instructions.
                    <a href="{_escape_json(url)}" target="_blank" class="text-brand-600 hover:underline">Open manually ↗</a>
                </p>
            </div>
            '''

        # Build the response
        parts = []

        # Google Doc links
        if doc_links:
            doc_items = "".join(
                f'<li><a href="{d["url"]}" target="_blank" class="text-brand-600 hover:underline">📄 {_escape_html(d["text"])}</a></li>'
                for d in doc_links
            )
            parts.append(f'''
                <div class="mb-3">
                    <p class="font-semibold text-sm text-gray-800 mb-1">📎 Reference Documents</p>
                    <ul class="list-disc list-inside space-y-0.5 text-sm">{doc_items}</ul>
                </div>
            ''')

        # Other links
        if other_links:
            other_items = "".join(
                f'<li><a href="{l["url"]}" target="_blank" class="text-brand-600 hover:underline">🔗 {_escape_html(l["text"])}</a></li>'
                for l in other_links
            )
            parts.append(f'''
                <div class="mb-3">
                    <p class="font-semibold text-sm text-gray-800 mb-1">🔗 Other Links</p>
                    <ul class="list-disc list-inside space-y-0.5 text-sm">{other_items}</ul>
                </div>
            ''')

        # Instructions text
        if instructions:
            # Truncate to 2000 chars for display
            display_text = instructions[:2000]
            if len(instructions) > 2000:
                display_text += "..."
            parts.append(f'''
                <div>
                    <p class="font-semibold text-sm text-gray-800 mb-1">📝 Instructions</p>
                    <div class="text-sm text-gray-700 whitespace-pre-wrap max-h-60 overflow-y-auto bg-gray-50 rounded p-3">{_escape_html(display_text)}</div>
                </div>
            ''')

        content = "\n".join(parts)

        return f'''
        <div class="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm mt-3">
            <p class="font-semibold text-blue-800 mb-2 flex items-center gap-2">
                📥 Instructions Grabbed
                <span class="text-xs font-normal text-blue-600">for {_escape_html(title)}</span>
            </p>
            {content}
            <p class="text-xs text-blue-500 mt-2">
                Grabbed {len(html)} chars from assignment page.
                <a href="{_escape_json(url)}" target="_blank" class="hover:underline">Open in tab ↗</a>
            </p>
        </div>
        '''

    except Exception as e:
        return f'''
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg text-sm mt-3">
            <p class="font-semibold text-red-800">❌ Grab failed</p>
            <p class="text-red-700 mt-1">{_escape_html(str(e))}</p>
            <p class="text-red-600 text-xs mt-2">
                Make sure no other app is stealing focus during the grab.
                <a href="{_escape_json(url)}" target="_blank" class="hover:underline">Open manually ↗</a>
            </p>
        </div>
        '''


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
    """Escape a string for embedding in an HTMX hx-vals JSON value.

    Uses json.dumps() for proper JSON escaping (handles \\, \", \\n, \\t, etc.)
    then strips the surrounding double quotes that json.dumps adds.

    Critically: does NOT escape single quotes — hx-vals='...' uses single
    quotes as the HTML attribute delimiter, so escaping ' would break it.
    """
    import json as _json
    return _json.dumps(s, ensure_ascii=False)[1:-1]


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


def _fmt_date(raw: str) -> str:
    """
    Format a due date string for display — strips day-of-week and trailing time.

    Input:  "Sunday, September 27, 2026 23:59"
    Output: "September 27, 2026"
    """
    if not raw:
        return "No date"
    import re as _re
    cleaned = _re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*", "", raw, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"\s+\d{1,2}:\d{2}\s*(AM|PM)?$", "", cleaned, flags=_re.IGNORECASE)
    return cleaned.strip() or "No date"


def _parse_date(raw: str) -> str:
    """Parse a due date into YYYY-MM-DD for sorting."""
    import re as _re
    from datetime import datetime
    if not raw:
        return ""
    cleaned = _re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*", "", raw, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"\s+\d{1,2}:\d{2}\s*(AM|PM)?$", "", cleaned, flags=_re.IGNORECASE)
    cleaned = cleaned.strip()
    if not cleaned:
        return ""
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return cleaned


def _escape_html(text: str) -> str:
    """Escape a string for safe embedding in HTML."""
    import html as html_mod
    return html_mod.escape(text)


# ── Print descriptions to server console ──────────────────────────────

_CONSOLE_DUMP: str = ""  # <script> block injected into grab response


def _print_descriptions(assignments: list[dict]) -> None:
    """
    Print every collected description to the server terminal so the user
    can verify the text in the CMD window where uvicorn is running.
    """
    print()
    print("=" * 72)
    print("  ASSIGNMENT DESCRIPTION REPORT")
    print("=" * 72)

    total_chars = 0
    grabbed_count = 0

    for i, a in enumerate(assignments):
        title = a.get("title", "?")
        course = a.get("course", "?")
        desc = a.get("description", "") or ""
        char_count = len(desc)
        total_chars += char_count

        print()
        print(f"  [{i+1}] {title}")
        print(f"      Course: {course}  |  {char_count} chars")
        print(f"      {'─' * 60}")

        if char_count > 50:
            grabbed_count += 1
            # Print the FULL text, indented
            for line in desc.split("\n"):
                print(f"      {line}")
        else:
            print(f"      (no description collected)")

        print(f"      {'─' * 60}")

    print()
    print(f"  Summary: {grabbed_count}/{len(assignments)} assignments have descriptions")
    print(f"  Total:   {total_chars} chars collected for AI context")
    print("=" * 72)
    print()

    # Also build a small inline script tag showing summary in Chrome console
    global _CONSOLE_DUMP
    import json as _json
    records = [
        {"title": a.get("title", "?"), "course": a.get("course", "?"), "char_count": len(a.get("description", "") or "")}
        for a in assignments
    ]
    json_data = _json.dumps(records, indent=2, ensure_ascii=False)

    _CONSOLE_DUMP = f'''
<script>
console.log("=" .repeat(72));
console.log("  ASSIGNMENT DESCRIPTION REPORT  (" + new Date().toLocaleTimeString() + ")");
console.log("=" .repeat(72));
const _d = {json_data};
for (let i = 0; i < _d.length; i++) {{
    console.log(`  [${{i+1}}] ${{_d[i].title}}  --  ${{_d[i].course}}  (${{_d[i].char_count}} chars)`);
}}
console.log("=" .repeat(72));
console.log("  (Full text printed in the server terminal)");
console.log("=" .repeat(72));
</script>
'''