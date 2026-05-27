import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("email_service")


class AnalyticsService:
    """
    Provides email analytics by aggregating data from MongoDB collections:
    - email_logs         → sent/failed counts, provider breakdown
    - email_events       → open/click events per email_id
    - bulk_send_jobs     → campaign-level stats
    - sender_accounts    → per-account quota usage
    """

    # ------------------------------------------------------------------
    # Overall Summary
    # ------------------------------------------------------------------

    def get_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Returns aggregated email stats for the last N days.
        Covers: sent, failed, opened, clicked, bounced, unsubscribed + rates.
        """
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            return self._empty_summary(days)

        logs = mongo_client.get_collection("email_logs")
        events = mongo_client.get_collection("email_events")
        suppressions = mongo_client.get_collection("suppressions")

        since = self._days_ago(days)

        # Total sent / failed from email_logs
        total_sent = 0
        total_failed = 0
        if logs is not None:
            total_sent = logs.count_documents({"status": "sent", "created_at": {"$gte": since}})
            total_failed = logs.count_documents({"status": "failed", "created_at": {"$gte": since}})

        # Opens and clicks from email_events
        total_opens = 0
        unique_opens = 0
        total_clicks = 0
        unique_clicks = 0
        if events is not None:
            total_opens = events.count_documents({"event_type": "open", "occurred_at": {"$gte": since}})
            unique_opens = len(events.distinct("email_id", {"event_type": "open", "occurred_at": {"$gte": since}}))
            total_clicks = events.count_documents({"event_type": "click", "occurred_at": {"$gte": since}})
            unique_clicks = len(events.distinct("email_id", {"event_type": "click", "occurred_at": {"$gte": since}}))

        # Bounces
        total_bounces = 0
        total_spam = 0
        total_unsubscribed = 0
        if suppressions is not None:
            total_bounces = suppressions.count_documents({"reason": "bounce"})
            total_spam = suppressions.count_documents({"reason": "spam_complaint"})
            total_unsubscribed = suppressions.count_documents({"reason": "unsubscribed"})

        # Compute rates
        delivered = total_sent
        open_rate = round((unique_opens / delivered * 100), 2) if delivered > 0 else 0.0
        click_rate = round((unique_clicks / delivered * 100), 2) if delivered > 0 else 0.0

        return {
            "period_days": days,
            "since": since.isoformat(),
            "emails_sent": total_sent,
            "emails_failed": total_failed,
            "total_opens": total_opens,
            "unique_opens": unique_opens,
            "total_clicks": total_clicks,
            "unique_clicks": unique_clicks,
            "open_rate_pct": open_rate,
            "click_rate_pct": click_rate,
            "bounces": total_bounces,
            "spam_complaints": total_spam,
            "unsubscribes": total_unsubscribed,
        }

    # ------------------------------------------------------------------
    # Campaign Analytics
    # ------------------------------------------------------------------

    def get_campaign_analytics(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns open/click analytics for a specific bulk send job.
        Correlates bulk_send_jobs → email_logs → email_events by job_id.
        """
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            return None

        jobs_coll = mongo_client.get_collection("bulk_send_jobs")
        logs_coll = mongo_client.get_collection("email_logs")
        events_coll = mongo_client.get_collection("email_events")

        # Fetch the job
        job = None
        if jobs_coll is not None:
            job = jobs_coll.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            return None

        # Find all email_ids sent under this job
        email_ids = []
        if logs_coll is not None:
            docs = list(logs_coll.find({"job_id": job_id}, {"email_id": 1, "_id": 0}))
            email_ids = [d["email_id"] for d in docs if "email_id" in d]

        opens = 0
        clicks = 0
        unique_openers = 0
        unique_clickers = 0
        top_urls: List[Dict] = []

        if events_coll is not None and email_ids:
            opens = events_coll.count_documents({"event_type": "open", "email_id": {"$in": email_ids}})
            clicks = events_coll.count_documents({"event_type": "click", "email_id": {"$in": email_ids}})
            unique_openers = len(events_coll.distinct("email_id", {"event_type": "open", "email_id": {"$in": email_ids}}))
            unique_clickers = len(events_coll.distinct("email_id", {"event_type": "click", "email_id": {"$in": email_ids}}))

            # Top clicked URLs via aggregation
            pipeline = [
                {"$match": {"event_type": "click", "email_id": {"$in": email_ids}}},
                {"$group": {"_id": "$url", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]
            top_urls = [{"url": d["_id"], "clicks": d["count"]} for d in events_coll.aggregate(pipeline)]

        sent = job.get("sent", 0)
        open_rate = round((unique_openers / sent * 100), 2) if sent > 0 else 0.0
        click_rate = round((unique_clickers / sent * 100), 2) if sent > 0 else 0.0

        return {
            "job_id": job_id,
            "job_status": job.get("status"),
            "template_name": job.get("template_name"),
            "initiated_by": job.get("initiated_by"),
            "total_recipients": job.get("total_recipients", 0),
            "sent": sent,
            "failed": job.get("failed", 0),
            "skipped_suppressed": job.get("skipped_suppressed", 0),
            "opens": opens,
            "clicks": clicks,
            "unique_openers": unique_openers,
            "unique_clickers": unique_clickers,
            "open_rate_pct": open_rate,
            "click_rate_pct": click_rate,
            "top_clicked_urls": top_urls,
        }

    # ------------------------------------------------------------------
    # Top Clicked URLs (global)
    # ------------------------------------------------------------------

    def get_top_clicked_urls(self, limit: int = 10, days: int = 30) -> List[Dict]:
        """Returns the top clicked URLs across all emails in the last N days."""
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            return []
        events = mongo_client.get_collection("email_events")
        if events is None:
            return []

        since = self._days_ago(days)
        pipeline = [
            {"$match": {"event_type": "click", "occurred_at": {"$gte": since}}},
            {"$group": {"_id": "$url", "clicks": {"$sum": 1}, "unique_emails": {"$addToSet": "$email_id"}}},
            {"$project": {"url": "$_id", "clicks": 1, "unique_emails": {"$size": "$unique_emails"}, "_id": 0}},
            {"$sort": {"clicks": -1}},
            {"$limit": limit},
        ]
        return list(events.aggregate(pipeline))

    # ------------------------------------------------------------------
    # Sender Pool Stats
    # ------------------------------------------------------------------

    def get_sender_pool_stats(self) -> Dict[str, Any]:
        """Returns quota usage for every registered sender account."""
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            return {"accounts": [], "total_sent_today": 0, "total_remaining_today": 0}

        coll = mongo_client.get_collection("sender_accounts")
        if coll is None:
            return {"accounts": [], "total_sent_today": 0, "total_remaining_today": 0}

        accounts = list(coll.find({}, {"_id": 0, "smtp_password": 0}))
        total_sent = sum(a.get("sent_today", 0) for a in accounts)
        total_limit = sum(a.get("daily_limit", 500) for a in accounts)
        total_remaining = max(0, total_limit - total_sent)

        for a in accounts:
            limit = a.get("daily_limit", 500)
            sent = a.get("sent_today", 0)
            a["remaining_today"] = max(0, limit - sent)
            a["usage_pct"] = round((sent / limit * 100), 1) if limit > 0 else 0.0

        return {
            "accounts": accounts,
            "total_sent_today": total_sent,
            "total_capacity_today": total_limit,
            "total_remaining_today": total_remaining,
            "overall_usage_pct": round((total_sent / total_limit * 100), 1) if total_limit > 0 else 0.0,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _days_ago(self, days: int) -> datetime:
        from datetime import timedelta
        return datetime.now(timezone.utc) - timedelta(days=days)

    def _empty_summary(self, days: int) -> Dict[str, Any]:
        return {
            "period_days": days,
            "since": self._days_ago(days).isoformat(),
            "emails_sent": 0, "emails_failed": 0,
            "total_opens": 0, "unique_opens": 0,
            "total_clicks": 0, "unique_clicks": 0,
            "open_rate_pct": 0.0, "click_rate_pct": 0.0,
            "bounces": 0, "spam_complaints": 0, "unsubscribes": 0,
        }


# Module-level singleton
analytics_service = AnalyticsService()
