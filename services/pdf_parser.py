"""PDF text extraction for Study Buddy (PyMuPDF)."""

import pymupdf


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract readable text from a PDF, page by page."""
    with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
        pages = [page.get_text().strip() for page in doc]
    return "\n\n".join(f"[Page {i}]\n{text}" for i, text in enumerate(pages, 1) if text)
