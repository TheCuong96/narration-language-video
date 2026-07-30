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
