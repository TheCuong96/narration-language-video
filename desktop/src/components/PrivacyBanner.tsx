export function PrivacyBanner() {
  return (
    <aside className="privacy">
      <strong>Quyền riêng tư (Community)</strong>
      <ul>
        <li>Whisper và FFmpeg chạy <em>trên máy bạn</em>.</li>
        <li>Dịch (deep-translator) và edge-tts <em>cần Internet</em>.</li>
        <li>Video <em>không</em> được upload lên server của Dub VI.</li>
        <li>Chỉ transcript/text được gửi tới dịch vụ dịch và TTS đang chọn.</li>
      </ul>
    </aside>
  );
}
