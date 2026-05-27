from abc import ABC, abstractmethod
from typing import List, Optional
from app.services.attachment_handler import PreparedAttachment


class BaseEmailProvider(ABC):
    """
    Abstract Base Class representing an email delivery provider.
    """

    @abstractmethod
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
        Sends the email using the configured backend.

        :param from_email:     Sender email address
        :param to_emails:      List of recipient email addresses
        :param subject:        Email subject line (UTF-8 / emoji supported)
        :param body_text:      Plain text version of email
        :param body_html:      HTML version of email (optional)
        :param cc_emails:      CC recipient email addresses (optional)
        :param bcc_emails:     BCC recipient email addresses (optional)
        :param attachments:    List of prepared attachments (optional)
        :param is_confidential: Whether the email is confidential/sensitive
        :param from_name:      Display name in From header (optional)
        :param inline_images:  List of InlineImageSchema for CID embedding (optional)
        :return: string representation of the message ID or confirmation from provider
        :raises ProviderError: If the provider fails to send the email
        """
        pass
