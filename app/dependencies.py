from typing import Optional
from fastapi import Header, HTTPException, status


async def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> dict:
    """
    FastAPI dependency — validates the X-Api-Key header on protected routes.

    Usage:
        from app.dependencies import verify_api_key
        from fastapi import Depends

        @router.post("/send")
        def send_email(req: EmailRequest, key: dict = Depends(verify_api_key)):
            ...

    Headers required:
        X-Api-Key: srk_<your_service_key>

    Raises:
        401 — No key provided
        403 — Key is invalid, revoked, or not found

    Returns:
        dict with: prefix, service_name, scopes, description
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-Api-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    from app.services.api_key_manager import api_key_manager
    key_doc = api_key_manager.validate_key(x_api_key)

    if not key_doc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or revoked API key.",
        )

    return key_doc


async def optional_api_key(x_api_key: Optional[str] = Header(default=None)) -> Optional[dict]:
    """
    Optional version of verify_api_key — does not raise if key is absent.
    Useful for endpoints that support both authenticated and internal calls.
    """
    if not x_api_key:
        return None

    from app.services.api_key_manager import api_key_manager
    return api_key_manager.validate_key(x_api_key)
