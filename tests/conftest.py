import os
import shutil
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.template_engine import TemplateEngine


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Sets up environment configurations for testing.
    """
    settings.EMAIL_PROVIDER = "smtp"
    settings.SMTP_HOST = "localhost"
    settings.SMTP_PORT = 1025
    settings.SMTP_USERNAME = "test_user"
    settings.SMTP_PASSWORD = "test_password"
    settings.SMTP_USE_SSL = False
    settings.SMTP_USE_TLS = False
    settings.DEFAULT_SENDER_EMAIL = "sender@example.com"
    settings.MAX_ATTACHMENT_SIZE_MB = 1.0
    settings.MAX_TOTAL_ATTACHMENT_SIZE_MB = 2.0
    settings.ENABLE_MONGO_LOGGING = False
    settings.ENABLE_MONGO_TEMPLATES = False
    yield


@pytest.fixture
def temp_template_dir(tmp_path):
    """
    Creates a temporary directory for test templates.
    """
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    
    # Write test templates
    welcome_tmpl = templates_dir / "welcome.html"
    welcome_tmpl.write_text("Hello {{ username }}, welcome to {{ app_name }}!")
    
    bad_tmpl = templates_dir / "bad.html"
    bad_tmpl.write_text("Hello {{ username } {% if %}") # Syntax error
    
    return str(templates_dir)


@pytest.fixture
def test_template_engine(temp_template_dir):
    return TemplateEngine(template_dir=temp_template_dir)


@pytest.fixture
def test_client():
    return TestClient(app)
