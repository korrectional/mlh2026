"""Study Buddy router — stub for branch."""

from fastapi import APIRouter, UploadFile, File, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/study-buddy", tags=["study-buddy"])


@router.get("/", response_class=HTMLResponse)
async def study_buddy_page():
    """Placeholder — branch will render full template."""
    return "<h1>Study Buddy — under construction</h1>"


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Placeholder — branch will extract text, generate quiz, return HTML."""
    contents = await file.read()
    return HTMLResponse(f"""
        <div class="p-4 bg-yellow-50 rounded border">
            <p>Received <strong>{file.filename}</strong> ({len(contents)} bytes).</p>
            <p>Quiz generation not yet implemented.</p>
        </div>
    """)


@router.post("/answer")
async def check_answer():
    """Placeholder — branch will check answer and return explanation."""
    return HTMLResponse("<p>Answer checking not yet implemented.</p>")