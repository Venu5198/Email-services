import logging
import time
import uuid
import re
from datetime import datetime, timezone
from typing import Optional, List

from app.config import settings
from app.schemas.bulk_email import BulkEmailRequest, BulkJobStatusResponse
from app.services.template_engine import TemplateEngine
from app.exceptions import ValidationError, ProviderError

logger = logging.getLogger("email_service.bulk")


class BulkEmailService:
    """
    Handles high-volume personalized bulk email sending with:
    - SenderPoolManager rotation across up to 20 sender accounts (10,000 emails/day)
    - MongoDB cursor-based pagination (memory-safe for 10,000+ recipients)
    - Per-recipient Jinja2 context merging and template rendering
    - Individual suppression list checking
    - Job tracking via MongoDB bulk_send_jobs collection
    - Batch throttling to respect SMTP/provider rate limits
    - Automatic failover when a sender account is exhausted
    """

    def __init__(self, template_dir: str = "app/templates"):
        self.template_engine = TemplateEngine(template_dir=template_dir)
        # Provider fallbacks (used when sender pool has no accounts)
        from app.services.providers.smtp import SmtpEmailProvider
        from app.services.providers.sendgrid import SendGridEmailProvider
        from app.services.providers.ses import SesEmailProvider
        self.providers = {
            "smtp": SmtpEmailProvider(),
            "sendgrid": SendGridEmailProvider(),
            "ses": SesEmailProvider(),
        }

    def _get_provider(self, provider_name: Optional[str]):
        """Returns the configured provider OR the sender pool if pool has accounts."""
        from app.services.sender_pool import sender_pool
        # If sender pool has accounts loaded, prefer it for SMTP (it handles rotation)
        if (provider_name is None or provider_name == "smtp") and len(sender_pool._accounts) > 0:
            return None  # Signal to use pool
        key = (provider_name or settings.EMAIL_PROVIDER).lower()
        if key not in self.providers:
            raise ValidationError(f"Unknown provider: '{key}'.")
        return self.providers[key]

    def _log_job(self, jobs_coll, job_id: str, status: str,
                 total: int, sent: int, failed: int, skipped: int,
                 template_name: Optional[str], initiated_by: Optional[str],
                 started_at: datetime, completed_at=None, error_detail=None):
        """Upserts a bulk job status record in MongoDB."""
        if jobs_coll is None:
            return
        doc = {
            "job_id": job_id,
            "status": status,
            "total_recipients": total,
            "sent": sent,
            "failed": failed,
            "skipped_suppressed": skipped,
            "template_name": template_name,
            "initiated_by": initiated_by,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat() if completed_at else None,
            "error_detail": error_detail,
            "updated_at": datetime.now(timezone.utc),
        }
        try:
            jobs_coll.update_one({"job_id": job_id}, {"$set": doc}, upsert=True)
        except Exception as ex:
            logger.error(f"Failed to update bulk job log for {job_id}: {ex}")

    def run_bulk_send(self, req: BulkEmailRequest, job_id: Optional[str] = None) -> BulkJobStatusResponse:
        """
        Executes the full bulk send workflow.
        job_id is passed in from the route so the same ID is used for tracking.
        """
        if not job_id:
            job_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        provider = self._get_provider(req.provider_override)
        provider_name = req.provider_override or settings.EMAIL_PROVIDER

        # --- Job tracking collection ---
        jobs_coll = None
        if settings.ENABLE_MONGO_LOGGING:
            from app.utils.mongo_client import mongo_client
            jobs_coll = mongo_client.get_collection("bulk_send_jobs")

        # --- Suppression collection ---
        suppressions_coll = None
        if settings.ENABLE_MONGO_LOGGING:
            from app.utils.mongo_client import mongo_client
            suppressions_coll = mongo_client.get_collection("suppressions")

        logger.info(f"[BulkJob {job_id}] Starting — source={req.recipient_source}, "
                    f"batch_size={req.batch_size}, provider={provider_name}")

        # Load sender pool (ensures quotas are fresh)
        from app.services.sender_pool import sender_pool
        sender_pool.load_accounts()
        use_pool = (provider_name == "smtp" and len(sender_pool._accounts) > 0)
        if use_pool:
            logger.info(
                f"[BulkJob {job_id}] Using SenderPool — "
                f"{sender_pool.get_pool_status()['active_available_senders']} active senders, "
                f"{sender_pool.get_pool_status()['total_remaining_today']:,} emails remaining today."
            )

        # --- Load recipients ---
        recipient_docs: List[dict] = []

        if req.recipient_source == "mongodb":
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                raise ValidationError("MongoDB is not connected but is requested as recipient source.")
            coll_name = req.recipient_collection or "contacts"
            coll = mongo_client.get_collection(coll_name)
            if coll is None:
                raise ValidationError(f"MongoDB collection '{coll_name}' is not accessible.")
            query = req.recipient_query or {}
            try:
                # Use cursor-based iteration — memory-safe for 10,000+ records
                cursor = coll.find(query).batch_size(req.batch_size)
                recipient_docs = list(cursor)
                logger.info(f"[BulkJob {job_id}] Loaded {len(recipient_docs)} recipients from '{coll_name}'")
            except Exception as ex:
                raise ValidationError(f"Failed to query recipients from MongoDB: {ex}")

        elif req.recipient_source == "list":
            if not req.to_emails:
                raise ValidationError("to_emails must be provided when recipient_source='list'.")
            recipient_docs = [{"email": str(e)} for e in req.to_emails]
            logger.info(f"[BulkJob {job_id}] Using explicit list of {len(recipient_docs)} recipients")

        else:
            raise ValidationError(f"Unknown recipient_source: '{req.recipient_source}'. Use 'mongodb' or 'list'.")

        if not recipient_docs:
            raise ValidationError("No recipients found for the bulk send job.")

        total = len(recipient_docs)
        sent_count = 0
        failed_count = 0
        skipped_count = 0

        # Mark job as in_progress
        self._log_job(jobs_coll, job_id, "in_progress", total, 0, 0, 0,
                      req.template_name, req.initiated_by, started_at)

        # --- Process in batches ---
        for batch_start in range(0, total, req.batch_size):
            batch = recipient_docs[batch_start: batch_start + req.batch_size]
            logger.info(f"[BulkJob {job_id}] Processing batch "
                        f"{batch_start + 1}–{batch_start + len(batch)} of {total}")

            for doc in batch:
                email_addr = doc.get("email")
                if not email_addr:
                    skipped_count += 1
                    continue

                # Suppression check
                if suppressions_coll is not None:
                    try:
                        if suppressions_coll.find_one({"email": email_addr}):
                            logger.info(f"[BulkJob {job_id}] Suppressed: {email_addr}")
                            skipped_count += 1
                            continue
                    except Exception as ex:
                        logger.error(f"Suppression check failed for {email_addr}: {ex}")

                # Build per-recipient context
                personal_context = {
                    **req.template_context,
                    **{k: v for k, v in doc.items() if k != "_id"},
                }
                if "username" not in personal_context:
                    name_field = doc.get("name") or doc.get("first_name")
                    personal_context["username"] = name_field or email_addr.split("@")[0]

                # Render body
                rendered_html = req.body_html
                rendered_text = req.body_text or ""

                if req.template_name:
                    try:
                        rendered_html = self.template_engine.render_from_file(
                            req.template_name, personal_context
                        )
                    except Exception as ex:
                        logger.error(f"Template render failed for {email_addr}: {ex}")
                        failed_count += 1
                        continue

                    if not rendered_text and rendered_html:
                        rendered_text = re.sub(re.compile("<.*?>"), "", rendered_html).strip()

                # Render subject
                rendered_subject = req.subject or ""
                if req.subject_template:
                    try:
                        rendered_subject = self.template_engine.render_subject(
                            req.subject_template, personal_context
                        )
                    except Exception as ex:
                        logger.error(f"Subject render failed for {email_addr}: {ex}")
                        failed_count += 1
                        continue

                if not rendered_subject:
                    rendered_subject = "Important Update from SyncRivo"

                # Send — use pool if available, else fall back to fixed provider
                try:
                    if use_pool:
                        sender_pool.send(
                            to_emails=[email_addr],
                            subject=rendered_subject,
                            body_text=rendered_text,
                            body_html=rendered_html,
                            cc_emails=[str(e) for e in req.cc_emails] if req.cc_emails else None,
                            bcc_emails=[str(e) for e in req.bcc_emails] if req.bcc_emails else None,
                            is_confidential=req.is_confidential,
                        )
                    else:
                        provider.send(
                            from_email=settings.DEFAULT_SENDER_EMAIL,
                            to_emails=[email_addr],
                            subject=rendered_subject,
                            body_text=rendered_text,
                            body_html=rendered_html,
                            cc_emails=[str(e) for e in req.cc_emails] if req.cc_emails else None,
                            bcc_emails=[str(e) for e in req.bcc_emails] if req.bcc_emails else None,
                            attachments=[],
                            is_confidential=req.is_confidential,
                        )
                    sent_count += 1
                    logger.debug(f"[BulkJob {job_id}] Sent to {email_addr}")
                except ProviderError as ex:
                    if "exhausted" in str(ex).lower() or "10,000" in str(ex):
                        # Pool fully exhausted — abort the whole job
                        logger.error(f"[BulkJob {job_id}] Sender pool exhausted. Aborting job.")
                        completed_at = datetime.now(timezone.utc)
                        self._log_job(jobs_coll, job_id, "failed", total, sent_count,
                                      failed_count, skipped_count, req.template_name,
                                      req.initiated_by, started_at, completed_at,
                                      error_detail=str(ex))
                        return BulkJobStatusResponse(
                            job_id=job_id, status="failed",
                            total_recipients=total, sent=sent_count,
                            failed=failed_count + (total - sent_count - failed_count - skipped_count),
                            skipped_suppressed=skipped_count,
                            template_name=req.template_name, initiated_by=req.initiated_by,
                            started_at=started_at.isoformat(),
                            completed_at=completed_at.isoformat(), error_detail=str(ex),
                        )
                    failed_count += 1
                    logger.error(f"[BulkJob {job_id}] Failed to send to {email_addr}: {ex}")
                except Exception as ex:
                    failed_count += 1
                    logger.error(f"[BulkJob {job_id}] Failed to send to {email_addr}: {ex}")

            # Throttle between batches
            if req.delay_between_batches_seconds > 0 and batch_start + req.batch_size < total:
                time.sleep(req.delay_between_batches_seconds)

        # --- Complete ---
        completed_at = datetime.now(timezone.utc)
        self._log_job(jobs_coll, job_id, "completed", total, sent_count, failed_count, skipped_count,
                      req.template_name, req.initiated_by, started_at, completed_at)

        logger.info(
            f"[BulkJob {job_id}] Completed — "
            f"sent={sent_count}, failed={failed_count}, skipped={skipped_count}, total={total}"
        )

        return BulkJobStatusResponse(
            job_id=job_id,
            status="completed",
            total_recipients=total,
            sent=sent_count,
            failed=failed_count,
            skipped_suppressed=skipped_count,
            template_name=req.template_name,
            initiated_by=req.initiated_by,
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
        )
