"""Zapis ustawień: pojedyncze klucze w config.toml + własny prompt cleanupu.

Edycja configu podmienia wyłącznie wskazany klucz w jego sekcji — komentarze
i reszta pliku zostają nietknięte (ten sam duch co dictionary.py dla
[dictionary]). Własny prompt mieszka w osobnym pliku tekstowym, bo
wieloliniowy string w ręcznie edytowanym TOML-u byłby kruchy; brak pliku
= domyślny prompt z cleanup.py.
"""

from __future__ import annotations

import json
import re
import threading

from .cleanup import SYSTEM_PROMPT
from .config import DATA_DIR, ensure_user_config

PROMPT_PATH = DATA_DIR / "cleanup_prompt.txt"

_lock = threading.Lock()


def _quote(s: str) -> str:
    # basic string TOML-a ma dla typowych wartości tę samą składnię co JSON
    return json.dumps(s, ensure_ascii=False)


def set_config_value(section: str, key: str, value: str) -> None:
    """Ustawia klucz w danej sekcji configu użytkownika, tworząc sekcję w razie braku."""
    with _lock:
        path = ensure_user_config()
        text = path.read_text(encoding="utf-8")
        rendered = f"{key} = {_quote(value)}"
        sec_re = re.compile(rf"(?ms)^\[{re.escape(section)}\]\n.*?(?=^\[|\Z)")
        m = sec_re.search(text)
        if m is None:
            text = text.rstrip("\n") + f"\n\n[{section}]\n{rendered}\n"
        else:
            block = m.group(0)
            key_re = re.compile(rf"(?m)^{re.escape(key)}\s*=.*$")
            if key_re.search(block):
                block = key_re.sub(lambda _: rendered, block, count=1)
            else:
                nl = block.index("\n") + 1
                block = block[:nl] + rendered + "\n" + block[nl:]
            text = text[: m.start()] + block + text[m.end() :]
        path.write_text(text, encoding="utf-8")


def load_prompt() -> str:
    """Prompt cleanupu: własny użytkownika, a gdy go brak — domyślny."""
    try:
        custom = PROMPT_PATH.read_text(encoding="utf-8").strip()
        if custom:
            return custom
    except OSError:
        pass
    return SYSTEM_PROMPT


def save_prompt(text: str) -> str:
    """Zapisuje własny prompt i zwraca obowiązujący.

    Tekst pusty albo identyczny z domyślnym kasuje plik — użytkownik wraca
    na domyślny prompt i dostaje jego przyszłe ulepszenia z aktualizacjami.
    """
    text = text.strip()
    if not text or text == SYSTEM_PROMPT.strip():
        PROMPT_PATH.unlink(missing_ok=True)
        return SYSTEM_PROMPT
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROMPT_PATH.write_text(text + "\n", encoding="utf-8")
    return text
