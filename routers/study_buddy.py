"""
Study Buddy — routes.

Flow:
  1. User uploads a PDF → /study-buddy/upload
  2. PyMuPDF extracts the text → Gemini writes a multiple-choice quiz
  3. Quiz comes back as an HTML snippet (HTMX swaps it into the page)
  4. Each answer → /study-buddy/answer → graded card, plus a Gemini
     explanation when the answer is wrong
"""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from services.gemini import ask_gemini, ask_gemini_json
from services.pdf_parser import extract_text_from_pdf

router = APIRouter(prefix="/study-buddy", tags=["study-buddy"])

_jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")),
    autoescape=True,
    cache_size=0,
    auto_reload=True,
)

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_CONTEXT_CHARS = 120_000
ALLOWED_QUESTION_COUNTS = (5, 10, 15)

# In-memory quiz sessions, keyed by quiz_id. Cleared when the server restarts.
_quizzes: dict[str, dict] = {}


def _render(name: str, **context) -> HTMLResponse:
    return HTMLResponse(_jinja_env.get_template(name).render(**context))


def _error(message: str) -> HTMLResponse:
    # 200 so HTMX swaps the message in (it ignores 4xx/5xx bodies by default).
    return _render("partials/study_buddy_error.html", message=message)


# ── Page ───────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def study_buddy_page(request: Request):
    return _render("study-buddy.html", request=request)


# ── Upload → quiz ─────────────────────────────────────────────────────

@router.post("/upload", response_class=HTMLResponse)
async def upload_pdf(file: UploadFile = File(...), num_questions: int = Form(5)):
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

    if num_questions not in ALLOWED_QUESTION_COUNTS:
        num_questions = 5

    try:
        raw = await ask_gemini_json(
            prompt=_quiz_prompt(num_questions),
            context=text[:MAX_CONTEXT_CHARS],
            system_prompt="You are a study buddy who writes practice quizzes from a student's course material.",
        )
        data = json.loads(raw)
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
        filename=file.filename,
        title=_quizzes[quiz_id]["title"],
        questions=questions,
    )


# ── Answer → graded card (+ explanation) ──────────────────────────────

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


def _clean_questions(raw_questions) -> list[dict]:
    """Keep only well-formed questions so a sloppy model reply can't break the page."""
    clean = []
    for q in raw_questions if isinstance(raw_questions, list) else []:
        if not isinstance(q, dict):
            continue
        options = q.get("options")
        idx = q.get("correct_index")
        if (
            isinstance(q.get("question"), str)
            and isinstance(options, list)
            and len(options) == 4
            and all(isinstance(o, str) for o in options)
            and isinstance(idx, int)
            and 0 <= idx < 4
        ):
            clean.append({
                "question": q["question"],
                "options": options,
                "correct_index": idx,
                "topic": str(q.get("topic") or "General"),
            })
    return clean
