from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

# Disable HuggingFace xet (Xet storage) protocol — falls back to standard HTTPS.
# Required: xet binary bundled with huggingface_hub 0.36+ fails with "Permission denied"
# when the container's temp filesystem blocks executable mappings.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

logger = logging.getLogger(__name__)

_model_instance = None


def _get_model():
    """Lazy singleton — loads Faster-Whisper model once per process."""
    global _model_instance
    if _model_instance is None:
        from faster_whisper import WhisperModel
        from app.core.config import settings

        logger.info(
            "Loading Faster-Whisper model '%s' (device=%s, compute_type=%s)",
            settings.WHISPER_MODEL,
            settings.WHISPER_DEVICE,
            settings.WHISPER_COMPUTE_TYPE,
        )
        _model_instance = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
            download_root=settings.WHISPER_CACHE_DIR,
        )
        logger.info("Faster-Whisper model loaded.")
    return _model_instance


@dataclass
class TranscriptionResult:
    text: str
    language: str
    duration_seconds: float


def transcribe_audio(file_path: Path) -> TranscriptionResult:
    """
    Transcribe an audio/video file using Faster-Whisper.
    Runs synchronously — call via asyncio.to_thread in async context.
    """
    model = _get_model()
    logger.info("Starting transcription: %s", file_path.name)

    try:
        segments_gen, info = model.transcribe(
            str(file_path),
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        # Materialise the lazy generator
        text_parts: list[str] = []
        duration = 0.0
        for seg in segments_gen:
            text_parts.append(seg.text.strip())
            duration = max(duration, seg.end)
        detected_language = getattr(info, "language", "unknown") or "unknown"
        detected_duration = (getattr(info, "duration", None) or duration) or 0.0
    except ValueError:
        # All audio removed by VAD (silent file) — return empty transcript
        logger.warning("Transcription produced no segments (silent or empty audio): %s", file_path.name)
        text_parts = []
        detected_language = "unknown"
        detected_duration = 0.0

    full_text = " ".join(text_parts).strip()

    logger.info(
        "Transcription complete: %.1f s, language=%s, words=%d",
        detected_duration,
        detected_language,
        len(full_text.split()),
    )

    return TranscriptionResult(
        text=full_text,
        language=detected_language,
        duration_seconds=detected_duration,
    )
