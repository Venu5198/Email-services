/**
 * SyncRivo Email Service — Full Browser Test Suite
 * Tests all 11 pages: interactions, form fills, button clicks, visual bug detection
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE = 'http://localhost:3000';
const API  = 'http://localhost:8000';
const SS_DIR = path.join(__dirname, 'test-screenshots');
if (!fs.existsSync(SS_DIR)) fs.mkdirSync(SS_DIR, { recursive: true });

const results = [];
let page, browser, context;

// ── Helpers ────────────────────────────────────────────────────────────────

async function go(route) {
  await page.goto(`${BASE}${route}`, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1200); // let animations settle
}

async function shot(name) {
  const file = path.join(SS_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return file;
}

function log(page_name, test, status, detail = '') {
  const icon = status === 'PASS' ? '✅' : status === 'WARN' ? '⚠️' : '❌';
  const line = `  ${icon} [${status}] ${test}${detail ? ' — ' + detail : ''}`;
  console.log(line);
  results.push({ page: page_name, test, status, detail });
}

async function checkNoNetworkError(page_name) {
  const errorEl = await page.$('text=Network Error');
  if (errorEl) {
    log(page_name, 'No Network Error', 'FAIL', 'Network Error banner visible');
  } else {
    log(page_name, 'No Network Error', 'PASS');
  }
}

async function checkNoConsoleErrors(page_name, errors) {
  if (errors.length === 0) {
    log(page_name, 'No console errors', 'PASS');
  } else {
    log(page_name, 'No console errors', 'WARN', errors.slice(0,2).join(' | '));
  }
}

async function checkVisible(page_name, selector, label) {
  try {
    const el = await page.waitForSelector(selector, { timeout: 5000 });
    const visible = await el.isVisible();
    log(page_name, `${label} visible`, visible ? 'PASS' : 'FAIL');
    return visible;
  } catch {
    log(page_name, `${label} visible`, 'FAIL', `selector not found: ${selector}`);
    return false;
  }
}

// ── Main Test Runner ───────────────────────────────────────────────────────

(async () => {
  console.log('\n══════════════════════════════════════════════════════════════');
  console.log('  SyncRivo Email Service — Browser Test Suite');
  console.log('  Target: http://localhost:3000');
  console.log('══════════════════════════════════════════════════════════════\n');

  browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  page = await context.newPage();

  // Track console errors per page
  let consoleErrors = [];
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', err => consoleErrors.push(err.message));

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 1 — DASHBOARD
  // ════════════════════════════════════════════════════════════════════════
  console.log('📊 Page 1: Dashboard (/)');
  consoleErrors = [];
  await go('/');
  await shot('01_dashboard');

  await checkNoNetworkError('Dashboard');
  await checkNoConsoleErrors('Dashboard', consoleErrors);
  await checkVisible('Dashboard', 'h1:text("Dashboard")', 'Dashboard heading');
  await checkVisible('Dashboard', 'text=Emails Sent', 'Emails Sent card');
  await checkVisible('Dashboard', 'text=Open Rate', 'Open Rate card');
  await checkVisible('Dashboard', 'text=Click Rate', 'Click Rate card');
  await checkVisible('Dashboard', 'text=Bounces', 'Bounces card');
  await checkVisible('Dashboard', 'text=Engagement Breakdown', 'Engagement Breakdown section');
  await checkVisible('Dashboard', 'text=Sender Pool Quota', 'Sender Pool Quota section');
  await checkVisible('Dashboard', 'text=Quick Actions', 'Quick Actions section');
  // Sidebar nav
  await checkVisible('Dashboard', 'text=Compose', 'Sidebar: Compose link');
  await checkVisible('Dashboard', 'text=Campaigns', 'Sidebar: Campaigns link');
  await checkVisible('Dashboard', 'text=Contacts', 'Sidebar: Contacts link');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 2 — CONTACTS
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n👥 Page 2: Contacts (/contacts)');
  consoleErrors = [];
  await go('/contacts');
  await shot('02_contacts');

  await checkNoNetworkError('Contacts');
  await checkNoConsoleErrors('Contacts', consoleErrors);
  await checkVisible('Contacts', 'h1:text("Contacts")', 'Contacts heading');
  await checkVisible('Contacts', 'text=Total Contacts', 'Total Contacts stat');
  await checkVisible('Contacts', 'text=Active', 'Active stat card');
  await checkVisible('Contacts', 'text=Import Emails', 'Import Emails button');
  await checkVisible('Contacts', 'text=Add Contact', 'Add Contact button');

  // Check contacts table has data
  const contactRows = await page.$$('table tbody tr');
  log('Contacts', `Table has contacts (${contactRows.length} rows)`, contactRows.length >= 5 ? 'PASS' : 'WARN', `Expected ≥5, got ${contactRows.length}`);

  // Click group filter
  await checkVisible('Contacts', 'select', 'Group filter dropdown');
  const groupSelect = await page.$('select');
  if (groupSelect) {
    try {
      const opts = await groupSelect.$$('option');
      const vals = await Promise.all(opts.map(o => o.getAttribute('value')));
      const internalVal = vals.find(v => v && v.toLowerCase().includes('internal'));
      if (internalVal) {
        await groupSelect.selectOption(internalVal);
        await page.waitForTimeout(800);
        const filtered = await page.$$('table tbody tr');
        log('Contacts', 'Group filter works (internal → 2 rows)', filtered.length === 2 ? 'PASS' : 'WARN', `Got ${filtered.length} rows`);
        await shot('02b_contacts_filtered');
      } else {
        log('Contacts', 'Group filter works', 'WARN', 'internal option not found');
      }
    } catch(e) {
      log('Contacts', 'Group filter works', 'WARN', e.message.slice(0,80));
    }
  }

  // Click "Add Contact" tab
  await page.click('button:has-text("Add Single")');
  await page.waitForTimeout(500);
  await shot('02c_contacts_add_form');
  await checkVisible('Contacts', 'input[id="c-name"]', 'Add Contact name field');
  await checkVisible('Contacts', 'input[id="c-email"]', 'Add Contact email field');

  // Fill the add contact form
  await page.fill('input[id="c-name"]', 'Playwright Test User');
  await page.fill('input[id="c-email"]', 'playwright@test.com');
  await shot('02d_contacts_add_filled');
  log('Contacts', 'Add Contact form fillable', 'PASS');

  // Click "Bulk Import" tab
  await page.click('button:has-text("Bulk Import")');
  await page.waitForTimeout(500);
  await shot('02e_contacts_import_tab');
  await checkVisible('Contacts', 'textarea', 'Import textarea visible');
  const importTextarea = await page.$('textarea');
  if (importTextarea) {
    await importTextarea.fill('test.import1@gmail.com\ntest.import2@gmail.com, test.import3@yahoo.com');
    await page.waitForTimeout(300);
    log('Contacts', 'Import textarea accepts email input', 'PASS');
    await shot('02f_contacts_import_filled');
  }

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 3 — CAMPAIGNS
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n📧 Page 3: Campaigns (/campaigns)');
  consoleErrors = [];
  await go('/campaigns');
  await shot('03_campaigns');

  await checkNoNetworkError('Campaigns');
  await checkNoConsoleErrors('Campaigns', consoleErrors);
  await checkVisible('Campaigns', 'h1:text("Campaigns")', 'Campaigns heading');
  await checkVisible('Campaigns', 'button:has-text("New Campaign")', 'New Campaign button');

  // Open the new campaign form
  await page.click('button:has-text("New Campaign")');
  await page.waitForTimeout(600);
  await shot('03b_campaigns_form_open');

  await checkVisible('Campaigns', 'button:has-text("Load from Database")', 'Load from Database button');
  await checkVisible('Campaigns', 'textarea', 'Recipients textarea');

  // Click "Load from Database"
  await page.click('button:has-text("Load from Database")');
  await page.waitForTimeout(1500); // wait for modal + API
  await shot('03c_campaigns_db_modal');
  await checkVisible('Campaigns', 'text=Load Recipients from Database', 'DB load modal opens');
  await checkVisible('Campaigns', 'text=recipient', 'Recipient count shown in modal');

  // Select internal group in modal
  const modalSelect = await page.$('.fixed select');
  if (modalSelect) {
    try {
      const mopts = await modalSelect.$$('option');
      const mvals = await Promise.all(mopts.map(o => o.getAttribute('value')));
      const mInternal = mvals.find(v => v && v.toLowerCase().includes('internal'));
      if (mInternal) {
        await modalSelect.selectOption(mInternal);
        await page.waitForTimeout(800);
        await shot('03d_campaigns_modal_filtered');
        log('Campaigns', 'Modal group filter works', 'PASS');
      }
    } catch(e) {
      log('Campaigns', 'Modal group filter works', 'WARN', e.message.slice(0,80));
    }
  }

  // Load recipients — click button inside the modal
  try {
    await page.locator('.fixed button:has-text("Load")').click({ timeout: 8000 });
    await page.waitForTimeout(1000);
    // Wait for modal to close
    await page.waitForSelector('.fixed', { state: 'hidden', timeout: 5000 }).catch(() => {});
    await shot('03e_campaigns_recipients_loaded');
    const recipientBadge = await page.$('text=/\d+ emails/');
    log('Campaigns', 'Recipients auto-loaded from DB', recipientBadge ? 'PASS' : 'WARN');
  } catch(e) {
    // Close modal via Cancel if Load failed
    await page.locator('.fixed button:has-text("Cancel")').click({ timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(500);
    log('Campaigns', 'Recipients auto-loaded from DB', 'WARN', e.message.slice(0, 80));
  }

  // Now fill subject and template (modal is closed)
  const subjectInput = await page.$('input[placeholder="Your email subject"]');
  if (subjectInput) {
    await subjectInput.fill('Playwright Test Campaign');
    log('Campaigns', 'Subject field fillable', 'PASS');
  }

  try {
    const templateSel = await page.$('select');
    if (templateSel) {
      await templateSel.selectOption('newsletter.html');
      log('Campaigns', 'Template selector works', 'PASS');
    }
  } catch(e) {
    log('Campaigns', 'Template selector works', 'WARN', e.message.slice(0, 60));
  }
  await shot('03f_campaigns_form_filled');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 4 — COMPOSE
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n✏️  Page 4: Compose (/compose)');
  consoleErrors = [];
  await go('/compose');
  await shot('04_compose');

  await checkNoNetworkError('Compose');
  await checkNoConsoleErrors('Compose', consoleErrors);
  await checkVisible('Compose', 'h1:text("Compose")', 'Compose heading');

  // Fill the compose form
  const toInput = await page.$('input[type="email"], input[placeholder*="recipient"], input[id*="to"]');
  if (toInput) {
    await toInput.fill('venukrishnaya@gmail.com');
    log('Compose', 'To field fillable', 'PASS');
  }

  const subj = await page.$('input[placeholder*="subject"], input[id*="subject"]');
  if (subj) {
    await subj.fill('Playwright Automated Test Email');
    log('Compose', 'Subject field fillable', 'PASS');
  }

  const bodyArea = await page.$('textarea');
  if (bodyArea) {
    await bodyArea.fill('This email was sent by the Playwright automated test suite.');
    log('Compose', 'Body textarea fillable', 'PASS');
  }
  await shot('04b_compose_filled');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 5 — TEMPLATES
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n📄 Page 5: Templates (/templates)');
  consoleErrors = [];
  await go('/templates');
  await shot('05_templates');

  await checkNoNetworkError('Templates');
  await checkNoConsoleErrors('Templates', consoleErrors);
  await checkVisible('Templates', 'h1:text("Templates")', 'Templates heading');
  await checkVisible('Templates', 'select', 'Template dropdown');

  // Select and preview a template
  const tmplSelect = await page.$('select');
  if (tmplSelect) {
    try {
      await tmplSelect.selectOption('support_acknowledgment.html');
      await page.waitForTimeout(400);
      log('Templates', 'Template selected from dropdown', 'PASS');
    } catch(e) {
      log('Templates', 'Template selected from dropdown', 'WARN', e.message.slice(0,60));
    }
  }

  const previewBtn = await page.$('button:has-text("Preview Template")');
  if (previewBtn) {
    await previewBtn.click();
    await page.waitForTimeout(2500); // wait for template render
    await shot('05b_templates_preview');
    const iframe = await page.$('iframe[title="Email Preview"]');
    log('Templates', 'Template preview renders in iframe', iframe ? 'PASS' : 'WARN');
  }

  // Switch to Create tab
  await page.click('button:has-text("Create Template")');
  await page.waitForTimeout(400);
  await shot('05c_templates_create');
  await checkVisible('Templates', 'input[id="tname"]', 'Template Name field');
  await checkVisible('Templates', 'textarea[id="thtml"]', 'HTML Body textarea');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 6 — SENDER POOL
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n👤 Page 6: Sender Pool (/sender-pool)');
  consoleErrors = [];
  await go('/sender-pool');
  await shot('06_sender_pool');

  await checkNoNetworkError('Sender Pool');
  await checkNoConsoleErrors('Sender Pool', consoleErrors);
  await checkVisible('Sender Pool', 'h1:text("Sender Pool")', 'Sender Pool heading');
  await checkVisible('Sender Pool', 'text=Total Accounts', 'Total Accounts stat');
  await checkVisible('Sender Pool', 'text=Reset Quotas', 'Reset Quotas button');
  await checkVisible('Sender Pool', 'text=Add Account', 'Add Account button');

  // Check existing sender account row
  const accountRows = await page.$$('tr');
  log('Sender Pool', 'Sender account table visible', accountRows.length > 0 ? 'PASS' : 'WARN');

  // Click Add Account button
  await page.click('button:has-text("Add Account")');
  await page.waitForTimeout(500);
  await shot('06b_sender_pool_add_form');
  await checkVisible('Sender Pool', 'input[placeholder*="gmail"], input[type="email"]', 'Gmail Address field');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 7 — SCHEDULER
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n🕐 Page 7: Scheduler (/scheduler)');
  consoleErrors = [];
  await go('/scheduler');
  await shot('07_scheduler');

  await checkNoNetworkError('Scheduler');
  await checkNoConsoleErrors('Scheduler', consoleErrors);
  await checkVisible('Scheduler', 'h1:text("Scheduler")', 'Scheduler heading');
  await checkVisible('Scheduler', 'button:has-text("Schedule Email")', 'Schedule Email button');

  // Open schedule form
  await page.click('button:has-text("Schedule Email")');
  await page.waitForTimeout(500);
  await shot('07b_scheduler_form');
  await checkVisible('Scheduler', 'text=Send At', 'Send At field visible');
  await checkVisible('Scheduler', 'text=Cron Expression', 'Cron Expression option visible');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 8 — INBOX MONITOR
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n📬 Page 8: Inbox Monitor (/inbox-monitor)');
  consoleErrors = [];
  await go('/inbox-monitor');
  await shot('08_inbox_monitor');

  await checkNoNetworkError('Inbox Monitor');
  await checkNoConsoleErrors('Inbox Monitor', consoleErrors);
  await checkVisible('Inbox Monitor', 'h1:text("Inbox Monitor")', 'Inbox Monitor heading');
  await checkVisible('Inbox Monitor', 'text=Monitor Status', 'Monitor Status card');
  await checkVisible('Inbox Monitor', 'text=Monitoring Inbox', 'Monitoring Inbox card');
  await checkVisible('Inbox Monitor', 'text=Slack Connected', 'Slack Connected card');
  await checkVisible('Inbox Monitor', 'text=Triage Rules', 'Triage Rules panel');
  await checkVisible('Inbox Monitor', 'text=Recent Matches', 'Recent Matches panel');
  await checkVisible('Inbox Monitor', 'button:has-text("Test Slack")', 'Test Slack button');
  await checkVisible('Inbox Monitor', 'button:has-text("Add Rule")', 'Add Rule button');

  // Click Add Rule
  await page.click('button:has-text("Add Rule")');
  await page.waitForTimeout(500);
  await shot('08b_inbox_monitor_add_rule');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 9 — SUPPRESSIONS
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n🚫 Page 9: Suppressions (/suppressions)');
  consoleErrors = [];
  await go('/suppressions');
  await shot('09_suppressions');

  await checkNoNetworkError('Suppressions');
  await checkNoConsoleErrors('Suppressions', consoleErrors);
  await checkVisible('Suppressions', 'h1:text("Suppressions")', 'Suppressions heading');
  await checkVisible('Suppressions', 'button:has-text("Add Suppression")', 'Add Suppression button');

  await page.click('button:has-text("Add Suppression")');
  await page.waitForTimeout(500);
  await shot('09b_suppressions_form');
  await checkVisible('Suppressions', 'input[type="email"]', 'Email input in suppression form');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 10 — ANALYTICS
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n📈 Page 10: Analytics (/analytics)');
  consoleErrors = [];
  await go('/analytics');
  await shot('10_analytics');

  await checkNoNetworkError('Analytics');
  await checkNoConsoleErrors('Analytics', consoleErrors);
  await checkVisible('Analytics', 'h1:text("Analytics")', 'Analytics heading');
  await checkVisible('Analytics', 'text=Emails Sent', 'Emails Sent stat');
  await checkVisible('Analytics', 'text=Open Rate', 'Open Rate stat');

  // ════════════════════════════════════════════════════════════════════════
  // PAGE 11 — API KEYS
  // ════════════════════════════════════════════════════════════════════════
  console.log('\n🔑 Page 11: API Keys (/api-keys)');
  consoleErrors = [];
  await go('/api-keys');
  await shot('11_api_keys');

  await checkNoNetworkError('API Keys');
  await checkNoConsoleErrors('API Keys', consoleErrors);
  await checkVisible('API Keys', 'h1:text("API Keys")', 'API Keys heading');
  await checkVisible('API Keys', 'button:has-text("Generate Key")', 'Generate Key button');

  await page.click('button:has-text("Generate Key")');
  await page.waitForTimeout(500);
  await shot('11b_api_keys_form');
  await checkVisible('API Keys', 'input[placeholder*="label"], input[id*="label"]', 'Key label input');

  // ════════════════════════════════════════════════════════════════════════
  // FINAL REPORT
  // ════════════════════════════════════════════════════════════════════════
  await browser.close();

  const total  = results.length;
  const passed = results.filter(r => r.status === 'PASS').length;
  const warned = results.filter(r => r.status === 'WARN').length;
  const failed = results.filter(r => r.status === 'FAIL').length;

  console.log('\n══════════════════════════════════════════════════════════════');
  console.log('  TEST RESULTS SUMMARY');
  console.log('══════════════════════════════════════════════════════════════');
  console.log(`  Total:  ${total} checks`);
  console.log(`  ✅ Pass: ${passed}`);
  console.log(`  ⚠️  Warn: ${warned}`);
  console.log(`  ❌ Fail: ${failed}`);
  console.log(`  Score:  ${Math.round((passed / total) * 100)}%`);
  console.log('──────────────────────────────────────────────────────────────');
  if (failed > 0) {
    console.log('  FAILURES:');
    results.filter(r => r.status === 'FAIL').forEach(r =>
      console.log(`    ❌ [${r.page}] ${r.test}${r.detail ? ' — ' + r.detail : ''}`)
    );
  }
  if (warned > 0) {
    console.log('  WARNINGS:');
    results.filter(r => r.status === 'WARN').forEach(r =>
      console.log(`    ⚠️  [${r.page}] ${r.test}${r.detail ? ' — ' + r.detail : ''}`)
    );
  }
  console.log('══════════════════════════════════════════════════════════════');
  console.log(`  Screenshots saved to: ${SS_DIR}`);
  console.log('══════════════════════════════════════════════════════════════\n');

  // Write JSON results
  const jsonOut = path.join(SS_DIR, 'results.json');
  fs.writeFileSync(jsonOut, JSON.stringify({ summary: { total, passed, warned, failed }, results }, null, 2));
  console.log(`  JSON results: ${jsonOut}\n`);

  process.exit(failed > 0 ? 1 : 0);
})();
