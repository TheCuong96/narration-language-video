# Changelog

## Unreleased

### Performance

- Dịch offline NLLB xử lý theo lô (batch) thay vì từng câu một → nhanh hơn nhiều lần trên cả CPU/GPU; GPU dùng fp16, CPU giảm beam search xuống 1 (greedy) để ưu tiên tốc độ
- TTS offline XTTS chạy suy luận trong `torch.no_grad()` → giảm bộ nhớ dùng và tăng tốc nhẹ

### Fixed

- Engine PyInstaller chuyển **onedir** (không còn bung `%TEMP%\_MEI*` mỗi lần chạy)
- Dọn orphan `_MEI*` lúc mở app / sau khi engine thoát / hủy job; script `scripts/cleanup-mei-temp.ps1`
- Tốc độ đọc được quyết định độc lập theo toàn bộ thời lượng từng câu: câu vừa khung giữ 1×, câu vượt khung mới tăng đều; retry TTS không còn tự đổi rate hoặc làm câu sau bị nhanh theo

## 0.1.1 — 2026-07-31

### Added

- Offline translate provider: **NLLB-200 distilled 600M** (`--translate-provider nllb`)
- Offline TTS provider: **XTTS-v2 / viXTTS** (`--tts-provider xtts-v2`)
- Settings UI chọn provider + tải model NLLB/XTTS
- `engine/requirements-offline.txt` (torch, transformers, Coqui TTS)
- Doctor kiểm tra deps/model khi bật offline

### Notes

- XTTS khuyến nghị GPU; license Coqui CPML (không thương mại)
- Provider selection được lưu job options để resume/retry/continue

## 0.1.0 — 2026-07-31

### Added

- Engine Python module hóa (`engine/dubvi`) với JSONL events, job cache, cancel/retry
- Hàng đợi tuần tự, đa định dạng (MP4/MKV/MOV/AVI/WebM)
- Ba chế độ audio: `vi_only`, `dual_track`, `mix`
- Review/sửa bản dịch trước TTS
- Provider interface (Community: deep-translator + edge-tts)
- Quản lý model Whisper trong `%LOCALAPPDATA%/DubVI/models`
- Desktop React + Tauri v2 (Process / Transcript / Settings)
- Friendly error UI + doctor/privacy notice
- Build scripts: download-ffmpeg, build-engine, build-desktop, verify, clean

### Notes

- Bản mặc định CPU; GPU NVIDIA tách `requirements-gpu-nvidia.txt`
- Model Whisper không bundle trong installer
- Icon hiện là placeholder
