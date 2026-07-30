import type {
  AppSettings,
  DoctorReport,
  EngineEvent,
  JobOptions,
  ProbeInfo,
  QueueState,
  SegmentRow,
  WhisperModelInfo,
} from "./types";

export type EventHandler = (ev: EngineEvent) => void;

async function isTauri(): Promise<boolean> {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!(await isTauri())) {
    throw new Error("Chạy trong Tauri để gọi engine (npm run tauri dev).");
  }
  const { invoke: tauriInvoke } = await import("@tauri-apps/api/core");
  return tauriInvoke<T>(cmd, args);
}

let unlistenRef: (() => void) | null = null;

export async function pickVideos(): Promise<string[]> {
  return invoke<string[]>("pick_videos");
}

export async function pickOutputDir(): Promise<string | null> {
  return invoke<string | null>("pick_output_dir");
}

export async function openFolder(path: string): Promise<void> {
  await invoke("open_folder", { path });
}

export async function probeVideos(paths: string[]): Promise<ProbeInfo[]> {
  return invoke<ProbeInfo[]>("probe_videos", { paths });
}

export async function startJob(options: JobOptions, onEvent: EventHandler): Promise<string> {
  if (!(await isTauri())) throw new Error("Cần Tauri để bắt đầu job");
  const { listen } = await import("@tauri-apps/api/event");
  if (unlistenRef) {
    unlistenRef();
    unlistenRef = null;
  }
  unlistenRef = await listen<EngineEvent>("engine-event", (e) => onEvent(e.payload));
  return invoke<string>("start_job", { options });
}

export async function cancelJob(jobId: string): Promise<void> {
  await invoke("cancel_job", { jobId });
}

export async function retryFailed(jobId: string, stems?: string[]): Promise<void> {
  await invoke("retry_failed", { jobId, stems: stems ?? null });
}

export async function getQueue(jobId: string): Promise<QueueState> {
  return invoke<QueueState>("get_queue", { jobId });
}

export async function reviewGet(jobId: string, stem: string): Promise<{ segments: SegmentRow[] }> {
  return invoke("review_get", { jobId, stem });
}

export async function reviewSet(
  jobId: string,
  stem: string,
  segments: SegmentRow[],
): Promise<void> {
  await invoke("review_set", { jobId, stem, segments });
}

export async function continueAfterReview(jobId: string, stem: string): Promise<void> {
  await invoke("continue_after_review", { jobId, stem });
}

export async function listModels(): Promise<WhisperModelInfo[]> {
  return invoke("list_models");
}

export async function downloadModel(modelId: string, onEvent?: EventHandler): Promise<void> {
  if (onEvent && (await isTauri())) {
    const { listen } = await import("@tauri-apps/api/event");
    const un = await listen<EngineEvent>("engine-event", (e) => onEvent(e.payload));
    try {
      await invoke("download_model", { modelId });
    } finally {
      un();
    }
    return;
  }
  await invoke("download_model", { modelId });
}

export async function deleteModel(modelId: string): Promise<void> {
  await invoke("delete_model", { modelId });
}

export async function getSettings(): Promise<AppSettings> {
  return invoke("get_settings");
}

export async function saveSettings(settings: AppSettings): Promise<void> {
  await invoke("save_settings", { settings });
}

export async function doctor(): Promise<DoctorReport> {
  return invoke("doctor");
}

export async function privacyNotice(): Promise<Record<string, unknown>> {
  return invoke("privacy_notice");
}

export function filterVideoFiles(files: FileList | File[]): File[] {
  const exts = [".mp4", ".mkv", ".mov", ".avi", ".webm"];
  return Array.from(files).filter((f) =>
    exts.some((e) => f.name.toLowerCase().endsWith(e)),
  );
}
