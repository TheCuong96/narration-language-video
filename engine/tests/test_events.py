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
