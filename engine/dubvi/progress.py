"""Weighted pipeline progress for clear overall / stage percentages."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import events
from .models import Stage

# Estimated wall-time shares for the six user-visible stages (sum = 124).
#
# The unit is an observed relative time share, not an equal completion score.
# Every stage also reports its measured wall time so the UI can show
# what was actually spent while these estimates keep the bar useful before a
# stage (or the first video in a job) has completed.
OVERALL_STAGE_WEIGHTS: dict[str, float] = {
    Stage.EXTRACTING.value: 5,
    Stage.TRANSCRIBING.value: 28,
    Stage.TRANSLATING.value: 12,
    Stage.TTS.value: 70,
    Stage.ALIGNING.value: 6,
    Stage.MUXING.value: 3,
}
OVERALL_WEIGHT_TOTAL = sum(OVERALL_STAGE_WEIGHTS.values())

# Auxiliary stages (init / review / cleanup) — shown in UI but not in overall %.
STAGE_WEIGHTS: dict[str, float] = {
    **OVERALL_STAGE_WEIGHTS,
    Stage.INIT.value: 0,
    Stage.REVIEW.value: 0,
    Stage.CLEANUP.value: 0,
}

STAGE_LABELS: dict[str, str] = {
    Stage.INIT.value: "Chuẩn bị",
    Stage.EXTRACTING.value: "Tách audio",
    Stage.TRANSCRIBING.value: "Nhận dạng lời nói",
    Stage.TRANSLATING.value: "Dịch",
    Stage.REVIEW.value: "Chờ sửa bản dịch",
    Stage.TTS.value: "Tạo giọng đọc",
    Stage.ALIGNING.value: "Căn giờ",
    Stage.MUXING.value: "Ghép",
    Stage.CLEANUP.value: "Dọn file tạm",
    Stage.DONE.value: "Hoàn tất",
    Stage.QUEUED.value: "Hàng đợi",
}


def overall_from_stage_fracs(stage_fracs: dict[str, float]) -> float:
    """Map per-stage 0..1 fractions to 0..100 overall (single file)."""
    done_w = sum(
        OVERALL_STAGE_WEIGHTS[k] * max(0.0, min(1.0, stage_fracs.get(k, 0.0)))
        for k in OVERALL_STAGE_WEIGHTS
    )
    return round(100.0 * done_w / OVERALL_WEIGHT_TOTAL, 1)


@dataclass
class ProgressTracker:
    file_index: int  # 0-based
    file_total: int
    file_name: str = ""
    _stage_fracs: dict[str, float] = field(default_factory=dict)
    _current_stage: str = ""
    _stage_started_at: float | None = None
    _stage_durations_sec: dict[str, float] = field(default_factory=dict)
    _last_overall_percent: float = 0.0

    def _file_base(self) -> float:
        if self.file_total <= 0:
            return 0.0
        return 100.0 * self.file_index / self.file_total

    def _file_span(self) -> float:
        if self.file_total <= 0:
            return 100.0
        return 100.0 / self.file_total

    def overall_percent(self) -> float:
        """Overall job percent 0..100 across the six main stages.

        The returned value is monotonic for the lifetime of this tracker.  A
        resumed/cache path can announce an earlier stage again, but that must
        never make the user-visible total move backwards.
        """
        within = overall_from_stage_fracs(self._stage_fracs)
        within = max(0.0, min(100.0, within))
        calculated = round(self._file_base() + self._file_span() * within / 100.0, 1)
        self._last_overall_percent = max(self._last_overall_percent, calculated)
        return self._last_overall_percent

    def _set_stage_frac(self, stage: str, frac: float) -> None:
        if stage not in OVERALL_STAGE_WEIGHTS:
            return
        clamped = max(0.0, min(1.0, frac))
        # Concurrent callbacks, cache replay and resume can repeat an older
        # value.  Preserve the highest confirmed fraction for every stage.
        self._stage_fracs[stage] = max(self._stage_fracs.get(stage, 0.0), clamped)

    def _finish_current_stage_timing(self, now: float | None = None) -> None:
        name = self._current_stage
        if name not in OVERALL_STAGE_WEIGHTS or self._stage_started_at is None:
            self._stage_started_at = None
            return
        ended_at = time.perf_counter() if now is None else now
        elapsed = max(0.0, ended_at - self._stage_started_at)
        self._stage_durations_sec[name] = self._stage_durations_sec.get(name, 0.0) + elapsed
        self._stage_started_at = None

    def _timing_snapshot(self) -> dict[str, float]:
        """Measured seconds per main stage, including the active stage."""
        snapshot = dict(self._stage_durations_sec)
        if self._current_stage in OVERALL_STAGE_WEIGHTS and self._stage_started_at is not None:
            live = max(0.0, time.perf_counter() - self._stage_started_at)
            snapshot[self._current_stage] = snapshot.get(self._current_stage, 0.0) + live
        return {key: round(value, 2) for key, value in snapshot.items()}

    def split_current_stage_timing(self, task_seconds: dict[Stage | str, float]) -> None:
        """Split one overlapped wall-clock stage into measured sub-stage shares.

        Long videos pipeline transcription and translation chunk-by-chunk. The
        workers measure both tasks separately, while this method normalizes
        those measurements to the combined wall time so their sum never double
        counts parallel work.
        """
        current = self._current_stage
        self._finish_current_stage_timing()
        combined_wall = self._stage_durations_sec.pop(current, 0.0)
        normalized: dict[str, float] = {}
        for stage, seconds in task_seconds.items():
            name = stage.value if isinstance(stage, Stage) else stage
            if name in OVERALL_STAGE_WEIGHTS:
                normalized[name] = max(0.0, float(seconds))
        task_total = sum(normalized.values())
        if task_total <= 0:
            normalized = {name: OVERALL_STAGE_WEIGHTS[name] for name in normalized}
            task_total = sum(normalized.values()) or 1.0
        for name, seconds in normalized.items():
            share = combined_wall * seconds / task_total
            self._stage_durations_sec[name] = self._stage_durations_sec.get(name, 0.0) + share

    def begin_stage(self, stage: Stage | str, message: str = "") -> None:
        name = stage.value if isinstance(stage, Stage) else stage
        now = time.perf_counter()
        previous = self._current_stage
        # Close previous overall stage at its last reported fraction (usually 100%).
        if previous != name and previous in OVERALL_STAGE_WEIGHTS:
            prev_frac = self._stage_fracs.get(previous, 0.0)
            if prev_frac < 1.0:
                self._set_stage_frac(previous, 1.0)
        if previous != name:
            self._finish_current_stage_timing(now)
        self._current_stage = name
        if name in OVERALL_STAGE_WEIGHTS and name not in self._stage_fracs:
            self._stage_fracs[name] = 0.0
        if name in OVERALL_STAGE_WEIGHTS and self._stage_started_at is None:
            self._stage_started_at = now
        label = STAGE_LABELS.get(name, name)
        msg = message or label
        events.stage(
            name,
            msg,
            file=self.file_name,
            file_index=self.file_index + 1,
            file_total=self.file_total,
        )
        self.emit(0, 1, msg)

    def emit_chunk_early_progress(self, done: int, total: int, message: str = "") -> None:
        """
        Long-video chunk path: each chunk runs transcribe + translate.

        Advance both stage fractions together so overall reflects all 6 parts.
        """
        total = max(int(total), 1)
        done = max(0, min(int(done), total))
        frac = done / total
        self._set_stage_frac(Stage.TRANSCRIBING.value, frac)
        self._set_stage_frac(Stage.TRANSLATING.value, frac)
        self._current_stage = Stage.TRANSCRIBING.value
        self.emit(done, total, message, force_frac=frac)

    def emit(
        self,
        current: int,
        total: int,
        message: str = "",
        *,
        force_frac: float | None = None,
    ) -> None:
        total = max(total, 1)
        current = max(0, min(current, total))
        frac = force_frac if force_frac is not None else (current / total)
        frac = max(0.0, min(1.0, frac))
        if self._current_stage in OVERALL_STAGE_WEIGHTS:
            self._set_stage_frac(self._current_stage, frac)
            # Report the monotonic stage value as well; duplicated callbacks
            # must not make the thin per-stage bar jump backwards.
            frac = self._stage_fracs[self._current_stage]
        stage_pct = round(100.0 * frac, 1)
        overall = self.overall_percent()
        name = self._current_stage or "progress"
        label = STAGE_LABELS.get(name, name)
        msg = message or f"{label}: {current}/{total}"
        timings = self._timing_snapshot()
        events.progress(
            name,
            current,
            total,
            msg,
            percent=stage_pct,
            overall_percent=overall,
            file=self.file_name,
            file_index=self.file_index + 1,
            file_total=self.file_total,
            stage_label=label,
            stage_elapsed_sec=timings.get(name, 0.0),
            stage_durations_sec=timings,
            stage_fracs={key: round(value, 4) for key, value in self._stage_fracs.items()},
        )

    def complete_file(self) -> None:
        self._finish_current_stage_timing()
        for key in OVERALL_STAGE_WEIGHTS:
            self._stage_fracs[key] = 1.0
        self._current_stage = Stage.DONE.value
        overall = round(self._file_base() + self._file_span(), 1)
        self._last_overall_percent = max(self._last_overall_percent, overall)
        events.progress(
            Stage.DONE,
            self.file_index + 1,
            self.file_total,
            f"Xong {self.file_name}",
            percent=100,
            overall_percent=min(100.0, overall),
            file=self.file_name,
            file_index=self.file_index + 1,
            file_total=self.file_total,
            stage_label="Hoàn tất",
            stage_elapsed_sec=0.0,
            stage_durations_sec=self._timing_snapshot(),
            stage_fracs={key: 1.0 for key in OVERALL_STAGE_WEIGHTS},
        )
