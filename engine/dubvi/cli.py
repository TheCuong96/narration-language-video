"""CLI entry for Dub VI engine (JSONL events for Tauri sidecar)."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from . import __version__, events, queue, review
from .jobs import load_job_state, request_cancel
from .models import (
    DEFAULT_MIX_ORIGINAL_DB,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    AudioMode,
    ErrorCode,
    JobConfig,
    StartFrom,
)
from .pipeline import continue_stem, run_job
from .settings_store import load_settings, save_settings, AppSettings
from .system_info import collect_system_info, new_job_id, setup_logging


def _add_run_shared(p: argparse.ArgumentParser) -> None:
    p.add_argument("--output", "-o", type=Path, required=True, help="Output folder")
    p.add_argument("--job-id", default=None, help="Resume / identify job id")
    p.add_argument("--voice", default=DEFAULT_VOICE)
    p.add_argument("--model", default=DEFAULT_MODEL, help="Whisper model size")
    p.add_argument("--source-lang", default="en")
    p.add_argument("--target-lang", default="vi")
    p.add_argument("--only", nargs="*", default=[])
    p.add_argument("--terms", nargs="*", default=[])
    p.add_argument("--gpu", action="store_true", help="Prefer NVIDIA CUDA if available")
    p.add_argument("--cpu", action="store_true", help="Force CPU (default)")
    p.add_argument("--force", action="store_true")
    p.add_argument(
        "--audio-mode",
        choices=[m.value for m in AudioMode],
        default=AudioMode.VI_ONLY.value,
    )
    p.add_argument("--mix-db", type=float, default=DEFAULT_MIX_ORIGINAL_DB)
    p.add_argument("--review", action="store_true")
    p.add_argument("--translate-only", action="store_true")
    p.add_argument(
        "--from-stage",
        choices=[s.value for s in StartFrom],
        default=StartFrom.AUTO.value,
    )
    p.add_argument("--no-reencode", action="store_true")
    p.add_argument("--no-cleanup", action="store_true")
    p.add_argument("--human", action="store_true")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dubvi-engine",
        description="Dub VI engine - Vietnamese narration pipeline (JSONL events)",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Dub videos (folder and/or file list)")
    run_p.add_argument("--input", "-i", type=Path, default=None)
    run_p.add_argument("--files", "-f", nargs="+", type=Path, default=[])
    _add_run_shared(run_p)

    retry_p = sub.add_parser("retry", help="Retry failed items")
    retry_p.add_argument("--job-id", required=True)
    retry_p.add_argument("--output", "-o", type=Path, default=None)
    retry_p.add_argument("--stem", nargs="*", default=[])
    retry_p.add_argument("--gpu", action="store_true")
    retry_p.add_argument("--cpu", action="store_true")
    retry_p.add_argument("--human", action="store_true")
    retry_p.add_argument("--audio-mode", choices=[m.value for m in AudioMode], default=None)

    cont = sub.add_parser("continue", help="Continue after translation review")
    cont.add_argument("--job-id", required=True)
    cont.add_argument("--stem", required=True)
    cont.add_argument("--voice", default=None)
    cont.add_argument("--audio-mode", choices=[m.value for m in AudioMode], default=None)
    cont.add_argument("--mix-db", type=float, default=None)
    cont.add_argument("--human", action="store_true")

    rev_get = sub.add_parser("review-get", help="Get EN/VI transcript")
    rev_get.add_argument("--job-id", required=True)
    rev_get.add_argument("--stem", required=True)

    rev_set = sub.add_parser("review-set", help="Save edited VI translation")
    rev_set.add_argument("--job-id", required=True)
    rev_set.add_argument("--stem", required=True)
    rev_set.add_argument("--file", type=Path, required=True)

    q_p = sub.add_parser("queue", help="Show job queue JSON")
    q_p.add_argument("--job-id", required=True)

    probe_p = sub.add_parser("probe", help="Probe video duration/size for UI")
    probe_p.add_argument("paths", nargs="+", type=Path)

    models_p = sub.add_parser("models", help="List Whisper models")
    models_dl = sub.add_parser("models-download", help="Download a Whisper model")
    models_dl.add_argument("model_id")
    models_rm = sub.add_parser("models-delete", help="Delete a Whisper model cache")
    models_rm.add_argument("model_id")
    models_rm.add_argument("--yes", action="store_true")

    sub.add_parser("settings-get", help="Print settings JSON")
    set_p = sub.add_parser("settings-set", help="Merge settings from JSON file")
    set_p.add_argument("--file", type=Path, required=True)

    doctor = sub.add_parser("doctor", help="Check FFmpeg, engine, disk, models")

    sub.add_parser("system-info", help="Print system JSON")
    cancel_p = sub.add_parser("cancel", help="Request cancel")
    cancel_p.add_argument("job_id")
    voices_p = sub.add_parser("list-voices", help="List Vietnamese edge-tts voices")
    voices_p.add_argument("--json", action="store_true", dest="as_json")

    privacy = sub.add_parser("privacy-notice", help="Print privacy notice JSON")
    _ = (models_p, privacy, doctor)

    return p


def _cfg_from_run(args: argparse.Namespace) -> JobConfig:
    prefer_gpu = bool(args.gpu) and not args.cpu
    files = [Path(f) for f in (args.files or [])]
    input_dir = args.input.expanduser().resolve() if args.input else None
    if input_dir is None and not files:
        raise SystemExit("Cần --input thư mục hoặc --files danh sách video")
    return JobConfig(
        input_dir=input_dir,
        input_files=files,
        output_dir=args.output.expanduser().resolve(),
        job_id=args.job_id or new_job_id(),
        voice=args.voice,
        whisper_model=args.model,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        prefer_gpu=prefer_gpu,
        force=args.force,
        translate_only=args.translate_only,
        review_translation=args.review,
        only=list(args.only or []),
        extra_terms=list(args.terms or []),
        cleanup_on_success=not args.no_cleanup,
        audio_mode=AudioMode(args.audio_mode),
        mix_original_db=args.mix_db,
        start_from=StartFrom(args.from_stage),
        allow_reencode=not args.no_reencode,
    )


def _privacy_notice() -> dict:
    return {
        "whisper_local": True,
        "ffmpeg_local": True,
        "translate_needs_internet": True,
        "tts_needs_internet": True,
        "video_uploaded_to_dubvi": False,
        "what_leaves_device": [
            "Đoạn transcript gửi tới dịch vụ dịch (deep-translator / Google Translate web).",
            "Đoạn text đã dịch gửi tới edge-tts để tạo giọng.",
        ],
        "what_stays_local": [
            "File video gốc và kết quả.",
            "Whisper model và nhận dạng lời nói.",
            "FFmpeg tách/ghép media.",
            "Cache job trong %LOCALAPPDATA%/DubVI.",
        ],
        "providers_community": {
            "translate": "deep-translator",
            "tts": "edge-tts",
        },
        "future_providers": [
            "google-cloud-translate",
            "google-cloud-tts",
            "azure-speech",
        ],
        "note": "Không log API key, transcript riêng tư hoặc thông tin nhạy cảm vào log công khai.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "system-info":
        setup_logging()
        print(json.dumps(collect_system_info(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "privacy-notice":
        print(json.dumps(_privacy_notice(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "doctor":
        from . import models_manager
        from .ffmpeg import ffmpeg_path, ffprobe_path
        from .system_info import EngineError, free_disk_bytes, appdata_root

        report: dict = {"ok": True, "checks": []}
        for name, fn in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)):
            try:
                p = fn()
                report["checks"].append({"name": name, "ok": True, "path": p})
            except EngineError as e:
                report["ok"] = False
                report["checks"].append({"name": name, "ok": False, "error": e.message})
        report["checks"].append(
            {
                "name": "appdata",
                "ok": True,
                "path": str(appdata_root()),
                "free_mb": free_disk_bytes(appdata_root()) // (1024**2),
            }
        )
        report["models"] = models_manager.list_models()
        report["privacy"] = _privacy_notice()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    if args.command == "probe":
        from .media import probe_many

        print(json.dumps(probe_many(list(args.paths)), ensure_ascii=False, indent=2))
        return 0

    if args.command == "models":
        from . import models_manager

        print(json.dumps(models_manager.list_models(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "models-download":
        from . import models_manager

        events.set_json_mode(True)
        try:
            path = models_manager.download_model(args.model_id)
            events.completed(str(path), model=args.model_id)
            return 0
        except Exception as e:
            from .system_info import EngineError

            if isinstance(e, EngineError):
                events.error(e.code, e.message, fatal=True)
            else:
                events.error(ErrorCode.WHISPER_LOAD_FAILED, str(e), fatal=True)
            return 1

    if args.command == "models-delete":
        from . import models_manager

        try:
            models_manager.delete_model(args.model_id, confirm=bool(args.yes))
            print(json.dumps({"ok": True, "model": args.model_id}))
            return 0
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            return 1

    if args.command == "settings-get":
        print(json.dumps(load_settings().to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "settings-set":
        data = json.loads(args.file.read_text(encoding="utf-8"))
        cur = load_settings().to_dict()
        cur.update(data)
        path = save_settings(AppSettings.from_dict(cur))
        print(json.dumps({"ok": True, "path": str(path), "settings": cur}, ensure_ascii=False))
        return 0

    if args.command == "cancel":
        path = request_cancel(args.job_id)
        print(json.dumps({"ok": True, "flag": str(path)}, ensure_ascii=False))
        return 0

    if args.command == "list-voices":
        from .tts import list_vi_voices

        voices = asyncio.run(list_vi_voices())
        if getattr(args, "as_json", False):
            print(json.dumps(voices, ensure_ascii=False, indent=2))
        else:
            for v in voices:
                print(
                    f"{v.get('ShortName', ''):28} {v.get('Gender', ''):8} "
                    f"{v.get('FriendlyName', '')}"
                )
        return 0

    if args.command == "queue":
        data = queue.load_queue(args.job_id)
        if not data:
            print(json.dumps({"error": "QUEUE_NOT_FOUND", "job_id": args.job_id}))
            return 1
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.command == "review-get":
        print(json.dumps(review.get_review_payload(args.job_id, args.stem), ensure_ascii=False, indent=2))
        return 0

    if args.command == "review-set":
        segs = review.load_translation_file(args.file.expanduser().resolve())
        out = review.save_translation(args.job_id, args.stem, segs)
        print(json.dumps({"ok": True, "path": str(out)}, ensure_ascii=False))
        return 0

    if args.command == "continue":
        events.set_json_mode(not args.human)
        state = load_job_state(args.job_id)
        if not state:
            events.error(ErrorCode.INPUT_NOT_FOUND, f"Không thấy job {args.job_id}", fatal=True)
            return 1
        opts = state.get("options") or {}
        mode = AudioMode(args.audio_mode or opts.get("audio_mode") or AudioMode.VI_ONLY.value)
        cfg = JobConfig(
            output_dir=Path(state["output_dir"]),
            job_id=args.job_id,
            input_dir=Path(state["input_dir"]) if state.get("input_dir") else None,
            input_files=[Path(p) for p in state.get("input_files") or []],
            voice=args.voice or opts.get("voice") or DEFAULT_VOICE,
            audio_mode=mode,
            mix_original_db=args.mix_db if args.mix_db is not None else DEFAULT_MIX_ORIGINAL_DB,
            start_from=StartFrom.TTS,
            review_translation=False,
        )
        return continue_stem(cfg, args.stem)

    if args.command == "retry":
        events.set_json_mode(not args.human)
        state = load_job_state(args.job_id)
        if not state:
            events.error(ErrorCode.INPUT_NOT_FOUND, f"Không thấy job {args.job_id}", fatal=True)
            return 1
        stems = list(args.stem) if args.stem else queue.failed_stems(args.job_id)
        if not stems:
            events.error(ErrorCode.NO_VIDEOS, "Không có mục lỗi để thử lại", fatal=True)
            return 1
        opts = state.get("options") or {}
        out_dir = Path(args.output) if args.output else Path(state["output_dir"])
        q = queue.load_queue(args.job_id) or {"items": []}
        files = [Path(i["input"]) for i in q["items"] if i["stem"] in stems]
        mode = AudioMode(args.audio_mode or opts.get("audio_mode") or AudioMode.VI_ONLY.value)
        cfg = JobConfig(
            output_dir=out_dir.resolve(),
            job_id=args.job_id,
            input_files=files,
            voice=opts.get("voice") or DEFAULT_VOICE,
            whisper_model=opts.get("model") or DEFAULT_MODEL,
            prefer_gpu=bool(args.gpu) and not args.cpu,
            audio_mode=mode,
            retry_stems=stems,
            start_from=StartFrom.AUTO,
            review_translation=bool(opts.get("review_translation")),
        )
        return run_job(cfg)

    if args.command == "run":
        events.set_json_mode(not args.human)
        try:
            cfg = _cfg_from_run(args)
        except SystemExit as e:
            events.error(ErrorCode.INVALID_ARGS, str(e) or "Thiếu input", fatal=True)
            return 1
        return run_job(cfg)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
