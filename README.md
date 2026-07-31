# Dub VI

Ứng dụng desktop Windows để **lồng tiếng Việt** cho video (Community v0.1).

Whisper + FFmpeg chạy **trên máy bạn**. Mặc định dịch (`deep-translator`) và `edge-tts` cần **Internet**. Có thể chọn offline: **NLLB** + **XTTS-v2** (cài `engine/requirements-offline.txt` + tải model trong Settings). Video **không** được upload lên server của Dub VI.

## Người dùng cuối

1. Cài `release/DubVI_0.1.0_x64-setup.exe`
2. Mở **Dub VI** từ Start Menu
3. Settings → tải model Whisper (đề xuất **small** trên CPU)
4. Kéo thả video **hoặc dán URL** (yt-dlp tải về máy) → chọn thư mục ra → Bắt đầu
5. (Tuỳ chọn) Sửa bản dịch → tiếp tục tạo giọng

## Nhà phát triển

### Yêu cầu

- Windows 10/11 x64
- Python 3.10+
- Node.js 20+
- Rust + Visual Studio Build Tools (C++)
- Internet (tải FFmpeg / model / dịch / TTS)

### Chạy dev

```powershell
cd engine
pip install -r requirements-base.txt
python -m dubvi doctor

cd ..\desktop
npm install
npm run tauri dev
```

### Build bộ cài

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-desktop.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify-package.ps1
```

Artifact:

- `release/DubVI_0.1.0_x64-setup.exe`
- `release/DubVI_0.1.0_x64-setup.exe.sha256`

### Kiểm thử

```powershell
cd engine
python -m pytest tests -q
# integration (nặng / mạng):
python -m pytest tests -q -m integration
```

```powershell
cd desktop
npm run typecheck
npm run build
```

## Tài liệu

- [docs/architecture.md](docs/architecture.md)
- [docs/privacy.md](docs/privacy.md)
- [docs/release-checklist.md](docs/release-checklist.md)
- [CHANGELOG.md](CHANGELOG.md)
- [docs/completion-report.md](docs/completion-report.md)

### Offline (NLLB + XTTS)

```powershell
cd engine
pip install -r requirements-base.txt
pip uninstall -y TTS coqpit
pip install -r requirements-offline.txt
python -m dubvi models-download nllb-200-distilled-600M
python -m dubvi models-download xtts-v2
```

Nếu TTS báo lỗi `BeamSearchScorer` / `coqpit` / `torchcodec`: gỡ `TTS` cũ rồi cài lại `requirements-offline.txt` như trên.

Trong Settings: chọn dịch **NLLB**, TTS **XTTS-v2**, bật Auto GPU nếu có NVIDIA. XTTS dùng license Coqui CPML (không thương mại).

## Giới hạn v0.1

- Chỉ Windows x64
- Community mặc định: deep-translator + edge-tts (cần mạng)
- Offline NLLB/XTTS là tuỳ chọn (nặng; không nằm trong installer)
- Model Whisper / NLLB / XTTS tải riêng
- GPU NVIDIA là tuỳ chọn (`requirements-gpu-nvidia.txt`), bản mặc định là CPU
- Icon hiện là placeholder (xem `desktop/src-tauri/icons/TODO-ICON.md`)
