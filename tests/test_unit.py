import pytest
import base64
from unittest.mock import MagicMock, patch
from pydantic import ValidationError as PydanticValidationError

from app.exceptions import ValidationError, TemplateError, AttachmentError, ProviderError
from app.schemas.email import EmailRequest, AttachmentSchema
from app.services.attachment_handler import AttachmentHandler
from app.services.template_engine import TemplateEngine
from app.services.email_service import EmailService


# ==========================================
# 1. Pydantic Request Validation Tests
# ==========================================

def test_email_request_coercion():
    # Coerces single string to list
    req = EmailRequest(
        to_emails="test@example.com",
        subject="Hello",
        body_text="Welcome"
    )
    assert req.to_emails == ["test@example.com"]

    # Coerces comma-separated string to multiple list entries
    req_comma = EmailRequest(
        to_emails="test1@example.com, test2@example.com,test3@example.com",
        subject="Hello",
        body_text="Welcome"
    )
    assert req_comma.to_emails == ["test1@example.com", "test2@example.com", "test3@example.com"]

    # Coerces list containing comma-separated strings
    req_list_comma = EmailRequest(
        to_emails=["test1@example.com", "test2@example.com, test3@example.com"],
        subject="Hello",
        body_text="Welcome"
    )
    assert req_list_comma.to_emails == ["test1@example.com", "test2@example.com", "test3@example.com"]


def test_email_request_invalid_email():
    with pytest.raises(PydanticValidationError):
        EmailRequest(
            to_emails="notanemail",
            subject="Hello",
            body_text="Welcome"
        )


def test_email_request_header_injection():
    # Subject contains newlines
    with pytest.raises(PydanticValidationError) as exc_info:
        EmailRequest(
            to_emails="test@example.com",
            subject="Hello\nInjection: True",
            body_text="Welcome"
        )
    assert "Header injection detected" in str(exc_info.value)


def test_email_request_missing_content():
    # Neither body_text, body_html, nor template_name
    with pytest.raises(PydanticValidationError) as exc_info:
        EmailRequest(
            to_emails="test@example.com",
            subject="Test"
        )
    assert "Either body_text, body_html, or template_name must be provided" in str(exc_info.value)


# ==========================================
# 2. Template Engine Tests
# ==========================================

def test_template_rendering_success(test_template_engine):
    html = test_template_engine.render_from_file(
        "welcome.html", {"username": "Venu", "app_name": "Emailer"}
    )
    assert html == "Hello Venu, welcome to Emailer!"


def test_template_rendering_missing_placeholders(test_template_engine):
    with pytest.raises(TemplateError) as exc_info:
        test_template_engine.render_from_file(
            "welcome.html", {"username": "Venu"}  # Missing app_name
        )
    assert "Missing required template placeholders" in str(exc_info.value)
    assert "app_name" in str(exc_info.value)


def test_template_syntax_error(test_template_engine):
    with pytest.raises(TemplateError) as exc_info:
        test_template_engine.render_from_file(
            "bad.html", {"username": "Venu"}
        )
    assert "Syntax error in template" in str(exc_info.value)


# ==========================================
# 3. Attachment Handler Tests
# ==========================================

def test_attachment_unsupported_format():
    att = AttachmentSchema(
        filename="malicious.exe",
        content_base64=base64.b64encode(b"dummy code").decode("utf-8")
    )
    with pytest.raises(ValidationError) as exc_info:
        AttachmentHandler.validate_and_prepare([att])
    assert "Unsupported file format" in str(exc_info.value)


def test_attachment_size_limit_exceeded():
    # Individual limit is configured as 1.0 MB in conftest setup_test_environment
    large_content = b"a" * (1024 * 1024 + 100) # Slightly over 1MB
    att = AttachmentSchema(
        filename="test.pdf",
        content_base64=base64.b64encode(large_content).decode("utf-8")
    )
    with pytest.raises(AttachmentError) as exc_info:
        AttachmentHandler.validate_and_prepare([att])
    assert "exceeds individual size limit" in str(exc_info.value)


def test_attachment_total_size_exceeded():
    # Total limit is 2.0 MB
    content = b"a" * (1024 * 1024 - 100) # Just under 1MB each
    att1 = AttachmentSchema(
        filename="doc1.pdf",
        content_base64=base64.b64encode(content).decode("utf-8")
    )
    att2 = AttachmentSchema(
        filename="doc2.pdf",
        content_base64=base64.b64encode(content).decode("utf-8")
    )
    att3 = AttachmentSchema(
        filename="doc3.pdf",
        content_base64=base64.b64encode(content).decode("utf-8")
    )
    # Sum is ~3MB, exceeding 2.0MB
    with pytest.raises(AttachmentError) as exc_info:
        AttachmentHandler.validate_and_prepare([att1, att2, att3])
    assert "Total attachment size exceeds limit" in str(exc_info.value)


# ==========================================
# 4. Email Service Retry Orchestration Tests
# ==========================================

@patch("app.services.providers.smtp.SmtpEmailProvider.send")
def test_email_service_retry_mechanism(mock_smtp_send, temp_template_dir):
    # Setup service pointing to test templates dir
    service = EmailService(template_dir=temp_template_dir)
    
    # Configure mock to fail twice with ProviderError and succeed on the third attempt
    mock_smtp_send.side_effect = [
        ProviderError("Timeout connection lost"),
        ProviderError("Timeout connection lost"),
        "smtp-success-msg-id"
    ]

    req = EmailRequest(
        to_emails="test@example.com",
        subject="Resiliency check",
        body_text="Testing retries",
        provider_override="smtp"
    )

    response = service.send_email(req)
    
    # Assertions
    assert response.success is True
    assert response.message_id == "smtp-success-msg-id"
    assert response.provider_used == "smtp"
    # Ensure send was called exactly 3 times (2 retries + 1 success)
    assert mock_smtp_send.call_count == 3
