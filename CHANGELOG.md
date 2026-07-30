# Changelog

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
