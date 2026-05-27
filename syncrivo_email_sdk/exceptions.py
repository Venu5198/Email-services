"""
SyncRivo Email SDK — Exceptions
"""


class SyncRivoEmailError(Exception):
    """Base exception for all SyncRivo Email SDK errors."""
    def __init__(self, message: str, status_code: int = None, detail: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail

    def __str__(self):
        base = super().__str__()
        if self.status_code:
            return f"[HTTP {self.status_code}] {base}"
        return base


class AuthenticationError(SyncRivoEmailError):
    """Raised when the API key is missing or rejected (401/403)."""
    pass


class ValidationError(SyncRivoEmailError):
    """Raised when the request payload fails validation (422)."""
    pass


class RateLimitError(SyncRivoEmailError):
    """Raised when the email quota is exhausted (429)."""
    pass


class ServiceUnavailableError(SyncRivoEmailError):
    """Raised when the email service is temporarily unavailable (503)."""
    pass


class TemplateError(SyncRivoEmailError):
    """Raised when a template rendering error occurs."""
    pass


class ConnectionError(SyncRivoEmailError):
    """Raised when the SDK cannot reach the email service."""
    pass
