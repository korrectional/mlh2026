"""Lecture Note-Taker router — stub for branch."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/lecture", tags=["lecture"])


@router.get("/")
async def lecture_page():
    """Placeholder — branch will return HTML template."""
    return {"message": "Lecture Note-Taker — under construction"}


@router.websocket("/ws")
async def lecture_websocket(websocket: WebSocket):
    """Placeholder — branch will stream audio → Gemini → notes."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            # TODO: forward to Gemini, send back structured notes
            await websocket.send_json({"type": "note", "text": f"Received {len(data)} bytes"})
    except WebSocketDisconnect:
        pass