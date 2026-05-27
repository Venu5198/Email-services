"""
SyncRivo Email SDK — HTTP Client

Usage:
    from syncrivo_email_sdk import SyncRivoEmailClient

    client = SyncRivoEmailClient(
        base_url="http://localhost:8000",
        api_key="srk_your_service_key_here",
        service_name="crm",
    )

    # Send a demo booking confirmation
    client.send_demo_booking(
        customer_name="Rajesh Kumar",
        customer_email="rajesh@example.com",
        demo_date="Monday, June 2, 2026",
        demo_time="3:00 PM IST",
        meeting_link="https://meet.google.com/abc-xyz",
        host_name="Priya Sharma",
        host_email="priya@syncrivo.ai",
    )

    # Send a bulk campaign
    client.send_bulk(
        recipient_collection="contacts",
        template_name="newsletter.html",
        subject="🚀 SyncRivo Monthly Update",
        initiated_by="crm",
    )
"""
import json
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any

from syncrivo_email_sdk.models import EmailPayload, BulkEmailPayload
from syncrivo_email_sdk.exceptions import (
    AuthenticationError,
    ValidationError,
    RateLimitError,
    ServiceUnavailableError,
    SyncRivoEmailError,
)

try:
    import urllib.error as _ue
    ConnectionError = _ue.URLError
except Exception:
    pass


class SyncRivoEmailClient:
    """
    HTTP client for the SyncRivo Centralized Email Service.

    Provides typed methods for all business email operations:
    - Demo lifecycle (booked, rescheduled, cancelled, reminders)
    - Customer inquiry auto-replies
    - Internal incident/support alerts
    - Form submission acknowledgments
    - High-volume bulk campaigns
    - Generic transactional emails
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        service_name: str = "unknown",
        timeout: int = 30,
    ):
        """
        Args:
            base_url:     Base URL of the email service (no trailing slash).
            api_key:      Service API key (srk_...) from admin panel.
            service_name: Identifies this microservice in logs.
            timeout:      HTTP request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.service_name = service_name
        self.timeout = timeout

    # -----------------------------------------------------------------------
    # Internal HTTP helper
    # -----------------------------------------------------------------------

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        """Makes an authenticated HTTP request to the email service."""
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
            "X-Service-Name": self.service_name,
        }

        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}

        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                detail = json.loads(raw).get("detail", raw)
            except Exception:
                detail = raw

            if e.code == 401:
                raise AuthenticationError("Missing API key.", status_code=401, detail=detail)
            elif e.code == 403:
                raise AuthenticationError("Invalid or revoked API key.", status_code=403, detail=detail)
            elif e.code == 422:
                raise ValidationError(f"Validation error: {detail}", status_code=422, detail=detail)
            elif e.code == 429:
                raise RateLimitError("Email quota exhausted.", status_code=429, detail=detail)
            elif e.code == 503:
                raise ServiceUnavailableError("Email service unavailable.", status_code=503, detail=detail)
            else:
                raise SyncRivoEmailError(f"HTTP {e.code}: {detail}", status_code=e.code, detail=detail)

        except urllib.error.URLError as e:
            raise SyncRivoEmailError(f"Cannot connect to email service at {self.base_url}: {e}")

    # -----------------------------------------------------------------------
    # Generic send
    # -----------------------------------------------------------------------

    def send(self, payload: EmailPayload) -> dict:
        """Sends a transactional email synchronously."""
        return self._request("POST", "/api/v1/send", payload.to_dict())

    def send_async(self, payload: EmailPayload) -> dict:
        """Queues a transactional email asynchronously (returns immediately)."""
        return self._request("POST", "/api/v1/send-async", payload.to_dict())

    # -----------------------------------------------------------------------
    # Demo lifecycle
    # -----------------------------------------------------------------------

    def send_demo_booking(
        self,
        customer_name: str,
        customer_email: str,
        demo_date: str,
        demo_time: str,
        meeting_link: str,
        host_name: str,
        host_email: str,
        meeting_id: Optional[str] = None,
        calendar_link: Optional[str] = None,
        reschedule_link: Optional[str] = None,
        cancel_link: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
    ) -> dict:
        """Sends a demo booking confirmation email to the customer."""
        return self._request("POST", "/api/v1/demo/booked", {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "demo_date": demo_date,
            "demo_time": demo_time,
            "meeting_link": meeting_link,
            "host_name": host_name,
            "host_email": host_email,
            "meeting_id": meeting_id,
            "calendar_link": calendar_link,
            "reschedule_link": reschedule_link,
            "cancel_link": cancel_link,
            "cc_emails": cc_emails,
        })

    def send_demo_rescheduled(
        self,
        customer_name: str,
        customer_email: str,
        old_demo_date: str,
        old_demo_time: str,
        new_demo_date: str,
        new_demo_time: str,
        meeting_link: str,
        host_name: Optional[str] = None,
        calendar_link: Optional[str] = None,
        cancel_link: Optional[str] = None,
    ) -> dict:
        """Sends a demo reschedule notification to the customer."""
        return self._request("POST", "/api/v1/demo/rescheduled", {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "old_demo_date": old_demo_date,
            "old_demo_time": old_demo_time,
            "new_demo_date": new_demo_date,
            "new_demo_time": new_demo_time,
            "meeting_link": meeting_link,
            "host_name": host_name,
            "calendar_link": calendar_link,
            "cancel_link": cancel_link,
        })

    def send_demo_cancelled(
        self,
        customer_name: str,
        customer_email: str,
        demo_date: str,
        demo_time: str,
        rebook_link: Optional[str] = None,
    ) -> dict:
        """Sends a demo cancellation confirmation to the customer."""
        return self._request("POST", "/api/v1/demo/cancelled", {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "demo_date": demo_date,
            "demo_time": demo_time,
            "rebook_link": rebook_link,
        })

    def send_demo_reminder(
        self,
        customer_name: str,
        customer_email: str,
        demo_date: str,
        demo_time: str,
        meeting_link: str,
        reminder_type: str = "24h",
        host_name: Optional[str] = None,
        reschedule_link: Optional[str] = None,
    ) -> dict:
        """Sends a 24h or 1h demo reminder to the customer."""
        return self._request("POST", "/api/v1/demo/reminder", {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "demo_date": demo_date,
            "demo_time": demo_time,
            "meeting_link": meeting_link,
            "reminder_type": reminder_type,
            "host_name": host_name,
            "reschedule_link": reschedule_link,
        })

    # -----------------------------------------------------------------------
    # Customer inquiries & forms
    # -----------------------------------------------------------------------

    def send_inquiry_acknowledgment(
        self,
        customer_name: str,
        customer_email: str,
        ticket_id: str,
        inquiry_type: str = "general",
        priority: str = "medium",
        expected_response_hours: int = 24,
    ) -> dict:
        """Sends an auto-reply acknowledgment for a customer inquiry."""
        return self._request("POST", "/api/v1/inquiry/acknowledge", {
            "customer_name": customer_name,
            "customer_email": customer_email,
            "ticket_id": ticket_id,
            "inquiry_type": inquiry_type,
            "priority": priority,
            "expected_response_hours": expected_response_hours,
        })

    def send_form_acknowledgment(
        self,
        form_type: str,
        submitter_name: str,
        submitter_email: str,
        submission_id: str,
        message_preview: Optional[str] = None,
    ) -> dict:
        """Sends a form submission acknowledgment email."""
        return self._request("POST", "/api/v1/forms/acknowledge", {
            "form_type": form_type,
            "submitter_name": submitter_name,
            "submitter_email": submitter_email,
            "submission_id": submission_id,
            "message_preview": message_preview,
        })

    # -----------------------------------------------------------------------
    # Internal support alerts
    # -----------------------------------------------------------------------

    def send_support_alert(
        self,
        incident_id: str,
        severity: str,
        title: str,
        description: str,
        affected_service: str,
        reported_by: str,
        notify_emails: Optional[List[str]] = None,
        environment: str = "Production",
        action_items: Optional[List[str]] = None,
        is_confidential: bool = False,
    ) -> dict:
        """Sends an internal incident alert to the SyncRivo support team."""
        return self._request("POST", "/api/v1/internal/support-notify", {
            "incident_id": incident_id,
            "severity": severity,
            "title": title,
            "description": description,
            "affected_service": affected_service,
            "reported_by": reported_by,
            "notify_emails": notify_emails or ["support@syncrivo.ai"],
            "environment": environment,
            "action_items": action_items or [],
            "is_confidential": is_confidential,
        })

    # -----------------------------------------------------------------------
    # Bulk sending
    # -----------------------------------------------------------------------

    def send_bulk(
        self,
        recipient_collection: Optional[str] = None,
        recipient_query: Optional[Dict[str, Any]] = None,
        to_emails: Optional[List[str]] = None,
        template_name: Optional[str] = None,
        subject: Optional[str] = None,
        subject_template: Optional[str] = None,
        template_context: Optional[Dict[str, Any]] = None,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        batch_size: int = 500,
        delay_between_batches_seconds: float = 1.0,
        is_confidential: bool = False,
        initiated_by: Optional[str] = None,
    ) -> dict:
        """
        Queues a bulk email campaign. Returns immediately with a job ID.
        Use get_bulk_job_status(job_id) to monitor progress.
        """
        payload = BulkEmailPayload(
            recipient_source="mongodb" if recipient_collection else "list",
            recipient_collection=recipient_collection,
            recipient_query=recipient_query,
            to_emails=to_emails,
            template_name=template_name,
            subject=subject,
            subject_template=subject_template,
            template_context=template_context or {},
            body_text=body_text,
            body_html=body_html,
            batch_size=batch_size,
            delay_between_batches_seconds=delay_between_batches_seconds,
            is_confidential=is_confidential,
            initiated_by=initiated_by or self.service_name,
        )
        return self._request("POST", "/api/v1/bulk-send", payload.to_dict())

    def get_bulk_job_status(self, job_id: str) -> dict:
        """Fetches the current status of a bulk email job."""
        return self._request("GET", f"/api/v1/bulk-send/{job_id}/status")

    # -----------------------------------------------------------------------
    # Health check
    # -----------------------------------------------------------------------

    def health_check(self) -> dict:
        """Checks if the email service is running and healthy."""
        return self._request("GET", "/health")
