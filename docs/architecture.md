# Architecture — Dub VI v0.1

## Tổng quan

```
┌──────────────────────────┐
│  React + TypeScript UI   │  (Tauri WebView)
└────────────┬─────────────┘
             │ invoke / events (JSON)
┌────────────▼─────────────┐
│  Tauri v2 shell (Rust)   │  dialogs, drag-drop, spawn
└────────────┬─────────────┘
             │ stdout JSONL / argv
┌────────────▼─────────────┐
│  DubVIEngine (Python)    │  PyInstaller sidecar
│  + bundled ffmpeg/ffprobe│
└──────────────────────────┘
```

## Engine (`engine/dubvi`)

| Module | Vai trò |
|--------|---------|
| `pipeline.py` | Hàng đợi tuần tự, resume, review pause |
| `transcription.py` | faster-whisper, CPU mặc định, GPU fallback |
| `translation.py` | Provider interface → deep-translator hoặc NLLB offline |
| `tts.py` | Provider interface → edge-tts hoặc XTTS-v2 offline |
| `ffmpeg.py` / `audio.py` | Extract FLAC, align, mux (copy video khi được) |
| `models_manager.py` | Tải/xóa Whisper/NLLB/XTTS → `%LOCALAPPDATA%/DubVI/models` |
| `jobs.py` / `queue.py` | Job id, cancel flag, queue.json |
| `providers/` | Community + offline NLLB/XTTS + stub Google/Azure |

## IPC

Engine ghi **một JSON object / dòng** lên stdout:

- `stage`, `progress`, `warning`, `error` (+ `friendly`), `queue_updated`
- `review_ready`, `file_completed`, `completed`, `cancelled`

Không parse tiến độ từ log tự do.

## Dữ liệu người dùng

| Path | Nội dung |
|------|----------|
| `%LOCALAPPDATA%/DubVI/jobs/<id>` | Cache job (giữ khi fail để resume) |
| `%LOCALAPPDATA%/DubVI/models` | Whisper models |
| `%LOCALAPPDATA%/DubVI/logs` | Log kỹ thuật |
| `%LOCALAPPDATA%/DubVI/settings.json` | Settings |

Uninstall **không** xóa video/output người dùng. AppData có thể giữ lại (cache/model).

## Đóng gói

1. `download-ffmpeg.ps1` → `resources/bin`
2. `build-engine.ps1` → PyInstaller → Tauri `externalBin`
3. `build-desktop.ps1` → Tauri NSIS → `release/DubVI_0.1.0_x64-setup.exe` + `.sha256`

CUDA **không** nằm trong `requirements-base.txt`.
