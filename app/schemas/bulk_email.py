import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


class BulkEmailRequest(BaseModel):
    """
    Schema for sending personalized bulk emails to large recipient lists.
    Supports both MongoDB-sourced and explicit recipient lists.
    """

    # --- Recipient Source ---
    recipient_source: str = Field(
        default="mongodb",
        description="Source of recipients: 'mongodb' or 'list'."
    )
    recipient_collection: Optional[str] = Field(
        default=None,
        description="MongoDB collection name (required if recipient_source='mongodb')."
    )
    recipient_query: Optional[Dict[str, Any]] = Field(
        default=None,
        description="MongoDB query filter to select recipients (e.g. {'country': 'India'})."
    )
    to_emails: Optional[List[EmailStr]] = Field(
        default=None,
        description="Explicit list of recipient emails (used if recipient_source='list')."
    )

    # --- Batching / Throttle Controls ---
    batch_size: int = Field(
        default=500,
        ge=1,
        le=2000,
        description="Number of emails to process per batch. Max 2000."
    )
    delay_between_batches_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Seconds to pause between batches to avoid rate limiting."
    )

    # --- Email Content ---
    subject: Optional[str] = Field(
        default=None,
        description="Static subject line. Overridden by subject_template if provided."
    )
    subject_template: Optional[str] = Field(
        default=None,
        description="Jinja2 template string for dynamic subjects, e.g. 'Hello {{ name }}'."
    )
    template_name: Optional[str] = Field(
        default=None,
        description="Jinja2 HTML template filename, e.g. 'newsletter.html'."
    )
    template_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Base context for templates. Recipient fields are merged on top per email."
    )
    body_text: Optional[str] = Field(
        default=None,
        description="Static plain-text body (used if no template_name)."
    )
    body_html: Optional[str] = Field(
        default=None,
        description="Static HTML body (used if no template_name)."
    )

    # --- Options ---
    cc_emails: Optional[List[EmailStr]] = Field(
        default=None,
        description="CC recipients for all emails in the bulk job."
    )
    bcc_emails: Optional[List[EmailStr]] = Field(
        default=None,
        description="BCC recipients for all emails in the bulk job."
    )
    is_confidential: bool = Field(
        default=False,
        description="Mark emails as Company-Confidential and High Importance."
    )
    provider_override: Optional[str] = Field(
        default=None,
        description="Override the global email provider: 'smtp', 'sendgrid', 'ses'."
    )
    initiated_by: Optional[str] = Field(
        default=None,
        description="Identifier of the microservice or user initiating the bulk job."
    )


class BulkJobStatusResponse(BaseModel):
    """Response model for bulk send job status."""
    job_id: str
    status: str                    # queued, in_progress, completed, failed, cancelled
    total_recipients: int
    sent: int
    failed: int
    skipped_suppressed: int
    template_name: Optional[str] = None
    initiated_by: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_detail: Optional[str] = None
