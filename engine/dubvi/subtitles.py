"""Load existing Vietnamese subtitles (SRT / VTT) and skip ASR + translation."""

from __future__ import annotations

import re
from pathlib import Path

from .models import ErrorCode, Segment
from .system_info import EngineError, get_logger

log = get_logger("dubvi.subtitles")

SUBTITLE_EXTENSIONS = (".srt", ".vtt")
# Udemy / yt-dlp language tags commonly used for Vietnamese subs.
_VI_TAGS = ("vi", "vie", "vn", "vi-vn", "vi-VN", "vietnamese")
_HTML_TAG = re.compile(r"</?[^>]+>")
_SSA_TAG = re.compile(r"\{[^}]+\}")
_CUE_ARROW = re.compile(
    r"^(.+?)\s+-->\s+(.+?)(?:\s+.*)?$",
)


def is_subtitle_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUBTITLE_EXTENSIONS


def parse_timestamp(raw: str) -> float:
    """Parse SRT/VTT timestamps: ``HH:MM:SS,mmm``, ``MM:SS.mmm``, or seconds."""
    text = (raw or "").strip().replace(",", ".")
    if not text:
        raise ValueError("empty timestamp")
    # Drop VTT cue settings accidentally glued to the end time.
    text = text.split()[0]
    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        return float(text)
    except ValueError as e:
        raise ValueError(f"Không đọc được mốc thời gian: {raw}") from e


def clean_cue_text(text: str) -> str:
    out = (text or "").replace("\u00a0", " ")
    out = out.replace("\\N", " ").replace("\\n", " ")
    out = _SSA_TAG.sub(" ", out)
    out = _HTML_TAG.sub(" ", out)
    out = out.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", out).strip()


def _read_subtitle_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1258", errors="replace")


def _iter_blocks(text: str) -> list[list[str]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def parse_subtitle_file(path: Path) -> list[Segment]:
    """Parse SRT or VTT into timed Vietnamese segments (text_vi filled)."""
    if not path.is_file():
        raise EngineError(ErrorCode.SUBTITLE_NOT_FOUND, f"Không tìm thấy phụ đề: {path}")
    text = _read_subtitle_text(path)
    suffix = path.suffix.lower()
    if suffix == ".vtt" or text.lstrip().upper().startswith("WEBVTT"):
        cues = _parse_vtt_blocks(_iter_blocks(text))
    else:
        cues = _parse_srt_blocks(_iter_blocks(text))
    segments: list[Segment] = []
    next_id = 0
    for start, end, body in cues:
        vi = clean_cue_text(body)
        if not vi:
            continue
        if end <= start:
            end = start + 0.3
        segments.append(
            Segment(id=next_id, start=start, end=end, text_en="", text_vi=vi)
        )
        next_id += 1
    if not segments:
        raise EngineError(
            ErrorCode.SUBTITLE_INVALID,
            f"File phụ đề không có câu nào dùng được: {path.name}",
        )
    return segments


def _parse_srt_blocks(blocks: list[list[str]]) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    for block in blocks:
        lines = list(block)
        if lines and re.fullmatch(r"\d+", lines[0].strip()):
            lines = lines[1:]
        if not lines:
            continue
        parsed = _split_timing_line(lines[0])
        if not parsed:
            continue
        start, end = parsed
        body = "\n".join(lines[1:])
        cues.append((start, end, body))
    return cues


def _parse_vtt_blocks(blocks: list[list[str]]) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    for block in blocks:
        first = block[0].strip()
        upper = first.upper()
        if upper.startswith("WEBVTT") or upper.startswith("NOTE") or upper.startswith("STYLE") or upper.startswith("REGION"):
            continue
        lines = list(block)
        timing_idx = 0
        parsed = _split_timing_line(lines[0])
        if not parsed and len(lines) > 1:
            timing_idx = 1
            parsed = _split_timing_line(lines[1])
        if not parsed:
            continue
        start, end = parsed
        body = "\n".join(lines[timing_idx + 1 :])
        cues.append((start, end, body))
    return cues


def _split_timing_line(line: str) -> tuple[float, float] | None:
    match = _CUE_ARROW.match(line.strip())
    if not match:
        return None
    try:
        return parse_timestamp(match.group(1)), parse_timestamp(match.group(2))
    except ValueError:
        return None


def _language_tagged_stems(video_stem: str) -> list[str]:
    stems = []
    seen: set[str] = set()
    for tag in _VI_TAGS:
        for candidate in (f"{video_stem}_{tag}", f"{video_stem}.{tag}"):
            key = candidate.casefold()
            if key in seen:
                continue
            seen.add(key)
            stems.append(candidate)
    return stems


def _candidate_names(video_stem: str) -> list[str]:
    names: list[str] = []
    for stem in _language_tagged_stems(video_stem):
        for ext in SUBTITLE_EXTENSIONS:
            names.append(stem + ext)
    for ext in SUBTITLE_EXTENSIONS:
        names.append(video_stem + ext)
    return names


# `Lesson 01_vi.srt` → stem `Lesson 01`. `_vi` is the Udemy / user-facing tag.
_VI_FILENAME = re.compile(
    r"^(?P<stem>.+?)(?P<tag>_vi|_vie|_vn|\.vi-vn|\.vietnamese|\.vi|\.vie)"
    r"(?P<ext>\.srt|\.vtt)$",
    re.IGNORECASE,
)
_TAG_RANK = {
    "_vi": 0,
    "_vie": 1,
    "_vn": 2,
    ".vi": 3,
    ".vie": 4,
    ".vi-vn": 5,
    ".vietnamese": 6,
}


def vi_subtitle_video_stem(path: Path) -> tuple[str, int] | None:
    """If this is a Vietnamese subtitle, return (matching video stem, rank)."""
    match = _VI_FILENAME.fullmatch(path.name)
    if not match:
        return None
    tag = match.group("tag").lower()
    return match.group("stem"), _TAG_RANK.get(tag, 20)


def subtitle_matches_video(subtitle: Path, video: Path) -> int:
    """Return match rank (lower is better) or -1 if this subtitle is not for video."""
    parsed = vi_subtitle_video_stem(subtitle)
    if parsed:
        stem, rank = parsed
        if stem.casefold() == video.stem.casefold():
            return rank
        return -1
    vkey = video.stem.casefold()
    skey = subtitle.stem.casefold()
    ranked = [s.casefold() for s in _language_tagged_stems(video.stem)]
    if skey in ranked:
        return ranked.index(skey)
    if skey == vkey:
        return 100
    return -1


def _walk_files(root: Path, max_depth: int) -> list[Path]:
    found: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for item in entries:
            try:
                if item.is_file():
                    found.append(item)
                elif (
                    item.is_dir()
                    and depth < max_depth
                    and not item.name.startswith(".")
                ):
                    stack.append((item, depth + 1))
            except OSError:
                continue
    return found


def _search_roots(video: Path, extra_files: list[Path]) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None, *, as_dir: bool) -> None:
        if path is None:
            return
        target = path if (as_dir or path.is_dir()) else path.parent
        if not target.is_dir():
            return
        try:
            key = str(target.resolve()).casefold()
        except OSError:
            key = str(target).casefold()
        if key in seen:
            return
        seen.add(key)
        roots.append(target)

    add(video.parent, as_dir=True)
    add(video.parent.parent if video.parent else None, as_dir=True)
    for extra in extra_files:
        add(extra, as_dir=extra.is_dir())
    return roots


def find_subtitle_for_video(
    video: Path,
    extra_files: list[Path] | None = None,
) -> Path | None:
    """Find `{video_stem}_vi.srt` in the video folder (or nearby), even if files are not adjacent."""
    extras = [Path(p) for p in (extra_files or []) if p]
    ranked: list[tuple[int, int, Path]] = []
    # same_dir_penalty, tag_rank, path — lower is better
    video_parent: Path | None
    try:
        video_parent = video.parent.resolve() if video.parent else None
    except OSError:
        video_parent = video.parent

    def consider(path: Path, *, explicit: bool = False) -> None:
        try:
            rp = path.expanduser().resolve()
        except OSError:
            return
        if not is_subtitle_file(rp):
            return
        rank = subtitle_matches_video(rp, video)
        if rank < 0:
            return
        try:
            parent = rp.parent.resolve()
        except OSError:
            parent = rp.parent
        if explicit:
            same = -1
        elif video_parent is not None and parent == video_parent:
            same = 0
        else:
            same = 1
        ranked.append((same, rank, rp))

    for extra in extras:
        if extra.is_dir():
            continue
        consider(extra, explicit=True)

    for root in _search_roots(video, extras):
        # Same folder + one level of subfolders (Subs/, vi/, …).
        depth = 1 if root == video.parent else 0
        for file in _walk_files(root, max_depth=depth):
            consider(file)

    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1], str(item[2]).casefold()))
    return ranked[0][2]


def expected_subtitle_names(video: Path) -> list[str]:
    return _candidate_names(video.stem)[:6] + [video.stem + ".srt"]


def resolve_subtitle_path(
    video: Path,
    extra_files: list[Path] | None = None,
) -> Path:
    found = find_subtitle_for_video(video, extra_files)
    if found is None:
        raise EngineError(
            ErrorCode.SUBTITLE_NOT_FOUND,
            f"Không thấy phụ đề tiếng Việt cho «{video.name}». "
            f"Cần file «{video.stem}_vi.srt» trong cùng thư mục (hoặc thư mục con).",
        )
    return found
