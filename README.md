# Liquid Whisper

Lokalny klon Wispr Flow na macOS: przytrzymaj hotkey (prawy ⌥), powiedz coś po polsku
(z angielskimi wtrąceniami), puść — oczyszczony tekst wskakuje w aktywne pole tekstowe.
Wszystko działa lokalnie: Whisper large-v3-turbo (mlx-whisper) + mały LLM przez Ollama.
W trakcie dyktowania na dole ekranu widać liquid-metalowy HUD (React + metal-fx w pywebview).

Szczegóły projektu: [BRIEF.md](BRIEF.md).

## Uruchomienie

```bash
.venv/bin/python -m liquid_whisper
```

Tryb bez HUD: `.venv/bin/python -m liquid_whisper --no-hud`.

## Setup od zera

Wymagania: macOS (Apple Silicon), Homebrew.

```bash
# 1. Narzędzia systemowe
brew install python ffmpeg node ollama
brew services start ollama   # albo uruchom aplikację Ollama

# 2. Zależności Pythona
python3 -m venv .venv
.venv/bin/pip install mlx-whisper sounddevice pynput pywebview \
    pyobjc-framework-Quartz pyobjc-framework-Cocoa pyobjc-framework-ApplicationServices

# 3. Model cleanup (dobrany w etapie 3 — patrz config.toml [cleanup].model)
ollama pull qwen3:4b-instruct

# 4. Bundle HUD
cd hud && npm install && npm run build && cd ..

# 5. Start (model Whispera ~1,6 GB ściągnie się przy pierwszym uruchomieniu)
.venv/bin/python -m liquid_whisper
```

Konfiguracja (hotkey, modele, słowniczek terminów): [config.toml](config.toml).

## Uprawnienia macOS (troubleshooting)

Wszystkie uprawnienia nadaje się **aplikacji terminala**, z której uruchamiasz program
(Terminal/iTerm2), w System Settings → Privacy & Security:

| Uprawnienie | Po co | Objaw braku |
|---|---|---|
| **Accessibility** | nasłuch hotkeya + syntetyczne ⌘V | log: „Brak uprawnień Accessibility"; hotkey milczy, nic się nie wkleja |
| **Input Monitoring** | nasłuch klawiatury (pynput) | log: „This process is not trusted" |
| **Microphone** | nagrywanie | cisza w transkrypcie (RMS ~0) |

Po nadaniu uprawnień **zrestartuj terminal** — działający proces ich nie doczyta.

Inne typowe problemy:

- **Wkleja się stary tekst / nic** — aktywne pole musi obsługiwać ⌘V; kliknij w pole przed dyktowaniem.
- **Cleanup nie działa** — sprawdź `curl http://localhost:11434/api/version`; przy braku
  odpowiedzi uruchom Ollama. Pipeline wtedy i tak wkleja surowy transkrypt (fallback).
- **Zły mikrofon** — domyślne wejście zmienisz w System Settings → Sound → Input.
- **HUD się nie pokazuje** — zbuduj bundle: `cd hud && npm run build`; aplikacja bez niego
  przechodzi w tryb headless (dyktowanie działa dalej).

## Narzędzia deweloperskie

```bash
.venv/bin/python -m liquid_whisper.cli file plik.wav   # transkrypcja pliku
.venv/bin/python -m liquid_whisper.cli record 15       # nagraj 15 s, transkrypt do schowka
.venv/bin/python scripts/compare_cleanup.py            # porównanie modeli cleanup na recordings/
```
