import { useMemo, type DragEvent } from "react";
import type { AudioMode, QueueItem } from "../lib/types";
import { estimateEta, formatElapsed } from "../hooks/useElapsed";

const VOICES = [
  { id: "vi-VN-HoaiMyNeural", label: "Nữ — Hoài My" },
  { id: "vi-VN-NamMinhNeural", label: "Nam — Nam Minh" },
];
const MODELS = ["tiny", "base", "small", "medium", "large-v3"];

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: "Chờ",
    running: "Đang chạy",
    review: "Review",
    completed: "Xong",
    failed: "Lỗi",
    cancelled: "Đã dừng",
    skipped: "Bỏ qua",
  };
  return map[s] || s;
}

interface Props {
  files: string[];
  queue: QueueItem[];
  outputDir: string;
  voice: string;
  model: string;
  audioMode: AudioMode;
  mixDb: number;
  review: boolean;
  force: boolean;
  preferGpu: boolean;
  busy: boolean;
  stageLabel: string;
  fileProgress: { current: number; total: number; message: string };
  overallProgress: { current: number; total: number };
  elapsedSec: number;
  dragOver: boolean;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: DragEvent) => void;
  onPickFiles: () => void;
  onPickOut: () => void;
  onChangeOutput: (v: string) => void;
  onVoice: (v: string) => void;
  onModel: (v: string) => void;
  onAudioMode: (v: AudioMode) => void;
  onMixDb: (v: number) => void;
  onReview: (v: boolean) => void;
  onForce: (v: boolean) => void;
  onGpu: (v: boolean) => void;
  onStart: () => void;
  onStop: () => void;
  onRetry: () => void;
  onOpenOut: () => void;
  onOpenReview: (stem: string) => void;
}

export function ProcessPage(props: Props) {
  const {
    files,
    queue,
    outputDir,
    voice,
    model,
    audioMode,
    mixDb,
    review,
    force,
    preferGpu,
    busy,
    stageLabel,
    fileProgress,
    overallProgress,
    elapsedSec,
    dragOver,
    onDragOver,
    onDragLeave,
    onDrop,
    onPickFiles,
    onPickOut,
    onChangeOutput,
    onVoice,
    onModel,
    onAudioMode,
    onMixDb,
    onReview,
    onForce,
    onGpu,
    onStart,
    onStop,
    onRetry,
    onOpenOut,
    onOpenReview,
  } = props;

  const fileLabel = useMemo(() => {
    if (!files.length) return "Chưa chọn video";
    if (files.length === 1) return files[0];
    return `${files.length} video đã chọn`;
  }, [files]);

  const completed = queue.filter((q) =>
    ["completed", "skipped"].includes(q.status),
  ).length;
  const eta = estimateEta(elapsedSec, completed, queue.length || files.length);

  const overallPct =
    overallProgress.total > 0
      ? Math.round((100 * overallProgress.current) / overallProgress.total)
      : queue.length
        ? Math.round((100 * completed) / queue.length)
        : 0;

  const filePct =
    fileProgress.total > 0
      ? Math.round((100 * fileProgress.current) / fileProgress.total)
      : 0;

  return (
    <>
      <div
        className={`dropzone ${dragOver ? "active" : ""}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={onPickFiles}
        role="button"
        tabIndex={0}
      >
        <strong>Kéo và thả video vào đây</strong>
        <span>MP4 · MKV · MOV · AVI · WebM — hoặc bấm chọn một / nhiều file</span>
        <div className="drop-path">{fileLabel}</div>
      </div>

      <div className="grid">
        <section className="panel">
          <h2>Thiết lập</h2>
          <div className="row">
            <label>Thư mục ra</label>
            <input
              value={outputDir}
              onChange={(e) => onChangeOutput(e.target.value)}
              placeholder="D:\\videos\\vi"
            />
            <button type="button" onClick={onPickOut}>
              Chọn
            </button>
          </div>
          <div className="row">
            <label>Giọng</label>
            <select value={voice} onChange={(e) => onVoice(e.target.value)}>
              {VOICES.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </select>
          </div>
          <div className="row">
            <label>Whisper</label>
            <select value={model} onChange={(e) => onModel(e.target.value)}>
              {MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="row">
            <label>Âm thanh</label>
            <select
              value={audioMode}
              onChange={(e) => onAudioMode(e.target.value as AudioMode)}
            >
              <option value="vi_only">Chỉ giọng Việt</option>
              <option value="dual_track">Hai track (EN + VI)</option>
              <option value="mix">Trộn VI + gốc giảm âm</option>
            </select>
          </div>
          {audioMode === "mix" && (
            <div className="row">
              <label>Gốc (dB)</label>
              <input
                type="number"
                value={mixDb}
                onChange={(e) => onMixDb(Number(e.target.value))}
              />
            </div>
          )}
          <div className="row checks">
            <label>
              <input
                type="checkbox"
                checked={review}
                onChange={(e) => onReview(e.target.checked)}
              />{" "}
              Sửa bản dịch trước TTS
            </label>
            <label>
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => onForce(e.target.checked)}
              />{" "}
              Làm lại
            </label>
            <label>
              <input
                type="checkbox"
                checked={preferGpu}
                onChange={(e) => onGpu(e.target.checked)}
              />{" "}
              Auto GPU
            </label>
          </div>
          <div className="actions">
            <button type="button" className="primary" disabled={busy} onClick={onStart}>
              Bắt đầu
            </button>
            <button type="button" className="danger" disabled={!busy} onClick={onStop}>
              Dừng
            </button>
            <button type="button" disabled={busy} onClick={onRetry}>
              Thử lại lỗi
            </button>
            <button type="button" disabled={!outputDir} onClick={onOpenOut}>
              Mở kết quả
            </button>
          </div>
        </section>

        <section className="panel">
          <h2>Tiến độ</h2>
          <div className="stage">{stageLabel || "Sẵn sàng"}</div>
          <div className="meta-line">
            Đã chạy: <strong>{formatElapsed(elapsedSec)}</strong>
            {eta ? (
              <>
                {" "}
                · Còn khoảng: <strong>{eta}</strong>
              </>
            ) : null}
          </div>
          <label className="bar-label">Tổng ({overallPct}%)</label>
          <div className="bar">
            <i style={{ width: `${overallPct}%` }} />
          </div>
          <label className="bar-label">
            Công đoạn ({filePct}%) — {fileProgress.message}
          </label>
          <div className="bar thin">
            <i style={{ width: `${filePct}%` }} />
          </div>
        </section>
      </div>

      <section className="panel">
        <h2>Hàng đợi</h2>
        <ul className="queue">
          {queue.length === 0 && <li className="empty">Chưa có video</li>}
          {queue.map((item) => (
            <li key={`${item.stem}-${item.index}`}>
              <div>
                <div className="q-title">{item.stem}</div>
                <div className="q-meta">
                  {item.duration_label || "—"} · {item.size_label || "—"}
                </div>
                {item.error && <div className="q-err">{item.error}</div>}
                {item.status === "review" && (
                  <button type="button" onClick={() => onOpenReview(item.stem)}>
                    Mở transcript
                  </button>
                )}
              </div>
              <span className={`badge ${item.status}`}>{statusLabel(item.status)}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
