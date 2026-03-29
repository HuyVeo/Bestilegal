"""
Speech-to-Text Service — Nhận dạng giọng nói tiếng Việt

Pipeline: Validate audio → Noise gate → PCM→WAV → Gọi API Whisper → Trả text
Backend: OpenAI Whisper (whisper-1) hoặc Groq Whisper (whisper-large-v3)
Fallback: Groq lỗi → tự động chuyển sang OpenAI
"""
import io
import os
import logging
import struct
import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MIN_AUDIO_DURATION_S = 0.3
MAX_AUDIO_DURATION_S = 30.0
SILENCE_RMS_THRESHOLD = 0.005
MIN_SPEECH_RATIO = 0.05

VIETNAMESE_PROMPT = (
    "Xin chào, đây là đoạn hội thoại tiếng Việt. "
    "Hà Nội, Hồ Chí Minh, Đà Nẵng, Hội An, Huế, Sapa, Phú Quốc, Nha Trang, "
    "Ninh Bình, Quảng Ninh, Hạ Long, Đà Lạt, Cần Thơ, Vũng Tàu."
)


class STTService:
    """Speech-to-Text: PCM audio → Vietnamese text via Whisper API."""

    def __init__(self):
        self.provider = os.getenv("STT_PROVIDER", "openai").lower()
        self.model = os.getenv("STT_MODEL", "whisper-1")
        self._openai_client = None
        self._groq_client = None
        logger.info("STT Service: provider=%s model=%s", self.provider, self.model)

    async def _get_openai_client(self):
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._openai_client

    async def _get_groq_client(self):
        if self._groq_client is None:
            from groq import AsyncGroq
            self._groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        return self._groq_client

    async def transcribe(self, audio_bytes: bytes, language: str = "vi") -> str:
        if not audio_bytes or len(audio_bytes) < 100:
            logger.warning("STT: audio rỗng hoặc quá ngắn, bỏ qua")
            return ""

        pcm_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float = pcm_int16.astype(np.float32) / 32768.0

        duration_s = len(audio_float) / SAMPLE_RATE
        if duration_s < MIN_AUDIO_DURATION_S:
            logger.warning("STT: audio quá ngắn (%.2fs), bỏ qua", duration_s)
            return ""

        if duration_s > MAX_AUDIO_DURATION_S:
            logger.info("STT: cắt audio từ %.1fs xuống %.1fs", duration_s, MAX_AUDIO_DURATION_S)
            max_samples = int(MAX_AUDIO_DURATION_S * SAMPLE_RATE)
            pcm_int16 = pcm_int16[:max_samples]
            audio_float = audio_float[:max_samples]
            audio_bytes = pcm_int16.tobytes()

        rms = float(np.sqrt(np.mean(audio_float ** 2)))
        if rms < SILENCE_RMS_THRESHOLD:
            logger.debug("STT: audio toàn silence (RMS=%.5f), bỏ qua", rms)
            return ""

        speech_frames = np.sum(np.abs(audio_float) > 0.01)
        speech_ratio = speech_frames / len(audio_float)
        if speech_ratio < MIN_SPEECH_RATIO:
            logger.debug("STT: speech ratio quá thấp (%.3f), bỏ qua", speech_ratio)
            return ""

        logger.info("STT: processing %.2fs audio (RMS=%.4f, speech=%.2f%%)", duration_s, rms, speech_ratio * 100)

        wav_bytes = self._pcm_to_wav(audio_bytes)

        if self.provider == "groq":
            return await self._transcribe_groq(wav_bytes, language)
        return await self._transcribe_openai(wav_bytes, language)

    async def _transcribe_openai(self, wav_bytes: bytes, language: str) -> str:
        try:
            client = await self._get_openai_client()
            wav_file = io.BytesIO(wav_bytes)
            wav_file.name = "audio.wav"
            response = await client.audio.transcriptions.create(
                model=self.model,
                file=wav_file,
                language=language,
                response_format="text",
                prompt=VIETNAMESE_PROMPT,
            )
            text = response.strip() if isinstance(response, str) else str(response).strip()
            logger.info("STT OpenAI result: '%s'", text[:80])
            return text
        except Exception as e:
            logger.error("OpenAI STT error: %s", e)
            raise

    async def _transcribe_groq(self, wav_bytes: bytes, language: str) -> str:
        try:
            client = await self._get_groq_client()
            wav_file = io.BytesIO(wav_bytes)
            wav_file.name = "audio.wav"
            response = await client.audio.transcriptions.create(
                model=self.model if "whisper" in self.model else "whisper-large-v3",
                file=wav_file,
                language=language,
                response_format="text",
                prompt=VIETNAMESE_PROMPT,
            )
            text = response.strip() if isinstance(response, str) else str(response).strip()
            logger.info("STT Groq result: '%s'", text[:80])
            return text
        except Exception as e:
            logger.error("Groq STT error: %s → fallback OpenAI", e)
            return await self._transcribe_openai(wav_bytes, language)

    @staticmethod
    def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = SAMPLE_RATE,
                     channels: int = 1, sample_width: int = 2) -> bytes:
        data_size = len(pcm_bytes)
        byte_rate = sample_rate * channels * sample_width
        block_align = channels * sample_width
        bits_per_sample = sample_width * 8
        header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF', 36 + data_size, b'WAVE',
            b'fmt ', 16, 1, channels,
            sample_rate, byte_rate, block_align, bits_per_sample,
            b'data', data_size,
        )
        return header + pcm_bytes
