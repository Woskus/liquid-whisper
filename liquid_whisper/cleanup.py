"""Czyszczenie transkryptu lokalnym LLM przez Ollama.

Zadanie: usunąć wypełniacze („yyy", „eee"), poprawić interpunkcję i fonetyczne
zniekształcenia angielskich terminów (słowniczek), nie zmieniać sensu ani stylu.
"""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger("liquid_whisper.cleanup")

OLLAMA_URL = "http://localhost:11434"

SYSTEM_PROMPT = """Jesteś korektorem transkryptów z dyktowania po polsku z angielskimi wtrąceniami IT.

Popraw podany transkrypt według zasad:
1. Usuń wypełniacze mowy: „yyy", „eee", „hmm", „no więc" na początku zdania itp.
2. Popraw interpunkcję, wielkie litery i oczywiste literówki.
3. Napraw fonetycznie zniekształcone angielskie terminy (np. „co derewie" → „code review", „bildzie" → „buildzie"). Pomocniczy słowniczek terminów, które mogły zostać zniekształcone:
{dictionary}
Znane błędne zapisy i ich poprawki (stosuj zawsze, z zachowaniem odmiany):
{corrections}
4. NIE zmieniaj sensu, stylu ani szyku wypowiedzi. NIE dodawaj niczego od siebie. NIE odpowiadaj na treść transkryptu.
5. Zachowaj naturalną polską odmianę terminów (np. „w backlogu", „na buildzie").

Zwróć WYŁĄCZNIE poprawiony tekst, bez komentarzy i cudzysłowów."""


class Cleaner:
    def __init__(
        self,
        model: str,
        dictionary: list[str] | None = None,
        corrections: dict[str, str] | None = None,
        min_words: int = 0,
        timeout_s: float = 10.0,
        keep_alive: str = "60m",
    ) -> None:
        self.model = model
        self.dictionary = dictionary or []
        self.corrections = corrections or {}
        self.min_words = min_words
        self.timeout_s = timeout_s
        self.keep_alive = keep_alive
        self._client = httpx.Client(base_url=OLLAMA_URL, timeout=timeout_s)

    def _system_prompt(self) -> str:
        terms = ", ".join(self.dictionary) if self.dictionary else "(brak)"
        pairs = (
            "\n".join(f"- „{w}” → „{c}”" for w, c in self.corrections.items())
            if self.corrections
            else "(brak)"
        )
        return SYSTEM_PROMPT.format(dictionary=terms, corrections=pairs)

    def ensure_server(self, wait_s: float = 20.0) -> bool:
        """Jeśli Ollama nie odpowiada — uruchamia aplikację Ollama w tle i czeka aż wstanie."""
        import subprocess
        import time

        try:
            self._client.get("/api/version", timeout=1.5)
            return True
        except httpx.HTTPError:
            pass
        log.info("Ollama nie działa — uruchamiam w tle...")
        try:
            subprocess.run(["open", "-g", "-a", "Ollama"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.warning("nie udało się uruchomić aplikacji Ollama — cleanup będzie pomijany")
            return False
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            try:
                self._client.get("/api/version", timeout=1.5)
                log.info("Ollama wystartowała")
                return True
            except httpx.HTTPError:
                time.sleep(0.5)
        log.warning("Ollama nie wstała w %.0f s — cleanup będzie pomijany do skutku", wait_s)
        return False

    def warmup(self) -> None:
        """Ładuje model do RAM na starcie, żeby pierwsze dyktando nie płaciło za load."""
        self.ensure_server()
        try:
            self._client.post(
                "/api/generate",
                json={"model": self.model, "keep_alive": self.keep_alive},
                timeout=120.0,
            ).raise_for_status()
            log.info("model cleanup %s załadowany", self.model)
        except httpx.HTTPError as e:
            log.warning("warmup cleanup nie powiódł się (%s) — pierwsze dyktando będzie wolniejsze", e)

    def clean(self, text: str) -> str:
        """Zwraca oczyszczony tekst; przy błędzie/timeout — surowy (dyktowanie ma działać zawsze)."""
        if self.min_words and len(text.split()) < self.min_words:
            log.info("krótkie dyktando (<%d słów) — pomijam cleanup", self.min_words)
            return text
        try:
            resp = self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self._system_prompt()},
                        {"role": "user", "content": text},
                    ],
                    "stream": False,
                    "think": False,
                    "keep_alive": self.keep_alive,
                    "options": {"temperature": 0.0},
                },
            )
            resp.raise_for_status()
            cleaned = resp.json()["message"]["content"].strip()
            if not cleaned:
                log.warning("cleanup zwrócił pusty tekst — używam surowego")
                return text
            return cleaned
        except httpx.HTTPError as e:
            log.warning("cleanup nieudany (%s) — wklejam surowy transkrypt", e)
            return text
