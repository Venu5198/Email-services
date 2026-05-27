import uuid
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger("email_service")

# Regex for finding href links in HTML (handles both single and double quotes)
_HREF_RE = re.compile(r'href=["\'](?!mailto:|#|cid:)([^"\']+)["\']', re.IGNORECASE)

# 1×1 transparent GIF in base64 — the tracking pixel image bytes
_TRANSPARENT_GIF = (
    b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff"
    b"\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
)


class TrackingService:
    """
    Injects open-tracking pixels and click-tracking link wrappers into HTML email bodies,
    and records open/click events to MongoDB for analytics.

    Only active when ENABLE_TRACKING=True in settings.
    """

    def generate_email_id(self) -> str:
        """Generates a unique email ID for correlating open/click events."""
        return str(uuid.uuid4())

    def inject_tracking_pixel(self, html: str, email_id: str) -> str:
        """
        Injects a 1×1 transparent GIF tracking pixel just before </body>.
        When an email client loads this image, an open event is recorded.
        """
        if not settings.ENABLE_TRACKING:
            return html

        base = settings.TRACKING_BASE_URL.rstrip("/")
        pixel_url = f"{base}/track/open/{email_id}"
        pixel_tag = (
            f'\n<img src="{pixel_url}" width="1" height="1" '
            f'alt="" style="display:none;border:0;" />'
        )

        if "</body>" in html.lower():
            # Insert before closing body tag (case-insensitive)
            idx = html.lower().rfind("</body>")
            return html[:idx] + pixel_tag + html[idx:]

        # Fallback: append to end of HTML
        return html + pixel_tag

    def wrap_links(self, html: str, email_id: str) -> str:
        """
        Wraps all non-mailto, non-anchor href links through the click tracking endpoint.
        Original URL is passed as a ?url= query parameter and the user is redirected.
        """
        if not settings.ENABLE_TRACKING:
            return html

        base = settings.TRACKING_BASE_URL.rstrip("/")

        def replace_href(match: re.Match) -> str:
            original_url = match.group(1)
            from urllib.parse import quote
            tracked_url = f"{base}/track/click/{email_id}?url={quote(original_url, safe='')}"
            # Preserve quote style from original
            quote_char = match.group(0)[5]  # char after 'href='
            return f"href={quote_char}{tracked_url}{quote_char}"

        return _HREF_RE.sub(replace_href, html)

    def record_open(
        self,
        email_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Records an email open event to MongoDB email_events collection."""
        self._record_event(
            email_id=email_id,
            event_type="open",
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def record_click(
        self,
        email_id: str,
        url: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """Records a link click event to MongoDB email_events collection."""
        self._record_event(
            email_id=email_id,
            event_type="click",
            url=url,
            ip_address=ip_address,
        )

    def _record_event(
        self,
        email_id: str,
        event_type: str,
        url: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Writes an event document to the email_events MongoDB collection."""
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return
            coll = mongo_client.get_collection("email_events")
            if coll is None:
                return

            doc = {
                "event_id": str(uuid.uuid4()),
                "email_id": email_id,
                "event_type": event_type,
                "occurred_at": datetime.now(timezone.utc),
            }
            if url:
                doc["url"] = url
            if ip_address:
                doc["ip_address"] = ip_address
            if user_agent:
                doc["user_agent"] = user_agent

            coll.insert_one(doc)
            logger.debug(f"TrackingService: recorded {event_type} for email_id={email_id}")
        except Exception as e:
            # Never raise — tracking must not break email delivery
            logger.warning(f"TrackingService: failed to record {event_type} event — {e}")

    @staticmethod
    def get_transparent_gif() -> bytes:
        """Returns raw bytes of a 1×1 transparent GIF image."""
        return _TRANSPARENT_GIF


# Module-level singleton
tracking_service = TrackingService()
