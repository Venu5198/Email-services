'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listApiKeys, generateApiKey, revokeApiKey, deleteApiKey } from '@/lib/api'
import { Card, Btn, Input, Select, SectionTitle, Spinner, Table, Badge, EmptyState } from '@/components/ui'
import { Key, Plus, Trash2, ShieldOff, Copy, CheckCircle, AlertCircle, Eye, EyeOff } from 'lucide-react'
import { formatDate, MICROSERVICES } from '@/lib/utils'

export default function ApiKeysPage() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ service_name: '', description: '' })
  const [newKey, setNewKey] = useState(null)
  const [copied, setCopied] = useState(false)
  const [msg, setMsg] = useState(null)

  const { data, isLoading } = useQuery({ queryKey: ['api-keys'], queryFn: listApiKeys })
  const keys = data?.data?.api_keys || []

  const genMut = useMutation({
    mutationFn: () => generateApiKey(form),
    onSuccess: (res) => {
      qc.invalidateQueries(['api-keys'])
      setNewKey(res.data)
      setShowForm(false)
      setForm({ service_name: '', description: '' })
    },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  const revokeMut = useMutation({
    mutationFn: prefix => revokeApiKey(prefix),
    onSuccess: () => { qc.invalidateQueries(['api-keys']); setMsg({ ok: true, text: 'API key revoked.' }) },
  })

  const deleteMut = useMutation({
    mutationFn: prefix => deleteApiKey(prefix),
    onSuccess: () => { qc.invalidateQueries(['api-keys']); setMsg({ ok: true, text: 'API key deleted.' }) },
  })

  const copyKey = (k) => {
    navigator.clipboard.writeText(k)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">API Keys</h1>
          <p className="text-slate-500 text-sm mt-1">Generate keys per microservice for authenticated access</p>
        </div>
        <Btn onClick={() => setShowForm(s => !s)}><Plus size={14} /> Generate Key</Btn>
      </div>

      {msg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {msg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />} {msg.text}
        </div>
      )}

      {/* New Key Reveal */}
      {newKey && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-5 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle size={16} className="text-green-400" />
            <p className="text-green-400 font-semibold text-sm">API Key Generated — Save it now, it won't be shown again!</p>
          </div>
          <div className="bg-slate-900 rounded-lg p-3 flex items-center justify-between gap-3">
            <code className="text-violet-300 text-sm font-mono break-all">{newKey.api_key}</code>
            <Btn size="sm" variant="secondary" onClick={() => copyKey(newKey.api_key)}>
              <Copy size={12} /> {copied ? 'Copied!' : 'Copy'}
            </Btn>
          </div>
          <p className="text-slate-400 text-xs mt-2">Service: <strong>{newKey.service_name}</strong> · Prefix: <code>{newKey.prefix}</code></p>
          <Btn size="sm" variant="ghost" className="mt-3" onClick={() => setNewKey(null)}>Dismiss</Btn>
        </div>
      )}

      {showForm && (
        <Card className="mb-6">
          <SectionTitle>Generate API Key</SectionTitle>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">Service Name *</label>
              <select
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                value={form.service_name}
                onChange={e => setForm(f => ({ ...f, service_name: e.target.value }))}
              >
                <option value="">— Select microservice —</option>
                {MICROSERVICES.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <Input id="desc" label="Description (optional)" placeholder="Production key for CRM" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <Btn onClick={() => genMut.mutate()} disabled={genMut.isPending || !form.service_name}>
              <Key size={14} /> {genMut.isPending ? 'Generating…' : 'Generate Key'}
            </Btn>
            <Btn variant="secondary" onClick={() => setShowForm(false)}>Cancel</Btn>
          </div>
        </Card>
      )}

      <Card>
        {isLoading ? <Spinner /> : (
          <Table
            headers={['Service', 'Prefix', 'Description', 'Created', 'Status', 'Actions']}
            empty={keys.length === 0 ? <EmptyState icon={Key} message="No API keys yet" /> : null}
          >
            {keys.map(k => (
              <tr key={k.prefix} className="hover:bg-slate-800/30 transition-colors">
                <td className="px-4 py-3 text-sm text-violet-300 font-medium">{k.service_name}</td>
                <td className="px-4 py-3"><code className="text-xs text-slate-300 bg-slate-800 px-2 py-1 rounded">{k.prefix}…</code></td>
                <td className="px-4 py-3 text-sm text-slate-400">{k.description || '—'}</td>
                <td className="px-4 py-3 text-xs text-slate-500">{formatDate(k.created_at)}</td>
                <td className="px-4 py-3">
                  <Badge color={k.is_active ? 'green' : 'slate'}>{k.is_active ? 'Active' : 'Revoked'}</Badge>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    {k.is_active && (
                      <Btn variant="secondary" size="sm" onClick={() => revokeMut.mutate(k.prefix)}>
                        <ShieldOff size={12} /> Revoke
                      </Btn>
                    )}
                    <Btn variant="danger" size="sm" onClick={() => deleteMut.mutate(k.prefix)}>
                      <Trash2 size={12} />
                    </Btn>
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  )
}
