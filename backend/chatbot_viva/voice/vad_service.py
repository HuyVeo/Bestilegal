"""
Voice Activity Detection (VAD) — Full-Duplex Turn Detection

Phát hiện khi nào user bắt đầu/kết thúc nói trong luồng audio liên tục.
Dùng Silero VAD (nếu có torch) hoặc Energy+ZCR fallback.

Gồm 3 class chính:
  - VADService: Load và quản lý Silero model (singleton)
  - VADSession: Per-session state (sample buffer) — tránh audio bị trộn giữa các session
  - TurnDetector: State machine quản lý lượt nói (LISTENING → SPEECH → speech_end)
"""
import numpy as np
import logging
import os
import time
import collections
import threading
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512


class TurnState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    SPEECH = "speech"
    SPEECH_ENDED = "speech_ended"


class VADService:
    """
    Voice Activity Detection service — model holder (singleton).
    Model được load 1 lần, dùng chung qua VADSession cho từng session.
    """

    def __init__(self):
        self.threshold = float(os.getenv("VAD_THRESHOLD", "0.45"))
        self.silence_ms = int(os.getenv("VAD_SILENCE_DURATION", "1200"))
        self.min_speech_ms = int(os.getenv("VAD_MIN_SPEECH", "400"))
        self.speech_pad_ms = int(os.getenv("VAD_SPEECH_PAD_MS", "300"))
        self.speech_start_frames = int(os.getenv("VAD_SPEECH_START_FRAMES", "2"))
        self.silence_end_frames = int(os.getenv("VAD_SILENCE_END_FRAMES", "8"))
        self.model = None
        self._model_lock = threading.Lock()
        self._load_model()

    def _load_model(self):
        try:
            import torch
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
                verbose=False,
            )
            self.model = model
            logger.info("Silero VAD loaded")
        except Exception as e:
            logger.warning("Silero VAD không load được: %s → dùng Energy+ZCR fallback", e)
            self.model = None

    def create_session(self) -> "VADSession":
        """Tạo VAD session mới với state riêng biệt."""
        return VADSession(self)


class VADSession:
    """
    Per-session VAD state — mỗi client có buffer riêng, tránh audio bị trộn.
    Silero model được share qua lock để đảm bảo thread-safe.
    """

    def __init__(self, service: VADService):
        self._service = service
        self._sample_buf = np.array([], dtype=np.float32)

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        if self._service.model is not None:
            return self._silero_detect(audio_chunk)
        return self._energy_zcr_detect(audio_chunk)

    def _silero_detect(self, audio_chunk: np.ndarray) -> bool:
        try:
            import torch
            self._sample_buf = np.concatenate([self._sample_buf, audio_chunk])
            result = False
            while len(self._sample_buf) >= CHUNK_SAMPLES:
                window = self._sample_buf[:CHUNK_SAMPLES]
                self._sample_buf = self._sample_buf[CHUNK_SAMPLES:]
                tensor = torch.from_numpy(window).float()
                with self._service._model_lock:
                    conf = self._service.model(tensor, SAMPLE_RATE).item()
                if conf > self._service.threshold:
                    result = True
            return result
        except Exception as e:
            logger.debug("Silero error: %s", e)
            return self._energy_zcr_detect(audio_chunk)

    @staticmethod
    def _energy_zcr_detect(audio_chunk: np.ndarray) -> bool:
        if len(audio_chunk) < 160:
            return False
        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
        signs = np.sign(audio_chunk)
        signs[signs == 0] = 1
        zcr = float(np.mean(np.abs(np.diff(signs))) / 2)
        return (rms > 0.015) and (0.04 < zcr < 0.5)

    def reset(self):
        self._sample_buf = np.array([], dtype=np.float32)
        if self._service.model is not None:
            try:
                with self._service._model_lock:
                    self._service.model.reset_states()
            except Exception:
                pass


class TurnDetector:
    """
    State machine phát hiện lượt nói cho full-duplex.
    LISTENING → (2 frame speech) → SPEECH → (8 frame silence / 1.2s) → speech_end

    Mỗi TurnDetector có VADSession riêng — không dùng chung buffer.
    """

    def __init__(self, vad_service: VADService):
        self.vad_service = vad_service
        self.vad = vad_service.create_session()
        self.state = TurnState.IDLE
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._speech_start_time: Optional[float] = None
        self._last_speech_time: Optional[float] = None
        pre_roll_bytes = int(vad_service.speech_pad_ms / 1000 * SAMPLE_RATE * 2)
        self._pre_roll = bytearray()
        self._pre_roll_max = pre_roll_bytes
        self._audio_buffer = bytearray()
        self._speech_start_thr = vad_service.speech_start_frames
        self._silence_end_thr = vad_service.silence_end_frames
        self._min_speech_s = vad_service.min_speech_ms / 1000.0
        self._silence_s = vad_service.silence_ms / 1000.0

    def _append_pre_roll(self, pcm_bytes: bytes):
        """Append to pre-roll buffer, giữ maxlen bằng cách cắt đầu — O(1) amortized."""
        self._pre_roll.extend(pcm_bytes)
        overflow = len(self._pre_roll) - self._pre_roll_max
        if overflow > 0:
            del self._pre_roll[:overflow]

    def reset(self):
        self.state = TurnState.IDLE
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._speech_start_time = None
        self._last_speech_time = None
        self._audio_buffer = bytearray()
        self._pre_roll.clear()
        self.vad.reset()

    def start_listening(self):
        self.state = TurnState.LISTENING
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._speech_start_time = None
        self._last_speech_time = None
        self._audio_buffer = bytearray()
        self._pre_roll.clear()
        self.vad.reset()
        logger.debug("TurnDetector: LISTENING")

    def process_audio(self, pcm_bytes: bytes) -> dict:
        if self.state == TurnState.IDLE:
            return {"is_speech": False, "event": None, "audio": None}

        audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        is_speech = self.vad.is_speech(audio_np)
        now = time.monotonic()
        event = None
        audio_out = None

        if is_speech:
            self._consecutive_speech += 1
            self._consecutive_silence = 0
            self._last_speech_time = now

            if self.state == TurnState.LISTENING:
                self._append_pre_roll(pcm_bytes)
                if self._consecutive_speech >= self._speech_start_thr:
                    self.state = TurnState.SPEECH
                    self._speech_start_time = now
                    self._audio_buffer = bytearray(self._pre_roll)
                    self._audio_buffer.extend(pcm_bytes)
                    self._pre_roll.clear()
                    event = "speech_start"
                    logger.debug("TurnDetector: SPEECH started")
            elif self.state == TurnState.SPEECH:
                self._audio_buffer.extend(pcm_bytes)
            elif self.state == TurnState.SPEECH_ENDED:
                self.state = TurnState.SPEECH
                self._audio_buffer.extend(pcm_bytes)
        else:
            self._consecutive_silence += 1
            self._consecutive_speech = 0

            if self.state == TurnState.LISTENING:
                self._append_pre_roll(pcm_bytes)
            elif self.state == TurnState.SPEECH:
                self._audio_buffer.extend(pcm_bytes)
                silence_elapsed = (now - self._last_speech_time) if self._last_speech_time else 0
                frames_ok = self._consecutive_silence >= self._silence_end_thr
                time_ok = silence_elapsed >= self._silence_s

                if frames_ok or time_ok:
                    speech_duration = (now - self._speech_start_time) if self._speech_start_time else 0
                    if speech_duration >= self._min_speech_s:
                        event = "speech_end"
                        audio_out = bytes(self._audio_buffer)
                        logger.info(
                            "Turn end: %.2fs speech, %d bytes → STT",
                            speech_duration, len(audio_out),
                        )
                    else:
                        logger.debug("Turn too short (%.2fs), discard", speech_duration)

                    self._audio_buffer = bytearray()
                    self.state = TurnState.LISTENING
                    self._pre_roll.clear()
                    self.vad.reset()

        return {"is_speech": is_speech, "event": event, "audio": audio_out}

    def get_buffered_audio(self) -> bytes:
        return bytes(self._audio_buffer)
