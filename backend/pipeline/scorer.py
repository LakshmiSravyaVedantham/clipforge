# backend/pipeline/scorer.py
"""Score scenes by audio excitement (RMS energy peaks)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np

try:
    import librosa
    _LIBROSA_AVAILABLE = True
except ImportError:
    _LIBROSA_AVAILABLE = False

from pipeline.detector import Scene


@dataclass
class ScoredScene:
    scene: Scene
    score: float

    @property
    def start_sec(self) -> float:
        return self.scene.start_sec

    @property
    def end_sec(self) -> float:
        return self.scene.end_sec

    @property
    def duration(self) -> float:
        return self.scene.duration


def _load_audio(path: Path) -> Tuple[np.ndarray, int]:
    """Load audio from video file. Separated for testability."""
    if not _LIBROSA_AVAILABLE:
        raise RuntimeError(
            "librosa not installed. Run: pip install librosa"
        )
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    return y, sr


def _rms_score(y: np.ndarray, sr: int, start: float, end: float) -> float:
    """Mean RMS energy of an audio segment. Higher = more exciting."""
    if not _LIBROSA_AVAILABLE:
        raise RuntimeError(
            "librosa not installed. Run: pip install librosa"
        )
    start_sample = int(start * sr)
    end_sample = int(end * sr)
    segment = y[start_sample:end_sample]
    if len(segment) == 0:
        return 0.0
    rms = librosa.feature.rms(y=segment, frame_length=2048, hop_length=512)
    return float(np.mean(rms))


def score_scenes(
    path: Path, scenes: List[Scene], top_k: int = 10
) -> List[ScoredScene]:
    """Score and rank scenes by audio excitement. Returns top_k sorted descending.

    Audio RMS energy is used as a proxy for excitement — explosions, commentary
    peaks, and action sequences all produce louder audio than quiet moments.
    """
    if not scenes:
        return []
    y, sr = _load_audio(path)
    scored = [
        ScoredScene(scene=s, score=_rms_score(y, sr, s.start_sec, s.end_sec))
        for s in scenes
    ]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_k]
