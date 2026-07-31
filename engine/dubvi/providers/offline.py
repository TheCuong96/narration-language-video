"""Local offline providers: NLLB translation + XTTS-v2 TTS (optional heavy deps)."""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

from ..lang_codes import to_nllb_lang, to_xtts_lang
from ..models import ErrorCode
from ..system_info import EngineError, get_logger, resolve_device
from .base import TtsProvider, TranslateProvider

log = get_logger("dubvi.providers.offline")

_nllb_lock = threading.Lock()
_nllb_cache: dict[str, object] = {}
_xtts_lock = threading.Lock()
_xtts_cache: dict[str, object] = {}


def _offline_deps_hint(pkg: str) -> str:
    return (
        f"Thiếu gói offline '{pkg}'. Cài: "
        f"pip install -r engine/requirements-offline.txt"
    )


def _ensure_nllb_deps() -> None:
    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError as e:
        raise EngineError(
            ErrorCode.TRANSLATE_FAILED,
            _offline_deps_hint("transformers/torch"),
        ) from e


def _patch_xtts_vietnamese_tokenizer() -> None:
    """viXTTS vocab supports Vietnamese, but coqui-tts tokenizer rejects lang='vi'."""
    from TTS.tts.layers.xtts import tokenizer as tok_mod
    from TTS.tts.utils.text.cleaners import collapse_whitespace, lowercase

    cls = tok_mod.VoiceBpeTokenizer
    if getattr(cls.preprocess_text, "_dubvi_vi_patched", False):
        return

    original = cls.preprocess_text

    def preprocess_text(self, txt, lang):
        lang = (lang or "").split("-")[0]
        if lang == "vi":
            # Basic Latin-script cleaning; Vietnamese diacritics kept.
            txt = lowercase(txt)
            txt = collapse_whitespace(txt)
            return txt
        return original(self, txt, lang)

    preprocess_text._dubvi_vi_patched = True  # type: ignore[attr-defined]
    cls.preprocess_text = preprocess_text
    # Ensure length warnings work for vi
    _orig_init = cls.__init__

    def __init__(self, vocab_file=None):
        _orig_init(self, vocab_file=vocab_file)
        if "vi" not in self.char_limits:
            self.char_limits["vi"] = 250

    cls.__init__ = __init__


def _patch_xtts_audio_loader() -> None:
    """
    Newer torchaudio routes through torchcodec and needs FFmpeg DLLs on PATH.
    Patch Coqui's load_audio to use soundfile so speaker WAVs load reliably on Windows.
    """
    import numpy as np
    import soundfile as sf
    import torch
    import TTS.tts.models.xtts as xtts_mod

    if getattr(xtts_mod.load_audio, "_dubvi_patched", False):
        return

    def load_audio(audiopath, sampling_rate):
        data, lsr = sf.read(audiopath, always_2d=False)
        audio = np.asarray(data, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        tensor = torch.from_numpy(audio).float().unsqueeze(0)  # [1, T]
        if int(lsr) != int(sampling_rate) and tensor.shape[-1] > 1:
            tensor = torch.nn.functional.interpolate(
                tensor.unsqueeze(0),
                size=max(1, int(round(tensor.shape[-1] * sampling_rate / lsr))),
                mode="linear",
                align_corners=False,
            ).squeeze(0)
        tensor = tensor.clamp_(-1, 1)
        return tensor

    load_audio._dubvi_patched = True  # type: ignore[attr-defined]
    xtts_mod.load_audio = load_audio


def _ensure_ffmpeg_on_path() -> None:
    """Help torchcodec/torchaudio find FFmpeg if still used elsewhere."""
    try:
        from ..ffmpeg import ffmpeg_path

        ff = Path(ffmpeg_path()).resolve().parent
        path = os.environ.get("PATH", "")
        if str(ff) not in path.split(os.pathsep):
            os.environ["PATH"] = str(ff) + os.pathsep + path
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(ff))
            except OSError:
                pass
    except Exception as e:
        log.debug("Could not expose ffmpeg on PATH: %s", e)


def _ensure_xtts_deps() -> None:
    try:
        import torch  # noqa: F401
        import TTS  # noqa: F401
        from TTS.tts.configs.xtts_config import XttsConfig  # noqa: F401
        from TTS.tts.models.xtts import Xtts  # noqa: F401
    except ImportError as e:
        msg = str(e)
        hint = (
            "pip uninstall -y TTS coqpit && "
            "pip install -r engine/requirements-offline.txt && "
            "pip install \"coqui-tts[codec]>=0.27.0\""
        )
        if "BeamSearchScorer" in msg or "coqpit" in msg.lower() or "torchcodec" in msg.lower():
            raise EngineError(
                ErrorCode.TTS_FAILED,
                f"XTTS deps lỗi: {e}. Sửa bằng: {hint}",
            ) from e
        raise EngineError(
            ErrorCode.TTS_FAILED,
            _offline_deps_hint("coqui-tts[codec] / torch") + f" — {hint}",
        ) from e


class NllbTranslateProvider(TranslateProvider):
    """Meta NLLB-200 distilled 600M — chạy local qua Hugging Face Transformers."""

    name = "nllb"
    requires_internet = False
    requires_api_key = False
    model_id = "nllb-200-distilled-600M"

    def __init__(self, *, prefer_gpu: bool = False, model_dir: Path | None = None):
        self.prefer_gpu = prefer_gpu
        self._model_dir = model_dir

    def privacy_note(self) -> str:
        return (
            "Dịch NLLB chạy hoàn toàn trên máy bạn. Transcript không gửi ra Internet "
            "(trừ lần tải model)."
        )

    def _resolve_dir(self) -> Path:
        from .. import models_manager

        if self._model_dir is not None:
            return self._model_dir
        path = models_manager.model_path(self.model_id)
        if not models_manager.is_model_downloaded(self.model_id):
            raise EngineError(
                ErrorCode.TRANSLATE_FAILED,
                f"Model NLLB '{self.model_id}' chưa tải đủ (thiếu pytorch_model.bin / "
                f"model.safetensors). Vào Settings → Xóa rồi Tải lại, hoặc:\n"
                f"  python -m dubvi models-delete {self.model_id} --yes\n"
                f"  python -m dubvi models-download {self.model_id}",
            )
        return path

    def _load(self):
        _ensure_nllb_deps()
        model_dir = self._resolve_dir()
        device_info = resolve_device(prefer_gpu=self.prefer_gpu)
        device = device_info.device  # cpu | cuda
        key = f"{model_dir}|{device}"
        with _nllb_lock:
            cached = _nllb_cache.get(key)
            if cached is not None:
                return cached

            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            log.info("Loading NLLB from %s on %s", model_dir, device)
            tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
            model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir))
            model.eval()
            if device == "cuda":
                try:
                    model = model.to("cuda")
                except Exception as e:
                    log.warning("NLLB CUDA failed, fallback CPU: %s", e)
                    device = "cpu"
                    model = model.to("cpu")
            else:
                model = model.to("cpu")

            bundle = {
                "tokenizer": tokenizer,
                "model": model,
                "device": device,
                "torch": torch,
            }
            _nllb_cache[key] = bundle
            return bundle

    def translate(self, text: str, *, source: str, target: str) -> str:
        text = (text or "").strip()
        if not text:
            return text

        bundle = self._load()
        tokenizer = bundle["tokenizer"]
        model = bundle["model"]
        device = bundle["device"]
        torch = bundle["torch"]

        src = to_nllb_lang(source, default="eng_Latn")
        tgt = to_nllb_lang(target, default="vie_Latn")

        tokenizer.src_lang = src
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        if device == "cuda":
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        forced_bos = tokenizer.convert_tokens_to_ids(tgt)
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos,
                max_new_tokens=512,
                num_beams=4,
            )
        out = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
        return (out or text).strip()


class XttsTtsProvider(TtsProvider):
    """
    Coqui XTTS-v2 (ưu tiên checkpoint viXTTS cho tiếng Việt).
    Cần speaker reference WAV; ghi MP3 qua FFmpeg.
    """

    name = "xtts-v2"
    requires_internet = False
    requires_api_key = False
    model_id = "xtts-v2"

    def __init__(
        self,
        *,
        prefer_gpu: bool = False,
        model_dir: Path | None = None,
        speaker_wav: Path | str | None = None,
        language: str = "vi",
    ):
        self.prefer_gpu = prefer_gpu
        self._model_dir = model_dir
        self._speaker_wav = Path(speaker_wav) if speaker_wav else None
        self.language = language

    def privacy_note(self) -> str:
        return (
            "TTS XTTS-v2 chạy hoàn toàn trên máy bạn. Text không gửi ra Internet "
            "(trừ lần tải model). Model dùng license Coqui CPML (không thương mại)."
        )

    def _resolve_dir(self) -> Path:
        from .. import models_manager

        if self._model_dir is not None:
            return self._model_dir
        path = models_manager.model_path(self.model_id)
        if not models_manager.is_model_downloaded(self.model_id):
            raise EngineError(
                ErrorCode.TTS_FAILED,
                f"Chưa tải model XTTS '{self.model_id}'. "
                f"Vào Settings → tải model, hoặc: python -m dubvi models-download {self.model_id}",
            )
        return path

    def _resolve_speaker(self) -> Path:
        if self._speaker_wav and self._speaker_wav.is_file():
            return self._speaker_wav
        # Edge voice names are ignored for XTTS — use bundled/default speaker.
        default = self._resolve_dir() / "speaker_default.wav"
        if default.is_file():
            return default
        raise EngineError(
            ErrorCode.TTS_FAILED,
            "XTTS cần file speaker WAV tham chiếu. Đặt xtts_speaker_wav trong Settings "
            f"hoặc tải lại model để có {default.name}.",
        )

    def _load(self):
        _ensure_xtts_deps()
        _ensure_ffmpeg_on_path()
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        model_dir = self._resolve_dir()
        device_info = resolve_device(prefer_gpu=self.prefer_gpu)
        device = device_info.device
        key = f"{model_dir}|{device}"
        with _xtts_lock:
            cached = _xtts_cache.get(key)
            if cached is not None:
                return cached

            import torch
            from TTS.tts.configs.xtts_config import XttsConfig
            from TTS.tts.models.xtts import Xtts

            _patch_xtts_audio_loader()
            _patch_xtts_vietnamese_tokenizer()

            config_path = model_dir / "config.json"
            if not config_path.is_file():
                raise EngineError(
                    ErrorCode.TTS_FAILED,
                    f"Thiếu config.json trong model XTTS: {model_dir}",
                )

            log.info("Loading XTTS from %s on %s", model_dir, device)
            config = XttsConfig()
            config.load_json(str(config_path))
            model = Xtts.init_from_config(config)
            model.load_checkpoint(config, checkpoint_dir=str(model_dir), eval=True)
            if device == "cuda":
                try:
                    model.cuda()
                except Exception as e:
                    log.warning("XTTS CUDA failed, fallback CPU: %s", e)
                    device = "cpu"
            bundle = {
                "model": model,
                "config": config,
                "device": device,
                "torch": torch,
            }
            _xtts_cache[key] = bundle
            return bundle

    def _synthesize_sync(
        self,
        text: str,
        out_path: Path,
        *,
        voice: str,
        rate: str = "+0%",
    ) -> None:
        del rate  # XTTS speed not mapped from edge-tts rate strings in v0.1
        text = (text or "").strip()
        if not text:
            raise EngineError(ErrorCode.TTS_FAILED, "Đoạn TTS trống")

        # Allow voice to be a filesystem path to a speaker wav
        speaker: Path | None = None
        if voice and Path(voice).is_file() and voice.lower().endswith((".wav", ".mp3", ".flac")):
            speaker = Path(voice)
        if speaker is None:
            speaker = self._resolve_speaker()

        bundle = self._load()
        model = bundle["model"]
        config = bundle["config"]

        lang = to_xtts_lang(self.language, default="vi")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        wav_tmp = out_path.with_suffix(".xtts.wav")

        try:
            outputs = model.synthesize(
                text,
                config,
                speaker_wav=str(speaker),
                gpt_cond_len=3,
                language=lang,
            )
            import numpy as np
            import soundfile as sf

            wav = outputs["wav"]
            if hasattr(wav, "cpu"):
                wav = wav.cpu().numpy()
            wav = np.asarray(wav, dtype=np.float32).reshape(-1)
            sample_rate = 24000
            audio_cfg = getattr(config, "audio", None)
            if audio_cfg is not None:
                sr = getattr(audio_cfg, "sample_rate", None) or getattr(
                    audio_cfg, "output_sample_rate", None
                )
                if sr:
                    sample_rate = int(sr)
            sf.write(str(wav_tmp), wav, sample_rate)

            from ..ffmpeg import ffmpeg_path, run_ffmpeg

            if out_path.suffix.lower() == ".mp3":
                run_ffmpeg(
                    [
                        ffmpeg_path(),
                        "-y",
                        "-i",
                        str(wav_tmp),
                        "-codec:a",
                        "libmp3lame",
                        "-qscale:a",
                        "2",
                        str(out_path),
                    ]
                )
            else:
                wav_tmp.replace(out_path)
        finally:
            if wav_tmp.exists() and out_path.suffix.lower() == ".mp3":
                try:
                    wav_tmp.unlink()
                except OSError:
                    pass

    async def synthesize(
        self,
        text: str,
        out_path: Path,
        *,
        voice: str,
        rate: str = "+0%",
    ) -> None:
        await asyncio.to_thread(
            self._synthesize_sync,
            text,
            out_path,
            voice=voice,
            rate=rate,
        )
