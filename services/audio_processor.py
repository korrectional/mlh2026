"""Google Web Speech transcription and MP3 encoding for browser PCM audio."""

import lameenc

SAMPLE_RATE = 16000
SEGMENT_SECONDS = 15
SEGMENT_BYTES = SAMPLE_RATE * 2 * SEGMENT_SECONDS


class SpeechServiceError(Exception):
    """The Google Web Speech service could not transcribe a segment."""


def transcribe_audio(pcm: bytes) -> str:
    """Recognize 16-bit mono PCM audio using SpeechRecognition."""
    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise SpeechServiceError("Install SpeechRecognition to enable transcription.") from exc

    if not pcm or len(pcm) < 2:
        return ""

    recognizer = sr.Recognizer()
    recognizer.operation_timeout = 20

    if len(pcm) <= SEGMENT_BYTES:
        audio = sr.AudioData(pcm, SAMPLE_RATE, 2)
        try:
            return recognizer.recognize_google(audio, language="en-US")
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as exc:
            raise SpeechServiceError("Google speech recognition is unavailable. Check your internet connection.") from exc

    # If the full recording is longer than 15 seconds, transcribe across segments
    results = []
    chunk_size = SEGMENT_BYTES
    for offset in range(0, len(pcm), chunk_size):
        chunk = pcm[offset:offset + chunk_size]
        if len(chunk) % 2 != 0:
            chunk = chunk[:-1]
        if len(chunk) < SAMPLE_RATE * 2:  # skip sub-second trailing noise
            continue
        audio = sr.AudioData(chunk, SAMPLE_RATE, 2)
        try:
            text = recognizer.recognize_google(audio, language="en-US")
            if text:
                results.append(text)
        except sr.UnknownValueError:
            continue
        except sr.RequestError:
            continue

    return " ".join(results)


def encode_mp3(pcm: bytes) -> bytes:
    """Encode 16-bit mono PCM to a compact, playable MP3."""
    encoder = lameenc.Encoder()
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(1)
    encoder.set_bit_rate(48)
    encoder.set_quality(5)
    output = bytearray()
    for offset in range(0, len(pcm), 64 * 1024):
        output.extend(encoder.encode(pcm[offset:offset + 64 * 1024]))
    output.extend(encoder.flush())
    return bytes(output)
