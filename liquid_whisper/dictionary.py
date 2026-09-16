"""Odczyt i zapis sekcji [dictionary] w konfiguracji użytkownika.

Zapis podmienia wyłącznie końcówkę pliku od nagłówka [dictionary] —
reszta configu (komentarze, inne sekcje) zostaje nietknięta.
"""

from __future__ import annotations

import threading
import tomllib

from .config import CONFIG_PATH, ensure_user_config

_lock = threading.Lock()


def load() -> tuple[list[str], dict[str, str]]:
    with open(ensure_user_config(), "rb") as f:
        raw = tomllib.load(f)
    d = raw.get("dictionary", {})
    return list(d.get("terms", [])), dict(d.get("corrections", {}))


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save(terms: list[str], corrections: dict[str, str]) -> None:
    with _lock:
        text = CONFIG_PATH.read_text(encoding="utf-8")
        idx = text.index("[dictionary]")
        lines = ["[dictionary]", "terms = ["]
        lines += [f"    {_quote(t)}," for t in terms]
        lines.append("]")
        if corrections:
            lines += ["", "# usłyszane -> poprawne (akceptowane propozycje trafiają tutaj)"]
            lines.append("[dictionary.corrections]")
            lines += [f"{_quote(w)} = {_quote(c)}" for w, c in corrections.items()]
        CONFIG_PATH.write_text(text[:idx] + "\n".join(lines) + "\n", encoding="utf-8")


def add_term(term: str) -> None:
    terms, corrections = load()
    term = term.strip()
    if term and term not in terms:
        terms.append(term)
        save(terms, corrections)


def remove_term(term: str) -> None:
    terms, corrections = load()
    if term in terms:
        terms.remove(term)
        save(terms, corrections)


def add_correction(wrong: str, correct: str) -> None:
    terms, corrections = load()
    wrong, correct = wrong.strip().lower(), correct.strip()
    if wrong and correct:
        corrections[wrong] = correct
        save(terms, corrections)


def remove_correction(wrong: str) -> None:
    terms, corrections = load()
    if wrong in corrections:
        del corrections[wrong]
        save(terms, corrections)
