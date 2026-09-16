"""Główna aplikacja: push-to-talk (przytrzymaj hotkey → mów → puść → tekst w aktywnym polu)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from pynput import keyboard

from .asr import Transcriber
from .audio import Recorder
from .config import Config, load_config
from .latency import LatencyReport
from .paste import paste_text

log = logging.getLogger("liquid_whisper.app")

MIN_DICTATION_S = 0.3


def parse_hotkey(name: str) -> keyboard.Key | keyboard.KeyCode:
    """"alt_r" → Key.alt_r; pojedynczy znak → KeyCode."""
    try:
        return getattr(keyboard.Key, name)
    except AttributeError:
        return keyboard.KeyCode.from_char(name)


def check_permissions() -> bool:
    from ApplicationServices import AXIsProcessTrusted

    trusted = bool(AXIsProcessTrusted())
    if not trusted:
        log.warning(
            "Brak uprawnień Accessibility — hotkey i ⌘V nie zadziałają. "
            "System Settings → Privacy & Security → Accessibility: dodaj aplikację "
            "terminala, z której uruchamiasz Liquid Whisper (oraz Input Monitoring)."
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
        self.cleaner = None  # wpinany w etapie 3
        self.hotkey = parse_hotkey(cfg.hotkey)
        self._pressed = False

    def _set_state(self, state: str) -> None:
        log.info("stan: %s", state)
        self.on_state(state)

    def _on_press(self, key) -> None:
        if key == self.hotkey and not self._pressed:
            self._pressed = True
            self.recorder.start()
            self._set_state("recording")

    def _on_release(self, key) -> None:
        if key == self.hotkey and self._pressed:
            self._pressed = False
            audio = self.recorder.stop()
            self._set_state("processing")
            threading.Thread(target=self._process, args=(audio,), daemon=True).start()

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

    def start_listener(self) -> keyboard.Listener:
        listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        listener.start()
        return listener

    def run(self) -> None:
        check_permissions()
        log.info("ładowanie modelu ASR...")
        self.asr.warmup()
        self._set_state("idle")
        log.info("gotowy — przytrzymaj [%s], mów, puść", self.cfg.hotkey)
        listener = self.start_listener()
        listener.join()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    App(load_config()).run()


if __name__ == "__main__":
    main()
