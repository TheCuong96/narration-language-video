import { useState } from "react";
import type { UrlDownloadNotice } from "../lib/types";
import type { UrlHelpInfo } from "../lib/engine";
import { formatElapsed } from "../hooks/useElapsed";

interface Props {
  urlInput: string;
  downloadDir: string;
  urlHelp: UrlHelpInfo | null;
  downloadingUrl: boolean;
  lastUrlDownload: UrlDownloadNotice | null;
  busy: boolean;
  stageLabel: string;
  elapsedSec: number;
  fileProgress: {
    current: number;
    total: number;
    percent: number;
    message: string;
    stageLabel: string;
    stage: string;
  };
  onChangeUrl: (v: string) => void;
  onChangeDownloadDir: (v: string) => void;
  onPickDownloadDir: () => void;
  onDownloadUrl: () => void;
  onStop: () => void;
  onOpenDownloadFolder: () => void;
  onDismissDownloadNotice: () => void;
  onGoDub: () => void;
}

export function DownloadPage(props: Props) {
  const {
    urlInput,
    downloadDir,
    urlHelp,
    downloadingUrl,
    lastUrlDownload,
    busy,
    stageLabel,
    elapsedSec,
    fileProgress,
    onChangeUrl,
    onChangeDownloadDir,
    onPickDownloadDir,
    onDownloadUrl,
    onStop,
    onOpenDownloadFolder,
    onDismissDownloadNotice,
    onGoDub,
  } = props;

  const [showUrlHelp, setShowUrlHelp] = useState(false);
  const locked = downloadingUrl;
  const filePct = Math.max(0, Math.min(100, Math.round(fileProgress.percent || 0)));

  return (
    <>
      <section className={`panel url-panel ${locked ? "settings-locked" : ""}`}>
        <h2>Tải từ liên kết (yt-dlp)</h2>
        <p className="muted url-lead">
          Dán URL video công khai → tải về máy. Sau đó có thể mở tab Lồng tiếng để
          thuyết minh tiếng Việt.
        </p>
        <div className="row url-row">
          <label htmlFor="download-dir">Lưu vào</label>
          <input
            id="download-dir"
            value={downloadDir}
            onChange={(e) => onChangeDownloadDir(e.target.value)}
            placeholder="Để trống = thư mục tạm của app (AppData\DubVI\downloads)"
            disabled={locked}
          />
          <button type="button" onClick={onPickDownloadDir} disabled={locked}>
            Chọn
          </button>
        </div>
        <div className="row url-row">
          <label htmlFor="video-url">URL</label>
          <input
            id="video-url"
            value={urlInput}
            onChange={(e) => onChangeUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=…"
            disabled={locked}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !locked) {
                e.preventDefault();
                onDownloadUrl();
              }
            }}
          />
          <button
            type="button"
            className="primary"
            disabled={locked || !urlInput.trim() || busy}
            onClick={onDownloadUrl}
          >
            {downloadingUrl ? "Đang tải…" : "Tải về"}
          </button>
          <button
            type="button"
            className="danger"
            disabled={!downloadingUrl}
            onClick={onStop}
          >
            Hủy tải
          </button>
        </div>
        <p className="muted url-dir-hint">
          {downloadDir.trim()
            ? `Video sẽ lưu vào: ${downloadDir.trim()}`
            : "Chưa chọn thư mục — file sẽ vào thư mục tải tạm của Dub VI."}
        </p>

        {downloadingUrl ? (
          <div className="url-status url-status-busy" role="status">
            <strong>Đang tải về máy…</strong>
            <span>{stageLabel || "Theo dõi tiến độ bên dưới."}</span>
            <div className="meta-line" style={{ marginTop: 8 }}>
              Đã chạy: <strong>{formatElapsed(elapsedSec)}</strong>
              {filePct > 0 ? ` · ${filePct}%` : ""}
            </div>
            <div className="bar thin" style={{ marginTop: 8 }}>
              <i style={{ width: `${filePct}%` }} />
            </div>
            {fileProgress.message ? (
              <div className="progress-detail">{fileProgress.message}</div>
            ) : null}
          </div>
        ) : null}

        {lastUrlDownload && !downloadingUrl ? (
          <div className="url-status url-status-ok" role="status">
            <div className="url-status-head">
              <strong>Đã tải video về máy</strong>
              <button
                type="button"
                className="linkish url-status-dismiss"
                onClick={onDismissDownloadNotice}
              >
                Đóng
              </button>
            </div>
            <dl className="url-status-meta">
              <div>
                <dt>Tên file</dt>
                <dd>{lastUrlDownload.fileName}</dd>
              </div>
              <div>
                <dt>Thư mục</dt>
                <dd className="path">{lastUrlDownload.folder}</dd>
              </div>
              <div>
                <dt>Đường dẫn đầy đủ</dt>
                <dd className="path">{lastUrlDownload.path}</dd>
              </div>
              {(lastUrlDownload.duration_label || lastUrlDownload.size_label) && (
                <div>
                  <dt>Thông tin</dt>
                  <dd>
                    {lastUrlDownload.duration_label || "—"}
                    {" · "}
                    {lastUrlDownload.size_label || "—"}
                  </dd>
                </div>
              )}
              <div>
                <dt>URL nguồn</dt>
                <dd className="path">{lastUrlDownload.sourceUrl}</dd>
              </div>
            </dl>
            <div className="url-status-actions">
              <button type="button" className="primary" onClick={onOpenDownloadFolder}>
                Mở thư mục tải về
              </button>
              <button type="button" onClick={onGoDub}>
                Sang tab Lồng tiếng
              </button>
            </div>
          </div>
        ) : null}

        <button
          type="button"
          className="linkish"
          onClick={() => setShowUrlHelp((v) => !v)}
          style={{ marginTop: 10 }}
        >
          {showUrlHelp ? "Ẩn hướng dẫn" : "Xem trang nào tải được?"}
        </button>
        {showUrlHelp && (
          <div className="url-help">
            <p>
              {urlHelp?.summary ||
                "Dùng yt-dlp để tải một video công khai từ http(s)."}
            </p>
            <div className="url-help-cols">
              <div>
                <strong>Thường ổn</strong>
                <ul>
                  {(
                    urlHelp?.typically_works || [
                      "YouTube (video công khai)",
                      "Nhiều trang khác yt-dlp hỗ trợ",
                    ]
                  ).map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </div>
              <div>
                <strong>Hay lỗi / hạn chế</strong>
                <ul>
                  {(
                    urlHelp?.often_fails_or_unsupported || [
                      "Video riêng tư / trả phí",
                      "Một số trang chống bot",
                    ]
                  ).map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </div>
            </div>
            {urlHelp?.tips?.length ? (
              <ul>
                {urlHelp.tips.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            ) : null}
            <p className="url-help-foot">
              Danh sách site:{" "}
              <a
                href={
                  urlHelp?.supported_sites_url ||
                  "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md"
                }
                target="_blank"
                rel="noreferrer"
              >
                supportedsites.md
              </a>
              {urlHelp?.yt_dlp_version ? ` · yt-dlp ${urlHelp.yt_dlp_version}` : ""}
            </p>
          </div>
        )}
      </section>
    </>
  );
}
