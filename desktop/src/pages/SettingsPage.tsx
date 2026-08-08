import { useEffect, useState } from "react";
import type {
  AppSettings,
  DoctorReport,
  WhisperModelInfo,
  XttsSpeakerOption,
} from "../lib/types";
import { PrivacyBanner } from "../components/PrivacyBanner";

type SaveSection = "general" | "providers";
type SaveFlash = { kind: "ok" | "err"; text: string };

interface Props {
  settings: AppSettings;
  models: WhisperModelInfo[];
  doctor: DoctorReport | null;
  downloading: string | null;
  downloadPct: number;
  xttsSpeakers: XttsSpeakerOption[];
  /** When true, freeze all setting controls until the job finishes/stops. */
  busy?: boolean;
  onChange: (s: AppSettings) => void;
  onSave: () => Promise<void>;
  onDoctor: () => void;
  onDownload: (id: string) => void;
  onDelete: (id: string) => void;
  onRefreshModels: () => void;
  onPickSpeakerWav: () => void;
  onRefreshSpeakers: () => void;
}

function SaveStatus({ flash }: { flash: SaveFlash | null }) {
  if (!flash) return null;
  return (
    <div
      className={`save-flash ${flash.kind === "ok" ? "ok" : "err"}`}
      role="status"
      aria-live="polite"
    >
      {flash.kind === "ok" ? "✓" : "✗"} {flash.text}
    </div>
  );
}

function ModelList({
  models,
  downloading,
  downloadPct,
  onDownload,
  onDelete,
}: {
  models: WhisperModelInfo[];
  downloading: string | null;
  downloadPct: number;
  onDownload: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (!models.length) {
    return <p className="muted">Không có model trong danh mục.</p>;
  }
  return (
    <>
      {downloading && models.some((m) => m.id === downloading) && (
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
              {m.license_note ? (
                <div className="q-meta">License: {m.license_note}</div>
              ) : null}
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
    </>
  );
}

export function SettingsPage({
  settings,
  models,
  doctor,
  downloading,
  downloadPct,
  xttsSpeakers,
  busy = false,
  onChange,
  onSave,
  onDoctor,
  onDownload,
  onDelete,
  onRefreshModels,
  onPickSpeakerWav,
  onRefreshSpeakers,
}: Props) {
  const [saving, setSaving] = useState<SaveSection | null>(null);
  const [generalFlash, setGeneralFlash] = useState<SaveFlash | null>(null);
  const [providerFlash, setProviderFlash] = useState<SaveFlash | null>(null);

  useEffect(() => {
    if (generalFlash?.kind !== "ok") return;
    const t = window.setTimeout(() => setGeneralFlash(null), 4000);
    return () => window.clearTimeout(t);
  }, [generalFlash]);

  useEffect(() => {
    if (providerFlash?.kind !== "ok") return;
    const t = window.setTimeout(() => setProviderFlash(null), 4000);
    return () => window.clearTimeout(t);
  }, [providerFlash]);

  async function handleSave(section: SaveSection) {
    const setFlash = section === "general" ? setGeneralFlash : setProviderFlash;
    setSaving(section);
    setFlash(null);
    try {
      await onSave();
      setFlash({
        kind: "ok",
        text:
          section === "general"
            ? "Đã lưu cài đặt thành công."
            : "Đã lưu nhà cung cấp thành công.",
      });
    } catch (e) {
      setFlash({
        kind: "err",
        text:
          section === "general"
            ? `Lưu cài đặt thất bại: ${e}`
            : `Lưu nhà cung cấp thất bại: ${e}`,
      });
    } finally {
      setSaving(null);
    }
  }

  const whisperModels = models.filter((m) => (m.kind || "whisper") === "whisper");
  const translateModels = models.filter((m) => m.kind === "translate");
  const ttsModels = models.filter((m) => m.kind === "tts");
  const offlineTranslate = settings.translate_provider === "nllb";
  const offlineTts = settings.tts_provider === "xtts-v2";

  const selectedSpeaker = settings.xtts_speaker_wav || "";
  const matchedSpeaker = xttsSpeakers.find(
    (s) => s.path === selectedSpeaker || s.id === selectedSpeaker,
  );
  const selectValue = matchedSpeaker
    ? matchedSpeaker.path
    : selectedSpeaker
      ? "__custom__"
      : xttsSpeakers.find((s) => s.default)?.path || xttsSpeakers[0]?.path || "";

  return (
    <div className="settings-stack">
      <PrivacyBanner settings={settings} />
      {busy ? (
        <p className="settings-lock-note">
          Đang xử lý video — mọi cài đặt bị khóa đến khi xong hoặc tạm dừng.
        </p>
      ) : null}

      <fieldset className="settings-fieldset" disabled={busy}>
      <section className="panel">
        <h2>Cài đặt chung</h2>
        <div className="row">
          <label>Model nhận dạng lời nói</label>
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
            placeholder="Nhớ sau khi chọn ở tab Lồng tiếng"
          />
        </div>
        <div className="row">
          <label>Thư mục tải URL</label>
          <input
            value={settings.default_download_dir || ""}
            onChange={(e) =>
              onChange({ ...settings, default_download_dir: e.target.value })
            }
            placeholder="Để trống = AppData\\DubVI\\downloads"
          />
        </div>
        <p className="muted" style={{ marginTop: "-0.35rem" }}>
          Hai đường dẫn trên được nhớ tự động khi bạn chọn thư mục ở tab Tải từ liên
          kết / Lồng tiếng; vẫn giữ sau khi tắt app. Chỉ đổi khi bạn chọn chỗ mới hoặc
          sửa rồi bấm Lưu ở đây.
        </p>
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
          <button
            type="button"
            className="primary"
            disabled={saving !== null}
            onClick={() => void handleSave("general")}
          >
            {saving === "general" ? "Đang lưu…" : "Lưu cài đặt"}
          </button>
          <button type="button" onClick={onDoctor}>
            Kiểm tra FFmpeg &amp; engine
          </button>
        </div>
        <SaveStatus flash={generalFlash} />
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
        <h2>Nhà cung cấp dịch &amp; giọng đọc</h2>
        <p className="muted">
          Online (mặc định) không cần model lớn. Offline cần{" "}
          <code>pip uninstall -y TTS coqpit</code> rồi{" "}
          <code>pip install -r engine/requirements-offline.txt</code> và tải model bên
          dưới. Giọng đọc offline nên bật <strong>Auto GPU</strong>. License model
          offline: Coqui CPML (không thương mại).
        </p>
        <div className="row">
          <label>Dịch thuật</label>
          <select
            value={settings.translate_provider}
            onChange={(e) =>
              onChange({ ...settings, translate_provider: e.target.value })
            }
          >
            <option value="deep-translator">Google — online (cần Internet)</option>
            <option value="nllb">Offline trên máy (NLLB)</option>
          </select>
        </div>
        <div className="row">
          <label>Cách tạo giọng đọc</label>
          <select
            value={settings.tts_provider}
            onChange={(e) => onChange({ ...settings, tts_provider: e.target.value })}
          >
            <option value="edge-tts">Microsoft Edge — online (cần Internet)</option>
            <option value="xtts-v2">Offline trên máy (XTTS)</option>
          </select>
        </div>
        {offlineTts && (
          <>
            <div className="row">
              <label>Giọng mẫu</label>
              <select
                value={selectValue}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "__custom__") {
                    onPickSpeakerWav();
                    return;
                  }
                  onChange({ ...settings, xtts_speaker_wav: v });
                }}
                disabled={!xttsSpeakers.length && !selectedSpeaker}
              >
                {!xttsSpeakers.length && (
                  <option value="">
                    Chưa có mẫu — hãy tải model giọng đọc bên dưới
                  </option>
                )}
                {xttsSpeakers.map((s) => (
                  <option key={s.path} value={s.path}>
                    {s.label}
                  </option>
                ))}
                <option value="__custom__">Chọn file WAV của tôi…</option>
              </select>
            </div>
            <p className="muted">
              Đây là <strong>file giọng mẫu 3–10 giây</strong> để máy bắt chước
              giọng. Các lựa chọn trên lấy từ model giọng đọc đã tải (thư mục{" "}
              <code>%LOCALAPPDATA%\DubVI\models\xtts-v2\samples</code>). Để trống /
              chọn mặc định cũng được — app dùng{" "}
              <code>speaker_default.wav</code>.
            </p>
            {selectedSpeaker && !matchedSpeaker ? (
              <div className="row">
                <label>File tùy chọn</label>
                <input value={selectedSpeaker} readOnly />
              </div>
            ) : null}
            <div className="actions">
              <button type="button" onClick={onRefreshSpeakers}>
                Làm mới danh sách giọng
              </button>
              <button type="button" onClick={onPickSpeakerWav}>
                Chọn WAV tùy chỉnh…
              </button>
            </div>
          </>
        )}
        {(offlineTranslate || offlineTts) && (
          <p className="muted">
            {offlineTranslate
              ? "Đã chọn dịch offline — tải model dịch bên dưới. "
              : null}
            {offlineTts
              ? "Đã chọn tạo giọng offline — tải model giọng đọc bên dưới rồi chọn giọng mẫu."
              : null}
          </p>
        )}
        <div className="actions">
          <button
            type="button"
            className="primary"
            disabled={saving !== null}
            onClick={() => void handleSave("providers")}
          >
            {saving === "providers" ? "Đang lưu…" : "Lưu nhà cung cấp"}
          </button>
        </div>
        <SaveStatus flash={providerFlash} />
      </section>

      <section className="panel">
        <h2>Model nhận dạng lời nói (tải khi cần)</h2>
        <p className="muted">
          Model dùng để nghe video và viết lại lời nói thành chữ.{" "}
          <strong>Không</strong> nằm trong bộ cài — lưu tại{" "}
          <code>%LOCALAPPDATA%\DubVI\models</code>. Đề xuất <strong>small</strong> cho
          máy CPU phổ thông. Tải sẽ báo dung lượng trước — không tải âm thầm.
        </p>
        <div className="actions">
          <button type="button" onClick={onRefreshModels}>
            Làm mới danh sách
          </button>
        </div>
        <ModelList
          models={whisperModels}
          downloading={downloading}
          downloadPct={downloadPct}
          onDownload={onDownload}
          onDelete={onDelete}
        />
      </section>

      <section className="panel">
        <h2>Model offline — dịch thuật &amp; tạo giọng đọc</h2>
        <p className="muted">
          ~2–4 GB mỗi model. Cần Internet lúc tải; sau đó chạy trên máy. Model tạo
          giọng đọc khá nặng — nên có GPU NVIDIA.
        </p>
        <div className="actions">
          <button type="button" onClick={onRefreshModels}>
            Làm mới danh sách
          </button>
        </div>
        <h3>Dịch thuật (NLLB)</h3>
        <ModelList
          models={translateModels}
          downloading={downloading}
          downloadPct={downloadPct}
          onDownload={onDownload}
          onDelete={onDelete}
        />
        <h3>Tạo giọng đọc (XTTS)</h3>
        <ModelList
          models={ttsModels}
          downloading={downloading}
          downloadPct={downloadPct}
          onDownload={onDownload}
          onDelete={onDelete}
        />
      </section>
      </fieldset>
    </div>
  );
}
