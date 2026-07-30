from __future__ import annotations

import pytest

from dubvi.jobs import CancellationToken
from dubvi.models import ErrorCode
from dubvi.system_info import EngineError


def test_cancel_flag(tmp_path):
    token = CancellationToken(tmp_path)
    assert not token.is_cancelled()
    token.request_cancel()
    assert token.is_cancelled()
    with pytest.raises(EngineError) as ei:
        token.check()
    assert ei.value.code == ErrorCode.CANCELLED
    token.clear()
    assert not token.is_cancelled()
