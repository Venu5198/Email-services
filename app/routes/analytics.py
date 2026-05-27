import logging
from typing import Optional
from fastapi import APIRouter, status, Query

from app.services.analytics_service import analytics_service

logger = logging.getLogger("email_service")
router = APIRouter(prefix="/api/v1/analytics", tags=["Email Analytics"])


@router.get(
    "/summary",
    summary="Email Analytics Summary",
    description=(
        "Returns aggregated email statistics for the last N days: "
        "sent, failed, open rate, click rate, bounces, unsubscribes. "
        "Data is sourced from email_logs, email_events, and suppressions collections."
    ),
)
def get_analytics_summary(
    days: int = Query(default=7, ge=1, le=90, description="Number of past days to include (1–90).")
):
    """Returns overall email performance metrics for the specified time window."""
    return analytics_service.get_summary(days=days)


@router.get(
    "/campaign/{job_id}",
    summary="Campaign Analytics",
    description=(
        "Returns per-campaign open and click analytics for a bulk send job. "
        "Correlates bulk_send_jobs → email_logs → email_events by job_id. "
        "Includes top clicked URLs for this campaign."
    ),
)
def get_campaign_analytics(job_id: str):
    """Returns open/click analytics for a specific bulk send job."""
    result = analytics_service.get_campaign_analytics(job_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bulk job '{job_id}' not found."
        )
    return result


@router.get(
    "/top-clicked",
    summary="Top Clicked URLs",
    description=(
        "Returns the most clicked URLs across all tracked emails in the last N days. "
        "Useful for identifying which CTAs and links get the most engagement."
    ),
)
def get_top_clicked_urls(
    limit: int = Query(default=10, ge=1, le=50, description="Number of top URLs to return."),
    days: int = Query(default=30, ge=1, le=90, description="Number of past days to include."),
):
    """Returns top clicked URLs ranked by click count."""
    return {
        "period_days": days,
        "top_urls": analytics_service.get_top_clicked_urls(limit=limit, days=days)
    }


@router.get(
    "/sender-pool",
    summary="Sender Pool Quota Analytics",
    description=(
        "Returns current quota usage for every registered sender account in the pool. "
        "Shows sent_today, daily_limit, remaining_today, and usage percentage per account."
    ),
)
def get_sender_pool_analytics():
    """Returns quota usage breakdown per sender account."""
    return analytics_service.get_sender_pool_stats()
