import { useMemo, type DragEvent, type MouseEvent } from "react";
import type { AudioMode, QueueItem, XttsSpeakerOption } from "../lib/types";
import { formatElapsed, useElapsed } from "../hooks/useElapsed";
import { computeProgressEta } from "../lib/progressEta";

function CheckHelp({ tip }: { tip: string }) {
  const stop = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };
  return (
    <span
      className="check-help"
      tabIndex={0}
      role="note"
      aria-label={tip}
      onClick={stop}
      onMouseDown={stop}
    >
      !
      <span className="check-help-tip">{tip}</span>
    </span>
  );
}

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
  ttsProvider: string;
  xttsSpeakers: XttsSpeakerOption[];
  xttsSpeakerWav: string;
  busy: boolean;
  canResume: boolean;
  stageLabel: string;
  fileProgress: {
    current: number;
    total: number;
    percent: number;
    message: string;
    stageLabel: string;
    stage: string;
  };
  overallProgress: {
    percent: number;
    fileIndex: number;
    fileTotal: number;
    fileName: string;
  };
  elapsedSec: number;
  completedElapsedSec: number[];
  dragOver: boolean;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: DragEvent) => void;
  onPickFiles: () => void;
  onPickOut: () => void;
  onChangeOutput: (v: string) => void;
  onVoice: (v: string) => void;
  onXttsSpeaker: (path: string) => void;
  onModel: (v: string) => void;
  onAudioMode: (v: AudioMode) => void;
  onMixDb: (v: number) => void;
  onReview: (v: boolean) => void;
  onForce: (v: boolean) => void;
  onGpu: (v: boolean) => void;
  onStart: () => void;
  onStop: () => void;
  onResume: () => void;
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
    ttsProvider,
    xttsSpeakers,
    xttsSpeakerWav,
    busy,
    canResume,
    stageLabel,
    fileProgress,
    overallProgress,
    elapsedSec,
    completedElapsedSec,
    dragOver,
    onDragOver,
    onDragLeave,
    onDrop,
    onPickFiles,
    onPickOut,
    onChangeOutput,
    onVoice,
    onXttsSpeaker,
    onModel,
    onAudioMode,
    onMixDb,
    onReview,
    onForce,
    onGpu,
    onStart,
    onStop,
    onResume,
    onRetry,
    onOpenOut,
    onOpenReview,
  } = props;

  const fileLabel = useMemo(() => {
    if (!files.length) return "Chưa chọn video";
    if (files.length === 1) return files[0];
    return `${files.length} video đã chọn`;
  }, [files]);

  const totalFiles = overallProgress.fileTotal || queue.length || files.length;
  const overallPct = Math.max(
    0,
    Math.min(100, Math.round(overallProgress.percent || 0)),
  );
  const filePct = Math.max(0, Math.min(100, Math.round(fileProgress.percent || 0)));
  const stageKey = fileProgress.stage || "";
  const fileIndex = overallProgress.fileIndex || 0;

  const stageElapsedSec = useElapsed(busy && !!stageKey, stageKey);
  const fileElapsedSec = useElapsed(busy && fileIndex > 0, String(fileIndex));

  const eta = useMemo(
    () =>
      computeProgressEta({
        busy,
        elapsedSec,
        stageElapsedSec,
        fileElapsedSec,
        overallPct: overallProgress.percent || 0,
        stagePct: fileProgress.percent || 0,
        stageKey,
        fileIndex,
        fileTotal: totalFiles,
        queue,
        completedElapsedSec,
      }),
    [
      busy,
      elapsedSec,
      stageElapsedSec,
      fileElapsedSec,
      overallProgress.percent,
      fileProgress.percent,
      stageKey,
      fileIndex,
      totalFiles,
      queue,
      completedElapsedSec,
    ],
  );

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
            {ttsProvider === "xtts-v2" ? (
              <select
                value={
                  xttsSpeakers.some((s) => s.path === xttsSpeakerWav)
                    ? xttsSpeakerWav
                    : xttsSpeakers.find((s) => s.default)?.path ||
                      xttsSpeakers[0]?.path ||
                      ""
                }
                onChange={(e) => onXttsSpeaker(e.target.value)}
                disabled={!xttsSpeakers.length}
              >
                {!xttsSpeakers.length ? (
                  <option value="">
                    Chưa có mẫu — tải XTTS trong Settings
                  </option>
                ) : (
                  xttsSpeakers.map((s) => (
                    <option key={s.path} value={s.path}>
                      {s.label}
                    </option>
                  ))
                )}
              </select>
            ) : (
              <select value={voice} onChange={(e) => onVoice(e.target.value)}>
                {VOICES.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </select>
            )}
          </div>
          {ttsProvider === "xtts-v2" ? (
            <p className="muted" style={{ marginTop: "-0.35rem" }}>
              Đang dùng TTS offline (XTTS). Giọng Edge (Hoài My…) chỉ hiện khi chọn
              edge-tts trong Settings.
            </p>
          ) : null}
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
              <CheckHelp tip="Chọn khi muốn dừng lại xem/sửa bản dịch Việt trước khi tạo giọng. Video mới thường để trống." />
            </label>
            <label>
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => onForce(e.target.checked)}
              />{" "}
              Làm lại
              <CheckHelp tip="Chọn khi muốn xử lý lại file đã chạy trước đó (bỏ kết quả cũ). Lần đầu xử lý thì không cần." />
            </label>
            <label>
              <input
                type="checkbox"
                checked={preferGpu}
                onChange={(e) => onGpu(e.target.checked)}
              />{" "}
              Auto GPU
              <CheckHelp tip="Chọn nếu máy có card Nvidia và muốn nhận dạng giọng nhanh hơn. Không có Nvidia hoặc lỗi thì app tự dùng CPU." />
            </label>
          </div>
          <div className="actions">
            <button type="button" className="primary" disabled={busy} onClick={onStart}>
              Bắt đầu
            </button>
            <button type="button" className="danger" disabled={!busy} onClick={onStop}>
              Tạm dừng
            </button>
            <button
              type="button"
              className="primary"
              disabled={busy || !canResume}
              onClick={onResume}
            >
              Tiếp tục
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
          </div>
          {(overallProgress.fileName || overallProgress.fileIndex > 0) && (
            <div className="meta-line">
              File{" "}
              <strong>
                {overallProgress.fileIndex || "—"}/{totalFiles || "—"}
              </strong>
              {overallProgress.fileName ? ` · ${overallProgress.fileName}` : ""}
            </div>
          )}

          {(eta.stage || eta.file || eta.job) && (
            <div className="eta-box" aria-live="polite">
              {eta.stage && (
                <div className="eta-row">
                  <span className="eta-k">Công đoạn</span>
                  <span>
                    còn <strong>{eta.stage.remainLabel}</strong>
                    <span className="eta-clock"> · xong ~{eta.stage.finishLabel}</span>
                  </span>
                </div>
              )}
              {eta.file && (
                <div className="eta-row">
                  <span className="eta-k">Video này</span>
                  <span>
                    còn <strong>{eta.file.remainLabel}</strong>
                    <span className="eta-clock"> · xong ~{eta.file.finishLabel}</span>
                  </span>
                </div>
              )}
              {eta.job && (
                <div className="eta-row eta-row-total">
                  <span className="eta-k">
                    {totalFiles > 1 ? `Tất cả ${totalFiles} video` : "Tổng"}
                  </span>
                  <span>
                    còn <strong>{eta.job.remainLabel}</strong>
                    <span className="eta-clock"> · xong ~{eta.job.finishLabel}</span>
                  </span>
                </div>
              )}
            </div>
          )}

          <label className="bar-label">
            Tổng toàn job: <strong>{overallPct}%</strong>
            {eta.job ? ` · còn ~${eta.job.remainLabel}` : ""}
          </label>
          <div className="bar">
            <i style={{ width: `${overallPct}%` }} />
          </div>
          <label className="bar-label">
            Công đoạn hiện tại:{" "}
            <strong>
              {fileProgress.stageLabel || "—"} · {filePct}%
            </strong>
            {fileProgress.total > 0
              ? ` (${fileProgress.current}/${fileProgress.total})`
              : ""}
            {eta.stage ? ` · còn ~${eta.stage.remainLabel}` : ""}
          </label>
          <div className="bar thin">
            <i style={{ width: `${filePct}%` }} />
          </div>
          {fileProgress.message ? (
            <div className="progress-detail">{fileProgress.message}</div>
          ) : null}
          <ul className="stage-legend">
            {eta.legend.map((s) => (
              <li
                key={s.key}
                className={
                  s.active ? "stage-active" : s.done ? "stage-done" : undefined
                }
              >
                {s.label} ~{s.weight}%
                {s.estLabel ? (
                  <>
                    {" "}
                    ·{" "}
                    {s.active && eta.stage
                      ? `còn ~${eta.stage.remainLabel}`
                      : `~${s.estLabel}`}
                  </>
                ) : null}
              </li>
            ))}
          </ul>
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
