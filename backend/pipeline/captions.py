# backend/pipeline/captions.py
"""Generate subtitles via OpenAI Whisper. Model is loaded lazily and cached."""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

try:
    import whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False

# Lazy singleton — loaded on first transcription call
_model = None


def _get_model():
    """Load and cache the Whisper base model."""
    global _model
    if not _WHISPER_AVAILABLE:
        raise RuntimeError("openai-whisper not installed. Run: pip install openai-whisper")
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def transcribe_segment(
    video_path: Path,
    start: float,
    end: float,
) -> List[Tuple[float, float, str]]:
    """Transcribe audio from start to end seconds.

    Returns list of (start_sec, end_sec, text) tuples for subtitle rendering.
    Returns empty list if no speech detected or whisper is unavailable.
    """
    model = _get_model()
    try:
        result = model.transcribe(
            str(video_path),
            language="en",
            clip_timestamps=[start, end],
            verbose=False,
        )
    except Exception:
        return []

    segments = []
    for seg in result.get("segments", []):
        text = seg.get("text", "").strip()
        if text:
            segments.append((float(seg["start"]), float(seg["end"]), text))
    return segments
