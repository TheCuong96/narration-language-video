export type AudioMode = "vi_only" | "dual_track" | "mix";
export type DeviceMode = "cpu" | "auto";
export type Page = "process" | "transcript" | "settings";

export type QueueItemStatus =
  | "pending"
  | "running"
  | "review"
  | "completed"
  | "failed"
  | "cancelled"
  | "skipped";

export interface QueueItem {
  index: number;
  input: string;
  output: string;
  stem: string;
  status: QueueItemStatus;
  error?: string | null;
  code?: string | null;
  duration_label?: string;
  size_label?: string;
  duration_sec?: number;
  size_bytes?: number;
  /** True when this file was fetched via yt-dlp URL download. */
  from_url?: boolean;
}

export interface UrlDownloadNotice {
  path: string;
  folder: string;
  fileName: string;
  sourceUrl: string;
  duration_label?: string;
  size_label?: string;
}

export interface QueueState {
  job_id: string;
  items: QueueItem[];
}

export interface SegmentRow {
  id: number;
  start: number;
  end: number;
  text_en: string;
  text_vi: string;
}

export interface FriendlyError {
  title: string;
  body: string;
  hint?: string;
}

export interface EngineEvent {
  type: string;
  ts?: string;
  stage?: string;
  message?: string;
  current?: number;
  total?: number;
  percent?: number;
  overall_percent?: number;
  stage_label?: string;
  file?: string;
  file_index?: number;
  file_total?: number;
  code?: string;
  input?: string;
  output?: string;
  job_id?: string;
  stem?: string;
  segments?: SegmentRow[];
  queue?: QueueState;
  level?: string;
  fatal?: boolean;
  friendly?: FriendlyError;
  [key: string]: unknown;
}

export interface JobOptions {
  files: string[];
  outputDir: string;
  voice: string;
  model: string;
  audioMode: AudioMode;
  mixDb: number;
  review: boolean;
  force: boolean;
  preferGpu: boolean;
  translateProvider: string;
  ttsProvider: string;
  xttsSpeakerWav?: string;
}

export interface WhisperModelInfo {
  id: string;
  label: string;
  size_mb: number;
  speed: string;
  quality: string;
  recommended_for: string;
  recommended?: boolean;
  downloaded: boolean;
  local_mb: number;
  download_root: string;
  kind?: "whisper" | "translate" | "tts" | string;
  provider?: string;
  license_note?: string;
}

export interface XttsSpeakerOption {
  id: string;
  label: string;
  path: string;
  name: string;
  default?: boolean;
}

export interface AppSettings {
  whisper_model: string;
  device_mode: DeviceMode;
  default_output_dir: string;
  /** Folder where yt-dlp saves remote videos before dubbing. */
  default_download_dir: string;
  cleanup_temps: boolean;
  mix_original_db: number;
  voice: string;
  audio_mode: AudioMode;
  review_by_default: boolean;
  translate_provider: string;
  tts_provider: string;
  xtts_speaker_wav?: string;
}

export interface ProbeInfo {
  path: string;
  name: string;
  stem: string;
  size_bytes: number;
  size_label: string;
  duration_sec: number;
  duration_label: string;
  error?: string | null;
}

export interface CutSegmentResult {
  ok: boolean;
  path: string;
  source: string;
  start_sec: number;
  end_sec: number;
  duration_sec: number;
  duration_label: string;
  size_bytes: number;
  size_label: string;
  stem: string;
  name: string;
  copied?: boolean;
  code?: string;
  error?: string;
}

export interface DoctorReport {
  ok: boolean;
  checks: { name: string; ok: boolean; path?: string; error?: string; free_mb?: number }[];
  models?: WhisperModelInfo[];
  privacy?: Record<string, unknown>;
}
