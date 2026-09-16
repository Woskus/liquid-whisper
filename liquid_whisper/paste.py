"""Wstrzykiwanie tekstu: schowek + symulacja ⌘V przez CGEvent (pyobjc)."""

from __future__ import annotations

import time

import Quartz
from AppKit import NSPasteboard, NSPasteboardTypeString

KEY_V = 9  # kVK_ANSI_V
KEY_BACKSPACE = 51


def type_text(text: str) -> None:
    """Wpisuje tekst w aktywne pole jako zdarzenia klawiatury (unicode, bez schowka).

    Używane przez streaming na żywo — ⌘V byłoby zbyt inwazyjne przy częstych
    aktualizacjach. Chunki po 20 znaków (limit CGEventKeyboardSetUnicodeString).
    """
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for i in range(0, len(text), 20):
        chunk = text[i : i + 20]
        for key_down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(source, 0, key_down)
            Quartz.CGEventKeyboardSetUnicodeString(event, len(chunk.encode("utf-16-le")) // 2, chunk)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.004)


def send_backspaces(n: int) -> None:
    """Cofa n znaków w aktywnym polu (rewizja tekstu wpisanego przez streaming)."""
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for i in range(n):
        for key_down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(source, KEY_BACKSPACE, key_down)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        if i % 10 == 9:
            time.sleep(0.004)


def set_clipboard(text: str) -> None:
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)


def get_clipboard() -> str | None:
    pb = NSPasteboard.generalPasteboard()
    return pb.stringForType_(NSPasteboardTypeString)


def send_cmd_v() -> None:
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    down = Quartz.CGEventCreateKeyboardEvent(source, KEY_V, True)
    Quartz.CGEventSetFlags(down, Quartz.kCGEventFlagMaskCommand)
    up = Quartz.CGEventCreateKeyboardEvent(source, KEY_V, False)
    Quartz.CGEventSetFlags(up, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)


def paste_text(text: str, restore_clipboard: bool = True) -> None:
    """Wkleja tekst w aktywne pole: schowek → ⌘V → (opcjonalnie) przywrócenie schowka."""
    previous = get_clipboard() if restore_clipboard else None
    set_clipboard(text)
    time.sleep(0.05)  # pasteboard musi zdążyć się zsynchronizować przed ⌘V
    send_cmd_v()
    if restore_clipboard and previous is not None:
        # ⌘V czyta schowek asynchronicznie w docelowej aplikacji
        time.sleep(0.3)
        set_clipboard(previous)
