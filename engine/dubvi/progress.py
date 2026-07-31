"""Weighted pipeline progress for clear overall / stage percentages."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import events
from .models import Stage

# Relative weights within one video (sum ~= 100)
STAGE_WEIGHTS: dict[str, float] = {
    Stage.INIT.value: 2,
    Stage.EXTRACTING.value: 5,
    Stage.TRANSCRIBING.value: 40,
    Stage.TRANSLATING.value: 15,
    Stage.REVIEW.value: 1,
    Stage.TTS.value: 25,
    Stage.ALIGNING.value: 8,
    Stage.MUXING.value: 4,
    Stage.CLEANUP.value: 1,
}

STAGE_LABELS: dict[str, str] = {
    Stage.INIT.value: "Chuẩn bị",
    Stage.EXTRACTING.value: "Tách âm thanh",
    Stage.TRANSCRIBING.value: "Nhận dạng lời nói",
    Stage.TRANSLATING.value: "Dịch sang tiếng Việt",
    Stage.REVIEW.value: "Chờ sửa bản dịch",
    Stage.TTS.value: "Tạo giọng đọc",
    Stage.ALIGNING.value: "Căn thời gian",
    Stage.MUXING.value: "Ghép video",
    Stage.CLEANUP.value: "Dọn file tạm",
    Stage.DONE.value: "Hoàn tất",
    Stage.QUEUED.value: "Hàng đợi",
}


@dataclass
class ProgressTracker:
    file_index: int  # 0-based
    file_total: int
    file_name: str = ""
    _completed_weight: float = 0.0
    _current_stage: str = ""
    _stage_frac: float = 0.0
    _history: list[str] = field(default_factory=list)

    def _file_base(self) -> float:
        if self.file_total <= 0:
            return 0.0
        return 100.0 * self.file_index / self.file_total

    def _file_span(self) -> float:
        if self.file_total <= 0:
            return 100.0
        return 100.0 / self.file_total

    def overall_percent(self) -> float:
        """Overall job percent 0..100."""
        within = 0.0
        total_w = sum(STAGE_WEIGHTS.values()) or 100.0
        within = 100.0 * (self._completed_weight + self._stage_weight() * self._stage_frac) / total_w
        within = max(0.0, min(100.0, within))
        return round(self._file_base() + self._file_span() * within / 100.0, 1)

    def _stage_weight(self) -> float:
        return STAGE_WEIGHTS.get(self._current_stage, 0.0)

    def begin_stage(self, stage: Stage | str, message: str = "") -> None:
        name = stage.value if isinstance(stage, Stage) else stage
        # Close previous stage as complete
        if self._current_stage and self._current_stage in STAGE_WEIGHTS:
            if self._current_stage not in self._history:
                self._completed_weight += STAGE_WEIGHTS[self._current_stage]
                self._history.append(self._current_stage)
        self._current_stage = name
        self._stage_frac = 0.0
        label = STAGE_LABELS.get(name, name)
        msg = message or label
        events.stage(name, msg, file=self.file_name, file_index=self.file_index + 1, file_total=self.file_total)
        self.emit(0, 1, msg)

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
        self._stage_frac = max(0.0, min(1.0, frac))
        stage_pct = round(100.0 * self._stage_frac, 1)
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
        # Mark all remaining weights done for this file
        for key, w in STAGE_WEIGHTS.items():
            if key not in self._history:
                self._completed_weight += w
                self._history.append(key)
        self._stage_frac = 1.0
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
