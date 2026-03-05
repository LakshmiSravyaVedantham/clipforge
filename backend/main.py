"""clipforge FastAPI backend."""
from __future__ import annotations

import asyncio
import logging
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiofiles
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from jobs import JobStatus, create_job, get_job, update_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "clipforge"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB

_cleanup_registry: dict[str, tuple[datetime, Path]] = {}


def register_for_cleanup(job_id: str, zip_path: Path) -> None:
    _cleanup_registry[job_id] = (datetime.now(timezone.utc) + timedelta(hours=1), zip_path)


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(300)
        now = datetime.now(timezone.utc)
        expired = [jid for jid, (exp, _) in _cleanup_registry.items() if now > exp]
        for jid in expired:
            _, path = _cleanup_registry.pop(jid)
            path.unlink(missing_ok=True)
            logger.info(f"Cleaned up job {jid}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(cleanup_loop())
    yield


app = FastAPI(title="clipforge", version="0.1.0", lifespan=lifespan)
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
    # NOTE: _jobs dict is not thread-safe; safe for single-worker uvicorn only (I1)
    # TODO v2: validate with ffprobe before enqueueing (I3)
    import uuid as _uuid

    if file.content_type not in ("video/mp4", "video/quicktime", "video/x-matroska"):
        raise HTTPException(400, "Unsupported file type. Upload mp4, mov, or mkv.")

    # Whitelist suffix (Fix I4)
    raw_suffix = Path(file.filename or "").suffix.lower()
    suffix = {".mp4": ".mp4", ".mov": ".mov", ".mkv": ".mkv"}.get(raw_suffix, ".mp4")

    # Stream to temp file before creating job (Fix I2)
    tmp_path = UPLOAD_DIR / f"tmp_{_uuid.uuid4()}{suffix}"
    try:
        async with aiofiles.open(tmp_path, "wb") as f:
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SIZE_BYTES:
                    raise HTTPException(413, "File exceeds 500MB limit.")
                await f.write(chunk)
    except HTTPException:
        tmp_path.unlink(missing_ok=True)
        raise

    # Only create job after successful upload
    job = create_job()
    dest = UPLOAD_DIR / f"{job.job_id}_input{suffix}"
    tmp_path.rename(dest)

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


async def run_pipeline(job_id: str) -> None:
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

        register_for_cleanup(job_id, out_zip)
        update_job(job_id, status=JobStatus.DONE, stage="done", progress=100, output_zip=out_zip)
        logger.info(f"Job {job_id} complete: {out_zip}")

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        update_job(job_id, status=JobStatus.FAILED, stage="failed", error=str(e))
    finally:
        job = get_job(job_id)
        if job and job.input_path and job.input_path.exists():
            job.input_path.unlink(missing_ok=True)
