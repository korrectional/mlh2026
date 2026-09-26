"""Lecture Note-Taker page and single-stream PCM WebSocket."""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from services.audio_processor import AudioProcessor, SAMPLE_RATE, encode_mp3

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
    """Transcribe and store the same PCM packets; return MP3 on request."""
    await websocket.accept()
    audio_data = bytearray()
    events = asyncio.Queue()
    loop = asyncio.get_running_loop()
    processor = None
    sender = None
    stopped = False
    active = True
    chunks = 0

    def emit(kind, text):
        # RealtimeSTT callbacks run on worker threads; serialize WebSocket sends.
        def enqueue():
            if active:
                key = "message" if kind == "transcription_error" else "text"
                events.put_nowait({"type": kind, key: text})

        loop.call_soon_threadsafe(enqueue)

    async def send_events():
        while True:
            event = await events.get()
            if isinstance(event, bytes):
                await websocket.send_bytes(event)
            else:
                await websocket.send_json(event)

    try:
        start = await websocket.receive()
        try:
            config = json.loads(start.get("text") or "")
        except ValueError:
            config = None
        if not isinstance(config, dict) or config.get("type") != "start" or config.get("sample_rate") != SAMPLE_RATE:
            await websocket.close(code=1003)
            return

        sender = asyncio.create_task(send_events())
        processor = AudioProcessor(emit)
        try:
            await asyncio.to_thread(processor.start)
        except Exception:
            await websocket.send_json({"type": "transcription_error", "message": "Could not load the local speech model."})
            await websocket.close(code=1011)
            return
        await events.put({"type": "ready"})

        while True:
            message = await websocket.receive()
            data = message.get("bytes")
            if data is not None:
                if stopped or not data or len(data) % 2 or len(data) > 65536:
                    await websocket.close(code=1003)
                    return
                audio_data.extend(data)
                await asyncio.to_thread(processor.process_audio_chunk, data)
                chunks += 1
                await events.put({
                    "type": "audio_received", "bytes": len(data),
                    "total_bytes": len(audio_data), "chunks": chunks,
                })
            elif message.get("text") is not None:
                try:
                    command = json.loads(message["text"])
                except ValueError:
                    command = None
                kind = command.get("type") if isinstance(command, dict) else None
                if kind == "stop" and not stopped:
                    await asyncio.to_thread(processor.close)
                    stopped = True
                    # Deliver the final utterance before enabling MP3 download.
                    await asyncio.sleep(0)
                    await events.put({"type": "recording_stopped"})
                elif kind == "download_audio" and stopped and audio_data:
                    try:
                        mp3 = await asyncio.to_thread(encode_mp3, bytes(audio_data))
                    except Exception:
                        await events.put({"type": "download_error", "message": "Could not encode the MP3."})
                        continue
                    await events.put({"type": "download_started", "total_bytes": len(mp3)})
                    for offset in range(0, len(mp3), 64 * 1024):
                        await events.put(mp3[offset:offset + 64 * 1024])
                    await events.put({"type": "download_complete"})
                else:
                    await events.put({"type": "download_error", "message": "Stop a recording before downloading its MP3."})
            else:
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            pass
    finally:
        if processor and not stopped:
            await asyncio.to_thread(processor.close)
        active = False
        if sender:
            if not sender.done():
                sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
