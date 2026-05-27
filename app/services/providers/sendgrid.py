import base64
import logging
from typing import List, Optional
from app.config import settings
from app.exceptions import ProviderError
from app.services.attachment_handler import PreparedAttachment
from app.services.providers.base import BaseEmailProvider

logger = logging.getLogger("email_service")

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail,
        Email,
        To,
        Cc,
        Bcc,
        Attachment,
        FileContent,
        FileName,
        FileType,
        Disposition,
        Header
    )
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False


class SendGridEmailProvider(BaseEmailProvider):
    """
    SendGrid API Provider implementing BaseEmailProvider.
    Requires 'sendgrid' package.
    """

    def __init__(self):
        if not SENDGRID_AVAILABLE:
            raise ProviderError(
                "SendGrid package is not installed. Please install 'sendgrid' library."
            )
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL or settings.DEFAULT_SENDER_EMAIL

    def send(
        self,
        from_email: str,
        to_emails: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        attachments: Optional[List[PreparedAttachment]] = None,
        is_confidential: bool = False,
        from_name: Optional[str] = None,
        inline_images: Optional[list] = None,
    ) -> str:
        if not self.api_key:
            raise ProviderError("SendGrid API Key is not configured in settings.")

        sender = from_email or self.from_email
        logger.info(f"Sending email to {to_emails} via SendGrid API")

        # Formulate SendGrid Mail message
        message = Mail(
            from_email=Email(sender),
            to_emails=[To(email) for email in to_emails],
            subject=subject,
            plain_text_content=body_text,
            html_content=body_html
        )

        # CC & BCC
        if cc_emails:
            for email in cc_emails:
                message.add_cc(Cc(email))
        if bcc_emails:
            for email in bcc_emails:
                message.add_bcc(Bcc(email))

        # Confidential Mode Headers
        if is_confidential:
            message.add_header(Header("Sensitivity", "Company-Confidential"))
            message.add_header(Header("Importance", "High"))

        # Attachments
        if attachments:
            for att in attachments:
                encoded_content = base64.b64encode(att.content).decode("utf-8")
                sg_attachment = Attachment(
                    file_content=FileContent(encoded_content),
                    file_name=FileName(att.filename),
                    file_type=FileType(att.content_type),
                    disposition=Disposition("attachment")
                )
                message.add_attachment(sg_attachment)

        try:
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            if response.status_code >= 400:
                logger.error(f"SendGrid delivery failed. Status: {response.status_code}, Body: {response.body}")
                raise ProviderError(f"SendGrid returned status code {response.status_code}: {response.body}")
            
            # Retrieve message ID from response headers if available
            message_id = response.headers.get("X-Message-Id") or f"sg-{response.status_code}"
            logger.info(f"SendGrid email sent successfully. Message ID: {message_id}")
            return str(message_id)

        except Exception as e:
            logger.error(f"SendGrid API execution failed: {e}")
            raise ProviderError(f"SendGrid sending failed: {e}")
