"""Weighted pipeline progress for clear overall / stage percentages."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import events
from .models import Stage

# Overall job bar = weighted sum of these 6 stages only (sum = 124).
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

    def _file_base(self) -> float:
        if self.file_total <= 0:
            return 0.0
        return 100.0 * self.file_index / self.file_total

    def _file_span(self) -> float:
        if self.file_total <= 0:
            return 100.0
        return 100.0 / self.file_total

    def overall_percent(self) -> float:
        """Overall job percent 0..100 across the 6 main stages."""
        within = overall_from_stage_fracs(self._stage_fracs)
        within = max(0.0, min(100.0, within))
        return round(self._file_base() + self._file_span() * within / 100.0, 1)

    def _set_stage_frac(self, stage: str, frac: float) -> None:
        if stage not in OVERALL_STAGE_WEIGHTS:
            return
        self._stage_fracs[stage] = max(0.0, min(1.0, frac))

    def begin_stage(self, stage: Stage | str, message: str = "") -> None:
        name = stage.value if isinstance(stage, Stage) else stage
        # Close previous overall stage at its last reported fraction (usually 100%).
        if self._current_stage and self._current_stage in OVERALL_STAGE_WEIGHTS:
            prev_frac = self._stage_fracs.get(self._current_stage, 0.0)
            if prev_frac < 1.0:
                self._set_stage_frac(self._current_stage, 1.0)
        self._current_stage = name
        if name in OVERALL_STAGE_WEIGHTS and name not in self._stage_fracs:
            self._stage_fracs[name] = 0.0
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
        stage_pct = round(100.0 * frac, 1)
        overall = self.overall_percent()
        name = self._current_stage or "progress"
        label = STAGE_LABELS.get(name, name)
        msg = message or f"{label}: {current}/{total}"
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
        )

    def complete_file(self) -> None:
        for key in OVERALL_STAGE_WEIGHTS:
            self._stage_fracs[key] = 1.0
        self._current_stage = Stage.DONE.value
        overall = round(self._file_base() + self._file_span(), 1)
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
        )
