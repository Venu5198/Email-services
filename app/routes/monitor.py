import logging
from typing import Optional, List
from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("email_service")
router = APIRouter(prefix="/api/v1/inbox-monitor", tags=["Inbox Monitor"])


# -----------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------

class InboxRuleCreate(BaseModel):
    """Schema for creating or updating an inbox triage rule."""
    rule_name: str = Field(..., description="Unique name for this rule.")
    keywords: List[str] = Field(
        ...,
        description="List of keywords to match in subject + body. Case-insensitive."
    )
    from_domain_filter: Optional[str] = Field(
        default=None,
        description="Optional sender domain filter (e.g. 'gmail.com'). Null = match all senders."
    )
    severity: str = Field(
        default="medium",
        description="Severity level: critical, high, medium, low."
    )
    notify_channels: List[str] = Field(
        default=["slack"],
        description="Channels to notify on match. Supported: 'slack'."
    )
    auto_reply_template: Optional[str] = Field(
        default=None,
        description="Template filename to auto-reply with (e.g. 'support_acknowledgment.html')."
    )
    notify_emails: Optional[List[str]] = Field(
        default=None,
        description="Internal emails to also notify when this rule fires."
    )
    is_active: bool = Field(default=True, description="Whether this rule is currently active.")


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@router.get(
    "/status",
    summary="Inbox Monitor Status",
    description="Returns whether the inbox polling monitor is running and its configuration.",
)
def get_monitor_status():
    """Returns the current state of the inbox monitor."""
    from app.services.inbox_monitor import inbox_monitor
    from app.config import settings

    imap_user = getattr(settings, "IMAP_USERNAME", None)
    slack_url = getattr(settings, "SLACK_WEBHOOK_URL", None)

    return {
        "is_running": inbox_monitor._running,
        "poll_interval_seconds": inbox_monitor.poll_interval,
        "monitoring_inbox": imap_user or "not configured",
        "slack_configured": bool(slack_url),
        "whatsapp_configured": False,
    }


@router.post(
    "/rules",
    status_code=status.HTTP_201_CREATED,
    summary="Create Inbox Triage Rule",
    description="Creates or updates a keyword triage rule used by the inbox monitor.",
)
def create_inbox_rule(rule: InboxRuleCreate):
    """Creates or updates an inbox triage rule in MongoDB."""
    from app.utils.mongo_client import mongo_client

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("inbox_rules")
    if coll is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="inbox_rules collection is unavailable."
        )

    doc = rule.model_dump()
    coll.update_one(
        {"rule_name": rule.rule_name},
        {"$set": doc},
        upsert=True
    )
    return {"message": f"Inbox rule '{rule.rule_name}' saved successfully."}


@router.get(
    "/rules",
    summary="List Inbox Triage Rules",
    description="Returns all configured inbox triage rules.",
)
def list_inbox_rules(active_only: bool = False):
    """Lists all inbox triage rules from MongoDB."""
    from app.utils.mongo_client import mongo_client

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("inbox_rules")
    if coll is None:
        return []

    query = {"is_active": True} if active_only else {}
    docs = list(coll.find(query, {"_id": 0}))
    return docs


@router.put(
    "/rules/{rule_name}",
    summary="Update Inbox Triage Rule",
    description="Updates an existing inbox triage rule.",
)
def update_inbox_rule(rule_name: str, rule: InboxRuleCreate):
    """Updates an existing inbox rule."""
    from app.utils.mongo_client import mongo_client

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("inbox_rules")
    result = coll.update_one(
        {"rule_name": rule_name},
        {"$set": rule.model_dump()}
    ) if coll is not None else None

    if not result or result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbox rule '{rule_name}' not found."
        )
    return {"message": f"Inbox rule '{rule_name}' updated successfully."}


@router.delete(
    "/rules/{rule_name}",
    summary="Delete Inbox Triage Rule",
    description="Permanently deletes an inbox triage rule.",
)
def delete_inbox_rule(rule_name: str):
    """Deletes an inbox triage rule."""
    from app.utils.mongo_client import mongo_client

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("inbox_rules")
    result = coll.delete_one({"rule_name": rule_name}) if coll is not None else None
    if not result or result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inbox rule '{rule_name}' not found."
        )
    return {"message": f"Inbox rule '{rule_name}' deleted successfully."}


@router.get(
    "/matches",
    summary="Recent Inbox Matches",
    description="Returns the most recent emails that matched a triage rule.",
)
def list_inbox_matches(limit: int = 50, skip: int = 0):
    """Lists recent inbox match events from MongoDB."""
    from app.utils.mongo_client import mongo_client

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("inbox_matches")
    if coll is None:
        return []

    docs = list(
        coll.find({}, {"_id": 0})
        .sort("matched_at", -1)
        .skip(skip)
        .limit(limit)
    )
    # Convert datetime to string for JSON serialization
    for doc in docs:
        if "matched_at" in doc and hasattr(doc["matched_at"], "isoformat"):
            doc["matched_at"] = doc["matched_at"].isoformat()
    return docs


@router.post(
    "/test-slack",
    status_code=status.HTTP_200_OK,
    summary="Test Slack Notification",
    description=(
        "Sends a test Slack alert directly using the configured SLACK_WEBHOOK_URL. "
        "Use this to verify your Slack integration is working without needing to wait "
        "for an actual IMAP email. Returns success/failure and the webhook response."
    ),
)
def test_slack_notification(
    severity: str = "medium",
    title: str = "SyncRivo Email Service — Test Alert",
    message: str = "This is a manual test notification from the inbox monitor.",
):
    """
    Manually fires a Slack notification to verify the webhook is working.
    Useful for testing without waiting for an IMAP poll cycle.
    """
    from app.config import settings
    from app.services.notifiers.slack_notifier import SlackNotifier

    if not settings.SLACK_WEBHOOK_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SLACK_WEBHOOK_URL is not configured in .env."
        )

    notifier = SlackNotifier(webhook_url=settings.SLACK_WEBHOOK_URL)
    success = notifier.send_alert(
        title=title,
        body=message,
        severity=severity,
        fields=[
            {"title": "Source", "value": "Manual Test — Swagger UI"},
            {"title": "Severity", "value": severity.upper()},
        ],
    )

    if success:
        logger.info(f"Manual Slack test alert sent. severity={severity}")
        return {
            "success": True,
            "message": "Slack notification sent successfully. Check your Slack channel.",
            "webhook_url_prefix": settings.SLACK_WEBHOOK_URL[:40] + "...",
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Slack webhook request failed. Check logs for details and verify the webhook URL is valid.",
        )

