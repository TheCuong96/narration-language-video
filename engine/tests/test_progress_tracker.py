from dubvi.models import Stage
from dubvi.progress import OVERALL_WEIGHT_TOTAL, ProgressTracker, overall_from_stage_fracs


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


def test_overall_uses_six_stages_only():
    t = ProgressTracker(file_index=0, file_total=1, file_name="a.mp4")
    t.begin_stage(Stage.INIT)
    t.emit(1, 1)
    assert t.overall_percent() == 0.0
    t.begin_stage(Stage.EXTRACTING)
    t.emit(1, 1)
    assert t.overall_percent() == round(100 * 5 / OVERALL_WEIGHT_TOTAL, 1)
    t.begin_stage(Stage.TRANSCRIBING)
    t.emit(50, 100)
    expected = 100 * (5 + 28 * 0.5) / OVERALL_WEIGHT_TOTAL
    assert abs(t.overall_percent() - round(expected, 1)) < 0.15


def test_overall_from_stage_fracs_all_done():
    fracs = {k: 1.0 for k in (
        Stage.EXTRACTING.value,
        Stage.TRANSCRIBING.value,
        Stage.TRANSLATING.value,
        Stage.TTS.value,
        Stage.ALIGNING.value,
        Stage.MUXING.value,
    )}
    assert overall_from_stage_fracs(fracs) == 100.0


def test_chunk_early_progress_advances_transcribe_and_translate():
    t = ProgressTracker(file_index=0, file_total=1, file_name="long.mp4")
    t.begin_stage(Stage.EXTRACTING)
    t.emit(1, 1)
    t.begin_stage(Stage.TRANSCRIBING, "chunk")
    t.emit_chunk_early_progress(2, 4, "half")
    expected = 100 * (5 + 28 * 0.5 + 12 * 0.5) / OVERALL_WEIGHT_TOTAL
    assert abs(t.overall_percent() - round(expected, 1)) < 0.15


def test_two_files_split_overall():
    t0 = ProgressTracker(file_index=0, file_total=2, file_name="a.mp4")
    t0.complete_file()
    assert t0.overall_percent() == 50.0
    t1 = ProgressTracker(file_index=1, file_total=2, file_name="b.mp4")
    t1.complete_file()
    assert t1.overall_percent() == 100.0


def test_progress_never_moves_backwards_on_repeated_or_resumed_events():
    t = ProgressTracker(file_index=0, file_total=1, file_name="resume.mp4")
    t.begin_stage(Stage.EXTRACTING)
    t.emit(1, 1)
    t.begin_stage(Stage.TRANSCRIBING)
    t.emit(80, 100)
    high = t.overall_percent()

    # A delayed callback from the same stage must not lower either bar.
    t.emit(20, 100)
    assert t.overall_percent() == high

    # Re-labelling the same active stage must preserve its partial fraction,
    # not accidentally close it as 100%.
    t.begin_stage(Stage.TRANSCRIBING, "Đổi mô tả nhưng vẫn cùng công đoạn")
    assert t.overall_percent() == high

    # Cache/resume may announce an earlier stage after a later one.
    t.begin_stage(Stage.TRANSLATING)
    t.emit(50, 100)
    later = t.overall_percent()
    t.begin_stage(Stage.TRANSCRIBING)
    t.emit(0, 100)
    assert t.overall_percent() >= later


def test_progress_event_contains_measured_stage_times(monkeypatch):
    emitted: list[dict] = []
    clock = iter(float(i) for i in range(20))
    monkeypatch.setattr("dubvi.progress.time.perf_counter", lambda: next(clock))
    monkeypatch.setattr("dubvi.progress.events.stage", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "dubvi.progress.events.progress",
        lambda *args, **kwargs: emitted.append(kwargs),
    )

    t = ProgressTracker(file_index=0, file_total=1, file_name="timed.mp4")
    t.begin_stage(Stage.EXTRACTING)
    t.emit(1, 1)
    t.begin_stage(Stage.TRANSCRIBING)

    payload = emitted[-1]
    assert payload["stage_durations_sec"][Stage.EXTRACTING.value] > 0
    assert payload["stage_elapsed_sec"] >= 0
    assert payload["stage_fracs"][Stage.EXTRACTING.value] == 1.0


def test_parallel_stage_timings_are_split_without_double_counting(monkeypatch):
    clock = iter([0.0, 2.0, 10.0, 10.0])
    monkeypatch.setattr("dubvi.progress.time.perf_counter", lambda: next(clock))
    monkeypatch.setattr("dubvi.progress.events.stage", lambda *args, **kwargs: None)
    monkeypatch.setattr("dubvi.progress.events.progress", lambda *args, **kwargs: None)

    t = ProgressTracker(file_index=0, file_total=1, file_name="chunks.mp4")
    t.begin_stage(Stage.TRANSCRIBING)
    t.split_current_stage_timing(
        {Stage.TRANSCRIBING: 3.0, Stage.TRANSLATING: 1.0}
    )
    timings = t._timing_snapshot()

    assert timings[Stage.TRANSCRIBING.value] == 7.5
    assert timings[Stage.TRANSLATING.value] == 2.5
    assert sum(timings.values()) == 10.0
