from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator
import base64
import mimetypes

from app.utils.validation import validate_header_injection, sanitize_html_content


class AttachmentSchema(BaseModel):
    """
    Represents an attachment, which can either be:
    1. A local file path.
    2. In-memory data sent via Base64.
    """
    file_path: Optional[str] = Field(default=None, description="Local absolute path to the file to attach.")
    filename: Optional[str] = Field(default=None, description="Name of the file for in-memory attachments.")
    content_base64: Optional[str] = Field(default=None, description="Base64 encoded content of the file for in-memory attachments.")
    content_type: Optional[str] = Field(default=None, description="MIME content type of the file. Will be guessed if not provided.")

    @model_validator(mode="after")
    def validate_attachment_source(self) -> "AttachmentSchema":
        if not self.file_path and not self.content_base64:
            raise ValueError("Attachment must provide either file_path or content_base64.")
        if self.content_base64 and not self.filename:
            raise ValueError("filename is required for in-memory (base64) attachments.")
        return self


class InlineImageSchema(BaseModel):
    """
    Represents an inline image embedded directly inside the HTML email body via CID.

    Usage in HTML template:
        <img src="cid:company_logo" alt="SyncRivo Logo">

    In the API request:
        inline_images: [
            {
                "cid": "company_logo",
                "file_path": "/path/to/logo.png"
            }
        ]

    The image is embedded as a MIME part — no external URL is needed.
    Renders correctly even when the recipient's email client blocks external images.
    """
    cid: str = Field(
        ...,
        description="Content-ID referenced in HTML as src='cid:{cid}'. Must be unique per email."
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Absolute path to the image file on the server."
    )
    content_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded image content (alternative to file_path)."
    )
    content_type: Optional[str] = Field(
        default=None,
        description="MIME type, e.g. 'image/png'. Auto-detected from file extension if not provided."
    )
    filename: Optional[str] = Field(
        default=None,
        description="Filename for the inline image (used in headers)."
    )

    @model_validator(mode="after")
    def validate_inline_image_source(self) -> "InlineImageSchema":
        if not self.file_path and not self.content_base64:
            raise ValueError("InlineImage must provide either file_path or content_base64.")
        return self


class EmailRequest(BaseModel):
    """
    Unified validation schema for sending emails.
    """
    to_emails: Optional[Union[EmailStr, List[EmailStr]]] = Field(
        default=None, description="Recipient email address(es)."
    )
    recipient_source: Optional[str] = Field(
        default=None, description="Source of recipient emails (e.g. 'mongodb')."
    )
    recipient_collection: Optional[str] = Field(
        default=None, description="Collection name if source is 'mongodb'."
    )
    recipient_query: Optional[Dict[str, Any]] = Field(
        default=None, description="Query dictionary to filter recipients."
    )
    cc_emails: Optional[Union[EmailStr, List[EmailStr]]] = Field(
        default=None, description="CC recipient email address(es)."
    )
    bcc_emails: Optional[Union[EmailStr, List[EmailStr]]] = Field(
        default=None, description="BCC recipient email address(es)."
    )
    subject: Optional[str] = Field(
        default=None, description="Subject of the email. Optional if subject template is defined."
    )
    body_text: Optional[str] = Field(
        default=None, description="Plain text body."
    )
    body_html: Optional[str] = Field(
        default=None, description="HTML formatted body."
    )
    
    # Template configurations
    template_name: Optional[str] = Field(
        default=None, description="Jinja2 template filename (e.g. 'welcome.html')."
    )
    template_context: Dict[str, Any] = Field(
        default_factory=dict, description="Key-value values for the template placeholders."
    )

    # Dynamic subject rendering
    subject_template: Optional[str] = Field(
        default=None, description="Jinja2 template string for the subject."
    )

    # Attachments
    attachments: Optional[List[AttachmentSchema]] = Field(
        default=None, description="List of file path or in-memory attachments."
    )

    # Inline images (embedded directly in HTML body via CID)
    inline_images: Optional[List[InlineImageSchema]] = Field(
        default=None,
        description=(
            "Images embedded in the email body via Content-ID (CID). "
            "Reference in HTML as <img src='cid:your_cid'>. "
            "Renders without external URLs — works even with image blocking enabled."
        )
    )

    # Sender display name (overrides the default 'SyncRivo')
    from_name: Optional[str] = Field(
        default=None,
        description=(
            "Display name shown in the From header. "
            "e.g. 'SyncRivo Support' renders as: SyncRivo Support <support@syncrivo.ai>. "
            "Defaults to settings.DEFAULT_SENDER_NAME if not provided."
        )
    )

    # Custom configs/flags
    is_confidential: bool = Field(
        default=False, description="Flag to send as Company-Confidential & High Importance."
    )
    provider_override: Optional[str] = Field(
        default=None, description="Override global provider ('smtp', 'sendgrid', 'ses')."
    )

    @field_validator("to_emails", "cc_emails", "bcc_emails", mode="before")
    @classmethod
    def coerce_to_list(cls, value: Any) -> Optional[List[str]]:
        if value is None:
            return None
        if isinstance(value, str):
            return [email.strip() for email in value.split(",") if email.strip()]
        if isinstance(value, list):
            coerced = []
            for v in value:
                if isinstance(v, str):
                    coerced.extend([email.strip() for email in v.split(",") if email.strip()])
            return coerced
        return value

    @field_validator("subject", "subject_template")
    @classmethod
    def check_header_injection(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            validate_header_injection(value)
        return value

    @field_validator("body_html")
    @classmethod
    def sanitize_html(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            return sanitize_html_content(value)
        return value

    @model_validator(mode="after")
    def validate_recipients_and_content(self) -> "EmailRequest":
        # Validate recipient lists are not empty
        if self.recipient_source:
            if self.recipient_source != "mongodb":
                raise ValueError("recipient_source must be 'mongodb' if provided.")
        else:
            if not self.to_emails:
                raise ValueError("to_emails is required when recipient_source is not set.")
            if isinstance(self.to_emails, list) and len(self.to_emails) == 0:
                raise ValueError("to_emails list cannot be empty.")
            
        # Ensure subject or subject_template is present, unless template_name is provided
        if not self.subject and not self.subject_template and not self.template_name:
            raise ValueError("Subject, subject_template, or template_name must be provided.")

        # Ensure content is provided
        if not self.body_text and not self.body_html and not self.template_name:
            raise ValueError("Either body_text, body_html, or template_name must be provided.")

        return self


class EmailResponse(BaseModel):
    """
    Standard model representing email delivery result.
    """
    success: bool
    message_id: Optional[str] = None
    provider_used: str
    message: str
