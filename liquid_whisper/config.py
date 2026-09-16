"""Wczytywanie konfiguracji z config.toml (jeden plik na cały projekt)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.toml"


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


def load_config(path: Path = CONFIG_PATH) -> Config:
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
    )
