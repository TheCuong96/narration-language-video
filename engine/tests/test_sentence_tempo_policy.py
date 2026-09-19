from __future__ import annotations

from pathlib import Path


def _captured_filter(monkeypatch, tmp_path: Path, *, source: float, target: float) -> str:
    from dubvi import ffmpeg

    durations = iter((source, target))
    command: list[str] = []

    monkeypatch.setattr(ffmpeg, "probe_duration", lambda _path: next(durations))
    monkeypatch.setattr(ffmpeg, "ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setattr(ffmpeg, "run_ffmpeg", lambda args, **_kwargs: command.extend(args))

    ffmpeg.stretch_to_duration(
        tmp_path / "source.mp3",
        tmp_path / "fitted.wav",
        target_sec=target,
        allow_spill=False,
        max_tempo=8.0,
        min_tempo=1.0,
    )
    return command[command.index("-af") + 1]


def test_any_overflow_applies_uniform_atempo(monkeypatch, tmp_path: Path):
    """A 40ms overrun is sped across the sentence, never tail-trimmed at 1×."""
    audio_filter = _captured_filter(
        monkeypatch,
        tmp_path,
        source=1.04,
        target=1.0,
    )

    assert audio_filter.startswith("atempo=1.0400,")
    assert audio_filter.endswith("atrim=0:1.000")


def test_strict_fit_is_not_capped_at_8x(monkeypatch, tmp_path: Path):
    """Strict fitting stacks atempo filters instead of trimming final words."""
    audio_filter = _captured_filter(
        monkeypatch,
        tmp_path,
        source=10.0,
        target=1.0,
    )

    assert audio_filter.count("atempo=2.0") == 3
    assert "atempo=1.2500" in audio_filter


def test_whole_track_fit_also_speeds_small_overflow(monkeypatch, tmp_path: Path):
    """The generic fitter follows the same no-tail-trim duration rule."""
    from dubvi import ffmpeg

    durations = iter((1.04, 1.0))
    command: list[str] = []
    monkeypatch.setattr(ffmpeg, "probe_duration", lambda _path: next(durations))
    monkeypatch.setattr(ffmpeg, "ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setattr(ffmpeg, "run_ffmpeg", lambda args, **_kwargs: command.extend(args))

    ffmpeg.fit_audio_to_duration(
        tmp_path / "source.wav",
        tmp_path / "fitted.wav",
        target_sec=1.0,
    )

    audio_filter = command[command.index("-af") + 1]
    assert audio_filter.startswith("atempo=1.0400,")
