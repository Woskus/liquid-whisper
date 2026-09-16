"""CLI narzędziowe: testy poszczególnych ogniw pipeline'u.

  python -m liquid_whisper.cli file <ścieżka.wav>   # transkrypcja pliku
  python -m liquid_whisper.cli record [sekundy]      # nagraj z mikrofonu → transkrypt → schowek
"""

from __future__ import annotations

import argparse
import logging
import sys

from .asr import Transcriber
from .audio import record_seconds
from .config import load_config
from .latency import LatencyReport


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    parser = argparse.ArgumentParser(prog="liquid-whisper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_file = sub.add_parser("file", help="transkrybuj plik audio")
    p_file.add_argument("path")

    p_rec = sub.add_parser("record", help="nagraj z mikrofonu i transkrybuj")
    p_rec.add_argument("seconds", nargs="?", type=float, default=8.0)

    args = parser.parse_args()
    cfg = load_config()
    asr = Transcriber(model=cfg.asr_model, language=cfg.language)
    report = LatencyReport()

    if args.cmd == "file":
        with report.measure("transkrypcja"):
            text = asr.transcribe(args.path)
        print(text)
    elif args.cmd == "record":
        asr.warmup()
        print(f"Nagrywam {args.seconds:.0f} s — mów teraz...", file=sys.stderr)
        audio = record_seconds(args.seconds, cfg.sample_rate)
        print("Koniec nagrania, transkrybuję...", file=sys.stderr)

        # zapis nagrania do katalogu danych — materiał do porównania modeli cleanup
        import datetime
        import wave

        import numpy as np

        from .config import DATA_DIR

        rec_dir = DATA_DIR / "recordings"
        rec_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        wav_path = rec_dir / f"dyktando_{stamp}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(cfg.sample_rate)
            wf.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
        print(f"(nagranie zapisane: {wav_path})", file=sys.stderr)
        with report.measure("transkrypcja"):
            text = asr.transcribe(audio)
        print(text)
        from .paste import set_clipboard

        set_clipboard(text)
        print("(transkrypt skopiowany do schowka)", file=sys.stderr)

    report.log_summary()


if __name__ == "__main__":
    main()
