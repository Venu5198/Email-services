// =============================================================================
// SyncRivo MongoDB Initialization Script
// Runs once on first container start when the data volume is empty.
// Creates the database, collections, and indexes for optimal query performance.
// =============================================================================

db = db.getSiblingDB('email_service');

print('SyncRivo: Initializing email_service database...');

// ── Collections & Indexes ────────────────────────────────────────────────────

// email_logs — core send audit trail
db.createCollection('email_logs');
db.email_logs.createIndex({ 'email_id': 1 });
db.email_logs.createIndex({ 'status': 1 });
db.email_logs.createIndex({ 'timestamp': -1 });
db.email_logs.createIndex({ 'recipients': 1 });
db.email_logs.createIndex({ 'job_id': 1 });

// email_events — open/click tracking events
db.createCollection('email_events');
db.email_events.createIndex({ 'email_id': 1 });
db.email_events.createIndex({ 'event_type': 1 });
db.email_events.createIndex({ 'occurred_at': -1 });

// suppressions — suppressed/unsubscribed emails
db.createCollection('suppressions');
db.suppressions.createIndex({ 'email': 1 }, { unique: true });
db.suppressions.createIndex({ 'reason': 1 });
db.suppressions.createIndex({ 'created_at': -1 });

// sender_accounts — SMTP sender pool
db.createCollection('sender_accounts');
db.sender_accounts.createIndex({ 'email': 1 }, { unique: true });
db.sender_accounts.createIndex({ 'is_active': 1 });

// email_templates — MongoDB-stored Jinja2 templates
db.createCollection('email_templates');
db.email_templates.createIndex({ 'template_name': 1 }, { unique: true });

// bulk_send_jobs — background bulk campaign tracking
db.createCollection('bulk_send_jobs');
db.bulk_send_jobs.createIndex({ 'job_id': 1 }, { unique: true });
db.bulk_send_jobs.createIndex({ 'status': 1 });
db.bulk_send_jobs.createIndex({ 'created_at': -1 });

// scheduled_jobs — APScheduler persisted jobs
db.createCollection('scheduled_jobs');
db.scheduled_jobs.createIndex({ 'job_id': 1 }, { unique: true });
db.scheduled_jobs.createIndex({ 'status': 1 });

// inbox_rules — keyword triage rules
db.createCollection('inbox_rules');
db.inbox_rules.createIndex({ 'rule_name': 1 }, { unique: true });
db.inbox_rules.createIndex({ 'is_active': 1 });

// inbox_matches — matched inbox alerts log
db.createCollection('inbox_matches');
db.inbox_matches.createIndex({ 'matched_at': -1 });

// api_keys — microservice API key registry
db.createCollection('api_keys');
db.api_keys.createIndex({ 'prefix': 1 }, { unique: true });
db.api_keys.createIndex({ 'service_name': 1 });
db.api_keys.createIndex({ 'is_active': 1 });

print('SyncRivo: ✓ All collections and indexes created.');
print('SyncRivo: Database ready — email_service');
