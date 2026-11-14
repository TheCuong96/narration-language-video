from pathlib import Path

from dubvi.mei_cleanup import cleanup_orphan_mei_dirs


def test_cleanup_removes_orphan_mei(tmp_path, monkeypatch):
    temp = tmp_path / "Temp"
    temp.mkdir()
    orphan = temp / "_MEI12345"
    orphan.mkdir()
    (orphan / "marker.txt").write_text("x", encoding="utf-8")
    keep = temp / "_MEI99999"
    keep.mkdir()
    (keep / "keep.txt").write_text("y", encoding="utf-8")
    other = temp / "not-mei"
    other.mkdir()

    monkeypatch.setattr("dubvi.mei_cleanup.tempfile.gettempdir", lambda: str(temp))
    monkeypatch.setattr("dubvi.mei_cleanup.sys", type("S", (), {"_MEIPASS": str(keep)})())

    removed = cleanup_orphan_mei_dirs()
    assert removed == 1
    assert not orphan.exists()
    assert keep.exists()
    assert other.exists()
