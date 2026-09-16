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

WINDOW_W = 320
WINDOW_H = 110
MARGIN_BOTTOM = 70


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

    def make_click_through(self) -> None:
        """Okno HUD nie może łapać myszy ani kraść fokusu — dyktujemy do innej aplikacji."""
        try:
            from AppKit import NSApplication

            for win in NSApplication.sharedApplication().windows():
                win.setIgnoresMouseEvents_(True)
        except Exception:
            log.exception("nie udało się ustawić click-through (HUD może łapać kliknięcia)")


def run_with_hud(cfg: Config) -> None:
    hud = Hud()
    app = App(cfg, on_state=hud.set_state)

    def backend() -> None:
        hud.make_click_through()
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
