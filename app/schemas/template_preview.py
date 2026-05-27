from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class TemplatePreviewRequest(BaseModel):
    """
    Renders a Jinja2 template with the provided context and returns the
    rendered HTML/text WITHOUT sending any email.
    Useful for previewing templates before a bulk campaign launch.
    """
    template_name: str = Field(
        ...,
        description="Jinja2 template filename (e.g. 'newsletter.html') or a MongoDB template name."
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs for all template placeholders."
    )
    subject_template: Optional[str] = Field(
        default=None,
        description="Optional Jinja2 string for subject preview (e.g. 'Hello {{ name }}')."
    )


class TemplatePreviewResponse(BaseModel):
    """Rendered template output returned without sending any email."""
    template_name: str
    rendered_subject: Optional[str] = None
    rendered_html: str
    rendered_text: Optional[str] = None
    variables_used: list[str] = []
