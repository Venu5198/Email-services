'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listScheduledJobs, scheduleJob, cancelScheduledJob } from '@/lib/api'
import { Card, Btn, Input, Select, SectionTitle, Spinner, Table, StatusBadge, EmptyState } from '@/components/ui'
import { Clock, Plus, Trash2, CheckCircle, AlertCircle } from 'lucide-react'
import { formatDate } from '@/lib/utils'

const TEMPLATES = ['newsletter.html','product_promotion.html','demo_booking_confirm.html','internal_incident_alert.html','support_acknowledgment.html']

export default function SchedulerPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [mode, setMode] = useState('once')
  const [msg, setMsg] = useState(null)
  const [form, setForm] = useState({
    to: '', subject: '', template_name: '', body_text: '', from_name: 'SyncRivo',
    send_at: '', cron_expression: '0 9 * * MON', job_name: '',
  })
  const [statusFilter, setStatusFilter] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['scheduled-jobs', statusFilter],
    queryFn: () => listScheduledJobs(statusFilter || undefined),
    refetchInterval: 15000,
  })
  const jobs = data?.data?.jobs || []

  const createMut = useMutation({
    mutationFn: () => scheduleJob({
      email: {
        to_emails: form.to.split(',').map(e => e.trim()).filter(Boolean),
        subject: form.subject || undefined,
        template_name: form.template_name || undefined,
        body_text: form.body_text || undefined,
        from_name: form.from_name,
      },
      send_at: mode === 'once' ? form.send_at : undefined,
      cron_expression: mode === 'cron' ? form.cron_expression : undefined,
      job_name: form.job_name || undefined,
    }),
    onSuccess: () => { qc.invalidateQueries(['scheduled-jobs']); setShowForm(false); setMsg({ ok: true, text: 'Job scheduled!' }) },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  const cancelMut = useMutation({
    mutationFn: jobId => cancelScheduledJob(jobId),
    onSuccess: () => { qc.invalidateQueries(['scheduled-jobs']); setMsg({ ok: true, text: 'Job cancelled.' }) },
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Scheduler</h1>
          <p className="text-slate-500 text-sm mt-1">Schedule one-time or recurring email jobs</p>
        </div>
        <Btn onClick={() => setShowForm(s => !s)}><Plus size={14} /> New Job</Btn>
      </div>

      {msg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {msg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />} {msg.text}
        </div>
      )}

      {showForm && (
        <Card className="mb-6">
          <SectionTitle>Schedule Email Job</SectionTitle>
          {/* Mode toggle */}
          <div className="flex gap-2 mb-5">
            {['once', 'cron'].map(m => (
              <Btn key={m} size="sm" variant={mode === m ? 'primary' : 'secondary'} onClick={() => setMode(m)}>
                {m === 'once' ? '📅 One-time' : '🔄 Recurring (Cron)'}
              </Btn>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <Input id="s-to" label="To Emails *" placeholder="email1@example.com, email2@example.com" value={form.to} onChange={e => setForm(f => ({ ...f, to: e.target.value }))} />
            <Input id="s-name" label="Job Name" placeholder="Weekly Newsletter" value={form.job_name} onChange={e => setForm(f => ({ ...f, job_name: e.target.value }))} />
            <Input id="s-subject" label="Subject" placeholder="Your subject line" value={form.subject} onChange={e => setForm(f => ({ ...f, subject: e.target.value }))} />
            <Select id="s-tmpl" label="Template (optional)" value={form.template_name} onChange={e => setForm(f => ({ ...f, template_name: e.target.value }))}>
              <option value="">— No template —</option>
              {TEMPLATES.map(t => <option key={t} value={t}>{t}</option>)}
            </Select>
            {mode === 'once' ? (
              <div className="col-span-2">
                <Input id="s-at" label="Send At (UTC) *" type="datetime-local" value={form.send_at} onChange={e => setForm(f => ({ ...f, send_at: e.target.value + ':00Z' }))} />
              </div>
            ) : (
              <div className="col-span-2">
                <Input id="s-cron" label='Cron Expression (5-field)' placeholder="0 9 * * MON — every Monday 9am" value={form.cron_expression} onChange={e => setForm(f => ({ ...f, cron_expression: e.target.value }))} />
                <p className="text-slate-500 text-xs mt-1.5">Examples: <code>0 9 * * *</code> = daily 9am · <code>0 9 * * MON</code> = Monday 9am · <code>0 0 1 * *</code> = 1st of month</p>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <Btn onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.to}>
              <Clock size={14} /> {createMut.isPending ? 'Scheduling…' : 'Schedule Job'}
            </Btn>
            <Btn variant="secondary" onClick={() => setShowForm(false)}>Cancel</Btn>
          </div>
        </Card>
      )}

      <Card>
        <div className="flex items-center gap-3 mb-5">
          <Select id="filter" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="sent">Sent</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </Select>
          <span className="text-slate-400 text-sm">{jobs.length} jobs</span>
        </div>

        {isLoading ? <Spinner /> : (
          <Table
            headers={['Job Name', 'Type', 'Next Run', 'Status', 'Runs', 'Actions']}
            empty={jobs.length === 0 ? <EmptyState icon={Clock} message="No scheduled jobs" /> : null}
          >
            {jobs.map(j => (
              <tr key={j.job_id} className="hover:bg-slate-800/30 transition-colors">
                <td className="px-4 py-3">
                  <p className="text-sm text-white font-medium">{j.job_name}</p>
                  <p className="text-xs text-slate-500 font-mono">{j.job_id?.slice(0, 8)}…</p>
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {j.cron_expression ? <code>{j.cron_expression}</code> : 'One-time'}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">{formatDate(j.next_run_at || j.send_at)}</td>
                <td className="px-4 py-3"><StatusBadge status={j.status} /></td>
                <td className="px-4 py-3 text-sm text-slate-400">{j.run_count || 0}</td>
                <td className="px-4 py-3">
                  {j.status === 'pending' && (
                    <Btn variant="danger" size="sm" onClick={() => cancelMut.mutate(j.job_id)}>
                      <Trash2 size={12} /> Cancel
                    </Btn>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  )
}
