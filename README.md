# Liquid Whisper

Lokalny klon Wispr Flow na macOS dla języka polskiego: przytrzymaj hotkey (domyślnie
prawy Ctrl), powiedz coś po polsku (z angielskimi wtrąceniami IT), puść — oczyszczony
tekst wskakuje w aktywne pole tekstowe dowolnej aplikacji. Wszystko działa w 100%
lokalnie i za darmo: Whisper large-v3-turbo (mlx-whisper) + mały LLM przez Ollama.
Zero chmury, zero subskrypcji, głos nie opuszcza komputera.

> **English note:** Liquid Whisper is a fully local push-to-talk dictation tool for
> macOS (Apple Silicon), tuned for **Polish** speech with English tech jargon mixed in.
> The UI, prompts and docs are in Polish.

- **Push-to-talk** — przytrzymaj hotkey, mów, puść.
- **Nagrywanie ciągłe** — dwuklik hotkeya zaczyna, pojedyncze kliknięcie kończy
  (pojedyncze przypadkowe kliknięcie jest ignorowane).
- **Cleanup przez LLM** — lokalny model (Ollama) usuwa „yyy/eee", poprawia interpunkcję
  i fonetycznie zniekształcone angielskie terminy („co derewie" → „code review").
- **Samouczący się słowniczek** — pipeline porównuje surowy transkrypt z oczyszczonym
  i proponuje poprawki, które akceptujesz jednym kliknięciem.
- **Liquid-metalowy HUD** — chromowany wskaźnik nagrywania na dole ekranu
  (React + [metal-fx](https://github.com/Jakubantalik/metal-fx) w pywebview).

Historia i decyzje projektowe: [brief.md](brief.md).

## Instalacja z pomocą agenta AI (zalecane)

Sklonuj repozytorium, otwórz je w Claude Code (lub innym agencie AI) i poproś:

> „Przygotuj mi tę aplikację do działania zgodnie z AGENTS.md — zainstaluj zależności,
> pobierz modele, zbuduj aplikację i wytłumacz, jak z niej korzystać."

Agent znajdzie kompletną instrukcję w [AGENTS.md](AGENTS.md).

## Instalacja ręczna

Wymagania: macOS na **Apple Silicon** (pipeline używa MLX), Homebrew, ~8 GB wolnego
RAM przy pracy (ASR ~1,5 GB + LLM ~4 GB), ~6 GB dysku na modele.

```bash
# 1. Narzędzia systemowe
brew install python ffmpeg node ollama
brew services start ollama   # albo uruchom aplikację Ollama

# 2. Zależności Pythona
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Model cleanup (LLM czyszczący transkrypt, ~3,3 GB)
ollama pull gemma3:4b

# 4. Bundle HUD
cd hud && npm install && npm run build && cd ..

# 5. Start (model Whispera ~1,6 GB ściągnie się z Hugging Face przy pierwszym uruchomieniu)
.venv/bin/python -m liquid_whisper
```

## Uruchomienie

Jako natywna aplikacja macOS (zalecane — uprawnienia przypięte do aplikacji):

```bash
./scripts/make_app.sh && open "Liquid Whisper.app"
```

Bundle opakowuje venv projektu, więc po zmianie kodu nie trzeba go przebudowywać
(tylko po przeniesieniu folderu projektu). Logi: `~/Library/Logs/LiquidWhisper.log`.
Zamykanie: menu → **Zakończ Liquid Whisper** albo `pkill -f "liquid_whisper"`.

Z terminala: `.venv/bin/python -m liquid_whisper` (tryb bez HUD: `--no-hud`).

## Konfiguracja

Menu (ikona kropli) → **Ustawienia…** otwiera okienko, w którym zmienisz na żywo
(bez restartu aplikacji):

- **przycisk nagrywania** — prawy/lewy Ctrl, Option, Command, Shift albo F13–F19,
- **model cleanup** — lista pokazuje modele zainstalowane w Ollamie,
- **prompt cleanupu** — pełna treść promptu systemowego (znaczniki `{dictionary}`
  i `{corrections}` są podmieniane na słowniczek); jeden klik przywraca domyślny.

Prywatne ustawienia mieszkają **poza repozytorium** — w
`~/Library/Application Support/LiquidWhisper/`: `config.toml` (powstaje przy pierwszym
uruchomieniu z szablonu [config.default.toml](config.default.toml)), własny prompt
(`cleanup_prompt.txt`), propozycje słowniczka (`suggestions.json`) i nagrania testowe
(`recordings/`).

## Pasek menu i słowniczek

Aplikacja pokazuje ikonę kropli w pasku menu. Menu → **Słowniczek…** otwiera okienko z:

- **Propozycjami z dyktand** — pipeline porównuje surowy transkrypt z oczyszczonym
  i zbiera pary „usłyszane → poprawione"; jednym kliknięciem akceptujesz je do
  słowniczka (✓) albo odrzucasz (✕).
- **Poprawkami** (usłyszane → poprawne) i **terminami** — edytowalne ręcznie,
  używane w prompcie cleanupu od następnego dyktanda.

## Uprawnienia macOS (troubleshooting)

Uprawnienia nadaje się w System Settings → Privacy & Security temu, co uruchamia
program: **Liquid Whisper.app** (start przez `open`) albo aplikacji terminala
(start przez `python -m liquid_whisper`):

| Uprawnienie | Po co | Objaw braku |
|---|---|---|
| **Accessibility** | syntetyczne ⌘V (wklejanie) | log: „Brak uprawnień Accessibility"; nic się nie wkleja |
| **Input Monitoring** | globalny nasłuch hotkeya (CGEventTap) | hotkey milczy / „nie można utworzyć event tapu" |
| **Microphone** | nagrywanie | cisza w transkrypcie (RMS ~0) |

Po nadaniu uprawnień **uruchom aplikację ponownie** — działający proces ich nie doczyta.

Inne typowe problemy:

- **Wkleja się stary tekst / nic** — aktywne pole musi obsługiwać ⌘V; kliknij w pole przed dyktowaniem.
- **Cleanup nie działa** — aplikacja przy starcie sama uruchamia Ollamę, jeśli ta nie
  działa (`open -g -a Ollama`). Gdyby i to zawiodło (log: „Ollama nie wstała"), uruchom ją
  ręcznie; pipeline w międzyczasie wkleja surowy transkrypt (fallback).
- **Zły mikrofon** — domyślne wejście zmienisz w System Settings → Sound → Input.
- **HUD się nie pokazuje** — zbuduj bundle: `cd hud && npm run build`; aplikacja bez niego
  przechodzi w tryb headless (dyktowanie działa dalej).

## Narzędzia deweloperskie

```bash
.venv/bin/python -m liquid_whisper.cli file plik.wav   # transkrypcja pliku
.venv/bin/python -m liquid_whisper.cli record 15       # nagraj 15 s, transkrypt do schowka
.venv/bin/python scripts/compare_cleanup.py            # porównanie modeli cleanup na nagraniach
```

## Licencja

[MIT](LICENSE).
