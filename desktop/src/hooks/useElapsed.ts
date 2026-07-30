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
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}:${String(m % 60).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
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
