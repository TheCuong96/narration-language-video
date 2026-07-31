"""Map ErrorCode → friendly Vietnamese messages for the desktop UI."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ErrorCode


@dataclass
class FriendlyError:
    code: str
    title: str
    message: str
    hint: str = ""


FRIENDLY: dict[str, FriendlyError] = {
    ErrorCode.DISK_SPACE_LOW.value: FriendlyError(
        ErrorCode.DISK_SPACE_LOW.value,
        "Không đủ dung lượng ổ cứng",
        "Ổ đĩa không còn đủ chỗ để xử lý video này.",
        "Giải phóng dung lượng hoặc chọn thư mục đầu ra trên ổ khác.",
    ),
    ErrorCode.FFMPEG_MISSING.value: FriendlyError(
        ErrorCode.FFMPEG_MISSING.value,
        "Thiếu FFmpeg",
        "Ứng dụng không tìm thấy ffmpeg. Hãy cài lại Dub VI hoặc kiểm tra bộ cài.",
        "",
    ),
    ErrorCode.FFPROBE_MISSING.value: FriendlyError(
        ErrorCode.FFPROBE_MISSING.value,
        "Thiếu ffprobe",
        "Ứng dụng không tìm thấy ffprobe kèm theo bộ cài.",
        "",
    ),
    ErrorCode.NO_VIDEOS.value: FriendlyError(
        ErrorCode.NO_VIDEOS.value,
        "Chưa có video",
        "Hãy thêm ít nhất một file MP4, MKV, MOV, AVI hoặc WebM.",
        "",
    ),
    ErrorCode.INPUT_NOT_FOUND.value: FriendlyError(
        ErrorCode.INPUT_NOT_FOUND.value,
        "Không tìm thấy file hoặc thư mục",
        "Đường dẫn đầu vào không tồn tại hoặc đã bị di chuyển.",
        "",
    ),
    ErrorCode.UNSUPPORTED_FORMAT.value: FriendlyError(
        ErrorCode.UNSUPPORTED_FORMAT.value,
        "Định dạng không hỗ trợ",
        "Chỉ nhận MP4, MKV, MOV, AVI, WebM mà FFmpeg đọc được.",
        "",
    ),
    ErrorCode.WHISPER_LOAD_FAILED.value: FriendlyError(
        ErrorCode.WHISPER_LOAD_FAILED.value,
        "Không tải được model nhận dạng lời nói",
        "Model nhận dạng lời nói chưa sẵn sàng hoặc bị lỗi.",
        "Mở Settings → Model nhận dạng lời nói để tải lại.",
    ),
    ErrorCode.TRANSCRIBE_FAILED.value: FriendlyError(
        ErrorCode.TRANSCRIBE_FAILED.value,
        "Nhận dạng lời nói thất bại",
        "Không thể tạo transcript từ audio của video.",
        "Thử model lớn hơn hoặc kiểm tra video có tiếng nói rõ không.",
    ),
    ErrorCode.TRANSLATE_FAILED.value: FriendlyError(
        ErrorCode.TRANSLATE_FAILED.value,
        "Dịch thất bại",
        "Không kết nối được dịch vụ dịch (cần Internet).",
        "Kiểm tra mạng rồi thử lại. Transcript đã lưu trong cache.",
    ),
    ErrorCode.TTS_FAILED.value: FriendlyError(
        ErrorCode.TTS_FAILED.value,
        "Tạo giọng đọc thất bại",
        "edge-tts không tạo được audio (cần Internet).",
        "Thử lại; các đoạn đã tạo sẽ được giữ trong cache.",
    ),
    ErrorCode.MUX_FAILED.value: FriendlyError(
        ErrorCode.MUX_FAILED.value,
        "Ghép video thất bại",
        "Không ghi được file đầu ra.",
        "Kiểm tra quyền ghi thư mục và dung lượng ổ cứng.",
    ),
    ErrorCode.CANCELLED.value: FriendlyError(
        ErrorCode.CANCELLED.value,
        "Đã dừng",
        "Tác vụ bị hủy. Bạn có thể chạy lại từ cache.",
        "",
    ),
    ErrorCode.REVIEW_PENDING.value: FriendlyError(
        ErrorCode.REVIEW_PENDING.value,
        "Chờ sửa bản dịch",
        "Hãy xem và chỉnh transcript tiếng Việt trước khi tạo giọng.",
        "",
    ),
    ErrorCode.TRANSLATION_INVALID.value: FriendlyError(
        ErrorCode.TRANSLATION_INVALID.value,
        "Bản dịch không hợp lệ",
        "Một số đoạn tiếng Việt còn trống hoặc sai định dạng.",
        "",
    ),
}


def friendly_error(code: str | ErrorCode, detail: str = "") -> FriendlyError:
    key = code.value if isinstance(code, ErrorCode) else str(code)
    base = FRIENDLY.get(
        key,
        FriendlyError(
            key or "INTERNAL",
            "Đã xảy ra lỗi",
            detail or "Có lỗi không mong muốn khi xử lý.",
            "Bấm «Xem chi tiết kỹ thuật» để sao chép log hỗ trợ.",
        ),
    )
    if detail and key == ErrorCode.DISK_SPACE_LOW.value:
        # Prefer concrete numbers from engine message
        return FriendlyError(base.code, base.title, detail, base.hint)
    if detail and base.message == "Có lỗi không mong muốn khi xử lý.":
        return FriendlyError(base.code, base.title, detail, base.hint)
    if detail and detail not in base.message:
        return FriendlyError(
            base.code,
            base.title,
            f"{base.message}\n\n{detail}",
            base.hint,
        )
    return base
