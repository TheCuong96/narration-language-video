"""Loopback-only Ollama HTTP transport; never installs a runtime or loads weights."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

import requests

from . import events
from .models import ErrorCode
from .system_info import EngineError

BASE_URL = "http://127.0.0.1:11434"
ALLOWED_MODELS = ("translategemma:4b", "translategemma:12b", "translategemma:27b")


def normalize_model(model: str) -> str:
    model = model.strip().lower()
    if model == "translategemma":
        model = ALLOWED_MODELS[0]
    if model not in ALLOWED_MODELS:
        raise EngineError(ErrorCode.INVALID_ARGS, "Model TranslateGemma không nằm trong danh sách cho phép.")
    return model


def normalize_base_url(base_url: str = BASE_URL) -> str:
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except (ValueError, TypeError) as exc:
        raise EngineError(ErrorCode.INVALID_ARGS, "Địa chỉ Ollama không hợp lệ.") from exc
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or port != 11434):
        raise EngineError(ErrorCode.INVALID_ARGS, "Ollama chỉ được kết nối localhost:11434.")
    return BASE_URL


def format_ollama_error(error: Exception) -> str:
    if isinstance(error, requests.Timeout):
        return "Ollama quá thời gian chờ. Kiểm tra RAM/VRAM hoặc chọn model nhỏ hơn."
    if isinstance(error, requests.ConnectionError):
        return "Ollama chưa chạy hoặc không kết nối được port 11434. Cài/mở Ollama: https://ollama.com/download. NLLB và Google vẫn có thể dùng."
    if isinstance(error, requests.HTTPError):
        status = error.response.status_code if error.response is not None else "?"
        return f"Ollama trả lỗi HTTP {status}. Kiểm tra runtime và RAM/VRAM."
    return "Ollama trả dữ liệu JSON không hợp lệ hoặc phản hồi không đúng định dạng."


def request(method: str, endpoint: str, *, base_url: str = BASE_URL,
            timeout=(4, 300), **kwargs):
    # Ignore proxy environment variables and reject redirects to remote hosts.
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.request(method, normalize_base_url(base_url) + endpoint,
                                       timeout=timeout, allow_redirects=False, **kwargs)
        response.raise_for_status()
        if 300 <= response.status_code < 400:
            response.close()
            raise EngineError(ErrorCode.TRANSLATE_FAILED, "Ollama chuyển hướng HTTP bị từ chối.")
        return response
    except requests.RequestException as exc:
        raise EngineError(ErrorCode.TRANSLATE_FAILED, format_ollama_error(exc)) from exc


def json_response(response) -> dict:
    try:
        data = response.json()
        if not isinstance(data, dict) or data.get("error"):
            raise ValueError("invalid object")
        return data
    except (ValueError, TypeError) as exc:
        raise EngineError(ErrorCode.TRANSLATE_FAILED, format_ollama_error(exc)) from exc
    finally:
        response.close()


def list_installed_models(base_url: str = BASE_URL) -> list[dict]:
    data = json_response(request("GET", "/api/tags", base_url=base_url, timeout=(4, 5)))
    models = data.get("models")
    if not isinstance(models, list) or any(not isinstance(m, dict) for m in models):
        raise EngineError(ErrorCode.TRANSLATE_FAILED, "Danh sách model Ollama không hợp lệ.")
    return models


def check_health(base_url: str = BASE_URL) -> dict:
    try:
        models = list_installed_models(base_url)
        version = None
        try:
            version = json_response(request("GET", "/api/version", base_url=base_url,
                                            timeout=(4, 5))).get("version")
        except EngineError:
            pass
        return {"available": True, "base_url": normalize_base_url(base_url),
                "version": version, "models": models}
    except EngineError as exc:
        return {"available": False, "base_url": BASE_URL, "error": exc.message, "models": []}


def is_model_installed(model: str, base_url: str = BASE_URL) -> bool:
    model = normalize_model(model)
    return any(m.get("name", m.get("model")) == model for m in list_installed_models(base_url))


def pull_model(model: str, progress_callback=None, *, base_url: str = BASE_URL) -> None:
    model = normalize_model(model)
    events.stage("downloading_model", f"Ollama quản lý tải {model}")
    events.warning("MODEL_LICENSE", "Gemma Terms of Use; lần tải model cần Internet.", model=model)
    success = False
    warned = False
    try:
        with request("POST", "/api/pull", base_url=base_url,
                     json={"model": model, "stream": True}, stream=True) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if not isinstance(data, dict) or data.get("error"):
                    raise EngineError(ErrorCode.TRANSLATE_FAILED, "Ollama tải model thất bại. Kiểm tra Internet và dung lượng ổ đĩa.")
                status = str(data.get("status", "Đang tải"))
                total = max(0, int(data.get("total", 0)))
                current = max(0, int(data.get("completed", 0)))
                if total:
                    events.progress("downloading_model", current, total, status, model=model)
                elif not warned:
                    events.warning("MODEL_SIZE_UNKNOWN", "Ollama chưa cung cấp tổng dung lượng.", model=model)
                    warned = True
                if progress_callback:
                    progress_callback(current, total, status)
                success = status == "success"
        if not success:
            raise EngineError(ErrorCode.TRANSLATE_FAILED, "Luồng tải Ollama kết thúc trước khi hoàn tất; hãy thử lại.")
        events.progress("downloading_model", 1, 1, f"Đã tải {model}", model=model)
    except (requests.RequestException, ValueError, TypeError) as exc:
        raise EngineError(ErrorCode.TRANSLATE_FAILED, format_ollama_error(exc)) from exc


def delete_model(model: str, *, base_url: str = BASE_URL) -> None:
    response = request("DELETE", "/api/delete", base_url=base_url,
                       json={"model": normalize_model(model)})
    response.close()
