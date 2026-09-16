# AGENTS.md — instrukcja dla agentów AI

Ten plik prowadzi agenta AI (Claude Code, Codex, Cursor itp.) przez przygotowanie
Liquid Whisper do działania na komputerze użytkownika oraz przez pracę nad kodem.

## Czym jest ta aplikacja

Lokalne narzędzie do dyktowania na macOS (klon Wispr Flow) dla języka polskiego
z angielskimi wtrąceniami IT. Pipeline: hotkey (push-to-talk) → nagranie z mikrofonu →
transkrypcja Whisper large-v3-turbo (mlx-whisper, MLX) → cleanup lokalnym LLM przez
Ollama (usuwanie „yyy", interpunkcja, naprawa fonetycznie zniekształconych terminów
ze słowniczka) → wklejenie w aktywne pole przez schowek + syntetyczne ⌘V.
Wszystko w 100% lokalnie, bez API i chmury.

## Wymagania sprzętowe — sprawdź NAJPIERW

- **macOS na Apple Silicon** (M1 lub nowszy) — twarde wymaganie, mlx-whisper używa
  frameworku MLX. Sprawdź: `uname -m` musi zwrócić `arm64`.
- **Homebrew** — sprawdź: `brew --version`. Jeśli brak, poproś użytkownika o instalację
  (wymaga hasła administratora).
- ~6 GB dysku na modele (Whisper ~1,6 GB + gemma3:4b ~3,3 GB), ~8 GB wolnego RAM w pracy.

Jeśli platforma się nie zgadza (Intel Mac, Linux, Windows) — zatrzymaj się i powiedz
o tym użytkownikowi; aplikacja nie zadziała.

## Setup krok po kroku

Wykonuj z katalogu głównego repozytorium:

```bash
# 1. Narzędzia systemowe
brew install python ffmpeg node ollama

# 2. Serwer Ollama (musi działać w tle)
brew services start ollama      # alternatywa: open -a Ollama
# weryfikacja (odczekaj kilka sekund):
curl -s http://localhost:11434/api/version

# 3. Zależności Pythona
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Model LLM do cleanupu (~3,3 GB, może potrwać kilka minut)
ollama pull gemma3:4b

# 5. Bundle HUD (React + metal-fx)
cd hud && npm install && npm run build && cd ..

# 6. Model Whispera (~1,6 GB z Hugging Face) — pobierze się przy pierwszym użyciu;
# żeby pobrać z góry i zweryfikować transkrypcję:
.venv/bin/python -c "
from liquid_whisper.asr import Transcriber
t = Transcriber(); t.warmup(); print('ASR OK')
"

# 7. Build natywnej aplikacji macOS
./scripts/make_app.sh
```

Uruchomienie: `open "Liquid Whisper.app"` (zalecane) albo
`.venv/bin/python -m liquid_whisper` (dev; `--no-hud` = tryb headless).

## Uprawnienia macOS — tego NIE zrobisz za użytkownika

Przy pierwszym starcie aplikacja sama poprosi o uprawnienia systemowymi monitami.
Poinstruuj użytkownika, że musi zatwierdzić w System Settings → Privacy & Security:

1. **Microphone** — nagrywanie dyktand.
2. **Input Monitoring** — globalny nasłuch hotkeya (CGEventTap).
3. **Accessibility** — syntetyczne ⌘V wklejające tekst.

Uprawnienia dostaje ten proces, który uruchamia program: `Liquid Whisper.app` przy
starcie przez `open`, aplikacja terminala przy starcie z konsoli. **Po nadaniu
uprawnień aplikację trzeba uruchomić ponownie.** Objawy braków opisuje tabelka
w README (sekcja „Uprawnienia macOS").

## Weryfikacja, że działa

1. `curl -s http://localhost:11434/api/version` — Ollama odpowiada.
2. Krok 6 z setupu wypisał `ASR OK` — Whisper pobrany i działa.
3. Test bez uprawnień systemowych: `.venv/bin/python -m liquid_whisper.cli record 5`
   — nagrywa 5 s z mikrofonu, wypisuje transkrypt, kopiuje go do schowka
   (wymaga tylko zgody na mikrofon).
4. Pełny test: uruchom aplikację, poproś użytkownika, żeby kliknął w dowolne pole
   tekstowe, przytrzymał **prawy Ctrl**, powiedział zdanie i puścił — po ~2–3 s
   oczyszczony tekst powinien się wkleić.

Logi aplikacji (start przez `open`): `~/Library/Logs/LiquidWhisper.log`.

## Jak się z niej korzysta — wytłumacz użytkownikowi

- **Krótkie dyktando**: przytrzymaj prawy Ctrl, mów, puść. Tekst wklei się w aktywne pole.
- **Długie dyktando**: dwuklik prawego Ctrl włącza nagrywanie ciągłe; pojedyncze
  kliknięcie je kończy. Pojedyncze przypadkowe kliknięcie jest ignorowane.
- **Pasek menu** (ikona kropli) → **Słowniczek…**: akceptowanie/odrzucanie propozycji
  poprawek z dyktand oraz ręczna edycja terminów i poprawek.
- **Pasek menu → Ustawienia…**: zmiana przycisku nagrywania, wybór modelu cleanup
  spośród zainstalowanych w Ollamie i edycja promptu systemowego — wszystko działa
  od razu, bez restartu.
- **Konfiguracja plikowa**: `~/Library/Application Support/LiquidWhisper/config.toml`
  — ręczne zmiany wymagają restartu aplikacji (okno ustawień nie).

## Architektura i mapa repozytorium

```
liquid_whisper/         pakiet Pythona (rdzeń)
  app.py                maszyna stanów push-to-talk/toggle, orkiestracja pipeline'u
  audio.py              nagrywanie (sounddevice), detekcja mowy
  asr.py                transkrypcja mlx-whisper (language="pl" wymuszone)
  cleanup.py            cleanup przez Ollama /api/chat, prompt ze słowniczkiem
  paste.py              schowek + syntetyczne ⌘V (CGEvent)
  hotkey.py             globalny nasłuch klawisza (CGEventTap, Quartz)
  hud.py                overlay pywebview renderujący hud/dist
  menubar.py            ikona w pasku menu (AppKit) + okna słowniczka (hud/dict.html)
                        i ustawień (hud/settings.html)
  dictionary.py         odczyt/zapis sekcji [dictionary] w configu użytkownika
  settings.py           punktowa edycja kluczy configu + własny prompt cleanupu
  learn.py              propozycje słowniczka z diffu surowy→oczyszczony
  config.py             ścieżki + wczytywanie configu (patrz niżej)
  cli.py                narzędzia: transkrypcja pliku / nagranie testowe
hud/                    HUD w React + metal-fx (Vite); build: npm run build → hud/dist
scripts/make_app.sh     buduje "Liquid Whisper.app" (bundle opakowujący venv)
scripts/compare_cleanup.py  benchmark modeli cleanup na nagraniach użytkownika
config.default.toml     szablon konfiguracji (jedyna konfiguracja w repo)
brief.md                brief projektu — decyzje i research
```

**Prywatne dane użytkownika NIE mieszkają w repo**, tylko w
`~/Library/Application Support/LiquidWhisper/`:

- `config.toml` — tworzony przy pierwszym starcie z `config.default.toml`
  (kopiuje `liquid_whisper/config.py:ensure_user_config`); potem edytowany przez
  użytkownika oraz okna słowniczka i ustawień.
- `cleanup_prompt.txt` — własny prompt systemowy cleanupu; brak pliku = domyślny
  prompt z `cleanup.py` (reset w oknie ustawień kasuje plik).
- `suggestions.json` — stan propozycji słowniczka.
- `recordings/` — nagrania testowe z `cli.py record`.

Nigdy nie commituj tych plików ani ich treści (słowniczek zawiera prywatny żargon
użytkownika, nagrania to jego głos).

## Konwencje projektu

- Język projektu to **polski**: komentarze, docstringi, logi, commit messages.
- Brak frameworka testów — weryfikacja przez CLI i realne dyktanda (sekcja wyżej).
- Zmiany w kodzie Pythona nie wymagają przebudowy bundle'a `.app` (opakowuje venv
  i kod z katalogu projektu); przebudowa (`./scripts/make_app.sh`) jest potrzebna
  tylko po przeniesieniu folderu projektu. Zmiany w `hud/src` wymagają `npm run build`.
- Callback event tapa hotkeya działa na głównym wątku i musi wracać natychmiast —
  akcje idą przez kolejkę do wątku roboczego (patrz `app.py`). Nie wołaj z niego
  blokujących rzeczy.
- Cleanup ma zawsze fallback do surowego transkryptu — dyktowanie musi działać nawet
  bez Ollamy.
