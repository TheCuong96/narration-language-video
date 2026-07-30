from dubvi.errors_ui import friendly_error
from dubvi.models import ErrorCode


def test_disk_space_friendly_keeps_numbers():
    detail = "Cần ít nhất 12.0 GB nhưng ổ đĩa chỉ còn 7.0 GB (D:\\out)."
    fe = friendly_error(ErrorCode.DISK_SPACE_LOW, detail)
    assert fe.title == "Không đủ dung lượng ổ cứng"
    assert "12.0 GB" in fe.message
    assert "7.0 GB" in fe.message


def test_unknown_code_fallback():
    fe = friendly_error("SOMETHING_NEW", "chi tiết")
    assert fe.code == "SOMETHING_NEW"
    assert "chi tiết" in fe.message
