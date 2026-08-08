import type {
  AppSettings,
  CutSegmentResult,
  DoctorReport,
  EngineEvent,
  JobOptions,
  ProbeInfo,
  QueueState,
  SegmentRow,
  WhisperModelInfo,
  XttsSpeakerOption,
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

async function ensureEngineListen(onEvent: EventHandler): Promise<void> {
  if (!(await isTauri())) return;
  const { listen } = await import("@tauri-apps/api/event");
  if (unlistenRef) {
    unlistenRef();
    unlistenRef = null;
  }
  unlistenRef = await listen<EngineEvent>("engine-event", (e) => onEvent(e.payload));
}

export async function pickVideos(): Promise<string[]> {
  return invoke<string[]>("pick_videos");
}

export async function pickOutputDir(): Promise<string | null> {
  return invoke<string | null>("pick_output_dir");
}

export async function pickDownloadDir(): Promise<string | null> {
  return invoke<string | null>("pick_download_dir");
}

export async function pickSpeakerWav(): Promise<string | null> {
  return invoke<string | null>("pick_speaker_wav");
}

export async function listXttsSpeakers(): Promise<XttsSpeakerOption[]> {
  return invoke<XttsSpeakerOption[]>("list_xtts_speakers");
}

export async function openFolder(path: string): Promise<void> {
  await invoke("open_folder", { path });
}

export async function probeVideos(paths: string[]): Promise<ProbeInfo[]> {
  return invoke<ProbeInfo[]>("probe_videos", { paths });
}

/** Clone [start, end) from an existing local video into a new file. */
export async function cutSegment(opts: {
  input: string;
  start: string;
  end: string;
  output?: string | null;
  name?: string | null;
}): Promise<CutSegmentResult> {
  return invoke<CutSegmentResult>("cut_segment", {
    input: opts.input,
    start: opts.start,
    end: opts.end,
    output: opts.output?.trim() || null,
    name: opts.name?.trim() || null,
  });
}

export interface UrlProbeInfo {
  ok: boolean;
  url: string;
  id: string;
  title: string;
  extractor?: string;
  webpage_url?: string;
  duration_sec?: number | null;
  duration_label?: string;
  size_bytes?: number | null;
  size_label?: string;
  ext?: string;
  uploader?: string;
  is_live?: boolean;
  code?: string;
  error?: string;
}

export interface UrlHelpInfo {
  summary: string;
  typically_works: string[];
  often_fails_or_unsupported: string[];
  tips: string[];
  supported_sites_url: string;
  yt_dlp_version?: string | null;
}

export async function probeUrl(url: string): Promise<UrlProbeInfo> {
  return invoke<UrlProbeInfo>("probe_url", { url });
}

export async function urlHelp(): Promise<UrlHelpInfo> {
  return invoke<UrlHelpInfo>("url_help");
}

/** Download remote video via yt-dlp; resolves to local absolute path. */
export async function downloadUrl(
  url: string,
  onEvent?: EventHandler,
  onJobId?: (jobId: string) => void,
  downloadDir?: string | null,
): Promise<string> {
  if (!(await isTauri())) throw new Error("Cần Tauri để tải video từ URL");
  const { listen } = await import("@tauri-apps/api/event");
  const dir = (downloadDir || "").trim() || null;
  return new Promise<string>((resolve, reject) => {
    let settled = false;
    let unlisten: (() => void) | null = null;
    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      unlisten?.();
      fn();
    };
    void listen<EngineEvent>("engine-event", (e) => {
      const ev = e.payload;
      onEvent?.(ev);
      if (ev.type === "completed" && (ev.output || ev.path)) {
        finish(() => resolve(String(ev.output || ev.path)));
        return;
      }
      if (ev.type === "error" && ev.fatal) {
        const msg =
          ev.friendly?.body ||
          ev.message ||
          "Không tải được video từ URL.";
        finish(() => reject(new Error(msg)));
        return;
      }
      if (ev.type === "cancelled") {
        finish(() => reject(new Error("Đã hủy tải video.")));
        return;
      }
      if (ev.type === "engine_exited") {
        const code = typeof ev.code === "number" ? ev.code : Number(ev.code);
        if (!settled && code !== 0 && !Number.isNaN(code)) {
          finish(() =>
            reject(new Error(`Tải video thất bại (mã ${code}).`)),
          );
        }
      }
    }).then((un) => {
      unlisten = un;
      invoke<string>("download_url", { url, downloadDir: dir })
        .then((jobId) => {
          if (jobId) onJobId?.(jobId);
        })
        .catch((err) => {
          finish(() => reject(err instanceof Error ? err : new Error(String(err))));
        });
    });
  });
}

export async function startJob(options: JobOptions, onEvent: EventHandler): Promise<string> {
  if (!(await isTauri())) throw new Error("Cần Tauri để bắt đầu job");
  await ensureEngineListen(onEvent);
  return invoke<string>("start_job", { options });
}

export async function cancelJob(jobId: string): Promise<void> {
  await invoke("cancel_job", { jobId });
}

export async function retryFailed(
  jobId: string,
  onEvent?: EventHandler,
  stems?: string[],
): Promise<void> {
  if (onEvent) await ensureEngineListen(onEvent);
  await invoke("retry_failed", { jobId, stems: stems ?? null });
}

export async function resumeJob(
  jobId: string,
  onEvent?: EventHandler,
  stems?: string[],
): Promise<void> {
  if (onEvent) await ensureEngineListen(onEvent);
  await invoke("resume_job", { jobId, stems: stems ?? null });
}

export async function getQueue(jobId: string): Promise<QueueState> {
  return invoke<QueueState>("get_queue", { jobId });
}

export interface EnqueueResult {
  ok: boolean;
  job_id: string;
  added: string[];
  added_count: number;
  queue?: QueueState;
}

/** Append videos to a running job — they process automatically after the current file. */
export async function enqueueVideos(
  jobId: string,
  files: string[],
): Promise<EnqueueResult> {
  return invoke<EnqueueResult>("enqueue_videos", { jobId, files });
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

export async function continueAfterReview(
  jobId: string,
  stem: string,
  onEvent?: EventHandler,
): Promise<void> {
  if (onEvent) await ensureEngineListen(onEvent);
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
