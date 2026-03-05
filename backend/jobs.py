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
    progress: int = 0
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
