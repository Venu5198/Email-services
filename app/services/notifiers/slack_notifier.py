import logging
import json
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("email_service.slack")


class SlackNotifier:
    """
    Sends alert notifications to a Slack channel via an Incoming Webhook URL.
    
    Setup:
        1. Go to https://api.slack.com/apps → Create App → Incoming Webhooks
        2. Enable Incoming Webhooks and copy the Webhook URL
        3. Set SLACK_WEBHOOK_URL in your .env file
    
    No external dependencies required — uses Python's built-in urllib.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    def _is_configured(self) -> bool:
        return bool(self.webhook_url)

    def send_alert(
        self,
        title: str,
        body: str,
        severity: str = "medium",
        fields: Optional[list] = None,
        color: Optional[str] = None,
    ) -> bool:
        """
        Sends a formatted alert message to Slack.

        Args:
            title: Bold alert title shown at the top.
            body: Main message body text.
            severity: 'critical', 'high', 'medium', or 'low'.
            fields: Optional list of {"title": ..., "value": ...} dicts for sidebar details.
            color: Override sidebar color (hex). Auto-selected from severity if not provided.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._is_configured():
            logger.warning("SlackNotifier: SLACK_WEBHOOK_URL is not configured. Skipping.")
            return False

        # Severity → color and emoji mappings
        severity_map = {
            "critical": {"color": "#dc2626", "emoji": "🚨"},
            "high": {"color": "#f97316", "emoji": "🔴"},
            "medium": {"color": "#f59e0b", "emoji": "🟡"},
            "low": {"color": "#10b981", "emoji": "🟢"},
        }
        meta = severity_map.get(severity.lower(), {"color": "#64748b", "emoji": "⚠️"})
        sidebar_color = color or meta["color"]
        emoji = meta["emoji"]

        # Build Slack message payload using Block Kit
        attachment = {
            "color": sidebar_color,
            "fallback": f"[{severity.upper()}] {title}: {body}",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{emoji} {title}", "emoji": True},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": body},
                },
            ],
        }

        # Add optional detail fields
        if fields:
            field_elements = [
                {
                    "type": "mrkdwn",
                    "text": f"*{f['title']}*\n{f['value']}"
                }
                for f in fields
            ]
            # Slack fields come in pairs
            for i in range(0, len(field_elements), 2):
                chunk = field_elements[i:i + 2]
                attachment["blocks"].append({
                    "type": "section",
                    "fields": chunk,
                })

        payload = json.dumps({"attachments": [attachment]}).encode("utf-8")

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    logger.info(f"Slack alert sent: [{severity.upper()}] {title}")
                    return True
                else:
                    logger.error(f"Slack webhook returned status {resp.status}")
                    return False
        except urllib.error.URLError as ex:
            logger.error(f"Slack webhook request failed: {ex}")
            return False
        except Exception as ex:
            logger.error(f"Unexpected error sending Slack alert: {ex}")
            return False

    def send_inbox_alert(
        self,
        sender_email: str,
        subject: str,
        matched_keywords: list,
        severity: str,
        rule_name: str,
        auto_replied: bool = False,
    ) -> bool:
        """
        Specialized alert for inbox monitor keyword matches.
        Sends a pre-formatted Slack message with email details.
        """
        emoji = {"critical": "🚨", "high": "🔴", "medium": "🟡", "low": "🟢"}.get(
            severity.lower(), "⚠️"
        )
        title = f"Inbox Alert — {severity.upper()} Priority"
        body = (
            f"An incoming email matched the rule *{rule_name}*.\n"
            f"*From:* {sender_email}\n"
            f"*Subject:* {subject}\n"
            f"*Matched Keywords:* `{'`, `'.join(matched_keywords)}`"
        )
        if auto_replied:
            body += "\n✅ Auto-reply has been sent to the sender."

        return self.send_alert(
            title=title,
            body=body,
            severity=severity,
            fields=[
                {"title": "From", "value": sender_email},
                {"title": "Rule", "value": rule_name},
            ],
        )
