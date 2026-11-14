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
2. `build-engine.ps1` → PyInstaller **onedir** → `desktop/src-tauri/resources/engine/`
3. `build-desktop.ps1` → Tauri NSIS → `release/DubVI_0.1.0_x64-setup.exe` + `.sha256`

Engine dùng **onedir** (không onefile): onefile mỗi lần chạy bung ~1GB vào `%TEMP%\_MEI*` và thường không xóa khi bị `taskkill /F`. App vẫn dọn orphan `_MEI*` lúc khởi động / sau khi engine thoát. Có thể chạy thủ công: `scripts/cleanup-mei-temp.ps1`.

CUDA **không** nằm trong `requirements-base.txt`.


## TranslateGemma và cache dịch

Kiến trúc IPC giữ nguyên: React/TypeScript → Rust JobOptions → CLI argv → JSONL events.
`translate_provider` chứa tag đầy đủ; `translate_concurrency` truyền qua mọi tầng (0 tự động, 1–32 batch size).
`translate_fallback_online` mặc định false, được lưu trong settings/job options và khôi phục khi resume/retry/continue.

- `providers/ollama.py`: một user message theo prompt TranslateGemma, hai dòng trống trước text; marker `[[DUBVI_SEG_000001]]` và recursive splitting khi marker sai.
- `ollama_manager.py`: HTTP requests trực tiếp, bỏ proxy môi trường, từ chối redirects, chỉ loopback port 11434 và allowlist 4B/12B/27B. Không có SDK, shell model command, cài runtime hoặc tự tải model.
- `models_manager.py`: `runtime=ollama` dispatch tags/pull/delete, không dùng model_path/Hugging Face. NDJSON pull chuyển thành stage/progress/warning; CLI phát completed/error.
- `providers/fallback.py`: local-first, chỉ Google khi opt-in; không rải logic fallback trong pipeline. Log metadata batch/provider và loại lỗi, không ghi text.
- `translation.py`: batch tuần tự; Ollama request lock dùng chung cả chunk workers. Google limiter thread-safe dùng chung mọi request/retry, cooldown chung khi 429.
- Cache `.json.meta.json` chứa SHA256 fingerprint source/target, provider đầy đủ/model, prompt version, protected terms, text nguồn theo thứ tự, id/timestamp và chính sách fallback. Transcript JSON giữ định dạng list để tương thích review.
- Pipeline kiểm tra fingerprint trước shortcuts TTS/MUX/chunk AUTO; chunk merged cache cũng có metadata. Cache sai giữ transcript EN, xóa cache downstream để giọng đọc khớp bản dịch mới.

Whisper/NLLB/XTTS vẫn do Dub VI quản lý. TranslateGemma do Ollama quản lý ngoài app/installer.
Ollama quyết định GPU/CPU cho suy luận; device mode Dub VI quyết định batch mặc định (8 CPU, 16 Auto) và các engine có sẵn.
