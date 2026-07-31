import {
  formatElapsed,
  formatFinishClock,
  remainFromPercent,
  withinFilePercent,
} from "../hooks/useElapsed";
import type { QueueItem } from "./types";

/** Weights aligned with engine/dubvi/progress.py (display stages). */
export const STAGE_LEGEND = [
  { key: "extracting", label: "Tách audio", weight: 5 },
  { key: "transcribing", label: "Nhận dạng lời nói", weight: 40 },
  { key: "translating", label: "Dịch", weight: 15 },
  { key: "tts", label: "Tạo giọng đọc", weight: 25 },
  { key: "aligning", label: "Căn giờ", weight: 8 },
  { key: "muxing", label: "Ghép", weight: 4 },
] as const;

const LEGEND_WEIGHT_SUM = STAGE_LEGEND.reduce((a, s) => a + s.weight, 0);

export type EtaLine = {
  remainSec: number;
  remainLabel: string;
  finishLabel: string;
};

function toEtaLine(remainSec: number | null): EtaLine | null {
  if (remainSec == null) return null;
  return {
    remainSec,
    remainLabel: formatElapsed(remainSec),
    finishLabel: formatFinishClock(remainSec),
  };
}

export type StageLegendEta = {
  key: string;
  label: string;
  weight: number;
  /** Estimated full duration of this stage for current video. */
  estSec: number | null;
  estLabel: string | null;
  active: boolean;
  done: boolean;
};

export type ProgressEta = {
  stage: EtaLine | null;
  file: EtaLine | null;
  job: EtaLine | null;
  legend: StageLegendEta[];
  /** Projected seconds for one full video at current pace. */
  fileTotalEstSec: number | null;
};

function blendRemain(a: number | null, b: number | null, aWeight = 0.55): number | null {
  if (a == null) return b;
  if (b == null) return a;
  return Math.round(a * aWeight + b * (1 - aWeight));
}

/**
 * Multi-video remain from finished files' wall times + video durations.
 * Falls back to null when not enough completed work.
 */
function remainFromQueueHistory(
  queue: QueueItem[],
  fileIndex: number,
  fileTotal: number,
  fileRemainSec: number | null,
  completedElapsedSec: number[],
): number | null {
  if (fileTotal <= 1 || completedElapsedSec.length === 0) return null;

  const completedItems = queue.filter((q) => q.status === "completed");
  let completedDur = 0;
  for (const it of completedItems) {
    if (typeof it.duration_sec === "number" && it.duration_sec > 0) {
      completedDur += it.duration_sec;
    }
  }
  const completedWall = completedElapsedSec.reduce((a, b) => a + b, 0);
  if (completedWall < 8) return null;

  const rate =
    completedDur > 30
      ? completedWall / completedDur // sec processing / sec media
      : completedWall / Math.max(completedElapsedSec.length, 1); // avg sec / file

  let remainOther = 0;
  const startIdx = Math.max(fileIndex, 1); // 1-based current; remaining after current
  for (let i = startIdx; i < fileTotal; i++) {
    const item = queue[i];
    if (!item || item.status === "completed" || item.status === "skipped") continue;
    if (completedDur > 30 && typeof item.duration_sec === "number" && item.duration_sec > 0) {
      remainOther += item.duration_sec * rate;
    } else {
      remainOther += rate;
    }
  }

  const cur = fileRemainSec ?? 0;
  return Math.round(cur + remainOther);
}

export function computeProgressEta(input: {
  busy: boolean;
  elapsedSec: number;
  stageElapsedSec: number;
  fileElapsedSec: number;
  overallPct: number;
  stagePct: number;
  stageKey: string;
  fileIndex: number;
  fileTotal: number;
  queue: QueueItem[];
  /** Wall seconds for each completed file in this job (from engine). */
  completedElapsedSec: number[];
}): ProgressEta {
  const {
    busy,
    elapsedSec,
    stageElapsedSec,
    fileElapsedSec,
    overallPct,
    stagePct,
    stageKey,
    fileIndex,
    fileTotal,
    queue,
    completedElapsedSec,
  } = input;

  const empty: ProgressEta = {
    stage: null,
    file: null,
    job: null,
    legend: STAGE_LEGEND.map((s) => ({
      ...s,
      estSec: null,
      estLabel: null,
      active: false,
      done: false,
    })),
  };

  if (!busy && overallPct < 100) return empty;

  const stageRemain = remainFromPercent(stageElapsedSec, stagePct, {
    minElapsed: 4,
    minPercent: 3,
  });

  const filePct = withinFilePercent(overallPct, fileIndex, fileTotal || 1);
  const fileRemainFromFile = remainFromPercent(fileElapsedSec, filePct, {
    minElapsed: 8,
    minPercent: 3,
  });

  // Also derive file remain from job overall when multi-file (more stable early on).
  let fileRemainFromJob: number | null = null;
  if ((fileTotal || 1) > 1 && overallPct > 2) {
    const jobRemain = remainFromPercent(elapsedSec, overallPct, {
      minElapsed: 8,
      minPercent: 2,
    });
    if (jobRemain != null) {
      const span = 100 / (fileTotal || 1);
      const doneInFile = filePct / 100;
      const remainFracInFile = Math.max(0, 1 - doneInFile);
      // Portion of job remain belonging to rest of current file ≈ span * remainFrac
      // vs total remaining job span weight
      const filesLeftIncl = Math.max(
        0.01,
        (fileTotal || 1) - Math.max(0, (fileIndex || 1) - 1) - doneInFile,
      );
      fileRemainFromJob = Math.round(
        (jobRemain * (span * remainFracInFile)) / (span * filesLeftIncl),
      );
    }
  }

  const fileRemain = blendRemain(fileRemainFromFile, fileRemainFromJob, 0.65);

  const jobRemainPct = remainFromPercent(elapsedSec, overallPct, {
    minElapsed: 8,
    minPercent: 2,
  });
  const jobRemainQueue = remainFromQueueHistory(
    queue,
    fileIndex || 1,
    fileTotal || queue.length || 1,
    fileRemain,
    completedElapsedSec,
  );
  const jobRemain = blendRemain(jobRemainPct, jobRemainQueue, 0.6);

  // Projected full duration of current file
  let fileTotalEstSec: number | null = null;
  if (fileRemain != null && filePct > 3) {
    fileTotalEstSec = Math.round(fileElapsedSec + fileRemain);
  } else if (fileElapsedSec > 12 && filePct > 5) {
    fileTotalEstSec = Math.round((fileElapsedSec * 100) / filePct);
  }

  const order = STAGE_LEGEND.map((s) => s.key);
  const activeIdx = order.indexOf(stageKey);
  const legend: StageLegendEta[] = STAGE_LEGEND.map((s, i) => {
    const estSec =
      fileTotalEstSec != null
        ? Math.round((fileTotalEstSec * s.weight) / LEGEND_WEIGHT_SUM)
        : null;
    return {
      ...s,
      estSec,
      estLabel: estSec != null ? formatElapsed(estSec) : null,
      active: s.key === stageKey,
      done: activeIdx >= 0 ? i < activeIdx : false,
    };
  });

  // Refine active stage estimate with live stage progress when available
  if (stageRemain != null && activeIdx >= 0) {
    const full =
      stagePct > 3
        ? Math.round(stageElapsedSec + stageRemain)
        : legend[activeIdx].estSec;
    if (full != null) {
      legend[activeIdx] = {
        ...legend[activeIdx],
        estSec: full,
        estLabel: formatElapsed(full),
      };
    }
  }

  return {
    stage: toEtaLine(stageRemain),
    file: toEtaLine(fileRemain),
    job: toEtaLine(jobRemain),
    legend,
    fileTotalEstSec,
  };
}
