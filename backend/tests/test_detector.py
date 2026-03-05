import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.detector import Scene, detect_scenes


def test_detect_scenes_returns_list():
    """Mocks the underlying PySceneDetect call and verifies Scene objects."""
    start_mock = MagicMock()
    start_mock.get_seconds.return_value = 0.0
    end_mock = MagicMock()
    end_mock.get_seconds.return_value = 3.0
    mock_scene_list = [(start_mock, end_mock)]

    with patch("pipeline.detector._run_detector", return_value=mock_scene_list):
        result = detect_scenes(Path("fake.mp4"))

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].start_sec == 0.0
    assert result[0].end_sec == 3.0


def test_detect_scenes_filters_short_scenes():
    """Scenes shorter than min_duration should be excluded."""
    start_mock = MagicMock()
    start_mock.get_seconds.return_value = 0.0
    end_mock = MagicMock()
    end_mock.get_seconds.return_value = 1.0  # 1s — shorter than default 1.5s min

    with patch("pipeline.detector._run_detector", return_value=[(start_mock, end_mock)]):
        result = detect_scenes(Path("fake.mp4"), min_duration=1.5)

    assert result == []


def test_scene_duration_property():
    """Scene.duration should return end - start."""
    s = Scene(start_sec=2.5, end_sec=8.0)
    assert s.duration == pytest.approx(5.5)
