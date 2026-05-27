import re
from app.exceptions import ValidationError


def validate_header_injection(value: str) -> str:
    """
    Prevents SMTP Header Injection attacks by ensuring no newline characters exist in headers like Subject.
    """
    if not value:
        return value
    if "\r" in value or "\n" in value:
        raise ValueError("Header injection detected: Subject cannot contain newline characters.")
    return value


def sanitize_html_content(html: str) -> str:
    """
    Basic sanitization of HTML to strip dangerous script tags and inline events.
    In templates, Jinja2's autoescape=True takes care of safety, but for direct body_html,
    we sanitize it.
    """
    if not html:
        return html
    
    # Remove script blocks
    clean_html = re.sub(r"<script\b[^>]*>([\s\S]*?)<\/script>", "", html, flags=re.IGNORECASE)
    
    # Remove onclick, onload, etc. event handlers
    clean_html = re.sub(r"\bon[a-z]+\s*=\s*\"[^\"]*\"", "", clean_html, flags=re.IGNORECASE)
    clean_html = re.sub(r"\bon[a-z]+\s*=\s*'[^']*'", "", clean_html, flags=re.IGNORECASE)
    
    return clean_html
