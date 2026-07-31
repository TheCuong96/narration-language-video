"""yt-dlp adapter: probe / download remote videos into local files for the dubbing pipeline."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import events
from .ffmpeg import ffmpeg_path
from .models import ErrorCode
from .system_info import EngineError, appdata_root, free_disk_bytes, get_logger, new_job_id

log = get_logger("dubvi.ytdlp")

# Prefer progressive/compatible MP4 up to 1080p for Whisper + remux.
_DEFAULT_FORMAT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b[height<=1080]/b"
_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}

# YouTube (2025+) needs EJS challenge scripts + a JS runtime (Deno preferred).
# Pip installs do not bundle EJS; allow fetching from GitHub when needed.
_REMOTE_COMPONENTS = ["ejs:github"]


def downloads_dir() -> Path:
    d = appdata_root() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def normalize_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        raise EngineError(ErrorCode.YTDLP_INVALID_URL, "Chưa dán URL video.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise EngineError(
            ErrorCode.YTDLP_INVALID_URL,
            "URL không hợp lệ. Chỉ chấp nhận liên kết bắt đầu bằng http:// hoặc https://.",
        )
    return url


def _require_yt_dlp():
    try:
        import yt_dlp  # type: ignore
    except ImportError as e:
        raise EngineError(
            ErrorCode.YTDLP_NOT_FOUND,
            "Chưa cài yt-dlp. Chạy: pip install -r engine/requirements-base.txt",
        ) from e
    return yt_dlp


def yt_dlp_version() -> str | None:
    try:
        from yt_dlp.version import __version__

        return str(__version__)
    except Exception:
        return None


def _ffmpeg_location() -> str | None:
    try:
        ff = Path(ffmpeg_path())
        return str(ff.parent)
    except EngineError:
        return None


def _which_runtime(name: str) -> str | None:
    """Find deno/node even when WinGet installs outside the default PATH lookup."""
    exe = f"{name}.exe" if sys.platform == "win32" else name
    found = shutil.which(name) or shutil.which(exe)
    if found:
        return found
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or ""
        candidates = [
            Path(local) / "Microsoft" / "WinGet" / "Packages",
            Path(local) / "deno",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Deno",
        ]
        for root in candidates:
            if not root.is_dir():
                continue
            direct = root / exe
            if direct.is_file():
                return str(direct)
            try:
                for hit in root.rglob(exe):
                    if hit.is_file():
                        return str(hit)
            except OSError:
                continue
    return None


def detect_js_runtime() -> dict[str, dict[str, str]]:
    """
    Return yt-dlp js_runtimes mapping: {name: {path: ...}}.
    Deno is preferred; Node is a fallback. Empty dict if nothing found.
    """
    deno = _which_runtime("deno")
    if deno:
        return {"deno": {"path": deno}}
    node = _which_runtime("node")
    if node:
        return {"node": {"path": node}}
    return {}


def js_runtime_status() -> dict[str, Any]:
    runtimes = detect_js_runtime()
    if "deno" in runtimes:
        return {"ok": True, "runtime": "deno", "path": runtimes["deno"].get("path")}
    if "node" in runtimes:
        return {"ok": True, "runtime": "node", "path": runtimes["node"].get("path")}
    return {
        "ok": False,
        "runtime": None,
        "path": None,
        "error": "Thiếu Deno (khuyên dùng) hoặc Node.js — YouTube cần JS runtime. Cài: winget install DenoLand.Deno",
    }


def map_ytdlp_error(exc: BaseException) -> EngineError:
    msg = str(exc) or exc.__class__.__name__
    low = msg.lower()
    if "unsupported url" in low or "no suitable extractor" in low or "unsupported website" in low:
        return EngineError(
            ErrorCode.YTDLP_UNSUPPORTED_OR_CHANGED_SITE,
            "Website này chưa được hỗ trợ hoặc extractor đã lỗi thời. Thử cập nhật yt-dlp.",
        )
    if (
        "sign in" in low
        or "login required" in low
        or "private video" in low
        or "members-only" in low
        or "confirm your age" in low
        or "http error 401" in low
        or "http error 403" in low
    ):
        return EngineError(
            ErrorCode.YTDLP_AUTH_REQUIRED,
            "Video cần đăng nhập, quyền riêng tư hoặc bị hạn chế tuổi — app chưa hỗ trợ cookie/đăng nhập.",
        )
    if (
        "challenge solving failed" in low
        or "no supported javascript runtime" in low
        or "javascript runtime" in low
        or ("not available" in low and "youtube" in low)
        or low.strip().endswith("this video is not available")
        or "this video is not available" in low
    ):
        js = js_runtime_status()
        if not js.get("ok"):
            return EngineError(
                ErrorCode.YTDLP_DOWNLOAD_FAILED,
                "YouTube cần Deno (JS runtime) để tải video. Cài: winget install DenoLand.Deno rồi thử lại.",
            )
        return EngineError(
            ErrorCode.YTDLP_DOWNLOAD_FAILED,
            "YouTube từ chối tải video này (có thể region/age/challenge). "
            "Thử cập nhật: pip install -U \"yt-dlp[default]\". "
            "Hoặc mở video trong trình duyệt — nếu xem được mà vẫn lỗi, tải file thủ công rồi kéo thả vào app.",
        )
    if "timed out" in low or "timeout" in low or "temporary failure in name resolution" in low:
        return EngineError(ErrorCode.YTDLP_NETWORK, "Kết nối mạng quá chậm hoặc bị gián đoạn khi tải video.")
    if "requested format is not available" in low or "format is not available" in low:
        return EngineError(
            ErrorCode.YTDLP_FORMAT_UNAVAILABLE,
            "Không tìm được định dạng video phù hợp để tải.",
        )
    if "no space" in low or "not enough space" in low or "errno 28" in low:
        return EngineError(ErrorCode.DISK_SPACE_LOW, "Không đủ dung lượng ổ cứng để tải video.")
    return EngineError(ErrorCode.YTDLP_DOWNLOAD_FAILED, msg[:500])


def _base_opts(*, out_dir: Path | None = None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "ignoreconfig": True,
        # Never allow user-controlled dangerous options.
        "compat_opts": set(),
        # Required for pip-installed yt-dlp against modern YouTube challenges.
        "remote_components": list(_REMOTE_COMPONENTS),
    }
    runtimes = detect_js_runtime()
    if runtimes:
        opts["js_runtimes"] = runtimes
    ff_loc = _ffmpeg_location()
    if ff_loc:
        opts["ffmpeg_location"] = ff_loc
    if out_dir is not None:
        opts["paths"] = {"home": str(out_dir), "temp": str(out_dir / "_tmp")}
        opts["outtmpl"] = {"default": "source-%(id)s.%(ext)s"}
        opts["restrictfilenames"] = True
        opts["windowsfilenames"] = True
    return opts


def _format_duration(sec: float | None) -> str:
    if sec is None or sec < 0:
        return "—"
    s = int(round(sec))
    h, rem = divmod(s, 3600)
    m, sec_i = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec_i:02d}"
    return f"{m}:{sec_i:02d}"


def _format_size(n: int | None) -> str:
    if not n or n < 0:
        return "—"
    mb = n / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


def probe_url(url: str) -> dict[str, Any]:
    """Return metadata JSON without downloading."""
    url = normalize_url(url)
    yt_dlp = _require_yt_dlp()
    opts = _base_opts()
    opts["skip_download"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except EngineError:
        raise
    except Exception as e:
        raise map_ytdlp_error(e) from e

    if not info:
        raise EngineError(ErrorCode.YTDLP_DOWNLOAD_FAILED, "Không lấy được thông tin video.")

    # Playlist entries: take first when --no-playlist still returns playlist wrapper
    if info.get("_type") == "playlist" and info.get("entries"):
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise EngineError(ErrorCode.YTDLP_DOWNLOAD_FAILED, "Playlist trống hoặc không truy cập được.")
        info = entries[0]

    duration = info.get("duration")
    try:
        duration_sec = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_sec = None
    filesize = info.get("filesize") or info.get("filesize_approx")
    try:
        size_bytes = int(filesize) if filesize else None
    except (TypeError, ValueError):
        size_bytes = None

    return {
        "ok": True,
        "url": url,
        "id": info.get("id") or "",
        "title": info.get("title") or info.get("id") or "video",
        "extractor": info.get("extractor") or info.get("ie_key") or "",
        "webpage_url": info.get("webpage_url") or url,
        "duration_sec": duration_sec,
        "duration_label": _format_duration(duration_sec),
        "size_bytes": size_bytes,
        "size_label": _format_size(size_bytes),
        "ext": info.get("ext") or "mp4",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "is_live": bool(info.get("is_live")),
        "was_live": bool(info.get("was_live")),
    }


def _pick_downloaded_path(info: dict[str, Any], out_dir: Path) -> Path:
    requested = info.get("requested_downloads") or []
    for item in requested:
        fp = item.get("filepath") or item.get("filename")
        if fp:
            p = Path(fp)
            if p.is_file():
                return p
    for key in ("filepath", "_filename", "filename"):
        fp = info.get(key)
        if fp:
            p = Path(fp)
            if p.is_file():
                return p
    vid = str(info.get("id") or "")
    if vid:
        matches = sorted(out_dir.glob(f"source-{vid}.*"))
        for m in matches:
            if m.is_file() and m.suffix.lower() in _VIDEO_EXTS and "_tmp" not in m.parts:
                return m
    # Last resort: newest video file in out_dir
    candidates = [
        p
        for p in out_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _VIDEO_EXTS
    ]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    raise EngineError(ErrorCode.YTDLP_DOWNLOAD_FAILED, "Tải xong nhưng không tìm thấy file video.")


def download_url(url: str, *, out_dir: Path | None = None) -> Path:
    """Download a single video; stream JSONL progress; return local path."""
    url = normalize_url(url)
    yt_dlp = _require_yt_dlp()

    root = out_dir.expanduser().resolve() if out_dir else downloads_dir() / new_job_id()
    root.mkdir(parents=True, exist_ok=True)
    (root / "_tmp").mkdir(parents=True, exist_ok=True)

    free = free_disk_bytes(root)
    if free < 500 * 1024 * 1024:
        raise EngineError(
            ErrorCode.DISK_SPACE_LOW,
            f"Cần ít nhất ~500 MB trống nhưng ổ đĩa chỉ còn {free // (1024**2)} MB.",
        )

    events.stage("downloading_video", "Đang tải video từ URL…", stage_label="Tải video")
    events.progress("downloading_video", 0, 100, "Bắt đầu tải…", stage_label="Tải video")

    last_pct = [-1]

    def hook(d: dict[str, Any]) -> None:
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                pct = int(min(99, max(0, round(100 * done / total))))
            else:
                pct = 0
            if pct != last_pct[0]:
                last_pct[0] = pct
                speed = d.get("_speed_str") or ""
                eta = d.get("_eta_str") or ""
                detail = "Đang tải"
                if speed:
                    detail += f" · {speed}"
                if eta:
                    detail += f" · còn {eta}"
                events.progress(
                    "downloading_video",
                    pct,
                    100,
                    detail,
                    stage_label="Tải video",
                    percent=float(pct),
                )
        elif status == "finished":
            events.progress(
                "downloading_video",
                95,
                100,
                "Đang ghép/chuyển định dạng (FFmpeg)…",
                stage_label="Tải video",
            )

    opts = _base_opts(out_dir=root)
    opts.update(
        {
            "format": _DEFAULT_FORMAT,
            "merge_output_format": "mp4",
            "progress_hooks": [hook],
        }
    )

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except EngineError:
        raise
    except Exception as e:
        raise map_ytdlp_error(e) from e

    if not info:
        raise EngineError(ErrorCode.YTDLP_DOWNLOAD_FAILED, "Không tải được video.")

    if info.get("_type") == "playlist" and info.get("entries"):
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise EngineError(ErrorCode.YTDLP_DOWNLOAD_FAILED, "Playlist trống.")
        info = entries[0]

    path = _pick_downloaded_path(info, root)
    # Prefer remuxed mp4 sibling if present
    mp4 = path.with_suffix(".mp4")
    if path.suffix.lower() != ".mp4" and mp4.is_file():
        path = mp4

    events.progress(
        "downloading_video",
        100,
        100,
        f"Đã tải: {path.name}",
        stage_label="Tải video",
    )
    log.info("Downloaded %s -> %s", url, path)
    return path.resolve()


def supported_sites_help() -> dict[str, Any]:
    """Static guidance for the UI about which URLs can be downloaded."""
    js = js_runtime_status()
    tips = [
        "Dán URL trang xem video (không phải trang tìm kiếm).",
        "YouTube cần Deno (hoặc Node 22+) trên máy — cài: winget install DenoLand.Deno",
        "Video dài và 4K sẽ nặng — app ưu tiên tối đa ~1080p MP4.",
        "Chọn «Lưu vào» để tải về thư mục bạn muốn; để trống thì dùng %LOCALAPPDATA%\\DubVI\\downloads.",
        "Chỉ tải nội dung bạn có quyền sử dụng / chỉnh sửa.",
    ]
    if js.get("ok"):
        tips.insert(1, f"JS runtime đã sẵn sàng: {js.get('runtime')} ({js.get('path')})")
    return {
        "summary": (
            "Dub VI dùng yt-dlp để tải một video công khai từ liên kết http(s). "
            "Sau khi tải xong, video được đưa vào hàng đợi thuyết minh tiếng Việt như file local."
        ),
        "typically_works": [
            "YouTube — video công khai (cần Deno/Node để vượt challenge)",
            "Vimeo, Dailymotion và nhiều trang có extractor trong yt-dlp",
            "Một số trang tin / giáo dục công khai (tùy site còn hỗ trợ)",
            "Link trực tiếp tới file media (mp4/webm) nếu máy chủ cho phép",
        ],
        "often_fails_or_unsupported": [
            "Video riêng tư, chưa công bố, hoặc chỉ dành cho thành viên trả phí",
            "Nội dung cần đăng nhập / cookie / xác minh tuổi (app chưa gắn cookie trình duyệt)",
            "Livestream đang phát (nên đợi hết hoặc dùng bản đã ghi)",
            "Playlist / cả kênh — app chỉ tải 1 video (bỏ playlist)",
            "Nền tảng có DRM hoặc chặn tải (Netflix, Disney+, Spotify…)",
            "Site vừa đổi giao diện khiến extractor yt-dlp lỗi thời (cần cập nhật yt-dlp)",
            "Máy chưa có Deno/Node → YouTube hay báo «This video is not available»",
        ],
        "tips": tips,
        "supported_sites_url": "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md",
        "yt_dlp_version": yt_dlp_version(),
        "js_runtime": js,
    }
