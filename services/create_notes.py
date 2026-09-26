"""Generate lecture notes from finalized PCM audio with Gemini."""

import asyncio
from io import BytesIO
import json
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


def _parse_notes_and_concepts(response_text: str) -> tuple[str, list[dict]]:
    """Parse Gemini response into markdown notes and a list of review concepts."""
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            notes = data.get("notes", "")
            raw_concepts = data.get("concepts", [])
            concepts = []
            if isinstance(raw_concepts, list):
                for item in raw_concepts:
                    if isinstance(item, dict) and item.get("concept"):
                        concepts.append({
                            "concept": str(item.get("concept", "")).strip(),
                            "reason": str(item.get("reason", "")).strip(),
                            "tip": str(item.get("tip", "")).strip(),
                        })
            return (notes if isinstance(notes, str) else str(notes), concepts)
    except Exception:
        pass

    return (response_text, [])


async def create_notes_and_concepts(audio_data: bytes) -> tuple[str, list[dict]]:
    """Send 16 kHz mono, 16-bit PCM lecture audio to Gemini.

    Returns a tuple of (notes_markdown, list_of_concepts_to_review).
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
        "Analyze this lecture audio and output a JSON object with two fields:\n"
        "1. 'notes': Comprehensive, clean, structured study notes formatted with Markdown headings, bullet points, and key takeaways.\n"
        "2. 'concepts': A list of difficult, crucial, or confusing concepts from the lecture that students should review. "
        "For each concept, provide 'concept' (short title), 'reason' (why it is tricky or important), and 'tip' (actionable study tip).\n\n"
        "Return valid JSON matching this schema:\n"
        "{\n"
        '  "notes": "string",\n'
        '  "concepts": [\n'
        '    {"concept": "string", "reason": "string", "tip": "string"}\n'
        '  ]\n'
        "}"
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

    return _parse_notes_and_concepts(response.text or "")


async def create_notes(audio_data: bytes) -> str:
    """Send 16 kHz mono, 16-bit PCM lecture audio to Gemini and return notes string."""
    notes, _ = await create_notes_and_concepts(audio_data)
    return notes
