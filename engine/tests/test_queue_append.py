from __future__ import annotations

from pathlib import Path

import pytest

from dubvi import queue
from dubvi.models import QueueItemStatus
from dubvi.system_info import EngineError, job_dir


def _touch_videos(tmp: Path, names: list[str]) -> list[Path]:
    out = []
    for n in names:
        p = tmp / n
        p.write_bytes(b"x")
        out.append(p)
    return out


def test_append_videos_mid_job(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    job_id = "appendjob01"
    job_dir(job_id)
    vids = _touch_videos(tmp_path, ["a.mp4", "b.mp4"])
    out = tmp_path / "out"
    out.mkdir()
    queue.init_queue(job_id, [vids[0]], out)
    queue.update_item(job_id, "a", status=QueueItemStatus.RUNNING)

    data, added = queue.append_videos(job_id, [vids[1]], out)
    assert [p.name for p in added] == ["b.mp4"]
    assert len(data["items"]) == 2
    assert data["items"][1]["status"] == QueueItemStatus.PENDING.value
    assert data["items"][1]["stem"] == "b"

    # Duplicate path ignored
    data2, added2 = queue.append_videos(job_id, [vids[1]], out)
    assert added2 == []
    assert len(data2["items"]) == 2


def test_append_rejects_duplicate_stem(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    job_id = "appendjob02"
    job_dir(job_id)
    a = tmp_path / "clip.mp4"
    a.write_bytes(b"x")
    other = tmp_path / "sub"
    other.mkdir()
    b = other / "clip.mp4"
    b.write_bytes(b"y")
    out = tmp_path / "out"
    out.mkdir()
    queue.init_queue(job_id, [a], out)

    with pytest.raises(EngineError):
        queue.append_videos(job_id, [b], out)


def test_next_work_item_picks_appended_pending(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    job_id = "appendjob03"
    job_dir(job_id)
    vids = _touch_videos(tmp_path, ["one.mp4", "two.mp4"])
    out = tmp_path / "out"
    out.mkdir()
    queue.init_queue(job_id, [vids[0]], out)
    queue.update_item(job_id, "one", status=QueueItemStatus.COMPLETED)
    queue.append_videos(job_id, [vids[1]], out)

    nxt = queue.next_work_item(job_id)
    assert nxt is not None
    assert nxt["stem"] == "two"

    queue.update_item(job_id, "two", status=QueueItemStatus.COMPLETED)
    assert queue.next_work_item(job_id) is None


def test_next_work_item_resume_stems(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    job_id = "appendjob04"
    job_dir(job_id)
    vids = _touch_videos(tmp_path, ["x.mp4", "y.mp4"])
    out = tmp_path / "out"
    out.mkdir()
    queue.init_queue(job_id, vids, out)
    queue.update_item(job_id, "x", status=QueueItemStatus.CANCELLED)
    queue.update_item(job_id, "y", status=QueueItemStatus.PENDING)

    # Pending wins first (y before cancelled x if y is second... order is queue order)
    # x is first in queue but cancelled; also_stems includes x → x is eligible
    # pending y also eligible — first matching in order is x (cancelled + also)
    nxt = queue.next_work_item(job_id, also_stems=["x"])
    assert nxt is not None
    assert nxt["stem"] == "x"


def test_next_work_item_skips_already_attempted_failed(monkeypatch, tmp_path: Path):
    """A stem that failed again must not block later resume stems."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))

    job_id = "appendjob05"
    job_dir(job_id)
    vids = _touch_videos(tmp_path, ["a.mp4", "b.mp4"])
    out = tmp_path / "out"
    out.mkdir()
    queue.init_queue(job_id, vids, out)
    queue.update_item(job_id, "a", status=QueueItemStatus.FAILED)
    queue.update_item(job_id, "b", status=QueueItemStatus.FAILED)

    first = queue.next_work_item(job_id, also_stems=["a", "b"])
    assert first is not None and first["stem"] == "a"

    # After attempting a (still failed), exclude it so b can run.
    second = queue.next_work_item(
        job_id, also_stems=["a", "b"], exclude_stems={"a"}
    )
    assert second is not None and second["stem"] == "b"
