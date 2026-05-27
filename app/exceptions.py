class EmailServiceException(Exception):
    """Base exception for all email service errors."""
    pass


class ValidationError(EmailServiceException):
    """Raised when request data, addresses, or sizes fail validation checks."""
    pass


class TemplateError(EmailServiceException):
    """Raised when there is a syntax error or missing placeholders during rendering."""
    pass


class AttachmentError(EmailServiceException):
    """Raised when attachment processing fails (e.g., file not found, size limit exceeded)."""
    pass


class ProviderError(EmailServiceException):
    """Raised when email delivery fails on the third-party or SMTP provider side."""
    pass
