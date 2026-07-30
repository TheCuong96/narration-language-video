# Phase 1 — Báo cáo & kết quả refactor engine

## 1. Cấu trúc hiện tại (trước refactor)

| File | Vai trò |
|------|---------|
| `dub_vi.py` | Monolith: FFmpeg + Whisper + translate + TTS + mux + CLI |
| `dub_vi_gui.py` | Tkinter GUI gọi `sys.executable dub_vi.py` |
| `dub_deps.py` | Auto-install pip/FFmpeg khi chạy (không phù hợp ship) |
| `install_desktop_app.ps1` | Copy script + shortcut, vẫn phụ thuộc Python hệ thống |

**Giữ nguyên** các file trên cho đến khi bản Tauri build thành công.

## 2. Luồng xử lý

`extract → transcribe → translate → TTS → align/tempo → mux`  
Video gốc không bị ghi đè (chỉ đọc).

## 3. Dependency

- **Base (CPU):** `faster-whisper`, `edge-tts`, `deep-translator` + FFmpeg bundle (sau)
- **GPU (tùy chọn):** `nvidia-cublas-cu12`, `nvidia-cudnn-cu12` — tách khỏi bản mặc định

## 4. Lỗi đóng gói (đã xác định)

- GUI gọi Python script → người dùng phải có Python
- `ensure_deps` cài pip/winget lúc runtime → không chấp nhận được khi ship
- WAV PCM full video phình ổ cứng
- Log tự do → UI khó parse tiến độ
- Không có cancel/resume/job id chuẩn
- PyInstaller chưa có; FFmpeg chưa bundle

## 5. Rủi ro video dài

- Whisper + TTS từng đoạn: thời gian dài, dễ lỗi mạng TTS/dịch
- Cache bắt buộc để resume
- FLAC thay WAV giảm dung lượng tạm
- Spillover: không cắt cuối câu VI khi dài hơn timestamp

## 6. Phase 1 đã triển khai

Thư mục mới:

```
engine/
├── dubvi/          # package engine
├── tests/
├── requirements-base.txt
├── requirements-gpu-nvidia.txt
└── DubVIEngine.spec
```

Chạy:

```powershell
cd engine
pip install -r requirements-base.txt
python -m dubvi system-info
python -m dubvi run -i "D:\videos\en" -o "D:\videos\vi"
# Hủy: python -m dubvi cancel <job-id>
```

Events JSONL trên stdout; log kỹ thuật: `%LOCALAPPDATA%\DubVI\logs`; job: `%LOCALAPPDATA%\DubVI\jobs\<id>`.
