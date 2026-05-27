import logging
from fastapi import APIRouter, status, HTTPException
from app.schemas.demo_email import (
    DemoBookingRequest,
    DemoRescheduleRequest,
    DemoCancelRequest,
    DemoReminderRequest,
    InquiryAcknowledgeRequest,
    SupportNotifyRequest,
    FormAcknowledgeRequest,
)
from app.schemas.email import EmailRequest
from app.services.email_service import EmailService

logger = logging.getLogger("email_service")
router = APIRouter(prefix="/api/v1", tags=["Business Emails"])

email_service = EmailService()


# ---------------------------------------------------------------------------
# Demo Lifecycle Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/demo/booked",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send Demo Booking Confirmation",
    description="Sends a branded booking confirmation email to the customer after a demo is scheduled.",
)
def send_demo_booked(req: DemoBookingRequest):
    """Triggers a demo booking confirmation email."""
    template_context = {
        "customer_name": req.customer_name,
        "demo_date": req.demo_date,
        "demo_time": req.demo_time,
        "meeting_link": req.meeting_link,
        "host_name": req.host_name,
        "host_email": req.host_email,
        "meeting_id": req.meeting_id or "",
        "calendar_link": req.calendar_link or "",
        "reschedule_link": req.reschedule_link or "",
        "cancel_link": req.cancel_link or "",
    }
    email_req = EmailRequest(
        to_emails=req.customer_email,
        cc_emails=",".join(req.cc_emails) if req.cc_emails else None,
        subject=f"✅ Your SyncRivo Demo is Confirmed — {req.demo_date}",
        template_name="demo_booking_confirm.html",
        template_context=template_context,
    )
    email_service.send_email(email_req)
    logger.info(f"Demo booking confirmation sent to {req.customer_email}")
    return {
        "success": True,
        "message": f"Demo booking confirmation sent to {req.customer_email}",
        "customer": req.customer_name,
        "demo_date": req.demo_date,
    }


@router.post(
    "/demo/rescheduled",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send Demo Reschedule Confirmation",
    description="Sends an updated appointment email when a demo is rescheduled.",
)
def send_demo_rescheduled(req: DemoRescheduleRequest):
    """Triggers a demo reschedule notification email."""
    template_context = {
        "customer_name": req.customer_name,
        "old_demo_date": req.old_demo_date,
        "old_demo_time": req.old_demo_time,
        "new_demo_date": req.new_demo_date,
        "new_demo_time": req.new_demo_time,
        "meeting_link": req.meeting_link,
        "host_name": req.host_name or "",
        "calendar_link": req.calendar_link or "",
        "cancel_link": req.cancel_link or "",
    }
    email_req = EmailRequest(
        to_emails=req.customer_email,
        cc_emails=",".join(req.cc_emails) if req.cc_emails else None,
        subject=f"🔄 Demo Rescheduled — New Time: {req.new_demo_date} at {req.new_demo_time}",
        template_name="demo_reschedule_confirm.html",
        template_context=template_context,
    )
    email_service.send_email(email_req)
    logger.info(f"Demo reschedule confirmation sent to {req.customer_email}")
    return {
        "success": True,
        "message": f"Demo reschedule confirmation sent to {req.customer_email}",
        "new_date": req.new_demo_date,
        "new_time": req.new_demo_time,
    }


@router.post(
    "/demo/cancelled",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send Demo Cancellation Confirmation",
    description="Notifies the customer that their demo has been cancelled and offers a re-booking link.",
)
def send_demo_cancelled(req: DemoCancelRequest):
    """Triggers a demo cancellation notification email."""
    template_context = {
        "customer_name": req.customer_name,
        "demo_date": req.demo_date,
        "demo_time": req.demo_time,
        "rebook_link": req.rebook_link or "https://syncrivo.ai/book-demo",
    }
    email_req = EmailRequest(
        to_emails=req.customer_email,
        cc_emails=",".join(req.cc_emails) if req.cc_emails else None,
        subject=f"Demo Cancelled — We Hope to See You Soon",
        template_name="demo_cancel_confirm.html",
        template_context=template_context,
    )
    email_service.send_email(email_req)
    logger.info(f"Demo cancellation confirmation sent to {req.customer_email}")
    return {
        "success": True,
        "message": f"Demo cancellation confirmation sent to {req.customer_email}",
    }


@router.post(
    "/demo/reminder",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send Demo Reminder",
    description="Sends a 24-hour or 1-hour reminder before the demo session.",
)
def send_demo_reminder(req: DemoReminderRequest):
    """Triggers a 24h or 1h demo reminder email."""
    if req.reminder_type == "1h":
        template_name = "demo_reminder_1h.html"
        subject = f"🔴 Your SyncRivo Demo Starts in 1 Hour — {req.demo_time}"
    else:
        template_name = "demo_reminder_24h.html"
        subject = f"⏰ Reminder: Your SyncRivo Demo is Tomorrow at {req.demo_time}"

    template_context = {
        "customer_name": req.customer_name,
        "demo_date": req.demo_date,
        "demo_time": req.demo_time,
        "meeting_link": req.meeting_link,
        "host_name": req.host_name or "",
        "reschedule_link": req.reschedule_link or "",
    }
    email_req = EmailRequest(
        to_emails=req.customer_email,
        subject=subject,
        template_name=template_name,
        template_context=template_context,
    )
    email_service.send_email(email_req)
    logger.info(f"Demo reminder ({req.reminder_type}) sent to {req.customer_email}")
    return {
        "success": True,
        "message": f"Demo {req.reminder_type} reminder sent to {req.customer_email}",
    }


# ---------------------------------------------------------------------------
# Inquiry Auto-Reply
# ---------------------------------------------------------------------------

@router.post(
    "/inquiry/acknowledge",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send Inquiry Auto-Reply",
    description="Sends an immediate acknowledgment email to a customer who submitted a priority inquiry.",
)
def send_inquiry_acknowledgment(req: InquiryAcknowledgeRequest):
    """Auto-replies to a customer inquiry with ticket ID and SLA info."""
    # High priority: send synchronously; medium/low: also sync here (caller decides background)
    template_context = {
        "customer_name": req.customer_name,
        "ticket_id": req.ticket_id,
        "inquiry_type": req.inquiry_type,
        "priority": req.priority,
        "expected_response_hours": req.expected_response_hours,
        "submitter_email": req.customer_email,
    }
    priority_label = {"high": "🔴 HIGH", "medium": "🟡 MEDIUM", "low": "🟢 LOW"}.get(
        req.priority.lower(), req.priority.upper()
    )
    email_req = EmailRequest(
        to_emails=req.customer_email,
        subject=f"We Received Your {req.inquiry_type.title()} Inquiry [{req.ticket_id}]",
        template_name="inquiry_auto_reply.html",
        template_context=template_context,
    )
    email_service.send_email(email_req)
    logger.info(f"Inquiry auto-reply sent to {req.customer_email} — ticket {req.ticket_id}, priority {priority_label}")
    return {
        "success": True,
        "message": f"Auto-reply sent to {req.customer_email}",
        "ticket_id": req.ticket_id,
        "priority": req.priority,
    }


# ---------------------------------------------------------------------------
# Internal Support Team Notifications
# ---------------------------------------------------------------------------

@router.post(
    "/internal/support-notify",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Notify Support Team",
    description="Sends an incident or service request alert to the SyncRivo support team at support@syncrivo.ai.",
)
def send_support_notification(req: SupportNotifyRequest):
    """Sends an internal incident/service alert to the support team."""
    template_context = {
        "incident_id": req.incident_id,
        "severity": req.severity.lower(),
        "title": req.title,
        "description": req.description,
        "affected_service": req.affected_service,
        "reported_by": req.reported_by,
        "environment": req.environment or "Production",
        "action_items": req.action_items or [],
        "reported_at": req.reported_at or "Now",
        "is_confidential": req.is_confidential,
    }
    to_addresses = ",".join([str(e) for e in req.notify_emails])
    cc_addresses = ",".join([str(e) for e in req.cc_emails]) if req.cc_emails else None

    severity_emoji = {"critical": "🚨", "high": "🔴", "medium": "🟡", "low": "🟢"}.get(
        req.severity.lower(), "⚠️"
    )
    email_req = EmailRequest(
        to_emails=to_addresses,
        cc_emails=cc_addresses,
        subject=f"{severity_emoji} [{req.severity.upper()}] Incident: {req.title} — {req.incident_id}",
        template_name="internal_incident_alert.html",
        template_context=template_context,
        is_confidential=req.is_confidential,
    )
    email_service.send_email(email_req)
    logger.info(
        f"Support team notified — incident {req.incident_id} severity={req.severity} "
        f"to {req.notify_emails}"
    )
    return {
        "success": True,
        "message": f"Support team notified about incident {req.incident_id}",
        "notified_emails": req.notify_emails,
        "severity": req.severity,
    }


# ---------------------------------------------------------------------------
# Form Submission Acknowledgment
# ---------------------------------------------------------------------------

@router.post(
    "/forms/acknowledge",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Acknowledge Form Submission",
    description="Sends a confirmation email to a user after they submit a SyncRivo form.",
)
def send_form_acknowledgment(req: FormAcknowledgeRequest):
    """Sends a form submission acknowledgment email."""
    template_context = {
        "submitter_name": req.submitter_name,
        "submitter_email": req.submitter_email,
        "form_type": req.form_type,
        "submission_id": req.submission_id,
        "message_preview": req.message_preview or "",
    }
    email_req = EmailRequest(
        to_emails=req.submitter_email,
        subject=f"✅ We Received Your {req.form_type.replace('_', ' ').title()} — SyncRivo",
        template_name="form_submission_ack.html",
        template_context=template_context,
    )
    email_service.send_email(email_req)
    logger.info(
        f"Form acknowledgment sent to {req.submitter_email} — "
        f"form_type={req.form_type}, submission_id={req.submission_id}"
    )
    return {
        "success": True,
        "message": f"Form acknowledgment sent to {req.submitter_email}",
        "submission_id": req.submission_id,
        "form_type": req.form_type,
    }
