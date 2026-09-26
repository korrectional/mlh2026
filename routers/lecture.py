"""Lecture Note-Taker page and audio WebSocket."""

from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

router = APIRouter(prefix="/lecture", tags=["lecture"])
_jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).resolve().parent.parent / "templates")),
    cache_size=0,
    auto_reload=True,
)


@router.get("/", response_class=HTMLResponse)
async def lecture_page(request: Request):
    return HTMLResponse(_jinja_env.get_template("lecture.html").render(request=request))


@router.websocket("/ws")
async def lecture_websocket(websocket: WebSocket):
    """Receive live MediaRecorder chunks and acknowledge their arrival."""
    await websocket.accept()
    # Keep the actual audio for this connection, in the order it arrives.
    audio_data = bytearray()
    chunks = 0
    try:
        while True:
            data = await websocket.receive_bytes()
            audio_data.extend(data)
            chunks += 1
            await websocket.send_json({
                "type": "audio_received",
                "bytes": len(data),
                "total_bytes": len(audio_data),
                "chunks": chunks,
            })

    except WebSocketDisconnect:
        pass
