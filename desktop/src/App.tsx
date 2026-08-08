import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { ErrorDialog } from "./components/ErrorDialog";
import {
  cancelJob,
  continueAfterReview,
  deleteModel,
  doctor as runDoctor,
  downloadModel,
  cutSegment,
  downloadUrl,
  filterVideoFiles,
  getQueue,
  getSettings,
  listModels,
  listXttsSpeakers,
  openFolder,
  pickDownloadDir,
  pickOutputDir,
  pickSpeakerWav,
  pickVideos,
  probeVideos,
  resumeJob,
  retryFailed,
  reviewGet,
  reviewSet,
  saveSettings,
  startJob,
  urlHelp as fetchUrlHelp,
  type UrlHelpInfo,
} from "./lib/engine";
import type {
  AppSettings,
  AudioMode,
  DoctorReport,
  EngineEvent,
  FriendlyError,
  Page,
  QueueItem,
  SegmentRow,
  UrlDownloadNotice,
  WhisperModelInfo,
  XttsSpeakerOption,
} from "./lib/types";

function parentDir(path: string): string {
  const i = Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"));
  return i >= 0 ? path.slice(0, i) : path;
}

function baseName(path: string): string {
  const i = Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"));
  return i >= 0 ? path.slice(i + 1) : path;
}

function stemName(path: string): string {
  return baseName(path).replace(/\.[^.]+$/, "");
}

/** Suggested clip stem from source + time range (no extension). */
function suggestCloneName(source: string, start: string, end: string): string {
  const stem = stemName(source) || "clip";
  const tag = (t: string) => t.trim().replace(/:/g, "-") || "0";
  return `${stem}_clip_${tag(start)}-${tag(end || "end")}`;
}
import { useElapsed } from "./hooks/useElapsed";
import { ClonePage } from "./pages/ClonePage";
import { DownloadPage } from "./pages/DownloadPage";
import { DubPage } from "./pages/DubPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TranscriptPage } from "./pages/TranscriptPage";

const defaultSettings: AppSettings = {
  whisper_model: "small",
  device_mode: "cpu",
  default_output_dir: "",
  default_download_dir: "",
  cleanup_temps: true,
  mix_original_db: -18,
  voice: "vi-VN-HoaiMyNeural",
  audio_mode: "vi_only",
  review_by_default: false,
  translate_provider: "deep-translator",
  tts_provider: "edge-tts",
  xtts_speaker_wav: "",
};

function friendlyLine(ev: EngineEvent): { text: string; cls?: string } {
  switch (ev.type) {
    case "stage":
      return { text: ev.message || ev.stage || "..." };
    case "progress":
      return { text: `${ev.message || ev.stage}: ${ev.current}/${ev.total}` };
    case "warning":
      return { text: `⚠ ${ev.message}`, cls: "warn" };
    case "error":
      return { text: `✗ ${ev.friendly?.title || ev.message}`, cls: "error" };
    case "file_completed":
      return { text: `✓ ${ev.output}` };
    case "review_ready":
      return { text: `⏸ ${ev.message}`, cls: "warn" };
    case "completed":
      return { text: "Hoàn tất" };
    case "log":
      return { text: ev.message || "", cls: ev.level === "warn" ? "warn" : undefined };
    default:
      return { text: ev.message || ev.type };
  }
}

export default function App() {
  const [page, setPage] = useState<Page>("dub");
  const [files, setFiles] = useState<string[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [outputDir, setOutputDir] = useState("");
  const [voice, setVoice] = useState(defaultSettings.voice);
  const [model, setModel] = useState(defaultSettings.whisper_model);
  const [audioMode, setAudioMode] = useState<AudioMode>("vi_only");
  const [mixDb, setMixDb] = useState(-18);
  const [review, setReview] = useState(false);
  const [force, setForce] = useState(false);
  const [preferGpu, setPreferGpu] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [logs, setLogs] = useState<{ text: string; cls?: string }[]>([]);
  const [stageLabel, setStageLabel] = useState("Sẵn sàng");
  const [fileProgress, setFileProgress] = useState({
    current: 0,
    total: 0,
    percent: 0,
    message: "",
    stageLabel: "",
    stage: "",
  });
  const [overallProgress, setOverallProgress] = useState({
    percent: 0,
    fileIndex: 0,
    fileTotal: 0,
    fileName: "",
  });
  /** Wall-clock seconds for each completed file in the current job. */
  const [completedElapsedSec, setCompletedElapsedSec] = useState<number[]>([]);
  const [reviewStem, setReviewStem] = useState<string | null>(null);
  const [segments, setSegments] = useState<SegmentRow[]>([]);
  const [errOpen, setErrOpen] = useState(false);
  const [errFriendly, setErrFriendly] = useState<FriendlyError | null>(null);
  const [errTech, setErrTech] = useState("");
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [models, setModels] = useState<WhisperModelInfo[]>([]);
  const [xttsSpeakers, setXttsSpeakers] = useState<XttsSpeakerOption[]>([]);
  const [doctorReport, setDoctorReport] = useState<DoctorReport | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadPct, setDownloadPct] = useState(0);
  const [urlInput, setUrlInput] = useState("");
  const [downloadDir, setDownloadDir] = useState("");
  const [urlHelp, setUrlHelp] = useState<UrlHelpInfo | null>(null);
  const [downloadingUrl, setDownloadingUrl] = useState(false);
  const [lastUrlDownload, setLastUrlDownload] = useState<UrlDownloadNotice | null>(
    null,
  );
  const [cloneSource, setCloneSource] = useState("");
  const [cloneStart, setCloneStart] = useState("0");
  const [cloneEnd, setCloneEnd] = useState("");
  const [cloneName, setCloneName] = useState("");
  const [cloningSegment, setCloningSegment] = useState(false);
  const cloneNameTouchedRef = useRef(false);
  const urlJobIdRef = useRef<string | null>(null);
  const urlDownloadedPathsRef = useRef<Set<string>>(new Set());

  const refreshXttsSpeakers = useCallback(async () => {
    try {
      const speakers = await listXttsSpeakers();
      setXttsSpeakers(speakers);
      setSettings((s) => {
        if (s.xtts_speaker_wav || !speakers.length) return s;
        const preferred =
          speakers.find((x) => x.default)?.path || speakers[0]?.path || "";
        return preferred ? { ...s, xtts_speaker_wav: preferred } : s;
      });
    } catch {
      setXttsSpeakers([]);
    }
  }, []);
  /** Avoid duplicate dialogs when engine emits error then exits. */
  const sawTerminalRef = useRef(false);
  /** User pressed Stop — don't treat taskkill exit as a crash dialog. */
  const userStoppedRef = useRef(false);
  /** Job was stopped and can be resumed from the same job id / stage cache. */
  const [canResume, setCanResume] = useState(false);

  const elapsedSec = useElapsed(
    busy || downloadingUrl,
    jobId || (downloadingUrl ? "url-download" : null),
  );

  const pushLog = useCallback((line: { text: string; cls?: string }) => {
    if (!line.text) return;
    setLogs((prev) => [...prev.slice(-500), line]);
  }, []);

  const onEngineEvent = useCallback(
    (ev: EngineEvent) => {
      pushLog(friendlyLine(ev));
      if (ev.type === "queue_updated" && ev.queue?.items) {
        setQueue((prev) => {
          const meta = new Map(prev.map((p) => [p.stem, p]));
          return ev.queue!.items.map((it) => {
            const prevItem = meta.get(it.stem);
            const fromUrl =
              Boolean(prevItem?.from_url) ||
              urlDownloadedPathsRef.current.has(it.input);
            return {
              ...it,
              duration_label: prevItem?.duration_label,
              size_label: prevItem?.size_label,
              duration_sec: prevItem?.duration_sec,
              size_bytes: prevItem?.size_bytes,
              from_url: fromUrl || prevItem?.from_url,
            };
          });
        });
      }
      if (ev.type === "stage") {
        setStageLabel(ev.message || (ev.stage_label as string) || ev.stage || "");
      }
      if (ev.type === "progress") {
        if (ev.stage === "downloading_model") {
          setDownloadPct(
            typeof ev.percent === "number" ? ev.percent : ev.current || 0,
          );
        } else if (ev.stage === "downloading_video") {
          const stagePct =
            typeof ev.percent === "number"
              ? ev.percent
              : ev.total
                ? Math.round((100 * (ev.current || 0)) / ev.total)
                : 0;
          setFileProgress({
            current: ev.current || 0,
            total: ev.total || 100,
            percent: stagePct,
            message: ev.message || "Đang tải video…",
            stageLabel: (ev.stage_label as string) || "Tải video",
            stage: ev.stage || "downloading_video",
          });
          setOverallProgress({
            percent: stagePct,
            fileIndex: 1,
            fileTotal: 1,
            fileName: "",
          });
          if (ev.message || ev.stage_label) {
            setStageLabel(String(ev.message || ev.stage_label || "Đang tải video…"));
          }
        } else {
          const stagePct =
            typeof ev.percent === "number"
              ? ev.percent
              : ev.total
                ? Math.round((100 * (ev.current || 0)) / ev.total)
                : 0;
          const overallPct =
            typeof ev.overall_percent === "number"
              ? ev.overall_percent
              : stagePct;
          setFileProgress({
            current: ev.current || 0,
            total: ev.total || 0,
            percent: stagePct,
            message: ev.message || ev.stage || "",
            stageLabel: (ev.stage_label as string) || ev.stage || "",
            stage: ev.stage || "",
          });
          setOverallProgress({
            percent: overallPct,
            fileIndex: (ev.file_index as number) || 0,
            fileTotal: (ev.file_total as number) || 0,
            fileName: (ev.file as string) || "",
          });
          if (ev.message || ev.stage_label) {
            setStageLabel(
              String(ev.message || ev.stage_label || ev.stage || ""),
            );
          }
        }
      }
      if (ev.type === "stage" && ev.stage) {
        setFileProgress((p) => ({
          ...p,
          stage: ev.stage || p.stage,
          stageLabel: (ev.stage_label as string) || p.stageLabel,
        }));
      }
      if (ev.type === "file_completed") {
        setFileProgress((p) => ({ ...p, percent: 100, message: "Xong file này" }));
        const mins = ev.elapsed_min;
        const skipped = Boolean(ev.skipped);
        if (typeof mins === "number" && mins > 0 && !skipped) {
          setCompletedElapsedSec((prev) => [...prev, Math.round(mins * 60)]);
        }
      }
      if (ev.type === "completed") {
        setOverallProgress((p) => ({ ...p, percent: 100 }));
        setFileProgress((p) => ({ ...p, percent: 100, message: "Hoàn tất" }));
        setStageLabel("Hoàn tất");
        setCanResume(false);
      }
      if (ev.type === "review_ready" && ev.stem && ev.segments) {
        setReviewStem(ev.stem);
        setSegments(ev.segments);
        setPage("transcript");
      }
      if (ev.type === "error" && ev.fatal) {
        sawTerminalRef.current = true;
        setErrFriendly(ev.friendly || { title: "Lỗi", body: ev.message || "" });
        setErrTech(JSON.stringify(ev, null, 2));
        setErrOpen(true);
        setBusy(false);
      }
      if (ev.type === "completed" || ev.type === "cancelled") {
        sawTerminalRef.current = true;
        setBusy(false);
        if (ev.type === "cancelled") {
          setCanResume(true);
          setStageLabel("Đã tạm dừng — bấm Tiếp tục để xử lý tiếp");
        }
        if (downloading) {
          setDownloading(null);
          setDownloadPct(0);
        }
      }
      if (ev.type === "engine_exited") {
        const code = typeof ev.code === "number" ? ev.code : Number(ev.code);
        setBusy(false);
        if (downloading) {
          setDownloading(null);
          setDownloadPct(0);
        }
        if (userStoppedRef.current || code === 2) {
          userStoppedRef.current = false;
          sawTerminalRef.current = true;
          setStageLabel("Đã tạm dừng — bấm Tiếp tục để xử lý tiếp");
          setCanResume(true);
        } else if (
          !sawTerminalRef.current &&
          code !== 0 &&
          code !== 3 &&
          !Number.isNaN(code)
        ) {
          sawTerminalRef.current = true;
          setStageLabel(`Engine lỗi (code ${code})`);
          setErrFriendly({
            title: "Engine dừng bất thường",
            body: `Tiến trình xử lý kết thúc với mã ${code}. Thử Bắt đầu lại. Nếu lỗi lặp lại, chạy scripts/build-engine.ps1 rồi cài lại.`,
          });
          setErrTech(String(ev.message || `exit code ${code}`));
          setErrOpen(true);
        }
      }
    },
    [pushLog, downloading],
  );

  useEffect(() => {
    (async () => {
      try {
        const s = await getSettings();
        setSettings({ ...defaultSettings, ...s });
        setModel(s.whisper_model);
        setVoice(s.voice);
        setAudioMode(s.audio_mode);
        setMixDb(s.mix_original_db);
        setReview(s.review_by_default);
        setPreferGpu(s.device_mode === "auto");
        if (s.default_output_dir) setOutputDir(s.default_output_dir);
        if (s.default_download_dir) setDownloadDir(s.default_download_dir);
      } catch {
        /* browser preview */
      }
      try {
        setModels(await listModels());
      } catch {
        /* ignore */
      }
      try {
        setXttsSpeakers(await listXttsSpeakers());
      } catch {
        /* ignore */
      }
      try {
        setUrlHelp(await fetchUrlHelp());
      } catch {
        /* browser preview / engine missing */
      }
    })();
  }, []);

  useEffect(() => {
    let un: (() => void) | undefined;
    (async () => {
      try {
        if (!("__TAURI_INTERNALS__" in window)) return;
        const { getCurrentWebview } = await import("@tauri-apps/api/webview");
        un = await getCurrentWebview().onDragDropEvent((event) => {
          if (event.payload.type === "over") setDragOver(true);
          else if (event.payload.type === "leave") setDragOver(false);
          else if (event.payload.type === "drop") {
            setDragOver(false);
            const paths = (event.payload.paths || []).filter((p) =>
              /\.(mp4|mkv|mov|avi|webm)$/i.test(p),
            );
            if (paths.length) void addFiles(paths);
          }
        });
      } catch {
        /* ignore */
      }
    })();
    return () => un?.();
  }, []);

  async function addFiles(paths: string[], opts?: { fromUrl?: boolean }) {
    const merged = Array.from(new Set([...files, ...paths]));
    setFiles(merged);
    if (opts?.fromUrl) {
      for (const p of paths) urlDownloadedPathsRef.current.add(p);
    }
    const nextSource = cloneSource || paths[0] || "";
    if (!cloneSource && paths[0]) {
      setCloneSource(paths[0]);
    }
    try {
      const probed = await probeVideos(merged);
      setQueue(
        probed.map((p, i) => ({
          index: i,
          input: p.path,
          output: "",
          stem: p.stem,
          status: "pending",
          duration_label: p.duration_label,
          size_label: p.size_label,
          duration_sec: p.duration_sec,
          size_bytes: p.size_bytes,
          from_url: urlDownloadedPathsRef.current.has(p.path),
        })),
      );
      let endForSuggest = cloneEnd.trim();
      if (!endForSuggest) {
        const srcPath = nextSource;
        const info = probed.find((p) => p.path === srcPath) || probed[0];
        if (info?.duration_sec && info.duration_sec > 0) {
          endForSuggest = String(Math.floor(info.duration_sec));
          setCloneEnd(endForSuggest);
        }
      }
      if (nextSource && !cloneNameTouchedRef.current) {
        setCloneName(suggestCloneName(nextSource, cloneStart, endForSuggest));
      }
      return probed;
    } catch {
      setQueue(
        merged.map((f, i) => ({
          index: i,
          input: f,
          output: "",
          stem: f.replace(/^.*[\\/]/, "").replace(/\.[^.]+$/, ""),
          status: "pending",
          from_url: urlDownloadedPathsRef.current.has(f),
        })),
      );
      return null;
    }
  }

  async function onPickFiles() {
    if (busy || downloadingUrl) return;
    try {
      const picked = await pickVideos();
      if (picked?.length) await addFiles(picked);
    } catch (e) {
      pushLog({ text: String(e), cls: "warn" });
    }
  }

  async function onDownloadUrl() {
    const url = urlInput.trim();
    if (!url || busy || downloadingUrl) return;
    setDownloadingUrl(true);
    sawTerminalRef.current = false;
    userStoppedRef.current = false;
    setCanResume(false);
    setStageLabel("Đang tải video từ URL…");
    setFileProgress({
      current: 0,
      total: 100,
      percent: 0,
      message: "Đang khởi động yt-dlp…",
      stageLabel: "Tải video",
      stage: "downloading_video",
    });
    setOverallProgress({
      percent: 0,
      fileIndex: 1,
      fileTotal: 1,
      fileName: "",
    });
    pushLog({ text: `Tải URL: ${url}` });
    try {
      const path = await downloadUrl(
        url,
        onEngineEvent,
        (id) => {
          urlJobIdRef.current = id;
        },
        downloadDir.trim() || null,
      );
      pushLog({ text: `Đã tải: ${path}` });
      const sourceUrl = url;
      setUrlInput("");
      const probed = await addFiles([path], { fromUrl: true });
      const info = probed?.find((p) => p.path === path);
      setLastUrlDownload({
        path,
        folder: parentDir(path),
        fileName: baseName(path),
        sourceUrl,
        duration_label: info?.duration_label,
        size_label: info?.size_label,
      });
      setStageLabel("Đã tải video về máy — kiểm tra thư mục rồi Bắt đầu");
      setFileProgress((p) => ({
        ...p,
        percent: 100,
        message: `Đã lưu: ${baseName(path)}`,
        stageLabel: "Tải video",
      }));
      setOverallProgress((p) => ({ ...p, percent: 100 }));
    } catch (e) {
      const msg = String(e);
      if (!userStoppedRef.current) {
        setErrFriendly({
          title: "Không tải được video",
          body: msg,
        });
        setErrTech(msg);
        setErrOpen(true);
        setStageLabel("Tải URL thất bại");
      } else {
        setStageLabel("Đã hủy tải URL");
      }
      pushLog({ text: msg, cls: "error" });
    } finally {
      setDownloadingUrl(false);
      urlJobIdRef.current = null;
      userStoppedRef.current = false;
    }
  }

  async function onPickOut() {
    if (busy || downloadingUrl) return;
    try {
      const dir = await pickOutputDir();
      if (dir) setOutputDir(dir);
    } catch (e) {
      pushLog({ text: String(e), cls: "warn" });
    }
  }

  async function onPickDownloadDir() {
    if (busy || downloadingUrl) return;
    try {
      const dir = await pickDownloadDir();
      if (dir) setDownloadDir(dir);
    } catch (e) {
      pushLog({ text: String(e), cls: "warn" });
    }
  }

  function refreshCloneNameSuggestion(
    source: string,
    start: string,
    end: string,
    force = false,
  ) {
    if (!source) return;
    if (force || !cloneNameTouchedRef.current) {
      setCloneName(suggestCloneName(source, start, end));
    }
  }

  function onPickCloneSource(path: string) {
    setCloneSource(path);
    const item = queue.find((q) => q.input === path);
    let end = cloneEnd.trim();
    if (item?.duration_sec && item.duration_sec > 0 && !end) {
      end = String(Math.floor(item.duration_sec));
      setCloneEnd(end);
    }
    cloneNameTouchedRef.current = false;
    refreshCloneNameSuggestion(path, cloneStart, end, true);
    pushLog({ text: `Chọn nguồn clone: ${baseName(path)}` });
  }

  function onCloneSourceChange(path: string) {
    setCloneSource(path);
    if (!path) return;
    const item = queue.find((q) => q.input === path);
    let end = cloneEnd.trim();
    if (item?.duration_sec && item.duration_sec > 0 && !end) {
      end = String(Math.floor(item.duration_sec));
      setCloneEnd(end);
    }
    cloneNameTouchedRef.current = false;
    refreshCloneNameSuggestion(path, cloneStart, end, true);
  }

  function onCloneStartChange(v: string) {
    setCloneStart(v);
    refreshCloneNameSuggestion(cloneSource, v, cloneEnd);
  }

  function onCloneEndChange(v: string) {
    setCloneEnd(v);
    refreshCloneNameSuggestion(cloneSource, cloneStart, v);
  }

  function onCloneNameChange(v: string) {
    cloneNameTouchedRef.current = true;
    setCloneName(v);
  }

  async function onCloneSegment() {
    const input = cloneSource.trim();
    const start = cloneStart.trim();
    const end = cloneEnd.trim();
    const name = cloneName.trim();
    if (!input || !start || !end || !name || busy || downloadingUrl || cloningSegment) {
      return;
    }
    setCloningSegment(true);
    pushLog({
      text: `Clone «${name}» · ${start} → ${end} từ ${baseName(input)}`,
    });
    try {
      const result = await cutSegment({ input, start, end, name });
      pushLog({
        text: `Đã tạo clip: ${result.name} (${result.duration_label || "—"})`,
      });
      await addFiles([result.path]);
      setCloneSource(result.path);
      cloneNameTouchedRef.current = false;
      setCloneName(suggestCloneName(result.path, "0", end));
      setCloneStart("0");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrFriendly({
        title: "Không clone được đoạn video",
        body: msg,
      });
      setErrTech(msg);
      setErrOpen(true);
      pushLog({ text: msg, cls: "error" });
    } finally {
      setCloningSegment(false);
    }
  }

  function onBrowserDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (busy || downloadingUrl) return;
    const list = filterVideoFiles(e.dataTransfer.files);
    if (!list.length) return;
    pushLog({
      text: "Kéo-thả trong trình duyệt không có đường dẫn đầy đủ — hãy dùng app Tauri.",
      cls: "warn",
    });
  }

  async function onStart() {
    if (!files.length || !outputDir) {
      setErrFriendly({
        title: "Thiếu thông tin",
        body: "Hãy chọn video và thư mục đầu ra.",
      });
      setErrTech("files/output missing");
      setErrOpen(true);
      return;
    }
    setBusy(true);
    sawTerminalRef.current = false;
    userStoppedRef.current = false;
    setCanResume(false);
    setLogs([]);
    setFileProgress({
      current: 0,
      total: 0,
      percent: 0,
      message: "Đang khởi động…",
      stageLabel: "",
      stage: "",
    });
    setOverallProgress({
      percent: 0,
      fileIndex: 1,
      fileTotal: files.length,
      fileName: "",
    });
    setCompletedElapsedSec([]);
    try {
      const id = await startJob(
        {
          files,
          outputDir,
          voice,
          model,
          audioMode,
          mixDb,
          review,
          force,
          preferGpu,
          translateProvider: settings.translate_provider || "deep-translator",
          ttsProvider: settings.tts_provider || "edge-tts",
          xttsSpeakerWav: settings.xtts_speaker_wav || "",
        },
        onEngineEvent,
      );
      setJobId(id);
      setStageLabel("Đang xử lý tuần tự…");
    } catch (e) {
      setBusy(false);
      setErrFriendly({ title: "Không bắt đầu được", body: String(e) });
      setErrTech(String(e));
      setErrOpen(true);
    }
  }

  async function onStop() {
    userStoppedRef.current = true;
    if (downloadingUrl) {
      const id = urlJobIdRef.current || jobId;
      try {
        if (id) await cancelJob(id);
      } catch (e) {
        pushLog({ text: String(e), cls: "warn" });
      }
      setDownloadingUrl(false);
      setStageLabel("Đã hủy tải URL");
      return;
    }
    if (!jobId) {
      setBusy(false);
      setStageLabel("Đã tạm dừng");
      return;
    }
    // Optimistic UI: mark in-flight items cancelled so Tiếp tục can show.
    setQueue((prev) =>
      prev.map((it) =>
        it.status === "running" ? { ...it, status: "cancelled" } : it,
      ),
    );
    setCanResume(true);
    try {
      await cancelJob(jobId);
      setStageLabel("Đã tạm dừng — bấm Tiếp tục để xử lý tiếp");
      setBusy(false);
      try {
        const q = await getQueue(jobId);
        if (q?.items?.length) {
          setQueue((prev) => {
            const meta = new Map(prev.map((p) => [p.stem, p]));
            return q.items.map((it) => {
              const prevItem = meta.get(it.stem);
              return {
                ...it,
                duration_label: prevItem?.duration_label,
                size_label: prevItem?.size_label,
                duration_sec: prevItem?.duration_sec,
                size_bytes: prevItem?.size_bytes,
                from_url:
                  Boolean(prevItem?.from_url) ||
                  urlDownloadedPathsRef.current.has(it.input),
              };
            });
          });
          const resumable = q.items.some((it) =>
            ["pending", "failed", "cancelled", "running"].includes(it.status),
          );
          setCanResume(resumable);
        }
      } catch {
        /* keep optimistic state */
      }
    } catch (e) {
      pushLog({ text: String(e), cls: "error" });
      // Unblock UI even if cancel CLI/engine fails
      setBusy(false);
      setStageLabel("Đã tạm dừng (ép) — bấm Tiếp tục để xử lý tiếp");
      setCanResume(true);
    }
  }

  async function onResume() {
    if (!jobId) return;
    setBusy(true);
    sawTerminalRef.current = false;
    userStoppedRef.current = false;
    setCanResume(false);
    setStageLabel("Đang tiếp tục từ công đoạn đã dừng…");
    try {
      await resumeJob(jobId, onEngineEvent);
    } catch (e) {
      setBusy(false);
      setCanResume(true);
      pushLog({ text: String(e), cls: "error" });
      setErrFriendly({
        title: "Không tiếp tục được",
        body: String(e),
      });
      setErrTech(String(e));
      setErrOpen(true);
    }
  }

  async function onRetry() {
    if (!jobId) return;
    setBusy(true);
    sawTerminalRef.current = false;
    userStoppedRef.current = false;
    setCanResume(false);
    try {
      await retryFailed(jobId, onEngineEvent);
    } catch (e) {
      setBusy(false);
      pushLog({ text: String(e), cls: "error" });
    }
  }

  async function loadReview(stem: string) {
    if (!jobId) return;
    try {
      const data = await reviewGet(jobId, stem);
      setReviewStem(stem);
      setSegments(data.segments);
      setPage("transcript");
    } catch (e) {
      pushLog({ text: String(e), cls: "error" });
    }
  }

  async function saveAndContinue() {
    if (!jobId || !reviewStem) return;
    setBusy(true);
    sawTerminalRef.current = false;
    try {
      await reviewSet(jobId, reviewStem, segments);
      await continueAfterReview(jobId, reviewStem, onEngineEvent);
      setStageLabel(`Tạo giọng đọc: ${reviewStem}`);
      setPage("dub");
    } catch (e) {
      setBusy(false);
      setErrFriendly({ title: "Không tiếp tục được", body: String(e) });
      setErrTech(String(e));
      setErrOpen(true);
    }
  }

  async function onPickCloneFile() {
    if (busy || downloadingUrl || cloningSegment) return;
    try {
      const paths = await pickVideos();
      const path = paths[0];
      if (!path) return;
      setCloneSource(path);
      let end = cloneEnd.trim();
      try {
        const infos = await probeVideos([path]);
        const d = infos[0]?.duration_sec;
        if (typeof d === "number" && d > 0 && !end) {
          end = String(Math.floor(d));
          setCloneEnd(end);
        }
      } catch {
        /* optional probe */
      }
      cloneNameTouchedRef.current = false;
      refreshCloneNameSuggestion(path, cloneStart, end || cloneEnd, true);
      pushLog({ text: `Chọn nguồn clone: ${baseName(path)}` });
    } catch (e) {
      pushLog({ text: String(e), cls: "warn" });
    }
  }

  function goCloneWithSource(path: string) {
    onPickCloneSource(path);
    setPage("clone");
  }

  return (
    <div className="app">
      <header className="brand">
        <div>
          <h1>Dub VI</h1>
          <p>Tải video · cắt đoạn · lồng tiếng Việt — chọn tab theo việc cần làm.</p>
        </div>
        <nav className="tabs">
          {(
            [
              ["download", "Tải từ liên kết"],
              ["clone", "Clone đoạn"],
              ["dub", "Lồng tiếng"],
              ["settings", "Settings"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={page === id ? "tab active" : "tab"}
              onClick={() => setPage(id)}
            >
              {label}
            </button>
          ))}
          {page === "transcript" ? (
            <button
              type="button"
              className="tab active"
              onClick={() => setPage("transcript")}
            >
              Transcript
            </button>
          ) : null}
        </nav>
      </header>

      {page === "download" && (
        <DownloadPage
          urlInput={urlInput}
          downloadDir={downloadDir}
          urlHelp={urlHelp}
          downloadingUrl={downloadingUrl}
          lastUrlDownload={lastUrlDownload}
          busy={busy}
          stageLabel={stageLabel}
          elapsedSec={elapsedSec}
          fileProgress={fileProgress}
          onChangeUrl={setUrlInput}
          onChangeDownloadDir={setDownloadDir}
          onPickDownloadDir={() => void onPickDownloadDir()}
          onDownloadUrl={() => void onDownloadUrl()}
          onStop={onStop}
          onOpenDownloadFolder={() => {
            if (lastUrlDownload?.folder) void openFolder(lastUrlDownload.folder);
          }}
          onDismissDownloadNotice={() => setLastUrlDownload(null)}
          onGoDub={() => setPage("dub")}
        />
      )}

      {page === "clone" && (
        <ClonePage
          cloneSource={cloneSource}
          cloneStart={cloneStart}
          cloneEnd={cloneEnd}
          cloneName={cloneName}
          cloningSegment={cloningSegment}
          busy={busy}
          downloadingUrl={downloadingUrl}
          queue={queue}
          onCloneSource={onCloneSourceChange}
          onCloneStart={onCloneStartChange}
          onCloneEnd={onCloneEndChange}
          onCloneName={onCloneNameChange}
          onCloneSegment={() => void onCloneSegment()}
          onPickCloneFile={() => void onPickCloneFile()}
          onGoDub={() => setPage("dub")}
        />
      )}

      {page === "dub" && (
        <DubPage
          files={files}
          queue={queue}
          outputDir={outputDir}
          voice={voice}
          model={model}
          audioMode={audioMode}
          mixDb={mixDb}
          review={review}
          force={force}
          preferGpu={preferGpu}
          ttsProvider={settings.tts_provider || "edge-tts"}
          xttsSpeakers={xttsSpeakers}
          xttsSpeakerWav={settings.xtts_speaker_wav || ""}
          busy={busy}
          canResume={canResume}
          downloadingUrl={downloadingUrl}
          stageLabel={stageLabel}
          fileProgress={fileProgress}
          overallProgress={overallProgress}
          elapsedSec={elapsedSec}
          completedElapsedSec={completedElapsedSec}
          dragOver={dragOver}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onBrowserDrop}
          onPickFiles={onPickFiles}
          onPickOut={onPickOut}
          onChangeOutput={setOutputDir}
          onVoice={setVoice}
          onXttsSpeaker={(path) =>
            setSettings((s) => ({ ...s, xtts_speaker_wav: path }))
          }
          onModel={setModel}
          onAudioMode={setAudioMode}
          onMixDb={setMixDb}
          onReview={setReview}
          onForce={setForce}
          onGpu={setPreferGpu}
          onStart={onStart}
          onStop={onStop}
          onResume={onResume}
          onRetry={onRetry}
          onOpenOut={() => outputDir && openFolder(outputDir)}
          onOpenReview={loadReview}
          onGoClone={goCloneWithSource}
        />
      )}

      {page === "transcript" && (
        <TranscriptPage
          stem={reviewStem}
          segments={segments}
          onChange={setSegments}
          onSaveContinue={saveAndContinue}
          busy={busy}
        />
      )}

      {page === "settings" && (
        <SettingsPage
          settings={settings}
          models={models}
          doctor={doctorReport}
          downloading={downloading}
          downloadPct={downloadPct}
          xttsSpeakers={xttsSpeakers}
          busy={busy}
          onChange={setSettings}
          onSave={async () => {
            try {
              await saveSettings(settings);
              setModel(settings.whisper_model);
              setVoice(settings.voice);
              setAudioMode(settings.audio_mode);
              setMixDb(settings.mix_original_db);
              setReview(settings.review_by_default);
              setPreferGpu(settings.device_mode === "auto");
              if (settings.default_output_dir) setOutputDir(settings.default_output_dir);
              if (settings.default_download_dir !== undefined) {
                setDownloadDir(settings.default_download_dir || "");
              }
              pushLog({ text: "Đã lưu cài đặt" });
            } catch (e) {
              pushLog({ text: String(e), cls: "error" });
              throw e;
            }
          }}
          onDoctor={async () => {
            try {
              setDoctorReport(await runDoctor());
            } catch (e) {
              pushLog({ text: String(e), cls: "error" });
            }
          }}
          onDownload={async (id) => {
            setDownloading(id);
            setDownloadPct(0);
            try {
              await downloadModel(id, onEngineEvent);
              setModels(await listModels());
              if (id === "xtts-v2") await refreshXttsSpeakers();
            } catch (e) {
              setErrFriendly({ title: "Tải model thất bại", body: String(e) });
              setErrTech(String(e));
              setErrOpen(true);
            } finally {
              setDownloading(null);
            }
          }}
          onDelete={async (id) => {
            try {
              await deleteModel(id);
              setModels(await listModels());
              if (id === "xtts-v2") {
                setXttsSpeakers([]);
                setSettings((s) => ({ ...s, xtts_speaker_wav: "" }));
              }
            } catch (e) {
              pushLog({ text: String(e), cls: "error" });
            }
          }}
          onRefreshModels={async () => {
            try {
              setModels(await listModels());
              await refreshXttsSpeakers();
            } catch (e) {
              pushLog({ text: String(e), cls: "warn" });
            }
          }}
          onRefreshSpeakers={() => {
            void refreshXttsSpeakers();
          }}
          onPickSpeakerWav={async () => {
            try {
              const path = await pickSpeakerWav();
              if (path) {
                setSettings((s) => ({ ...s, xtts_speaker_wav: path }));
                pushLog({ text: `Đã chọn speaker: ${path}` });
              }
            } catch (e) {
              pushLog({ text: String(e), cls: "error" });
            }
          }}
        />
      )}

      <section className="panel">
        <h2>Nhật ký</h2>
        <div className="log">
          {logs.map((l, i) => (
            <div key={i} className={l.cls}>
              {l.text}
            </div>
          ))}
        </div>
      </section>

      <ErrorDialog
        open={errOpen}
        friendly={errFriendly}
        technical={errTech}
        onClose={() => setErrOpen(false)}
      />
    </div>
  );
}
