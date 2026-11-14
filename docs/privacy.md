# Privacy — Dub VI Community

## Chạy local

- **Whisper** nhận dạng lời nói trên máy bạn.
- **FFmpeg** tách/ghép media trên máy bạn.
- File video gốc và video kết quả **không** được gửi tới server của Dub VI.
- **NLLB** (nếu chọn) dịch trên máy bạn.
- **XTTS-v2** (nếu chọn) tạo giọng trên máy bạn.

## Cần Internet

| Thành phần | Dữ liệu rời máy |
|------------|-----------------|
| deep-translator (Google Translate web) | Các đoạn transcript văn bản |
| edge-tts | Các đoạn text tiếng Việt để tạo giọng |
| Tải model Whisper / NLLB / XTTS (Hugging Face) | Tên model / file model |

Khi chọn **nllb** + **xtts-v2**, sau khi model đã tải xong thì transcript và TTS **không** gửi ra mạng.

## Không làm

- Không upload video lên backend Dub VI (không có backend cloud trong v0.1).
- Không đăng nhập / thanh toán trong v0.1.
- Không ghi API key vào log.
- Không ghi toàn bộ transcript vào log công khai (log kỹ thuật chỉ metadata/tiến độ; tránh dump nội dung nhạy cảm).

## License offline TTS

XTTS-v2 / viXTTS dùng **Coqui Public Model License (CPML)** — thường **không dùng thương mại**. Dùng cá nhân/nghiên cứu; kiểm tra license trước khi phân phối nội dung thương mại.

## Provider tương lai

Interface đã chuẩn bị cho Google Cloud Translation/TTS và Azure Speech (API key của người dùng). **Chưa triển khai** trong Community v0.1.


## TranslateGemma / Ollama

TranslateGemma dịch qua HTTP `127.0.0.1:11434`. Sau khi model đã tải, transcript không rời máy qua provider này.
App chỉ chấp nhận localhost/127.0.0.1, không nhận URL tùy ý từ UI, không theo redirect hoặc proxy môi trường.
Tải model bằng Ollama cần Internet; request tải chỉ chứa tên model. Model và runtime không bundle trong installer và không tự tải/cài lúc khởi động.
Ba tag được phép: `translategemma:4b`, `translategemma:12b`, `translategemma:27b` (3,3/8,1/17 GB gần đúng).

NLLB/TranslateGemma lỗi có thể chuyển sang provider local đã tải. **Không âm thầm gửi tới Google**: `translate_fallback_online=false` mặc định.
Nếu người dùng bật fallback Google, UI/CLI privacy notice nêu rõ transcript có thể gửi Google khi local lỗi.
Chọn edge-tts vẫn gửi text tạo giọng online; muốn cả dịch và TTS local, chọn TranslateGemma hoặc NLLB cùng XTTS.

TranslateGemma dùng Gemma Terms of Use; Dub VI không sở hữu model hoặc được Google bảo trợ.
Nếu bundle trọng số trong tương lai phải bổ sung NOTICE và điều khoản Gemma; hiện tại trọng số do người dùng yêu cầu Ollama tải riêng.
