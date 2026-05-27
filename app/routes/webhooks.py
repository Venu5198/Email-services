import logging
from typing import List, Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, status, HTTPException, Header
from pydantic import BaseModel, Field

logger = logging.getLogger("email_service")
router = APIRouter(prefix="/api/v1/webhooks", tags=["Bounce Webhooks"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SendGridEvent(BaseModel):
    """Single event object in a SendGrid Event Webhook payload."""
    email: str = Field(..., description="Recipient email address.")
    event: str = Field(..., description="Event type: bounce, blocked, unsubscribe, spam_report, etc.")
    timestamp: Optional[int] = Field(default=None, description="Unix epoch timestamp.")
    reason: Optional[str] = Field(default=None, description="Bounce reason or SMTP error.")
    type: Optional[str] = Field(default=None, description="Bounce type: bounce, blocked.")
    sg_message_id: Optional[str] = Field(default=None)


class SESBounceRecipient(BaseModel):
    emailAddress: str
    action: Optional[str] = None
    status: Optional[str] = None
    diagnosticCode: Optional[str] = None


class SESBounce(BaseModel):
    bounceType: str  # Permanent | Transient
    bounceSubType: str
    bouncedRecipients: List[SESBounceRecipient]
    timestamp: Optional[str] = None


class SESComplaintRecipient(BaseModel):
    emailAddress: str


class SESComplaint(BaseModel):
    complainedRecipients: List[SESComplaintRecipient]
    complaintFeedbackType: Optional[str] = None
    timestamp: Optional[str] = None


class SESNotification(BaseModel):
    """AWS SES SNS notification wrapper."""
    notificationType: str  # Bounce | Complaint | Delivery
    bounce: Optional[SESBounce] = None
    complaint: Optional[SESComplaint] = None


# ---------------------------------------------------------------------------
# SendGrid Webhook
# ---------------------------------------------------------------------------

@router.post(
    "/sendgrid",
    status_code=status.HTTP_200_OK,
    summary="SendGrid Event Webhook",
    description=(
        "Receives SendGrid Event Webhook notifications. "
        "Handles: bounce, blocked, unsubscribe, spam_report. "
        "Hard bounces and spam complaints are automatically added to the suppression list."
    ),
)
async def sendgrid_webhook(request: Request):
    """
    Processes SendGrid bounce and complaint events.
    No API key required — URL is registered in SendGrid dashboard.
    """
    try:
        payload: List[Any] = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload from SendGrid."
        )

    if not isinstance(payload, list):
        payload = [payload]

    processed = 0
    suppressed = 0

    for raw_event in payload:
        try:
            event = SendGridEvent(**raw_event)
        except Exception as e:
            logger.warning(f"SendGrid webhook: could not parse event — {e}")
            continue

        processed += 1
        action = _handle_sendgrid_event(event)
        if action == "suppressed":
            suppressed += 1

    logger.info(f"SendGrid webhook: processed {processed} events, suppressed {suppressed} emails.")
    return {"status": "ok", "processed": processed, "suppressed": suppressed}


def _handle_sendgrid_event(event: SendGridEvent) -> str:
    """Applies suppression logic based on SendGrid event type."""
    email = event.email
    ev_type = event.event.lower()

    if ev_type in ("bounce", "blocked"):
        reason = f"bounce:{event.reason or event.type or 'unknown'}"
        _suppress(email, reason, "bounce")
        logger.info(f"Webhook[SendGrid]: {email} bounced — suppressed. reason={event.reason}")
        _log_event(email, ev_type, event.reason)
        return "suppressed"

    elif ev_type == "spam_report":
        _suppress(email, "spam_complaint", "spam_complaint")
        logger.info(f"Webhook[SendGrid]: {email} marked as spam — suppressed.")
        _log_event(email, "spam_report", None)
        return "suppressed"

    elif ev_type == "unsubscribe":
        _suppress(email, "unsubscribed", "unsubscribed")
        logger.info(f"Webhook[SendGrid]: {email} unsubscribed via SendGrid — suppressed.")
        _log_event(email, "unsubscribe", None)
        return "suppressed"

    else:
        # delivery, open, click — just log
        _log_event(email, ev_type, None)
        return "logged"


# ---------------------------------------------------------------------------
# AWS SES Webhook (via SNS)
# ---------------------------------------------------------------------------

@router.post(
    "/ses",
    status_code=status.HTTP_200_OK,
    summary="AWS SES / SNS Bounce Notification",
    description=(
        "Receives AWS SES bounce and complaint notifications via Amazon SNS. "
        "Permanent bounces and spam complaints are automatically suppressed."
    ),
)
async def ses_webhook(request: Request):
    """
    Processes AWS SES bounce/complaint SNS notifications.
    SNS sends a JSON body with a `Message` field containing the SES notification.
    """
    import json

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON from SNS."
        )

    # SNS wraps the actual message in a JSON-string `Message` field
    message_str = body.get("Message", "{}")
    try:
        notification_dict = json.loads(message_str) if isinstance(message_str, str) else message_str
    except Exception:
        notification_dict = {}

    notification_type = notification_dict.get("notificationType", "")
    suppressed = 0

    if notification_type == "Bounce":
        bounce = notification_dict.get("bounce", {})
        bounce_type = bounce.get("bounceType", "")
        recipients = bounce.get("bouncedRecipients", [])

        for r in recipients:
            email = r.get("emailAddress", "")
            if not email:
                continue
            if bounce_type == "Permanent":
                _suppress(email, f"ses_hard_bounce:{bounce.get('bounceSubType','')}", "bounce")
                logger.info(f"Webhook[SES]: {email} permanent bounce — suppressed.")
                suppressed += 1
            else:
                # Transient — log but don't suppress
                logger.info(f"Webhook[SES]: {email} transient bounce — logged only.")
            _log_event(email, f"ses_{bounce_type.lower()}_bounce", bounce.get("bounceSubType"))

    elif notification_type == "Complaint":
        recipients = notification_dict.get("complaint", {}).get("complainedRecipients", [])
        for r in recipients:
            email = r.get("emailAddress", "")
            if email:
                _suppress(email, "ses_spam_complaint", "spam_complaint")
                logger.info(f"Webhook[SES]: {email} spam complaint — suppressed.")
                suppressed += 1
                _log_event(email, "ses_complaint", None)

    logger.info(f"SES webhook: type={notification_type}, suppressed={suppressed}")
    return {"status": "ok", "notification_type": notification_type, "suppressed": suppressed}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _suppress(email: str, reason: str, category: str) -> None:
    """Adds an email to the suppressions collection."""
    try:
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            return
        coll = mongo_client.get_collection("suppressions")
        if coll is None:
            return
        coll.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "reason": reason,
                "category": category,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"Webhook: failed to suppress {email} — {e}")


def _log_event(email: str, event_type: str, detail: Optional[str]) -> None:
    """Logs a webhook event to the email_events collection."""
    try:
        import uuid
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            return
        coll = mongo_client.get_collection("email_events")
        if coll is None:
            return
        coll.insert_one({
            "event_id": str(uuid.uuid4()),
            "email": email,
            "event_type": f"webhook_{event_type}",
            "detail": detail,
            "occurred_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.warning(f"Webhook: failed to log event for {email} — {e}")
