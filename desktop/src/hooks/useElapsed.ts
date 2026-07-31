import { useEffect, useState } from "react";

export function useElapsed(running: boolean, resetKey?: string | null) {
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    if (running) {
      setStartedAt(Date.now());
      setElapsedSec(0);
    } else {
      setStartedAt(null);
    }
  }, [running, resetKey]);

  useEffect(() => {
    if (!running || startedAt == null) return;
    const id = window.setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, [running, startedAt]);

  return elapsedSec;
}

export function formatElapsed(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}:${String(m % 60).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  }
  return `${m}:${String(r).padStart(2, "0")}`;
}

/** Clock time when `remainSec` elapses from now (local HH:mm). */
export function formatFinishClock(remainSec: number): string {
  const t = new Date(Date.now() + Math.max(0, remainSec) * 1000);
  return `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
}

/**
 * Remaining seconds from linear progress: elapsed * (100 - pct) / pct.
 * Returns null until enough signal to avoid wild early guesses.
 */
export function remainFromPercent(
  elapsedSec: number,
  percent: number,
  opts?: { minElapsed?: number; minPercent?: number; maxRemain?: number },
): number | null {
  const minElapsed = opts?.minElapsed ?? 6;
  const minPercent = opts?.minPercent ?? 2;
  const maxRemain = opts?.maxRemain ?? 48 * 3600;
  if (percent >= 99.5) return 0;
  if (percent < minPercent || elapsedSec < minElapsed) return null;
  const remain = Math.round((elapsedSec * (100 - percent)) / percent);
  if (remain < 0 || remain > maxRemain) return null;
  return remain;
}

/** Rough ETA from completed/total items and elapsed. */
export function estimateEta(
  elapsedSec: number,
  completed: number,
  total: number,
): string | null {
  if (completed <= 0 || elapsedSec < 5 || total <= completed) return null;
  const per = elapsedSec / completed;
  const remain = Math.round(per * (total - completed));
  return formatElapsed(remain);
}

/** Within-file percent 0..100 from job overall percent + file index. */
export function withinFilePercent(
  overallPct: number,
  fileIndex: number,
  fileTotal: number,
): number {
  if (fileTotal <= 1) return Math.max(0, Math.min(100, overallPct));
  const idx = Math.max(1, fileIndex);
  const base = ((idx - 1) / fileTotal) * 100;
  const span = 100 / fileTotal;
  if (span <= 0) return 0;
  return Math.max(0, Math.min(100, ((overallPct - base) / span) * 100));
}
