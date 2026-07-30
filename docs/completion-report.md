# Báo cáo hoàn thành Dub VI v0.1

Ngày: 2026-07-31

## Kết quả chạy thật trên máy phát triển

| Kiểm tra | Kết quả |
|----------|---------|
| `python -m pytest tests -q -m "not integration"` | **24 passed** |
| `npm run typecheck` + `npm run build` | **Pass** |
| `cargo check` (Tauri) | **Pass** |
| `scripts/download-ffmpeg.ps1` | **Pass** (ffmpeg/ffprobe trong `resources/bin`) |
| PyInstaller `DubVIEngine.exe` | **Pass** (~91 MB) |
| `npm run tauri build` (NSIS) | **Pass** |
| `scripts/verify-package.ps1` | **VERIFY PASSED** |
| Artifact | `release/DubVI_0.1.0_x64-setup.exe` (~144 MB) + `.sha256` |
| SHA256 | `507aa230f24b8057cdb09fb61d5df656de54e4efd693e1603ac73b54343fffc4` |

## Chưa xác minh

| Hạng mục | Ghi chú |
|----------|---------|
| Cài trên VM Windows sạch (không Python/FFmpeg/CUDA/Node/Rust) | **Chưa chạy** — làm theo `docs/release-checklist.md` |
| Xử lý video có lời nói thật end-to-end trên máy sạch | **Chưa** |
| Gỡ cài đặt + xác nhận không xóa video người dùng | **Chưa** |
| Integration test có speech + mạng đầy đủ | Có smoke; có thể skip khi thiếu model |

**Không tuyên bố “đã kiểm thử trên máy người dùng sạch”.**

## Source đã hoàn thiện

- Engine JSONL, queue, cancel/retry/resume, review TTS, 3 audio modes, copy-video / reencode warning
- Providers Community + stub trả phí
- Model manager (`%LOCALAPPDATA%/DubVI/models`)
- React UI: Process / Transcript / Settings / Error dialog / privacy
- Build scripts + docs (README, architecture, privacy, checklist, CHANGELOG)

## Lệnh build lại

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-desktop.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1
```

## Bước tiếp theo để đóng v0.1 “ship”

1. Cài `release/DubVI_0.1.0_x64-setup.exe` trên VM sạch  
2. Tick hết mục trong `docs/release-checklist.md`  
3. Thay icon placeholder (`desktop/src-tauri/icons/TODO-ICON.md`)
