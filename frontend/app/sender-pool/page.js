'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listSenderAccounts, addSenderAccount, removeSenderAccount, updateSenderAccount, resetSenderQuotas } from '@/lib/api'
import { Card, Btn, Input, Select, SectionTitle, Spinner, Table, StatusBadge } from '@/components/ui'
import { Plus, RefreshCw, Trash2, Power, CheckCircle, AlertCircle } from 'lucide-react'
import { formatPct } from '@/lib/utils'

export default function SenderPoolPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ email: '', smtp_password: '', display_name: 'SyncRivo', daily_limit: 500 })
  const [msg, setMsg] = useState(null)

  const { data, isLoading } = useQuery({ queryKey: ['sender-accounts'], queryFn: listSenderAccounts, refetchInterval: 30000 })
  const accounts = data?.data?.accounts || []
  const summary = data?.data || {}

  const addMut = useMutation({
    mutationFn: () => addSenderAccount(form),
    onSuccess: () => { qc.invalidateQueries(['sender-accounts']); setShowForm(false); setMsg({ ok: true, text: 'Account added!' }) },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  const resetMut = useMutation({
    mutationFn: resetSenderQuotas,
    onSuccess: () => { qc.invalidateQueries(['sender-accounts']); setMsg({ ok: true, text: 'Quotas reset!' }) },
  })

  const deleteMut = useMutation({
    mutationFn: email => removeSenderAccount(email),
    onSuccess: () => qc.invalidateQueries(['sender-accounts']),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Sender Pool</h1>
          <p className="text-slate-500 text-sm mt-1">Manage sender accounts · {accounts.length} registered</p>
        </div>
        <div className="flex gap-2">
          <Btn variant="secondary" onClick={() => resetMut.mutate()} disabled={resetMut.isPending}>
            <RefreshCw size={14} className={resetMut.isPending ? 'animate-spin' : ''} /> Reset Quotas
          </Btn>
          <Btn onClick={() => setShowForm(s => !s)}><Plus size={14} /> Add Account</Btn>
        </div>
      </div>

      {msg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {msg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />} {msg.text}
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Total Accounts', value: summary.total_accounts || accounts.length },
          { label: 'Sent Today', value: (summary.total_sent_today ?? 0).toLocaleString() },
          { label: 'Remaining Today', value: (summary.total_remaining_today ?? summary.total_daily_capacity ?? 0).toLocaleString() },
        ].map(s => (
          <Card key={s.label} className="!p-4">
            <p className="text-slate-400 text-xs">{s.label}</p>
            <p className="text-white text-2xl font-bold mt-1">{s.value}</p>
          </Card>
        ))}
      </div>

      {/* Add Form */}
      {showForm && (
        <Card className="mb-6">
          <SectionTitle>Add Sender Account</SectionTitle>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <Input id="email" label="Gmail Address *" placeholder="sender@gmail.com" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            <Input id="pass" label="App Password *" type="password" placeholder="xxxx xxxx xxxx xxxx" value={form.smtp_password} onChange={e => setForm(f => ({ ...f, smtp_password: e.target.value }))} />
            <Input id="dname" label="Display Name" placeholder="SyncRivo" value={form.display_name} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} />
            <Input id="limit" label="Daily Limit" type="number" min="1" max="2000" value={form.daily_limit} onChange={e => setForm(f => ({ ...f, daily_limit: Number(e.target.value) }))} />
          </div>
          <div className="flex gap-2">
            <Btn onClick={() => addMut.mutate()} disabled={addMut.isPending || !form.email || !form.smtp_password}>
              {addMut.isPending ? 'Adding…' : 'Add Account'}
            </Btn>
            <Btn variant="secondary" onClick={() => setShowForm(false)}>Cancel</Btn>
          </div>
        </Card>
      )}

      {/* Accounts Table */}
      {isLoading ? <Spinner /> : (
        <Card>
          <Table headers={['Email', 'Display Name', 'Sent Today', 'Daily Limit', 'Usage', 'Status', 'Actions']}>
            {accounts.map(acc => (
              <tr key={acc.email} className="hover:bg-slate-800/30 transition-colors">
                <td className="px-4 py-3 text-sm text-slate-300">{acc.email}</td>
                <td className="px-4 py-3 text-sm text-slate-400">{acc.display_name}</td>
                <td className="px-4 py-3 text-sm text-white font-medium">{acc.sent_today}</td>
                <td className="px-4 py-3 text-sm text-slate-400">{acc.daily_limit}</td>
                <td className="px-4 py-3 w-32">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-slate-700 rounded-full">
                      <div
                        className={`h-full rounded-full ${(acc.usage_pct || 0) > 80 ? 'bg-red-500' : 'bg-violet-500'}`}
                        style={{ width: `${Math.min(acc.usage_pct || 0, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-400 w-10 text-right">{formatPct(acc.usage_pct)}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={acc.is_active ? 'active' : 'inactive'} />
                </td>
                <td className="px-4 py-3">
                  <Btn variant="danger" size="sm" onClick={() => deleteMut.mutate(acc.email)}>
                    <Trash2 size={12} />
                  </Btn>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  )
}
