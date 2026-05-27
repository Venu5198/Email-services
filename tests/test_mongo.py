import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.exceptions import ValidationError


@pytest.fixture
def mock_mongo():
    with patch("app.main.mongo_client") as mock_client, \
         patch("app.utils.mongo_client.mongo_client") as mock_global_client:
        mock_client.is_connected = True
        mock_global_client.is_connected = True
        
        # Store distinct mocks for each collection name
        collections = {}
        def get_mock_collection(name):
            if name not in collections:
                collections[name] = MagicMock(name=f"mock_coll_{name}")
            return collections[name]
        
        mock_client.get_collection.side_effect = get_mock_collection
        mock_global_client.get_collection.side_effect = get_mock_collection
        
        mock_db = MagicMock()
        mock_db.__getitem__.side_effect = get_mock_collection
        mock_client.db = mock_db
        mock_global_client.db = mock_db
        
        class MockMongoHelper:
            def __getitem__(self, name):
                return get_mock_collection(name)
                
        yield MockMongoHelper()


def test_api_create_template_success(mock_mongo, test_client):
    mock_coll = mock_mongo["email_templates"]
    
    payload = {
        "template_name": "db_welcome",
        "subject_template": "Welcome, {{ username }}!",
        "body_html": "<h1>Hello {{ username }}</h1>",
        "body_text": "Hello {{ username }}"
    }
    
    response = test_client.post("/api/v1/templates", json=payload)
    assert response.status_code == 201
    assert "saved successfully" in response.json()["message"]
    mock_coll.update_one.assert_called_once()


def test_api_get_template_success(mock_mongo, test_client):
    mock_coll = mock_mongo["email_templates"]
    mock_coll.find_one.return_value = {
        "template_name": "db_welcome",
        "subject_template": "Welcome, {{ username }}!",
        "body_html": "<h1>Hello {{ username }}</h1>",
        "body_text": "Hello {{ username }}"
    }
    
    response = test_client.get("/api/v1/templates/db_welcome")
    assert response.status_code == 200
    data = response.json()
    assert data["template_name"] == "db_welcome"
    assert data["subject_template"] == "Welcome, {{ username }}!"


def test_api_delete_template_success(mock_mongo, test_client):
    mock_coll = mock_mongo["email_templates"]
    mock_coll.delete_one.return_value.deleted_count = 1
    
    response = test_client.delete("/api/v1/templates/db_welcome")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]


def test_api_add_suppression_success(mock_mongo, test_client):
    mock_coll = mock_mongo["suppressions"]
    
    payload = {
        "email": "blocked@example.com",
        "reason": "unsubscribe"
    }
    
    response = test_client.post("/api/v1/suppressions", json=payload)
    assert response.status_code == 201
    assert "added to suppression list" in response.json()["message"]
    mock_coll.update_one.assert_called_once()


def test_api_list_suppressions(mock_mongo, test_client):
    mock_coll = mock_mongo["suppressions"]
    from datetime import datetime, timezone
    mock_coll.find.return_value.skip.return_value.limit.return_value = [
        {"email": "blocked@example.com", "reason": "bounce", "created_at": datetime.now(timezone.utc)}
    ]
    
    response = test_client.get("/api/v1/suppressions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["email"] == "blocked@example.com"


@patch("app.services.providers.smtp.SmtpEmailProvider.send")
def test_email_service_suppression_blocks_send(mock_smtp_send, mock_mongo, test_client):
    # Enable Mongo Logging so check runs
    with patch("app.services.email_service.settings") as mock_settings:
        mock_settings.ENABLE_MONGO_LOGGING = True
        mock_settings.EMAIL_PROVIDER = "smtp"
        mock_settings.RETRY_ATTEMPTS = 1
        
        mock_suppressions = mock_mongo["suppressions"]
        # Find matches for blocked@example.com
        mock_suppressions.find.return_value = [{"email": "blocked@example.com", "reason": "unsubscribe"}]
        
        # Setup logging collection to mock insert/update
        mock_logs = mock_mongo["email_logs"]
        mock_logs.insert_one.return_value.inserted_id = "some_log_id"

        payload = {
            "to_emails": "blocked@example.com",
            "subject": "Suppression Test",
            "body_text": "This should be blocked"
        }
        
        response = test_client.post("/api/v1/send", json=payload)
        assert response.status_code == 400
        assert "suppressed" in response.json()["detail"]
        mock_smtp_send.assert_not_called()


@patch("app.services.providers.smtp.SmtpEmailProvider.send")
def test_email_service_recipient_sourcing_from_mongo(mock_smtp_send, mock_mongo, test_client):
    # Enable Mongo Logging so check runs
    with patch("app.services.email_service.settings") as mock_settings:
        mock_settings.ENABLE_MONGO_LOGGING = True
        mock_settings.ENABLE_MONGO_TEMPLATES = False
        mock_settings.EMAIL_PROVIDER = "smtp"
        mock_settings.RETRY_ATTEMPTS = 1
        mock_smtp_send.return_value = "msg-db-sourcing"
        
        # Mock sample contact collection with dynamic fields
        mock_contacts = mock_mongo["sample contact"]
        mock_contacts.find.return_value = [
            {"email": "contact1@example.com", "role": "admin", "country": "Canada"},
            {"email": "contact2@example.com", "role": "user", "country": "India"}
        ]
        
        # Setup logging collection to mock insert/update
        mock_logs = mock_mongo["email_logs"]
        mock_logs.insert_one.return_value.inserted_id = "some_log_id"
        
        mock_suppressions = mock_mongo["suppressions"]
        mock_suppressions.find.return_value = []
        mock_suppressions.find_one.return_value = None

        payload = {
            "recipient_source": "mongodb",
            "recipient_collection": "sample contact",
            "subject_template": "Hello {{ role }}",
            "template_name": "welcome.html",
            "template_context": {
                "app_name": "TestApp"
            }
        }
        
        response = test_client.post("/api/v1/send", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Sent 2 emails successfully" in data["message"]
        
        # Verify SMTP send was called separately for each recipient with personalized content
        assert mock_smtp_send.call_count == 2
        
        # Check first call args
        first_call_args = mock_smtp_send.call_args_list[0][1]
        assert first_call_args["to_emails"] == ["contact1@example.com"]
        assert first_call_args["subject"] == "Hello admin"
        assert "Hello contact1" in first_call_args["body_html"]
        assert "TestApp" in first_call_args["body_html"]
        
        # Check second call args
        second_call_args = mock_smtp_send.call_args_list[1][1]
        assert second_call_args["to_emails"] == ["contact2@example.com"]
        assert second_call_args["subject"] == "Hello user"
        assert "Hello contact2" in second_call_args["body_html"]
        assert "TestApp" in second_call_args["body_html"]
