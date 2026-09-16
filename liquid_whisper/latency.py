"""Pomiar latencji poszczególnych ogniw pipeline'u.

Budżet: 2–3 s od puszczenia hotkeya do wklejenia tekstu.
Każde ogniwo logowane osobno + suma.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager

log = logging.getLogger("liquid_whisper.latency")


class LatencyReport:
    """Zbiera czasy ogniw jednego dyktanda i loguje podsumowanie."""

    def __init__(self) -> None:
        self.stages: dict[str, float] = {}

    @contextmanager
    def measure(self, stage: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt = time.perf_counter() - t0
            self.stages[stage] = dt
            log.info("%s: %.2f s", stage, dt)

    @property
    def total(self) -> float:
        return sum(self.stages.values())

    def summary(self) -> str:
        parts = " | ".join(f"{k} {v:.2f}s" for k, v in self.stages.items())
        return f"{parts} | RAZEM {self.total:.2f}s"

    def log_summary(self) -> None:
        log.info("latencja: %s", self.summary())
