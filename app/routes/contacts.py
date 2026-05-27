"""
Contacts Route — /api/v1/contacts
Manages the contacts collection in MongoDB.
Used by the Campaigns page to auto-populate bulk email recipients.
"""
import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, EmailStr

from app.utils.mongo_client import mongo_client

logger = logging.getLogger("email_service")
router = APIRouter(prefix="/api/v1/contacts", tags=["Contacts"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name: str
    email: EmailStr
    group: Optional[str] = "general"
    tags: Optional[List[str]] = []
    active: Optional[bool] = True


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    group: Optional[str] = None
    tags: Optional[List[str]] = None
    active: Optional[bool] = None


class ContactImport(BaseModel):
    contacts: List[ContactCreate]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_coll():
    coll = mongo_client.get_collection("contacts")
    if coll is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return coll


def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_contacts(
    group: Optional[str] = Query(None, description="Filter by group name"),
    active_only: bool = Query(True, description="Only return active contacts"),
    limit: int = Query(1000, le=5000),
    skip: int = Query(0, ge=0),
):
    """Return all contacts, optionally filtered by group and active status."""
    coll = get_coll()
    query: dict = {}
    if active_only:
        query["active"] = True
    if group:
        query["group"] = group

    total = coll.count_documents(query)
    docs = list(coll.find(query, {"_id": 0}).sort("name", 1).skip(skip).limit(limit))

    # Build comma-separated email string for easy copy-paste into campaigns
    email_list = [d["email"] for d in docs]

    return {
        "total": total,
        "returned": len(docs),
        "contacts": docs,
        "email_list": email_list,   # Ready to paste into bulk campaign
        "email_csv": ", ".join(email_list),
    }


@router.get("/groups")
def list_groups():
    """Return all unique groups in the contacts collection."""
    coll = get_coll()
    groups = coll.distinct("group")
    counts = {}
    for g in groups:
        counts[g] = coll.count_documents({"group": g, "active": True})
    return {"groups": groups, "counts": counts}


@router.get("/stats")
def contact_stats():
    """Summary statistics for the contacts collection."""
    coll = get_coll()
    total = coll.count_documents({})
    active = coll.count_documents({"active": True})
    inactive = coll.count_documents({"active": False})
    groups = coll.distinct("group")
    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "groups": len(groups),
        "group_names": groups,
    }


@router.post("", status_code=201)
def create_contact(body: ContactCreate):
    """Add a single contact. Fails if email already exists."""
    coll = get_coll()
    if coll.find_one({"email": body.email}):
        raise HTTPException(status_code=409, detail=f"Contact '{body.email}' already exists.")
    doc = body.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    coll.insert_one(doc)
    doc.pop("_id", None)
    return {"message": "Contact created", "contact": doc}


@router.post("/import")
def import_contacts(body: ContactImport):
    """
    Bulk import contacts. Skips duplicates (upserts by email).
    Returns count of inserted and updated.
    """
    coll = get_coll()
    inserted = 0
    updated = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for c in body.contacts:
        doc = c.model_dump()
        existing = coll.find_one({"email": c.email})
        if existing:
            coll.update_one({"email": c.email}, {"$set": {**doc, "updated_at": now}})
            updated += 1
        else:
            doc["created_at"] = now
            coll.insert_one(doc)
            inserted += 1

    return {
        "message": f"Import complete: {inserted} inserted, {updated} updated",
        "inserted": inserted,
        "updated": updated,
        "total_processed": len(body.contacts),
    }


@router.patch("/{email}")
def update_contact(email: str, body: ContactUpdate):
    """Update a contact's name, group, tags, or active status."""
    coll = get_coll()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = coll.update_one({"email": email}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Contact '{email}' not found.")
    return {"message": f"Contact '{email}' updated.", "updated_fields": list(updates.keys())}


@router.delete("/{email}")
def delete_contact(email: str):
    """Permanently delete a contact by email."""
    coll = get_coll()
    result = coll.delete_one({"email": email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Contact '{email}' not found.")
    return {"message": f"Contact '{email}' deleted."}


@router.post("/{email}/deactivate")
def deactivate_contact(email: str):
    """Soft-delete: mark a contact as inactive (won't appear in bulk sends)."""
    coll = get_coll()
    result = coll.update_one({"email": email}, {"$set": {"active": False, "updated_at": datetime.now(timezone.utc).isoformat()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Contact '{email}' not found.")
    return {"message": f"Contact '{email}' deactivated."}
