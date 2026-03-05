# backend/pipeline/assembler.py
"""Assemble highlight clips into TikTok, YouTube, and Trailer formats."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import List

try:
    from moviepy.editor import (
        CompositeVideoClip,
        TextClip,
        VideoFileClip,
        concatenate_videoclips,
        vfx,
    )
    _MOVIEPY_AVAILABLE = True
except ImportError:
    _MOVIEPY_AVAILABLE = False

from pipeline.scorer import ScoredScene

TIKTOK_W, TIKTOK_H = 1080, 1920    # 9:16 vertical
YOUTUBE_W, YOUTUBE_H = 1920, 1080  # 16:9 horizontal
TRAILER_MAX_SEC = 90
YOUTUBE_MAX_SEC = 600  # 10 min
TIKTOK_MAX_SEC = 60
YOUTUBE_MAX_CLIPS = 8
TRAILER_MAX_CLIPS = 8


def _require_moviepy() -> None:
    if not _MOVIEPY_AVAILABLE:
        raise RuntimeError("moviepy not installed. Run: pip install moviepy")


def _crop_vertical(clip):
    """Center-crop a landscape clip to 9:16 for TikTok."""
    w, h = clip.size
    target_w = int(h * 9 / 16)
    return clip.crop(x_center=w / 2, width=target_w, height=h).resize((TIKTOK_W, TIKTOK_H))


def _add_captions(clip, subs: list, offset: float):
    """Overlay subtitle TextClips onto the video clip."""
    overlays = [clip]
    for start, end, text in subs:
        t_start = max(0.0, start - offset)
        t_end = min(clip.duration, end - offset)
        if t_end <= t_start or not text:
            continue
        txt = (
            TextClip(
                text,
                fontsize=50,
                color="white",
                font="DejaVu-Sans-Bold",
                stroke_color="black",
                stroke_width=2,
                method="caption",
                size=(int(clip.w * 0.9), None),
            )
            .set_start(t_start)
            .set_end(t_end)
            .set_position(("center", 0.85), relative=True)
        )
        overlays.append(txt)
    return CompositeVideoClip(overlays)


def _make_tiktok(source: "VideoFileClip", top: ScoredScene, job_dir: Path) -> Path:
    """Best single moment, vertical crop, captions, max 60s."""
    from pipeline.captions import transcribe_segment
    duration = min(top.duration, TIKTOK_MAX_SEC)
    clip = source.subclip(top.start_sec, top.start_sec + duration)
    clip = _crop_vertical(clip)
    subs = transcribe_segment(Path(source.filename), top.start_sec, top.start_sec + duration)
    clip = _add_captions(clip, subs, top.start_sec)
    out = job_dir / "tiktok.mp4"
    clip.write_videofile(str(out), codec="libx264", audio_codec="aac",
                         fps=30, preset="fast", logger=None)
    clip.close()
    return out


def _make_youtube(source: "VideoFileClip", highlights: List[ScoredScene], job_dir: Path) -> Path:
    """Top moments concatenated, capped at 10 minutes."""
    clips = []
    total = 0.0
    for h in highlights[:YOUTUBE_MAX_CLIPS]:
        dur = min(h.duration, 90.0)
        if total + dur > YOUTUBE_MAX_SEC:
            break
        clips.append(source.subclip(h.start_sec, h.start_sec + dur))
        total += dur
    if not clips:
        # Fallback: use first 60s of source
        clips = [source.subclip(0, min(60, source.duration))]
    final = concatenate_videoclips(clips, method="compose")
    out = job_dir / "youtube.mp4"
    final.write_videofile(str(out), codec="libx264", audio_codec="aac",
                          fps=30, preset="fast", logger=None)
    final.close()
    for c in clips:
        c.close()
    return out


def _make_trailer(source: "VideoFileClip", highlights: List[ScoredScene], job_dir: Path) -> Path:
    """Cinematic trailer: fast cuts then slow-mo climax, capped at 90s."""
    clips = []
    # Fast cuts from lower-ranked highlights
    for h in highlights[1:TRAILER_MAX_CLIPS]:
        dur = min(h.duration, 6.0)
        clips.append(source.subclip(h.start_sec, h.start_sec + dur))
    # Slow-mo climax from top highlight
    if highlights:
        best = highlights[0]
        dur = min(best.duration, 20.0)
        clips.append(source.subclip(best.start_sec, best.start_sec + dur).fx(vfx.speedx, 0.5))
    if not clips:
        clips = [source.subclip(0, min(30, source.duration))]
    final = concatenate_videoclips(clips, method="compose")
    if final.duration > TRAILER_MAX_SEC:
        final = final.subclip(0, TRAILER_MAX_SEC)
    out = job_dir / "trailer.mp4"
    final.write_videofile(str(out), codec="libx264", audio_codec="aac",
                          fps=30, preset="fast", logger=None)
    final.close()
    for c in clips:
        c.close()
    return out


def assemble_all(input_path: Path, highlights: List[ScoredScene], job_id: str) -> Path:
    """Run all 3 assemblers and zip outputs. Cleans up temp files."""
    _require_moviepy()
    if not highlights:
        raise ValueError("No highlights to assemble — scoring produced empty list.")

    job_dir = input_path.parent / f"{job_id}_out"
    job_dir.mkdir(exist_ok=True)

    source = VideoFileClip(str(input_path))
    tiktok = youtube = trailer = None  # initialize so cleanup never hits NameError
    try:
        tiktok = _make_tiktok(source, highlights[0], job_dir)
        youtube = _make_youtube(source, highlights, job_dir)
        trailer = _make_trailer(source, highlights, job_dir)
    finally:
        source.close()

    zip_path = input_path.parent / f"{job_id}_output.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if tiktok and tiktok.exists():
            zf.write(tiktok, "tiktok.mp4")
        if youtube and youtube.exists():
            zf.write(youtube, "youtube.mp4")
        if trailer and trailer.exists():
            zf.write(trailer, "trailer.mp4")

    for f in [tiktok, youtube, trailer]:
        if f:
            f.unlink(missing_ok=True)
    shutil.rmtree(job_dir, ignore_errors=True)

    return zip_path
