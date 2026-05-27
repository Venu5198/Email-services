import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger("email_service.api_key")


class ApiKeyManager:
    """
    Manages API key lifecycle for microservice authentication.

    Keys are:
    - Generated as cryptographically secure 32-byte random tokens
    - Stored as SHA-256 hashes in MongoDB (never stored in plaintext)
    - Prefixed with 'srk_' (SyncRivo Key) for easy identification
    - Scoped per service (e.g. 'crm', 'booking', 'support_portal')
    - Tracked with usage metadata (last_used, request_count)

    Collection: api_keys
    Fields: prefix, key_hash, service_name, description,
            is_active, created_at, last_used_at, request_count
    """

    KEY_PREFIX = "srk_"
    HASH_ALGORITHM = "sha256"

    # -----------------------------------------------------------------------
    # Key generation
    # -----------------------------------------------------------------------

    def generate_key(
        self,
        service_name: str,
        description: str = "",
        scopes: Optional[List[str]] = None,
    ) -> Dict:
        """
        Generates a new API key and stores its hash in MongoDB.

        Returns the full plaintext key ONCE — it is never stored or retrievable again.
        The caller must save it immediately.

        Args:
            service_name: Identifier for the microservice (e.g. 'crm', 'booking').
            description:  Human-readable label (e.g. 'CRM Service Production Key').
            scopes:       Optional list of allowed scopes (future use).

        Returns:
            {
                "key": "srk_abc123...",   ← Save this — shown once only
                "prefix": "srk_abc1",     ← Stored in DB for display
                "service_name": "crm",
                "created_at": "2026-05-24T..."
            }
        """
        raw_token = secrets.token_urlsafe(32)
        plaintext_key = f"{self.KEY_PREFIX}{raw_token}"
        key_hash = self._hash_key(plaintext_key)
        prefix = plaintext_key[:12]  # First 12 chars for display (e.g. srk_abc123xx)

        doc = {
            "prefix": prefix,
            "key_hash": key_hash,
            "service_name": service_name,
            "description": description,
            "scopes": scopes or ["email:send", "email:bulk", "email:status"],
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "last_used_at": None,
            "request_count": 0,
        }

        try:
            from app.utils.mongo_client import mongo_client
            if mongo_client.is_connected:
                coll = mongo_client.get_collection("api_keys")
                if coll is not None:
                    coll.insert_one(doc)
                    logger.info(
                        f"API key generated for service '{service_name}' "
                        f"(prefix: {prefix})"
                    )
        except Exception as ex:
            logger.error(f"Failed to store API key in MongoDB: {ex}")
            raise RuntimeError(f"API key storage failed: {ex}")

        return {
            "key": plaintext_key,
            "prefix": prefix,
            "service_name": service_name,
            "description": description,
            "scopes": doc["scopes"],
            "created_at": doc["created_at"].isoformat(),
            "note": "⚠️ Save this key now — it will NOT be shown again.",
        }

    # -----------------------------------------------------------------------
    # Key validation (used by FastAPI dependency)
    # -----------------------------------------------------------------------

    def validate_key(self, plaintext_key: str) -> Optional[Dict]:
        """
        Validates an API key and returns the key document if valid.

        Steps:
        1. Hash the incoming key
        2. Look up the hash in MongoDB
        3. Verify the key is active
        4. Update last_used_at and increment request_count

        Returns the key document on success, None on failure.
        """
        if not plaintext_key or not plaintext_key.startswith(self.KEY_PREFIX):
            return None

        key_hash = self._hash_key(plaintext_key)

        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                logger.warning("API key validation: MongoDB not connected.")
                return None

            coll = mongo_client.get_collection("api_keys")
            if coll is None:
                return None

            doc = coll.find_one({"key_hash": key_hash, "is_active": True})
            if not doc:
                return None

            # Update usage tracking asynchronously (non-blocking best-effort)
            try:
                coll.update_one(
                    {"key_hash": key_hash},
                    {
                        "$set": {"last_used_at": datetime.now(timezone.utc)},
                        "$inc": {"request_count": 1},
                    },
                )
            except Exception as ex:
                logger.warning(f"Failed to update key usage stats: {ex}")

            return {
                "prefix": doc.get("prefix"),
                "service_name": doc.get("service_name"),
                "scopes": doc.get("scopes", []),
                "description": doc.get("description"),
            }

        except Exception as ex:
            logger.error(f"API key validation error: {ex}")
            return None

    # -----------------------------------------------------------------------
    # Key management
    # -----------------------------------------------------------------------

    def list_keys(self) -> List[Dict]:
        """Returns all API keys (without hashes) for the admin dashboard."""
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return []
            coll = mongo_client.get_collection("api_keys")
            if coll is None:
                return []

            docs = list(coll.find({}, {"_id": 0, "key_hash": 0}))
            for doc in docs:
                for field in ("created_at", "last_used_at"):
                    if doc.get(field) and hasattr(doc[field], "isoformat"):
                        doc[field] = doc[field].isoformat()
            return docs
        except Exception as ex:
            logger.error(f"Failed to list API keys: {ex}")
            return []

    def revoke_key(self, prefix: str) -> bool:
        """Deactivates an API key by its display prefix."""
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return False
            coll = mongo_client.get_collection("api_keys")
            if coll is None:
                return False
            result = coll.update_one(
                {"prefix": prefix},
                {"$set": {"is_active": False}}
            )
            if result.matched_count > 0:
                logger.info(f"API key revoked: prefix={prefix}")
                return True
            return False
        except Exception as ex:
            logger.error(f"Failed to revoke API key {prefix}: {ex}")
            return False

    def delete_key(self, prefix: str) -> bool:
        """Permanently deletes an API key record."""
        try:
            from app.utils.mongo_client import mongo_client
            if not mongo_client.is_connected:
                return False
            coll = mongo_client.get_collection("api_keys")
            if coll is None:
                return False
            result = coll.delete_one({"prefix": prefix})
            return result.deleted_count > 0
        except Exception as ex:
            logger.error(f"Failed to delete API key {prefix}: {ex}")
            return False

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _hash_key(self, plaintext_key: str) -> str:
        """Returns a SHA-256 hex digest of the plaintext key."""
        return hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()


# Global singleton
api_key_manager = ApiKeyManager()
