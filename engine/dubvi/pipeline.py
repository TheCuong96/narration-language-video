"""End-to-end dubbing pipeline: sequential queue, review, resume, audio modes."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from . import audio, cache, events, queue, review, transcription, translation, tts
from .jobs import CancellationToken, create_job, update_job_state, video_work_dir
from .models import (
    AudioMode,
    ErrorCode,
    JobConfig,
    QueueItemStatus,
    Stage,
    StartFrom,
)
from .system_info import (
    EngineError,
    ensure_disk_space,
    get_logger,
    setup_logging,
)
from .ffmpeg import probe_duration
from .progress import ProgressTracker

log = get_logger("dubvi.pipeline")


def collect_videos(cfg: JobConfig) -> list[Path]:
    videos = queue.resolve_inputs(
        input_dir=cfg.input_dir,
        input_files=cfg.input_files,
        only=cfg.only or None,
    )
    if cfg.retry_stems:
        keys = {k.lower() for k in cfg.retry_stems}
        videos = [v for v in videos if v.stem.lower() in keys]
        if not videos:
            raise EngineError(ErrorCode.NO_VIDEOS, "Không có video khớp danh sách retry")
    return videos


def _should_skip_extract(work: Path, start_from: StartFrom) -> bool:
    if start_from in (StartFrom.TRANSCRIBE, StartFrom.TRANSLATE, StartFrom.TTS, StartFrom.MUX):
        return (work / cache.AUDIO_FLAC).exists()
    if start_from == StartFrom.AUTO:
        return (work / cache.AUDIO_FLAC).exists()
    return False


def _has_vi(work: Path) -> bool:
    segs = cache.load_segments(work / cache.TRANSCRIPT_VI)
    return bool(segs and all(s.text_vi for s in segs))


def process_one(
    video: Path,
    model,
    cfg: JobConfig,
    job_root: Path,
    cancel: CancellationToken,
    *,
    file_index: int = 0,
    file_total: int = 1,
) -> Path | None:
    """
    Process a single video sequentially.
    Returns output path, or None if paused for translation review.
    """
    name = video.stem
    work = video_work_dir(job_root, name)
    output = queue.output_path_for(video, cfg.output_dir)
    tracker = ProgressTracker(
        file_index=file_index,
        file_total=max(file_total, 1),
        file_name=video.name,
    )

    if output.exists() and not cfg.force and cfg.start_from == StartFrom.AUTO:
        events.log(f"Bỏ qua (đã có): {output.name}")
        events.file_completed(str(video), str(output), skipped=True)
        queue.update_item(cfg.job_id, name, status=QueueItemStatus.SKIPPED, output=str(output))
        tracker.complete_file()
        return output

    if cfg.force and cfg.start_from == StartFrom.AUTO:
        cache.clear_downstream(work, keep_en=True)

    tracker.begin_stage(Stage.INIT, f"Bắt đầu: {video.name}")
    queue.update_item(cfg.job_id, name, status=QueueItemStatus.RUNNING)
    t0 = time.time()
    cancel.check()

    ensure_disk_space(video, work, cfg.output_dir)
    duration = probe_duration(video)
    events.log(f"Độ dài: {duration / 60:.1f} phút")
    tracker.emit(1, 1, f"Độ dài {duration / 60:.1f} phút")

    # --- extract ---
    if cfg.start_from == StartFrom.EXTRACT or not _should_skip_extract(work, cfg.start_from):
        if cfg.start_from == StartFrom.EXTRACT:
            flac = work / cache.AUDIO_FLAC
            if flac.exists():
                flac.unlink()
        flac = audio.extract_for_whisper(video, work, tracker=tracker)
    else:
        flac = work / cache.AUDIO_FLAC
        tracker.begin_stage(Stage.EXTRACTING, "Dùng cache âm thanh")
        tracker.emit(1, 1, "Đã có audio.flac")
        events.log("Dùng cache audio.flac")
    cancel.check()

    # --- transcribe ---
    if cfg.start_from in (StartFrom.TRANSCRIBE,):
        tp = work / cache.TRANSCRIPT_EN
        if tp.exists():
            tp.unlink()
    if cfg.start_from in (StartFrom.TRANSLATE, StartFrom.TTS, StartFrom.MUX) and (
        work / cache.TRANSCRIPT_EN
    ).exists():
        segments = cache.load_segments(work / cache.TRANSCRIPT_EN) or []
        tracker.begin_stage(Stage.TRANSCRIBING, "Dùng cache nhận dạng")
        tracker.emit(1, 1, f"Cache: {len(segments)} đoạn")
        events.log("Dùng cache transcript tiếng Anh")
    else:
        segments = transcription.transcribe(
            flac,
            work / cache.TRANSCRIPT_EN,
            model,
            source_lang=cfg.source_lang,
            cancel=cancel,
            tracker=tracker,
            duration_sec=duration,
        )
    events.log(f"Số đoạn: {len(segments)}")
    cancel.check()

    # --- translate ---
    if cfg.start_from == StartFrom.TRANSLATE:
        cache.clear_downstream(work, keep_en=True)

    if cfg.start_from in (StartFrom.TTS, StartFrom.MUX) and _has_vi(work):
        segments_vi = cache.load_segments(work / cache.TRANSCRIPT_VI) or []
        tracker.begin_stage(Stage.TRANSLATING, "Dùng cache bản dịch")
        tracker.emit(1, 1, f"Cache: {len(segments_vi)} đoạn")
        events.log("Dùng cache bản dịch tiếng Việt")
    else:
        segments_vi = translation.translate_segments(
            segments,
            work / cache.TRANSCRIPT_VI,
            source_lang=cfg.source_lang,
            target_lang=cfg.target_lang,
            terms=cfg.terms,
            cancel=cancel,
            tracker=tracker,
            provider_name=cfg.translate_provider,
            prefer_gpu=cfg.prefer_gpu,
        )

    script_path = work / cache.SCRIPT_VI
    lines = [f"[{s.start:.1f}-{s.end:.1f}] {s.text_vi}" for s in segments_vi]
    script_path.write_text("\n".join(lines), encoding="utf-8")

    # --- review pause ---
    if cfg.review_translation or cfg.translate_only:
        payload = review.get_review_payload(cfg.job_id, name)
        tracker.begin_stage(Stage.REVIEW, "Chờ xem / sửa bản dịch")
        tracker.emit(1, 1, "Tạm dừng để review transcript")
        events.review_ready(
            job_id=cfg.job_id,
            stem=name,
            transcript_path=str(work / cache.TRANSCRIPT_VI),
            segments=payload["segments"],
        )
        queue.update_item(cfg.job_id, name, status=QueueItemStatus.REVIEW)
        if cfg.translate_only or cfg.review_translation:
            events.log(
                "Tạm dừng để review. Sửa bản dịch rồi chạy: "
                f"python -m dubvi continue --job-id {cfg.job_id} --stem {name}"
            )
            return None

    # --- TTS + align + mux ---
    return _finish_from_tts(
        video=video,
        work=work,
        output=output,
        segments_vi=segments_vi,
        duration=duration,
        cfg=cfg,
        cancel=cancel,
        t0=t0,
        tracker=tracker,
    )


def _finish_from_tts(
    *,
    video: Path,
    work: Path,
    output: Path,
    segments_vi,
    duration: float,
    cfg: JobConfig,
    cancel: CancellationToken,
    t0: float,
    tracker: ProgressTracker | None = None,
) -> Path:
    cancel.check()
    if cfg.start_from == StartFrom.MUX and (work / cache.NARRATION).exists():
        narration = work / cache.NARRATION
        events.log("Dùng cache narration.wav")
        if tracker:
            tracker.begin_stage(Stage.TTS, "Dùng cache narration")
            tracker.emit(1, 1, "Đã có narration.wav")
            tracker.begin_stage(Stage.ALIGNING, "Bỏ qua căn giờ (đã có narration)")
            tracker.emit(1, 1, "OK")
    else:
        if cfg.start_from == StartFrom.TTS:
            for dname in (cache.SEGMENTS_DIR, cache.FITTED_DIR):
                d = work / dname
                if d.exists():
                    import shutil

                    shutil.rmtree(d, ignore_errors=True)
            narr = work / cache.NARRATION
            if narr.exists():
                narr.unlink()

        mp3_paths = asyncio.run(
            tts.synthesize_all(
                segments_vi,
                work / cache.SEGMENTS_DIR,
                voice=cfg.voice,
                cancel=cancel,
                tracker=tracker,
                provider_name=cfg.tts_provider,
                prefer_gpu=cfg.prefer_gpu,
                speaker_wav=cfg.xtts_speaker_wav,
                language=cfg.target_lang or "vi",
            )
        )
        cancel.check()
        narration = audio.build_narration(
            segments_vi,
            work,
            duration,
            mp3_paths,
            cancel=cancel,
            tracker=tracker,
        )

    cancel.check()
    audio.mux(
        video,
        narration,
        output,
        audio_mode=cfg.audio_mode,
        mix_original_db=cfg.mix_original_db,
        allow_reencode=cfg.allow_reencode,
        tracker=tracker,
    )

    if cfg.cleanup_on_success:
        if tracker:
            tracker.begin_stage(Stage.CLEANUP, "Dọn file tạm")
        else:
            events.stage(Stage.CLEANUP, "Dọn file tạm")
        cache.cleanup_temps_after_success(work, keep_transcripts=True)
        if tracker:
            tracker.emit(1, 1, "Đã dọn tạm")

    if tracker:
        tracker.complete_file()

    elapsed = (time.time() - t0) / 60
    events.log(f"Xong {video.name} → {output.name} ({elapsed:.1f} phút)")
    events.file_completed(str(video), str(output), elapsed_min=round(elapsed, 2))
    queue.update_item(
        cfg.job_id,
        video.stem,
        status=QueueItemStatus.COMPLETED,
        output=str(output),
    )
    return output


def continue_stem(cfg: JobConfig, stem: str) -> int:
    """Continue one video after translation review (TTS → mux)."""
    log_path = setup_logging(cfg.job_id)
    events.set_json_mode(True)
    jid, job_root = create_job(
        output_dir=cfg.output_dir,
        input_dir=cfg.input_dir,
        input_files=cfg.input_files,
        options={"voice": cfg.voice, "audio_mode": cfg.audio_mode.value},
        job_id=cfg.job_id,
        clear_cancel=True,
    )
    cancel = CancellationToken(job_root)
    update_job_state(jid, status="running", log=str(log_path))

    q = queue.load_queue(jid)
    item = None
    if q:
        item = next((i for i in q["items"] if i["stem"] == stem), None)
    if not item:
        events.error(ErrorCode.INPUT_NOT_FOUND, f"Không thấy '{stem}' trong hàng đợi", fatal=True)
        return 1

    video = Path(item["input"])
    work = video_work_dir(job_root, stem)
    segments_vi = cache.load_segments(work / cache.TRANSCRIPT_VI)
    if not segments_vi or not all(s.text_vi for s in segments_vi):
        events.error(
            ErrorCode.TRANSLATION_INVALID,
            "Chưa có bản dịch hợp lệ — hãy lưu bản dịch trước",
            fatal=True,
        )
        return 1

    cfg.start_from = StartFrom.TTS
    cfg.review_translation = False
    cfg.translate_only = False
    try:
        duration = probe_duration(video)
        output = Path(item["output"])
        queue.update_item(jid, stem, status=QueueItemStatus.RUNNING)
        tracker = ProgressTracker(file_index=0, file_total=1, file_name=video.name)
        # Assume earlier stages done when continuing from review
        for st in (
            Stage.INIT,
            Stage.EXTRACTING,
            Stage.TRANSCRIBING,
            Stage.TRANSLATING,
            Stage.REVIEW,
        ):
            tracker.begin_stage(st, f"(đã xong) {st.value}")
            tracker.emit(1, 1, "OK")
        _finish_from_tts(
            video=video,
            work=work,
            output=output,
            segments_vi=segments_vi,
            duration=duration,
            cfg=cfg,
            cancel=cancel,
            t0=time.time(),
            tracker=tracker,
        )
        update_job_state(jid, status="completed")
        events.completed(str(output), job_id=jid, stem=stem)
        return 0
    except EngineError as e:
        if e.code == ErrorCode.CANCELLED:
            events.cancelled(e.message)
            queue.update_item(jid, stem, status=QueueItemStatus.CANCELLED)
            return 2
        events.error(e.code, e.message, fatal=True)
        queue.update_item(jid, stem, status=QueueItemStatus.FAILED, error=e.message, code=e.code.value)
        return 1


def run_job(cfg: JobConfig) -> int:
    """
    Run a full job sequentially (one video at a time to limit RAM).
    Exit: 0 ok, 1 error, 2 cancelled, 3 paused for review.
    """
    log_path = setup_logging(cfg.job_id)
    log.info("job start id=%s log=%s", cfg.job_id, log_path)

    jid, job_root = create_job(
        output_dir=cfg.output_dir,
        input_dir=cfg.input_dir,
        input_files=cfg.input_files,
        options={
            "voice": cfg.voice,
            "model": cfg.whisper_model,
            "prefer_gpu": cfg.prefer_gpu,
            "force": cfg.force,
            "audio_mode": cfg.audio_mode.value,
            "review_translation": cfg.review_translation,
            "translate_provider": cfg.translate_provider,
            "tts_provider": cfg.tts_provider,
            "xtts_speaker_wav": cfg.xtts_speaker_wav,
        },
        job_id=cfg.job_id,
    )
    cfg.job_id = jid
    cancel = CancellationToken(job_root)
    update_job_state(jid, status="running", log=str(log_path))

    events.system(
        {
            "job_id": jid,
            "job_dir": str(job_root),
            "log": str(log_path),
            "input_dir": str(cfg.input_dir) if cfg.input_dir else None,
            "output_dir": str(cfg.output_dir),
            "audio_mode": cfg.audio_mode.value,
        }
    )

    try:
        videos = collect_videos(cfg)
        cfg.output_dir.mkdir(parents=True, exist_ok=True)

        # Init or refresh queue (preserve completed when retrying subset)
        existing = queue.load_queue(jid)
        if not existing or not cfg.retry_stems:
            qdata = queue.init_queue(jid, videos, cfg.output_dir)
        else:
            qdata = existing
        events.queue_updated(qdata)

        need_model = cfg.start_from not in (StartFrom.TTS, StartFrom.MUX)
        model = None
        if need_model:
            # Still may need model if cache missing
            model, device_info = transcription.load_whisper_model(
                cfg.whisper_model,
                prefer_gpu=cfg.prefer_gpu,
            )
            if device_info.fallback_reason:
                events.log(device_info.fallback_reason, level="warn")

        failed: list[str] = []
        review_paused: list[str] = []
        last_output: str | None = None

        for idx, video in enumerate(videos):
            events.progress(
                Stage.QUEUED,
                idx,
                len(videos),
                f"Bắt đầu video {idx + 1}/{len(videos)}: {video.name}",
                percent=0 if len(videos) else 0,
                overall_percent=round(100.0 * idx / max(len(videos), 1), 1),
                file=video.name,
                file_index=idx + 1,
                file_total=len(videos),
                stage_label="Hàng đợi",
            )
            try:
                cancel.check()
                # Lazy-load model if first file that needs it
                if model is None:
                    model, device_info = transcription.load_whisper_model(
                        cfg.whisper_model,
                        prefer_gpu=cfg.prefer_gpu,
                    )
                out = process_one(
                    video,
                    model,
                    cfg,
                    job_root,
                    cancel,
                    file_index=idx,
                    file_total=len(videos),
                )
                if out is None:
                    review_paused.append(video.stem)
                else:
                    last_output = str(out)
                events.queue_updated(queue.load_queue(jid) or {})
            except EngineError as e:
                if e.code == ErrorCode.CANCELLED:
                    events.cancelled(e.message)
                    queue.update_item(jid, video.stem, status=QueueItemStatus.CANCELLED)
                    update_job_state(jid, status="cancelled")
                    return 2
                log.exception("file error %s", video.name)
                events.error(e.code, f"{video.name}: {e.message}", fatal=False)
                queue.update_item(
                    jid,
                    video.stem,
                    status=QueueItemStatus.FAILED,
                    error=e.message,
                    code=e.code.value,
                )
                failed.append(video.name)
                events.queue_updated(queue.load_queue(jid) or {})
            except Exception as e:
                log.exception("unexpected %s", video.name)
                events.error(ErrorCode.INTERNAL, f"{video.name}: {e}", fatal=False)
                queue.update_item(
                    jid,
                    video.stem,
                    status=QueueItemStatus.FAILED,
                    error=str(e),
                    code=ErrorCode.INTERNAL.value,
                )
                failed.append(video.name)

        if review_paused and not failed:
            update_job_state(jid, status="review", review_stems=review_paused)
            events.stage(Stage.REVIEW, f"Chờ review {len(review_paused)} video")
            return 3

        if failed:
            update_job_state(jid, status="failed", failed=failed)
            q = queue.load_queue(jid) or {}
            details: list[str] = []
            for name in failed:
                stem = Path(name).stem
                item = next(
                    (it for it in (q.get("items") or []) if it.get("stem") == stem),
                    None,
                )
                err = (item or {}).get("error") if item else None
                details.append(f"{name}: {err}" if err else name)
            events.error(
                ErrorCode.INTERNAL,
                f"Hoàn tất với {len(failed)} lỗi: {'; '.join(details)}",
                fatal=True,
            )
            return 1

        update_job_state(jid, status="completed", output=last_output)
        events.stage(Stage.DONE, "Hoàn tất tất cả video")
        events.completed(last_output, job_id=jid, count=len(videos))
        return 0

    except EngineError as e:
        if e.code == ErrorCode.CANCELLED:
            events.cancelled(e.message)
            update_job_state(jid, status="cancelled")
            return 2
        events.error(e.code, e.message, fatal=True)
        update_job_state(jid, status="failed", error=e.message, code=e.code.value)
        return 1
    except Exception as e:
        log.exception("job failed")
        events.error(ErrorCode.INTERNAL, str(e), fatal=True)
        update_job_state(jid, status="failed", error=str(e))
        return 1
