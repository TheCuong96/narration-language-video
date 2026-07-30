"""Provider interfaces — no API keys logged; Community uses free public endpoints."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class TranslateProvider(ABC):
    name: str
    requires_internet: bool = True
    requires_api_key: bool = False

    @abstractmethod
    def translate(self, text: str, *, source: str, target: str) -> str:
        ...

    def privacy_note(self) -> str:
        return "Chỉ gửi đoạn transcript tới dịch vụ dịch đang chọn. Video không được upload."


class TtsProvider(ABC):
    name: str
    requires_internet: bool = True
    requires_api_key: bool = False

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        out_path: Path,
        *,
        voice: str,
        rate: str = "+0%",
    ) -> None:
        ...

    def privacy_note(self) -> str:
        return "Chỉ gửi đoạn text đã dịch tới dịch vụ TTS đang chọn. Video không được upload."
