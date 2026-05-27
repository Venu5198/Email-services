import smtplib
import base64
import logging
import mimetypes
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formataddr
from typing import List, Optional

from app.config import settings
from app.exceptions import ProviderError
from app.services.attachment_handler import PreparedAttachment
from app.services.providers.base import BaseEmailProvider

logger = logging.getLogger("email_service")


def _encode_subject(subject: str) -> str:
    """
    RFC 2047 — encodes the subject line using UTF-8 quoted-printable encoding.

    This ensures emojis and non-ASCII characters (e.g. ✅ 🚨 🔴) display
    correctly in ALL email clients (Gmail, Outlook, Apple Mail, Thunderbird).

    WITHOUT this:   Subject: =?utf-8?b?4pyF...?=  (garbled in some clients)
    WITH this:      Subject: ✅ Your Demo is Confirmed  (renders perfectly)
    """
    try:
        # If pure ASCII — no encoding needed
        subject.encode("ascii")
        return subject
    except UnicodeEncodeError:
        # Contains non-ASCII — encode as UTF-8 Base64 per RFC 2047
        return Header(subject, charset="utf-8").encode()


def _build_from_header(from_email: str, from_name: Optional[str] = None) -> str:
    """
    Builds a properly formatted From header with display name.

    Result: 'SyncRivo Support <support@syncrivo.ai>'

    The display name is RFC 2047 encoded if it contains non-ASCII characters
    (e.g. names with accents or unicode characters).
    """
    display_name = from_name or settings.DEFAULT_SENDER_NAME
    return formataddr((display_name, from_email))


class SmtpEmailProvider(BaseEmailProvider):
    """
    SMTP Email Provider — Phase 4 Enhanced Version.

    Features added in Phase 4:
    - RFC 2047 UTF-8 subject encoding (emoji subjects display correctly everywhere)
    - from_name display name support (e.g. 'SyncRivo Support <support@syncrivo.ai>')
    - Inline image embedding via CID (Content-ID) for logo/image in HTML body
    - Inline images render even when email client blocks external images
    - Full attachment support (PDF, DOCX, CSV, XLSX, images, etc.)
    """

    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD.replace(" ", "") if settings.SMTP_PASSWORD else None
        self.use_tls = settings.SMTP_USE_TLS
        self.use_ssl = settings.SMTP_USE_SSL

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
        """
        Sends an email via SMTP with full Phase 4 feature support.

        Args:
            from_email:     Sender email address.
            to_emails:      List of recipient addresses.
            subject:        Subject line (supports emojis — auto RFC 2047 encoded).
            body_text:      Plain text fallback body.
            body_html:      HTML body (supports inline CID image references).
            cc_emails:      Optional CC recipients.
            bcc_emails:     Optional BCC recipients.
            attachments:    Optional list of PreparedAttachment objects.
            is_confidential: Adds Sensitivity and Importance headers.
            from_name:      Optional display name for the From header.
            inline_images:  Optional list of InlineImageSchema objects for CID embedding.
        """
        logger.info(f"Preparing SMTP email to {to_emails} via {self.host}")

        has_inline = bool(inline_images)

        # -----------------------------------------------------------------------
        # Build the MIME structure based on content type
        #
        # Structure depends on what's included:
        #
        # Plain text only:
        #   MIMEText(plain)
        #
        # HTML only (no inline images, no attachments):
        #   MIMEMultipart(alternative)
        #   ├── MIMEText(plain)
        #   └── MIMEText(html)
        #
        # HTML + inline images (no attachments):
        #   MIMEMultipart(related)
        #   ├── MIMEMultipart(alternative)
        #   │   ├── MIMEText(plain)
        #   │   └── MIMEText(html)
        #   └── MIMEImage(cid=logo, ...)
        #
        # HTML + inline images + attachments:
        #   MIMEMultipart(mixed)
        #   ├── MIMEMultipart(related)
        #   │   ├── MIMEMultipart(alternative)
        #   │   │   ├── MIMEText(plain)
        #   │   │   └── MIMEText(html)
        #   │   └── MIMEImage(cid=logo, ...)
        #   └── MIMEBase(attachment, ...)
        # -----------------------------------------------------------------------

        if has_inline or attachments or body_html:
            # Build the alternative part (plain + html)
            alt_part = MIMEMultipart("alternative")
            alt_part.attach(MIMEText(body_text or "", "plain", "utf-8"))
            if body_html:
                alt_part.attach(MIMEText(body_html, "html", "utf-8"))

            if has_inline:
                # Wrap in related to embed CID images alongside HTML
                related_part = MIMEMultipart("related")
                related_part.attach(alt_part)
                for img in inline_images:
                    related_part.attach(self._build_inline_image(img))

                if attachments:
                    # Wrap everything in mixed for file attachments
                    root = MIMEMultipart("mixed")
                    root.attach(related_part)
                    for att in attachments:
                        root.attach(self._build_attachment(att))
                else:
                    root = related_part
            else:
                if attachments:
                    root = MIMEMultipart("mixed")
                    root.attach(alt_part)
                    for att in attachments:
                        root.attach(self._build_attachment(att))
                else:
                    root = alt_part
        else:
            # Plain text only — simple single-part message
            root = MIMEText(body_text or "", "plain", "utf-8")

        # -----------------------------------------------------------------------
        # Set message headers
        # -----------------------------------------------------------------------
        root["Subject"] = _encode_subject(subject)
        root["From"] = _build_from_header(from_email, from_name)
        root["To"] = ", ".join(to_emails)
        root["Message-ID"] = make_msgid(domain=from_email.split("@")[-1])

        if cc_emails:
            root["Cc"] = ", ".join(cc_emails)
        if bcc_emails:
            root["Bcc"] = ", ".join(bcc_emails)

        if is_confidential:
            root["Sensitivity"] = "Company-Confidential"
            root["Importance"] = "High"
            root["X-Priority"] = "1"

        # ── Phase 6: List-Unsubscribe (Gmail/Yahoo 2024 bulk sender requirement) ──
        # Added for all non-confidential emails that have an HTML body (marketing).
        # This enables the native "Unsubscribe" button in Gmail and Yahoo Mail.
        if not is_confidential and body_html and to_emails:
            try:
                from app.services.unsubscribe_service import unsubscribe_service
                primary_recipient = to_emails[0]
                unsub_url = unsubscribe_service.build_unsubscribe_url(primary_recipient)
                unsub_mailto = f"mailto:unsubscribe@syncrivo.ai?subject=unsubscribe&body={primary_recipient}"
                root["List-Unsubscribe"] = f"<{unsub_mailto}>, <{unsub_url}>"
                root["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
            except Exception as _e:
                logger.debug(f"Could not add List-Unsubscribe header: {_e}")

        # -----------------------------------------------------------------------
        # Connect and send
        # -----------------------------------------------------------------------
        server = None
        try:
            if self.use_ssl:
                logger.debug(f"Connecting via SSL: {self.host}:{self.port}")
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=15)
            else:
                logger.debug(f"Connecting via SMTP: {self.host}:{self.port}")
                server = smtplib.SMTP(self.host, self.port, timeout=15)
                if self.use_tls:
                    logger.debug("Upgrading to TLS")
                    server.starttls()

            if self.username and self.password:
                server.login(self.username, self.password)

            # Build full recipient list (To + Cc + Bcc) for the envelope
            all_recipients = list(to_emails)
            if cc_emails:
                all_recipients.extend(cc_emails)
            if bcc_emails:
                all_recipients.extend(bcc_emails)

            server.sendmail(from_email, all_recipients, root.as_string())
            msg_id = root.get("Message-ID") or make_msgid()
            logger.info(f"SMTP email sent. Message-ID: {msg_id}")
            return msg_id

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth failed for {self.username}: {e}")
            raise ProviderError(f"SMTP Authentication Failed: {e}")
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP connect failed to {self.host}:{self.port}: {e}")
            raise ProviderError(f"SMTP Connection Failed: {e}")
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            raise ProviderError(f"SMTP sending failed: {e}")
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _build_inline_image(self, img) -> MIMEImage:
        """
        Builds a MIMEImage part for a CID-embedded inline image.

        The HTML template references it as: <img src="cid:company_logo">
        This attaches it with Content-ID: <company_logo> so email clients
        display it inline without needing an external URL.
        """
        if img.file_path:
            with open(img.file_path, "rb") as f:
                data = f.read()
            filename = img.filename or img.file_path.split("/")[-1].split("\\")[-1]
            content_type = img.content_type or (mimetypes.guess_type(img.file_path)[0] or "image/png")
        elif img.content_base64:
            data = base64.b64decode(img.content_base64)
            filename = img.filename or f"{img.cid}.png"
            content_type = img.content_type or "image/png"
        else:
            raise ProviderError(f"InlineImage '{img.cid}' has no file_path or content_base64.")

        subtype = content_type.split("/")[-1] if "/" in content_type else "png"
        mime_img = MIMEImage(data, _subtype=subtype)
        mime_img.add_header("Content-ID", f"<{img.cid}>")
        mime_img.add_header("Content-Disposition", "inline", filename=filename)
        return mime_img

    def _build_attachment(self, att: PreparedAttachment) -> MIMEBase:
        """
        Builds a MIMEBase part for a regular (downloadable) file attachment.
        """
        maintype, subtype = "application", "octet-stream"
        if "/" in att.content_type:
            maintype, subtype = att.content_type.split("/", 1)

        part = MIMEBase(maintype, subtype)
        part.set_payload(att.content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=att.filename)
        return part
