'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getMonitorStatus, listInboxRules, createInboxRule, deleteInboxRule, listInboxMatches, testSlack } from '@/lib/api'
import { Card, Btn, Input, Select, SectionTitle, Spinner, Table, StatusBadge, Badge, EmptyState } from '@/components/ui'
import { Inbox, Plus, Trash2, Bell, CheckCircle, AlertCircle, Zap } from 'lucide-react'
import { formatDate, SEVERITY_COLORS } from '@/lib/utils'

export default function InboxMonitorPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [slackMsg, setSlackMsg] = useState(null)
  const [msg, setMsg] = useState(null)
  const [form, setForm] = useState({
    rule_name: '', keywords: '', severity: 'high',
    auto_reply_template: '', from_domain_filter: '', is_active: true,
  })

  const { data: statusRes } = useQuery({ queryKey: ['monitor-status'], queryFn: getMonitorStatus, refetchInterval: 30000 })
  const { data: rulesRes, isLoading: rulesLoading } = useQuery({ queryKey: ['inbox-rules'], queryFn: listInboxRules })
  const { data: matchesRes, isLoading: matchesLoading } = useQuery({ queryKey: ['inbox-matches'], queryFn: () => listInboxMatches(20), refetchInterval: 30000 })

  const status = statusRes?.data || {}
  const rules = rulesRes?.data || []
  const matches = matchesRes?.data || []

  const createMut = useMutation({
    mutationFn: () => createInboxRule({
      rule_name: form.rule_name,
      keywords: form.keywords.split(',').map(k => k.trim()).filter(Boolean),
      severity: form.severity,
      auto_reply_template: form.auto_reply_template || undefined,
      from_domain_filter: form.from_domain_filter || undefined,
      notify_channels: ['slack'],
      is_active: form.is_active,
    }),
    onSuccess: () => { qc.invalidateQueries(['inbox-rules']); setShowForm(false); setMsg({ ok: true, text: 'Rule saved!' }) },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  const deleteMut = useMutation({
    mutationFn: name => deleteInboxRule(name),
    onSuccess: () => qc.invalidateQueries(['inbox-rules']),
  })

  const testSlackMut = useMutation({
    mutationFn: () => testSlack('medium', 'SyncRivo Test Alert', 'This is a manual Slack test from the admin dashboard.'),
    onSuccess: () => setSlackMsg({ ok: true, text: 'Slack notification sent! Check your channel.' }),
    onError: e => setSlackMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Inbox Monitor</h1>
          <p className="text-slate-500 text-sm mt-1">Keyword triage rules for incoming support emails</p>
        </div>
        <div className="flex gap-2">
          <Btn variant="secondary" onClick={() => testSlackMut.mutate()} disabled={testSlackMut.isPending}>
            <Bell size={14} className={testSlackMut.isPending ? 'animate-pulse' : ''} />
            {testSlackMut.isPending ? 'Sending…' : 'Test Slack'}
          </Btn>
          <Btn onClick={() => setShowForm(s => !s)}><Plus size={14} /> Add Rule</Btn>
        </div>
      </div>

      {/* Status card */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <Card className="!p-4">
          <p className="text-slate-400 text-xs mb-1">Monitor Status</p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`w-2 h-2 rounded-full ${status.is_running ? 'bg-green-400 animate-pulse' : 'bg-slate-500'}`} />
            <p className="text-white font-semibold text-sm">{status.is_running ? 'Running' : 'Stopped'}</p>
          </div>
        </Card>
        <Card className="!p-4">
          <p className="text-slate-400 text-xs mb-1">Monitoring Inbox</p>
          <p className="text-white text-sm font-medium mt-1 truncate">{status.monitoring_inbox || '—'}</p>
        </Card>
        <Card className="!p-4">
          <p className="text-slate-400 text-xs mb-1">Slack Connected</p>
          <Badge color={status.slack_configured ? 'green' : 'red'}>{status.slack_configured ? '✓ Configured' : '✗ Not set'}</Badge>
        </Card>
      </div>

      {slackMsg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${slackMsg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {slackMsg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />} {slackMsg.text}
          <button className="ml-auto text-xs opacity-60 hover:opacity-100" onClick={() => setSlackMsg(null)}>✕</button>
        </div>
      )}

      {msg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {msg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />} {msg.text}
        </div>
      )}

      {showForm && (
        <Card className="mb-6">
          <SectionTitle>Create Triage Rule</SectionTitle>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <Input id="rname" label="Rule Name *" placeholder="critical_incident_triage" value={form.rule_name} onChange={e => setForm(f => ({ ...f, rule_name: e.target.value }))} />
            <Select id="rsev" label="Severity" value={form.severity} onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </Select>
            <div className="col-span-2">
              <Input id="rkw" label="Keywords (comma-separated) *" placeholder="urgent, down, outage, critical, broken" value={form.keywords} onChange={e => setForm(f => ({ ...f, keywords: e.target.value }))} />
            </div>
            <Input id="rdomain" label="From Domain Filter (optional)" placeholder="gmail.com" value={form.from_domain_filter} onChange={e => setForm(f => ({ ...f, from_domain_filter: e.target.value }))} />
            <Input id="rtempl" label="Auto-reply Template (optional)" placeholder="support_acknowledgment.html" value={form.auto_reply_template} onChange={e => setForm(f => ({ ...f, auto_reply_template: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <Btn onClick={() => createMut.mutate()} disabled={createMut.isPending || !form.rule_name || !form.keywords}>
              {createMut.isPending ? 'Saving…' : 'Save Rule'}
            </Btn>
            <Btn variant="secondary" onClick={() => setShowForm(false)}>Cancel</Btn>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <SectionTitle>Triage Rules ({rules.length})</SectionTitle>
          {rulesLoading ? <Spinner /> : rules.length === 0 ? <EmptyState icon={Inbox} message="No rules configured" /> : (
            <div className="space-y-3">
              {rules.map(r => {
                const sc = SEVERITY_COLORS[r.severity] || SEVERITY_COLORS.medium
                return (
                  <div key={r.rule_name} className={`${sc.bg} border ${sc.border} rounded-xl p-4`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`w-2 h-2 rounded-full ${sc.dot}`} />
                          <p className={`text-sm font-semibold ${sc.text}`}>{r.rule_name}</p>
                          <Badge color={r.severity === 'critical' ? 'red' : r.severity === 'high' ? 'orange' : r.severity === 'medium' ? 'yellow' : 'green'}>
                            {r.severity}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {(r.keywords || []).map(kw => (
                            <code key={kw} className="text-xs bg-slate-900/50 text-slate-300 px-1.5 py-0.5 rounded">{kw}</code>
                          ))}
                        </div>
                        {r.auto_reply_template && <p className="text-xs text-slate-400 mt-2">Auto-reply: {r.auto_reply_template}</p>}
                      </div>
                      <Btn variant="danger" size="sm" onClick={() => deleteMut.mutate(r.rule_name)}>
                        <Trash2 size={12} />
                      </Btn>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        <Card>
          <SectionTitle>Recent Matches</SectionTitle>
          {matchesLoading ? <Spinner /> : matches.length === 0 ? <EmptyState icon={Zap} message="No inbox matches yet" /> : (
            <div className="space-y-3 max-h-[480px] overflow-y-auto pr-1">
              {matches.map((m, i) => (
                <div key={i} className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-white font-medium truncate max-w-[200px]">{m.sender}</span>
                    <StatusBadge status={m.severity} />
                  </div>
                  <p className="text-xs text-slate-400 mb-2">"{m.subject}"</p>
                  <div className="flex flex-wrap gap-1">
                    {(m.matched_keywords || []).map(kw => (
                      <code key={kw} className="text-xs bg-slate-700 text-violet-300 px-1.5 py-0.5 rounded">{kw}</code>
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 mt-2">{formatDate(m.matched_at)}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
