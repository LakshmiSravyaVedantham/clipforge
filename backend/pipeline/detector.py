"""Scene boundary detection using PySceneDetect."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

try:
    from scenedetect import SceneManager, open_video
    from scenedetect.detectors import ContentDetector
    _SCENEDETECT_AVAILABLE = True
except ImportError:
    _SCENEDETECT_AVAILABLE = False


@dataclass
class Scene:
    start_sec: float
    end_sec: float

    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec


def _run_detector(path: Path) -> List[tuple]:
    """Run PySceneDetect on the video file. Separated for testability."""
    if not _SCENEDETECT_AVAILABLE:
        raise RuntimeError(
            "scenedetect not installed. Run: pip install scenedetect[opencv]"
        )
    video = open_video(str(path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=27.0))
    manager.detect_scenes(video)
    return manager.get_scene_list()


def detect_scenes(path: Path, min_duration: float = 1.5) -> List[Scene]:
    """Detect scene boundaries. Returns scenes longer than min_duration seconds.

    Zero-duration scenes (PySceneDetect artifacts) are always excluded.
    min_duration is inclusive: a scene of exactly min_duration seconds is included.
    """
    raw = _run_detector(path)
    scenes = []
    for start, end in raw:
        s = Scene(start_sec=start.get_seconds(), end_sec=end.get_seconds())
        if s.duration > 0 and s.duration >= min_duration:
            scenes.append(s)
    return scenes
