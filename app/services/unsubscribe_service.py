import hmac
import hashlib
import base64
import logging
from urllib.parse import quote
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger("email_service")


class UnsubscribeService:
    """
    Handles one-click unsubscribe token generation, verification, and
    automatic suppression list management.

    Token format (URL-safe base64 of: email|timestamp):
        HMAC-SHA256(secret, email|timestamp) + "|" + email + "|" + timestamp

    The token is URL-safe, stateless, and cannot be forged without the secret key.
    """

    def _secret(self) -> bytes:
        return settings.UNSUBSCRIBE_SECRET_KEY.encode("utf-8")

    def generate_token(self, email: str) -> str:
        """
        Generates a signed, URL-safe unsubscribe token for the given email address.
        The token is safe to embed in email footers and List-Unsubscribe headers.
        """
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        payload = f"{email}|{timestamp}"
        sig = hmac.new(self._secret(), payload.encode(), hashlib.sha256).hexdigest()
        raw = f"{sig}|{payload}"
        token = base64.urlsafe_b64encode(raw.encode()).decode()
        logger.debug(f"UnsubscribeService: token generated for {email}")
        return token

    def verify_token(self, token: str) -> str:
        """
        Verifies a signed unsubscribe token and returns the email address if valid.
        Raises ValueError if the token is invalid or tampered with.
        """
        try:
            raw = base64.urlsafe_b64decode(token.encode()).decode()
            parts = raw.split("|")
            if len(parts) != 3:
                raise ValueError("Malformed token structure.")
            sig, email, timestamp = parts
            expected_payload = f"{email}|{timestamp}"
            expected_sig = hmac.new(
                self._secret(), expected_payload.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                raise ValueError("Token signature mismatch — invalid or tampered token.")
            return email
        except Exception as e:
            logger.warning(f"UnsubscribeService: invalid token — {e}")
            raise ValueError(f"Invalid unsubscribe token: {e}")

    def unsubscribe_email(self, email: str, reason: str = "unsubscribed") -> bool:
        """
        Adds the email address to the suppressions collection.
        Returns True if newly suppressed, False if already suppressed.
        """
        from app.utils.mongo_client import mongo_client
        if not mongo_client.is_connected:
            logger.error("UnsubscribeService: MongoDB not connected — cannot suppress email.")
            return False

        coll = mongo_client.get_collection("suppressions")
        if coll is None:
            return False

        existing = coll.find_one({"email": email})
        if existing:
            logger.info(f"UnsubscribeService: {email} already suppressed.")
            return False

        coll.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "reason": reason,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True
        )
        logger.info(f"UnsubscribeService: {email} suppressed (reason: {reason}).")
        return True

    def build_unsubscribe_url(self, email: str) -> str:
        """Builds the full unsubscribe URL to embed in email footers."""
        token = self.generate_token(email)
        base = settings.UNSUBSCRIBE_BASE_URL.rstrip("/")
        return f"{base}/unsubscribe?token={quote(token)}"


# Module-level singleton
unsubscribe_service = UnsubscribeService()
