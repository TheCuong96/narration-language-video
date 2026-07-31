import {
  formatDurationVi,
  formatFinishAt,
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

/** Fallback process-time / media-time when no completed files yet. */
const DEFAULT_PROCESS_RATE = 1.8;

export type EtaConfidence = "estimating" | "rough" | "stable";

export type EtaLine = {
  remainSec: number;
  remainLabel: string;
  finishLabel: string;
};

function toEtaLine(remainSec: number | null): EtaLine | null {
  if (remainSec == null) return null;
  const clamped = Math.max(0, Math.round(remainSec));
  return {
    remainSec: clamped,
    remainLabel: formatDurationVi(clamped),
    finishLabel: formatFinishAt(clamped),
  };
}

export type StageLegendEta = {
  key: string;
  label: string;
  weight: number;
  /** Estimated full duration of this stage for current video. */
  estSec: number | null;
  estLabel: string | null;
  /** Remaining for active stage; full est for future; null when done. */
  remainSec: number | null;
  remainLabel: string | null;
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
  /** Active stage display name for UI. */
  stageName: string;
  confidence: EtaConfidence;
  confidenceLabel: string;
  /** Short status under the headline finish time. */
  summaryLabel: string | null;
};

function blendRemain(a: number | null, b: number | null, aWeight = 0.55): number | null {
  if (a == null) return b;
  if (b == null) return a;
  return Math.round(a * aWeight + b * (1 - aWeight));
}

function stageLabelOf(stageKey: string): string {
  const hit = STAGE_LEGEND.find((s) => s.key === stageKey);
  return hit?.label || stageKey || "Công đoạn hiện tại";
}

function confidenceOf(
  elapsedSec: number,
  overallPct: number,
  completedCount: number,
): { level: EtaConfidence; label: string } {
  if (completedCount >= 1 || (elapsedSec >= 45 && overallPct >= 15)) {
    return { level: "stable", label: "Ước lượng đang ổn định" };
  }
  if (elapsedSec >= 12 && overallPct >= 4) {
    return { level: "rough", label: "Ước lượng sơ bộ — sẽ chính xác hơn khi chạy thêm" };
  }
  return {
    level: "estimating",
    label: "Đang tính theo độ dài video — sẽ chỉnh khi có tiến độ thực",
  };
}

function mediaDurationOf(item: QueueItem | undefined): number {
  if (!item) return 0;
  return typeof item.duration_sec === "number" && item.duration_sec > 0
    ? item.duration_sec
    : 0;
}

/**
 * Seed remain from known media lengths × process rate (history or default).
 * Used before live % is reliable, and as a second signal for the job total.
 */
function remainFromMediaSeed(
  queue: QueueItem[],
  fileIndex: number,
  fileTotal: number,
  filePct: number,
  completedElapsedSec: number[],
): { fileRemain: number | null; jobRemain: number | null; rate: number } {
  const completedItems = queue.filter((q) => q.status === "completed");
  let completedDur = 0;
  for (const it of completedItems) completedDur += mediaDurationOf(it);
  const completedWall = completedElapsedSec.reduce((a, b) => a + b, 0);

  let rate = DEFAULT_PROCESS_RATE;
  if (completedWall >= 8 && completedDur > 30) {
    rate = completedWall / completedDur;
  } else if (completedWall >= 8 && completedElapsedSec.length > 0) {
    // No reliable media lengths — fall back later via avg wall/file.
    rate = DEFAULT_PROCESS_RATE;
  }

  const idx = Math.max(1, fileIndex || 1);
  const current = queue[idx - 1];
  const curDur = mediaDurationOf(current);

  let fileRemain: number | null = null;
  if (curDur > 0) {
    const fileTotalEst = curDur * rate;
    const doneFrac = Math.max(0, Math.min(0.99, filePct / 100));
    fileRemain = Math.round(fileTotalEst * (1 - doneFrac));
  }

  let jobRemain: number | null = fileRemain;
  if (fileTotal > 1) {
    let other = 0;
    let counted = 0;
    for (let i = idx; i < fileTotal; i++) {
      const item = queue[i];
      if (!item || item.status === "completed" || item.status === "skipped") continue;
      const d = mediaDurationOf(item);
      if (d > 0) {
        other += d * rate;
        counted += 1;
      } else if (completedElapsedSec.length > 0) {
        other += completedWall / completedElapsedSec.length;
        counted += 1;
      } else if (curDur > 0) {
        other += curDur * rate;
        counted += 1;
      }
    }
    if (fileRemain != null || counted > 0) {
      jobRemain = Math.round((fileRemain ?? 0) + other);
    }
  }

  return { fileRemain, jobRemain, rate };
}

/**
 * Multi-video remain from finished files' wall times + video durations.
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
  for (const it of completedItems) completedDur += mediaDurationOf(it);
  const completedWall = completedElapsedSec.reduce((a, b) => a + b, 0);
  if (completedWall < 8) return null;

  const rate =
    completedDur > 30
      ? completedWall / completedDur
      : completedWall / Math.max(completedElapsedSec.length, 1);

  let remainOther = 0;
  const startIdx = Math.max(fileIndex, 1);
  for (let i = startIdx; i < fileTotal; i++) {
    const item = queue[i];
    if (!item || item.status === "completed" || item.status === "skipped") continue;
    if (completedDur > 30 && mediaDurationOf(item) > 0) {
      remainOther += mediaDurationOf(item) * rate;
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

  const stageName = stageLabelOf(stageKey);
  const emptyLegend = STAGE_LEGEND.map((s) => ({
    ...s,
    estSec: null as number | null,
    estLabel: null as string | null,
    remainSec: null as number | null,
    remainLabel: null as string | null,
    active: false,
    done: false,
  }));

  const empty: ProgressEta = {
    stage: null,
    file: null,
    job: null,
    legend: emptyLegend,
    fileTotalEstSec: null,
    stageName,
    confidence: "estimating",
    confidenceLabel: "",
    summaryLabel: null,
  };

  if (!busy && overallPct < 100) return empty;

  const filePct = withinFilePercent(overallPct, fileIndex, fileTotal || 1);
  const seed = remainFromMediaSeed(
    queue,
    fileIndex || 1,
    fileTotal || queue.length || 1,
    filePct,
    completedElapsedSec,
  );

  const stageRemainLive = remainFromPercent(stageElapsedSec, stagePct, {
    minElapsed: 4,
    minPercent: 3,
  });

  const fileRemainFromFile = remainFromPercent(fileElapsedSec, filePct, {
    minElapsed: 8,
    minPercent: 3,
  });

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
      const filesLeftIncl = Math.max(
        0.01,
        (fileTotal || 1) - Math.max(0, (fileIndex || 1) - 1) - doneInFile,
      );
      fileRemainFromJob = Math.round(
        (jobRemain * (span * remainFracInFile)) / (span * filesLeftIncl),
      );
    }
  }

  // Prefer live progress; seed from media so ETA appears earlier and stays grounded.
  let fileRemain = blendRemain(fileRemainFromFile, fileRemainFromJob, 0.65);
  fileRemain = blendRemain(fileRemain, seed.fileRemain, fileRemain != null ? 0.7 : 0);

  // Stage remain: live first; else share of file remain by remaining stage weights.
  let stageRemain = stageRemainLive;
  if (stageRemain == null && fileRemain != null && stageKey) {
    const activeIdx = STAGE_LEGEND.findIndex((s) => s.key === stageKey);
    if (activeIdx >= 0) {
      const active = STAGE_LEGEND[activeIdx];
      const stageDone = Math.max(0, Math.min(0.99, stagePct / 100));
      const activeLeft = active.weight * (1 - stageDone);
      const futureWeight = STAGE_LEGEND.slice(activeIdx + 1).reduce(
        (a, s) => a + s.weight,
        0,
      );
      const remainWeight = activeLeft + futureWeight;
      if (remainWeight > 0) {
        stageRemain = Math.round(fileRemain * (activeLeft / remainWeight));
      }
    }
  }

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
  let jobRemain = blendRemain(jobRemainPct, jobRemainQueue, 0.6);
  jobRemain = blendRemain(jobRemain, seed.jobRemain, jobRemain != null ? 0.65 : 0);

  // Single-file job: job === file
  if ((fileTotal || 1) <= 1) {
    jobRemain = fileRemain ?? jobRemain;
  }

  let fileTotalEstSec: number | null = null;
  if (fileRemain != null && filePct > 3) {
    fileTotalEstSec = Math.round(fileElapsedSec + fileRemain);
  } else if (fileElapsedSec > 12 && filePct > 5) {
    fileTotalEstSec = Math.round((fileElapsedSec * 100) / filePct);
  } else if (seed.fileRemain != null) {
    const doneFrac = Math.max(0, Math.min(0.99, filePct / 100));
    fileTotalEstSec = Math.round(seed.fileRemain / Math.max(0.01, 1 - doneFrac));
  }

  const order = STAGE_LEGEND.map((s) => s.key);
  const activeIdx = order.indexOf(stageKey);
  const legend: StageLegendEta[] = STAGE_LEGEND.map((s, i) => {
    const estSec =
      fileTotalEstSec != null
        ? Math.round((fileTotalEstSec * s.weight) / LEGEND_WEIGHT_SUM)
        : null;
    const done = activeIdx >= 0 ? i < activeIdx : false;
    const active = s.key === stageKey;
    let remainSec: number | null = null;
    if (done) remainSec = 0;
    else if (active && stageRemain != null) remainSec = stageRemain;
    else if (!done && estSec != null) remainSec = estSec;
    return {
      ...s,
      estSec,
      estLabel: estSec != null ? formatDurationVi(estSec) : null,
      remainSec,
      remainLabel:
        remainSec != null
          ? done
            ? "xong"
            : active
              ? `còn ${formatDurationVi(remainSec)}`
              : `khoảng ${formatDurationVi(remainSec)}`
          : null,
      active,
      done,
    };
  });

  if (stageRemain != null && activeIdx >= 0) {
    const full =
      stagePct > 3
        ? Math.round(stageElapsedSec + stageRemain)
        : legend[activeIdx].estSec;
    if (full != null) {
      legend[activeIdx] = {
        ...legend[activeIdx],
        estSec: full,
        estLabel: formatDurationVi(full),
        remainSec: stageRemain,
        remainLabel: `còn ${formatDurationVi(stageRemain)}`,
      };
    }
  }

  const conf = confidenceOf(elapsedSec, overallPct, completedElapsedSec.length);
  const jobLine = toEtaLine(jobRemain);
  const summaryLabel = jobLine
    ? `Còn ${jobLine.remainLabel} · xong lúc ${jobLine.finishLabel}`
    : null;

  return {
    stage: toEtaLine(stageRemain),
    file: toEtaLine(fileRemain),
    job: jobLine,
    legend,
    fileTotalEstSec,
    stageName,
    confidence: conf.level,
    confidenceLabel: conf.label,
    summaryLabel,
  };
}
