"""
SyncRivo Email SDK
==================

A lightweight Python SDK for integrating with the SyncRivo Centralized Email Service.
Zero external dependencies — uses Python's built-in urllib.

Quick Start:
    from syncrivo_email_sdk import SyncRivoEmailClient

    client = SyncRivoEmailClient(
        base_url="http://email-service:8000",
        api_key="srk_your_key_here",
        service_name="crm",
    )

    client.send_demo_booking(
        customer_name="Arjun Mehta",
        customer_email="arjun@example.com",
        demo_date="Monday, June 2, 2026",
        demo_time="3:00 PM IST",
        meeting_link="https://meet.google.com/abc-xyz",
        host_name="Priya Sharma",
        host_email="priya@syncrivo.ai",
    )
"""

from syncrivo_email_sdk.client import SyncRivoEmailClient
from syncrivo_email_sdk.models import (
    EmailPayload,
    BulkEmailPayload,
    Attachment,
    InlineImage,
)
from syncrivo_email_sdk.exceptions import (
    SyncRivoEmailError,
    AuthenticationError,
    ValidationError,
    RateLimitError,
    ServiceUnavailableError,
    TemplateError,
)

__all__ = [
    "SyncRivoEmailClient",
    "EmailPayload",
    "BulkEmailPayload",
    "Attachment",
    "InlineImage",
    "SyncRivoEmailError",
    "AuthenticationError",
    "ValidationError",
    "RateLimitError",
    "ServiceUnavailableError",
    "TemplateError",
]

__version__ = "1.0.0"
__author__ = "SyncRivo Engineering Team"
