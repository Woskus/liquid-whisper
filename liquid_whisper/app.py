"""Główna aplikacja: push-to-talk (przytrzymaj hotkey → mów → puść → tekst w aktywnym polu)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from .asr import Transcriber
from .audio import Recorder
from .cleanup import Cleaner
from .config import Config, load_config
from .hotkey import HotkeyListener
from .latency import LatencyReport
from .paste import paste_text

log = logging.getLogger("liquid_whisper.app")

MIN_DICTATION_S = 0.3


def check_permissions() -> bool:
    from ApplicationServices import AXIsProcessTrusted

    trusted = bool(AXIsProcessTrusted())
    if not trusted:
        log.warning(
            "Brak uprawnień Accessibility — hotkey i ⌘V nie zadziałają. "
            "System Settings → Privacy & Security → Accessibility (i Input Monitoring): "
            "dodaj Liquid Whisper.app albo aplikację terminala, z której startujesz."
        )
    return trusted


class App:
    """Stany: idle → recording (hotkey wciśnięty) → processing → idle.

    on_state — hak dla HUD (etap 4).
    """

    def __init__(self, cfg: Config, on_state: Callable[[str], None] | None = None) -> None:
        self.cfg = cfg
        self.on_state = on_state or (lambda state: None)
        self.recorder = Recorder(cfg.sample_rate, cfg.channels)
        self.asr = Transcriber(cfg.asr_model, cfg.language)
        self.cleaner = (
            Cleaner(
                model=cfg.cleanup_model,
                dictionary=cfg.dictionary,
                min_words=cfg.cleanup_min_words,
                timeout_s=cfg.cleanup_timeout_s,
            )
            if cfg.cleanup_enabled
            else None
        )
        self.listener = HotkeyListener(cfg.hotkey, self._on_press, self._on_release)
        self._pressed = False

    def _set_state(self, state: str) -> None:
        log.info("stan: %s", state)
        self.on_state(state)

    def _on_press(self) -> None:
        try:
            if not self._pressed:
                self._pressed = True
                self.recorder.start()
                self._set_state("recording")
        except Exception:
            log.exception("nie udało się rozpocząć nagrywania")
            self._pressed = False
            self._set_state("idle")

    def _on_release(self) -> None:
        try:
            if self._pressed:
                self._pressed = False
                audio = self.recorder.stop()
                self._set_state("processing")
                threading.Thread(target=self._process, args=(audio,), daemon=True).start()
        except Exception:
            log.exception("błąd przy kończeniu nagrania")
            self._set_state("idle")

    def _process(self, audio) -> None:
        try:
            duration = len(audio) / self.cfg.sample_rate
            if duration < MIN_DICTATION_S:
                log.info("nagranie za krótkie (%.2f s) — ignoruję", duration)
                return
            report = LatencyReport()
            with report.measure("transkrypcja"):
                text = self.asr.transcribe(audio)
            if not text:
                log.info("pusty transkrypt — nic nie wklejam")
                return
            log.info("surowy transkrypt: %s", text)
            if self.cleaner is not None:
                with report.measure("cleanup"):
                    text = self.cleaner.clean(text)
                log.info("po cleanupie: %s", text)
            with report.measure("wklejenie"):
                paste_text(text)
            report.log_summary()
        except Exception:
            log.exception("błąd przetwarzania dyktanda")
        finally:
            self._set_state("idle")

    def run(self) -> None:
        check_permissions()
        log.info("ładowanie modelu ASR...")
        self.asr.warmup()
        if self.cleaner is not None:
            self.cleaner.warmup()
        self._set_state("idle")
        log.info("gotowy — przytrzymaj [%s], mów, puść", self.cfg.hotkey)
        self.listener.run_blocking()


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(prog="liquid-whisper")
    parser.add_argument("--no-hud", action="store_true", help="tryb headless, bez overlaya")
    args = parser.parse_args()
    cfg = load_config()

    if not args.no_hud:
        try:
            from .hud import run_with_hud

            run_with_hud(cfg)
            return
        except Exception:
            log.exception("HUD niedostępny — przechodzę w tryb headless")
    App(cfg).run()


if __name__ == "__main__":
    main()
