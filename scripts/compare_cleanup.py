"""Porównanie kandydatów cleanup (etap 3) na realnych dyktandach.

Transkrybuje wszystkie WAV-y z recordings/, przepuszcza surowe transkrypty
przez każdy model z listy i wypisuje zestawienie wyjść + latencji.

  .venv/bin/python scripts/compare_cleanup.py [model1 model2 ...]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from liquid_whisper.asr import Transcriber
from liquid_whisper.cleanup import Cleaner
from liquid_whisper.config import load_config

DEFAULT_MODELS = [
    "qwen3:4b-instruct",
    "gemma3:4b",
    "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0",
]


def main() -> None:
    models = sys.argv[1:] or DEFAULT_MODELS
    cfg = load_config()
    root = Path(__file__).resolve().parent.parent
    wavs = sorted((root / "recordings").glob("*.wav"))
    if not wavs:
        sys.exit("brak nagrań w recordings/")

    asr = Transcriber(model=cfg.asr_model, language=cfg.language)
    print("transkrybuję nagrania...", file=sys.stderr)
    transcripts = [(w.name, asr.transcribe(str(w))) for w in wavs]

    cleaners = {m: Cleaner(m, dictionary=cfg.dictionary, timeout_s=60.0) for m in models}
    for m, c in cleaners.items():
        print(f"warmup {m}...", file=sys.stderr)
        c.warmup()
        c.clean("To jest yyy test rozgrzewkowy pipelinu.")  # pierwszy strzał bywa wolniejszy

    latency: dict[str, list[float]] = {m: [] for m in models}
    for name, raw in transcripts:
        print(f"\n{'=' * 78}\n### {name}\nSUROWY : {raw}")
        for m, c in cleaners.items():
            t0 = time.perf_counter()
            cleaned = c.clean(raw)
            dt = time.perf_counter() - t0
            latency[m].append(dt)
            print(f"[{m}  {dt:.2f}s]\n         {cleaned}")

    print(f"\n{'=' * 78}\nŚrednia latencja cleanup:")
    for m, ts in latency.items():
        print(f"  {m}: {sum(ts) / len(ts):.2f}s (min {min(ts):.2f} / max {max(ts):.2f})")


if __name__ == "__main__":
    main()
