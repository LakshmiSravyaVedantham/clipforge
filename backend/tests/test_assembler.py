# backend/tests/test_assembler.py
"""Tests for format assembler. moviepy is fully mocked — no real video needed."""
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import zipfile
import tempfile
import pytest

from pipeline.detector import Scene
from pipeline.scorer import ScoredScene


def _make_highlight(start: float, end: float, score: float = 1.0) -> ScoredScene:
    return ScoredScene(scene=Scene(start, end), score=score)


def test_assemble_all_raises_on_empty_highlights():
    """assemble_all should raise ValueError when highlights list is empty."""
    with patch("pipeline.assembler._MOVIEPY_AVAILABLE", True):
        from pipeline.assembler import assemble_all
        with pytest.raises(ValueError, match="No highlights"):
            assemble_all(Path("fake.mp4"), [], "test-job-id")


def test_assemble_all_raises_when_moviepy_unavailable():
    """assemble_all should raise RuntimeError when moviepy is not installed."""
    with patch("pipeline.assembler._MOVIEPY_AVAILABLE", False):
        from pipeline.assembler import assemble_all
        highlights = [_make_highlight(0.0, 10.0)]
        with pytest.raises(RuntimeError, match="moviepy not installed"):
            assemble_all(Path("fake.mp4"), highlights, "test-job-id")


def test_crop_vertical_produces_portrait_dimensions():
    """_crop_vertical should produce 9:16 aspect ratio clip."""
    with patch("pipeline.assembler._MOVIEPY_AVAILABLE", True):
        from pipeline.assembler import _crop_vertical, TIKTOK_W, TIKTOK_H

    mock_clip = MagicMock()
    mock_clip.size = (1920, 1080)
    mock_cropped = MagicMock()
    mock_cropped.resize.return_value = MagicMock()
    mock_clip.crop.return_value = mock_cropped

    result = _crop_vertical(mock_clip)

    # Should crop to 9:16 width = int(1080 * 9/16) = 607
    mock_clip.crop.assert_called_once_with(x_center=960.0, width=607, height=1080)
    mock_cropped.resize.assert_called_once_with((TIKTOK_W, TIKTOK_H))


def test_make_youtube_falls_back_on_empty_highlights():
    """_make_youtube should use first 60s of source if no highlights fit."""
    with patch("pipeline.assembler._MOVIEPY_AVAILABLE", True):
        from pipeline.assembler import _make_youtube

    mock_source = MagicMock()
    mock_source.duration = 120.0
    mock_source.subclip.return_value = MagicMock()
    mock_concat = MagicMock()
    mock_concat.duration = 60.0

    with patch("pipeline.assembler.concatenate_videoclips", return_value=mock_concat, create=True), \
         tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp)
        _make_youtube(mock_source, [], job_dir)

    # Should fall back to source.subclip(0, 60)
    mock_source.subclip.assert_called_with(0, 60)


def test_make_trailer_uses_all_highlights_when_fewer_than_four():
    """With only 2 highlights, fast cuts should use highlights[1:], not highlights[3:]."""
    with patch("pipeline.assembler._MOVIEPY_AVAILABLE", True):
        from pipeline.assembler import _make_trailer

    mock_source = MagicMock()
    mock_source.duration = 30.0
    mock_subclip = MagicMock()
    mock_subclip.duration = 5.0
    mock_source.subclip.return_value = mock_subclip
    mock_subclip.fx.return_value = mock_subclip

    mock_final = MagicMock()
    mock_final.duration = 10.0

    highlights = [
        _make_highlight(0.0, 10.0, score=2.0),  # top — slow-mo
        _make_highlight(10.0, 15.0, score=1.0), # second — fast cut
    ]

    with patch("pipeline.assembler.concatenate_videoclips", return_value=mock_final, create=True), \
         patch("pipeline.assembler.vfx", create=True), \
         tempfile.TemporaryDirectory() as tmp:
        _make_trailer(mock_source, highlights, Path(tmp))

    # subclip should be called twice: once for fast cut (h[1]) + once for slow-mo (h[0])
    assert mock_source.subclip.call_count == 2


def test_assemble_all_initializes_output_vars_before_assembly():
    """assemble_all should not raise NameError if assembly partially fails."""
    with patch("pipeline.assembler._MOVIEPY_AVAILABLE", True), \
         patch("pipeline.assembler.VideoFileClip", create=True) as mock_vfc, \
         patch("pipeline.assembler._make_tiktok", side_effect=RuntimeError("ffmpeg missing")):
        from pipeline.assembler import assemble_all

        mock_vfc.return_value = MagicMock()
        highlights = [_make_highlight(0.0, 10.0)]

        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "fake.mp4"
            input_path.touch()
            with pytest.raises(RuntimeError, match="ffmpeg missing"):
                assemble_all(input_path, highlights, "test-job")
        # Should raise the original RuntimeError, not a NameError
