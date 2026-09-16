# Liquid Whisper

Lokalny klon Wispr Flow na macOS: przytrzymaj hotkey (prawy Ctrl), powiedz coś po polsku
(z angielskimi wtrąceniami), puść — oczyszczony tekst wskakuje w aktywne pole tekstowe.
Na dłuższe dyktanda: **dwuklik** hotkeya włącza nagrywanie ciągłe, pojedyncze
kliknięcie je kończy. Pojedyncze przypadkowe kliknięcie jest ignorowane.
Wszystko działa lokalnie: Whisper large-v3-turbo (mlx-whisper) + mały LLM przez Ollama.
W trakcie dyktowania na dole ekranu widać liquid-metalowy HUD (React + metal-fx w pywebview).

Szczegóły projektu: [BRIEF.md](BRIEF.md).

## Uruchomienie

Jako natywna aplikacja macOS (zalecane — uprawnienia przypięte do aplikacji):

```bash
./scripts/make_app.sh && open "Liquid Whisper.app"
```

Bundle opakowuje venv projektu, więc po zmianie kodu nie trzeba go przebudowywać
(tylko po przeniesieniu folderu projektu). Logi: `~/Library/Logs/LiquidWhisper.log`.
Zamykanie: ikona w Docku → Wymuś koniec (⌘⌥Esc) albo `pkill -f "liquid_whisper"`.

Z terminala: `.venv/bin/python -m liquid_whisper` (tryb bez HUD: `--no-hud`).

## Setup od zera

Wymagania: macOS (Apple Silicon), Homebrew.

```bash
# 1. Narzędzia systemowe
brew install python ffmpeg node ollama
brew services start ollama   # albo uruchom aplikację Ollama

# 2. Zależności Pythona
python3 -m venv .venv
.venv/bin/pip install mlx-whisper sounddevice pywebview \
    pyobjc-framework-Quartz pyobjc-framework-Cocoa pyobjc-framework-ApplicationServices

# 3. Model cleanup (dobrany w etapie 3 — patrz config.toml [cleanup].model)
ollama pull gemma3:4b

# 4. Bundle HUD
cd hud && npm install && npm run build && cd ..

# 5. Start (model Whispera ~1,6 GB ściągnie się przy pierwszym uruchomieniu)
.venv/bin/python -m liquid_whisper
```

Konfiguracja (hotkey, modele, słowniczek terminów): [config.toml](config.toml).

## Pasek menu i słowniczek

Aplikacja pokazuje ikonę kropli w pasku menu. Menu → **Słowniczek…** otwiera okienko z:

- **Propozycjami z dyktand** — pipeline porównuje surowy transkrypt z oczyszczonym
  i zbiera pary „usłyszane → poprawione"; jednym kliknięciem akceptujesz je do
  słowniczka (✓) albo odrzucasz (✕). Stan propozycji: `suggestions.json`.
- **Poprawkami** (usłyszane → poprawne) i **terminami** — edytowalne ręcznie,
  zapisywane w `config.toml`, używane w prompcie cleanupu od następnego dyktanda.

Menu → **Zakończ Liquid Whisper** zamyka aplikację.

## Uprawnienia macOS (troubleshooting)

Uprawnienia nadaje się w System Settings → Privacy & Security temu, co uruchamia
program: **Liquid Whisper.app** (start przez `open`) albo aplikacji terminala
(start przez `python -m liquid_whisper`):

| Uprawnienie | Po co | Objaw braku |
|---|---|---|
| **Accessibility** | syntetyczne ⌘V (wklejanie) | log: „Brak uprawnień Accessibility"; nic się nie wkleja |
| **Input Monitoring** | globalny nasłuch hotkeya (CGEventTap) | hotkey milczy / „nie można utworzyć event tapu" |
| **Microphone** | nagrywanie | cisza w transkrypcie (RMS ~0) |

Po nadaniu uprawnień **zrestartuj terminal** — działający proces ich nie doczyta.

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
.venv/bin/python scripts/compare_cleanup.py            # porównanie modeli cleanup na recordings/
```
