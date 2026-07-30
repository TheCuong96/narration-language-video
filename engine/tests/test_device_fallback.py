from dubvi.system_info import resolve_device


def test_default_cpu():
    info = resolve_device(prefer_gpu=False)
    assert info.device == "cpu"
    assert info.compute_type == "int8"


def test_prefer_gpu_without_nvidia_falls_back(monkeypatch):
    monkeypatch.setattr("dubvi.system_info.detect_nvidia_gpu", lambda: None)
    info = resolve_device(prefer_gpu=True)
    assert info.device == "cpu"
    assert info.fallback_reason
