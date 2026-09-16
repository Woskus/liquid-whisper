"""Liquid metal HUD: frameless, przezroczysty, always-on-top overlay pywebview.

Renderuje zbudowany bundle React + metal-fx z hud/dist. Stany przekazywane
z pipeline'u przez evaluate_js → window.setHudState.
"""

from __future__ import annotations

import logging
from pathlib import Path

import webview

from .app import App, check_permissions
from .config import Config

log = logging.getLogger("liquid_whisper.hud")

DIST_INDEX = Path(__file__).resolve().parent.parent / "hud" / "dist" / "index.html"

WINDOW_W = 500
WINDOW_H = 104
MARGIN_BOTTOM = 44


class Hud:
    def __init__(self) -> None:
        if not DIST_INDEX.exists():
            raise FileNotFoundError(
                f"brak bundle HUD: {DIST_INDEX} — zbuduj przez `cd hud && npm run build`"
            )
        screen = webview.screens[0]
        self.window = webview.create_window(
            "Liquid Whisper",
            DIST_INDEX.as_uri(),
            width=WINDOW_W,
            height=WINDOW_H,
            x=(screen.width - WINDOW_W) // 2,
            y=screen.height - WINDOW_H - MARGIN_BOTTOM,
            frameless=True,
            transparent=True,
            on_top=True,
            resizable=False,
            focus=False,
        )

    def set_state(self, state: str) -> None:
        try:
            self.window.evaluate_js(f"window.setHudState && window.setHudState('{state}')")
        except Exception:
            log.exception("nie udało się zaktualizować stanu HUD")

    def set_level(self, level: float) -> None:
        try:
            self.window.evaluate_js(f"window.setHudLevel && window.setHudLevel({level:.3f})")
        except Exception:
            pass  # wizualizacja poziomu jest kosmetyczna — nie zaśmiecamy loga

    def set_partial(self, text: str) -> None:
        import json

        try:
            self.window.evaluate_js(f"window.setHudText && window.setHudText({json.dumps(text)})")
        except Exception:
            pass

    def make_click_through(self) -> None:
        """Okno HUD nie może łapać myszy ani kraść fokusu — dyktujemy do innej aplikacji."""
        try:
            from AppKit import NSApplication

            for win in NSApplication.sharedApplication().windows():
                win.setIgnoresMouseEvents_(True)
        except Exception:
            log.exception("nie udało się ustawić click-through (HUD może łapać kliknięcia)")


def run_with_hud(cfg: Config) -> None:
    import Quartz

    hud = Hud()
    app = App(
        cfg,
        on_state=hud.set_state,
        on_level=hud.set_level,
        # pasek podglądu w HUD tylko gdy streaming nie wpisuje prosto w pole
        on_partial=hud.set_partial if cfg.streaming_mode == "hud" else None,
    )

    def backend() -> None:
        hud.make_click_through()
        # ikona w pasku menu musi powstać na wątku głównym
        from .menubar import create_status_item

        Quartz.CFRunLoopPerformBlock(
            Quartz.CFRunLoopGetMain(), Quartz.kCFRunLoopCommonModes, lambda: create_status_item(app)
        )
        Quartz.CFRunLoopWakeUp(Quartz.CFRunLoopGetMain())
        check_permissions()
        log.info("ładowanie modelu ASR...")
        app.asr.warmup()
        if app.cleaner is not None:
            app.cleaner.warmup()
        try:
            app.listener.attach_to_main_runloop()
        except PermissionError as e:
            log.error("%s — nadaj uprawnienia i uruchom ponownie", e)
            return
        log.info("gotowy — przytrzymaj [%s], mów, puść", cfg.hotkey)

    # webview.start blokuje główny wątek (wymóg cocoa); backend rusza w wątku pywebview
    webview.start(backend)
