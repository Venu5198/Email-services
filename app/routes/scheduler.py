import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, status, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.schemas.email import EmailRequest

logger = logging.getLogger("email_service")
router = APIRouter(prefix="/api/v1/schedule", tags=["Scheduled Email"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ScheduledEmailRequest(BaseModel):
    """
    Schedule an email to be sent at a specific time or on a recurring cron schedule.
    The full email request payload is embedded and replayed at send time.
    """
    # Email content — same fields as EmailRequest
    email: EmailRequest = Field(..., description="Full email request payload.")

    # Scheduling
    send_at: Optional[datetime] = Field(
        default=None,
        description="UTC datetime for one-time send. Example: '2026-06-02T09:00:00Z'."
    )
    cron_expression: Optional[str] = Field(
        default=None,
        description="5-field cron expression for recurring sends. Example: '0 9 * * MON' (every Monday 9am)."
    )
    job_name: Optional[str] = Field(
        default=None,
        description="Human-readable label for this job (e.g. 'Weekly Newsletter')."
    )
    max_runs: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of times a recurring job will run. Null = unlimited."
    )

    @field_validator("send_at", mode="before")
    @classmethod
    def require_future_date(cls, v):
        if v is not None:
            dt = v if isinstance(v, datetime) else datetime.fromisoformat(str(v))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt <= datetime.now(timezone.utc):
                raise ValueError("send_at must be a future datetime (UTC).")
        return v


class ScheduledJobResponse(BaseModel):
    """Response after scheduling an email job."""
    job_id: str
    job_name: str
    status: str
    send_at: Optional[str] = None
    cron_expression: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str
    max_runs: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Schedule an Email Job",
    description=(
        "Schedules an email to be sent at a future datetime (`send_at`) "
        "or on a recurring cron schedule (`cron_expression`). "
        "Exactly one of the two must be provided. "
        "Jobs survive service restarts via MongoDB persistence."
    ),
)
def create_scheduled_job(req: ScheduledEmailRequest):
    """Creates a new scheduled email job."""
    from app.services.scheduler_service import scheduler_service

    if not req.send_at and not req.cron_expression:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either send_at (one-time) or cron_expression (recurring)."
        )

    try:
        job = scheduler_service.schedule_job(
            email_request_dict=req.email.model_dump(),
            send_at=req.send_at,
            cron_expression=req.cron_expression,
            job_name=req.job_name,
            max_runs=req.max_runs,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Scheduler: failed to create job — {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule job: {e}"
        )

    return {
        "message": "Email job scheduled successfully.",
        "job_id": job["job_id"],
        "job_name": job["job_name"],
        "status": job["status"],
        "send_at": job.get("send_at"),
        "cron_expression": job.get("cron_expression"),
        "next_run_at": job.get("next_run_at"),
    }


@router.get(
    "",
    summary="List Scheduled Jobs",
    description="Returns all scheduled email jobs, optionally filtered by status.",
)
def list_scheduled_jobs(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: pending, sent, failed, cancelled, missed"
    )
):
    """Lists all scheduled jobs from MongoDB."""
    from app.services.scheduler_service import scheduler_service
    jobs = scheduler_service.list_jobs(status_filter=status_filter)
    return {"total": len(jobs), "jobs": jobs}


@router.get(
    "/{job_id}",
    summary="Get Scheduled Job",
    description="Returns the details and current status of a specific scheduled job.",
)
def get_scheduled_job(job_id: str):
    """Returns a single scheduled job by job_id."""
    from app.services.scheduler_service import scheduler_service
    job = scheduler_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled job '{job_id}' not found."
        )
    return job


@router.delete(
    "/{job_id}",
    summary="Cancel Scheduled Job",
    description="Cancels a pending or recurring scheduled job. Already-sent jobs cannot be cancelled.",
)
def cancel_scheduled_job(job_id: str):
    """Cancels a scheduled job."""
    from app.services.scheduler_service import scheduler_service
    cancelled = scheduler_service.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled job '{job_id}' not found or already completed."
        )
    return {"message": f"Scheduled job '{job_id}' has been cancelled."}
