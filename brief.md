# Liquid Whisper — lokalny klon Wispr Flow

> Brief projektu. Samowystarczalny — przeznaczony do rozpoczęcia pracy w nowej konwersacji, w osobnym folderze projektu. Powstał 2026-09-16 po sesji grillowania i researchu.

## Cel i problem

Własny, prywatny odpowiednik Wispr Flow działający w całości lokalnie na Macu: wciskam hotkey (push-to-talk), mówię po polsku lub angielsku (z typowymi dla IT wtrąceniami angielskimi w polskich zdaniach), a oczyszczony tekst wskakuje w aktywne pole tekstowe dowolnej aplikacji.

Za projektem stoją dwa motywy naraz:

1. **Realna potrzeba** — narzędzie do codziennego dyktowania, bez subskrypcji i bez wysyłania głosu do chmury.
2. **Nauka praktycznego AI engineeringu** — sklejenie działającego pipeline'u z gotowych klocków (ASR, lokalny LLM, integracja systemowa), nie badanie modeli od środka.

## Kluczowe założenia i granice

- **Wszystko lokalnie i za darmo**: wagi modeli z Hugging Face, zero API i chmury.
- **Latencja**: 2–3 s od puszczenia hotkeya do wklejonego tekstu jest akceptowalna.
- **Zakres**: narzędzie wyłącznie na własny użytek. Ma działać w podstawowych funkcjonalnościach — nie jest produktem. Cięższe funkcje (konfigurowalność, wiele trybów, dystrybucja) świadomie odpadają.
- **Odroczone świadomie**: tryb toggle (długie dyktanda), autostart, wielojęzyczny UI — dopiero po działającym MVP, jeśli w ogóle.

## Sprzęt

MacBook z **Apple M2 Max, 32 GB RAM** — zweryfikowane, że komfortowo udźwignie cały pipeline (ASR ~1,5 GB + LLM 4–5 GB RAM jednocześnie).

## Rekomendowany stack (wynik researchu)

### 1. ASR: Whisper large-v3-turbo przez `mlx-whisper`

- Whisper large-v3 ma dla polskiego WER ~4,7% na benchmarku FLEURS — najlepszy darmowy model do polskiego. Wersja **turbo** zachowuje ~99% jakości przy ~5× szybkości i ~1,5 GB RAM.
- **Odrzucone**: NVIDIA Parakeet v3 — szybszy, ale dla polskiego wyraźnie gorszy (WER 7,3% vs 4,7% na FLEURS).
- Implementacja: [`mlx-whisper`](https://pypi.org/project/mlx-whisper/) (framework MLX Apple'a) — ~2× szybszy od whisper.cpp na Apple Silicon, instalacja przez `pip install mlx-whisper`. Kilkunastosekundowe dyktando → ~1 s transkrypcji.
- Zawsze wymuszać `language="pl"` przy polskich dyktandach (patrz Ryzyka).

### 2. Czyszczenie tekstu: Ollama + mały LLM (dwa kandydaty do testu)

Zadanie: usunąć „yyy"/„eee", poprawić interpunkcję i literówki fonetyczne, nie zmieniać sensu ani stylu. Proste — model 4B wystarczy.

- **Kandydat A**: Qwen3 4B lub Gemma 3 4B (ogólne, szybkie, przyzwoity polski w prostej edycji).
- **Kandydat B**: [Bielik 4.5B v3 Instruct](https://ollama.com/SpeakLeash/bielik-4.5b-v3.0-instruct) (SpeakLeash) — polski model, dostępny wprost na Ollama.
- Decyzja po porównaniu obu na 5–10 własnych, realnych dyktandach.
- W prompcie czyszczącym trzymać **własny słowniczek terminów** (nazwy firmowe, żargon IT: „deployment", „backlog" itd.) do naprawiania fonetycznych zniekształceń — to ten sam trik co „dictionary" w Wispr Flow.

### 3. Rdzeń i integracja z macOS: Python

- **Globalny hotkey (push-to-talk)**: `pynput` — wymaga jednorazowego nadania uprawnień Accessibility terminalowi/interpreterowi (System Settings → Privacy & Security → Accessibility). Bez tego eventy klawiatury po cichu nie docierają.
- **Nagrywanie**: `sounddevice`, 16 kHz mono WAV.
- **Wstrzykiwanie tekstu**: schowek + symulacja ⌘V przez CGEvent (`pyobjc`) — standardowa technika, działa w każdej aplikacji.

### 4. UI: liquid metal (React + metal-fx w webview)

Design ma być mega futurystyczny, wzorowany na [metal.jakubantalik.com](https://metal.jakubantalik.com/) — czyli na bibliotece [`metal-fx`](https://github.com/Jakubantalik/metal-fx) ([npm](https://www.npmjs.com/package/metal-fx), MIT): animowany WebGL-owy efekt płynnego metalu dla komponentów React, presety chromatic/silver/gold, glow, odbicia reagujące na kursor.

Konsekwencja architektoniczna: metal-fx wymaga Reacta i WebGL, więc UI musi być webowe.

- **Rekomendacja**: rdzeń zostaje w Pythonie, UI jako **`pywebview`** — frameless, przezroczyste, always-on-top okno (WKWebView wspiera WebGL) renderujące zbudowany statycznie bundle React + metal-fx. Jeden proces, jeden język logiki, web tylko do wizualiów.
- Zakres UI w MVP: **pływający HUD** — chromowany pastylkowy wskaźnik nagrywania (idle / nagrywam / przetwarzam), pojawiający się przy wciśniętym hotkeyu. Osobne okno ustawień tylko jeśli będzie realnie potrzebne.
- **Fallback**, gdyby przezroczysty WebGL-owy overlay okazał się kapryśny: MVP z prostą ikoną w pasku menu (`rumps`), liquid metal HUD jako etap późniejszy. Nie blokować działającego dyktowania designem.
- Alternatywa odrzucona: Tauri/Electron — przenosi cały projekt na inny stack i mnoży złożoność nieproporcjonalnie do celu „ma działać".

## Główne ryzyko: mieszanie języków w jednym zdaniu

Whisper wybiera jeden język na okno audio (~30 s), więc polskie zdania z angielskimi wtrąceniami to jego najsłabszy punkt — angielskie terminy bywają „spolszczane" fonetycznie. Mitygacja dwuwarstwowa:

1. wymuszone `language="pl"` (angielskie terminy IT zwykle i tak przechodzą poprawnie),
2. słowniczek terminów w prompcie LLM-a czyszczącego, który naprawia zniekształcenia.

Drugie ryzyko: suma latencji (transkrypcja ~1 s + cleanup ~1–1,5 s) mieści się w budżecie 2–3 s, ale gdyby cleanup okazał się za wolny — fallback: czyścić tylko dłuższe dyktanda, krótkie wklejać surowe.

## Plan budowy

Kolejność zaprojektowana tak, żeby po każdym etapie mieć coś działającego.

1. **Etap 1 — rdzeń transkrypcji.** Najkrótszy możliwy skrypt: nagraj z mikrofonu → `mlx-whisper` (`language="pl"`) → tekst do schowka. **Punkt decyzyjny projektu**: tu weryfikuje się jakość polskiej transkrypcji na własnym głosie.
2. **Etap 2 — push-to-talk.** `pynput` + hotkey (np. prawy Option), uprawnienia Accessibility, wstrzykiwanie przez ⌘V. Po tym etapie narzędzie jest już używalne na surowo.
3. **Etap 3 — cleanup.** Ollama, porównanie Qwen3/Gemma 3 4B vs Bielik 4.5B na własnych dyktandach, prompt z regułami i słowniczkiem. Zwycięzca wpięty między transkrypcję a wklejenie. Pomiar latencji całości.
4. **Etap 4 — liquid metal HUD.** Mały bundle React + `metal-fx` (preset chromatic), `pywebview` jako frameless/transparent/always-on-top overlay ze stanami idle → nagrywam → przetwarzam.
5. **Etap 5 (opcjonalny) — drobiazgi.** Dźwięk start/stop, autostart jako LaunchAgent, tryb toggle do długich dyktand.

## Ściągi architektoniczne (open source do podglądania)

- [WhisperDictation](https://github.com/sam-pop/WhisperDictation) — macOS, whisper.cpp + Metal, push-to-talk i toggle.
- [VoiceInk](https://github.com/Beingpax/VoiceInk) — najdojrzalszy open-source'owy odpowiednik Wispr Flow na macOS (GPL v3, Swift).
- [laptop-dictation](https://github.com/CasterlyGit/laptop-dictation) — minimalny pythonowy pipeline push-to-talk → whisper → schowek.

Gdyby projekt kiedyś umarł — VoiceInk jest planem B jako gotowe narzędzie.

## Źródła researchu

- [Whisper large-v3-turbo — benchmark na Macu](https://whispernotes.app/blog/introducing-whisper-large-v3-turbo)
- [mlx-whisper vs whisper.cpp — benchmark](https://notes.billmill.org/dev_blog/2026/01/updated_my_mlx_whisper_vs._whisper.cpp_benchmark.html)
- [Canary-1B-v2 & Parakeet-TDT-0.6B-v3 — wyniki FLEURS, w tym polski (arXiv)](https://arxiv.org/pdf/2509.14128)
- [Bielik 4.5B v3 Instruct na Ollama](https://ollama.com/SpeakLeash/bielik-4.5b-v3.0-instruct)
- [Whisper a code-switching — dyskusja](https://github.com/openai/whisper/discussions/2009)
- [metal-fx — GitHub](https://github.com/Jakubantalik/metal-fx)
