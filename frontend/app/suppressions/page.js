'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listSuppressions, addSuppression, removeSuppression } from '@/lib/api'
import { Card, Btn, Input, Select, SectionTitle, Spinner, Table, StatusBadge, EmptyState } from '@/components/ui'
import { ShieldOff, Plus, Trash2, Search, CheckCircle, AlertCircle } from 'lucide-react'
import { formatDate } from '@/lib/utils'

export default function SuppressionsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({ email: '', reason: 'manual' })
  const [showForm, setShowForm] = useState(false)
  const [msg, setMsg] = useState(null)

  const { data, isLoading } = useQuery({ queryKey: ['suppressions'], queryFn: () => listSuppressions(500) })
  const all = data?.data || []
  const filtered = all.filter(s => s.email?.toLowerCase().includes(search.toLowerCase()) || s.reason?.toLowerCase().includes(search.toLowerCase()))

  const addMut = useMutation({
    mutationFn: () => addSuppression(form.email, form.reason),
    onSuccess: () => { qc.invalidateQueries(['suppressions']); setForm({ email: '', reason: 'manual' }); setShowForm(false); setMsg({ ok: true, text: `${form.email} suppressed.` }) },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  const removeMut = useMutation({
    mutationFn: email => removeSuppression(email),
    onSuccess: () => qc.invalidateQueries(['suppressions']),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Suppression List</h1>
          <p className="text-slate-500 text-sm mt-1">{all.length} suppressed addresses — emails are never sent to these</p>
        </div>
        <Btn onClick={() => setShowForm(s => !s)}><Plus size={14} /> Add Suppression</Btn>
      </div>

      {msg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {msg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />} {msg.text}
        </div>
      )}

      {showForm && (
        <Card className="mb-6">
          <SectionTitle>Add to Suppression List</SectionTitle>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <Input id="sup-email" label="Email Address *" placeholder="user@example.com" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            <Select id="sup-reason" label="Reason" value={form.reason} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))}>
              <option value="manual">Manual</option>
              <option value="bounce">Bounce</option>
              <option value="spam_complaint">Spam Complaint</option>
              <option value="unsubscribed">Unsubscribed</option>
            </Select>
          </div>
          <div className="flex gap-2">
            <Btn onClick={() => addMut.mutate()} disabled={addMut.isPending || !form.email}>
              {addMut.isPending ? 'Adding…' : 'Add'}
            </Btn>
            <Btn variant="secondary" onClick={() => setShowForm(false)}>Cancel</Btn>
          </div>
        </Card>
      )}

      <Card>
        <div className="flex items-center gap-3 mb-5">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
              placeholder="Search email or reason…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>

        {isLoading ? <Spinner /> : (
          <Table
            headers={['Email', 'Reason', 'Suppressed At', 'Action']}
            empty={filtered.length === 0 ? <EmptyState icon={ShieldOff} message="No suppressed emails" /> : null}
          >
            {filtered.map(s => (
              <tr key={s.email} className="hover:bg-slate-800/30 transition-colors">
                <td className="px-4 py-3 text-sm text-slate-300 font-mono">{s.email}</td>
                <td className="px-4 py-3"><StatusBadge status={s.reason || 'manual'} /></td>
                <td className="px-4 py-3 text-sm text-slate-500">{formatDate(s.created_at)}</td>
                <td className="px-4 py-3">
                  <Btn variant="danger" size="sm" onClick={() => removeMut.mutate(s.email)}>
                    <Trash2 size={12} /> Remove
                  </Btn>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  )
}
