# backend/tests/test_scorer.py
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from pipeline.detector import Scene
from pipeline.scorer import ScoredScene, score_scenes

FAKE_SCENES = [Scene(0.0, 5.0), Scene(5.0, 10.0), Scene(10.0, 15.0)]


def test_score_scenes_returns_sorted_list():
    """Scored scenes should be sorted descending by score."""
    fake_audio = np.zeros(22050 * 15)
    with patch("pipeline.scorer._load_audio", return_value=(fake_audio, 22050)):
        result = score_scenes(Path("fake.mp4"), FAKE_SCENES)
    assert isinstance(result, list)
    assert len(result) == len(FAKE_SCENES)
    assert all(isinstance(s.score, float) for s in result)
    scores = [s.score for s in result]
    assert scores == sorted(scores, reverse=True)


def test_score_scenes_empty_input():
    """Empty scene list should return empty list without loading audio."""
    with patch("pipeline.scorer._load_audio") as mock_load:
        result = score_scenes(Path("fake.mp4"), [])
    mock_load.assert_not_called()
    assert result == []


def test_score_scenes_respects_top_k():
    """top_k parameter should limit the number of returned scenes."""
    scenes = [Scene(float(i), float(i + 5)) for i in range(0, 50, 5)]  # 10 scenes
    fake_audio = np.zeros(22050 * 55)
    with patch("pipeline.scorer._load_audio", return_value=(fake_audio, 22050)):
        result = score_scenes(Path("fake.mp4"), scenes, top_k=3)
    assert len(result) == 3


def test_score_scenes_sorts_by_energy():
    """Higher-energy audio segments should rank above silent segments."""
    sr = 22050
    # First 5s: loud sine wave (high energy)
    # Last 5s: silence (zero energy)
    loud = np.sin(2 * np.pi * 440 * np.linspace(0, 5, 5 * sr)) * 0.9
    silent = np.zeros(5 * sr)
    audio = np.concatenate([loud, silent])

    scenes = [Scene(0.0, 5.0), Scene(5.0, 10.0)]  # loud first, silent second

    with patch("pipeline.scorer._load_audio", return_value=(audio, sr)):
        result = score_scenes(Path("fake.mp4"), scenes)

    # Loud scene should rank #1 (higher RMS = higher score)
    assert result[0].start_sec == 0.0
    assert result[1].start_sec == 5.0
    assert result[0].score > result[1].score


def test_scored_scene_properties():
    """ScoredScene properties should delegate to wrapped Scene."""
    scene = Scene(start_sec=2.0, end_sec=7.0)
    ss = ScoredScene(scene=scene, score=0.5)
    assert ss.start_sec == 2.0
    assert ss.end_sec == 7.0
    assert ss.duration == pytest.approx(5.0)
