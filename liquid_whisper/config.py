"""Wczytywanie konfiguracji z config.toml.

Prywatne dane użytkownika (hotkey, słowniczek, poprawki, propozycje, nagrania)
mieszkają poza repozytorium — w ~/Library/Application Support/LiquidWhisper/.
Przy pierwszym uruchomieniu kopiowany jest tam szablon config.default.toml.
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path.home() / "Library" / "Application Support" / "LiquidWhisper"
CONFIG_PATH = DATA_DIR / "config.toml"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.default.toml"


def ensure_user_config() -> Path:
    """Zakłada katalog danych i kopiuje szablon konfiguracji przy pierwszym starcie."""
    if not CONFIG_PATH.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
    return CONFIG_PATH


@dataclass
class Config:
    hotkey: str = "alt_r"
    sample_rate: int = 16000
    channels: int = 1
    asr_model: str = "mlx-community/whisper-large-v3-turbo"
    language: str = "pl"
    cleanup_enabled: bool = True
    cleanup_model: str = "gemma3:4b"
    cleanup_min_words: int = 0
    cleanup_timeout_s: float = 10.0
    dictionary: list[str] = field(default_factory=list)
    corrections: dict[str, str] = field(default_factory=dict)


def load_config(path: Path | None = None) -> Config:
    if path is None:
        path = ensure_user_config()
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return Config(
        hotkey=raw.get("hotkey", {}).get("key", "alt_r"),
        sample_rate=raw.get("audio", {}).get("sample_rate", 16000),
        channels=raw.get("audio", {}).get("channels", 1),
        asr_model=raw.get("asr", {}).get("model", "mlx-community/whisper-large-v3-turbo"),
        language=raw.get("asr", {}).get("language", "pl"),
        cleanup_enabled=raw.get("cleanup", {}).get("enabled", True),
        cleanup_model=raw.get("cleanup", {}).get("model", "gemma3:4b"),
        cleanup_min_words=raw.get("cleanup", {}).get("min_words", 0),
        cleanup_timeout_s=raw.get("cleanup", {}).get("timeout_s", 10.0),
        dictionary=raw.get("dictionary", {}).get("terms", []),
        corrections=raw.get("dictionary", {}).get("corrections", {}),
    )
