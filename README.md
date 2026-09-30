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


## TranslateGemma qua Ollama (Windows)

1. Cài Ollama từ [trang tải chính thức](https://ollama.com/download), rồi mở Ollama.
2. Mở Dub VI → Settings → chọn TranslateGemma 4B, 12B hoặc 27B.
3. Bấm **Kiểm tra Ollama** / **Làm mới danh sách**. Trong nhóm **Ollama quản lý**, bấm **Tải** và xác nhận dung lượng.
4. Đợi **Sẵn sàng**, lưu nhà cung cấp rồi chạy video. Chọn XTTS nếu cũng muốn tạo giọng hoàn toàn local.

Dung lượng gần đúng: **4B 3,3 GB**, **12B 8,1 GB**, **27B 17 GB**; RAM/VRAM cần thêm cho suy luận. 4B là lựa chọn khuyến nghị.
Dub VI chỉ gọi HTTP localhost `127.0.0.1:11434`; model và Ollama **không nằm trong installer**, không tự cài/tải lúc mở app.
Model do Ollama lưu và quản lý; không dùng thư mục `%LOCALAPPDATA%\DubVI\models` cho TranslateGemma.

Kích thước batch: `0` tự động (CPU 8, Auto 16), hoặc `1–32` subtitle/lượt. Mỗi lượt chỉ có một request Ollama; marker giữ id/timestamp/thứ tự và batch thiếu marker được chia nhỏ.
Google dùng batch tuần tự (mặc định 12 đoạn), limiter tối đa 4 request/giây và cooldown 2/4/8/16 giây khi bị rate limit.
Cache dịch có fingerprint ngôn ngữ, provider/model, phiên bản prompt, protected terms và text nguồn theo thứ tự; đổi provider dịch lại, giữ transcript nguồn.

Fallback local: NLLB ↔ TranslateGemma 4B nếu model thay thế đã cài. **Fallback Google mặc định tắt**; chỉ gửi transcript online nếu bật checkbox rõ ràng.

### Xử lý sự cố

- **Ollama chưa chạy / port 11434 không kết nối**: mở Ollama, kiểm tra dịch vụ local và firewall. NLLB/Google vẫn dùng được.
- **Model chưa tải**: Settings → nhóm Ollama → Tải đúng tag `translategemma:4b`, `:12b` hoặc `:27b`. Tag `latest` không thay thế tag `4b` trong catalog.
- **Hết RAM/VRAM / timeout**: đóng ứng dụng dùng bộ nhớ, chọn 4B và giảm batch; thử CPU/Auto phù hợp máy. Ollama tự quyết định thiết bị suy luận, tùy chọn thiết bị Dub VI điều chỉnh batch/Whisper/NLLB.
- **Tải bị ngắt**: thử lại từ Settings; Ollama quản lý việc tải tiếp. Tải cần Internet, dịch sau khi tải chạy local.
- **Xóa model**: bấm Xóa và xác nhận trong nhóm Ollama; không xóa dữ liệu media.

TranslateGemma chịu **Gemma Terms of Use**, xem [model chính thức và hướng dẫn prompt](https://ollama.com/library/translategemma).
Dub VI không sở hữu trọng số và không tuyên bố được Google bảo trợ. Hiện không bundle model; nếu phân phối trọng số trong tương lai cần bổ sung NOTICE và điều khoản Gemma.

### Kiểm tra CLI và model thật

```powershell
cd engine
python -m dubvi models --kind translate
python -m dubvi doctor
# Tải chỉ khi người dùng yêu cầu:
python -m dubvi models-download translategemma:4b
# Unit tests không gọi mạng:
python -m pytest tests -q
# Integration, chỉ dùng model đã tải:
$env:DUBVI_TEST_INTEGRATION = "1"
$env:DUBVI_TEST_OLLAMA = "1"
$env:DUBVI_TEST_OLLAMA_MODEL = "translategemma:4b"
python -m pytest tests/test_ollama_integration.py -q
```

Kiểm tra PrivacyBanner: `cd desktop; node scripts/test-privacy-banner.mjs`.
Build đầy đủ từ root: `scripts/build-engine.ps1`, `scripts/build-desktop.ps1`, rồi `scripts/verify-package.ps1` (PowerShell `-ExecutionPolicy Bypass -File`).
Sidecar onedir chứa requests/urllib3/certifi; Tauri dùng `CREATE_NO_WINDOW`, không cần Python ngoài trên máy người dùng.
