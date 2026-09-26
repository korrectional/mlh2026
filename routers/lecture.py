"""Lecture Note-Taker page and single-stream PCM WebSocket."""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from services.audio_processor import (
    SAMPLE_RATE, SpeechServiceError, encode_mp3,
)
from services.create_notes import create_notes, transcribe_lecture

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
    """Transcribe and store the full PCM stream; return notes, transcript, and MP3 on request."""
    await websocket.accept()
    audio_data = bytearray()
    events = asyncio.Queue()
    sender = None
    transcription_task = None
    notes_task = None
    stopped = False
    chunks = 0

    async def send_events():
        while True:
            event = await events.get()
            if isinstance(event, bytes):
                await websocket.send_bytes(event)
            else:
                await websocket.send_json(event)

    async def generate_transcript(final_audio: bytes):
        try:
            text = await transcribe_lecture(final_audio)
            if text.strip():
                await events.put({"type": "transcript", "text": text.strip()})
            else:
                await events.put({"type": "transcription_error", "message": "No speech recognized in the recording."})
        except SpeechServiceError as exc:
            await events.put({"type": "transcription_error", "message": str(exc)})
        except Exception as exc:
            await events.put({"type": "transcription_error", "message": f"Transcription failed: {exc}"})

    async def generate_notes(final_audio: bytes):
        try:
            notes = await create_notes(final_audio)
            if notes.strip():
                await events.put({"type": "notes", "text": notes.strip()})
            else:
                await events.put({"type": "notes_error", "message": "Gemini returned no notes for this recording."})
        except RuntimeError as exc:
            await events.put({"type": "notes_error", "message": str(exc)})
        except Exception as exc:
            await events.put({"type": "notes_error", "message": f"Could not generate notes with Gemini: {exc}"})

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

        while True:
            message = await websocket.receive()
            data = message.get("bytes")
            if data is not None:
                if stopped or not data or len(data) % 2 or len(data) > 65536:
                    await websocket.close(code=1003)
                    return
                audio_data.extend(data)
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
                    stopped = True
                    await events.put({"type": "recording_stopped"})
                    if audio_data:
                        final_bytes = bytes(audio_data)
                        transcription_task = asyncio.create_task(generate_transcript(final_bytes))
                        notes_task = asyncio.create_task(generate_notes(final_bytes))
                    else:
                        await events.put({"type": "transcription_error", "message": "No audio was captured for transcription."})
                        await events.put({"type": "notes_error", "message": "No audio was received for notes."})
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
        if notes_task:
            if not notes_task.done():
                notes_task.cancel()
            await asyncio.gather(notes_task, return_exceptions=True)
        if transcription_task:
            if not transcription_task.done():
                transcription_task.cancel()
            await asyncio.gather(transcription_task, return_exceptions=True)
        if sender:
            if not sender.done():
                sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
