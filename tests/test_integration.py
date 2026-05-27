import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.exceptions import ProviderError


def test_health_check_endpoint(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@patch("app.services.providers.smtp.SmtpEmailProvider.send")
def test_send_email_sync_success(mock_send, test_client):
    mock_send.return_value = "msg-12345"

    payload = {
        "to_emails": "recipient@example.com",
        "subject": "Integration Test Sync",
        "body_text": "This is a integration test."
    }

    response = test_client.post("/api/v1/send", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message_id"] == "msg-12345"
    assert data["provider_used"] == "smtp"


@patch("app.services.providers.smtp.SmtpEmailProvider.send")
def test_send_email_async_queued(mock_send, test_client):
    mock_send.return_value = "msg-async"

    payload = {
        "to_emails": ["recipient1@example.com", "recipient2@example.com"],
        "subject": "Integration Test Async",
        "body_text": "This is a integration background test."
    }

    response = test_client.post("/api/v1/send-async", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["success"] is True
    assert "queued" in data["message"]
    assert data["provider_used"] == "smtp"


@patch("app.services.providers.smtp.SmtpEmailProvider.send")
def test_send_email_validation_failure(mock_send, test_client):
    # Empty to_emails list
    payload = {
        "to_emails": [],
        "subject": "Missing recipients",
        "body_text": "Hello"
    }

    response = test_client.post("/api/v1/send", json=payload)
    assert response.status_code == 422 # Pydantic ValidationError returns 422 in FastAPI for request validation
    assert "to_emails" in response.text


@patch("app.services.providers.smtp.SmtpEmailProvider.send")
def test_send_email_provider_failure(mock_send, test_client):
    mock_send.side_effect = ProviderError("SMTP server down")

    payload = {
        "to_emails": "recipient@example.com",
        "subject": "Delivery failure test",
        "body_text": "Hello"
    }

    response = test_client.post("/api/v1/send", json=payload)
    assert response.status_code == 502
    data = response.json()
    assert data["error"] == "ProviderError"
    assert "Delivery backend failure" in data["detail"]
