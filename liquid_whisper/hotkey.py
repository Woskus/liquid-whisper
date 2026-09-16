"""Globalny hotkey push-to-talk przez natywny CGEventTap (Quartz).

Celowo bez pynput: jego mapowanie klawiszy woła TSM/HIToolbox spoza głównego
wątku, co pod macOS 26 ubija proces działający jako aplikacja GUI
(dispatch_assert_queue w HIToolbox). Tap patrzy wyłącznie na keycode.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

import Quartz

log = logging.getLogger("liquid_whisper.hotkey")

KEYCODES = {
    "alt_r": 61,
    "alt_l": 58,
    "cmd_r": 54,
    "cmd_l": 55,
    "ctrl_r": 62,
    "ctrl_l": 59,
    "shift_r": 60,
    "shift_l": 56,
    "f13": 105,
    "f14": 107,
    "f15": 113,
    "f16": 106,
    "f17": 64,
    "f18": 79,
    "f19": 80,
}

MODIFIER_FLAG = {
    "alt_r": Quartz.kCGEventFlagMaskAlternate,
    "alt_l": Quartz.kCGEventFlagMaskAlternate,
    "cmd_r": Quartz.kCGEventFlagMaskCommand,
    "cmd_l": Quartz.kCGEventFlagMaskCommand,
    "ctrl_r": Quartz.kCGEventFlagMaskControl,
    "ctrl_l": Quartz.kCGEventFlagMaskControl,
    "shift_r": Quartz.kCGEventFlagMaskShift,
    "shift_l": Quartz.kCGEventFlagMaskShift,
}


class HotkeyListener:
    """Wywołuje on_press przy wciśnięciu i on_release przy puszczeniu hotkeya."""

    def __init__(self, key: str, on_press: Callable[[], None], on_release: Callable[[], None]) -> None:
        if key not in KEYCODES:
            raise ValueError(f"nieobsługiwany hotkey '{key}' — dostępne: {', '.join(KEYCODES)}")
        self.key = key
        self.keycode = KEYCODES[key]
        self.modifier_flag = MODIFIER_FLAG.get(key)
        self.on_press = on_press
        self.on_release = on_release
        self._tap = None

    def set_key(self, key: str) -> None:
        """Podmienia hotkey na żywo — tap nasłuchuje wszystkich klawiszy,
        a callback filtruje po tych polach, więc nie trzeba go przepinać."""
        if key not in KEYCODES:
            raise ValueError(f"nieobsługiwany hotkey '{key}' — dostępne: {', '.join(KEYCODES)}")
        self.key = key
        self.keycode = KEYCODES[key]
        self.modifier_flag = MODIFIER_FLAG.get(key)
        log.info("hotkey zmieniony na [%s]", key)

    def _callback(self, proxy, type_, event, refcon):
        try:
            if type_ in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):
                # system wyłącza tap np. przy zbyt wolnym callbacku — włączamy z powrotem
                Quartz.CGEventTapEnable(self._tap, True)
                return event
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            if keycode != self.keycode:
                return event
            if self.modifier_flag is not None:
                if type_ == Quartz.kCGEventFlagsChanged:
                    down = bool(Quartz.CGEventGetFlags(event) & self.modifier_flag)
                    (self.on_press if down else self.on_release)()
            elif type_ == Quartz.kCGEventKeyDown:
                autorepeat = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventAutorepeat)
                if not autorepeat:
                    self.on_press()
            elif type_ == Quartz.kCGEventKeyUp:
                self.on_release()
        except Exception:
            log.exception("błąd w callbacku hotkeya")
        return event

    def _create_source(self):
        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
        )
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            self._callback,
            None,
        )
        if self._tap is None:
            raise PermissionError(
                "nie można utworzyć event tapu — brak uprawnień "
                "Accessibility/Input Monitoring dla tej aplikacji"
            )
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CGEventTapEnable(self._tap, True)
        return source

    def attach_to_main_runloop(self) -> None:
        """Tryb HUD: tap wpięty w główny run loop (pywebview/NSApp już go kręci)."""
        source = self._create_source()
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetMain(), source, Quartz.kCFRunLoopCommonModes)
        log.info("hotkey [%s] aktywny (main run loop)", self.key)

    def run_blocking(self) -> None:
        """Tryb headless: tap na run loopie bieżącego wątku, blokuje na zawsze."""
        source = self._create_source()
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes)
        log.info("hotkey [%s] aktywny", self.key)
        Quartz.CFRunLoopRun()
