from __future__ import annotations

import io
import json
import sys

from dubvi import events
from dubvi.models import ErrorCode, Stage


def test_emit_json_line():
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        events.set_json_mode(True)
        events.stage(Stage.TRANSCRIBING, "Đang nhận dạng lời nói")
        events.progress(Stage.TRANSCRIBING, 40, 100)
        events.error(ErrorCode.TTS_FAILED, "Không thể tạo giọng đọc", fatal=False)
        events.completed("lesson-vi.mp4")
    finally:
        sys.stdout = old

    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) == 4
    types = [json.loads(ln)["type"] for ln in lines]
    assert types == ["stage", "progress", "error", "completed"]
    assert json.loads(lines[2])["code"] == "TTS_FAILED"
    assert "Đang nhận dạng" in json.loads(lines[0])["message"]


def test_emit_survives_legacy_stdout_encoding():
    """Windows/PyInstaller often leave stdout as cp1252; Vietnamese must still emit."""

    class LegacyStdout(io.TextIOBase):
        encoding = "cp1252"

        def __init__(self) -> None:
            self.buffer = io.BytesIO()

        def write(self, s: str) -> int:  # type: ignore[override]
            # Simulate Windows text mode: encode with stream encoding.
            self.buffer.write(s.encode(self.encoding))
            return len(s)

        def flush(self) -> None:
            return None

    legacy = LegacyStdout()
    old = sys.stdout
    sys.stdout = legacy  # type: ignore[assignment]
    try:
        events.set_json_mode(True)
        # Reset so ensure_utf8_stdio runs again against this stream.
        events._stdio_utf8_ready = False  # noqa: SLF001
        events.stage(Stage.INIT, "Đang tải Whisper model=base device=cpu")
    finally:
        sys.stdout = old

    raw = legacy.buffer.getvalue().decode("utf-8")
    line = json.loads(raw.strip())
    assert line["type"] == "stage"
    assert "Đang tải" in line["message"]
