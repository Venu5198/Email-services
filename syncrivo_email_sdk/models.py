"""
SyncRivo Email SDK — Data Models
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class Attachment:
    """Represents an email attachment."""
    filename: str
    content_base64: str
    content_type: str = "application/octet-stream"
    file_path: Optional[str] = None


@dataclass
class InlineImage:
    """
    Represents an image embedded inline in the email HTML body via CID.

    Usage in HTML:
        <img src="cid:company_logo">
    """
    cid: str
    file_path: Optional[str] = None
    content_base64: Optional[str] = None
    content_type: Optional[str] = None
    filename: Optional[str] = None


@dataclass
class EmailPayload:
    """
    Full email request payload.
    Use the convenience methods on SyncRivoEmailClient instead of constructing this directly.
    """
    to_emails: Optional[str] = None                      # comma-separated or single
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    template_name: Optional[str] = None
    template_context: Dict[str, Any] = field(default_factory=dict)
    subject_template: Optional[str] = None
    cc_emails: Optional[str] = None
    bcc_emails: Optional[str] = None
    from_name: Optional[str] = None
    is_confidential: bool = False
    attachments: Optional[List[Attachment]] = None
    inline_images: Optional[List[InlineImage]] = None
    provider_override: Optional[str] = None
    recipient_source: Optional[str] = None
    recipient_collection: Optional[str] = None
    recipient_query: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Serializes the payload to a JSON-compatible dict for the API."""
        data: Dict[str, Any] = {}

        if self.to_emails:
            data["to_emails"] = self.to_emails
        if self.subject:
            data["subject"] = self.subject
        if self.body_html:
            data["body_html"] = self.body_html
        if self.body_text:
            data["body_text"] = self.body_text
        if self.template_name:
            data["template_name"] = self.template_name
        if self.template_context:
            data["template_context"] = self.template_context
        if self.subject_template:
            data["subject_template"] = self.subject_template
        if self.cc_emails:
            data["cc_emails"] = self.cc_emails
        if self.bcc_emails:
            data["bcc_emails"] = self.bcc_emails
        if self.from_name:
            data["from_name"] = self.from_name
        if self.is_confidential:
            data["is_confidential"] = True
        if self.provider_override:
            data["provider_override"] = self.provider_override
        if self.recipient_source:
            data["recipient_source"] = self.recipient_source
        if self.recipient_collection:
            data["recipient_collection"] = self.recipient_collection
        if self.recipient_query:
            data["recipient_query"] = self.recipient_query

        if self.attachments:
            data["attachments"] = [
                {
                    "filename": a.filename,
                    "content_base64": a.content_base64,
                    "content_type": a.content_type,
                    **({"file_path": a.file_path} if a.file_path else {}),
                }
                for a in self.attachments
            ]

        if self.inline_images:
            data["inline_images"] = [
                {
                    "cid": img.cid,
                    **({"file_path": img.file_path} if img.file_path else {}),
                    **({"content_base64": img.content_base64} if img.content_base64 else {}),
                    **({"content_type": img.content_type} if img.content_type else {}),
                    **({"filename": img.filename} if img.filename else {}),
                }
                for img in self.inline_images
            ]

        return data


@dataclass
class BulkEmailPayload:
    """Payload for high-volume bulk email sends."""
    recipient_source: str = "mongodb"
    recipient_collection: Optional[str] = None
    recipient_query: Optional[Dict[str, Any]] = None
    to_emails: Optional[List[str]] = None
    template_name: Optional[str] = None
    template_context: Dict[str, Any] = field(default_factory=dict)
    subject: Optional[str] = None
    subject_template: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    batch_size: int = 500
    delay_between_batches_seconds: float = 1.0
    is_confidential: bool = False
    provider_override: Optional[str] = None
    initiated_by: Optional[str] = None

    def to_dict(self) -> dict:
        data: Dict[str, Any] = {
            "recipient_source": self.recipient_source,
            "batch_size": self.batch_size,
            "delay_between_batches_seconds": self.delay_between_batches_seconds,
            "is_confidential": self.is_confidential,
            "template_context": self.template_context,
        }
        if self.recipient_collection:
            data["recipient_collection"] = self.recipient_collection
        if self.recipient_query:
            data["recipient_query"] = self.recipient_query
        if self.to_emails:
            data["to_emails"] = self.to_emails
        if self.template_name:
            data["template_name"] = self.template_name
        if self.subject:
            data["subject"] = self.subject
        if self.subject_template:
            data["subject_template"] = self.subject_template
        if self.body_text:
            data["body_text"] = self.body_text
        if self.body_html:
            data["body_html"] = self.body_html
        if self.provider_override:
            data["provider_override"] = self.provider_override
        if self.initiated_by:
            data["initiated_by"] = self.initiated_by
        return data
