"""
TTS Service — Text-to-Speech cho tiếng Việt

Pipeline: Text → Normalize → TTS Engine → Audio bytes
Engine: Edge-TTS (default), VieNeu-TTS (local), VietTTS (API server)
Fallback: engine lỗi → tự động chuyển sang Edge-TTS

Hỗ trợ 2 mode:
  - synthesize(): Trả toàn bộ audio bytes (cho non-edge engines)
  - synthesize_stream(): Async generator yield chunks (giảm TTFB cho Edge-TTS)
"""
import asyncio
import os
import logging
import tempfile
from typing import Optional, AsyncIterator

logger = logging.getLogger(__name__)

EDGE_VOICES = {
    "female": "vi-VN-HoaiMyNeural",
    "male": "vi-VN-NamMinhNeural",
}


class TTSService:
    """Text-to-Speech: Vietnamese text → audio bytes (MP3/WAV)."""

    def __init__(self):
        self.engine = os.getenv("TTS_ENGINE", "edge")
        self.rate = os.getenv("TTS_RATE", "+0%")
        self.pitch = os.getenv("TTS_PITCH", "+0Hz")
        self._vieneu_model = None
        logger.info("TTS Service: %s", self.engine)

    async def synthesize(self, text: str, voice: str = "female") -> Optional[bytes]:
        """Synthesize toàn bộ audio cho 1 câu. Dùng cho non-streaming cases."""
        if not text or not text.strip():
            return None

        from chatbot_viva.voice.text_norm import normalize_vietnamese_text
        text = normalize_vietnamese_text(text)

        try:
            if self.engine == "vieneu":
                return await self._synthesize_vieneu(text, voice)
            elif self.engine == "viettts":
                return await self._synthesize_viettts(text, voice)
            else:
                return await self._synthesize_edge(text, voice)
        except Exception as e:
            logger.error("TTS error (%s): %s", self.engine, e)
            if self.engine != "edge":
                logger.info("Falling back to Edge-TTS...")
                return await self._synthesize_edge(text, voice)
            raise

    async def synthesize_stream(self, text: str, voice: str = "female") -> AsyncIterator[bytes]:
        """
        Async generator — yield audio chunks ngay khi có.
        Giảm Time-To-First-Byte đáng kể cho Edge-TTS.
        Non-edge engines fallback sang synthesize() rồi yield 1 lần.
        """
        if not text or not text.strip():
            return

        from chatbot_viva.voice.text_norm import normalize_vietnamese_text
        text = normalize_vietnamese_text(text)

        try:
            if self.engine == "edge":
                async for chunk in self._stream_edge(text, voice):
                    yield chunk
            else:
                # Non-edge: synthesize full rồi yield
                audio = await self.synthesize(text, voice)
                if audio:
                    yield audio
        except Exception as e:
            logger.error("TTS stream error (%s): %s", self.engine, e)
            if self.engine != "edge":
                async for chunk in self._stream_edge(text, voice):
                    yield chunk

    async def _stream_edge(self, text: str, voice: str) -> AsyncIterator[bytes]:
        """Stream audio chunks từ Edge-TTS ngay khi nhận được."""
        import edge_tts
        voice_name = EDGE_VOICES.get(voice, EDGE_VOICES["female"])
        communicate = edge_tts.Communicate(
            text=text, voice=voice_name, rate=self.rate, pitch=self.pitch,
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    async def _synthesize_edge(self, text: str, voice: str) -> bytes:
        """Full synthesis — dùng khi cần toàn bộ audio."""
        audio_data = bytearray()
        async for chunk in self._stream_edge(text, voice):
            audio_data.extend(chunk)
        return bytes(audio_data)

    async def _synthesize_vieneu(self, text: str, voice: str) -> bytes:
        def _generate():
            if self._vieneu_model is None:
                from vieneu import Vieneu
                self._vieneu_model = Vieneu()
            audio = self._vieneu_model.infer(text=text)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                self._vieneu_model.save(audio, f.name)
                f.flush()
                with open(f.name, "rb") as wav_file:
                    wav_data = wav_file.read()
                os.unlink(f.name)
                return wav_data

        return await asyncio.get_running_loop().run_in_executor(None, _generate)

    async def _synthesize_viettts(self, text: str, voice: str) -> bytes:
        import httpx
        viettts_url = os.getenv("VIETTTS_URL", "http://localhost:8298")
        voice_id = "1" if voice == "female" else "2"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{viettts_url}/v1/audio/speech",
                json={
                    "model": "tts-1",
                    "input": text,
                    "voice": voice_id,
                    "response_format": "mp3",
                },
            )
            response.raise_for_status()
            return response.content
