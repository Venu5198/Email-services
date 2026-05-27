import logging
from email.message import EmailMessage
from email.utils import make_msgid
from typing import List, Optional
from app.config import settings
from app.exceptions import ProviderError
from app.services.attachment_handler import PreparedAttachment
from app.services.providers.base import BaseEmailProvider

logger = logging.getLogger("email_service")

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class SesEmailProvider(BaseEmailProvider):
    """
    AWS SES Provider implementing BaseEmailProvider.
    Uses 'boto3' and SES send_raw_email to support attachments, CC, BCC, and custom headers.
    """

    def __init__(self):
        if not BOTO3_AVAILABLE:
            raise ProviderError(
                "AWS SDK (boto3) is not installed. Please install 'boto3' library."
            )
        self.access_key = settings.AWS_ACCESS_KEY_ID
        self.secret_key = settings.AWS_SECRET_ACCESS_KEY
        self.region = settings.AWS_REGION
        self.from_email = settings.AWS_SES_FROM_EMAIL or settings.DEFAULT_SENDER_EMAIL

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
        logger.info(f"Sending email to {to_emails} via AWS SES")

        # Initialize boto3 SES client
        try:
            # If credentials are provided explicitly, use them; otherwise, let boto3 resolve automatically (best practice)
            if self.access_key and self.secret_key:
                session = boto3.Session(
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key,
                    region_name=self.region,
                )
            else:
                session = boto3.Session(region_name=self.region)
            
            client = session.client("ses")
        except Exception as e:
            logger.error(f"Failed to initialize AWS SES client: {e}")
            raise ProviderError(f"AWS SES initialization failed: {e}")

        # Construct raw MIME message to support attachments, CC, BCC, and custom headers
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_email or self.from_email
        msg["To"] = ", ".join(to_emails)

        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        # Note: Even though we add the BCC header to the MIME message, we can pass envelope destinations separately,
        # and standard SES transmission handles it. In raw transmission, it's best to include CC/BCC in standard headers,
        # but we must pass all destinations to the `Destinations` parameter of `send_raw_email` so AWS knows who to route it to.
        if bcc_emails:
            msg["Bcc"] = ", ".join(bcc_emails)

        # Confidential Mode Headers
        if is_confidential:
            msg["Sensitivity"] = "Company-Confidential"
            msg["Importance"] = "High"

        # Content
        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        # Attachments
        if attachments:
            for att in attachments:
                maintype, subtype = "application", "octet-stream"
                if "/" in att.content_type:
                    maintype, subtype = att.content_type.split("/", 1)
                msg.add_attachment(
                    att.content,
                    maintype=maintype,
                    subtype=subtype,
                    filename=att.filename,
                )

        # Build recipient destinations list for the SES envelope
        destinations = list(to_emails)
        if cc_emails:
            destinations.extend(cc_emails)
        if bcc_emails:
            destinations.extend(bcc_emails)

        try:
            response = client.send_raw_email(
                Source=from_email or self.from_email,
                Destinations=destinations,
                RawMessage={"Data": msg.as_bytes()},
            )
            message_id = response.get("MessageId") or f"ses-{str(make_msgid())}"
            logger.info(f"AWS SES email sent successfully. Message ID: {message_id}")
            return str(message_id)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(f"AWS SES API Error: Code={error_code}, Message={error_message}")
            raise ProviderError(f"AWS SES send failed: [{error_code}] {error_message}")
        except Exception as e:
            logger.error(f"Failed to send email via AWS SES: {e}")
            raise ProviderError(f"AWS SES sending failed: {e}")
