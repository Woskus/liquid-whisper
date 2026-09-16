"""Nagrywanie z mikrofonu: 16 kHz mono, float32 (format oczekiwany przez Whispera)."""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd


class Recorder:
    """Nagrywanie push-to-talk: start() przy wciśnięciu, stop() przy puszczeniu."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._chunks = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        self._chunks.append(indata.copy())

    def stop(self) -> np.ndarray:
        """Kończy nagrywanie i zwraca audio jako 1-D float32."""
        with self._lock:
            if self._stream is None:
                return np.zeros(0, dtype=np.float32)
            self._stream.stop()
            self._stream.close()
            self._stream = None
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks, axis=0)
            self._chunks = []
        return audio.reshape(-1).astype(np.float32)

    @property
    def recording(self) -> bool:
        return self._stream is not None


def record_seconds(seconds: float, sample_rate: int = 16000) -> np.ndarray:
    """Proste nagranie o stałej długości (do testów etapu 1)."""
    audio = sd.rec(
        int(seconds * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return audio.reshape(-1)
