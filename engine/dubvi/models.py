"""Shared data models and stable error codes for Dub VI engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ErrorCode(str, Enum):
    """Stable error codes consumed by the desktop UI."""

    OK = "OK"
    INPUT_NOT_FOUND = "INPUT_NOT_FOUND"
    NO_VIDEOS = "NO_VIDEOS"
    FFMPEG_MISSING = "FFMPEG_MISSING"
    FFPROBE_MISSING = "FFPROBE_MISSING"
    DISK_SPACE_LOW = "DISK_SPACE_LOW"
    WHISPER_LOAD_FAILED = "WHISPER_LOAD_FAILED"
    TRANSCRIBE_FAILED = "TRANSCRIBE_FAILED"
    TRANSLATE_FAILED = "TRANSLATE_FAILED"
    TTS_FAILED = "TTS_FAILED"
    MUX_FAILED = "MUX_FAILED"
    CANCELLED = "CANCELLED"
    INVALID_ARGS = "INVALID_ARGS"
    REVIEW_PENDING = "REVIEW_PENDING"
    TRANSLATION_INVALID = "TRANSLATION_INVALID"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    INTERNAL = "INTERNAL"


class Stage(str, Enum):
    INIT = "init"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    REVIEW = "review"
    TTS = "tts"
    ALIGNING = "aligning"
    MUXING = "muxing"
    CLEANUP = "cleanup"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AudioMode(str, Enum):
    """Output audio strategies."""

    VI_ONLY = "vi_only"  # Replace with Vietnamese narration only
    DUAL_TRACK = "dual_track"  # Keep EN + add VI as second audio track
    MIX = "mix"  # Mix VI with ducked original


class StartFrom(str, Enum):
    """Resume pipeline from a named stage (uses cache for earlier steps)."""

    AUTO = "auto"  # Resume intelligently from missing cache
    EXTRACT = "extract"
    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"
    TTS = "tts"
    MUX = "mux"


class QueueItemStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


DEFAULT_VOICE = "vi-VN-HoaiMyNeural"
DEFAULT_MODEL = "small"  # recommended for typical CPU machines
DEFAULT_SOURCE_LANG = "en"
DEFAULT_TARGET_LANG = "vi"
DEFAULT_MIX_ORIGINAL_DB = -18.0

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".webm")

# Containers that commonly accept H.264/H.265 + AAC with stream copy
COPY_FRIENDLY_CONTAINERS = {".mp4", ".mkv", ".mov"}

TECH_TERMS = [
    "Next.js",
    "TypeScript",
    "JavaScript",
    "React Hook Form",
    "Appwrite",
    "Plaid",
    "Dwolla",
    "Sentry",
    "shadcn/ui",
    "shadcn",
    "Tailwind CSS",
    "Tailwind",
    "Zod",
    "SSR",
    "Horizon",
    "Robinhood",
    "Stripe",
    "MongoDB",
    "Node.js",
    "GitHub",
    "Vercel",
    "FFmpeg",
]


@dataclass
class Segment:
    id: int
    start: float
    end: float
    text_en: str = ""
    text_vi: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "text_en": self.text_en,
            "text_vi": self.text_vi,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Segment:
        return cls(
            id=int(data["id"]),
            start=float(data["start"]),
            end=float(data["end"]),
            text_en=str(data.get("text_en") or data.get("text") or ""),
            text_vi=str(data.get("text_vi") or ""),
        )


@dataclass
class JobConfig:
    """Runtime options for one dubbing job (folder, files, or queue)."""

    output_dir: Path
    job_id: str
    input_dir: Path | None = None
    input_files: list[Path] = field(default_factory=list)
    voice: str = DEFAULT_VOICE
    whisper_model: str = DEFAULT_MODEL
    source_lang: str = DEFAULT_SOURCE_LANG
    target_lang: str = DEFAULT_TARGET_LANG
    prefer_gpu: bool = False
    force: bool = False
    translate_only: bool = False
    review_translation: bool = False  # pause after translate for UI edit
    only: list[str] = field(default_factory=list)
    extra_terms: list[str] = field(default_factory=list)
    cleanup_on_success: bool = True
    keep_extract_audio: bool = False
    audio_mode: AudioMode = AudioMode.VI_ONLY
    mix_original_db: float = DEFAULT_MIX_ORIGINAL_DB
    start_from: StartFrom = StartFrom.AUTO
    allow_reencode: bool = True  # if False, fail instead of re-encoding video
    retry_stems: list[str] = field(default_factory=list)  # only these on retry

    @property
    def terms(self) -> list[str]:
        return TECH_TERMS + list(self.extra_terms)


@dataclass
class DeviceInfo:
    device: str  # "cpu" | "cuda"
    compute_type: str
    gpu_name: str | None = None
    fallback_reason: str | None = None


@dataclass
class MuxPlan:
    """Decision for how to write the output container/streams."""

    video_codec_copy: bool
    reencode_video: bool
    reason: str
    output_suffix: str  # e.g. .mp4
    audio_mode: AudioMode
