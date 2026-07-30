#!/usr/bin/env python3
"""
dub-vi — Dub English (or other) videos into Vietnamese narration.

Pipeline:
  1. Extract audio (FFmpeg)
  2. Transcribe with faster-whisper (GPU/CPU)
  3. Translate segments -> Vietnamese (Google via deep-translator)
  4. edge-tts Vietnamese voice per segment (tempo-matched to original timing)
  5. Mux narration back onto original video (video stream copied)

Examples:
  python tools/dub_vi.py --setup
  python tools/dub_vi.py -i D:\\videos\\en -o D:\\videos\\vi
  dub-vi.cmd -i .\\in -o .\\out --only lesson1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Ensure tools/ is importable when run as script
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from dub_deps import add_nvidia_dll_dirs, ensure_deps  # noqa: E402

# Lazy-loaded after dependency check
edge_tts = None
GoogleTranslator = None
WhisperModel = None

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"
DEFAULT_MODEL = "medium"


def _load_libs() -> None:
    """Import heavy libs only after deps are ready."""
    global edge_tts, GoogleTranslator, WhisperModel
    if WhisperModel is not None:
        return
    add_nvidia_dll_dirs()
    import edge_tts as _edge_tts
    from deep_translator import GoogleTranslator as _GoogleTranslator
    from faster_whisper import WhisperModel as _WhisperModel

    edge_tts = _edge_tts
    GoogleTranslator = _GoogleTranslator
    WhisperModel = _WhisperModel

# Protect / restore terms that machine translation often mangles
TECH_TERMS = [
    "Next.js",
    "TypeScript",
    "JavaScript",
    "React Hook Form",
    "Appwrite",
    "Plaid",
    "Dwolla",
    "Sentry",
    "shadcn/ui",
    "shadcn",
    "Tailwind CSS",
    "Tailwind",
    "Zod",
    "SSR",
    "Horizon",
    "Robinhood",
    "Stripe",
    "MongoDB",
    "Node.js",
    "GitHub",
    "Vercel",
    "FFmpeg",
]


@dataclass
class Config:
    input_dir: Path
    output_dir: Path
    work_dir: Path
    voice: str = DEFAULT_VOICE
    whisper_model: str = DEFAULT_MODEL
    source_lang: str = "en"
    target_lang: str = "vi"
    device: str = "cuda"
    compute_type: str = "float16"
    translate_only: bool = False
    force: bool = False
    only: list[str] = field(default_factory=list)
    extra_terms: list[str] = field(default_factory=list)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(">", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True, **kwargs)


def ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def extract_audio(video: Path, wav: Path) -> None:
    wav.parent.mkdir(parents=True, exist_ok=True)
    if wav.exists():
        return
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def transcribe(
    wav: Path, transcript_path: Path, model: WhisperModel, source_lang: str
) -> list[dict]:
    if transcript_path.exists():
        return json.loads(transcript_path.read_text(encoding="utf-8"))

    print(f"  Transcribing {wav.name} ...", flush=True)
    kwargs: dict = {
        "vad_filter": True,
        "vad_parameters": dict(min_silence_duration_ms=400),
        "word_timestamps": False,
    }
    if source_lang and source_lang != "auto":
        kwargs["language"] = source_lang

    segments_iter, info = model.transcribe(str(wav), **kwargs)
    print(
        f"  Detected language={info.language} prob={info.language_probability:.2f}",
        flush=True,
    )

    segments: list[dict] = []
    for seg in segments_iter:
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append(
            {
                "id": len(segments),
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text_en": text,
            }
        )
        if len(segments) % 20 == 0:
            print(f"    ... {len(segments)} segments", flush=True)

    transcript_path.write_text(
        json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return segments


def protect_terms(text: str, terms: list[str]) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    out = text
    for i, term in enumerate(terms):
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        if pattern.search(out):
            token = f"XTERM{i}X"
            mapping[token] = term
            out = pattern.sub(token, out)
    return out, mapping


def restore_terms(text: str, mapping: dict[str, str]) -> str:
    out = text
    for token, term in mapping.items():
        out = re.sub(re.escape(token), term, out, flags=re.IGNORECASE)
    replacements = {
        r"\bPlayed\b": "Plaid",
        r"\bAppRide\b": "Appwrite",
        r"\bApp Ride\b": "Appwrite",
        r"\bZot\b": "Zod",
        r"\bShadZien\b": "shadcn",
    }
    for pat, rep in replacements.items():
        out = re.sub(pat, rep, out)
    return out


def clean_vi(text: str) -> str:
    text = text.strip().replace("&", " và ")
    return re.sub(r"\s+", " ", text)


def translate_segments(
    segments: list[dict],
    out_path: Path,
    source_lang: str,
    target_lang: str,
    terms: list[str],
) -> list[dict]:
    if out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))

    src = "auto" if source_lang in ("", "auto") else source_lang
    translator = GoogleTranslator(source=src, target=target_lang)
    print(f"  Translating {len(segments)} segments ({src} -> {target_lang}) ...", flush=True)
    result: list[dict] = []
    batch_size = 30
    for i in range(0, len(segments), batch_size):
        batch = segments[i : i + batch_size]
        for s in batch:
            protected, mapping = protect_terms(s["text_en"], terms)
            try:
                vi = translator.translate(protected)
            except Exception as e:
                print(f"    translate retry: {e}", flush=True)
                time.sleep(2)
                vi = translator.translate(protected)
            vi = restore_terms(vi or s["text_en"], mapping)
            result.append({**s, "text_vi": clean_vi(vi)})
        print(f"    ... {min(i + batch_size, len(segments))}/{len(segments)}", flush=True)
        time.sleep(0.3)

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


async def tts_segment(text: str, out_mp3: Path, voice: str, rate: str = "+0%") -> None:
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(out_mp3))


def stretch_to_duration(src: Path, dst: Path, target_sec: float) -> None:
    """Fit audio into target_sec using atempo + pad/trim."""
    dur = ffprobe_duration(src)
    if dur <= 0:
        run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=24000:cl=mono",
                "-t",
                f"{max(target_sec, 0.05):.3f}",
                "-c:a",
                "pcm_s16le",
                str(dst),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    usable = max(target_sec * 0.95, 0.05)
    # atempo: output_dur = input_dur / atempo
    filters: list[str] = []
    tempo = dur / usable if usable > 0 else 1.0
    tempo = max(0.85, min(tempo, 1.55))
    t = tempo
    while t < 0.5:
        filters.append("atempo=0.5")
        t /= 0.5
    while t > 2.0:
        filters.append("atempo=2.0")
        t /= 2.0
    filters.append(f"atempo={t:.4f}")
    af = ",".join(filters) + f",apad=whole_dur={target_sec:.3f},atrim=0:{target_sec:.3f}"
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-af",
            af,
            "-ar",
            "24000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def build_narration(
    segments: list[dict], work: Path, video_duration: float, voice: str
) -> Path:
    seg_dir = work / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    fitted_dir = work / "fitted"
    fitted_dir.mkdir(parents=True, exist_ok=True)

    narration = work / "narration.wav"
    if narration.exists():
        return narration

    for s in segments:
        mp3 = seg_dir / f"{s['id']:04d}.mp3"
        text = s.get("text_vi") or s.get("text_en") or ""
        if not text.strip():
            continue
        if mp3.exists() and mp3.stat().st_size < 500:
            mp3.unlink()
        if not mp3.exists():
            ok = False
            for attempt in range(4):
                try:
                    rate = "+0%" if attempt == 0 else ("-5%" if attempt == 1 else "+5%")
                    await tts_segment(text, mp3, voice=voice, rate=rate)
                    if mp3.exists() and mp3.stat().st_size >= 500:
                        ok = True
                        break
                    if mp3.exists():
                        mp3.unlink()
                except Exception as e:
                    print(f"    TTS fail seg {s['id']} try{attempt + 1}: {e}", flush=True)
                    if mp3.exists():
                        mp3.unlink()
                await asyncio.sleep(1.5 * (attempt + 1))
            if not ok:
                print(f"    TTS GIVE UP seg {s['id']}", flush=True)
        if (s["id"] + 1) % 25 == 0:
            print(f"    TTS {s['id'] + 1}/{len(segments)}", flush=True)

    pieces: list[Path] = []
    cursor = 0.0
    for idx, s in enumerate(segments):
        start = float(s["start"])
        end = float(s["end"])
        if end <= start:
            end = start + 0.3
        gap = start - cursor
        if gap > 0.02:
            sil = fitted_dir / f"sil_{idx:04d}.wav"
            if not sil.exists():
                run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=24000:cl=mono",
                        "-t",
                        f"{gap:.3f}",
                        "-c:a",
                        "pcm_s16le",
                        str(sil),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            pieces.append(sil)

        mp3 = seg_dir / f"{s['id']:04d}.mp3"
        fitted = fitted_dir / f"{s['id']:04d}.wav"
        target = max(end - start, 0.2)
        if mp3.exists():
            if not fitted.exists():
                stretch_to_duration(mp3, fitted, target)
            pieces.append(fitted)
        else:
            if not fitted.exists():
                run(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=24000:cl=mono",
                        "-t",
                        f"{target:.3f}",
                        "-c:a",
                        "pcm_s16le",
                        str(fitted),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            pieces.append(fitted)
        cursor = end

    if cursor < video_duration - 0.05:
        sil = fitted_dir / "sil_end.wav"
        if not sil.exists():
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=24000:cl=mono",
                    "-t",
                    f"{video_duration - cursor:.3f}",
                    "-c:a",
                    "pcm_s16le",
                    str(sil),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        pieces.append(sil)

    list_file = work / "concat.txt"
    with list_file.open("w", encoding="utf-8") as f:
        for p in pieces:
            escaped = str(p.resolve()).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:a",
            "pcm_s16le",
            str(narration),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return narration


def mux(video: Path, narration: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(narration),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def process_one(video: Path, model, cfg: Config) -> Path:
    name = video.stem
    work = cfg.work_dir / name
    work.mkdir(parents=True, exist_ok=True)
    output = cfg.output_dir / f"{name}.mp4"

    if output.exists() and not cfg.force:
        print(f"[SKIP] already done: {output.name}", flush=True)
        return output

    if cfg.force:
        for p in [
            work / "transcript_vi.json",
            work / "script_vi.txt",
            work / "narration.wav",
            work / "concat.txt",
            output,
        ]:
            if p.exists():
                p.unlink()
        for dname in ("fitted", "segments"):
            d = work / dname
            if d.exists():
                for f in d.glob("*"):
                    f.unlink()

    print(f"\n=== {video.name} ===", flush=True)
    t0 = time.time()
    duration = ffprobe_duration(video)
    print(f"  duration={duration / 60:.1f} min", flush=True)

    wav = work / "audio.wav"
    extract_audio(video, wav)

    segments = transcribe(
        wav, work / "transcript_en.json", model, source_lang=cfg.source_lang
    )
    print(f"  segments={len(segments)}", flush=True)

    terms = TECH_TERMS + cfg.extra_terms
    segments_vi = translate_segments(
        segments,
        work / "transcript_vi.json",
        source_lang=cfg.source_lang,
        target_lang=cfg.target_lang,
        terms=terms,
    )

    script_path = work / "script_vi.txt"
    if not script_path.exists():
        lines = [f"[{s['start']:.1f}-{s['end']:.1f}] {s['text_vi']}" for s in segments_vi]
        script_path.write_text("\n".join(lines), encoding="utf-8")

    if cfg.translate_only:
        print("  skip TTS/mux (--translate-only)", flush=True)
        return output

    narration = asyncio.run(build_narration(segments_vi, work, duration, cfg.voice))
    mux(video, narration, output)
    print(f"  DONE -> {output} ({(time.time() - t0) / 60:.1f} min)", flush=True)
    return output


def collect_videos(input_dir: Path, only: list[str]) -> list[Path]:
    videos = sorted(input_dir.glob("*.mp4"))
    if only:
        keys = {k.lower() for k in only}
        videos = [
            v
            for v in videos
            if v.stem.lower() in keys or any(k in v.stem.lower() for k in keys)
        ]
    return videos


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="dub-vi",
        description="Dub MP4 videos into Vietnamese narration (Whisper + translate + edge-tts + FFmpeg)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/dub_vi.py --setup
  python tools/dub_vi.py -i D:\\videos\\en -o D:\\videos\\vi
  python tools/dub_vi.py -i .\\in -o .\\out --only lesson1 lesson2
  python tools/dub_vi.py -i .\\in -o .\\out --voice vi-VN-NamMinhNeural
        """,
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("video-parts"),
        help="Folder of source MP4 files (default: video-parts)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("video-parts-vi"),
        help="Folder for dubbed MP4 output (default: video-parts-vi)",
    )
    parser.add_argument(
        "--work",
        type=Path,
        default=None,
        help="Cache/work folder (default: <output>-work next to output)",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        help="Process only matching stems, e.g. 01-Intro 02-Setup",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help=f"edge-tts voice (default: {DEFAULT_VOICE}). Also: vi-VN-NamMinhNeural",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Whisper model: tiny/base/small/medium/large-v3 (default: medium)",
    )
    parser.add_argument(
        "--source-lang",
        default="en",
        help="Source language code for Whisper/translate, or 'auto' (default: en)",
    )
    parser.add_argument(
        "--target-lang",
        default="vi",
        help="Target language for translation (default: vi)",
    )
    parser.add_argument(
        "--terms",
        nargs="*",
        default=[],
        help="Extra tech terms to keep untranslated",
    )
    parser.add_argument(
        "--translate-only",
        action="store_true",
        help="Stop after transcript + translation (no TTS/mux)",
    )
    parser.add_argument("--cpu", action="store_true", help="Force CPU for Whisper")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if output exists (keeps EN transcript cache)",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List Vietnamese edge-tts voices and exit",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Only check/install dependencies, then exit",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip dependency check (faster restart if you know deps are OK)",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Check only — do not auto-install missing packages/FFmpeg",
    )
    args = parser.parse_args()

    prefer_gpu = not args.cpu
    if args.setup or not args.skip_check:
        ready = ensure_deps(
            auto_install=not args.no_install,
            install_ffmpeg=not args.no_install,
            prefer_gpu=prefer_gpu,
        )
        if not ready:
            return 1
        if args.setup:
            print("Setup complete. Example:")
            print('  python tools/dub_vi.py -i "D:\\videos\\en" -o "D:\\videos\\vi"')
            return 0

    try:
        _load_libs()
    except Exception as e:
        print(f"[!!] Failed to load libraries: {e}", file=sys.stderr)
        print("Try: python tools/dub_vi.py --setup", file=sys.stderr)
        return 1

    if args.list_voices:
        async def _list() -> None:
            voices = await edge_tts.list_voices()
            for v in voices:
                if v.get("Locale", "").startswith("vi-"):
                    print(
                        f"{v['ShortName']:28} {v.get('Gender', ''):8} "
                        f"{v.get('FriendlyName', '')}"
                    )

        asyncio.run(_list())
        return 0

    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    if args.work:
        work_dir = args.work.resolve()
    else:
        work_dir = output_dir.parent / (output_dir.name + "-work")

    if not input_dir.is_dir():
        print(f"Input folder not found: {input_dir}", file=sys.stderr)
        return 1

    videos = collect_videos(input_dir, args.only or [])
    if not videos:
        print(f"No matching MP4 files in {input_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    device = "cpu" if args.cpu else "cuda"
    compute = "int8" if device == "cpu" else "float16"
    cfg = Config(
        input_dir=input_dir,
        output_dir=output_dir,
        work_dir=work_dir,
        voice=args.voice,
        whisper_model=args.model,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        device=device,
        compute_type=compute,
        translate_only=args.translate_only,
        force=args.force,
        only=args.only or [],
        extra_terms=args.terms or [],
    )

    print(
        f"dub-vi | in={input_dir} out={output_dir} work={work_dir}",
        flush=True,
    )
    print(
        f"Loading Whisper model={cfg.whisper_model} device={cfg.device} "
        f"compute={cfg.compute_type}",
        flush=True,
    )
    try:
        model = WhisperModel(
            cfg.whisper_model, device=cfg.device, compute_type=cfg.compute_type
        )
    except Exception as e:
        if cfg.device != "cpu":
            print(f"[..] GPU load failed ({e}); falling back to CPU", flush=True)
            cfg.device = "cpu"
            cfg.compute_type = "int8"
            model = WhisperModel(
                cfg.whisper_model, device="cpu", compute_type="int8"
            )
        else:
            raise

    failed: list[str] = []
    for video in videos:
        try:
            process_one(video, model, cfg)
        except Exception as e:
            print(f"[ERROR] {video.name}: {e}", file=sys.stderr)
            failed.append(video.name)
            continue

    if failed:
        print(
            f"\nFinished with {len(failed)} error(s): {', '.join(failed)}",
            flush=True,
        )
        return 1

    print(f"\nAll {len(videos)} video(s) processed -> {output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
