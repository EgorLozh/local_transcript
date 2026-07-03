import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

_DEBUG_LOG = Path(__file__).resolve().parent.parent / "debug-ede45e.log"


def _dbg(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    entry = {
        "sessionId": "ede45e",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with _DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass
    print(f"DEBUG[{hypothesis_id}] {message} {data}", flush=True)
    # #endregion


def _patch_torch_load() -> None:
    """PyTorch 2.6+ defaults weights_only=True; pyannote/speechbrain checkpoints need False."""
    import torch

    _original_load = torch.load
    _dbg(
        "B",
        "engine.py:_patch_torch_load",
        "patch applied",
        {"torch_version": torch.__version__, "torch_load_id": id(torch.load)},
    )

    def _load(*args, **kwargs):
        before = kwargs.get("weights_only", "<missing>")
        if kwargs.get("weights_only") is not False:
            kwargs["weights_only"] = False
        after = kwargs.get("weights_only")
        _dbg(
            "A",
            "engine.py:_load",
            "torch.load intercepted",
            {
                "weights_only_before": str(before),
                "weights_only_after_force": str(after),
                "kwargs_keys": sorted(kwargs.keys()),
                "arg0": str(args[0])[:120] if args else None,
            },
        )
        return _original_load(*args, **kwargs)

    torch.load = _load  # type: ignore[method-assign]
    _dbg(
        "D",
        "engine.py:_patch_torch_load",
        "torch.load replaced",
        {"new_torch_load_id": id(torch.load)},
    )


_patch_torch_load()

import whisperx

from app.config import resolve_diarization_model_path, settings

logger = logging.getLogger(__name__)


class TranscriptionEngine:
    def __init__(self) -> None:
        self._model = None
        self._diarize_model = None
        self._align_model = None
        self._align_metadata = None
        self._language: str | None = None

    @property
    def device(self) -> str:
        if settings.device == "cuda":
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        return settings.device

    @property
    def diarization_enabled(self) -> bool:
        return settings.diarization_available

    def load(self) -> None:
        if self._model is not None:
            return

        import torch

        _dbg(
            "C",
            "engine.py:load",
            "engine.load start",
            {
                "whisper_model": settings.whisper_model,
                "device": self.device,
                "torch_load_id_at_load": id(torch.load),
            },
        )
        logger.info(
            "Loading Whisper model %s on %s (%s)",
            settings.whisper_model,
            self.device,
            settings.compute_type,
        )
        self._model = whisperx.load_model(
            settings.whisper_model,
            self.device,
            compute_type=settings.compute_type,
        )

        if settings.diarization_available:
            diar_path = resolve_diarization_model_path(settings.diarization_model_path)
            try:
                import pyannote.audio

                pyannote_ver = getattr(pyannote.audio, "__version__", "unknown")
            except Exception:
                pyannote_ver = "unknown"
            _dbg(
                "F",
                "engine.py:load",
                "loading diarization",
                {
                    "diar_path": diar_path,
                    "exists": Path(diar_path).is_file(),
                    "pyannote_version": pyannote_ver,
                },
            )
            logger.info("Loading diarization model from %s", diar_path)
            try:
                self._diarize_model = whisperx.DiarizationPipeline(
                    model_name=diar_path,
                    use_auth_token=None,
                    device=self.device,
                )
                _dbg("F", "engine.py:load", "diarization loaded", {"ok": True})
            except Exception as exc:
                _dbg(
                    "H",
                    "engine.py:load",
                    "diarization failed",
                    {"error": str(exc), "error_type": type(exc).__name__},
                )
                logger.error(
                    "Failed to load diarization model (%s). "
                    "Use pyannote/speaker-diarization-3.1 with whisperx 3.3. "
                    "community-1 requires whisperx 3.8+ / pyannote 4.x.",
                    exc,
                )
                self._diarize_model = None
        else:
            logger.warning(
                "Diarization model not found at %s — speaker detection disabled",
                settings.diarization_model_path,
            )
        _dbg("G", "engine.py:load", "engine.load complete", {"diarization": self._diarize_model is not None})

    def _ensure_align_model(self, language: str) -> None:
        if self._align_model is not None and self._language == language:
            return
        self._align_model, self._align_metadata = whisperx.load_align_model(
            language_code=language,
            device=self.device,
        )
        self._language = language

    def _normalize_segments(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []
        for seg in result.get("segments", []):
            speaker = seg.get("speaker")
            segments.append(
                {
                    "start": float(seg["start"]),
                    "end": float(seg["end"]),
                    "text": str(seg["text"]).strip(),
                    "speaker": speaker,
                }
            )
        return segments

    def _run_diarization(
        self,
        audio,
        result: dict[str, Any],
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> dict[str, Any]:
        if self._diarize_model is None:
            return result

        diarize_segments = self._diarize_model(
            audio,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        return whisperx.assign_word_speakers(diarize_segments, result)

    def transcribe_file(
        self,
        audio_path: str | Path,
        *,
        diarize: bool = True,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[dict[str, Any]]:
        self.load()
        audio = whisperx.load_audio(str(audio_path))
        return self.transcribe_audio(
            audio,
            diarize=diarize and self.diarization_enabled,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

    def transcribe_audio(
        self,
        audio,
        *,
        diarize: bool = True,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[dict[str, Any]]:
        self.load()
        result = self._model.transcribe(audio, batch_size=settings.batch_size)
        language = result.get("language") or "en"
        self._ensure_align_model(language)
        result = whisperx.align(
            result["segments"],
            self._align_model,
            self._align_metadata,
            audio,
            self.device,
        )
        if diarize:
            result = self._run_diarization(
                audio,
                result,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
            )
        return self._normalize_segments(result)

    def transcribe_accumulated(
        self,
        audio_bytes: bytes,
        *,
        suffix: str = ".webm",
        after: float = 0.0,
    ) -> list[dict[str, Any]]:
        if not audio_bytes:
            return []

        self.load()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            audio = whisperx.load_audio(tmp_path)
            result = self._model.transcribe(audio, batch_size=settings.batch_size)
            segments: list[dict[str, Any]] = []
            for seg in result.get("segments", []):
                text = str(seg.get("text", "")).strip()
                if not text:
                    continue
                end = float(seg["end"])
                if end <= after:
                    continue
                segments.append(
                    {
                        "start": float(seg["start"]),
                        "end": end,
                        "text": text,
                        "speaker": None,
                    }
                )
            return segments
        except Exception:
            logger.exception("Failed to transcribe accumulated audio")
            return []
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        suffix: str = ".webm",
        diarize: bool = True,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> list[dict[str, Any]]:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return self.transcribe_file(
                tmp_path,
                diarize=diarize,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def status(self) -> dict[str, Any]:
        cuda_available = False
        gpu_name: str | None = None
        try:
            import torch

            cuda_available = torch.cuda.is_available()
            if cuda_available:
                gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            pass

        return {
            "model": settings.whisper_model,
            "device": self.device,
            "cuda_available": cuda_available,
            "gpu_name": gpu_name,
            "diarization_enabled": self.diarization_enabled,
            "chunk_sec": settings.chunk_sec,
        }


engine = TranscriptionEngine()
