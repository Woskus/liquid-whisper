"""Liquid metal HUD: frameless, przezroczysty, always-on-top overlay pywebview.

Renderuje zbudowany bundle React + metal-fx z hud/dist. Stany przekazywane
z pipeline'u przez evaluate_js → window.setHudState.
"""

from __future__ import annotations

import logging
from pathlib import Path

import Quartz
import webview

from .app import App, check_permissions
from .config import Config

log = logging.getLogger("liquid_whisper.hud")

DIST_INDEX = Path(__file__).resolve().parent.parent / "hud" / "dist" / "index.html"

WINDOW_W = 180
WINDOW_H = 70
MARGIN_BOTTOM = 52


class Hud:
    def __init__(self) -> None:
        if not DIST_INDEX.exists():
            raise FileNotFoundError(
                f"brak bundle HUD: {DIST_INDEX} — zbuduj przez `cd hud && npm run build`"
            )
        self._nswindow = None  # natywne NSWindow HUD-a, ustawiane w configure_overlay
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
        if state == "recording":
            # ekran/przestrzeń mogły się zmienić od startu — dosuń pastylkę na środek
            self.recenter_async()
        try:
            self.window.evaluate_js(f"window.setHudState && window.setHudState('{state}')")
        except Exception:
            log.exception("nie udało się zaktualizować stanu HUD")

    def set_level(self, level: float) -> None:
        try:
            self.window.evaluate_js(f"window.setHudLevel && window.setHudLevel({level:.3f})")
        except Exception:
            pass  # wizualizacja poziomu jest kosmetyczna — nie zaśmiecamy loga

    def configure_overlay(self) -> None:
        """Natywna konfiguracja HUD — wołać na wątku głównym.

        Okno pywebview jest tworzone jako titled (frameless = ukryta belka),
        a macOS klasyfikuje okna według stanu z chwili narodzin i takich nie
        wpuszcza na cudze przestrzenie fullscreen (isOnActiveSpace=False mimo
        CanJoinAllSpaces; późniejsza zmiana styleMask nic nie daje). Dlatego
        przenosimy contentView (z WKWebView) do świeżego, od urodzenia
        borderless NSPanelu, a okno pywebview chowamy — evaluate_js dalej
        działa, bo rozmawia z WKWebView, nie z oknem.
        """
        try:
            import AppKit
            from AppKit import NSApplication

            # aplikacja-agent (jak Spotlight): bez ikony w Docku i ⌘Tab — okna
            # zwykłych aplikacji nie pokazują się nad cudzym fullscreenem
            NSApplication.sharedApplication().setActivationPolicy_(
                AppKit.NSApplicationActivationPolicyAccessory
            )
            for win in NSApplication.sharedApplication().windows():
                if win.title() != "Liquid Whisper":
                    continue  # okna słowniczka/ustawień mają zostać zwykłymi oknami
                frame = win.frame()
                panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                    (frame.origin, frame.size),
                    AppKit.NSWindowStyleMaskBorderless
                    | AppKit.NSWindowStyleMaskNonactivatingPanel,
                    AppKit.NSBackingStoreBuffered,
                    False,
                )
                panel.setReleasedWhenClosed_(False)
                panel.setOpaque_(False)
                panel.setBackgroundColor_(AppKit.NSColor.clearColor())
                panel.setHasShadow_(False)
                panel.setIgnoresMouseEvents_(True)
                # poziom wygaszacza — ponad oknami fullscreen; CanJoinAllSpaces
                # + FullScreenAuxiliary: panel wchodzi na każdą przestrzeń
                panel.setLevel_(getattr(AppKit, "NSScreenSaverWindowLevel", 1000))
                panel.setCollectionBehavior_(
                    AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                    | AppKit.NSWindowCollectionBehaviorStationary
                    | AppKit.NSWindowCollectionBehaviorIgnoresCycle
                    | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
                )
                panel.setContentView_(win.contentView())
                win.orderOut_(None)
                panel.orderFrontRegardless()
                self._nswindow = panel
                self._recenter(panel)
        except Exception:
            log.exception("nie udało się skonfigurować okna HUD")

    def _recenter(self, win) -> None:
        """Środek ekranu w poziomie + stały margines od dołu — natywnie z ramki
        NSScreen, bo współrzędne wyliczane przez pywebview potrafią zjechać."""
        from AppKit import NSScreen

        screen = win.screen() or NSScreen.mainScreen()
        if screen is None:
            return
        sf = screen.frame()
        wf = win.frame()
        x = sf.origin.x + (sf.size.width - wf.size.width) / 2.0
        y = sf.origin.y + MARGIN_BOTTOM  # współrzędne Cocoa: origin w lewym dolnym rogu
        win.setFrameOrigin_((x, y))

    def recenter_async(self) -> None:
        """Wyśrodkowanie z dowolnego wątku (AppKit wolno ruszać tylko z głównego)."""
        if self._nswindow is None:
            return
        win = self._nswindow
        Quartz.CFRunLoopPerformBlock(
            Quartz.CFRunLoopGetMain(), Quartz.kCFRunLoopCommonModes, lambda: self._recenter(win)
        )
        Quartz.CFRunLoopWakeUp(Quartz.CFRunLoopGetMain())


def run_with_hud(cfg: Config) -> None:
    hud = Hud()
    app = App(cfg, on_state=hud.set_state, on_level=hud.set_level)

    def backend() -> None:
        # konfiguracja natywna okna i ikona w pasku menu — na wątku głównym
        from .menubar import create_status_item

        def _main_thread_setup() -> None:
            hud.configure_overlay()
            create_status_item(app)

        Quartz.CFRunLoopPerformBlock(
            Quartz.CFRunLoopGetMain(), Quartz.kCFRunLoopCommonModes, _main_thread_setup
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
