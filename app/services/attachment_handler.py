import os
import base64
import mimetypes
import logging
from typing import List, Tuple
from app.config import settings
from app.exceptions import AttachmentError, ValidationError
from app.schemas.email import AttachmentSchema

logger = logging.getLogger("email_service")

# Allowed extensions based on requirements (PDF, CSV, TXT, Images, etc.)
ALLOWED_EXTENSIONS = {
    ".pdf", ".csv", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip"
}


class PreparedAttachment:
    """
    Standardized internal representation of an attachment.
    """
    def __init__(self, filename: str, content: bytes, content_type: str):
        self.filename = filename
        self.content = content
        self.content_type = content_type
        self.size_bytes = len(content)


class AttachmentHandler:
    """
    Handles validation, reading, and preprocessing of email attachments.
    """

    @staticmethod
    def validate_and_prepare(
        attachments: List[AttachmentSchema]
    ) -> List[PreparedAttachment]:
        """
        Parses list of AttachmentSchema, verifies sizes and formats, and returns list of PreparedAttachments.
        """
        if not attachments:
            return []

        prepared: List[PreparedAttachment] = []
        total_size = 0.0
        max_file_size_bytes = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
        max_total_size_bytes = settings.MAX_TOTAL_ATTACHMENT_SIZE_MB * 1024 * 1024

        for att in attachments:
            filename: str = ""
            content: bytes = b""
            content_type: str = ""

            # Case 1: Local File Path
            if att.file_path:
                if not os.path.isfile(att.file_path):
                    logger.error(f"Attachment file not found: {att.file_path}")
                    raise AttachmentError(f"Attachment file does not exist: {att.file_path}")

                filename = os.path.basename(att.file_path)
                
                # Check extension validation
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    raise ValidationError(
                        f"Unsupported file format '{ext}' for file '{filename}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
                    )

                # Check individual file size
                file_size = os.path.getsize(att.file_path)
                if file_size > max_file_size_bytes:
                    raise AttachmentError(
                        f"Attachment '{filename}' exceeds individual size limit of {settings.MAX_ATTACHMENT_SIZE_MB}MB."
                    )

                # Read content
                try:
                    with open(att.file_path, "rb") as f:
                        content = f.read()
                except Exception as e:
                    logger.error(f"Failed to read attachment file '{att.file_path}': {e}")
                    raise AttachmentError(f"Failed to read attachment file '{filename}': {e}")

                # Guess content type
                guess, _ = mimetypes.guess_type(att.file_path)
                content_type = guess or "application/octet-stream"

            # Case 2: In-Memory / Base64 Content
            elif att.content_base64:
                filename = att.filename or "attachment"
                
                # Check extension validation
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    raise ValidationError(
                        f"Unsupported file format '{ext}' for file '{filename}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
                    )

                try:
                    content = base64.b64decode(att.content_base64)
                except Exception as e:
                    raise ValidationError(f"Invalid base64 payload for attachment '{filename}': {e}")

                # Check size
                file_size = len(content)
                if file_size > max_file_size_bytes:
                    raise AttachmentError(
                        f"Attachment '{filename}' exceeds individual size limit of {settings.MAX_ATTACHMENT_SIZE_MB}MB."
                    )

                # Set content type
                if att.content_type:
                    content_type = att.content_type
                else:
                    guess, _ = mimetypes.guess_type(filename)
                    content_type = guess or "application/octet-stream"

            total_size += len(content)
            if total_size > max_total_size_bytes:
                raise AttachmentError(
                    f"Total attachment size exceeds limit of {settings.MAX_TOTAL_ATTACHMENT_SIZE_MB}MB."
                )

            prepared.append(
                PreparedAttachment(
                    filename=filename, content=content, content_type=content_type
                )
            )

        return prepared
