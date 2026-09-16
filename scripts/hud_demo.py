"""Demo HUD (etap 4): otwiera prawdziwy overlay i cyklicznie przełącza stany
idle → nagrywam → przetwarzam, bez dotykania mikrofonu i modeli.

  .venv/bin/python scripts/hud_demo.py [liczba_cykli]
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from liquid_whisper.hud import Hud


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    hud = Hud()

    def run() -> None:
        hud.make_click_through()
        time.sleep(1.0)
        for i in range(cycles):
            print(f"cykl {i + 1}/{cycles}: recording", flush=True)
            hud.set_state("recording")
            time.sleep(2.5)
            print(f"cykl {i + 1}/{cycles}: processing", flush=True)
            hud.set_state("processing")
            time.sleep(1.5)
            print(f"cykl {i + 1}/{cycles}: idle", flush=True)
            hud.set_state("idle")
            time.sleep(1.5)
        hud.window.destroy()

    import webview

    webview.start(run)
    print("demo zakończone", flush=True)


if __name__ == "__main__":
    main()
