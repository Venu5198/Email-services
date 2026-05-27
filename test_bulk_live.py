"""
Live bulk email test using 'sample contact' MongoDB collection.
Sends personalized emails to all 6 contacts.
"""
import time
import json
import sys
import requests
from pymongo import MongoClient

BASE_URL = "http://localhost:8000"

# ── 1. Check server health ──────────────────────────────────────────────────
print("="*60)
print("STEP 1 — Server health check")
print("="*60)
try:
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"  Status : {resp.status_code}")
    print(f"  Response: {resp.json()}")
except Exception as e:
    print(f"  ❌ Server not reachable: {e}")
    sys.exit(1)

# ── 2. Preview the 6 contacts ───────────────────────────────────────────────
print()
print("="*60)
print("STEP 2 — Contacts in 'sample contact' collection")
print("="*60)
mc = MongoClient("mongodb://localhost:27017")
db = mc["email_service"]
docs = list(db["sample contact"].find({}, {"_id": 0}))
for i, d in enumerate(docs):
    email   = d.get("email", "N/A")
    role    = d.get("role", "N/A")
    country = d.get("country", "N/A")
    print(f"  {i+1}. {email:<35} | {role:<20} | {country}")

print(f"\n  Total contacts: {len(docs)}")

# ── 3. Send personalised bulk email ─────────────────────────────────────────
print()
print("="*60)
print("STEP 3 — Sending bulk email to all 6 contacts")
print("="*60)

payload = {
    "recipient_source": "mongodb",
    "recipient_collection": "sample contact",
    "recipient_query": {},
    "template_name": "marketing_article.html",
    "subject_template": "Hello {{ role }} from {{ country }} — SyncRivo Update",
    "template_context": {
        "article_title": "How SyncRivo Transforms Your Business Workflow",
        "article_summary": (
            "Discover how leading teams across Canada, India, the USA, and beyond "
            "are using SyncRivo to automate operations and move faster."
        ),
        "article_body": (
            "From intelligent email automation to real-time analytics, "
            "SyncRivo gives your team the tools to operate at peak efficiency."
        ),
        "tag": "Product Update",
        "category": "Product",
        "published_date": "May 24, 2026",
        "read_time": "3 min read",
        "tags": ["Automation", "AI", "Productivity"],
        "cta_url": "https://syncrivo.ai/get-started",
        "cta_title": "Get Started with SyncRivo",
        "cta_body": "Start your free trial and see the difference in 7 days.",
        "cta_text": "Start Free Trial",
        "company_name": "SyncRivo",
    },
    "batch_size": 500,
    "initiated_by": "live_test_run",
}

resp = requests.post(f"{BASE_URL}/api/v1/bulk-send", json=payload, timeout=60)
print(f"  HTTP Status : {resp.status_code}")
result = resp.json()
print(f"  Response    :\n{json.dumps(result, indent=4)}")

if resp.status_code not in (200, 202):
    print("  ❌ Bulk send failed.")
    sys.exit(1)

job_id = result.get("job_id", "")
if not job_id:
    print("  ❌ No job_id in response.")
    sys.exit(1)

# ── 4. Poll job status ───────────────────────────────────────────────────────
print()
print("="*60)
print(f"STEP 4 — Polling job status  (job_id: {job_id})")
print("="*60)

for attempt in range(20):
    time.sleep(3)
    status_resp = requests.get(f"{BASE_URL}/api/v1/bulk-send/{job_id}/status", timeout=10)
    status = status_resp.json()
    job_status = status.get("status", "unknown")
    sent      = status.get("sent", 0)
    failed    = status.get("failed", 0)
    skipped   = status.get("skipped_suppressed", 0)
    total     = status.get("total_recipients", len(docs))

    print(f"  Attempt {attempt+1:02d} | status={job_status} | "
          f"sent={sent}/{total} | failed={failed} | skipped={skipped}")

    if job_status in ("completed", "failed"):
        break

# ── 5. Final result ──────────────────────────────────────────────────────────
print()
print("="*60)
print("STEP 5 — Final Result")
print("="*60)
print(json.dumps(status, indent=4))

if status.get("status") == "completed" and status.get("sent", 0) > 0:
    print()
    print("  [OK] ALL EMAILS SENT SUCCESSFULLY!")
    print(f"  Sent    : {status.get('sent')}")
    print(f"  Failed  : {status.get('failed')}")
    print(f"  Skipped : {status.get('skipped_suppressed')}")
    print()
    print("  Check these inboxes:")
    for d in docs:
        print(f"    - {d.get('email')}")
else:
    err = status.get("error_detail", "see logs")
    print(f"  [FAIL] Job ended with status: {status.get('status')}")
    print(f"  Sent   : {status.get('sent')} / {status.get('total_recipients')}")
    print(f"  Failed : {status.get('failed')}")
    if err:
        print(f"  Error  : {err}")
