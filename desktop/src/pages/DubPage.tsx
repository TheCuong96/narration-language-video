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
  downloadingUrl: boolean;
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
  onGoClone: (path: string) => void;
}

export function DubPage(props: Props) {
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
    downloadingUrl,
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
    onGoClone,
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
  const settingsLocked = busy || downloadingUrl;
  const hasCompletedResult =
    !busy &&
    !downloadingUrl &&
    (overallPct >= 100 || queue.some((q) => q.status === "completed"));

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
        className={`dropzone ${dragOver && !settingsLocked ? "active" : ""} ${settingsLocked ? "locked" : ""}`}
        onDragOver={settingsLocked ? undefined : onDragOver}
        onDragLeave={settingsLocked ? undefined : onDragLeave}
        onDrop={settingsLocked ? undefined : onDrop}
        onClick={settingsLocked ? undefined : onPickFiles}
        role="button"
        tabIndex={settingsLocked ? -1 : 0}
        aria-disabled={settingsLocked}
      >
        <strong>Kéo và thả video vào đây</strong>
        <span>MP4 · MKV · MOV · AVI · WebM — hoặc bấm chọn một / nhiều file</span>
        <div className="drop-path">{fileLabel}</div>
        {settingsLocked ? (
          <div className="drop-locked">
            {downloadingUrl
              ? "Đang tải video từ URL ở tab khác…"
              : "Đang xử lý — không đổi video / thiết lập"}
          </div>
        ) : null}
      </div>

      <div className="grid">
        <section className={`panel ${settingsLocked ? "settings-locked" : ""}`}>
          <h2>Lồng tiếng Anh → Việt</h2>
          {settingsLocked ? (
            <p className="settings-lock-note">
              Đang xử lý — mọi thiết lập bị khóa đến khi xong hoặc tạm dừng.
            </p>
          ) : (
            <p className="muted url-lead">
              Nhận dạng lời nói → dịch Việt → tạo giọng đọc → ghép lại video.
            </p>
          )}
          <div className="row">
            <label>Thư mục ra</label>
            <input
              value={outputDir}
              onChange={(e) => onChangeOutput(e.target.value)}
              placeholder="D:\\videos\\vi — chọn một lần là nhớ mãi"
              disabled={settingsLocked}
            />
            <button type="button" onClick={onPickOut} disabled={settingsLocked}>
              Chọn
            </button>
          </div>
          {outputDir.trim() ? (
            <p className="muted" style={{ marginTop: "-0.35rem" }}>
              Đã nhớ thư mục ra — tắt app mở lại vẫn dùng đến khi bạn chọn chỗ khác.
            </p>
          ) : null}
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
                disabled={settingsLocked || !xttsSpeakers.length}
              >
                {!xttsSpeakers.length ? (
                  <option value="">
                    Chưa có mẫu — tải model giọng đọc trong Settings
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
              <select
                value={voice}
                onChange={(e) => onVoice(e.target.value)}
                disabled={settingsLocked}
              >
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
              Đang tạo giọng đọc offline trên máy. Giọng Edge (Hoài My…) chỉ hiện khi
              chọn Microsoft Edge trong Settings.
            </p>
          ) : null}
          <div className="row">
            <label>Nhận dạng lời nói</label>
            <select
              value={model}
              onChange={(e) => onModel(e.target.value)}
              disabled={settingsLocked}
            >
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
              disabled={settingsLocked}
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
                disabled={settingsLocked}
              />
            </div>
          )}
          <div className="row checks">
            <label>
              <input
                type="checkbox"
                checked={review}
                onChange={(e) => onReview(e.target.checked)}
                disabled={settingsLocked}
              />{" "}
              Sửa bản dịch trước khi tạo giọng
              <CheckHelp tip="Chọn khi muốn dừng lại xem/sửa bản dịch Việt trước khi tạo giọng đọc. Video mới thường để trống." />
            </label>
            <label>
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => onForce(e.target.checked)}
                disabled={settingsLocked}
              />{" "}
              Làm lại
              <CheckHelp tip="Chọn khi muốn xử lý lại file đã chạy trước đó (bỏ kết quả cũ). Lần đầu xử lý thì không cần." />
            </label>
            <label>
              <input
                type="checkbox"
                checked={preferGpu}
                onChange={(e) => onGpu(e.target.checked)}
                disabled={settingsLocked}
              />{" "}
              Auto GPU
              <CheckHelp tip="Chọn nếu máy có card Nvidia và muốn nhận dạng giọng nhanh hơn. Không có Nvidia hoặc lỗi thì app tự dùng CPU." />
            </label>
          </div>
          <div className="actions">
            <button
              type="button"
              className="primary"
              disabled={busy || downloadingUrl}
              onClick={onStart}
            >
              Bắt đầu
            </button>
            <button
              type="button"
              className="danger"
              disabled={!busy}
              onClick={onStop}
            >
              Tạm dừng
            </button>
            <button
              type="button"
              className="primary"
              disabled={busy || downloadingUrl || !canResume}
              onClick={onResume}
            >
              Tiếp tục
            </button>
            <button type="button" disabled={busy || downloadingUrl} onClick={onRetry}>
              Thử lại lỗi
            </button>
            <button
              type="button"
              className={
                hasCompletedResult ? "btn-open-result is-ready" : "btn-open-result"
              }
              disabled={!outputDir || busy || downloadingUrl}
              onClick={onOpenOut}
            >
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
            <div className={`eta-box eta-${eta.confidence}`} aria-live="polite">
              <div className="eta-title">Ước lượng thời gian</div>
              {eta.job && (
                <div className="eta-headline">
                  <div className="eta-finish">
                    Dự kiến xong lúc <strong>{eta.job.finishLabel}</strong>
                  </div>
                  <div className="eta-remain">
                    Còn khoảng <strong>{eta.job.remainLabel}</strong>
                    {totalFiles > 1 ? ` cho ${totalFiles} video` : ""}
                  </div>
                </div>
              )}
              <div className="eta-rows">
                {eta.stage && (
                  <div className="eta-row">
                    <span className="eta-k">{eta.stageName}</span>
                    <span className="eta-v">
                      còn <strong>{eta.stage.remainLabel}</strong>
                      <span className="eta-clock">
                        {" "}
                        · xong lúc {eta.stage.finishLabel}
                      </span>
                    </span>
                  </div>
                )}
                {eta.file && (
                  <div className="eta-row">
                    <span className="eta-k">
                      Video này
                      {overallProgress.fileIndex > 0
                        ? ` (${overallProgress.fileIndex}/${totalFiles || "—"})`
                        : ""}
                    </span>
                    <span className="eta-v">
                      còn <strong>{eta.file.remainLabel}</strong>
                      <span className="eta-clock">
                        {" "}
                        · xong lúc {eta.file.finishLabel}
                      </span>
                    </span>
                  </div>
                )}
                {eta.job && totalFiles > 1 && (
                  <div className="eta-row eta-row-total">
                    <span className="eta-k">Cả hàng đợi</span>
                    <span className="eta-v">
                      còn <strong>{eta.job.remainLabel}</strong>
                      <span className="eta-clock">
                        {" "}
                        · xong lúc {eta.job.finishLabel}
                      </span>
                    </span>
                  </div>
                )}
              </div>
              {eta.confidenceLabel ? (
                <div className="eta-note">{eta.confidenceLabel}</div>
              ) : null}
            </div>
          )}

          <label className="bar-label">
            Tổng tiến độ: <strong>{overallPct}%</strong>
            {eta.job ? ` · còn ${eta.job.remainLabel}` : ""}
          </label>
          <div className="bar">
            <i style={{ width: `${overallPct}%` }} />
          </div>
          <label className="bar-label">
            {fileProgress.stageLabel || eta.stageName || "Công đoạn"}:{" "}
            <strong>{filePct}%</strong>
            {fileProgress.total > 0
              ? ` (${fileProgress.current}/${fileProgress.total})`
              : ""}
            {eta.stage ? ` · còn ${eta.stage.remainLabel}` : ""}
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
                <span className="stage-legend-name">{s.label}</span>
                {s.remainLabel ? (
                  <span className="stage-legend-eta"> · {s.remainLabel}</span>
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
            <li
              key={`${item.stem}-${item.index}`}
              className={item.from_url ? "from-url" : undefined}
            >
              <div>
                <div className="q-title">
                  {item.stem}
                  {item.from_url ? (
                    <span className="badge-url" title="Đã tải từ URL về máy">
                      Đã tải từ URL
                    </span>
                  ) : null}
                </div>
                <div className="q-meta">
                  {item.duration_label || "—"} · {item.size_label || "—"}
                </div>
                {item.from_url && item.input ? (
                  <div className="q-path" title={item.input}>
                    {item.input}
                  </div>
                ) : null}
                {item.error && <div className="q-err">{item.error}</div>}
                <div className="q-actions">
                  {!settingsLocked && item.input ? (
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => onGoClone(item.input)}
                    >
                      Clone đoạn
                    </button>
                  ) : null}
                  {item.status === "review" && (
                    <button type="button" onClick={() => onOpenReview(item.stem)}>
                      Mở transcript
                    </button>
                  )}
                </div>
              </div>
              <span className={`badge ${item.status}`}>{statusLabel(item.status)}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
