from dubvi.models import Stage
from dubvi.progress import ProgressTracker


def test_overall_increases_across_stages():
    t = ProgressTracker(file_index=0, file_total=1, file_name="a.mp4")
    t.begin_stage(Stage.EXTRACTING)
    t.emit(1, 1)
    after_extract = t.overall_percent()
    t.begin_stage(Stage.TRANSCRIBING)
    t.emit(50, 100)
    mid = t.overall_percent()
    assert mid > after_extract
    t.emit(100, 100)
    t.begin_stage(Stage.TRANSLATING)
    t.emit(100, 100)
    assert t.overall_percent() > mid


def test_two_files_split_overall():
    t0 = ProgressTracker(file_index=0, file_total=2, file_name="a.mp4")
    t0.complete_file()
    assert t0.overall_percent() == 50.0
    t1 = ProgressTracker(file_index=1, file_total=2, file_name="b.mp4")
    t1.complete_file()
    assert t1.overall_percent() == 100.0
