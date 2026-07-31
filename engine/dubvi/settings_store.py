"""User settings persisted under %LOCALAPPDATA%/DubVI/settings.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import DEFAULT_MIX_ORIGINAL_DB, DEFAULT_MODEL, DEFAULT_VOICE, AudioMode
from .system_info import appdata_root


@dataclass
class AppSettings:
    whisper_model: str = "small"
    device_mode: str = "cpu"  # cpu | auto
    default_output_dir: str = ""
    cleanup_temps: bool = True
    mix_original_db: float = DEFAULT_MIX_ORIGINAL_DB
    voice: str = DEFAULT_VOICE
    audio_mode: str = AudioMode.VI_ONLY.value
    review_by_default: bool = False
    translate_provider: str = "deep-translator"
    tts_provider: str = "edge-tts"
    # Local XTTS speaker reference (WAV). Empty → model speaker_default.wav
    xtts_speaker_wav: str = ""
    # Never store API keys in plaintext logs; reserved for future
    # api_keys stored only if user opts in later versions

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        fields = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in fields}
        return cls(**filtered)


def settings_path() -> Path:
    return appdata_root() / "settings.json"


def load_settings() -> AppSettings:
    path = settings_path()
    if not path.exists():
        return AppSettings()
    try:
        return AppSettings.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return AppSettings()


def save_settings(settings: AppSettings) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
