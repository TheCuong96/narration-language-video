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
