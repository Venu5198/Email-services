import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.base import JobLookupError

from app.config import settings

logger = logging.getLogger("email_service")


class SchedulerService:
    """
    Manages scheduled and recurring email jobs using APScheduler.

    Supports two modes:
    - One-time: send at a specific UTC datetime (send_at)
    - Recurring: send on a cron schedule (cron_expression)

    All job metadata is persisted in MongoDB `scheduled_jobs` collection
    so that pending jobs survive service restarts.
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler(timezone=settings.SCHEDULER_TIMEZONE)
        self._started = False

    def start(self):
        """Starts the scheduler and re-queues all pending jobs from MongoDB."""
        if self._started:
            return
        self._scheduler.start()
        self._started = True
        logger.info("SchedulerService: APScheduler started.")
        self._restore_pending_jobs()

    def stop(self):
        """Gracefully shuts down the scheduler."""
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("SchedulerService: APScheduler stopped.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def schedule_job(
        self,
        email_request_dict: Dict[str, Any],
        send_at: Optional[datetime] = None,
        cron_expression: Optional[str] = None,
        job_name: Optional[str] = None,
        max_runs: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Schedules an email job. One of send_at or cron_expression must be provided.

        Returns a job metadata dict including job_id and next_run_at.
        """
        if not send_at and not cron_expression:
            raise ValueError("Either send_at or cron_expression must be provided.")

        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Persist to MongoDB immediately
        doc = {
            "job_id": job_id,
            "job_name": job_name or f"email_job_{job_id[:8]}",
            "send_at": send_at.isoformat() if send_at else None,
            "cron_expression": cron_expression,
            "max_runs": max_runs,
            "run_count": 0,
            "status": "pending",
            "email_request": email_request_dict,
            "created_at": now.isoformat(),
            "last_run_at": None,
            "next_run_at": None,
        }
        self._save_job(doc)

        # Add to APScheduler
        apscheduler_job = self._add_apscheduler_job(
            job_id=job_id,
            email_request_dict=email_request_dict,
            send_at=send_at,
            cron_expression=cron_expression,
        )

        next_run = None
        if apscheduler_job and apscheduler_job.next_run_time:
            next_run = apscheduler_job.next_run_time.isoformat()
            self._update_job(job_id, {"next_run_at": next_run})

        logger.info(f"SchedulerService: job '{job_id}' scheduled. next_run={next_run}")
        doc["next_run_at"] = next_run
        return doc

    def cancel_job(self, job_id: str) -> bool:
        """Cancels a scheduled job by its job_id. Returns True if found and cancelled."""
        try:
            self._scheduler.remove_job(job_id)
        except JobLookupError:
            pass  # May already have run or been removed

        updated = self._update_job(job_id, {"status": "cancelled"})
        if updated:
            logger.info(f"SchedulerService: job '{job_id}' cancelled.")
        return updated

    def list_jobs(self, status_filter: Optional[str] = None) -> List[Dict]:
        """Returns all jobs from MongoDB, optionally filtered by status."""
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            return []
        coll = mongo_client.get_collection("scheduled_jobs")
        if coll is None:
            return []
        query = {}
        if status_filter:
            query["status"] = status_filter
        docs = list(coll.find(query, {"_id": 0}).sort("created_at", -1).limit(100))
        return docs

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Returns a single job document by job_id."""
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            return None
        coll = mongo_client.get_collection("scheduled_jobs")
        if coll is None:
            return None
        return coll.find_one({"job_id": job_id}, {"_id": 0})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_apscheduler_job(
        self,
        job_id: str,
        email_request_dict: Dict[str, Any],
        send_at: Optional[datetime],
        cron_expression: Optional[str],
    ):
        """Registers the job with APScheduler using the appropriate trigger."""
        try:
            if send_at:
                trigger = DateTrigger(run_date=send_at)
            else:
                parts = cron_expression.split()
                if len(parts) != 5:
                    raise ValueError(f"Invalid cron expression '{cron_expression}' — must have 5 fields.")
                minute, hour, day, month, day_of_week = parts
                trigger = CronTrigger(
                    minute=minute, hour=hour, day=day,
                    month=month, day_of_week=day_of_week,
                    timezone=settings.SCHEDULER_TIMEZONE,
                )

            job = self._scheduler.add_job(
                func=self._execute_job,
                trigger=trigger,
                id=job_id,
                kwargs={"job_id": job_id, "email_request_dict": email_request_dict},
                replace_existing=True,
                misfire_grace_time=300,  # 5 min grace for misfires
            )
            return job
        except Exception as e:
            logger.error(f"SchedulerService: failed to add APScheduler job '{job_id}': {e}")
            self._update_job(job_id, {"status": "failed", "error": str(e)})
            return None

    def _execute_job(self, job_id: str, email_request_dict: Dict[str, Any]):
        """
        Callback invoked by APScheduler when a job fires.
        Builds an EmailRequest and calls EmailService.send_email().
        """
        logger.info(f"SchedulerService: executing job '{job_id}'.")
        try:
            from app.schemas.email import EmailRequest
            from app.services.email_service import EmailService

            request = EmailRequest(**email_request_dict)
            svc = EmailService()
            svc.send_email(request)

            self._update_job(job_id, {
                "status": "sent",
                "last_run_at": datetime.now(timezone.utc).isoformat(),
                "$inc": {"run_count": 1},
            })
            logger.info(f"SchedulerService: job '{job_id}' completed successfully.")
        except Exception as e:
            logger.error(f"SchedulerService: job '{job_id}' failed — {e}")
            self._update_job(job_id, {
                "status": "failed",
                "error": str(e),
                "last_run_at": datetime.now(timezone.utc).isoformat(),
            })

    def _restore_pending_jobs(self):
        """
        On service startup, re-queues all 'pending' jobs from MongoDB into APScheduler.
        One-time jobs that are in the past are skipped (marked as missed).
        """
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return
            coll = mongo_client.get_collection("scheduled_jobs")
            if coll is None:
                return

            now = datetime.now(timezone.utc)
            pending = list(coll.find({"status": "pending"}, {"_id": 0}))
            restored = 0

            for job in pending:
                job_id = job["job_id"]
                email_request_dict = job.get("email_request", {})
                send_at_str = job.get("send_at")
                cron_expr = job.get("cron_expression")

                send_at = None
                if send_at_str:
                    send_at = datetime.fromisoformat(send_at_str)
                    if send_at.tzinfo is None:
                        send_at = send_at.replace(tzinfo=timezone.utc)
                    if send_at < now:
                        # One-time job in the past — mark missed
                        self._update_job(job_id, {"status": "missed"})
                        logger.warning(f"SchedulerService: one-time job '{job_id}' was missed (scheduled for {send_at_str}).")
                        continue

                self._add_apscheduler_job(
                    job_id=job_id,
                    email_request_dict=email_request_dict,
                    send_at=send_at,
                    cron_expression=cron_expr,
                )
                restored += 1

            logger.info(f"SchedulerService: restored {restored} pending jobs on startup.")
        except Exception as e:
            logger.error(f"SchedulerService: failed to restore pending jobs — {e}")

    def _save_job(self, doc: Dict) -> None:
        """Saves a new job document to MongoDB."""
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return
            coll = mongo_client.get_collection("scheduled_jobs")
            if coll is not None:
                coll.insert_one({**doc})
        except Exception as e:
            logger.error(f"SchedulerService: failed to save job to MongoDB — {e}")

    def _update_job(self, job_id: str, updates: Dict) -> bool:
        """Updates an existing job document in MongoDB."""
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return False
            coll = mongo_client.get_collection("scheduled_jobs")
            if coll is None:
                return False

            # Separate $inc operations from $set operations
            inc_ops = updates.pop("$inc", None)
            set_ops = {k: v for k, v in updates.items()}

            mongo_update: Dict = {}
            if set_ops:
                mongo_update["$set"] = set_ops
            if inc_ops:
                mongo_update["$inc"] = inc_ops

            result = coll.update_one({"job_id": job_id}, mongo_update)
            return result.matched_count > 0
        except Exception as e:
            logger.error(f"SchedulerService: failed to update job '{job_id}' — {e}")
            return False


# Module-level singleton
scheduler_service = SchedulerService()
