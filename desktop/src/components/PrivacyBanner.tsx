import type { AppSettings } from "../lib/types";

interface Props {
  settings?: AppSettings;
}

export function PrivacyBanner({ settings }: Props) {
  const translate = settings?.translate_provider || "deep-translator";
  const tts = settings?.tts_provider || "edge-tts";
  const offlineTranslate = ["nllb", "nllb-offline", "offline-translate"].includes(
    translate,
  );
  const offlineTts = ["xtts-v2", "xtts", "vixtts", "offline-tts"].includes(tts);

  return (
    <aside className="privacy">
      <strong>Quyền riêng tư (Community)</strong>
      <ul>
        <li>
          Nhận dạng lời nói và xử lý video chạy <em>trên máy bạn</em>.
        </li>
        <li>
          Dịch thuật:{" "}
          {offlineTranslate ? (
            <em>offline trên máy</em>
          ) : (
            <em>cần Internet</em>
          )}
          .
        </li>
        <li>
          Tạo giọng đọc:{" "}
          {offlineTts ? <em>offline trên máy</em> : <em>cần Internet</em>}.
        </li>
        <li>
          Video <em>không</em> được upload lên server của Dub VI.
        </li>
        {!offlineTranslate || !offlineTts ? (
          <li>Chỉ bản dịch/text được gửi tới dịch vụ online đang chọn.</li>
        ) : (
          <li>
            Chế độ offline: bản dịch và giọng đọc không rời máy (trừ lúc tải model).
          </li>
        )}
      </ul>
    </aside>
  );
}
