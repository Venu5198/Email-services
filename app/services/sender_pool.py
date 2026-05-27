import smtplib
import logging
import threading
from datetime import datetime, timezone, date
from typing import Optional, List, Dict
from email.message import EmailMessage
from email.utils import make_msgid, formataddr

from app.config import settings
from app.exceptions import ProviderError

logger = logging.getLogger("email_service.sender_pool")


# ---------------------------------------------------------------------------
# Data model for a pooled sender account
# ---------------------------------------------------------------------------

class SenderAccount:
    """
    Represents one sender email account in the rotation pool.
    Tracks its SMTP credentials and daily sending quota.
    """

    def __init__(
        self,
        email: str,
        smtp_username: str,
        smtp_password: str,
        display_name: str = "SyncRivo",
        daily_limit: int = 500,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_use_ssl: Optional[bool] = None,
        sent_today: int = 0,
        last_reset_date: Optional[str] = None,
        is_active: bool = True,
    ):
        self.email = email
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password.replace(" ", "")
        self.display_name = display_name
        self.daily_limit = daily_limit
        # Inherit global SMTP settings if not overridden per-account
        self.smtp_host = smtp_host or settings.SMTP_HOST
        self.smtp_port = smtp_port or settings.SMTP_PORT
        self.smtp_use_ssl = smtp_use_ssl if smtp_use_ssl is not None else settings.SMTP_USE_SSL
        self.sent_today = sent_today
        self.last_reset_date = last_reset_date or str(date.today())
        self.is_active = is_active

    @property
    def from_address(self) -> str:
        """Returns formatted From header: 'SyncRivo <sender@syncrivo.ai>'"""
        return formataddr((self.display_name, self.email))

    @property
    def remaining_quota(self) -> int:
        return max(0, self.daily_limit - self.sent_today)

    @property
    def is_exhausted(self) -> bool:
        return self.sent_today >= self.daily_limit

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "smtp_username": self.smtp_username,
            "display_name": self.display_name,
            "daily_limit": self.daily_limit,
            "sent_today": self.sent_today,
            "remaining_quota": self.remaining_quota,
            "last_reset_date": self.last_reset_date,
            "is_active": self.is_active,
            "is_exhausted": self.is_exhausted,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
        }


# ---------------------------------------------------------------------------
# Pooled SMTP sender — sends from a specific SenderAccount's credentials
# ---------------------------------------------------------------------------

class PooledSmtpSender:
    """
    A lightweight SMTP sender that uses per-account credentials.
    Unlike the global SmtpEmailProvider (which reads from settings),
    this takes a SenderAccount and sends using its specific login.
    """

    def send(
        self,
        account: SenderAccount,
        to_emails: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        is_confidential: bool = False,
    ) -> str:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = account.from_address
        msg["To"] = ", ".join(to_emails)

        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        if bcc_emails:
            msg["Bcc"] = ", ".join(bcc_emails)

        if is_confidential:
            msg["Sensitivity"] = "Company-Confidential"
            msg["Importance"] = "High"

        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        server = None
        try:
            if account.smtp_use_ssl:
                server = smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=15)
                if settings.SMTP_USE_TLS:
                    server.starttls()

            server.login(account.smtp_username, account.smtp_password)
            server.send_message(msg)

            msg_id = msg.get("Message-ID") or str(make_msgid())
            return msg_id

        except smtplib.SMTPAuthenticationError as e:
            raise ProviderError(f"SMTP auth failed for {account.email}: {e}")
        except smtplib.SMTPConnectError as e:
            raise ProviderError(f"SMTP connect failed for {account.email}: {e}")
        except Exception as e:
            raise ProviderError(f"SMTP send failed for {account.email}: {e}")
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# SenderPoolManager — the main pool coordinator
# ---------------------------------------------------------------------------

class SenderPoolManager:
    """
    Manages a pool of up to 20 sender email accounts with:

    - Round-robin rotation across available senders
    - Per-account daily quota tracking (default: 500 emails/day per account)
    - Auto-reset of daily counters at midnight (checked on each call)
    - MongoDB persistence for quota state across restarts
    - Thread-safe counter increments
    - Automatic failover when an account is exhausted or inactive

    Architecture:
        Centralized Email Service
                |
                v
        SenderPoolManager
                |
                +--> sender1@syncrivo.ai → 500/day
                +--> sender2@syncrivo.ai → 500/day
                ...
                +--> sender20@syncrivo.ai → 500/day
                            Total: 10,000 emails/day
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._accounts: List[SenderAccount] = []
        self._current_index: int = 0
        self._smtp_sender = PooledSmtpSender()
        self._loaded = False

    # -----------------------------------------------------------------------
    # Account loading
    # -----------------------------------------------------------------------

    def load_accounts(self) -> List[SenderAccount]:
        """
        Loads sender accounts from MongoDB sender_accounts collection.
        Checks and resets daily counters if the date has changed.
        Returns the loaded list.
        """
        with self._lock:
            try:
                from app.utils.mongo_client import mongo_client
                if not mongo_client.is_connected:
                    logger.warning("SenderPool: MongoDB not connected. Pool will be empty.")
                    self._accounts = []
                    self._loaded = True
                    return []

                coll = mongo_client.get_collection("sender_accounts")
                if coll is None:
                    self._accounts = []
                    self._loaded = True
                    return []

                today_str = str(date.today())
                docs = list(coll.find({}))

                accounts = []
                for doc in docs:
                    # Auto-reset daily counter if it's a new day
                    if doc.get("last_reset_date") != today_str:
                        coll.update_one(
                            {"email": doc["email"]},
                            {"$set": {"sent_today": 0, "last_reset_date": today_str}}
                        )
                        doc["sent_today"] = 0
                        doc["last_reset_date"] = today_str

                    acc = SenderAccount(
                        email=doc["email"],
                        smtp_username=doc.get("smtp_username", doc["email"]),
                        smtp_password=doc.get("smtp_password", ""),
                        display_name=doc.get("display_name", "SyncRivo"),
                        daily_limit=doc.get("daily_limit", 500),
                        smtp_host=doc.get("smtp_host"),
                        smtp_port=doc.get("smtp_port"),
                        smtp_use_ssl=doc.get("smtp_use_ssl"),
                        sent_today=doc.get("sent_today", 0),
                        last_reset_date=doc.get("last_reset_date", today_str),
                        is_active=doc.get("is_active", True),
                    )
                    accounts.append(acc)

                self._accounts = accounts
                self._loaded = True
                logger.info(
                    f"SenderPool: Loaded {len(accounts)} sender accounts. "
                    f"Total daily capacity: {sum(a.daily_limit for a in accounts):,} emails."
                )
                return accounts

            except Exception as ex:
                logger.error(f"SenderPool: Failed to load accounts: {ex}")
                self._accounts = []
                self._loaded = True
                return []

    def get_all_accounts(self) -> List[SenderAccount]:
        """Returns a fresh load of all accounts from MongoDB."""
        return self.load_accounts()

    # -----------------------------------------------------------------------
    # Sender selection (round-robin rotation)
    # -----------------------------------------------------------------------

    def get_next_sender(self) -> Optional[SenderAccount]:
        """
        Returns the next available sender using round-robin rotation.

        Selection criteria:
          - Account must be active (is_active=True)
          - Account must not be exhausted (sent_today < daily_limit)
          - If today's date has changed since last load, daily counters are reset

        Returns None if all accounts are exhausted or no accounts are configured.
        """
        # Reload to pick up any quota resets or new accounts
        self.load_accounts()

        with self._lock:
            if not self._accounts:
                logger.error("SenderPool: No sender accounts configured.")
                return None

            # Check if daily reset is needed (date changed since last load)
            today_str = str(date.today())
            for acc in self._accounts:
                if acc.last_reset_date != today_str:
                    acc.sent_today = 0
                    acc.last_reset_date = today_str

            # Try all accounts starting from current index (round-robin)
            num_accounts = len(self._accounts)
            for attempt in range(num_accounts):
                idx = (self._current_index + attempt) % num_accounts
                acc = self._accounts[idx]

                if not acc.is_active:
                    continue
                if acc.is_exhausted:
                    logger.debug(
                        f"SenderPool: {acc.email} exhausted "
                        f"({acc.sent_today}/{acc.daily_limit}). Skipping."
                    )
                    continue

                # Found a valid sender — advance index for next call
                self._current_index = (idx + 1) % num_accounts
                logger.debug(
                    f"SenderPool: Selected {acc.email} "
                    f"({acc.sent_today}/{acc.daily_limit} used, "
                    f"{acc.remaining_quota} remaining)."
                )
                return acc

            logger.error(
                "SenderPool: All sender accounts are exhausted or inactive for today. "
                "Cannot send more emails until quotas reset at midnight."
            )
            return None

    # -----------------------------------------------------------------------
    # Quota management
    # -----------------------------------------------------------------------

    def increment_sent(self, account_email: str) -> None:
        """
        Increments the sent_today counter for the given account both in-memory
        and persisted to MongoDB.
        """
        with self._lock:
            # Update in-memory
            for acc in self._accounts:
                if acc.email == account_email:
                    acc.sent_today += 1
                    break

        # Persist to MongoDB (outside lock to avoid blocking)
        try:
            from app.utils.mongo_client import mongo_client
            if mongo_client.is_connected:
                coll = mongo_client.get_collection("sender_accounts")
                if coll is not None:
                    coll.update_one(
                        {"email": account_email},
                        {"$inc": {"sent_today": 1}}
                    )
        except Exception as ex:
            logger.error(f"SenderPool: Failed to persist quota for {account_email}: {ex}")

    def mark_account_failed(self, account_email: str, reason: str = "") -> None:
        """
        Marks an account as inactive after a send failure (e.g. auth error).
        The account will be skipped in future rotation until manually re-activated.
        """
        with self._lock:
            for acc in self._accounts:
                if acc.email == account_email:
                    acc.is_active = False
                    break

        try:
            from app.utils.mongo_client import mongo_client
            if mongo_client.is_connected:
                coll = mongo_client.get_collection("sender_accounts")
                if coll is not None:
                    coll.update_one(
                        {"email": account_email},
                        {"$set": {"is_active": False, "failure_reason": reason}}
                    )
            logger.warning(f"SenderPool: Account {account_email} marked inactive. Reason: {reason}")
        except Exception as ex:
            logger.error(f"SenderPool: Failed to mark {account_email} as failed: {ex}")

    def reset_daily_quotas(self) -> int:
        """
        Manually resets all daily quotas to 0.
        Normally runs automatically at midnight but can be triggered via admin endpoint.
        Returns the number of accounts reset.
        """
        today_str = str(date.today())
        count = 0
        with self._lock:
            for acc in self._accounts:
                acc.sent_today = 0
                acc.last_reset_date = today_str
                count += 1

        try:
            from app.utils.mongo_client import mongo_client
            if mongo_client.is_connected:
                coll = mongo_client.get_collection("sender_accounts")
                if coll is not None:
                    coll.update_many(
                        {},
                        {"$set": {"sent_today": 0, "last_reset_date": today_str}}
                    )
        except Exception as ex:
            logger.error(f"SenderPool: Failed to reset quotas in MongoDB: {ex}")

        logger.info(f"SenderPool: Daily quotas reset for {count} accounts.")
        return count

    # -----------------------------------------------------------------------
    # Send via pool — public interface used by bulk_email_service
    # -----------------------------------------------------------------------

    def send(
        self,
        to_emails: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        is_confidential: bool = False,
    ) -> str:
        """
        Selects the next available sender, sends the email, and increments quota.
        Falls back to the global DEFAULT_SENDER_EMAIL if pool is empty.
        Raises ProviderError if all senders are exhausted.
        """
        account = self.get_next_sender()

        if account is None:
            raise ProviderError(
                "All sender accounts are exhausted for today (10,000 email limit reached). "
                "Quotas reset at midnight."
            )

        try:
            msg_id = self._smtp_sender.send(
                account=account,
                to_emails=to_emails,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                is_confidential=is_confidential,
            )
            self.increment_sent(account.email)
            logger.info(
                f"SenderPool: Sent via {account.email} "
                f"({account.sent_today}/{account.daily_limit}) → {to_emails}"
            )
            return msg_id

        except ProviderError as ex:
            if "auth" in str(ex).lower():
                self.mark_account_failed(account.email, reason=str(ex))
            raise

    # -----------------------------------------------------------------------
    # Pool status summary
    # -----------------------------------------------------------------------

    def get_pool_status(self) -> Dict:
        """Returns a summary of the entire pool's current state."""
        self.load_accounts()
        accounts_status = [acc.to_dict() for acc in self._accounts]
        total_capacity = sum(a.daily_limit for a in self._accounts)
        total_sent = sum(a.sent_today for a in self._accounts)
        active_count = sum(1 for a in self._accounts if a.is_active and not a.is_exhausted)

        return {
            "total_accounts": len(self._accounts),
            "active_available_senders": active_count,
            "total_daily_capacity": total_capacity,
            "total_sent_today": total_sent,
            "total_remaining_today": max(0, total_capacity - total_sent),
            "capacity_used_pct": round(total_sent / total_capacity * 100, 1) if total_capacity > 0 else 0,
            "accounts": accounts_status,
        }


# Global singleton — shared across all services
sender_pool = SenderPoolManager()
