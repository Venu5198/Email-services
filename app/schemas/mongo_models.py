from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class TemplateCreate(BaseModel):
    template_name: str = Field(..., description="Unique template name.")
    subject_template: str = Field(..., description="Jinja2 subject template.")
    body_html: str = Field(..., description="HTML body template.")
    body_text: Optional[str] = Field(default=None, description="Plain text body template.")


class TemplateResponse(BaseModel):
    template_name: str
    subject_template: str
    body_html: str
    body_text: Optional[str] = None


class SuppressionCreate(BaseModel):
    email: EmailStr = Field(..., description="Email address to suppress.")
    reason: str = Field(default="unsubscribe", description="Reason (unsubscribe, bounce, spam_complaint).")


class SuppressionResponse(BaseModel):
    email: EmailStr
    reason: str
    created_at: datetime
