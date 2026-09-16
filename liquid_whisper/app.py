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
from .paste import paste_text, send_backspaces, type_text

log = logging.getLogger("liquid_whisper.app")

MIN_DICTATION_S = 0.3


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
        on_partial: Callable[[str], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.on_state = on_state or (lambda state: None)
        self.on_level = on_level
        self.on_partial = on_partial
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
        self._pressed = False
        # callback tapa działa na głównym wątku i musi wracać natychmiast
        # (timeout tapa, deadlock evaluate_js) — akcje wykonuje wątek roboczy
        self._actions: queue.Queue[Callable[[], None]] = queue.Queue()
        threading.Thread(target=self._action_worker, daemon=True).start()
        # streaming na żywo do aktywnego pola
        self._injected = ""  # tekst aktualnie wpisany w pole przez streaming
        self._inject_lock = threading.Lock()
        self._stream_thread: threading.Thread | None = None

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

    def _stream_pump(self) -> None:
        """Streaming transkrypcji: co ~1 s transkrybuje dotychczasowe audio.
        Tryb "input" wpisuje częściowy tekst prosto w aktywne pole (z rewizjami),
        tryb "hud" pokazuje go w pasku HUD. Finalny wynik i tak liczy się od zera
        po puszczeniu hotkeya."""
        import time

        from .audio import has_speech

        live = self.cfg.streaming_mode == "input"
        min_samples = int(self.cfg.sample_rate * 1.0)
        while self.recorder.recording:
            snap = self.recorder.snapshot()
            if len(snap) >= min_samples and has_speech(snap, self.cfg.sample_rate):
                try:
                    partial = self.asr.transcribe(snap)
                except Exception:
                    log.exception("streaming transkrypcji przerwany")
                    return
                if partial:
                    if live:
                        self._revise_injected(partial, only_while_recording=True)
                    elif self.recorder.recording and self.on_partial is not None:
                        try:
                            self.on_partial(partial)
                        except Exception:
                            return
            time.sleep(0.35)

    def _clear_injected(self) -> None:
        """Usuwa z pola podgląd wpisany przez streaming (nagranie odrzucone)."""
        if self._stream_thread is not None:
            self._stream_thread.join(timeout=3.0)
            self._stream_thread = None
        if self._injected:
            self._revise_injected("")
            self._injected = ""

    def _revise_injected(self, new_text: str, only_while_recording: bool = False) -> None:
        """Doprowadza tekst w aktywnym polu do new_text: cofa rozbieżną końcówkę
        i dopisuje różnicę (wspólny prefiks zostaje nietknięty)."""
        with self._inject_lock:
            if only_while_recording and not self.recorder.recording:
                return  # puszczono hotkey — finalną wersję wpisze _process
            old = self._injected
            prefix = 0
            for a, b in zip(old, new_text):
                if a != b:
                    break
                prefix += 1
            if len(old) - prefix > 0:
                send_backspaces(len(old) - prefix)
            if new_text[prefix:]:
                type_text(new_text[prefix:])
            self._injected = new_text

    def _press_action(self) -> None:
        try:
            if not self._pressed:
                self._pressed = True
                self.recorder.start()
                self._set_state("recording")
                self._injected = ""
                if self.on_level is not None:
                    threading.Thread(target=self._level_pump, daemon=True).start()
                if self.cfg.streaming_mode != "off" and (
                    self.cfg.streaming_mode == "input" or self.on_partial is not None
                ):
                    self._stream_thread = threading.Thread(target=self._stream_pump, daemon=True)
                    self._stream_thread.start()
        except Exception:
            log.exception("nie udało się rozpocząć nagrywania")
            self._pressed = False
            self._set_state("idle")

    def _release_action(self) -> None:
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
                self._clear_injected()
                return
            from .audio import has_speech

            if not has_speech(audio, self.cfg.sample_rate):
                log.info("brak mowy w nagraniu (%.1f s) — ignoruję", duration)
                self._clear_injected()
                return
            report = LatencyReport()
            with report.measure("transkrypcja"):
                text = self.asr.transcribe(audio)
            if not text:
                log.info("pusty transkrypt — nic nie wklejam")
                self._clear_injected()
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
            if self._stream_thread is not None:
                self._stream_thread.join(timeout=3.0)
                self._stream_thread = None
            if self._injected:
                # streaming już wpisał tekst — tylko korekta do wersji finalnej
                with report.measure("korekta"):
                    self._revise_injected(text)
                    self._injected = ""
            else:
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
