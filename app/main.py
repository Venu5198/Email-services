import logging
import sys
import asyncio
from contextlib import asynccontextmanager
from typing import List
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exceptions import (
    EmailServiceException,
    ValidationError,
    TemplateError,
    AttachmentError,
    ProviderError
)
from app.schemas.email import EmailRequest, EmailResponse
from app.schemas.mongo_models import TemplateCreate, TemplateResponse, SuppressionCreate, SuppressionResponse
from app.schemas.template_preview import TemplatePreviewRequest, TemplatePreviewResponse
from app.utils.mongo_client import mongo_client
from app.services.email_service import EmailService
from app.services.template_engine import TemplateEngine
from app.routes.demo import router as demo_router
from app.routes.bulk import router as bulk_router
from app.routes.monitor import router as monitor_router
from app.routes.admin import router as admin_router
from app.routes.unsubscribe import router as unsubscribe_router
from app.routes.tracking import router as tracking_router
from app.routes.scheduler import router as scheduler_router
from app.routes.analytics import router as analytics_router
from app.routes.webhooks import router as webhooks_router
from app.routes.contacts import router as contacts_router

# 1. Setup Structured Logging Configuration
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("email_service")


# Lifespan: start inbox monitor as background task on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.inbox_monitor import inbox_monitor
    from app.services.scheduler_service import scheduler_service

    # Start inbox monitor
    task = asyncio.create_task(inbox_monitor.start_polling())
    logger.info("Inbox monitor started via lifespan.")

    # Start APScheduler (restores pending jobs from MongoDB)
    scheduler_service.start()
    logger.info("Email scheduler started via lifespan.")

    yield

    # Graceful shutdown
    await inbox_monitor.stop()
    task.cancel()
    scheduler_service.stop()
    logger.info("Inbox monitor and scheduler stopped via lifespan.")


# Initialize FastAPI application
app = FastAPI(
    title="Enterprise Email Service API",
    description="A microservice for sending dynamic emails, managing attachments, and supporting SMTP, SendGrid, and AWS SES.",
    version="1.0.0",
    lifespan=lifespan,
)

# Initialize Core Email Service
email_service = EmailService()

# ── CORS Middleware ───────────────────────────────────────────────────────────
# Allow the Next.js frontend (localhost:3000) to call the FastAPI backend.
# In production replace '*' with your actual domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        # Add your production domain here, e.g. "https://app.syncrivo.ai"
    ],
    allow_credentials=True,
    allow_methods=["*"],   # GET, POST, PUT, PATCH, DELETE, OPTIONS
    allow_headers=["*"],   # Authorization, Content-Type, X-API-Key, etc.
)

# Register business email routes
app.include_router(demo_router)
app.include_router(bulk_router)
app.include_router(monitor_router)
app.include_router(admin_router)

# Register Phase 6 routes
app.include_router(unsubscribe_router)   # GET/POST /unsubscribe
app.include_router(tracking_router)      # GET /track/open/{id}, /track/click/{id}
app.include_router(scheduler_router)     # /api/v1/schedule
app.include_router(analytics_router)     # /api/v1/analytics
app.include_router(webhooks_router)      # /api/v1/webhooks
app.include_router(contacts_router)      # /api/v1/contacts


# 2. Register Custom Exception Handlers for Production-grade API Responses
@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    logger.warning(f"Validation failure on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "ValidationError", "detail": str(exc)},
    )


@app.exception_handler(TemplateError)
async def template_exception_handler(request: Request, exc: TemplateError):
    logger.error(f"Template rendering failure on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "TemplateError", "detail": str(exc)},
    )


@app.exception_handler(AttachmentError)
async def attachment_exception_handler(request: Request, exc: AttachmentError):
    logger.error(f"Attachment processing failure on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "AttachmentError", "detail": str(exc)},
    )


@app.exception_handler(ProviderError)
async def provider_exception_handler(request: Request, exc: ProviderError):
    logger.error(f"Email delivery provider failure on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "ProviderError", "detail": f"Delivery backend failure: {str(exc)}"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "detail": "An unexpected error occurred on the server."},
    )


# 3. API Route Endpoints
@app.post(
    "/api/v1/send",
    response_model=EmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Send Email Synchronously",
    description="Validates, renders, and transmits the email immediately, waiting for the provider response.",
)
def send_email_sync(request: EmailRequest) -> EmailResponse:
    return email_service.send_email(request)


def _async_send_worker(request: EmailRequest):
    """Worker function executed by FastAPI BackgroundTasks."""
    try:
        email_service.send_email(request)
    except Exception as e:
        logger.error(f"Background email send worker failed: {e}")


@app.post(
    "/api/v1/send-async",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send Email Asynchronously",
    description="Queues the email for background processing and returns immediately without blocking.",
)
def send_email_async(request: EmailRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_async_send_worker, request)
    provider_name = request.provider_override or settings.EMAIL_PROVIDER
    return {
        "success": True,
        "message": "Email request accepted and queued in the background.",
        "provider_used": provider_name,
    }


@app.get("/health", status_code=status.HTTP_200_OK, summary="Health Check")
def health_check():
    return {
        "status": "healthy",
        "provider_configured": settings.EMAIL_PROVIDER,
        "default_sender": settings.DEFAULT_SENDER_EMAIL,
    }


# --- Template Preview endpoint ---
@app.post(
    "/api/v1/templates/preview",
    response_model=TemplatePreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview Rendered Template",
    description=(
        "Renders a Jinja2 template with the provided context and returns the HTML output "
        "WITHOUT sending any email. Useful for checking layout and variable substitution "
        "before launching a bulk campaign. Supports both file templates and MongoDB templates."
    ),
)
def preview_template(req: TemplatePreviewRequest):
    """Renders a template to HTML without sending any email."""
    engine = TemplateEngine()

    # Try MongoDB template first
    body_html = None
    body_text = None
    subject = None

    if mongo_client.is_connected and settings.ENABLE_MONGO_TEMPLATES:
        coll = mongo_client.get_collection("email_templates")
        if coll is not None:
            doc = coll.find_one({"template_name": req.template_name})
            if doc:
                html_source = doc.get("body_html", "")
                text_source = doc.get("body_text", "")
                subj_source = doc.get("subject_template", "")
                if html_source:
                    body_html = engine.render_from_string(html_source, req.context, req.template_name)
                if text_source:
                    body_text = engine.render_from_string(text_source, req.context, req.template_name)
                if subj_source:
                    subject = engine.render_from_string(subj_source, req.context, "subject")

    # Fall back to file template
    if body_html is None:
        body_html = engine.render_from_file(req.template_name, req.context)

    # Render subject template if explicitly provided
    if req.subject_template and not subject:
        subject = engine.render_subject(req.subject_template, req.context)

    # Collect variables used
    variables_used = sorted(req.context.keys())

    return TemplatePreviewResponse(
        template_name=req.template_name,
        rendered_subject=subject,
        rendered_html=body_html,
        rendered_text=body_text,
        variables_used=variables_used,
    )


# --- MongoDB Templates endpoints ---
@app.post(
    "/api/v1/templates",
    status_code=status.HTTP_201_CREATED,
    summary="Create or Update Email Template",
    description="Stores a Jinja2 template in MongoDB for dynamic email rendering.",
)
def create_or_update_template(template: TemplateCreate):
    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected or enabled."
        )
    coll = mongo_client.get_collection("email_templates")
    if coll is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Templates collection is unavailable."
        )
    
    # Upsert template
    template_data = template.model_dump()
    coll.update_one(
        {"template_name": template.template_name},
        {"$set": template_data},
        upsert=True
    )
    return {"message": f"Template '{template.template_name}' saved successfully."}


@app.get(
    "/api/v1/templates/{template_name}",
    response_model=TemplateResponse,
    summary="Get Template Details",
)
def get_template(template_name: str):
    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )
    coll = mongo_client.get_collection("email_templates")
    doc = coll.find_one({"template_name": template_name}) if coll is not None else None
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_name}' not found."
        )
    return doc


@app.delete(
    "/api/v1/templates/{template_name}",
    summary="Delete Template",
)
def delete_template(template_name: str):
    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )
    coll = mongo_client.get_collection("email_templates")
    result = coll.delete_one({"template_name": template_name}) if coll is not None else None
    if not result or result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_name}' not found."
        )
    return {"message": f"Template '{template_name}' deleted successfully."}


# --- MongoDB Suppression endpoints ---
@app.post(
    "/api/v1/suppressions",
    status_code=status.HTTP_201_CREATED,
    summary="Suppress Email Address",
    description="Adds an email address to the suppression list to prevent sending emails to it.",
)
def add_suppression(suppression: SuppressionCreate):
    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )
    coll = mongo_client.get_collection("suppressions")
    if coll is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Suppressions collection is unavailable."
        )
    
    # Save suppression
    doc = {
        "email": suppression.email,
        "reason": suppression.reason,
        "created_at": datetime.now(timezone.utc)
    }
    coll.update_one(
        {"email": suppression.email},
        {"$set": doc},
        upsert=True
    )
    return {"message": f"Email '{suppression.email}' added to suppression list."}


@app.get(
    "/api/v1/suppressions",
    response_model=List[SuppressionResponse],
    summary="List Suppressed Emails",
)
def list_suppressions(limit: int = 100, skip: int = 0):
    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )
    coll = mongo_client.get_collection("suppressions")
    if coll is None:
        return []
    docs = list(coll.find().skip(skip).limit(limit))
    return docs


@app.delete(
    "/api/v1/suppressions/{email}",
    summary="Remove Suppression",
)
def delete_suppression(email: str):
    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )
    coll = mongo_client.get_collection("suppressions")
    result = coll.delete_one({"email": email}) if coll is not None else None
    if not result or result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email '{email}' not found in suppressions list."
        )
    return {"message": f"Email '{email}' removed from suppression list."}
