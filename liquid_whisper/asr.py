"""Transkrypcja przez mlx-whisper (Whisper large-v3-turbo, wymuszone language="pl")."""

from __future__ import annotations

import logging

import numpy as np

import mlx_whisper

log = logging.getLogger("liquid_whisper.asr")


class Transcriber:
    def __init__(
        self,
        model: str = "mlx-community/whisper-large-v3-turbo",
        language: str = "pl",
    ) -> None:
        self.model = model
        self.language = language

    def warmup(self) -> None:
        """Pierwsze wywołanie ładuje wagi (i ściąga je przy pierwszym uruchomieniu) —
        robimy to na starcie aplikacji, nie w trakcie pierwszego dyktanda."""
        silence = np.zeros(16000, dtype=np.float32)
        self.transcribe(silence)
        log.info("model %s załadowany", self.model)

    def transcribe(self, audio: np.ndarray | str) -> str:
        """Audio: 1-D float32 16 kHz albo ścieżka do pliku."""
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.model,
            language=self.language,
            fp16=True,
        )
        segments = result.get("segments") or []
        if segments:
            # cisza/oddech: Whisper halucynuje frazy typu "Dziękuję za oglądanie"
            kept = [s["text"] for s in segments if s.get("no_speech_prob", 0.0) < 0.6]
            dropped = len(segments) - len(kept)
            if dropped:
                log.info("odrzucono %d segment(y) bez mowy", dropped)
            return " ".join(t.strip() for t in kept).strip()
        return str(result["text"]).strip()
