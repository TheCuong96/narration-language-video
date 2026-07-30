import type { AppSettings, DoctorReport, WhisperModelInfo } from "../lib/types";
import { PrivacyBanner } from "../components/PrivacyBanner";

interface Props {
  settings: AppSettings;
  models: WhisperModelInfo[];
  doctor: DoctorReport | null;
  downloading: string | null;
  downloadPct: number;
  onChange: (s: AppSettings) => void;
  onSave: () => void;
  onDoctor: () => void;
  onDownload: (id: string) => void;
  onDelete: (id: string) => void;
  onRefreshModels: () => void;
}

export function SettingsPage({
  settings,
  models,
  doctor,
  downloading,
  downloadPct,
  onChange,
  onSave,
  onDoctor,
  onDownload,
  onDelete,
  onRefreshModels,
}: Props) {
  return (
    <div className="settings-stack">
      <PrivacyBanner />

      <section className="panel">
        <h2>Cài đặt chung</h2>
        <div className="row">
          <label>Model Whisper</label>
          <select
            value={settings.whisper_model}
            onChange={(e) => onChange({ ...settings, whisper_model: e.target.value })}
          >
            {["tiny", "base", "small", "medium", "large-v3"].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <div className="row">
          <label>Thiết bị</label>
          <select
            value={settings.device_mode}
            onChange={(e) =>
              onChange({
                ...settings,
                device_mode: e.target.value as AppSettings["device_mode"],
              })
            }
          >
            <option value="cpu">CPU (mặc định)</option>
            <option value="auto">Auto (thử GPU, fallback CPU)</option>
          </select>
        </div>
        <div className="row">
          <label>Thư mục ra mặc định</label>
          <input
            value={settings.default_output_dir}
            onChange={(e) =>
              onChange({ ...settings, default_output_dir: e.target.value })
            }
          />
        </div>
        <div className="row">
          <label>Mức audio gốc (mix)</label>
          <input
            type="number"
            value={settings.mix_original_db}
            onChange={(e) =>
              onChange({ ...settings, mix_original_db: Number(e.target.value) })
            }
          />
        </div>
        <div className="row checks">
          <label>
            <input
              type="checkbox"
              checked={settings.cleanup_temps}
              onChange={(e) =>
                onChange({ ...settings, cleanup_temps: e.target.checked })
              }
            />{" "}
            Tự xóa file tạm sau khi thành công
          </label>
          <label>
            <input
              type="checkbox"
              checked={settings.review_by_default}
              onChange={(e) =>
                onChange({ ...settings, review_by_default: e.target.checked })
              }
            />{" "}
            Review bản dịch mặc định
          </label>
        </div>
        <div className="actions">
          <button type="button" className="primary" onClick={onSave}>
            Lưu cài đặt
          </button>
          <button type="button" onClick={onDoctor}>
            Kiểm tra FFmpeg &amp; engine
          </button>
        </div>
        {doctor && (
          <ul className="doctor">
            {doctor.checks.map((c) => (
              <li key={c.name} className={c.ok ? "ok" : "bad"}>
                {c.ok ? "✓" : "✗"} {c.name}
                {c.path ? ` — ${c.path}` : ""}
                {c.error ? ` — ${c.error}` : ""}
                {c.free_mb != null ? ` — trống ${c.free_mb} MB` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h2>Model Whisper (tải khi cần)</h2>
        <p className="muted">
          Model <strong>không</strong> nằm trong bộ cài. Lưu tại{" "}
          <code>%LOCALAPPDATA%\DubVI\models</code>. Đề xuất <strong>small</strong> cho
          máy CPU phổ thông. Tải sẽ báo dung lượng trước — không tải âm thầm.
        </p>
        <div className="actions">
          <button type="button" onClick={onRefreshModels}>
            Làm mới danh sách
          </button>
        </div>
        {downloading && (
          <div className="download-progress">
            Đang tải <strong>{downloading}</strong>… {downloadPct}%
            <div className="bar">
              <i style={{ width: `${downloadPct}%` }} />
            </div>
          </div>
        )}
        <ul className="model-list">
          {models.map((m) => (
            <li key={m.id}>
              <div>
                <strong>
                  {m.label} {m.recommended ? "★" : ""}
                </strong>
                <div className="q-meta">
                  ~{m.size_mb} MB · {m.speed} · {m.quality}
                </div>
                <div className="q-meta">{m.recommended_for}</div>
                <div className="q-meta">
                  {m.downloaded
                    ? `Đã tải (${m.local_mb} MB trên đĩa)`
                    : "Chưa tải"}
                </div>
              </div>
              <div className="actions vertical">
                {!m.downloaded ? (
                  <button
                    type="button"
                    className="primary"
                    disabled={!!downloading}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Tải model ${m.id} (~${m.size_mb} MB) về máy?`,
                        )
                      ) {
                        onDownload(m.id);
                      }
                    }}
                  >
                    Tải
                  </button>
                ) : (
                  <button
                    type="button"
                    className="danger"
                    disabled={!!downloading}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Xóa model ${m.id} khỏi máy? Bạn sẽ phải tải lại khi dùng.`,
                        )
                      ) {
                        onDelete(m.id);
                      }
                    }}
                  >
                    Xóa
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>Nhà cung cấp (Community)</h2>
        <p className="muted">
          Đang dùng <code>deep-translator</code> + <code>edge-tts</code>. Các provider
          có API key (Google Cloud, Azure) được chuẩn bị interface nhưng{" "}
          <strong>chưa triển khai</strong> trong v0.1.
        </p>
      </section>
    </div>
  );
}
