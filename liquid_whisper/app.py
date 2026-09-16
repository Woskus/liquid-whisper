"""Główna aplikacja: push-to-talk (przytrzymaj hotkey → mów → puść → tekst w aktywnym polu)."""

from __future__ import annotations

import logging
import queue
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
TAP_MAX_S = 0.35  # krótsze przytrzymanie = "kliknięcie" (kandydat na dwuklik)
DOUBLE_TAP_GAP_S = 0.45  # maks. przerwa między kliknięciami dwukliku


def check_permissions() -> bool:
    """Sprawdza Accessibility i Input Monitoring; przy braku prosi systemowym
    promptem (macOS sam dodaje wtedy aplikację do właściwej listy w ustawieniach)."""
    import Quartz
    from ApplicationServices import AXIsProcessTrusted, AXIsProcessTrustedWithOptions

    ax = bool(AXIsProcessTrusted())
    if not ax:
        AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
        log.warning(
            "Brak uprawnień Accessibility (wklejanie ⌘V) — zatwierdź systemowy monit "
            "albo włącz ręcznie: System Settings → Privacy & Security → Accessibility."
        )
    im = bool(Quartz.CGPreflightListenEventAccess())
    if not im:
        Quartz.CGRequestListenEventAccess()
        log.warning(
            "Brak uprawnień Input Monitoring (nasłuch hotkeya) — zatwierdź monit "
            "albo włącz ręcznie: System Settings → Privacy & Security → Input Monitoring."
        )
    if not (ax and im):
        log.warning("po nadaniu uprawnień uruchom aplikację ponownie")
    return ax and im


class App:
    """Stany: idle → recording (hotkey wciśnięty) → processing → idle.

    on_state — hak dla HUD (etap 4).
    """

    def __init__(
        self,
        cfg: Config,
        on_state: Callable[[str], None] | None = None,
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.on_state = on_state or (lambda state: None)
        self.on_level = on_level
        self.recorder = Recorder(cfg.sample_rate, cfg.channels)
        self.asr = Transcriber(cfg.asr_model, cfg.language)
        self.cleaner = (
            Cleaner(
                model=cfg.cleanup_model,
                dictionary=cfg.dictionary,
                corrections=cfg.corrections,
                min_words=cfg.cleanup_min_words,
                timeout_s=cfg.cleanup_timeout_s,
            )
            if cfg.cleanup_enabled
            else None
        )
        from .learn import SuggestionStore

        self.suggestions = SuggestionStore()
        self.listener = HotkeyListener(cfg.hotkey, self._on_press, self._on_release)
        # tryby: idle | held (przytrzymany, push-to-talk) | grace (po 1. kliknięciu,
        # czekamy na ewentualny dwuklik) | held2 (2. kliknięcie wciśnięte) |
        # toggle (nagrywanie ciągłe) | stopping (kliknięcie kończące toggle)
        self._mode = "idle"
        self._press_t = 0.0
        self._grace_timer: threading.Timer | None = None
        # callback tapa działa na głównym wątku i musi wracać natychmiast
        # (timeout tapa, deadlock evaluate_js) — akcje wykonuje wątek roboczy
        self._actions: queue.Queue[Callable[[], None]] = queue.Queue()
        threading.Thread(target=self._action_worker, daemon=True).start()

    def _action_worker(self) -> None:
        while True:
            action = self._actions.get()
            try:
                action()
            except Exception:
                log.exception("błąd akcji hotkeya")

    def _set_state(self, state: str) -> None:
        log.info("stan: %s", state)
        self.on_state(state)

    def _on_press(self) -> None:
        self._actions.put(self._press_action)

    def _on_release(self) -> None:
        self._actions.put(self._release_action)

    def reload_dictionary(self) -> None:
        """Po zmianie słowniczka w okienku — świeże dane do promptu cleanupu."""
        from . import dictionary

        terms, corrections = dictionary.load()
        self.cfg.dictionary = terms
        self.cfg.corrections = corrections
        if self.cleaner is not None:
            self.cleaner.dictionary = terms
            self.cleaner.corrections = corrections

    def _level_pump(self) -> None:
        import time

        while self.recorder.recording:
            try:
                self.on_level(min(1.0, self.recorder.level * 15.0))
            except Exception:
                return
            time.sleep(0.08)

    def _start_recording(self) -> None:
        self.recorder.start()
        self._set_state("recording")
        if self.on_level is not None:
            threading.Thread(target=self._level_pump, daemon=True).start()

    def _finish_recording(self) -> None:
        audio = self.recorder.stop()
        self._set_state("processing")
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _press_action(self) -> None:
        import time

        try:
            if self._mode == "idle":
                self._press_t = time.monotonic()
                self._start_recording()
                self._mode = "held"
            elif self._mode == "grace":
                # drugie kliknięcie dwukliku — nagrywanie już trwa, tylko je utrzymujemy
                if self._grace_timer is not None:
                    self._grace_timer.cancel()
                    self._grace_timer = None
                self._press_t = time.monotonic()
                self._mode = "held2"
            elif self._mode == "toggle":
                # pojedyncze kliknięcie kończy nagrywanie ciągłe
                log.info("nagrywanie ciągłe: stop")
                self._finish_recording()
                self._mode = "stopping"
        except Exception:
            log.exception("nie udało się rozpocząć nagrywania")
            self._mode = "idle"
            self._set_state("idle")

    def _release_action(self) -> None:
        import time

        try:
            held_s = time.monotonic() - self._press_t
            if self._mode == "held":
                if held_s >= TAP_MAX_S:
                    self._finish_recording()  # klasyczny push-to-talk
                    self._mode = "idle"
                else:
                    # kliknięcie — czekamy chwilę na drugie (dwuklik = tryb ciągły)
                    self._mode = "grace"
                    self._grace_timer = threading.Timer(
                        DOUBLE_TAP_GAP_S, lambda: self._actions.put(self._grace_expired)
                    )
                    self._grace_timer.daemon = True
                    self._grace_timer.start()
            elif self._mode == "held2":
                if held_s >= TAP_MAX_S:
                    self._finish_recording()  # drugie "kliknięcie" okazało się przytrzymaniem
                    self._mode = "idle"
                else:
                    log.info("nagrywanie ciągłe: start (zakończysz pojedynczym kliknięciem)")
                    self._mode = "toggle"
            elif self._mode == "stopping":
                self._mode = "idle"
        except Exception:
            log.exception("błąd przy kończeniu nagrania")
            self._mode = "idle"
            self._set_state("idle")

    def _grace_expired(self) -> None:
        """Minęło okno dwukliku po pojedynczym kliknięciu — odrzucamy przypadkowe nagranie."""
        if self._mode != "grace":
            return
        self._grace_timer = None
        self._mode = "idle"
        self.recorder.stop()
        log.info("pojedyncze kliknięcie hotkeya — ignoruję")
        self._set_state("idle")

    def _process(self, audio) -> None:
        try:
            duration = len(audio) / self.cfg.sample_rate
            if duration < MIN_DICTATION_S:
                log.info("nagranie za krótkie (%.2f s) — ignoruję", duration)
                return
            from .audio import has_speech

            if not has_speech(audio, self.cfg.sample_rate):
                log.info("brak mowy w nagraniu (%.1f s) — ignoruję", duration)
                return
            report = LatencyReport()
            with report.measure("transkrypcja"):
                text = self.asr.transcribe(audio)
            if not text:
                log.info("pusty transkrypt — nic nie wklejam")
                return
            log.info("surowy transkrypt: %s", text)
            if self.cleaner is not None:
                raw = text
                with report.measure("cleanup"):
                    text = self.cleaner.clean(raw)
                log.info("po cleanupie: %s", text)
                if text != raw:
                    try:
                        from .learn import extract_pairs

                        self.suggestions.record(extract_pairs(raw, text), self.cfg.corrections)
                    except Exception:
                        log.exception("nie udało się zapisać propozycji słowniczka")
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
