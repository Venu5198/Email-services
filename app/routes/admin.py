import logging
from typing import Optional, List
from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel, Field, EmailStr

logger = logging.getLogger("email_service")
router = APIRouter(prefix="/api/v1/admin", tags=["Sender Pool Admin"])


# -----------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------

class SenderAccountCreate(BaseModel):
    """Schema for registering a new sender account in the pool."""
    email: EmailStr = Field(..., description="Sender email address (e.g. sender1@syncrivo.ai).")
    smtp_username: Optional[str] = Field(
        default=None,
        description="SMTP username. Defaults to the email address."
    )
    smtp_password: str = Field(..., description="Gmail App Password or SMTP password (spaces ignored).")
    display_name: str = Field(
        default="SyncRivo",
        description="Display name shown in From header (e.g. 'SyncRivo Team')."
    )
    daily_limit: int = Field(
        default=500,
        ge=1,
        le=2000,
        description="Maximum emails this account can send per day."
    )
    smtp_host: Optional[str] = Field(
        default=None,
        description="Custom SMTP host. Inherits global SMTP_HOST from config if not set."
    )
    smtp_port: Optional[int] = Field(
        default=None,
        description="Custom SMTP port. Inherits global SMTP_PORT if not set."
    )
    smtp_use_ssl: Optional[bool] = Field(
        default=None,
        description="Use SSL. Inherits global setting if not set."
    )
    is_active: bool = Field(default=True, description="Whether this account is active in the pool.")


class SenderAccountPatch(BaseModel):
    """Schema for updating specific fields of a sender account."""
    display_name: Optional[str] = None
    daily_limit: Optional[int] = Field(default=None, ge=1, le=2000)
    is_active: Optional[bool] = None
    smtp_password: Optional[str] = None


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@router.post(
    "/sender-accounts",
    status_code=status.HTTP_201_CREATED,
    summary="Register Sender Account",
    description=(
        "Adds a new email account to the sender rotation pool. "
        "Each account contributes up to its daily_limit (default 500) to the total daily capacity. "
        "With 20 accounts × 500 = **10,000 emails/day**."
    ),
)
def add_sender_account(account: SenderAccountCreate):
    """Registers a new sender account in the pool."""
    from app.utils.mongo_client import mongo_client
    from app.services.sender_pool import sender_pool
    from datetime import date

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("sender_accounts")
    if coll is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="sender_accounts collection is unavailable."
        )

    doc = {
        "email": str(account.email),
        "smtp_username": account.smtp_username or str(account.email),
        "smtp_password": account.smtp_password.replace(" ", ""),
        "display_name": account.display_name,
        "daily_limit": account.daily_limit,
        "smtp_host": account.smtp_host,
        "smtp_port": account.smtp_port,
        "smtp_use_ssl": account.smtp_use_ssl,
        "sent_today": 0,
        "last_reset_date": str(date.today()),
        "is_active": account.is_active,
    }

    # Upsert by email (idempotent — safe to re-register)
    coll.update_one(
        {"email": str(account.email)},
        {"$set": doc},
        upsert=True
    )

    # Reload pool
    sender_pool.load_accounts()
    pool_status = sender_pool.get_pool_status()

    logger.info(
        f"SenderPool: Account '{account.email}' registered. "
        f"Pool size: {pool_status['total_accounts']}, "
        f"Total capacity: {pool_status['total_daily_capacity']:,}/day"
    )

    return {
        "message": f"Sender account '{account.email}' registered successfully.",
        "pool_size": pool_status["total_accounts"],
        "total_daily_capacity": pool_status["total_daily_capacity"],
    }


@router.get(
    "/sender-accounts",
    summary="List Sender Pool Status",
    description=(
        "Returns all registered sender accounts with their current quota usage, "
        "remaining capacity, and active status."
    ),
)
def list_sender_accounts():
    """Returns the full sender pool status including per-account quota usage."""
    from app.services.sender_pool import sender_pool
    return sender_pool.get_pool_status()


@router.patch(
    "/sender-accounts/{email}",
    summary="Update Sender Account",
    description="Updates settings for an existing sender account (e.g. activate/deactivate, change limit).",
)
def update_sender_account(email: str, patch: SenderAccountPatch):
    """Partially updates a sender account."""
    from app.utils.mongo_client import mongo_client
    from app.services.sender_pool import sender_pool

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("sender_accounts")
    updates = {k: v for k, v in patch.model_dump().items() if v is not None}
    if "smtp_password" in updates:
        updates["smtp_password"] = updates["smtp_password"].replace(" ", "")

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update."
        )

    result = coll.update_one({"email": email}, {"$set": updates}) if coll is not None else None
    if not result or result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sender account '{email}' not found."
        )

    sender_pool.load_accounts()
    return {"message": f"Sender account '{email}' updated successfully.", "updates": updates}


@router.delete(
    "/sender-accounts/{email}",
    summary="Remove Sender Account",
    description="Permanently removes a sender account from the pool.",
)
def remove_sender_account(email: str):
    """Deletes a sender account from the pool."""
    from app.utils.mongo_client import mongo_client
    from app.services.sender_pool import sender_pool

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("sender_accounts")
    result = coll.delete_one({"email": email}) if coll is not None else None
    if not result or result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sender account '{email}' not found."
        )

    sender_pool.load_accounts()
    logger.info(f"SenderPool: Account '{email}' removed.")
    return {"message": f"Sender account '{email}' removed from pool."}


@router.post(
    "/sender-accounts/reset-quotas",
    summary="Reset All Daily Quotas",
    description=(
        "Manually resets the sent_today counter for all sender accounts to 0. "
        "This happens automatically at midnight, but can be triggered manually if needed."
    ),
)
def reset_sender_quotas():
    """Resets all daily quotas to 0."""
    from app.services.sender_pool import sender_pool
    count = sender_pool.reset_daily_quotas()
    return {
        "message": f"Daily quotas reset for {count} sender accounts.",
        "accounts_reset": count,
    }


@router.post(
    "/sender-accounts/{email}/activate",
    summary="Activate / Deactivate Sender Account",
    description="Toggles a sender account's active state in the pool.",
)
def toggle_sender_account(email: str, active: bool = True):
    """Activates or deactivates a sender account."""
    from app.utils.mongo_client import mongo_client
    from app.services.sender_pool import sender_pool

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    coll = mongo_client.get_collection("sender_accounts")
    result = coll.update_one(
        {"email": email},
        {"$set": {"is_active": active}}
    ) if coll is not None else None

    if not result or result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sender account '{email}' not found."
        )

    sender_pool.load_accounts()
    state = "activated" if active else "deactivated"
    logger.info(f"SenderPool: Account '{email}' {state}.")
    return {"message": f"Sender account '{email}' {state} successfully."}


# -----------------------------------------------------------------------
# API Key Management
# -----------------------------------------------------------------------

class ApiKeyCreate(BaseModel):
    """Schema for generating a new API key for a microservice."""
    service_name: str = Field(
        ...,
        description="Identifier for the calling microservice (e.g. 'crm', 'booking', 'support_portal')."
    )
    description: str = Field(
        default="",
        description="Human-readable label for this key (e.g. 'CRM Production Key')."
    )
    scopes: Optional[List[str]] = Field(
        default=None,
        description="Allowed scopes. Defaults to ['email:send', 'email:bulk', 'email:status']."
    )


@router.post(
    "/api-keys",
    status_code=status.HTTP_201_CREATED,
    summary="Generate API Key",
    description=(
        "Generates a new API key for a microservice to authenticate with this email service. "
        "**The full key is shown ONCE and never stored — save it immediately.** "
        "Keys are stored as SHA-256 hashes in MongoDB. "
        "Use the key in the `X-Api-Key` header for protected endpoints."
    ),
)
def generate_api_key(req: ApiKeyCreate):
    """Generates a new API key for a microservice."""
    from app.utils.mongo_client import mongo_client
    from app.services.api_key_manager import api_key_manager

    if not mongo_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB is not connected."
        )

    try:
        result = api_key_manager.generate_key(
            service_name=req.service_name,
            description=req.description,
            scopes=req.scopes,
        )
        logger.info(f"API key generated for service '{req.service_name}'")
        return result
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate API key: {ex}"
        )


@router.get(
    "/api-keys",
    summary="List API Keys",
    description=(
        "Returns all registered API keys with metadata. "
        "Key hashes and plaintext values are never returned — only prefix and metadata."
    ),
)
def list_api_keys():
    """Lists all API keys (prefix + metadata only, no hashes)."""
    from app.services.api_key_manager import api_key_manager
    return {"api_keys": api_key_manager.list_keys()}


@router.patch(
    "/api-keys/{prefix}/revoke",
    summary="Revoke API Key",
    description=(
        "Deactivates an API key. The key will be rejected on all future requests. "
        "Use the key prefix (first 12 chars) shown when the key was generated."
    ),
)
def revoke_api_key(prefix: str):
    """Revokes an API key by its display prefix."""
    from app.services.api_key_manager import api_key_manager
    success = api_key_manager.revoke_key(prefix)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key with prefix '{prefix}' not found."
        )
    logger.info(f"API key revoked: prefix={prefix}")
    return {"message": f"API key '{prefix}' has been revoked."}


@router.delete(
    "/api-keys/{prefix}",
    summary="Delete API Key",
    description="Permanently deletes an API key record from the database.",
)
def delete_api_key(prefix: str):
    """Permanently deletes an API key."""
    from app.services.api_key_manager import api_key_manager
    success = api_key_manager.delete_key(prefix)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key with prefix '{prefix}' not found."
        )
    logger.info(f"API key deleted: prefix={prefix}")
    return {"message": f"API key '{prefix}' has been permanently deleted."}

