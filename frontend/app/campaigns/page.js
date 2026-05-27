'use client'
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listBulkJobs, createBulkJob, getCampaignAnalytics, listContacts, listContactGroups } from '@/lib/api'
import { Card, Btn, Input, Textarea, SectionTitle, Spinner } from '@/components/ui'
import {
  Layers, Plus, BarChart2, CheckCircle, AlertCircle,
  ChevronDown, ChevronUp, Database, Users, X, RefreshCw
} from 'lucide-react'
import { formatDate, formatNumber, formatPct } from '@/lib/utils'

const TEMPLATES = [
  'newsletter.html','product_promotion.html','demo_booking_confirm.html',
  'internal_incident_alert.html','support_acknowledgment.html',
  'video_announcement.html','welcome.html','form_submission_ack.html',
  'inquiry_auto_reply.html','marketing_article.html',
]

const STATUS_COLORS = {
  completed: 'bg-green-500/15 text-green-400 border-green-500/30',
  pending:   'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  running:   'bg-blue-500/15 text-blue-400 border-blue-500/30',
  failed:    'bg-red-500/15 text-red-400 border-red-500/30',
}

export default function CampaignsPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [expandedJob, setExpandedJob] = useState(null)
  const [analytics, setAnalytics] = useState({})
  const [msg, setMsg] = useState(null)

  // ── Campaign form state ────────────────────────────────────────────────────
  const [form, setForm] = useState({
    to: '',
    template_name: '',
    subject: '',
    body_text: '',
    from_name: 'SyncRivo',
    throttle_per_second: 2,
  })

  // ── DB load modal state ────────────────────────────────────────────────────
  const [showDbModal, setShowDbModal] = useState(false)
  const [selectedGroup, setSelectedGroup] = useState('')
  const [dbActiveOnly, setDbActiveOnly] = useState(true)

  // ── Check sessionStorage for pre-filled recipients (from Contacts page) ───
  useEffect(() => {
    const stored = sessionStorage.getItem('campaign_recipients')
    if (stored) {
      setForm(f => ({ ...f, to: stored }))
      sessionStorage.removeItem('campaign_recipients')
      setShowForm(true)
      setMsg({ ok: true, text: `Recipients loaded from Contacts page (${stored.split(',').length} emails)` })
    }
  }, [])

  // ── Queries ────────────────────────────────────────────────────────────────
  const jobsQ = useQuery({
    queryKey: ['bulk-jobs'],
    queryFn: () => listBulkJobs().then(r => r.data),
    refetchInterval: 8000,
  })
  const jobs = jobsQ.data?.jobs || []

  const groupsQ = useQuery({
    queryKey: ['contact-groups'],
    queryFn: () => listContactGroups().then(r => r.data),
    enabled: showDbModal,
  })
  const groups = groupsQ.data?.groups || []

  const contactsQ = useQuery({
    queryKey: ['contacts-for-campaign', selectedGroup, dbActiveOnly],
    queryFn: () => listContacts(selectedGroup, dbActiveOnly).then(r => r.data),
    enabled: showDbModal,
  })
  const contactsData = contactsQ.data || {}

  // ── Load recipients from DB ────────────────────────────────────────────────
  const loadFromDb = () => {
    const csv = contactsData.email_csv || ''
    if (!csv) return
    setForm(f => ({ ...f, to: csv }))
    setShowDbModal(false)
    setMsg({ ok: true, text: `Loaded ${contactsData.returned} recipient(s) from database${selectedGroup ? ` [group: ${selectedGroup}]` : ''}` })
  }

  // ── Create campaign ────────────────────────────────────────────────────────
  const recipientList = form.to.split(',').map(e => e.trim()).filter(Boolean)

  const createMut = useMutation({
    mutationFn: () => createBulkJob({
      to_emails: recipientList,
      template_name: form.template_name || undefined,
      subject: form.subject || undefined,
      body_text: form.body_text || undefined,
      from_name: form.from_name,
      throttle_per_second: Number(form.throttle_per_second),
    }),
    onSuccess: (res) => {
      qc.invalidateQueries(['bulk-jobs'])
      setShowForm(false)
      setForm({ to: '', template_name: '', subject: '', body_text: '', from_name: 'SyncRivo', throttle_per_second: 2 })
      setMsg({ ok: true, text: `Campaign launched! Sending to ${recipientList.length} recipients. Job ID: ${res.data?.job_id?.slice(0,8)}…` })
    },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  // ── Analytics expand ───────────────────────────────────────────────────────
  const loadAnalytics = async (jobId) => {
    if (expandedJob === jobId) { setExpandedJob(null); return }
    setExpandedJob(jobId)
    if (!analytics[jobId]) {
      try {
        const res = await getCampaignAnalytics(jobId)
        setAnalytics(a => ({ ...a, [jobId]: res.data }))
      } catch {}
    }
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Campaigns</h1>
          <p className="text-slate-500 text-sm mt-1">Bulk email jobs — auto-refreshes every 8s</p>
        </div>
        <div className="flex gap-2">
          <Btn variant="secondary" size="sm" onClick={() => qc.invalidateQueries(['bulk-jobs'])}>
            <RefreshCw size={13} />
          </Btn>
          <Btn onClick={() => { setShowForm(s => !s) }}>
            <Plus size={14} /> New Campaign
          </Btn>
        </div>
      </div>

      {/* Message */}
      {msg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {msg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
          <span className="flex-1">{msg.text}</span>
          <button onClick={() => setMsg(null)} className="opacity-60 hover:opacity-100"><X size={14} /></button>
        </div>
      )}

      {/* ── Create Campaign Form ──────────────────────────────────────────────── */}
      {showForm && (
        <Card className="mb-6 border border-violet-500/20">
          <div className="flex items-center justify-between mb-4">
            <SectionTitle className="mb-0">New Bulk Campaign</SectionTitle>
            <button onClick={() => setShowForm(false)} className="text-slate-500 hover:text-white transition-colors">
              <X size={16} />
            </button>
          </div>

          <div className="space-y-4">
            {/* Recipient emails — with Load from DB button */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-slate-400">
                  Recipient Emails *
                  {recipientList.length > 0 && (
                    <span className="ml-2 px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-400 text-xs border border-violet-500/20">
                      {recipientList.length} emails
                    </span>
                  )}
                </label>
                <Btn size="sm" variant="secondary" onClick={() => setShowDbModal(true)}>
                  <Database size={12} /> Load from Database
                </Btn>
              </div>
              <textarea
                id="b-to"
                rows={4}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500 resize-y font-mono"
                placeholder="user1@example.com, user2@example.com&#10;— or click 'Load from Database' to auto-fill —"
                value={form.to}
                onChange={e => setForm(f => ({ ...f, to: e.target.value }))}
              />
              {recipientList.length > 0 && (
                <p className="text-xs text-slate-500 mt-1">
                  First 3: {recipientList.slice(0, 3).join(', ')}{recipientList.length > 3 ? ` +${recipientList.length - 3} more` : ''}
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1.5">Template</label>
                <select
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                  value={form.template_name}
                  onChange={e => setForm(f => ({ ...f, template_name: e.target.value }))}
                >
                  <option value="">— No template (use plain text) —</option>
                  {TEMPLATES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1.5">Subject *</label>
                <input
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                  placeholder="Your email subject"
                  value={form.subject}
                  onChange={e => setForm(f => ({ ...f, subject: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1.5">From Name</label>
                <input
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                  value={form.from_name}
                  onChange={e => setForm(f => ({ ...f, from_name: e.target.value }))}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1.5">
                  Throttle (emails/sec)
                  <span className="text-slate-500 font-normal ml-1">— 2 recommended for Gmail</span>
                </label>
                <input type="number" min="1" max="20"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                  value={form.throttle_per_second}
                  onChange={e => setForm(f => ({ ...f, throttle_per_second: Number(e.target.value) }))}
                />
              </div>
            </div>

            {!form.template_name && (
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1.5">Plain Text Body</label>
                <textarea rows={4}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500 resize-y"
                  placeholder="Your email body text (used when no template is selected)"
                  value={form.body_text}
                  onChange={e => setForm(f => ({ ...f, body_text: e.target.value }))}
                />
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <Btn
                onClick={() => createMut.mutate()}
                disabled={createMut.isPending || recipientList.length === 0 || (!form.template_name && !form.body_text)}
              >
                <Layers size={14} />
                {createMut.isPending ? `Launching…` : `Launch Campaign (${recipientList.length} recipients)`}
              </Btn>
              <Btn variant="secondary" onClick={() => setShowForm(false)}>Cancel</Btn>
            </div>

            {recipientList.length === 0 && (
              <p className="text-xs text-yellow-400/80">⚠ Add recipients manually or click "Load from Database"</p>
            )}
            {!form.template_name && !form.body_text && recipientList.length > 0 && (
              <p className="text-xs text-yellow-400/80">⚠ Select a template or enter plain text body</p>
            )}
          </div>
        </Card>
      )}

      {/* ── DB Load Modal ─────────────────────────────────────────────────────── */}
      {showDbModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 w-full max-w-lg shadow-2xl">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-violet-500/15 text-violet-400">
                  <Database size={18} />
                </div>
                <div>
                  <h3 className="text-white font-semibold">Load Recipients from Database</h3>
                  <p className="text-slate-500 text-xs">Select a group and filter to auto-populate recipients</p>
                </div>
              </div>
              <button onClick={() => setShowDbModal(false)} className="text-slate-500 hover:text-white transition-colors">
                <X size={18} />
              </button>
            </div>

            {/* Group filter */}
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1.5">Filter by Group</label>
                <select
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                  value={selectedGroup}
                  onChange={e => setSelectedGroup(e.target.value)}
                >
                  <option value="">All Groups</option>
                  {groups.map(g => (
                    <option key={g} value={g}>
                      {g} ({groupsQ.data?.counts?.[g] ?? '?'} contacts)
                    </option>
                  ))}
                </select>
              </div>

              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={dbActiveOnly} onChange={e => setDbActiveOnly(e.target.checked)}
                  className="accent-violet-500 w-4 h-4" />
                <span className="text-sm text-slate-300">Active contacts only</span>
              </label>
            </div>

            {/* Preview */}
            <div className="bg-slate-800 rounded-xl p-4 mb-5">
              {contactsQ.isLoading ? (
                <div className="flex justify-center py-4"><Spinner /></div>
              ) : (
                <>
                  <div className="flex items-center gap-2 mb-3">
                    <Users size={14} className="text-violet-400" />
                    <span className="text-sm font-semibold text-white">
                      {contactsData.returned ?? 0} recipient(s) will be loaded
                    </span>
                    {selectedGroup && (
                      <span className="px-2 py-0.5 rounded-full text-xs bg-violet-500/15 text-violet-400 border border-violet-500/20">
                        {selectedGroup}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 font-mono leading-relaxed max-h-32 overflow-y-auto">
                    {contactsData.email_csv
                      ? contactsData.email_csv.split(', ').slice(0, 8).join('\n') + (contactsData.returned > 8 ? `\n… and ${contactsData.returned - 8} more` : '')
                      : <span className="text-slate-600">No contacts found</span>
                    }
                  </div>
                </>
              )}
            </div>

            <div className="flex gap-3">
              <Btn
                className="flex-1 justify-center"
                onClick={loadFromDb}
                disabled={!contactsData.returned || contactsData.returned === 0}
              >
                <Database size={14} />
                Load {contactsData.returned > 0 ? `${contactsData.returned} Recipients` : 'Recipients'}
              </Btn>
              <Btn variant="secondary" onClick={() => setShowDbModal(false)}>Cancel</Btn>
            </div>
          </div>
        </div>
      )}

      {/* ── Jobs List ──────────────────────────────────────────────────────────── */}
      {jobsQ.isLoading ? <Spinner /> : (
        <div className="space-y-3">
          {jobs.length === 0 && (
            <div className="flex flex-col items-center py-20 text-slate-500">
              <Layers size={40} className="mb-3 opacity-20" />
              <p className="text-sm">No campaigns yet.</p>
              <Btn className="mt-4" onClick={() => setShowForm(true)}>
                <Plus size={14} /> Create your first campaign
              </Btn>
            </div>
          )}
          {jobs.map(job => {
            const an = analytics[job.job_id]
            const pct = job.total_recipients > 0 ? Math.min(((job.sent || 0) / job.total_recipients) * 100, 100) : 0
            const statusCls = STATUS_COLORS[job.status] || 'bg-slate-700/40 text-slate-400 border-slate-600/30'
            return (
              <Card key={job.job_id} className="!p-0 overflow-hidden">
                <div className="p-4 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${statusCls}`}>
                        {job.status}
                      </span>
                      <span className="text-xs text-slate-500 font-mono">{job.job_id?.slice(0, 12)}…</span>
                    </div>
                    <p className="text-sm text-slate-200 font-medium">
                      {job.template_name || 'Plain text email'}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">{formatDate(job.created_at)}</p>
                  </div>

                  <div className="flex gap-6 text-center shrink-0">
                    <div>
                      <p className="text-lg font-bold text-white">{formatNumber(job.total_recipients || 0)}</p>
                      <p className="text-xs text-slate-500">Total</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold text-green-400">{formatNumber(job.sent || 0)}</p>
                      <p className="text-xs text-slate-500">Sent</p>
                    </div>
                    <div>
                      <p className="text-lg font-bold text-red-400">{formatNumber(job.failed || 0)}</p>
                      <p className="text-xs text-slate-500">Failed</p>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-28 shrink-0">
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-violet-500 to-cyan-500 rounded-full transition-all duration-700"
                        style={{ width: `${pct}%` }} />
                    </div>
                    <p className="text-xs text-slate-500 text-center mt-1">{pct.toFixed(0)}%</p>
                  </div>

                  <button onClick={() => loadAnalytics(job.job_id)}
                    className="p-2 rounded-lg text-slate-400 hover:text-violet-400 hover:bg-violet-500/10 transition-colors">
                    <BarChart2 size={16} />
                    {expandedJob === job.job_id ? <ChevronUp size={12} className="mt-0.5" /> : <ChevronDown size={12} className="mt-0.5" />}
                  </button>
                </div>

                {/* Analytics panel */}
                {expandedJob === job.job_id && (
                  <div className="border-t border-slate-800 bg-slate-800/30 px-6 py-4">
                    {an ? (
                      <div className="grid grid-cols-4 gap-4 text-center">
                        <div>
                          <p className="text-xl font-bold text-green-400">{formatPct(an.open_rate_pct)}</p>
                          <p className="text-xs text-slate-500">Open Rate</p>
                        </div>
                        <div>
                          <p className="text-xl font-bold text-blue-400">{formatPct(an.click_rate_pct)}</p>
                          <p className="text-xs text-slate-500">Click Rate</p>
                        </div>
                        <div>
                          <p className="text-xl font-bold text-violet-400">{formatNumber(an.unique_openers)}</p>
                          <p className="text-xs text-slate-500">Unique Opens</p>
                        </div>
                        <div>
                          <p className="text-xl font-bold text-cyan-400">{formatNumber(an.unique_clickers)}</p>
                          <p className="text-xs text-slate-500">Unique Clicks</p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex justify-center py-3"><Spinner /></div>
                    )}
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
