"""Generate lecture notes from finalized PCM audio with Gemini."""

import asyncio
from io import BytesIO
import wave

from google.genai import types

from services.audio_processor import SAMPLE_RATE, transcribe_audio
from services.gemini import _get_client, DEFAULT_MODEL


async def transcribe_lecture(audio_data: bytes) -> str:
    """Transcribe finalized 16 kHz mono PCM lecture audio.

    Uses Gemini when configured, and falls back to local/SpeechRecognition
    transcription.
    """
    if not audio_data or len(audio_data) % 2:
        raise ValueError("Audio must be non-empty 16-bit PCM data.")

    client = _get_client()
    if client is not None:
        try:
            wav = BytesIO()
            with wave.open(wav, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(SAMPLE_RATE)
                output.writeframes(audio_data)

            prompt = (
                "Provide a complete, accurate, word-for-word transcript of the spoken words "
                "in this lecture audio. Break the transcript into readable paragraphs. "
                "Do not summarize or omit spoken content."
            )
            if wav.tell() <= 18 * 1024 * 1024:
                response = await client.aio.models.generate_content(
                    model=DEFAULT_MODEL,
                    contents=[types.Part.from_bytes(data=wav.getvalue(), mime_type="audio/wav"), prompt],
                )
            else:
                wav.seek(0)
                uploaded = await client.aio.files.upload(file=wav, config={"mime_type": "audio/wav"})
                try:
                    while uploaded.state and uploaded.state.name == "PROCESSING":
                        await asyncio.sleep(2)
                        uploaded = await client.aio.files.get(name=uploaded.name)
                    if uploaded.state and uploaded.state.name == "FAILED":
                        raise RuntimeError("Gemini could not process the lecture audio.")
                    response = await client.aio.models.generate_content(
                        model=DEFAULT_MODEL, contents=[uploaded, prompt],
                    )
                finally:
                    try:
                        await client.aio.files.delete(name=uploaded.name)
                    except Exception:
                        pass
            text = (response.text or "").strip()
            if text:
                return text
        except Exception:
            # Fall back to audio_processor transcribe_audio if Gemini encounters an issue
            pass

    # SpeechRecognition fallback
    return await asyncio.to_thread(transcribe_audio, audio_data)


async def create_notes(audio_data: bytes) -> str:
    """Send 16 kHz mono, 16-bit PCM lecture audio to Gemini and return notes.

    The shared Gemini client reads GEMINI_API_KEY from the local environment
    (including .env). This function expects the finalized audio buffer, not
    individual WebSocket packets.
    """
    if not audio_data or len(audio_data) % 2:
        raise ValueError("Audio must be non-empty 16-bit PCM data.")

    client = _get_client()
    if client is None:
        raise RuntimeError("Set GEMINI_API_KEY in your environment or .env file.")

    wav = BytesIO()
    with wave.open(wav, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(audio_data)

    prompt = (
        "Write clear, structured study notes from this lecture audio. "
        "Include key ideas and concise explanations. Do not invent details."
    )
    if wav.tell() <= 18 * 1024 * 1024:
        response = await client.aio.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[types.Part.from_bytes(data=wav.getvalue(), mime_type="audio/wav"), prompt],
        )
    else:
        wav.seek(0)
        uploaded = await client.aio.files.upload(file=wav, config={"mime_type": "audio/wav"})
        try:
            while uploaded.state and uploaded.state.name == "PROCESSING":
                await asyncio.sleep(2)
                uploaded = await client.aio.files.get(name=uploaded.name)
            if uploaded.state and uploaded.state.name == "FAILED":
                raise RuntimeError("Gemini could not process the lecture audio.")
            response = await client.aio.models.generate_content(
                model=DEFAULT_MODEL, contents=[uploaded, prompt],
            )
        finally:
            try:
                await client.aio.files.delete(name=uploaded.name)
            except Exception:
                pass
    return response.text or ""
