"""Paid provider stubs for future versions — not wired in v0.1."""

from __future__ import annotations

from pathlib import Path

from .base import TtsProvider, TranslateProvider


class GoogleCloudTranslateStub(TranslateProvider):
    name = "google-cloud-translate"
    requires_internet = True
    requires_api_key = True

    def translate(self, text: str, *, source: str, target: str) -> str:
        raise NotImplementedError(
            "Google Cloud Translation chưa có trong Community v0.1. "
            "Dùng deep-translator hoặc nâng cấp bản Pro sau này."
        )


class GoogleCloudTtsStub(TtsProvider):
    name = "google-cloud-tts"
    requires_internet = True
    requires_api_key = True

    async def synthesize(
        self, text: str, out_path: Path, *, voice: str, rate: str = "+0%"
    ) -> None:
        raise NotImplementedError("Google Cloud TTS chưa có trong Community v0.1.")


class AzureSpeechStub(TtsProvider):
    name = "azure-speech"
    requires_internet = True
    requires_api_key = True

    async def synthesize(
        self, text: str, out_path: Path, *, voice: str, rate: str = "+0%"
    ) -> None:
        raise NotImplementedError("Azure Speech chưa có trong Community v0.1.")
