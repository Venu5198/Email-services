import logging
from typing import List, Optional
from tenacity import Retrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.exceptions import ProviderError, ValidationError
from app.schemas.email import EmailRequest, EmailResponse
from app.services.attachment_handler import AttachmentHandler
from app.services.template_engine import TemplateEngine
from app.services.providers.base import BaseEmailProvider
from app.services.providers.smtp import SmtpEmailProvider
from app.services.providers.sendgrid import SendGridEmailProvider
from app.services.providers.ses import SesEmailProvider

logger = logging.getLogger("email_service")


class EmailService:
    """
    Main coordinator service for validating, rendering, and sending emails.
    """

    def __init__(self, template_dir: str = "app/templates"):
        self.template_engine = TemplateEngine(template_dir=template_dir)
        
        # Initialize providers
        self.providers = {
            "smtp": SmtpEmailProvider(),
            "sendgrid": SendGridEmailProvider(),
            "ses": SesEmailProvider(),
        }

    def _get_provider(self, provider_name: Optional[str]) -> BaseEmailProvider:
        """
        Resolves the appropriate email delivery provider based on settings or request override.
        """
        provider_key = (provider_name or settings.EMAIL_PROVIDER).lower()
        if provider_key not in self.providers:
            raise ValidationError(
                f"Unknown or unsupported email provider: '{provider_key}'. Allowed: {list(self.providers.keys())}"
            )
        return self.providers[provider_key]

    def send_email(self, request: EmailRequest) -> EmailResponse:
        """
        Orchestrates email sending workflow: validation, template rendering,
        attachment processing, provider selection, and retrying delivery on failures.
        """
        logger.info(f"Incoming email request to: {request.to_emails}")

        # 0. Load recipients from MongoDB if source is set
        recipient_docs = []
        if request.recipient_source == "mongodb":
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                raise ValidationError("MongoDB is not connected but is requested as recipient source.")
            
            coll_name = request.recipient_collection or "sample contact"
            coll = mongo_client.get_collection(coll_name)
            if coll is None:
                raise ValidationError(f"MongoDB collection '{coll_name}' is not accessible.")
            
            query = request.recipient_query or {}
            try:
                recipient_docs = list(coll.find(query))
                if not recipient_docs:
                    raise ValidationError(f"No recipients found in MongoDB collection '{coll_name}' with query: {query}")
                request.to_emails = [doc["email"] for doc in recipient_docs if "email" in doc]
                logger.info(f"Loaded {len(recipient_docs)} recipient records from MongoDB collection '{coll_name}'")
            except ValidationError:
                raise
            except Exception as e:
                logger.error(f"Error querying recipients from collection '{coll_name}': {e}")
                raise ValidationError(f"Failed to query recipients from MongoDB: {e}")

        # 1. Resolve Provider
        provider = self._get_provider(request.provider_override)
        provider_name = request.provider_override or settings.EMAIL_PROVIDER

        # 2. Retrieve DB Template if enabled
        db_template = None
        if request.template_name and settings.ENABLE_MONGO_TEMPLATES:
            from app.utils.mongo_client import mongo_client
            templates_coll = mongo_client.get_collection("email_templates")
            if templates_coll is not None:
                try:
                    db_template = templates_coll.find_one({"template_name": request.template_name})
                except Exception as ex:
                    logger.error(f"Error querying templates from MongoDB: {ex}")

        # 3. Handle Attachments
        prepared_attachments = []
        if request.attachments:
            prepared_attachments = AttachmentHandler.validate_and_prepare(request.attachments)

        # 4. Determine Sender Address
        sender_email = settings.DEFAULT_SENDER_EMAIL

        # 5. Set up Retry Runner
        retryer = Retrying(
            stop=stop_after_attempt(settings.RETRY_ATTEMPTS),
            wait=wait_exponential(
                min=settings.RETRY_BACKOFF_MIN, max=settings.RETRY_BACKOFF_MAX
            ),
            retry=retry_if_exception_type(ProviderError),
            reraise=True,
        )

        # 6. Branch: Personalized Mail Merge Loop (MongoDB Source) vs Standard Send
        if request.recipient_source == "mongodb" and recipient_docs:
            sent_count = 0
            last_message_id = None
            
            for doc in recipient_docs:
                email_addr = doc.get("email")
                if not email_addr:
                    continue
                
                # Check suppression list
                if settings.ENABLE_MONGO_LOGGING:
                    from app.utils.mongo_client import mongo_client
                    suppressions_coll = mongo_client.get_collection("suppressions")
                    if suppressions_coll is not None:
                        try:
                            if suppressions_coll.find_one({"email": email_addr}):
                                logger.warning(f"Skipping suppressed recipient: {email_addr}")
                                continue
                        except Exception as ex:
                            logger.error(f"Error checking suppression list for {email_addr}: {ex}")

                # Build personalized template context
                personal_context = {
                    **request.template_context,
                    **{k: v for k, v in doc.items() if k != "_id"}
                }
                if "username" not in personal_context:
                    personal_context["username"] = doc.get("name") or email_addr.split("@")[0]

                # Render personalized content
                rendered_body_html = request.body_html
                rendered_body_text = request.body_text or ""

                if request.template_name:
                    if db_template:
                        body_html_source = db_template.get("body_html", "")
                        rendered_body_html = self.template_engine.render_from_string(
                            body_html_source, personal_context, request.template_name
                        )
                        if not rendered_body_text:
                            body_text_source = db_template.get("body_text", "")
                            if body_text_source:
                                rendered_body_text = self.template_engine.render_from_string(
                                    body_text_source, personal_context, request.template_name
                                )
                    else:
                        rendered_body_html = self.template_engine.render_from_file(
                            request.template_name, personal_context
                        )

                    if not rendered_body_text and rendered_body_html:
                        import re
                        clean = re.compile("<.*?>")
                        rendered_body_text = re.sub(clean, "", rendered_body_html).strip()

                # Render Subject
                rendered_subject = request.subject or ""
                if request.subject_template:
                    rendered_subject = self.template_engine.render_subject(
                        request.subject_template, personal_context
                    )
                elif not rendered_subject and db_template and db_template.get("subject_template"):
                    rendered_subject = self.template_engine.render_subject(
                        db_template["subject_template"], personal_context
                    )

                if not rendered_subject:
                    rendered_subject = "Important Update"

                # Log entry
                log_id = None
                logs_coll = None
                if settings.ENABLE_MONGO_LOGGING:
                    from app.utils.mongo_client import mongo_client
                    from datetime import datetime, timezone
                    logs_coll = mongo_client.get_collection("email_logs")
                    if logs_coll is not None:
                        log_entry = {
                            "recipients": [email_addr],
                            "cc": [],
                            "bcc": [],
                            "subject": rendered_subject,
                            "provider": provider_name,
                            "status": "sending",
                            "retry_count": 0,
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }
                        try:
                            result = logs_coll.insert_one(log_entry)
                            log_id = result.inserted_id
                        except Exception as ex:
                            logger.error(f"Failed to insert email log: {ex}")

                # Send
                try:
                    logger.info(f"Sending personalized email to {email_addr} via {provider_name}")
                    message_id = retryer(
                        provider.send,
                        from_email=sender_email,
                        to_emails=[email_addr],
                        subject=rendered_subject,
                        body_text=rendered_body_text,
                        body_html=rendered_body_html,
                        cc_emails=None,
                        bcc_emails=None,
                        attachments=prepared_attachments,
                        is_confidential=request.is_confidential,
                        from_name=request.from_name,
                        inline_images=request.inline_images,
                    )

                    if log_id and logs_coll is not None:
                        from datetime import datetime, timezone
                        try:
                            logs_coll.update_one(
                                {"_id": log_id},
                                {
                                    "$set": {
                                        "status": "sent",
                                        "message_id": message_id,
                                        "updated_at": datetime.now(timezone.utc)
                                    }
                                }
                            )
                        except Exception as ex:
                            logger.error(f"Failed to update email log to sent: {ex}")

                    last_message_id = message_id
                    sent_count += 1
                except Exception as e:
                    if log_id and logs_coll is not None:
                        from datetime import datetime, timezone
                        try:
                            logs_coll.update_one(
                                {"_id": log_id},
                                {
                                    "$set": {
                                        "status": "failed",
                                        "error_detail": str(e),
                                        "updated_at": datetime.now(timezone.utc)
                                    }
                                }
                            )
                        except Exception as ex:
                            logger.error(f"Failed to update email log to failed: {ex}")
                    logger.error(f"Personalized delivery failed to {email_addr}: {e}")

            return EmailResponse(
                success=True,
                message_id=last_message_id or "bulk-sourcing",
                provider_used=provider_name,
                message=f"Personalized mail merge completed. Sent {sent_count} emails successfully.",
            )

        # --- Standard Send Flow (Non-Bulk / Manual list) ---
        # Check Suppression List
        if settings.ENABLE_MONGO_LOGGING:
            from app.utils.mongo_client import mongo_client
            suppressions_coll = mongo_client.get_collection("suppressions")
            if suppressions_coll is not None:
                all_recipients = []
                if isinstance(request.to_emails, str):
                    all_recipients.append(request.to_emails)
                elif isinstance(request.to_emails, list):
                    all_recipients.extend(request.to_emails)

                if request.cc_emails:
                    if isinstance(request.cc_emails, str):
                        all_recipients.append(request.cc_emails)
                    elif isinstance(request.cc_emails, list):
                        all_recipients.extend(request.cc_emails)

                if request.bcc_emails:
                    if isinstance(request.bcc_emails, str):
                        all_recipients.append(request.bcc_emails)
                    elif isinstance(request.bcc_emails, list):
                        all_recipients.extend(request.bcc_emails)

                try:
                    suppressed_records = list(suppressions_coll.find({"email": {"$in": all_recipients}}))
                    if suppressed_records:
                        suppressed_emails = {r["email"] for r in suppressed_records}
                        logger.warning(f"Suppression list match found: {suppressed_emails}")

                        if isinstance(request.to_emails, list):
                            request.to_emails = [e for e in request.to_emails if e not in suppressed_emails]
                        elif isinstance(request.to_emails, str) and request.to_emails in suppressed_emails:
                            request.to_emails = []

                        if request.cc_emails:
                            if isinstance(request.cc_emails, list):
                                request.cc_emails = [e for e in request.cc_emails if e not in suppressed_emails]
                            elif isinstance(request.cc_emails, str) and request.cc_emails in suppressed_emails:
                                request.cc_emails = None

                        if request.bcc_emails:
                            if isinstance(request.bcc_emails, list):
                                request.bcc_emails = [e for e in request.bcc_emails if e not in suppressed_emails]
                            elif isinstance(request.bcc_emails, str) and request.bcc_emails in suppressed_emails:
                                request.bcc_emails = None

                        if not request.to_emails:
                            raise ValidationError(
                                f"All to_emails ({suppressed_emails}) are suppressed."
                            )
                except ValidationError:
                    raise
                except Exception as ex:
                    logger.error(f"Error checking suppression list: {ex}")

        # Render Template Content if applicable
        rendered_body_html = request.body_html
        rendered_body_text = request.body_text or ""

        if request.template_name:
            if db_template:
                body_html_source = db_template.get("body_html", "")
                rendered_body_html = self.template_engine.render_from_string(
                    body_html_source, request.template_context, request.template_name
                )
                if not rendered_body_text:
                    body_text_source = db_template.get("body_text", "")
                    if body_text_source:
                        rendered_body_text = self.template_engine.render_from_string(
                            body_text_source, request.template_context, request.template_name
                        )
            else:
                rendered_body_html = self.template_engine.render_from_file(
                    request.template_name, request.template_context
                )

            # Fallback plain text clean if not populated
            if not rendered_body_text and rendered_body_html:
                import re
                clean = re.compile("<.*?>")
                rendered_body_text = re.sub(clean, "", rendered_body_html).strip()

        # Render Subject
        rendered_subject = request.subject or ""
        if request.subject_template:
            rendered_subject = self.template_engine.render_subject(
                request.subject_template, request.template_context
            )
        elif not rendered_subject and db_template and db_template.get("subject_template"):
            rendered_subject = self.template_engine.render_subject(
                db_template["subject_template"], request.template_context
            )

        if not rendered_subject and not request.subject_template:
            raise ValidationError("Subject must be provided or resolved via template.")

        # ── Phase 6: Inject Tracking Pixel + Wrap Links ───────────────────────
        email_id = None
        if rendered_body_html and settings.ENABLE_TRACKING:
            from app.services.tracking_service import tracking_service
            email_id = tracking_service.generate_email_id()
            rendered_body_html = tracking_service.inject_tracking_pixel(rendered_body_html, email_id)
            rendered_body_html = tracking_service.wrap_links(rendered_body_html, email_id)

        # ── Phase 6: Inject Unsubscribe Footer for bulk/marketing emails ──────
        # Only injected when a template is used (marketing flow) and not confidential
        if rendered_body_html and request.template_name and not request.is_confidential:
            to_addr = (
                request.to_emails[0]
                if isinstance(request.to_emails, list) and request.to_emails
                else str(request.to_emails or "")
            )
            if to_addr:
                from app.services.unsubscribe_service import unsubscribe_service
                unsub_url = unsubscribe_service.build_unsubscribe_url(to_addr)
                unsub_footer = (
                    f'<div style="text-align:center;margin-top:24px;padding-top:16px;'
                    f'border-top:1px solid #e2e8f0;font-size:12px;color:#94a3b8;">'
                    f'You received this email because you are a SyncRivo user. '
                    f'<a href="{unsub_url}" style="color:#6366f1;text-decoration:underline;">Unsubscribe</a>'
                    f'</div>'
                )
                if "</body>" in rendered_body_html.lower():
                    idx = rendered_body_html.lower().rfind("</body>")
                    rendered_body_html = rendered_body_html[:idx] + unsub_footer + rendered_body_html[idx:]
                else:
                    rendered_body_html += unsub_footer

        # Create Log Entry in MongoDB
        log_id = None
        logs_coll = None
        if settings.ENABLE_MONGO_LOGGING:
            from app.utils.mongo_client import mongo_client
            from datetime import datetime, timezone
            logs_coll = mongo_client.get_collection("email_logs")
            if logs_coll is not None:
                to_list = [request.to_emails] if isinstance(request.to_emails, str) else request.to_emails
                cc_list = [request.cc_emails] if isinstance(request.cc_emails, str) else request.cc_emails
                bcc_list = [request.bcc_emails] if isinstance(request.bcc_emails, str) else request.bcc_emails

                log_entry = {
                    "email_id": email_id,  # Phase 6: for tracking correlation
                    "recipients": to_list,
                    "cc": cc_list or [],
                    "bcc": bcc_list or [],
                    "subject": rendered_subject,
                    "provider": provider_name,
                    "status": "sending",
                    "retry_count": 0,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                try:
                    result = logs_coll.insert_one(log_entry)
                    log_id = result.inserted_id
                except Exception as ex:
                    logger.error(f"Failed to insert email log: {ex}")

        try:
            logger.info(
                f"Sending email through provider '{provider_name}' with {settings.RETRY_ATTEMPTS} attempts limit."
            )

            to_list = [request.to_emails] if isinstance(request.to_emails, str) else request.to_emails
            cc_list = [request.cc_emails] if isinstance(request.cc_emails, str) else request.cc_emails
            bcc_list = [request.bcc_emails] if isinstance(request.bcc_emails, str) else request.bcc_emails

            message_id = retryer(
                provider.send,
                from_email=sender_email,
                to_emails=to_list,
                subject=rendered_subject,
                body_text=rendered_body_text,
                body_html=rendered_body_html,
                cc_emails=cc_list,
                bcc_emails=bcc_list,
                attachments=prepared_attachments,
                is_confidential=request.is_confidential,
                from_name=request.from_name,
                inline_images=request.inline_images,
            )

            # Update log status to sent
            if log_id and logs_coll is not None:
                from datetime import datetime, timezone
                try:
                    logs_coll.update_one(
                        {"_id": log_id},
                        {
                            "$set": {
                                "status": "sent",
                                "message_id": message_id,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                except Exception as ex:
                    logger.error(f"Failed to update email log to sent: {ex}")

            logger.info(f"Email successfully processed. Provider: {provider_name}, Message ID: {message_id}")
            return EmailResponse(
                success=True,
                message_id=message_id,
                provider_used=provider_name,
                message="Email sent successfully.",
            )

        except ProviderError as e:
            # Update log status to failed
            if log_id and logs_coll is not None:
                from datetime import datetime, timezone
                try:
                    logs_coll.update_one(
                        {"_id": log_id},
                        {
                            "$set": {
                                "status": "failed",
                                "error_detail": str(e),
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                except Exception as ex:
                    logger.error(f"Failed to update email log to failed: {ex}")
            logger.error(f"Email delivery exhausted retries and failed via provider '{provider_name}': {e}")
            raise e
        except Exception as e:
            # Update log status to failed
            if log_id and logs_coll is not None:
                from datetime import datetime, timezone
                try:
                    logs_coll.update_one(
                        {"_id": log_id},
                        {
                            "$set": {
                                "status": "failed",
                                "error_detail": str(e),
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                except Exception as ex:
                    logger.error(f"Failed to update email log to failed: {ex}")
            logger.error(f"Unexpected error in EmailService: {e}")
            raise e
