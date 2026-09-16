"""Samouczenie słowniczka: różnice surowy → oczyszczony jako propozycje poprawek.

Po każdym dyktandzie porównujemy transkrypt Whispera z wyjściem cleanupu.
Zamienione krótkie frazy (podobne, ale nie identyczne) to kandydaci na wpisy
„usłyszane → poprawne". Użytkownik akceptuje/odrzuca je w okienku słowniczka.
"""

from __future__ import annotations

import json
import re
import threading
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from .config import DATA_DIR

STATE_PATH = DATA_DIR / "suggestions.json"

_WORD_RE = re.compile(r"[\w'-]+")


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _fold(text: str) -> str:
    """Bez diakrytyków i myślników — do odsiania poprawek czysto ortograficznych."""
    norm = unicodedata.normalize("NFKD", text.replace("ł", "l").replace("-", " "))
    return "".join(c for c in norm if not unicodedata.combining(c))


def extract_pairs(raw: str, cleaned: str) -> list[tuple[str, str]]:
    a, b = _tokens(raw), _tokens(cleaned)
    pairs: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "replace" or i2 - i1 > 3 or j2 - j1 > 3:
            continue
        wrong, correct = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if len(wrong) < 3 or len(correct) < 3:
            continue
        if _fold(wrong) == _fold(correct):
            continue  # tylko diakrytyki/łącznik — korekta ortografii, nie termin
        if SequenceMatcher(None, wrong, correct).ratio() < 0.4:
            continue  # zupełnie różne — przeredagowanie, nie poprawka terminu
        pairs.append((wrong, correct))
    return pairs


class SuggestionStore:
    """Trwały magazyn propozycji: pending (z licznikiem) i odrzucone."""

    def __init__(self, path: Path = STATE_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict = {"pending": {}, "rejected": []}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def record(self, pairs: list[tuple[str, str]], known_corrections: dict[str, str]) -> None:
        with self._lock:
            changed = False
            for wrong, correct in pairs:
                if wrong in known_corrections or wrong in self._data["rejected"]:
                    continue
                entry = self._data["pending"].setdefault(wrong, {"correct": correct, "count": 0})
                entry["correct"] = correct
                entry["count"] += 1
                changed = True
            if changed:
                self._save()

    def pending(self) -> list[dict]:
        with self._lock:
            items = [
                {"wrong": w, "correct": e["correct"], "count": e["count"]}
                for w, e in self._data["pending"].items()
            ]
        return sorted(items, key=lambda x: -x["count"])

    def resolve(self, wrong: str, accepted: bool) -> None:
        with self._lock:
            self._data["pending"].pop(wrong, None)
            if not accepted and wrong not in self._data["rejected"]:
                self._data["rejected"].append(wrong)
            self._save()
