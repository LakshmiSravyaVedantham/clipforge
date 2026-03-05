# backend/tests/test_captions.py
"""Tests for caption generation. Whisper is mocked — no model download required."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_transcribe_segment_returns_list():
    """transcribe_segment should return a list of (start, end, text) tuples."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {
        "segments": [
            {"start": 0.5, "end": 1.2, "text": " Hello world"},
            {"start": 1.5, "end": 2.0, "text": " Nice shot"},
        ]
    }
    with patch("pipeline.captions._WHISPER_AVAILABLE", True), \
         patch("pipeline.captions._get_model", return_value=mock_model):
        from pipeline.captions import transcribe_segment
        result = transcribe_segment(Path("fake.mp4"), 0.0, 5.0)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == (0.5, 1.2, "Hello world")
    assert result[1] == (1.5, 2.0, "Nice shot")


def test_transcribe_segment_skips_empty_text():
    """Segments with empty text after strip should be excluded."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "   "},  # whitespace only
            {"start": 1.0, "end": 2.0, "text": "Good one"},
        ]
    }
    with patch("pipeline.captions._WHISPER_AVAILABLE", True), \
         patch("pipeline.captions._get_model", return_value=mock_model):
        from pipeline.captions import transcribe_segment
        result = transcribe_segment(Path("fake.mp4"), 0.0, 5.0)

    assert len(result) == 1
    assert result[0][2] == "Good one"


def test_transcribe_segment_handles_transcribe_exception():
    """If whisper.transcribe raises, return empty list gracefully."""
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("ffmpeg not found")
    with patch("pipeline.captions._WHISPER_AVAILABLE", True), \
         patch("pipeline.captions._get_model", return_value=mock_model):
        from pipeline.captions import transcribe_segment
        result = transcribe_segment(Path("fake.mp4"), 0.0, 5.0)

    assert result == []


def test_transcribe_segment_empty_segments():
    """No segments from Whisper should return empty list."""
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {"segments": []}
    with patch("pipeline.captions._WHISPER_AVAILABLE", True), \
         patch("pipeline.captions._get_model", return_value=mock_model):
        from pipeline.captions import transcribe_segment
        result = transcribe_segment(Path("fake.mp4"), 0.0, 5.0)

    assert result == []
