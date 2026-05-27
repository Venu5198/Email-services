import logging
from fastapi import APIRouter, BackgroundTasks, status, HTTPException

from app.schemas.bulk_email import BulkEmailRequest, BulkJobStatusResponse
from app.services.bulk_email_service import BulkEmailService
from app.config import settings

logger = logging.getLogger("email_service")
router = APIRouter(prefix="/api/v1", tags=["Bulk Email"])

bulk_service = BulkEmailService()


def _bulk_worker(job_id: str, req: BulkEmailRequest):
    """Background task that executes the full bulk send workflow."""
    try:
        result = bulk_service.run_bulk_send(req, job_id=job_id)
        logger.info(
            f"Bulk job {result.job_id} finished — "
            f"sent={result.sent}, failed={result.failed}, skipped={result.skipped_suppressed}"
        )
    except Exception as e:
        logger.error(f"Bulk send background worker failed: {e}")
        # Mark job as failed in MongoDB so status endpoint shows error
        try:
            from app.utils.mongo_client import mongo_client
            from datetime import datetime, timezone
            jobs_coll = mongo_client.get_collection("bulk_send_jobs")
            if jobs_coll is not None:
                jobs_coll.update_one(
                    {"job_id": job_id},
                    {"$set": {"status": "failed", "error_detail": str(e),
                              "completed_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True
                )
        except Exception:
            pass


@router.post(
    "/bulk-send",
    response_model=BulkJobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send Bulk Emails (Async)",
    description=(
        "Queues a high-volume personalized bulk email job. "
        "Recipients are sourced from a MongoDB collection or an explicit email list. "
        "Each recipient receives an individually rendered, personalized email. "
        "The job runs in the background and progress is tracked in the bulk_send_jobs collection."
    ),
)
def bulk_send_emails(req: BulkEmailRequest, background_tasks: BackgroundTasks):
    """
    Accepts a bulk send request and dispatches it as a background task.

    - **recipient_source**: `'mongodb'` (query a collection) or `'list'` (explicit emails)
    - **recipient_query**: Any valid MongoDB query filter (e.g. `{'country': 'India'}`)
    - **batch_size**: How many emails per batch (1–2000)
    - **subject_template**: Jinja2 template for subject (e.g. `'Hello {{ role }}'`)
    - **template_name**: Jinja2 HTML template file (e.g. `'newsletter.html'`)
    - **template_context**: Base context merged with per-recipient MongoDB fields
    """
    import uuid
    from datetime import datetime, timezone
    from app.utils.mongo_client import mongo_client

    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    # Write initial 'queued' record IMMEDIATELY so status endpoint never returns 404
    if settings.ENABLE_MONGO_LOGGING:
        jobs_coll = mongo_client.get_collection("bulk_send_jobs")
        if jobs_coll is not None:
            try:
                jobs_coll.insert_one({
                    "job_id": job_id,
                    "status": "queued",
                    "total_recipients": 0,
                    "sent": 0,
                    "failed": 0,
                    "skipped_suppressed": 0,
                    "template_name": req.template_name,
                    "initiated_by": req.initiated_by,
                    "started_at": started_at,
                    "completed_at": None,
                    "error_detail": None,
                })
            except Exception as ex:
                logger.warning(f"Could not write initial job record: {ex}")

    background_tasks.add_task(_bulk_worker, job_id, req)

    logger.info(
        f"Bulk send job {job_id} accepted — source={req.recipient_source}, "
        f"collection={req.recipient_collection}, initiated_by={req.initiated_by}"
    )

    return BulkJobStatusResponse(
        job_id=job_id,
        status="queued",
        total_recipients=0,
        sent=0,
        failed=0,
        skipped_suppressed=0,
        template_name=req.template_name,
        initiated_by=req.initiated_by,
        started_at=started_at,
    )


@router.get(
    "/bulk-send/{job_id}/status",
    response_model=BulkJobStatusResponse,
    summary="Get Bulk Job Status",
    description="Returns the current progress and status of a bulk email send job.",
)
def get_bulk_job_status(job_id: str):
    """Fetches the progress of a bulk send job from MongoDB."""
    from app.utils.mongo_client import mongo_client

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected. Job tracking unavailable."
        )

    jobs_coll = mongo_client.get_collection("bulk_send_jobs")
    if jobs_coll is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="bulk_send_jobs collection is unavailable."
        )

    doc = jobs_coll.find_one({"job_id": job_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bulk job '{job_id}' not found."
        )

    return BulkJobStatusResponse(
        job_id=doc["job_id"],
        status=doc.get("status", "unknown"),
        total_recipients=doc.get("total_recipients", 0),
        sent=doc.get("sent", 0),
        failed=doc.get("failed", 0),
        skipped_suppressed=doc.get("skipped_suppressed", 0),
        template_name=doc.get("template_name"),
        initiated_by=doc.get("initiated_by"),
        started_at=doc.get("started_at"),
        completed_at=doc.get("completed_at"),
        error_detail=doc.get("error_detail"),
    )


@router.get(
    "/bulk-send/jobs",
    summary="List Recent Bulk Jobs",
    description="Returns the 20 most recent bulk send jobs ordered by start time (newest first).",
)
def list_bulk_jobs(limit: int = 20, skip: int = 0):
    """Lists recent bulk send jobs from MongoDB."""
    from app.utils.mongo_client import mongo_client

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    jobs_coll = mongo_client.get_collection("bulk_send_jobs")
    if jobs_coll is None:
        return []

    docs = list(
        jobs_coll.find({}, {"_id": 0})
        .sort("started_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return docs
