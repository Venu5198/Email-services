from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class DemoBookingRequest(BaseModel):
    """Schema for a new demo booking notification email."""
    customer_name: str = Field(..., description="Customer's full name.")
    customer_email: EmailStr = Field(..., description="Customer's email address.")
    demo_date: str = Field(..., description="Human-readable date, e.g. 'Monday, June 2, 2026'.")
    demo_time: str = Field(..., description="Human-readable time with timezone, e.g. '3:00 PM IST'.")
    meeting_link: str = Field(..., description="Video meeting URL.")
    host_name: str = Field(..., description="Name of the SyncRivo host/specialist.")
    host_email: EmailStr = Field(..., description="Email of the host.")
    meeting_id: Optional[str] = Field(default=None, description="Optional meeting ID shown to recipient.")
    calendar_link: Optional[str] = Field(default=None, description="Google/Outlook calendar add link.")
    reschedule_link: Optional[str] = Field(default=None, description="URL to reschedule the demo.")
    cancel_link: Optional[str] = Field(default=None, description="URL to cancel the demo.")
    cc_emails: Optional[List[EmailStr]] = Field(default=None, description="Optional CC recipients.")


class DemoRescheduleRequest(BaseModel):
    """Schema for a demo rescheduling notification email."""
    customer_name: str = Field(..., description="Customer's full name.")
    customer_email: EmailStr = Field(..., description="Customer's email address.")
    old_demo_date: str = Field(..., description="Previous demo date.")
    old_demo_time: str = Field(..., description="Previous demo time.")
    new_demo_date: str = Field(..., description="New rescheduled demo date.")
    new_demo_time: str = Field(..., description="New rescheduled demo time.")
    meeting_link: str = Field(..., description="Video meeting URL (usually unchanged).")
    host_name: Optional[str] = Field(default=None, description="Name of the host.")
    calendar_link: Optional[str] = Field(default=None, description="Updated calendar link.")
    cancel_link: Optional[str] = Field(default=None, description="URL to cancel the demo.")
    cc_emails: Optional[List[EmailStr]] = Field(default=None)


class DemoCancelRequest(BaseModel):
    """Schema for a demo cancellation notification email."""
    customer_name: str = Field(..., description="Customer's full name.")
    customer_email: EmailStr = Field(..., description="Customer's email address.")
    demo_date: str = Field(..., description="The date of the cancelled demo.")
    demo_time: str = Field(..., description="The time of the cancelled demo.")
    rebook_link: Optional[str] = Field(default=None, description="URL to book a new demo.")
    cc_emails: Optional[List[EmailStr]] = Field(default=None)


class DemoReminderRequest(BaseModel):
    """Schema for demo reminder emails (24h or 1h before)."""
    customer_name: str = Field(..., description="Customer's full name.")
    customer_email: EmailStr = Field(..., description="Customer's email address.")
    demo_date: str = Field(..., description="Demo date.")
    demo_time: str = Field(..., description="Demo time.")
    meeting_link: str = Field(..., description="Video meeting URL.")
    host_name: Optional[str] = Field(default=None)
    reschedule_link: Optional[str] = Field(default=None)
    reminder_type: str = Field(default="24h", description="'24h' or '1h'.")


class InquiryAcknowledgeRequest(BaseModel):
    """Schema for auto-reply to priority customer inquiries."""
    customer_name: str = Field(..., description="Customer's full name.")
    customer_email: EmailStr = Field(..., description="Customer's email address.")
    ticket_id: str = Field(..., description="Unique reference/ticket ID.")
    inquiry_type: str = Field(default="general", description="Type: sales, support, billing, general.")
    priority: str = Field(default="medium", description="Priority: high, medium, low.")
    expected_response_hours: int = Field(default=24, description="Expected SLA response hours.")


class SupportNotifyRequest(BaseModel):
    """Schema for notifying the SyncRivo support team of incidents or service requests."""
    incident_id: str = Field(..., description="Unique incident/request identifier.")
    severity: str = Field(..., description="Severity level: critical, high, medium, low.")
    title: str = Field(..., description="Short incident title.")
    description: str = Field(..., description="Detailed description of the incident.")
    affected_service: str = Field(..., description="Name of the affected service.")
    reported_by: str = Field(..., description="Who reported the incident.")
    notify_emails: List[EmailStr] = Field(
        default=["support@syncrivo.ai"],
        description="Team email addresses to notify."
    )
    environment: Optional[str] = Field(default="Production", description="e.g. Production, Staging.")
    action_items: Optional[List[str]] = Field(default=None, description="List of immediate actions required.")
    reported_at: Optional[str] = Field(default=None, description="Timestamp of the incident.")
    is_confidential: bool = Field(default=False, description="Mark as confidential internal alert.")
    cc_emails: Optional[List[EmailStr]] = Field(default=None)


class FormAcknowledgeRequest(BaseModel):
    """Schema for acknowledging form submissions from the SyncRivo website."""
    form_type: str = Field(
        ...,
        description="Form type: contact, feedback, partner, demo_request."
    )
    submitter_name: str = Field(..., description="Name of the person who submitted the form.")
    submitter_email: EmailStr = Field(..., description="Email of the form submitter.")
    submission_id: str = Field(..., description="Unique submission reference ID.")
    message_preview: Optional[str] = Field(
        default=None,
        description="Optional short preview of the submitted message (shown in email)."
    )
