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
from services.moodle_browser import grab_moodle_page

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Direct Jinja2 (same setup as main.py)
from jinja2 import Environment, FileSystemLoader
_jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")),
    cache_size=0,
    auto_reload=True,
)

# Inline SVG line icons (Lucide style) for the HTML snippets below.
_SVG_OPEN = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4 shrink-0" aria-hidden="true">'
)
_ICON_ARROW = _SVG_OPEN + '<path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>'
_ICON_FILE = (
    _SVG_OPEN
    + '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
    + '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>'
)
_ICON_LINK = (
    _SVG_OPEN
    + '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
    + '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>'
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
        return "<div class='rounded-2xl border border-neutral-700 bg-neutral-900 p-4 text-sm text-neutral-300'>The sample HTML did not parse any assignments.</div>"

    rows = ""
    for i, a in enumerate(assignments):
        overdue = (
            '<span class="dash-mono inline-flex items-center rounded-full bg-[#CC0000] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-white">Overdue</span>'
            if a.get('overdue') else
            '<span class="dash-mono text-[11px] uppercase tracking-[0.16em] text-neutral-500">On time</span>'
        )
        course = a.get('course', 'N/A')
        due = a.get('due_date', 'N/A')
        title = a.get('title', 'Untitled')
        rows += f"""
        <tr class="{"bg-neutral-900/40" if a.get('overdue') else ""}">
            <td class="px-6 py-3.5 text-sm font-medium text-white">{title}</td>
            <td class="px-6 py-3.5 text-sm text-neutral-400">{course}</td>
            <td class="dash-mono px-6 py-3.5 text-xs text-neutral-400">{due}</td>
            <td class="px-6 py-3.5 text-sm">{overdue}</td>
        </tr>"""

    return f"""
    <div class="dash-reveal overflow-hidden rounded-3xl border border-neutral-800 bg-neutral-950">
        <div class="flex items-center justify-between gap-4 border-b border-neutral-800 px-6 py-4">
            <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">{len(assignments)} assignments parsed</p>
            <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-600">Sample data</p>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full border-collapse text-left">
                <thead>
                    <tr class="border-b border-neutral-800">
                        <th class="dash-mono px-6 py-3 text-[11px] font-normal uppercase tracking-[0.2em] text-neutral-500">Title</th>
                        <th class="dash-mono px-6 py-3 text-[11px] font-normal uppercase tracking-[0.2em] text-neutral-500">Course</th>
                        <th class="dash-mono px-6 py-3 text-[11px] font-normal uppercase tracking-[0.2em] text-neutral-500">Due</th>
                        <th class="dash-mono px-6 py-3 text-[11px] font-normal uppercase tracking-[0.2em] text-neutral-500">Status</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-neutral-800">
                    {rows}
                </tbody>
            </table>
        </div>
    </div>
    """


# ── Grab (pyautogui flow) ──────────────────────────────────────────────

@router.post("/grab", response_class=HTMLResponse)
async def grab_moodle():
    """
    Open a new tab, navigate to Moodle, wait for load, then grab the HTML
    via pyautogui keyboard shortcuts.
    """
    from services.moodle_browser import grab_moodle_page as _grab
    try:
        html = _grab(url="https://moodle-courses2527.wolfware.ncsu.edu/my/")

        if not html or len(html) < 100:
            return '''
            <div class="rounded-2xl border border-neutral-700 bg-neutral-900 p-4 text-sm text-neutral-300">
                <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-400">Not enough content</p>
                <p class="mt-2 leading-relaxed">
                    The page may not have finished loading, or you may need to
                    sign in to Moodle first. Try again.
                </p>
            </div>'''

        # Parse the grabbed HTML
        assignments = parse_dashboard(html)

        if not assignments:
            return '''
            <div class="rounded-2xl border border-neutral-700 bg-neutral-900 p-4 text-sm text-neutral-300">
                <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-400">No assignments found</p>
                <p class="mt-2 leading-relaxed">
                    Grabbed {} characters but found no assignments.
                    Open the Moodle <span class="text-white">Dashboard</span> with the <span class="text-white">Timeline</span> block visible and try again.
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
                '<span class="dash-mono inline-flex shrink-0 items-center rounded-full bg-[#CC0000] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-white">Overdue</span>'
                if a.get("overdue") else ""
            )
            due = _fmt_date(a.get("due_date", ""))
            course = a.get("course", "") or "Unknown course"
            title = a.get("title", "Untitled")
            url = a.get("url", "")

            cards_html += f'''
            <div class="assignment-card rounded-3xl border border-neutral-800 bg-neutral-950 p-6"
                 x-data="{{ open: false }}" id="assignment-{i}">

                <div class="flex items-start justify-between gap-4">
                    <div class="min-w-0 flex-1">
                        <h3 class="truncate text-lg font-semibold tracking-tight text-white">{title}</h3>
                        <p class="dash-mono mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-neutral-500">
                            <span>{course}</span>
                            <span class="text-neutral-700">&middot;</span>
                            <span>{due}</span>
                        </p>
                    </div>
                    {overdue_badge}
                </div>

                <div class="mt-5 flex flex-wrap items-center gap-2">
                    <button hx-post="/dashboard/study-points" hx-target="#assignment-{i} .results-area"
                            hx-vals='{{ "assignment": "{title}", "course": "{course}", "due_date": "{_fmt_date(a.get('due_date', ''))}" }}'
                            class="rounded-full border border-neutral-800 px-4 py-2 text-sm text-neutral-300 transition hover:border-neutral-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#CC0000]/50">
                        Study points
                    </button>
                    <button hx-post="/dashboard/quiz" hx-target="#assignment-{i} .results-area"
                            hx-vals='{{ "assignment": "{title}", "course": "{course}", "due_date": "{_fmt_date(a.get('due_date', ''))}" }}'
                            class="rounded-full border border-neutral-800 px-4 py-2 text-sm text-neutral-300 transition hover:border-neutral-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#CC0000]/50">
                        Practice quiz
                    </button>
                </div>

                <div class="results-area mt-4 empty:hidden"></div>
            </div>
            '''

        return f'''
        <div class="dash-reveal space-y-4">
            <div class="flex items-end justify-between gap-4 px-1">
                <div>
                    <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">Timeline</p>
                    <h2 class="mt-1 text-2xl font-semibold tracking-tight text-white">
                        {len(assignments)} assignment{'s' if len(assignments) != 1 else ''}
                    </h2>
                </div>
                <span class="dash-mono inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-neutral-500">
                    <span class="h-1.5 w-1.5 rounded-full bg-[#CC0000]"></span>
                    Grabbed from browser
                </span>
            </div>
            {cards_html}
        </div>
        '''

    except Exception as e:
        return f'''
        <div class="rounded-2xl border border-[#CC0000]/50 bg-[#CC0000]/10 p-4 text-sm text-neutral-100">
            <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-white">Grab failed</p>
            <p class="mt-2 leading-relaxed">{e}</p>
            <p class="mt-2 text-xs text-neutral-400">Keep the browser window focused while the grab runs.</p>
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
        return "<div class='rounded-2xl border border-neutral-700 bg-neutral-900 p-4 text-sm text-neutral-300'>No assignments found. Try the Timeline view or copy more of the page.</div>"

    rows = ""
    for a in assignments:
        overdue_badge = '<span class="dash-mono ml-2 inline-flex items-center rounded-full bg-[#CC0000] px-2.5 py-0.5 align-middle text-[10px] uppercase tracking-[0.16em] text-white">Overdue</span>' if a.get('overdue') else ''
        rows += f"""
        <tr class="{"bg-neutral-900/40" if a.get('overdue') else ""}">
            <td class="px-6 py-3.5 text-sm font-medium text-white">{f'<a href="{a.get("url", "")}" target="_blank" class="text-white underline-offset-4 transition hover:underline">{a.get("title", "")}</a>' if a.get('url') else a.get('title', '')} {overdue_badge}</td>
            <td class="px-6 py-3.5 text-sm text-neutral-400">{a.get('course', '')}</td>
            <td class="dash-mono px-6 py-3.5 text-xs text-neutral-400">{a.get('due_date', '')}</td>
            <td class="px-6 py-3.5 text-sm">
                <a href="{a.get('url', '#')}" target="_blank" class="inline-flex items-center gap-1 text-sm text-neutral-300 underline-offset-4 transition hover:text-white hover:underline">Open {_ICON_ARROW}</a>
            </td>
        </tr>"""

    return f"""
    <div class="dash-reveal overflow-hidden rounded-3xl border border-neutral-800 bg-neutral-950">
        <div class="flex items-center justify-between gap-4 border-b border-neutral-800 px-6 py-4">
            <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">{len(assignments)} assignment{'s' if len(assignments) != 1 else ''} parsed</p>
            <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-600">Scrape only</p>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full border-collapse text-left">
                <thead>
                    <tr class="border-b border-neutral-800">
                        <th class="dash-mono px-6 py-3 text-[11px] font-normal uppercase tracking-[0.2em] text-neutral-500">Assignment</th>
                        <th class="dash-mono px-6 py-3 text-[11px] font-normal uppercase tracking-[0.2em] text-neutral-500">Course</th>
                        <th class="dash-mono px-6 py-3 text-[11px] font-normal uppercase tracking-[0.2em] text-neutral-500">Due</th>
                        <th class="dash-mono px-6 py-3 text-[11px] font-normal uppercase tracking-[0.2em] text-neutral-500">Link</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-neutral-800">
                    {rows}
                </tbody>
            </table>
        </div>
    </div>
    """


# ── Inspect dashboard HTML ─────────────────────────────────────────────

@router.post("/inspect", response_class=HTMLResponse)
async def inspect_dashboard(dashboard_html: str = Form(...)):
    """Parse Moodle dashboard HTML and return assignment cards."""
    assignments = parse_dashboard(dashboard_html)

    if not assignments:
        return """
        <div class="dash-reveal rounded-3xl border border-neutral-800 bg-neutral-950 p-7">
            <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">No results</p>
            <h3 class="mt-2 text-xl font-semibold tracking-tight text-white">No assignments found</h3>
            <p class="mt-2 max-w-prose text-sm leading-relaxed text-neutral-400">
                Nothing in that HTML looked like an assignment.
                Copy it from the Moodle <span class="text-neutral-200">Dashboard</span> with the <span class="text-neutral-200">Timeline</span> block visible.
            </p>
            <details class="dash-details mt-6 rounded-2xl bg-neutral-900/60 p-5 text-sm text-neutral-300">
                <summary class="dash-mono flex cursor-pointer list-none items-center justify-between gap-4 text-[11px] uppercase tracking-[0.2em] text-neutral-400 transition hover:text-white [&::-webkit-details-marker]:hidden">
                    How to copy the page
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="dash-chevron h-4 w-4 shrink-0" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>
                </summary>
                <ol class="mt-5 space-y-3">
                    <li class="flex gap-3"><span class="dash-mono w-5 shrink-0 text-xs text-neutral-600">01</span><span>Sign in to <span class="text-white">WolfWare</span> and open your Dashboard.</span></li>
                    <li class="flex gap-3"><span class="dash-mono w-5 shrink-0 text-xs text-neutral-600">02</span><span>Open DevTools with <kbd class="dash-mono rounded-md border border-neutral-700 bg-neutral-900 px-1.5 py-0.5 text-[11px] text-neutral-200">F12</kbd> and go to the Elements tab.</span></li>
                    <li class="flex gap-3"><span class="dash-mono w-5 shrink-0 text-xs text-neutral-600">03</span><span>Right-click <code class="dash-mono rounded-md bg-neutral-900 px-1.5 py-0.5 text-[12px] text-neutral-200">&lt;body&gt;</code>, then choose Copy, Copy outerHTML.</span></li>
                    <li class="flex gap-3"><span class="dash-mono w-5 shrink-0 text-xs text-neutral-600">04</span><span>Make sure the <span class="text-white">Timeline</span> block is visible before you copy.</span></li>
                </ol>
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
            '<span class="dash-mono inline-flex shrink-0 items-center rounded-full bg-[#CC0000] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-white">Overdue</span>'
            if a.get("overdue") else ""
        )
        due = _fmt_date(a.get("due_date", ""))
        course = a.get("course", "") or "Unknown course"
        title = a.get("title", "Untitled")
        url = a.get("url", "")
        grab_btn = f"""<button hx-post="/dashboard/grab-instructions" hx-target="#assignment-{i} .results-area"
                        hx-vals='{{"url": "{_escape_json(url)}", "title": "{_escape_json(title)}"}}'
                        hx-indicator="#spinner-{i}"
                        class="rounded-full border border-neutral-800 px-4 py-2 text-sm text-neutral-300 transition hover:border-neutral-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#CC0000]/50">
                    Grab instructions
                </button>""" if url else ""

        cards_html += f"""
        <div class="assignment-card rounded-3xl border border-neutral-800 bg-neutral-950 p-6"
             x-data="{{ open: false }}" id="assignment-{i}">

            <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                    <h3 class="truncate text-lg font-semibold tracking-tight text-white">{f'<a href="{url}" target="_blank" class="underline-offset-4 transition hover:underline">{title}</a>' if url else title}</h3>
                    <p class="dash-mono mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-neutral-500">
                        <span>{course}</span>
                        <span class="text-neutral-700">&middot;</span>
                        <span>{due}</span>
                    </p>
                </div>
                {overdue_badge}
            </div>

            <div class="mt-5 flex flex-wrap items-center gap-2">
                <button hx-post="/dashboard/study-points" hx-target="#assignment-{i} .results-area"
                        hx-vals='{{"assignment": "{_escape_json(title)}", "course": "{_escape_json(course)}", "due_date": "{_escape_json(due)}", "description": "{_escape_json(a.get('description', ''))}"}}'
                        hx-indicator="#spinner-{i}"
                        class="rounded-full border border-neutral-800 px-4 py-2 text-sm text-neutral-300 transition hover:border-neutral-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#CC0000]/50">
                    Study points
                </button>
                <button hx-post="/dashboard/quiz" hx-target="#assignment-{i} .results-area"
                        hx-vals='{{"assignment": "{_escape_json(title)}", "course": "{_escape_json(course)}", "due_date": "{_escape_json(due)}", "description": "{_escape_json(a.get('description', ''))}"}}'
                        hx-indicator="#spinner-{i}"
                        class="rounded-full border border-neutral-800 px-4 py-2 text-sm text-neutral-300 transition hover:border-neutral-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#CC0000]/50">
                    Practice quiz
                </button>
                {grab_btn}
                <div id="spinner-{i}" class="htmx-indicator ml-1">
                    <div class="h-4 w-4 animate-spin rounded-full border-2 border-neutral-800 border-t-[#CC0000]"></div>
                </div>
            </div>

            <div class="results-area mt-4 empty:hidden"></div>
        </div>
        """

    return f"""
    <div class="dash-reveal space-y-4">
        <div class="flex items-end justify-between gap-4 px-1">
            <div>
                <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">Timeline</p>
                <h2 class="mt-1 text-2xl font-semibold tracking-tight text-white">
                    {len(assignments)} assignment{'s' if len(assignments) != 1 else ''}
                </h2>
            </div>
            <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">Overdue first</p>
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
            <div class="rounded-2xl border border-neutral-700 bg-neutral-900 p-4 text-sm text-neutral-300">
                <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-400">Not enough content</p>
                <p class="mt-2 leading-relaxed">
                    The assignment page may not have finished loading.
                    Keep the browser window focused and try again.
                </p>
            </div>
            '''

        parsed = _extract_instructions(html)
        instructions = parsed["instructions"]
        doc_links = parsed["doc_links"]
        other_links = parsed["other_links"]

        if not instructions and not doc_links:
            return f'''
            <div class="rounded-2xl border border-neutral-700 bg-neutral-900 p-4 text-sm text-neutral-300">
                <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-400">No instructions found</p>
                <p class="mt-2 leading-relaxed">
                    Grabbed {len(html)} characters but could not find the assignment instructions.
                </p>
                <a href="{_escape_json(url)}" target="_blank" class="mt-3 inline-flex items-center gap-1 text-sm text-neutral-500 transition hover:text-white">Open assignment {_ICON_ARROW}</a>
            </div>
            '''

        # Build the response
        parts = []

        # Google Doc links
        if doc_links:
            doc_items = "".join(
                f'<li><a href="{d["url"]}" target="_blank" class="inline-flex items-center gap-2 text-neutral-300 underline-offset-4 transition hover:text-white hover:underline">{_ICON_FILE}{_escape_html(d["text"])}</a></li>'
                for d in doc_links
            )
            parts.append(f'''
                <div>
                    <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">Reference documents</p>
                    <ul class="mt-2 space-y-1.5 text-sm">{doc_items}</ul>
                </div>
            ''')

        # Other links
        if other_links:
            other_items = "".join(
                f'<li><a href="{l["url"]}" target="_blank" class="inline-flex items-center gap-2 text-neutral-300 underline-offset-4 transition hover:text-white hover:underline">{_ICON_LINK}{_escape_html(l["text"])}</a></li>'
                for l in other_links
            )
            parts.append(f'''
                <div>
                    <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">Other links</p>
                    <ul class="mt-2 space-y-1.5 text-sm">{other_items}</ul>
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
                    <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-neutral-500">Instructions</p>
                    <div class="mt-2 max-h-60 overflow-y-auto whitespace-pre-wrap rounded-xl border border-neutral-800 bg-neutral-950 p-4 text-sm leading-relaxed text-neutral-300">{_escape_html(display_text)}</div>
                </div>
            ''')

        content = "\n".join(parts)

        return f'''
        <div class="dash-reveal rounded-2xl border border-neutral-800 bg-neutral-900/60 p-5 text-sm text-neutral-200">
            <div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p class="dash-mono inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-neutral-400">
                    <span class="h-1.5 w-1.5 rounded-full bg-[#CC0000]"></span>
                    Instructions grabbed
                </p>
                <p class="min-w-0 truncate text-xs text-neutral-500">{_escape_html(title)}</p>
            </div>
            <div class="mt-4 space-y-5">
                {content}
            </div>
            <div class="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-neutral-800 pt-4">
                <p class="dash-mono text-[11px] text-neutral-500">{len(html)} characters from the assignment page</p>
                <a href="{_escape_json(url)}" target="_blank" class="inline-flex items-center gap-1 text-sm text-neutral-500 transition hover:text-white">Open in tab {_ICON_ARROW}</a>
            </div>
        </div>
        '''

    except Exception as e:
        return f'''
        <div class="rounded-2xl border border-[#CC0000]/50 bg-[#CC0000]/10 p-4 text-sm text-neutral-100">
            <p class="dash-mono text-[11px] uppercase tracking-[0.2em] text-white">Grab failed</p>
            <p class="mt-2 leading-relaxed">{_escape_html(str(e))}</p>
            <p class="mt-2 text-xs text-neutral-400">Keep the browser window focused while the grab runs.</p>
            <a href="{_escape_json(url)}" target="_blank" class="mt-3 inline-flex items-center gap-1 text-sm text-neutral-400 transition hover:text-white">Open assignment {_ICON_ARROW}</a>
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
    <div class="dash-reveal rounded-2xl border border-neutral-800 bg-neutral-900/60 p-5 text-sm text-neutral-300">
        <p class="dash-mono inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-neutral-400">
            <span class="h-1.5 w-1.5 rounded-full bg-[#CC0000]"></span>
            Study points
        </p>
        <div class="mt-3 max-w-none leading-relaxed text-neutral-300">
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
    <div class="dash-reveal rounded-2xl border border-neutral-800 bg-neutral-900/60 p-5 text-sm text-neutral-300">
        <p class="dash-mono inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-neutral-400">
            <span class="h-1.5 w-1.5 rounded-full bg-[#CC0000]"></span>
            Practice quiz
        </p>
        <div class="quiz-content mt-3 max-w-none leading-relaxed text-neutral-300">
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
                html_lines.append(f"</{in_list}>")
                in_list = False
            html_lines.append(f"<h4 class='mt-5 mb-2 text-sm font-semibold tracking-tight text-white first:mt-0'>{_inline_html(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            if in_list:
                html_lines.append(f"</{in_list}>")
                in_list = False
            html_lines.append(f"<h3 class='mt-5 mb-2 text-base font-semibold tracking-tight text-white first:mt-0'>{_inline_html(stripped[3:])}</h3>")
        elif stripped.startswith("# "):
            if in_list:
                html_lines.append(f"</{in_list}>")
                in_list = False
            html_lines.append(f"<h2 class='mt-5 mb-2 text-lg font-semibold tracking-tight text-white first:mt-0'>{_inline_html(stripped[2:])}</h2>")

        # Bullet list
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if in_list != "ul":
                if in_list:
                    html_lines.append(f"</{in_list}>")
                html_lines.append("<ul class='my-3 list-disc space-y-1.5 pl-5 text-neutral-300 marker:text-neutral-600'>")
                in_list = "ul"
            html_lines.append(f"<li class='pl-1'>{_inline_html(stripped[2:])}</li>")

        # Numbered list
        elif stripped and stripped[0].isdigit() and ". " in stripped[:4]:
            if in_list != "ol":
                if in_list:
                    html_lines.append(f"</{in_list}>")
                html_lines.append("<ol class='my-3 list-decimal space-y-1.5 pl-5 text-neutral-300 marker:text-neutral-500'>")
                in_list = "ol"
            text_part = stripped.split(". ", 1)[1] if ". " in stripped else stripped
            html_lines.append(f"<li class='pl-1'>{_inline_html(text_part)}</li>")

        # Empty line = paragraph break
        elif not stripped:
            if in_list:
                html_lines.append(f"</{in_list}>")
                in_list = False
            html_lines.append("")

        # Regular paragraph
        else:
            if in_list:
                html_lines.append(f"</{in_list}>")
                in_list = False
            html_lines.append(f"<p class='my-2 leading-relaxed text-neutral-300'>{_inline_html(stripped)}</p>")

    if in_list:
        html_lines.append(f"</{in_list}>")

    return "\n".join(html_lines)


def _inline_html(text: str) -> str:
    """Convert inline markdown (**bold**, `code`) to HTML."""
    import html as html_mod

    escaped = html_mod.escape(text)

    # **bold**
    import re
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong class='font-semibold text-white'>\1</strong>", escaped)
    # `code`
    escaped = re.sub(r"`(.+?)`", r"<code class='dash-mono rounded-md bg-neutral-900 px-1.5 py-0.5 text-[12px] text-neutral-200'>\1</code>", escaped)

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
