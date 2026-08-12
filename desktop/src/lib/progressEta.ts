import {
  formatDurationVi,
  formatFinishAt,
  remainFromPercent,
  withinFilePercent,
} from "../hooks/useElapsed";
import type { QueueItem } from "./types";

/**
 * Weights aligned with engine/dubvi/progress.py (display stages).
 * TTS dominates wall-clock (network Edge-TTS / local XTTS) — keep ~3× the old
 * share so legend + remaining-time splits match observed duration.
 */
export const STAGE_LEGEND = [
  { key: "extracting", label: "Tách audio", weight: 5 },
  { key: "transcribing", label: "Nhận dạng lời nói", weight: 28 },
  { key: "translating", label: "Dịch", weight: 12 },
  { key: "tts", label: "Tạo giọng đọc", weight: 70 },
  { key: "aligning", label: "Căn giờ", weight: 6 },
  { key: "muxing", label: "Ghép", weight: 3 },
] as const;

const LEGEND_WEIGHT_SUM = STAGE_LEGEND.reduce((a, s) => a + s.weight, 0);

/** Fallback process-time / media-time when no completed files yet (TTS-heavy). */
const DEFAULT_PROCESS_RATE = 2.8;

/**
 * Extra wall-time scale on top of progress weights. TTS live pace is often
 * optimistic early (short segments / warm connection) — keep a residual factor
 * that eases toward 1 as the stage progresses.
 */
const TTS_EARLY_PACE_FACTOR = 2.6;

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

function stageIndexOf(stageKey: string): number {
  return STAGE_LEGEND.findIndex((s) => s.key === stageKey);
}

/** Effective work completed / total using stage weights (TTS-heavy). */
function stageWorkProgress(
  stageKey: string,
  stagePct: number,
): { done: number; total: number; activeLeft: number; future: number } {
  const activeIdx = stageIndexOf(stageKey);
  const total = LEGEND_WEIGHT_SUM;
  if (activeIdx < 0) {
    return { done: 0, total, activeLeft: 0, future: total };
  }
  const stageDone = Math.max(0, Math.min(0.99, stagePct / 100));
  let done = 0;
  for (let i = 0; i < activeIdx; i++) done += STAGE_LEGEND[i].weight;
  done += STAGE_LEGEND[activeIdx].weight * stageDone;
  const activeLeft = STAGE_LEGEND[activeIdx].weight * (1 - stageDone);
  const future = STAGE_LEGEND.slice(activeIdx + 1).reduce((a, s) => a + s.weight, 0);
  return { done, total, activeLeft, future };
}

/**
 * File remain from elapsed so far vs weighted work left.
 * Fixes optimistic ETA when early stages are fast but TTS still ahead.
 */
function remainFromWeightedPace(
  fileElapsedSec: number,
  stageKey: string,
  stagePct: number,
): { fileRemain: number | null; stageRemain: number | null; fileTotalEst: number | null } {
  if (fileElapsedSec < 6 || !stageKey) {
    return { fileRemain: null, stageRemain: null, fileTotalEst: null };
  }
  const { done, total, activeLeft, future } = stageWorkProgress(stageKey, stagePct);
  if (done < 1) {
    return { fileRemain: null, stageRemain: null, fileTotalEst: null };
  }
  const fileTotalEst = (fileElapsedSec * total) / done;
  const fileRemain = Math.max(0, Math.round(fileTotalEst - fileElapsedSec));
  const remainWeight = activeLeft + future;
  const stageRemain =
    remainWeight > 0 ? Math.round(fileRemain * (activeLeft / remainWeight)) : 0;
  return {
    fileRemain,
    stageRemain,
    fileTotalEst: Math.round(fileTotalEst),
  };
}

/** Soften optimistic live TTS pace until enough segments have finished. */
function calibrateTtsLiveRemain(remainSec: number, stagePct: number): number {
  // factor: ~2.6 early → ~1.0 after most segments
  const t = Math.max(0, Math.min(1, stagePct / 100));
  const factor = 1 + (TTS_EARLY_PACE_FACTOR - 1) * Math.pow(1 - t, 1.35);
  return Math.round(remainSec * factor);
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

  const weighted = remainFromWeightedPace(fileElapsedSec, stageKey, stagePct);

  let stageRemainLive = remainFromPercent(stageElapsedSec, stagePct, {
    minElapsed: 4,
    minPercent: 3,
  });
  if (stageRemainLive != null && stageKey === "tts") {
    stageRemainLive = calibrateTtsLiveRemain(stageRemainLive, stagePct);
  }

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

  // Prefer weighted pace (knows TTS is still ahead) over raw linear % when available.
  let fileRemain = blendRemain(weighted.fileRemain, fileRemainFromFile, 0.72);
  fileRemain = blendRemain(fileRemain, fileRemainFromJob, 0.65);
  fileRemain = blendRemain(fileRemain, seed.fileRemain, fileRemain != null ? 0.7 : 0);

  // Stage remain: calibrated live TTS first; else weighted share of file remain.
  let stageRemain = stageRemainLive;
  if (stageRemain == null) {
    stageRemain = weighted.stageRemain;
  } else if (weighted.stageRemain != null && stageKey === "tts") {
    // Keep live signal but never drop far below weight-based TTS remain early on.
    stageRemain = Math.max(stageRemain, Math.round(weighted.stageRemain * 0.85));
  }
  if (stageRemain == null && fileRemain != null && stageKey) {
    const { activeLeft, future } = stageWorkProgress(stageKey, stagePct);
    const remainWeight = activeLeft + future;
    if (remainWeight > 0) {
      stageRemain = Math.round(fileRemain * (activeLeft / remainWeight));
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
  if (weighted.fileTotalEst != null) {
    fileTotalEstSec = weighted.fileTotalEst;
  } else if (fileRemain != null && filePct > 3) {
    fileTotalEstSec = Math.round(fileElapsedSec + fileRemain);
  } else if (fileElapsedSec > 12 && filePct > 5) {
    fileTotalEstSec = Math.round((fileElapsedSec * 100) / filePct);
  } else if (seed.fileRemain != null) {
    const doneFrac = Math.max(0, Math.min(0.99, filePct / 100));
    fileTotalEstSec = Math.round(seed.fileRemain / Math.max(0.01, 1 - doneFrac));
  }

  const activeIdx = stageIndexOf(stageKey);
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
