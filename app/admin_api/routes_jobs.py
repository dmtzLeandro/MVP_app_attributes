from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.jobs import get_job

router = APIRouter(prefix="/admin/jobs", tags=["admin-jobs"])


@router.get("/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": "Job not found",
                "details": {"job_id": job_id},
            },
        )
    return {"ok": True, "job": job}
