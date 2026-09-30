# Báo cáo triển khai TranslateGemma — ver8-gemma-ai

Ngày kiểm tra: 2026-10-01 (Asia/Saigon). Không commit, push hoặc tạo PR.

## Kiến trúc

Giữ nguyên React + TypeScript → Tauri v2/Rust → Python CLI/JSONL → PyInstaller onedir.
TranslateGemma là provider riêng gọi Ollama HTTP qua 127.0.0.1:11434. Ollama/model không được bundle hoặc tự cài/tải khi mở app.
Registry chấp nhận translategemma (alias 4B) và ba tag allowlist 4B/12B/27B.
Model catalog dispatch theo runtime, batch marker validation/splitting, fingerprint cache và local-first fallback nằm ở các module riêng.
Google dùng limiter thread-safe 4 requests/s cùng cooldown 2/4/8/16s. deep-translator batch thực chất lặp từng request; Dub VI tự điều phối các request tuần tự để mỗi đoạn thành công chỉ gửi một lần.

## Lỗi gốc đã tìm thấy và sửa

1. Google nhiều luồng + retries + backend phụ có thể vượt quota; thay bằng limiter/cooldown chung và batch tuần tự.
2. Cache chỉ kiểm tra số đoạn và text_vi; thêm fingerprint source/target/provider/model/prompt/terms/text/id/timestamp/chính sách fallback.
3. Pipeline TTS/MUX/chunk AUTO có shortcut bỏ qua fingerprint; thêm kiểm tra trước reuse và metadata cho chunk merged cache.
4. Timestamp số nguyên/số thực có cùng giá trị tạo hash khác nhau; chuẩn hóa float trong fingerprint.
5. Python có translate_concurrency nhưng TS/Rust không truyền; thêm settings/default/JobOptions/CLI/job persistence đầy đủ.
6. Resume/retry/continue chưa lưu đủ source/target/terms; lưu và khôi phục cùng provider/batch/fallback.
7. Tải model UI đóng listener ngay khi Rust spawn trả về, mất progress và refresh catalog quá sớm; chờ terminal JSONL event.
8. Rust loại bỏ doctor JSON khi CLI exit nonzero; giữ report checks để UI hiển thị hướng dẫn.
9. Unit test Google cũ gọi mạng thật; chuyển sang mock, chặn HTTP trong unit tests và opt-in integration.
10. Build Windows gặp WinError 206 ở license PyTorch lồng sâu; rút ngắn đường dẫn license, giữ mọi nội dung và index ánh xạ.

## Kiểm thử đã thực hiện

- `python -m pytest tests -q`: **166 passed, 3 skipped**; unit tests không gọi HTTP thật.
- `npm run typecheck`: đạt.
- `npm run build`: đạt.
- `node scripts/test-privacy-banner.mjs`: đạt cho NLLB, ba TranslateGemma và cảnh báo opt-in Google.
- `node scripts/test-model-download.mjs`: đạt lifecycle spawn/progress/completed/error và lọc model terminal event.
- Ollama thật v0.34.4, model **translategemma:12b** đã có sẵn: integration dịch câu đơn và batch hai câu **1 passed** (40,21 giây).
- NLLB CPU thật: dịch batch hai câu Anh → Việt thành công, process exit 0.
- XTTS CPU thật: tạo WAV tiếng Việt 196.140 byte trong thư mục build kiểm thử, process exit 0.
- Không tải hoặc xóa model của người dùng để kiểm thử. 12B/27B đã có; model 4B hiện mang tag latest, chưa có tag :4b.
- `git diff --check`: đạt (chỉ cảnh báo line endings Git trên Windows).

## Build thực tế

- Lần build-engine đầu thất bại WinError 206 tại license tree PyTorch; spec đã được sửa để giữ license ở đường dẫn ngắn.
- Download FFmpeg từ Gyan bị treo trước khi nhận dữ liệu; tiến trình đã dừng. Dùng FFmpeg/ffprobe static có sẵn qua Winget, bản N-125365-g9a01c1cb6a-20260630, copy vào resource checkout và kiểm tra version.
- `cargo check` trước khi có resource thất bại vì thiếu resources/bin/ffmpeg.exe; FFmpeg resource đã bổ sung.
- `cargo check` sau khi bổ sung resource: đạt. Rust release build: đạt; còn một warning scan_folder không dùng đã có trước.
- PyInstaller onedir sau sửa license: đạt. Frozen sidecar gọi catalog `/api/tags` thành công. Archive cập nhật đã được so sánh bytecode với source: cả 32 module Dub VI khớp.
- `scripts/build-desktop.ps1`: đạt toàn bộ engine/frontend/Rust/NSIS, installer LZMA đầu 422,9 MB.
- Sau khi source Python được cập nhật trong lúc build dài, tái tạo PYZ/EXE từ dependency TOC đã phân tích và xác nhận bytecode cả 32 module khớp source. Copy EXE mới vào onedir, đóng gói Tauri lần cuối thành công bằng override nén ZLIB để giảm thời gian (không thay cấu hình repo mặc định LZMA).
- Installer cuối: `release/DubVI_0.1.0_x64-setup.exe`, **601,4 MB**, build 2026-10-01 03:14:29 giờ máy. SHA256: `f34e1f5dc35425f8981bc6d33af8a902014adb5232d03f7e8a61d8fa8ef449cf`.
- `scripts/publish-installer.ps1`: đạt; `scripts/verify-package.ps1`: **VERIFY PASSED**, exit 0. Xác nhận checksum, FFmpeg, certifi, catalog frozen ba model Ollama, không GGUF/Ollama runtime và không video/.env trong release.

## Chạy dev

```powershell
cd engine
python -m pip install -r requirements-base.txt
python -m dubvi doctor
cd ../desktop
npm ci
npm run tauri dev
```

NLLB/XTTS dev còn cần requirements-offline.txt như README.

## Kiểm tra TranslateGemma

Cài/mở Ollama từ https://ollama.com/download. Settings → chọn tag → Kiểm tra Ollama → nhóm Ollama quản lý → Tải (xác nhận 3,3/8,1/17 GB) → đợi Sẵn sàng → Lưu nhà cung cấp.
Batch 0 tự động (CPU 8, Auto 16), 1–32 số subtitle/lượt; Ollama quyết định thiết bị suy luận.
Chọn XTTS nếu muốn cả dịch và giọng đọc local. Fallback Google mặc định false.

```powershell
cd engine
python -m dubvi models --kind translate
$env:DUBVI_TEST_INTEGRATION = "1"
$env:DUBVI_TEST_OLLAMA = "1"
$env:DUBVI_TEST_OLLAMA_MODEL = "translategemma:12b"
python -m pytest tests/test_ollama_integration.py -q
```

## Build installer

Từ root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-engine.ps1
powershell -ExecutionPolicy Bypass -File scripts/build-desktop.ps1
powershell -ExecutionPolicy Bypass -File scripts/verify-package.ps1
```

build-desktop tự gọi build-engine. Output mong đợi release/DubVI_0.1.0_x64-setup.exe cùng .sha256.
verify-package kiểm tra catalog của frozen sidecar, certifi, không GGUF/Ollama executable trong payload.

## Giới hạn kiểm chứng

- Chưa thao tác pull/delete model thật qua UI để tránh thay đổi kho model người dùng; API dispatch/progress/delete được mock test, UI download lifecycle được test.
- Chưa chạy suy luận thật 4B/27B hoặc benchmark chất lượng/dài hạn.
- Chưa chạy full video thực với review/resume/retry/NLLB/XTTS hoặc installer trong Windows VM sạch; unit regression tests đã đạt.
- NLLB và XTTS đã smoke test suy luận thật riêng lẻ; chưa chứng minh cả pipeline video/end-to-end qua UI.
- Bộ dependency offline trên máy build khá lớn, khiến PyInstaller phân tích lâu và installer có thể nặng dù không bundle TranslateGemma/Ollama.
- Gemma Terms of Use áp dụng cho model; Dub VI không sở hữu trọng số hoặc được Google bảo trợ. Nếu bundle trọng số trong tương lai cần NOTICE và điều khoản Gemma.

## File thêm/sửa

- `CHANGELOG.md`
- `README.md`
- `desktop/scripts/test-model-download.mjs`
- `desktop/scripts/test-privacy-banner.mjs`
- `desktop/src-tauri/src/engine.rs`
- `desktop/src-tauri/src/lib.rs`
- `desktop/src/App.tsx`
- `desktop/src/components/PrivacyBanner.tsx`
- `desktop/src/lib/engine.ts`
- `desktop/src/lib/types.ts`
- `desktop/src/pages/SettingsPage.tsx`
- `docs/architecture.md`
- `docs/privacy.md`
- `docs/release-checklist.md`
- `docs/translategemma-implementation-report.md`
- `desktop/src-tauri/Cargo.toml`
- `engine/DubVIEngine.spec`
- `engine/dubvi/cache.py`
- `engine/dubvi/chunks.py`
- `engine/dubvi/cli.py`
- `engine/dubvi/models.py`
- `engine/dubvi/models_manager.py`
- `engine/dubvi/ollama_manager.py`
- `engine/dubvi/pipeline.py`
- `engine/dubvi/providers/__init__.py`
- `engine/dubvi/providers/community.py`
- `engine/dubvi/providers/fallback.py`
- `engine/dubvi/providers/ollama.py`
- `engine/dubvi/settings_store.py`
- `engine/dubvi/translation.py`
- `engine/requirements-base.txt`
- `engine/tests/conftest.py`
- `engine/tests/test_google_rate_limit.py`
- `engine/tests/test_ollama_integration.py`
- `engine/tests/test_ollama_manager.py`
- `engine/tests/test_ollama_provider.py`
- `engine/tests/test_translation_cache_provider.py`
- `engine/tests/test_translation_fallback.py`
- `engine/tests/test_translation_job_options.py`
- `engine/tests/test_translation_terms.py`
- `scripts/build-engine.ps1`
- `scripts/download-ffmpeg.ps1`
- `scripts/verify-package.ps1`
