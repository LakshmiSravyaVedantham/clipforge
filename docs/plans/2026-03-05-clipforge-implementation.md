# clipforge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a web app where users upload gameplay footage and download 3 AI-generated video formats (TikTok clip, YouTube reel, cinematic trailer) in under 5 minutes.

**Architecture:** FastAPI backend handles file upload, background processing, and downloads. Next.js frontend handles upload UI and status polling. Core pipeline: PySceneDetect detects scene boundaries, librosa scores audio peaks, moviepy assembles final clips, Whisper generates captions.

**Tech Stack:** Python 3.11, FastAPI, PySceneDetect, moviepy, librosa, openai-whisper, Next.js 14 (App Router), Tailwind CSS, Railway (backend), Vercel (frontend)

---

## Project Structure

```
clipforge/
├── backend/
│   ├── main.py              # FastAPI app, routes
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── detector.py      # Scene detection
│   │   ├── scorer.py        # Highlight scoring
│   │   ├── assembler.py     # Format assembly (TikTok/YouTube/Trailer)
│   │   └── captions.py      # Whisper transcription
│   ├── jobs.py              # In-memory job state
│   ├── requirements.txt
│   └── Procfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # Upload page
│   │   ├── status/[jobId]/page.tsx  # Status + download page
│   │   └── layout.tsx
│   ├── components/
│   │   ├── Uploader.tsx
│   │   └── StatusPoller.tsx
│   ├── package.json
│   └── tailwind.config.ts
└── docs/plans/
```

---

### Task 1: Backend project setup

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/main.py` (skeleton)
- Create: `backend/jobs.py`
- Create: `backend/pipeline/__init__.py`

**Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9
scenedetect[opencv]==0.6.4
moviepy==1.0.3
librosa==0.10.2
openai-whisper==20231117
aiofiles==23.2.1
```

**Step 2: Create backend/jobs.py**

```python
"""In-memory job state. Resets on server restart — fine for v1."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0          # 0-100
    stage: str = "queued"
    input_path: Optional[Path] = None
    output_zip: Optional[Path] = None
    error: Optional[str] = None


_jobs: Dict[str, Job] = {}


def create_job() -> Job:
    job = Job(job_id=str(uuid.uuid4()))
    _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs) -> None:
    job = _jobs.get(job_id)
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)
```

**Step 3: Create backend/main.py skeleton**

```python
"""clipforge FastAPI backend."""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import aiofiles
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from jobs import JobStatus, create_job, get_job, update_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "clipforge"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


app = FastAPI(title="clipforge", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_video(file: UploadFile, background_tasks: BackgroundTasks):
    """Accept a gameplay video, enqueue processing job."""
    if file.content_type not in ("video/mp4", "video/quicktime", "video/x-matroska"):
        raise HTTPException(400, "Unsupported file type. Upload mp4, mov, or mkv.")

    job = create_job()
    dest = UPLOAD_DIR / f"{job.job_id}_input{Path(file.filename).suffix}"

    async with aiofiles.open(dest, "wb") as f:
        size = 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_SIZE_BYTES:
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "File exceeds 500MB limit.")
            await f.write(chunk)

    update_job(job.job_id, input_path=dest)
    background_tasks.add_task(run_pipeline, job.job_id)
    return {"job_id": job.job_id}


@app.get("/status/{job_id}")
def status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "error": job.error,
    }


@app.get("/download/{job_id}")
def download(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.status != JobStatus.DONE:
        raise HTTPException(400, "Job not complete yet.")
    if not job.output_zip or not job.output_zip.exists():
        raise HTTPException(500, "Output file missing.")
    return FileResponse(
        job.output_zip,
        media_type="application/zip",
        filename="clipforge_output.zip",
    )


async def run_pipeline(job_id: str):
    """Background task: run the full processing pipeline."""
    from pipeline.detector import detect_scenes
    from pipeline.scorer import score_scenes
    from pipeline.assembler import assemble_all

    job = get_job(job_id)
    try:
        update_job(job_id, status=JobStatus.PROCESSING, stage="detecting scenes", progress=5)
        scenes = detect_scenes(job.input_path)

        update_job(job_id, stage="scoring highlights", progress=30)
        highlights = score_scenes(job.input_path, scenes)

        update_job(job_id, stage="assembling clips", progress=55)
        out_zip = assemble_all(job.input_path, highlights, job_id)

        update_job(job_id, status=JobStatus.DONE, stage="done", progress=100, output_zip=out_zip)
        logger.info(f"Job {job_id} complete: {out_zip}")

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        update_job(job_id, status=JobStatus.FAILED, stage="failed", error=str(e))
    finally:
        # Clean input file
        if job.input_path and job.input_path.exists():
            job.input_path.unlink(missing_ok=True)
```

**Step 4: Commit**

```bash
cd clipforge
git add backend/
git commit -m "feat: backend skeleton — upload, status, download routes + job state"
```

---

### Task 2: Scene detection (detector.py)

**Files:**
- Create: `backend/pipeline/detector.py`
- Create: `backend/tests/test_detector.py`

**Step 1: Write failing test**

```python
# backend/tests/test_detector.py
from pathlib import Path
from pipeline.detector import detect_scenes, Scene

def test_detect_scenes_returns_list():
    # Use a small synthetic video or a fixture file
    # For unit testing, mock PySceneDetect
    from unittest.mock import patch, MagicMock
    mock_scene_list = [(MagicMock(get_seconds=lambda: 0.0),
                        MagicMock(get_seconds=lambda: 3.0))]
    with patch("pipeline.detector._run_detector", return_value=mock_scene_list):
        result = detect_scenes(Path("fake.mp4"))
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].start_sec == 0.0
    assert result[0].end_sec == 3.0
```

**Step 2: Run test — expect FAIL**

```bash
cd backend && python -m pytest tests/test_detector.py -v
# Expected: ImportError — pipeline.detector not found
```

**Step 3: Implement detector.py**

```python
# backend/pipeline/detector.py
"""Scene boundary detection using PySceneDetect."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector


@dataclass
class Scene:
    start_sec: float
    end_sec: float

    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec


def _run_detector(path: Path) -> list:
    video = open_video(str(path))
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=27.0))
    manager.detect_scenes(video)
    return manager.get_scene_list()


def detect_scenes(path: Path, min_duration: float = 1.5) -> List[Scene]:
    """Detect scene boundaries. Returns scenes longer than min_duration seconds."""
    raw = _run_detector(path)
    scenes = []
    for start, end in raw:
        s = Scene(start_sec=start.get_seconds(), end_sec=end.get_seconds())
        if s.duration >= min_duration:
            scenes.append(s)
    return scenes
```

**Step 4: Run test — expect PASS**

```bash
python -m pytest tests/test_detector.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add backend/pipeline/detector.py backend/tests/
git commit -m "feat: scene detection with PySceneDetect + unit test"
```

---

### Task 3: Highlight scoring (scorer.py)

**Files:**
- Create: `backend/pipeline/scorer.py`
- Create: `backend/tests/test_scorer.py`

**Step 1: Write failing test**

```python
# backend/tests/test_scorer.py
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pipeline.scorer import score_scenes, ScoredScene
from pipeline.detector import Scene

FAKE_SCENES = [Scene(0.0, 5.0), Scene(5.0, 10.0), Scene(10.0, 15.0)]

def test_score_scenes_returns_sorted_list():
    fake_audio = np.zeros(22050 * 15)  # 15 seconds of silence
    with patch("pipeline.scorer._load_audio", return_value=(fake_audio, 22050)):
        result = score_scenes(Path("fake.mp4"), FAKE_SCENES)
    assert isinstance(result, list)
    assert len(result) == len(FAKE_SCENES)
    # Scores should be floats
    assert all(isinstance(s.score, float) for s in result)
    # Should be sorted descending by score
    scores = [s.score for s in result]
    assert scores == sorted(scores, reverse=True)

def test_score_scenes_empty_input():
    with patch("pipeline.scorer._load_audio", return_value=(np.zeros(100), 22050)):
        result = score_scenes(Path("fake.mp4"), [])
    assert result == []
```

**Step 2: Run — expect FAIL**

```bash
python -m pytest tests/test_scorer.py -v
```

**Step 3: Implement scorer.py**

```python
# backend/pipeline/scorer.py
"""Score scenes by audio excitement (RMS energy peaks)."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List

import librosa
import numpy as np

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


def _load_audio(path: Path) -> tuple[np.ndarray, int]:
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    return y, sr


def _rms_score(y: np.ndarray, sr: int, start: float, end: float) -> float:
    """Mean RMS energy of the audio segment."""
    start_sample = int(start * sr)
    end_sample = int(end * sr)
    segment = y[start_sample:end_sample]
    if len(segment) == 0:
        return 0.0
    rms = librosa.feature.rms(y=segment, frame_length=2048, hop_length=512)
    return float(np.mean(rms))


def score_scenes(path: Path, scenes: List[Scene], top_k: int = 10) -> List[ScoredScene]:
    """Score and rank scenes by audio excitement. Returns top_k sorted descending."""
    if not scenes:
        return []
    y, sr = _load_audio(path)
    scored = [ScoredScene(scene=s, score=_rms_score(y, sr, s.start_sec, s.end_sec)) for s in scenes]
    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_k]
```

**Step 4: Run — expect PASS**

```bash
python -m pytest tests/test_scorer.py -v
```

**Step 5: Commit**

```bash
git add backend/pipeline/scorer.py backend/tests/test_scorer.py
git commit -m "feat: highlight scoring via librosa RMS energy"
```

---

### Task 4: Captions (captions.py)

**Files:**
- Create: `backend/pipeline/captions.py`

**Step 1: Implement captions.py**

```python
# backend/pipeline/captions.py
"""Generate subtitles via OpenAI Whisper."""
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import whisper


_model = None

def _get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def transcribe_segment(video_path: Path, start: float, end: float) -> List[Tuple[float, float, str]]:
    """
    Transcribe audio from start to end seconds.
    Returns list of (start, end, text) tuples for subtitle rendering.
    """
    model = _get_model()
    result = model.transcribe(
        str(video_path),
        language="en",
        clip_timestamps=[start, end],
        verbose=False,
    )
    segments = []
    for seg in result.get("segments", []):
        segments.append((seg["start"], seg["end"], seg["text"].strip()))
    return segments
```

**Step 2: Commit**

```bash
git add backend/pipeline/captions.py
git commit -m "feat: Whisper caption generation for video segments"
```

---

### Task 5: Format assembly (assembler.py)

**Files:**
- Create: `backend/pipeline/assembler.py`

**Step 1: Implement assembler.py**

```python
# backend/pipeline/assembler.py
"""Assemble highlight clips into TikTok, YouTube, and Trailer formats."""
from __future__ import annotations
import zipfile
import tempfile
from pathlib import Path
from typing import List

from moviepy.editor import (
    VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip, vfx
)

from pipeline.scorer import ScoredScene
from pipeline.captions import transcribe_segment


TIKTOK_W, TIKTOK_H = 1080, 1920   # vertical 9:16
YOUTUBE_W, YOUTUBE_H = 1920, 1080  # horizontal 16:9
TRAILER_W, TRAILER_H = 1920, 1080


def _crop_vertical(clip):
    """Center-crop a landscape clip to 9:16 for TikTok."""
    w, h = clip.size
    target_w = int(h * 9 / 16)
    x_center = w / 2
    return clip.crop(x_center=x_center, width=target_w, height=h).resize((TIKTOK_W, TIKTOK_H))


def _add_captions(clip, subs: list, offset: float):
    """Overlay subtitle text onto clip."""
    overlays = [clip]
    for start, end, text in subs:
        t_start = max(0, start - offset)
        t_end = min(clip.duration, end - offset)
        if t_end <= t_start or not text:
            continue
        txt = (TextClip(text, fontsize=50, color="white", font="DejaVu-Sans-Bold",
                        stroke_color="black", stroke_width=2, method="caption",
                        size=(clip.w * 0.9, None))
               .set_start(t_start).set_end(t_end)
               .set_position(("center", 0.85), relative=True))
        overlays.append(txt)
    return CompositeVideoClip(overlays)


def _make_tiktok(source: VideoFileClip, top: ScoredScene, job_dir: Path) -> Path:
    """Best single moment, vertical crop, captions, max 60s."""
    duration = min(top.duration, 60.0)
    clip = source.subclip(top.start_sec, top.start_sec + duration)
    clip = _crop_vertical(clip)
    subs = transcribe_segment(Path(source.filename), top.start_sec, top.start_sec + duration)
    clip = _add_captions(clip, subs, top.start_sec)
    out = job_dir / "tiktok.mp4"
    clip.write_videofile(str(out), codec="libx264", audio_codec="aac",
                         fps=30, preset="fast", logger=None)
    clip.close()
    return out


def _make_youtube(source: VideoFileClip, highlights: List[ScoredScene], job_dir: Path) -> Path:
    """Top moments concatenated, max 10 min total."""
    clips = []
    total = 0.0
    for h in highlights[:8]:
        dur = min(h.duration, 90.0)
        if total + dur > 600:
            break
        c = source.subclip(h.start_sec, h.start_sec + dur)
        clips.append(c)
        total += dur
    final = concatenate_videoclips(clips, method="compose")
    out = job_dir / "youtube.mp4"
    final.write_videofile(str(out), codec="libx264", audio_codec="aac",
                          fps=30, preset="fast", logger=None)
    final.close()
    for c in clips:
        c.close()
    return out


def _make_trailer(source: VideoFileClip, highlights: List[ScoredScene], job_dir: Path) -> Path:
    """Cinematic trailer: 90s, slow-mo on top moments, fast cuts on others."""
    clips = []
    top3 = highlights[:3]
    rest = highlights[3:8]

    # Fast cuts from rest
    for h in rest:
        dur = min(h.duration, 6.0)
        c = source.subclip(h.start_sec, h.start_sec + dur)
        clips.append(c)

    # Slow-mo climax from top moment
    if top3:
        best = top3[0]
        dur = min(best.duration, 20.0)
        c = source.subclip(best.start_sec, best.start_sec + dur).fx(vfx.speedx, 0.5)
        clips.append(c)

    final = concatenate_videoclips(clips, method="compose")
    if final.duration > 90:
        final = final.subclip(0, 90)
    out = job_dir / "trailer.mp4"
    final.write_videofile(str(out), codec="libx264", audio_codec="aac",
                          fps=30, preset="fast", logger=None)
    final.close()
    for c in clips:
        c.close()
    return out


def assemble_all(input_path: Path, highlights: List[ScoredScene], job_id: str) -> Path:
    """Run all 3 format assemblers and zip outputs."""
    job_dir = input_path.parent / f"{job_id}_out"
    job_dir.mkdir(exist_ok=True)

    source = VideoFileClip(str(input_path))

    tiktok = _make_tiktok(source, highlights[0], job_dir)
    youtube = _make_youtube(source, highlights, job_dir)
    trailer = _make_trailer(source, highlights, job_dir)
    source.close()

    zip_path = input_path.parent / f"{job_id}_output.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(tiktok, "tiktok.mp4")
        zf.write(youtube, "youtube.mp4")
        zf.write(trailer, "trailer.mp4")

    # Cleanup individual files
    for f in [tiktok, youtube, trailer]:
        f.unlink(missing_ok=True)
    import shutil
    shutil.rmtree(job_dir, ignore_errors=True)

    return zip_path
```

**Step 2: Commit**

```bash
git add backend/pipeline/assembler.py
git commit -m "feat: assemble TikTok, YouTube, trailer formats with moviepy"
```

---

### Task 6: Frontend — Next.js setup

**Files:**
- Create: `frontend/` (Next.js app)

**Step 1: Scaffold**

```bash
cd clipforge
npx create-next-app@latest frontend \
  --typescript --tailwind --app --no-src-dir \
  --import-alias "@/*" --no-eslint
```

**Step 2: Set API base URL**

Create `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Step 3: Commit**

```bash
git add frontend/
git commit -m "feat: Next.js frontend scaffold with Tailwind"
```

---

### Task 7: Upload page (frontend)

**Files:**
- Modify: `frontend/app/page.tsx`
- Create: `frontend/components/Uploader.tsx`

**Step 1: Create Uploader.tsx**

```tsx
// frontend/components/Uploader.tsx
"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL;
const MAX_MB = 500;

export default function Uploader() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleFile = useCallback(async (file: File) => {
    if (!file.type.startsWith("video/")) {
      setError("Please upload a video file (mp4, mov, mkv).");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File must be under ${MAX_MB}MB.`);
      return;
    }
    setError("");
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API}/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
      const { job_id } = await res.json();
      router.push(`/status/${job_id}`);
    } catch (e: any) {
      setError(e.message);
      setUploading(false);
    }
  }, [router]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <div className="max-w-xl w-full text-center space-y-6">
        <h1 className="text-4xl font-bold text-white">clipforge</h1>
        <p className="text-gray-400">Upload gameplay footage. Get TikTok, YouTube, and trailer clips — automatically.</p>

        <label
          className={`block border-2 border-dashed rounded-2xl p-16 cursor-pointer transition
            ${dragging ? "border-violet-400 bg-violet-950" : "border-gray-700 hover:border-gray-500"}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input type="file" accept="video/*" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
          <div className="space-y-3">
            <div className="text-5xl">🎮</div>
            <p className="text-gray-300 text-lg">
              {uploading ? "Uploading..." : "Drop your gameplay video here"}
            </p>
            <p className="text-gray-500 text-sm">mp4, mov, mkv · max 500MB · max 10 min</p>
          </div>
        </label>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>
    </div>
  );
}
```

**Step 2: Update page.tsx**

```tsx
// frontend/app/page.tsx
import Uploader from "@/components/Uploader";
export default function Home() { return <Uploader />; }
```

**Step 3: Commit**

```bash
git add frontend/app/page.tsx frontend/components/
git commit -m "feat: upload UI with drag-and-drop"
```

---

### Task 8: Status + download page (frontend)

**Files:**
- Create: `frontend/app/status/[jobId]/page.tsx`
- Create: `frontend/components/StatusPoller.tsx`

**Step 1: Create StatusPoller.tsx**

```tsx
// frontend/components/StatusPoller.tsx
"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL;

interface StatusData {
  job_id: string;
  status: "queued" | "processing" | "done" | "failed";
  progress: number;
  stage: string;
  error?: string;
}

export default function StatusPoller({ jobId }: { jobId: string }) {
  const [data, setData] = useState<StatusData | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API}/status/${jobId}`);
        const json = await res.json();
        setData(json);
        if (json.status !== "done" && json.status !== "failed") {
          setTimeout(poll, 2000);
        }
      } catch {
        setTimeout(poll, 3000);
      }
    };
    poll();
  }, [jobId]);

  if (!data) return <p className="text-gray-400">Connecting...</p>;

  if (data.status === "failed") return (
    <div className="text-center space-y-4">
      <p className="text-red-400 text-xl">Processing failed</p>
      <p className="text-gray-500 text-sm">{data.error}</p>
      <a href="/" className="text-violet-400 underline">Try another video</a>
    </div>
  );

  if (data.status === "done") return (
    <div className="text-center space-y-6">
      <div className="text-5xl">✅</div>
      <h2 className="text-2xl font-bold text-white">Your clips are ready</h2>
      <a
        href={`${API}/download/${jobId}`}
        className="inline-block bg-violet-600 hover:bg-violet-500 text-white font-semibold px-8 py-4 rounded-xl text-lg transition"
      >
        Download ZIP (TikTok + YouTube + Trailer)
      </a>
      <p className="text-gray-500 text-sm">Files available for 1 hour</p>
      <a href="/" className="block text-gray-500 hover:text-gray-300 text-sm transition">Process another video</a>
    </div>
  );

  return (
    <div className="text-center space-y-6 w-full max-w-sm">
      <div className="text-4xl animate-pulse">⚙️</div>
      <p className="text-gray-300 capitalize">{data.stage.replace(/_/g, " ")}...</p>
      <div className="w-full bg-gray-800 rounded-full h-3">
        <div
          className="bg-violet-600 h-3 rounded-full transition-all duration-500"
          style={{ width: `${data.progress}%` }}
        />
      </div>
      <p className="text-gray-500 text-sm">{data.progress}%</p>
    </div>
  );
}
```

**Step 2: Create status page**

```tsx
// frontend/app/status/[jobId]/page.tsx
import StatusPoller from "@/components/StatusPoller";

export default function StatusPage({ params }: { params: { jobId: string } }) {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <StatusPoller jobId={params.jobId} />
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/app/status/ frontend/components/StatusPoller.tsx
git commit -m "feat: status page with 2s polling and download button"
```

---

### Task 9: Cleanup job — delete files after 1 hour

**Files:**
- Modify: `backend/main.py`

**Step 1: Add cleanup task to main.py**

Add this to `main.py` after the download route:

```python
import asyncio
from datetime import datetime, timedelta

_cleanup_registry: dict[str, tuple[datetime, Path]] = {}


def register_for_cleanup(job_id: str, zip_path: Path) -> None:
    _cleanup_registry[job_id] = (datetime.utcnow() + timedelta(hours=1), zip_path)


async def cleanup_loop():
    while True:
        await asyncio.sleep(300)  # check every 5 min
        now = datetime.utcnow()
        expired = [jid for jid, (exp, _) in _cleanup_registry.items() if now > exp]
        for jid in expired:
            _, path = _cleanup_registry.pop(jid)
            path.unlink(missing_ok=True)
            logger.info(f"Cleaned up job {jid}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(cleanup_loop())
    yield

# Update app instantiation:
# app = FastAPI(title="clipforge", version="0.1.0", lifespan=lifespan)
```

Also call `register_for_cleanup(job_id, out_zip)` inside `run_pipeline` on success.

**Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat: auto-cleanup zip files after 1 hour"
```

---

### Task 10: Deploy

**Step 1: Create backend/Procfile for Railway**

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Step 2: Create backend/railway.json**

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

**Step 3: Push backend to Railway**

```bash
cd backend
railway login
railway init
railway up
# Note the public URL — set as NEXT_PUBLIC_API_URL in Vercel
```

**Step 4: Deploy frontend to Vercel**

```bash
cd frontend
vercel
# Set env var: NEXT_PUBLIC_API_URL=<railway-url>
vercel --prod
```

**Step 5: Create GitHub repo and push everything**

```bash
cd clipforge
gh repo create clipforge --public \
  --description "AI gameplay-to-content engine. Upload footage, get TikTok + YouTube + trailer clips." \
  --source . --remote origin --push
```

**Step 6: Commit**

```bash
git add backend/Procfile backend/railway.json
git commit -m "chore: add Railway deploy config"
```

---

### Task 11: Write and publish Dev.to post

After everything is deployed and tested:

1. Title: `"I Built an AI That Turns Raw Gameplay into TikTok, YouTube, and Trailer Clips Automatically"`
2. Show the pipeline (scene detect → score → assemble)
3. Include before/after: raw footage → 3 outputs
4. Link the GitHub repo
5. Tags: `ai`, `python`, `gaming`, `opensource`

Publish with the Dev.to API:
```bash
curl -X POST https://dev.to/api/articles \
  -H "api-key: $DEVTO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"article": {"title": "...", "body_markdown": "...", "tags": ["ai","python","gaming","opensource"], "published": true}}'
```

---

## Testing Checklist

- [ ] Upload a 5-min gameplay video → job ID returned
- [ ] Status endpoint shows progress updates
- [ ] TikTok clip is vertical (1080x1920), ≤60s, has captions
- [ ] YouTube reel is horizontal, multiple scenes
- [ ] Trailer has slow-mo segment
- [ ] ZIP downloads correctly
- [ ] Files are cleaned up after 1 hour
- [ ] 500MB limit enforced
- [ ] Invalid file type rejected with 400
