"""Ikona Liquid Whisper w pasku menu (NSStatusItem) + okienko słowniczka.

Ikona: systemowy symbol kropli (motyw liquid), template — dopasowuje się do
jasnego/ciemnego paska. Menu: Słowniczek… / Zakończ.
"""

from __future__ import annotations

import logging
import threading

import objc
from AppKit import (
    NSApplication,
    NSImage,
    NSMenu,
    NSMenuItem,
    NSObject,
    NSStatusBar,
    NSVariableStatusItemLength,
)

from .config import PROJECT_ROOT

log = logging.getLogger("liquid_whisper.menubar")

DICT_HTML = PROJECT_ROOT / "hud" / "dict.html"

# referencje globalne — bez nich ObjC zwolniłby ikonę i handler
_status_item = None
_handler = None
_dict_window = None


class DictApi:
    """Most JS ↔ Python dla okienka słowniczka (pywebview js_api)."""

    def __init__(self, app) -> None:
        self._app = app

    def get_data(self):
        from . import dictionary

        terms, corrections = dictionary.load()
        return {
            "terms": terms,
            "corrections": corrections,
            "suggestions": self._app.suggestions.pending(),
        }

    def add_term(self, term):
        from . import dictionary

        dictionary.add_term(term)
        self._app.reload_dictionary()
        return self.get_data()

    def remove_term(self, term):
        from . import dictionary

        dictionary.remove_term(term)
        self._app.reload_dictionary()
        return self.get_data()

    def add_correction(self, wrong, correct):
        from . import dictionary

        dictionary.add_correction(wrong, correct)
        self._app.reload_dictionary()
        return self.get_data()

    def remove_correction(self, wrong):
        from . import dictionary

        dictionary.remove_correction(wrong)
        self._app.reload_dictionary()
        return self.get_data()

    def accept_suggestion(self, wrong, correct):
        from . import dictionary

        dictionary.add_correction(wrong, correct)
        self._app.suggestions.resolve(wrong, accepted=True)
        self._app.reload_dictionary()
        return self.get_data()

    def reject_suggestion(self, wrong):
        self._app.suggestions.resolve(wrong, accepted=False)
        return self.get_data()


def open_dictionary_window(app) -> None:
    """Otwiera (lub pokazuje) okienko słowniczka. Wołać spoza wątku głównego."""
    global _dict_window
    import webview

    if _dict_window is not None:
        try:
            _dict_window.show()
            return
        except Exception:
            _dict_window = None

    window = webview.create_window(
        "Liquid Whisper — słowniczek",
        DICT_HTML.as_uri(),
        width=440,
        height=560,
        on_top=True,
        js_api=DictApi(app),
    )
    _dict_window = window

    def _closed():
        global _dict_window
        _dict_window = None

    window.events.closed += _closed


class _MenuHandler(NSObject):
    def openDictionary_(self, sender):  # noqa: N802 (konwencja selektorów ObjC)
        # create_window pywebview nie może być wołane z wątku głównego
        threading.Thread(target=open_dictionary_window, args=(self.app,), daemon=True).start()

    def quitApp_(self, sender):  # noqa: N802
        NSApplication.sharedApplication().terminate_(None)


def create_status_item(app) -> None:
    """Tworzy ikonę w pasku menu. MUSI być wołane na wątku głównym."""
    global _status_item, _handler
    bar = NSStatusBar.systemStatusBar()
    _status_item = bar.statusItemWithLength_(NSVariableStatusItemLength)

    icon = NSImage.imageWithSystemSymbolName_accessibilityDescription_("drop.fill", "Liquid Whisper")
    if icon is not None:
        icon.setTemplate_(True)
        _status_item.button().setImage_(icon)
    else:
        _status_item.button().setTitle_("💧")

    _handler = _MenuHandler.alloc().init()
    _handler.app = app

    menu = NSMenu.alloc().init()
    item_dict = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Słowniczek…", "openDictionary:", ""
    )
    item_dict.setTarget_(_handler)
    menu.addItem_(item_dict)
    menu.addItem_(NSMenuItem.separatorItem())
    item_quit = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Zakończ Liquid Whisper", "quitApp:", "q"
    )
    item_quit.setTarget_(_handler)
    menu.addItem_(item_quit)
    _status_item.setMenu_(menu)
    log.info("ikona w pasku menu aktywna")
