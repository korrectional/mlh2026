"""Local transcription and MP3 encoding for browser PCM audio."""

from threading import Event, Thread

import lameenc

SAMPLE_RATE = 16000


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


class AudioProcessor:
    """Process one lecture stream with RealtimeSTT's external-audio API."""

    def __init__(self, emit):
        self.emit = emit
        self.recorder = None
        self.thread = None
        self.stopping = Event()
        self.last_partial = ""

    def start(self):
        # Delay loading models until a lecture actually starts.
        from RealtimeSTT import AudioToTextRecorder

        self.recorder = AudioToTextRecorder(
            use_microphone=False,
            model="tiny.en",
            language="en",
            device="cpu",
            compute_type="int8",
            silero_backend="raw_onnx",
            enable_realtime_transcription=True,
            use_main_model_for_realtime=True,
            realtime_processing_pause=0.5,
            on_realtime_transcription_update=self._on_partial,
            spinner=False,
            no_log_file=True,
        )
        self.thread = Thread(target=self._listen, daemon=True)
        self.thread.start()

    def process_audio_chunk(self, pcm: bytes):
        """Feed a 16 kHz mono PCM packet in arrival order."""
        self.recorder.feed_audio(pcm, original_sample_rate=SAMPLE_RATE)

    def _on_partial(self, text):
        if text and text != self.last_partial and not self.stopping.is_set():
            self.last_partial = text
            self.emit("partial", text)

    def _listen(self):
        try:
            while not self.stopping.is_set():
                text = self.recorder.text()
                if text:
                    self.last_partial = ""
                    self.emit("final", text)
        except Exception:
            if not self.stopping.is_set():
                self.emit("transcription_error", "Local transcription failed.")

    def close(self):
        """Finalize the current utterance and release model workers."""
        self.stopping.set()
        if self.recorder is None:
            return
        try:
            self.recorder.flush_audio_input()
            self.recorder.drain_audio_input(timeout=3)
            self.recorder.stop()
            if self.thread:
                self.thread.join(timeout=10)
        finally:
            self.recorder.shutdown()
