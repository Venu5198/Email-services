from typing import Optional
from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core Provider Configuration
    # Options: "smtp", "sendgrid", "ses"
    EMAIL_PROVIDER: str = Field(default="smtp")
    DEFAULT_SENDER_EMAIL: EmailStr = Field(default="noreply@syncrivo.ai")
    DEFAULT_SENDER_NAME: str = Field(default="SyncRivo", description="Display name used in From header.")

    # MongoDB Settings
    MONGODB_URI: str = Field(default="mongodb://localhost:27017")
    MONGODB_DB_NAME: str = Field(default="email_service")
    ENABLE_MONGO_LOGGING: bool = Field(default=True)
    ENABLE_MONGO_TEMPLATES: bool = Field(default=True)

    # SMTP Settings (Gmail, custom relay, etc.)
    SMTP_HOST: str = Field(default="smtp.gmail.com")
    SMTP_PORT: int = Field(default=465)
    SMTP_USERNAME: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SMTP_USE_TLS: bool = Field(default=False)
    SMTP_USE_SSL: bool = Field(default=True)

    # SendGrid Settings
    SENDGRID_API_KEY: Optional[str] = Field(default=None)
    SENDGRID_FROM_EMAIL: Optional[EmailStr] = Field(default=None)

    # AWS SES Settings
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None)
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None)
    AWS_REGION: str = Field(default="us-east-1")
    AWS_SES_FROM_EMAIL: Optional[EmailStr] = Field(default=None)

    # Attachment & Security Limits
    MAX_ATTACHMENT_SIZE_MB: float = Field(default=10.0)
    MAX_TOTAL_ATTACHMENT_SIZE_MB: float = Field(default=25.0)

    # Resiliency Settings
    RETRY_ATTEMPTS: int = Field(default=3)
    RETRY_BACKOFF_MIN: float = Field(default=1.0)
    RETRY_BACKOFF_MAX: float = Field(default=10.0)

    # Logging Settings
    LOG_LEVEL: str = Field(default="INFO")

    # Inbox Monitoring (IMAP)
    IMAP_HOST: str = Field(default="imap.gmail.com")
    IMAP_PORT: int = Field(default=993)
    IMAP_USERNAME: Optional[str] = Field(default=None, description="Inbox to monitor (e.g. support@syncrivo.ai)")
    IMAP_PASSWORD: Optional[str] = Field(default=None, description="App password for the monitored inbox.")
    INBOX_POLL_INTERVAL_SECONDS: int = Field(default=60, description="How often to poll inbox in seconds.")

    # Team Alerting
    SLACK_WEBHOOK_URL: Optional[str] = Field(default=None, description="Slack Incoming Webhook URL for alerts.")

    # ── Phase 6: Open & Click Tracking ────────────────────────────────────
    ENABLE_TRACKING: bool = Field(
        default=True,
        description="Inject tracking pixel + wrap links in HTML emails for open/click analytics."
    )
    TRACKING_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="Public base URL of this service used to build tracking pixel and click-wrap URLs."
    )

    # ── Phase 6: One-Click Unsubscribe ────────────────────────────────────
    UNSUBSCRIBE_SECRET_KEY: str = Field(
        default="change-me-to-a-random-32-char-secret",
        description="HMAC-SHA256 secret for signing unsubscribe tokens. Must be kept private."
    )
    UNSUBSCRIBE_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="Public base URL used to construct List-Unsubscribe links in emails."
    )

    # ── Phase 6: Scheduled Email Sending ──────────────────────────────────
    SCHEDULER_TIMEZONE: str = Field(
        default="UTC",
        description="Timezone for the APScheduler job scheduler (e.g. 'Asia/Kolkata', 'UTC')."
    )

    # ── Phase 6: Bounce Webhook ────────────────────────────────────────────
    SENDGRID_WEBHOOK_SECRET: Optional[str] = Field(
        default=None,
        description="Optional SendGrid Signed Event Webhook verification key."
    )


# Global config instance
settings = Settings()
