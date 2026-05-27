import imaplib
import email
import logging
import asyncio
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from app.config import settings
from app.services.notifiers.slack_notifier import SlackNotifier

logger = logging.getLogger("email_service.inbox_monitor")


class InboxMonitorService:
    """
    Polls a designated email inbox via IMAP at a configurable interval.
    
    On each poll it:
      1. Fetches new/unseen emails from the IMAP inbox.
      2. Matches against keyword triage rules stored in MongoDB.
      3. Sends Slack alerts for matched emails.
      4. Optionally triggers an auto-reply email via the email service.
      5. Marks processed emails as Seen to avoid re-processing.

    Configuration (add to .env):
        IMAP_HOST         = imap.gmail.com
        IMAP_PORT         = 993
        IMAP_USERNAME     = support@syncrivo.ai
        IMAP_PASSWORD     = <app_password>
        SLACK_WEBHOOK_URL = https://hooks.slack.com/services/...
        INBOX_POLL_INTERVAL_SECONDS = 60
    """

    def __init__(self):
        self.slack = SlackNotifier(webhook_url=getattr(settings, "SLACK_WEBHOOK_URL", None))
        self.poll_interval = getattr(settings, "INBOX_POLL_INTERVAL_SECONDS", 60)
        self._running = False

    # -----------------------------------------------------------------------
    # Public lifecycle methods
    # -----------------------------------------------------------------------

    async def start_polling(self):
        """Starts the continuous inbox polling loop (run as asyncio background task)."""
        self._running = True
        logger.info(
            f"InboxMonitor started — polling every {self.poll_interval}s "
            f"on {getattr(settings, 'IMAP_USERNAME', 'not configured')}"
        )
        while self._running:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._poll_once)
            except Exception as ex:
                logger.error(f"InboxMonitor poll error: {ex}")
            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stops the polling loop gracefully."""
        self._running = False
        logger.info("InboxMonitor stopped.")

    # -----------------------------------------------------------------------
    # Core poll cycle
    # -----------------------------------------------------------------------

    def _poll_once(self):
        """Connects to IMAP, fetches unseen emails, and processes each one."""
        imap_host = getattr(settings, "IMAP_HOST", None)
        imap_port = getattr(settings, "IMAP_PORT", 993)
        imap_user = getattr(settings, "IMAP_USERNAME", None)
        imap_pass = getattr(settings, "IMAP_PASSWORD", None)

        if not all([imap_host, imap_user, imap_pass]):
            logger.debug("InboxMonitor: IMAP credentials not configured. Skipping poll.")
            return

        try:
            # Connect via SSL
            mail = imaplib.IMAP4_SSL(imap_host, imap_port)
            mail.login(imap_user, imap_pass)
            mail.select("INBOX")

            # Fetch only UNSEEN messages
            _, msg_ids = mail.search(None, "UNSEEN")
            ids = msg_ids[0].split() if msg_ids[0] else []

            if not ids:
                logger.debug("InboxMonitor: No new emails.")
                mail.logout()
                return

            logger.info(f"InboxMonitor: Found {len(ids)} new email(s).")

            rules = self._load_rules()

            for msg_id in ids:
                try:
                    _, msg_data = mail.fetch(msg_id, "(RFC822)")
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    self._process_email(msg, rules)
                    # Mark as Seen after processing
                    mail.store(msg_id, "+FLAGS", "\\Seen")
                except Exception as ex:
                    logger.error(f"InboxMonitor: Failed to process message {msg_id}: {ex}")

            mail.logout()

        except imaplib.IMAP4.error as ex:
            logger.error(f"InboxMonitor: IMAP error: {ex}")
        except ConnectionRefusedError:
            logger.error("InboxMonitor: Could not connect to IMAP server.")

    # -----------------------------------------------------------------------
    # Per-email processing
    # -----------------------------------------------------------------------

    def _process_email(self, msg, rules: List[Dict]):
        """Checks a single email message against all triage rules."""
        sender = msg.get("From", "")
        subject = msg.get("Subject", "")
        body = self._extract_body(msg)

        full_text = f"{subject} {body}".lower()
        sender_domain = self._extract_domain(sender)

        logger.debug(f"InboxMonitor: Processing email from={sender}, subject={subject!r}")

        for rule in rules:
            keywords: List[str] = rule.get("keywords", [])
            domain_filter: Optional[str] = rule.get("from_domain_filter")
            severity: str = rule.get("severity", "medium")
            rule_name: str = rule.get("rule_name", "unnamed")
            notify_channels: List[str] = rule.get("notify_channels", ["slack"])
            auto_reply_template: Optional[str] = rule.get("auto_reply_template")

            # Domain filter check (optional)
            if domain_filter and domain_filter.lower() not in sender_domain.lower():
                continue

            # Keyword matching
            matched = [kw for kw in keywords if kw.lower() in full_text]
            if not matched:
                continue

            logger.info(
                f"InboxMonitor: Rule '{rule_name}' matched — "
                f"from={sender}, keywords={matched}, severity={severity}"
            )

            auto_replied = False

            # Auto-reply (if configured)
            if auto_reply_template:
                auto_replied = self._send_auto_reply(sender, subject, auto_reply_template, rule)

            # Slack notification
            if "slack" in notify_channels:
                self.slack.send_inbox_alert(
                    sender_email=sender,
                    subject=subject,
                    matched_keywords=matched,
                    severity=severity,
                    rule_name=rule_name,
                    auto_replied=auto_replied,
                )

            # Log the match in MongoDB
            self._log_match(sender, subject, matched, severity, rule_name)

            # Only fire the first matching rule to avoid duplicate alerts
            break

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _load_rules(self) -> List[Dict]:
        """Loads active triage rules from the MongoDB inbox_rules collection."""
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return []
            coll = mongo_client.get_collection("inbox_rules")
            if coll is None:
                return []
            return list(coll.find({"is_active": True}))
        except Exception as ex:
            logger.error(f"Failed to load inbox rules: {ex}")
            return []

    def _extract_body(self, msg) -> str:
        """Extracts plain text body from an email.message.Message object."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode("utf-8", errors="replace")
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
            except Exception:
                pass
        return body

    def _extract_domain(self, from_header: str) -> str:
        """Extracts the domain from a From header like 'Name <user@domain.com>'."""
        match = re.search(r"@([\w.-]+)", from_header)
        return match.group(1) if match else ""

    def _send_auto_reply(self, to_email: str, original_subject: str,
                          template_name: str, rule: Dict) -> bool:
        """Sends an auto-reply to the sender using the email service."""
        try:
            from app.services.email_service import EmailService
            from app.schemas.email import EmailRequest

            svc = EmailService()
            req = EmailRequest(
                to_emails=to_email,
                subject=f"Re: {original_subject}",
                template_name=template_name,
                template_context={
                    "customer_name": "Valued Customer",
                    "ticket_id": f"AUTO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                    "inquiry_type": "support",
                    "priority": rule.get("severity", "medium"),
                    "expected_response_hours": 4,
                    "submitter_email": to_email,
                    "issue_summary": original_subject[:80],
                    "response_sla": "Within 4 hours",
                },
            )
            svc.send_email(req)
            logger.info(f"InboxMonitor: Auto-reply sent to {to_email}")
            return True
        except Exception as ex:
            logger.error(f"InboxMonitor: Auto-reply failed to {to_email}: {ex}")
            return False

    def _log_match(self, sender: str, subject: str, keywords: List[str],
                    severity: str, rule_name: str):
        """Logs the matched email event to MongoDB inbox_matches collection."""
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return
            coll = mongo_client.get_collection("inbox_matches")
            if coll is None:
                return
            coll.insert_one({
                "sender": sender,
                "subject": subject,
                "matched_keywords": keywords,
                "severity": severity,
                "rule_name": rule_name,
                "matched_at": datetime.now(timezone.utc),
            })
        except Exception as ex:
            logger.error(f"Failed to log inbox match: {ex}")


# Global singleton instance
inbox_monitor = InboxMonitorService()
