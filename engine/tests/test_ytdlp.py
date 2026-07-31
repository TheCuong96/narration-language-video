from dubvi.models import ErrorCode
from dubvi.system_info import EngineError
from dubvi.ytdlp import map_ytdlp_error, normalize_url, supported_sites_help, _base_opts


def test_normalize_url_accepts_https():
    assert normalize_url("  https://www.youtube.com/watch?v=dQw4w9WgXcQ  ").startswith(
        "https://"
    )


def test_normalize_url_rejects_empty():
    try:
        normalize_url("")
        assert False, "expected error"
    except EngineError as e:
        assert e.code == ErrorCode.YTDLP_INVALID_URL


def test_normalize_url_rejects_non_http():
    try:
        normalize_url("ftp://example.com/a.mp4")
        assert False, "expected error"
    except EngineError as e:
        assert e.code == ErrorCode.YTDLP_INVALID_URL


def test_map_private_video():
    err = map_ytdlp_error(Exception("Private video. Sign in if you've been granted access"))
    assert err.code == ErrorCode.YTDLP_AUTH_REQUIRED


def test_map_unsupported():
    err = map_ytdlp_error(Exception("Unsupported URL: https://example.invalid/x"))
    assert err.code == ErrorCode.YTDLP_UNSUPPORTED_OR_CHANGED_SITE


def test_supported_sites_help_shape():
    help_data = supported_sites_help()
    assert "typically_works" in help_data
    assert "often_fails_or_unsupported" in help_data
    assert help_data["supported_sites_url"].endswith("supportedsites.md")
    assert len(help_data["typically_works"]) >= 2


def test_base_opts_enable_ejs_remote_components():
    opts = _base_opts()
    assert "ejs:github" in opts.get("remote_components", [])


def test_map_youtube_not_available():
    err = map_ytdlp_error(Exception("ERROR: [youtube] aDJi1C5EJQo: This video is not available"))
    assert err.code == ErrorCode.YTDLP_DOWNLOAD_FAILED
    assert "YouTube" in err.message or "youtube" in err.message.lower()
