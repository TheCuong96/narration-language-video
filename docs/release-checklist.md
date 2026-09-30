# Release checklist — Dub VI 0.1.0

## Build máy lập trình

- [ ] `scripts/clean-build.ps1` (tuỳ chọn)
- [ ] `scripts/build-desktop.ps1` thành công
- [ ] `scripts/verify-package.ps1` PASSED
- [ ] Có `release/DubVI_0.1.0_x64-setup.exe` + `.sha256`
- [ ] `requirements-base.txt` không chứa `nvidia-*`
- [ ] Icon: xác nhận placeholder hoặc thay icon chính thức

## VM Windows sạch (bắt buộc trước khi tuyên bố ship)

Môi trường: **không** Python, FFmpeg, CUDA, Node, Rust.

- [ ] Cài bằng setup.exe (Next → Install)
- [ ] Mở từ Start Menu «Dub VI»
- [ ] Settings → kiểm tra FFmpeg/engine OK
- [ ] Tải model `tiny` hoặc `small` (thấy dung lượng trước khi tải)
- [ ] Xử lý thành công video ngắn
- [ ] Dừng giữa chừng → chạy lại (resume cache)
- [ ] Sửa 1 câu transcript → tiếp tục TTS
- [ ] Gỡ cài đặt: app biến mất; **video/output người dùng vẫn còn**

## Kiểm thử tự động

- [ ] `cd engine && python -m pytest tests -q`
- [ ] `cd desktop && npm run typecheck && npm run build`

## Tài liệu

- [ ] README / CHANGELOG / privacy cập nhật version
- [ ] completion-report ghi rõ phần đã/ chưa xác minh trên máy sạch


## TranslateGemma

- [ ] `node desktop/scripts/test-privacy-banner.mjs` thành công (sau npm ci trong desktop)
- [ ] Frozen sidecar `models --kind translate` gọi tags và nhận dung lượng từ Ollama
- [ ] requests/urllib3/certifi nằm trong onedir, không cần Python ngoài
- [ ] Không có Ollama executable hoặc trọng số GGUF trong payload installer
- [ ] Máy sạch, Ollama chưa mở: Settings/doctor hiển thị hướng dẫn; NLLB/Google vẫn dùng được
- [ ] Cài/mở Ollama riêng, UI xác nhận dung lượng trước pull; progress và trạng thái Sẵn sàng
- [ ] UI xóa từng model với xác nhận (không xóa model dùng thật để chỉ kiểm tra)
- [ ] Video thực: TranslateGemma giữ id/timestamp/thứ tự; protected terms; review/resume/retry
- [ ] Google → NLLB → 4B → 12B: cache dịch invalid, transcript EN vẫn giữ
- [ ] Offline fallback mặc định không gửi Google; opt-in hiển thị cảnh báo privacy
- [ ] NLLB/XTTS chạy thật trong cấu hình offline, không chỉ unit mocks
- [ ] Gemma Terms of Use/model URL hiển thị, không tuyên bố Google bảo trợ
