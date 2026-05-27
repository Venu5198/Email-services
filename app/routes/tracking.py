import logging
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.services.tracking_service import tracking_service

logger = logging.getLogger("email_service")
router = APIRouter(tags=["Email Tracking"])


@router.get(
    "/track/open/{email_id}",
    summary="Email Open Tracking Pixel",
    description=(
        "Returns a 1×1 transparent GIF image and records an open event for the given email_id. "
        "This URL is embedded invisibly in every tracked HTML email. "
        "When an email client loads it, the open is recorded in MongoDB email_events."
    ),
)
def track_open(email_id: str, request: Request):
    """
    Records an email open event and returns a 1×1 transparent GIF.
    No authentication required — URL is embedded in outbound emails.
    """
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    tracking_service.record_open(
        email_id=email_id,
        ip_address=ip,
        user_agent=user_agent,
    )

    return Response(
        content=tracking_service.get_transparent_gif(),
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get(
    "/track/click/{email_id}",
    summary="Email Click Tracking",
    description=(
        "Records a click event for the given email_id and redirects the user to the "
        "original destination URL (passed as ?url= query parameter). "
        "This URL wraps all links in tracked HTML emails."
    ),
)
def track_click(email_id: str, url: str, request: Request):
    """
    Records a click event and redirects to the original URL.
    No authentication required — URL is embedded in outbound email links.
    """
    ip = request.client.host if request.client else None

    tracking_service.record_click(
        email_id=email_id,
        url=url,
        ip_address=ip,
    )

    return RedirectResponse(url=url, status_code=302)
