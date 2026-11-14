from unittest.mock import Mock

from dubvi.providers import community


def test_limiter_rate():
    now = [0.0]
    def sleep(delay):
        now[0] += delay
    limiter = community.GoogleRateLimiter(clock=lambda: now[0], sleep=sleep)
    timestamps = []
    for _ in range(12):
        limiter.acquire()
        timestamps.append(now[0])
    assert all(b - a >= .25 for a, b in zip(timestamps, timestamps[1:]))


def test_429_backoff(monkeypatch):
    import deep_translator
    translate = Mock(side_effect=[Exception("429 rate limit")] * 4 + ["Xin chào"])
    monkeypatch.setattr(deep_translator, "GoogleTranslator", Mock(return_value=Mock(translate=translate)))
    limiter = Mock()
    monkeypatch.setattr(community, "GOOGLE_LIMITER", limiter)
    assert community.GoogleDeepTranslator().translate("Hello", source="en", target="vi") == "Xin chào"
    assert [c.args[0] for c in limiter.cooldown.call_args_list] == [2, 4, 8, 16]
    assert limiter.acquire.call_count == 5


def test_batch_does_not_replay_success(monkeypatch):
    provider = community.GoogleDeepTranslator()
    from dubvi.system_info import EngineError
    from dubvi.models import ErrorCode
    call = Mock(side_effect=["Một", EngineError(ErrorCode.TRANSLATE_FAILED, "Google lỗi"), "Ba"])
    monkeypatch.setattr(provider, "translate", call)
    assert provider.translate_batch(["One", "Two", "Three"], source="en", target="vi") == ["Một", "Two", "Ba"]
    assert call.call_count == 3
