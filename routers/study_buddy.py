"""
Study Buddy — routes.

Study plan mode (default):
  1. Upload a PDF → /study-buddy/upload → Gemini breaks it into concepts
     (difficulty, key terms, prerequisites, a lesson, two questions each)
  2. services/study_plan scores complexity and estimates time to learn
  3. Student picks minutes/day (+ optional exam date) → /study-buddy/plan
  4. Each session: one review question on an earlier concept, then new
     concepts until the daily goal; overtime comes off the remaining total
  5. /plan/{id}/next-day simulates tomorrow for the demo

Quick quiz mode: upload → multiple-choice quiz → /study-buddy/answer grades
each question, with a Gemini explanation when the answer is wrong.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from services import study_plan
from services.gemini import ask_gemini, ask_gemini_json, ask_gemini_json_with_image, ask_gemini_with_image
from services.pdf_parser import extract_text_from_pdf

router = APIRouter(prefix="/study-buddy", tags=["study-buddy"])

_jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")),
    autoescape=True,
    cache_size=0,
    auto_reload=True,
)


def _fmt_minutes(m: int) -> str:
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m} min"


_jinja_env.filters["minutes"] = _fmt_minutes

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_CONTEXT_CHARS = 120_000
ALLOWED_QUESTION_COUNTS = (5, 10, 15)
DAILY_OPTIONS = (5, 10, 15, 20, 30)

# In-memory state, keyed by id. Cleared when the server restarts.
_quizzes: dict[str, dict] = {}
_plans: dict[str, dict] = {}


def _render(name: str, **context) -> HTMLResponse:
    return HTMLResponse(_jinja_env.get_template(name).render(**context))


def _error(message: str) -> HTMLResponse:
    # 200 so HTMX swaps the message in (it ignores 4xx/5xx bodies by default).
    return _render("partials/study_buddy_error.html", message=message)


# ── Page ───────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def study_buddy_page(request: Request):
    return _render("study-buddy.html", request=request, stage_html="")


# ── Upload → study plan analysis, or quick quiz ───────────────────────

@router.post("/upload", response_class=HTMLResponse)
async def upload_pdf(file: UploadFile = File(...), mode: str = Form("plan"), num_questions: int = Form(5)):
    if not (file.filename or "").lower().endswith(".pdf"):
        return _error("That isn't a PDF. Upload lecture slides or a chapter saved as .pdf.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_BYTES:
        return _error("That PDF is over 20 MB. Try a single chapter or lecture.")

    try:
        text = await extract_text_from_pdf(pdf_bytes)
    except Exception:
        return _error("Couldn't open that PDF. It may be corrupted or password-protected.")

    if len(text) < 200:
        return _error("No readable text found. Scanned or image-only PDFs aren't supported yet.")

    if mode == "quiz":
        return await _build_quiz(file.filename, text, num_questions)
    return await _build_analysis(file.filename, text)


# ── Image upload (photo of a page) ────────────────────────────────────

MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/upload-image", response_class=HTMLResponse)
async def upload_image(
    file: UploadFile = File(...),
    mode: str = Form("plan"),
    num_questions: int = Form(5),
):
    """Accept a photo of a textbook/notes page, send to Gemini as an image."""
    if not (file.content_type or "").startswith("image/"):
        return _error("That isn't an image. Take a photo of your textbook or notes page.")

    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return _error("That image is over 10 MB. Try a smaller photo.")

    mime_type = file.content_type or "image/jpeg"
    filename = file.filename or "photo.jpg"

    if mode == "quiz":
        return await _build_quiz_from_image(filename, image_bytes, mime_type, num_questions)
    return await _build_analysis_from_image(filename, image_bytes, mime_type)


async def _build_analysis_from_image(
    filename: str, image_bytes: bytes, mime_type: str
) -> HTMLResponse:
    try:
        raw = await ask_gemini_json_with_image(
            prompt=_concepts_prompt(),
            image_bytes=image_bytes,
            mime_type=mime_type,
            system_prompt=(
                "You are an expert tutor. The user took a photo of their course material. "
                "Read any text, diagrams, and formulas in the image."
            ),
        )
        data = _as_object(json.loads(raw), "concepts")
    except Exception as exc:
        return _error(f"Analysis failed: {exc}")

    concepts = _clean_concepts(data.get("concepts", []))
    if len(concepts) < 3:
        return _error(
            "Couldn't find enough distinct concepts in that photo. "
            "Try a clearer photo with the page flat and well-lit."
        )

    concepts = study_plan.prerequisite_order(concepts)
    for c in concepts:
        c["minutes"] = study_plan.concept_minutes(c)

    plan_id = uuid.uuid4().hex
    _plans[plan_id] = {
        "id": plan_id,
        "filename": filename,
        "title": str(data.get("title") or "Your material"),
        "concepts": concepts,
        "analysis": study_plan.analyze(concepts),
        "per_day": None,
        "exam": None,
        "start": date.today(),
        "day": 1,
        "completed": {},
        "credited": 0,
        "today": 0,
        "reviewed_today": False,
        "goal_days": set(),
    }
    return _render(
        "partials/study_buddy_analysis.html",
        plan=_plans[plan_id],
        daily_options=DAILY_OPTIONS,
    )


async def _build_quiz_from_image(
    filename: str, image_bytes: bytes, mime_type: str, num_questions: int
) -> HTMLResponse:
    if num_questions not in ALLOWED_QUESTION_COUNTS:
        num_questions = 5

    try:
        raw = await ask_gemini_json_with_image(
            prompt=_quiz_prompt(num_questions),
            image_bytes=image_bytes,
            mime_type=mime_type,
            system_prompt=(
                "You are a study buddy. The user took a photo of their course material. "
                "Read any text, diagrams, and formulas in the image."
            ),
        )
        data = _as_object(json.loads(raw), "questions")
    except Exception as exc:
        return _error(f"Quiz generation failed: {exc}")

    questions = _clean_questions(data.get("questions", []))
    if not questions:
        return _error(
            "Gemini didn't return usable questions from that photo. "
            "Try a clearer photo with the page flat and well-lit."
        )

    quiz_id = uuid.uuid4().hex
    _quizzes[quiz_id] = {
        "title": str(data.get("title") or "Practice Quiz"),
        "questions": questions,
        "answers": {},
        "source": "",  # no text context for image-based quizzes
    }
    return _render(
        "partials/study_buddy_quiz.html",
        quiz_id=quiz_id,
        filename=filename,
        title=_quizzes[quiz_id]["title"],
        questions=questions,
    )


async def _build_analysis(filename: str, text: str) -> HTMLResponse:
    try:
        raw = await ask_gemini_json(
            prompt=_concepts_prompt(),
            context=text[:MAX_CONTEXT_CHARS],
            system_prompt="You are an expert tutor who turns course material into short daily lessons.",
        )
        data = _as_object(json.loads(raw), "concepts")
    except Exception as exc:
        return _error(f"Analysis failed: {exc}")

    concepts = _clean_concepts(data.get("concepts", []))
    if len(concepts) < 3:
        return _error("Gemini couldn't find enough distinct concepts in that PDF. Try a fuller chapter.")

    concepts = study_plan.prerequisite_order(concepts)
    for c in concepts:
        c["minutes"] = study_plan.concept_minutes(c)

    plan_id = uuid.uuid4().hex
    _plans[plan_id] = {
        "id": plan_id,
        "filename": filename,
        "title": str(data.get("title") or "Your material"),
        "concepts": concepts,
        "analysis": study_plan.analyze(concepts),
        "per_day": None,
        "exam": None,
        "start": date.today(),
        "day": 1,
        "completed": {},
        "credited": 0,
        "today": 0,
        "reviewed_today": False,
        "goal_days": set(),
    }
    return _render("partials/study_buddy_analysis.html", plan=_plans[plan_id], daily_options=DAILY_OPTIONS)


async def _build_quiz(filename: str, text: str, num_questions: int) -> HTMLResponse:
    if num_questions not in ALLOWED_QUESTION_COUNTS:
        num_questions = 5

    try:
        raw = await ask_gemini_json(
            prompt=_quiz_prompt(num_questions),
            context=text[:MAX_CONTEXT_CHARS],
            system_prompt="You are a study buddy who writes practice quizzes from a student's course material.",
        )
        data = _as_object(json.loads(raw), "questions")
    except Exception as exc:
        return _error(f"Quiz generation failed: {exc}")

    questions = _clean_questions(data.get("questions", []))
    if not questions:
        return _error("Gemini didn't return usable questions. Try uploading again.")

    quiz_id = uuid.uuid4().hex
    _quizzes[quiz_id] = {
        "title": str(data.get("title") or "Practice Quiz"),
        "questions": questions,
        "answers": {},
        "source": text[:MAX_CONTEXT_CHARS],
    }
    return _render(
        "partials/study_buddy_quiz.html",
        quiz_id=quiz_id,
        filename=filename,
        title=_quizzes[quiz_id]["title"],
        questions=questions,
    )


# ── Study plan ────────────────────────────────────────────────────────

@router.post("/plan", response_class=HTMLResponse)
async def build_plan(plan_id: str = Form(...), per_day: int = Form(...), exam_date: str = Form("")):
    plan = _plans.get(plan_id)
    if not plan:
        return _expired()
    plan["per_day"] = max(1, min(per_day, 240))
    if plan["today"] >= plan["per_day"]:
        plan["goal_days"].add(plan["day"])
    else:
        plan["goal_days"].discard(plan["day"])
    try:
        plan["exam"] = date.fromisoformat(exam_date) if exam_date else None
    except ValueError:
        plan["exam"] = None
    response = _plan_view(plan)
    response.headers["HX-Push-Url"] = f"/study-buddy/plan/{plan_id}"
    return response


@router.get("/plan/{plan_id}", response_class=HTMLResponse)
async def show_plan(request: Request, plan_id: str):
    plan = _plans.get(plan_id)
    if request.headers.get("HX-Request"):
        return _plan_view(plan) if plan and plan["per_day"] else _expired()
    stage = _plan_view(plan).body.decode() if plan and plan["per_day"] else ""
    return _render("study-buddy.html", request=request, stage_html=stage)


@router.post("/plan/{plan_id}/session", response_class=HTMLResponse)
async def next_step(plan_id: str):
    plan = _plans.get(plan_id)
    if not plan or not plan["per_day"]:
        return _expired()

    review_idx = _review_candidate(plan)
    if review_idx is not None:
        return _render("partials/study_buddy_session.html", kind="review", idx=review_idx, **_session_context(plan))

    next_idx = _next_concept(plan)
    if next_idx is None:
        return _plan_view(plan)
    return _render("partials/study_buddy_session.html", kind="check", idx=next_idx, **_session_context(plan))


@router.post("/plan/{plan_id}/answer", response_class=HTMLResponse)
async def answer_step(plan_id: str, kind: str = Form(...), idx: int = Form(...), choice: int = Form(...)):
    plan = _plans.get(plan_id)
    if not plan or not plan["per_day"] or not 0 <= idx < len(plan["concepts"]):
        return _expired()

    concept = plan["concepts"][idx]
    q = concept["review"] if kind == "review" else concept["check"]
    if not 0 <= choice < 4:
        return _error("Pick one of the options.")
    correct = choice == q["correct_index"]
    day = plan["day"]

    if kind == "review":
        plan["reviewed_today"] = True
        if idx in plan["completed"]:
            plan["completed"][idx].update(last_review=day, correct=correct)
    elif idx not in plan["completed"]:
        plan["completed"][idx] = {"day": day, "correct": correct, "last_review": day}
        plan["credited"] += concept["minutes"]
        plan["today"] += concept["minutes"]

    finished = kind != "review" and _next_concept(plan) is None
    just_hit_goal = (plan["today"] >= plan["per_day"] or finished) and day not in plan["goal_days"]
    if just_hit_goal:
        plan["goal_days"].add(day)

    return _render(
        "partials/study_buddy_step_result.html",
        kind=kind,
        idx=idx,
        concept=concept,
        q=q,
        choice=choice,
        correct=correct,
        just_hit_goal=just_hit_goal,
        all_done=_next_concept(plan) is None,
        **_session_context(plan),
    )


@router.post("/plan/{plan_id}/next-day", response_class=HTMLResponse)
async def next_day(plan_id: str):
    plan = _plans.get(plan_id)
    if not plan or not plan["per_day"]:
        return _expired()
    plan["day"] += 1
    plan["today"] = 0
    plan["reviewed_today"] = False
    return _plan_view(plan)


def _expired() -> HTMLResponse:
    return _error("This plan expired (the server restarted). Upload the PDF again.")


def _next_concept(plan: dict) -> int | None:
    return next((i for i in range(len(plan["concepts"])) if i not in plan["completed"]), None)


def _review_candidate(plan: dict) -> int | None:
    """One review per day: missed concepts first, then the one reviewed longest ago. Skip today's new ones."""
    if plan["reviewed_today"]:
        return None
    pool = [(i, s) for i, s in plan["completed"].items() if s["day"] < plan["day"]]
    if not pool:
        return None
    return min(pool, key=lambda item: (item[1]["correct"], item[1]["last_review"], item[0]))[0]


def _streak(plan: dict) -> int:
    days = plan["goal_days"]
    d = plan["day"] if plan["day"] in days else plan["day"] - 1
    n = 0
    while d in days:
        n += 1
        d -= 1
    return n


def _session_context(plan: dict) -> dict:
    total = plan["analysis"]["total_minutes"]
    remaining = max(total - plan["credited"], 0)
    today_date = plan["start"] + timedelta(days=plan["day"] - 1)
    days_left = study_plan.days_until(plan["exam"], today_date)
    return {
        "plan": plan,
        "total": total,
        "remaining": remaining,
        "sessions_left": study_plan.sessions_left(remaining, plan["per_day"], plan["today"]),
        "goal_met": plan["today"] >= plan["per_day"],
        "overtime": max(plan["today"] - plan["per_day"], 0),
        "streak": _streak(plan),
        "exam": study_plan.exam_check(remaining, plan["per_day"], days_left, plan["today"]),
        "done_count": len(plan["completed"]),
    }


def _plan_view(plan: dict) -> HTMLResponse:
    ctx = _session_context(plan)
    remaining_idx = [i for i in range(len(plan["concepts"])) if i not in plan["completed"]]
    spans = study_plan.day_spans([plan["concepts"][i]["minutes"] for i in remaining_idx], plan["per_day"], plan["today"])
    upcoming = []
    for i, (start, end) in zip(remaining_idx, spans):
        if not upcoming or upcoming[-1]["start"] != start:
            upcoming.append({"start": start, "day": plan["day"] + start, "entries": []})
        upcoming[-1]["entries"].append({"idx": i, "last_day": plan["day"] + end})
    return _render("partials/study_buddy_plan.html", upcoming=upcoming, **ctx)


# ── Quick quiz: answer → graded card (+ explanation) ──────────────────

@router.post("/answer", response_class=HTMLResponse)
async def check_answer(quiz_id: str = Form(...), q_index: int = Form(...), choice: int = Form(...)):
    quiz = _quizzes.get(quiz_id)
    if not quiz or not 0 <= q_index < len(quiz["questions"]):
        return _error("This quiz expired (the server restarted). Upload the PDF again.")

    q = quiz["questions"][q_index]
    if not 0 <= choice < len(q["options"]):
        return _error("Pick one of the options.")

    quiz["answers"][q_index] = choice
    correct = choice == q["correct_index"]

    explanation = None
    if not correct:
        explanation = await ask_gemini(
            prompt=_explain_prompt(q, choice),
            context=quiz["source"],
            system_prompt="You are a patient, encouraging tutor. Reply in plain text, no markdown.",
        )

    answers = quiz["answers"]
    total = len(quiz["questions"])
    num_correct = sum(1 for i, c in answers.items() if c == quiz["questions"][i]["correct_index"])
    missed_topics = sorted({
        quiz["questions"][i]["topic"]
        for i, c in answers.items()
        if c != quiz["questions"][i]["correct_index"]
    })

    return _render(
        "partials/study_buddy_answer.html",
        i=q_index,
        q=q,
        choice=choice,
        correct=correct,
        explanation=explanation,
        answered=len(answers),
        total=total,
        num_correct=num_correct,
        finished=len(answers) == total,
        missed_topics=missed_topics,
    )


# ── Prompts & validation ──────────────────────────────────────────────

def _concepts_prompt() -> str:
    return """Break the course material in the context into its core concepts so a student can learn it in short daily sessions.

Return between 5 and 10 concepts. For each concept:
- "id": "c1", "c2", ...
- "name": 2-5 words
- "summary": one sentence
- "difficulty": 1, 2, or 3, using this rubric:
    1 = a definition or fact to remember
    2 = a process, mechanism, or relationship to understand
    3 = abstract reasoning, multi-step application, or math
- "key_terms": the technical terms a student must know for this concept (0-8 terms)
- "prerequisites": ids of other concepts in this list that must be understood first (may be empty)
- "lesson": a 60-100 word plain-text explanation for a student meeting this concept for the first time, ending with a concrete example
- "check": a multiple-choice question testing understanding of the lesson
- "review": a different multiple-choice question on the same concept, for a later review session

Each question is {"question": "...", "options": ["...", "...", "...", "..."], "correct_index": 0, "explanation": "1-2 sentences on why the right answer is right"}.
Exactly 4 options, exactly one correct, no letter prefixes, and vary which position is correct.

Return JSON: {"title": "short title for the material", "concepts": [...]}"""


def _quiz_prompt(n: int) -> str:
    return f"""Write exactly {n} multiple-choice questions that test real understanding of the key concepts in the context.
Mix conceptual, application, and analysis questions. Avoid trivia and questions answerable by pattern-matching.
Each question has exactly 4 options and exactly one correct answer. Do not prefix options with letters.

Return JSON in exactly this shape:
{{
  "title": "Short quiz title based on the material",
  "questions": [
    {{"question": "...", "options": ["...", "...", "...", "..."], "correct_index": 0, "topic": "2-4 word topic label"}}
  ]
}}"""


def _explain_prompt(q: dict, choice: int) -> str:
    return f"""A student answered this practice question incorrectly. Using the course material in the context,
explain in 3-5 sentences why their answer is wrong and why the correct answer is right.
Start by acknowledging what they were probably thinking, then teach the concept.

Question: {q['question']}
Student's answer: {q['options'][choice]}
Correct answer: {q['options'][q['correct_index']]}"""


def _as_object(data, key: str) -> dict:
    """Accept {key: [...]}, a list wrapping that object, or a bare list of items; anything else becomes {}."""
    if isinstance(data, list):
        wrapped = [d for d in data if isinstance(d, dict) and key in d]
        data = wrapped[0] if wrapped else {key: data}
    return data if isinstance(data, dict) else {}


def _clean_question(q) -> dict | None:
    if not isinstance(q, dict):
        return None
    options = q.get("options")
    idx = q.get("correct_index")
    if isinstance(options, list) and all(isinstance(o, (str, int, float)) and not isinstance(o, bool) for o in options):
        options = [str(o) for o in options]
    if isinstance(idx, float) and idx.is_integer():
        idx = int(idx)
    elif isinstance(idx, str) and idx.strip().isdigit():
        idx = int(idx.strip())
    if not (
        isinstance(q.get("question"), str)
        and isinstance(options, list)
        and len(options) == 4
        and all(isinstance(o, str) for o in options)
        and isinstance(idx, int)
        and not isinstance(idx, bool)
        and 0 <= idx < 4
    ):
        return None
    return {
        "question": q["question"],
        "options": options,
        "correct_index": idx,
        "explanation": str(q.get("explanation") or ""),
        "topic": str(q.get("topic") or "General"),
    }


def _clean_questions(raw_questions) -> list[dict]:
    """Keep only well-formed questions so a sloppy model reply can't break the page."""
    items = raw_questions if isinstance(raw_questions, list) else []
    return [q for q in (_clean_question(item) for item in items) if q]


def _clean_concepts(raw_concepts) -> list[dict]:
    clean = []
    seen_ids = set()
    for c in raw_concepts if isinstance(raw_concepts, list) else []:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not isinstance(c.get("lesson"), str):
            continue
        check = _clean_question(c.get("check"))
        if not check:
            continue
        cid = str(c.get("id") or f"c{len(clean) + 1}")
        if cid in seen_ids:
            cid = f"{cid}-{len(clean) + 1}"
        seen_ids.add(cid)
        try:
            difficulty = int(float(c.get("difficulty")))
        except (TypeError, ValueError):
            difficulty = 2
        terms = c.get("key_terms") if isinstance(c.get("key_terms"), list) else []
        prereqs = c.get("prerequisites") if isinstance(c.get("prerequisites"), list) else []
        clean.append({
            "id": cid,
            "name": c["name"],
            "summary": str(c.get("summary") or ""),
            "difficulty": difficulty if difficulty in (1, 2, 3) else 2,
            "key_terms": [str(t) for t in terms][:8],
            "prerequisites": [str(p) for p in prereqs],
            "lesson": c["lesson"],
            "check": check,
            "review": _clean_question(c.get("review")) or check,
        })
    ids = {c["id"] for c in clean}
    for c in clean:
        c["prerequisites"] = [p for p in c["prerequisites"] if p in ids and p != c["id"]]
    return clean
