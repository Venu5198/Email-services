'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  listContacts, listContactGroups, getContactStats,
  createContact, importContacts, deleteContact, deactivateContact
} from '@/lib/api'
import { Card, Btn, Input, SectionTitle, Spinner } from '@/components/ui'
import {
  Users, Plus, Trash2, UserX, CheckCircle, AlertCircle,
  Upload, Download, Filter, RefreshCw, Send
} from 'lucide-react'

export default function ContactsPage() {
  const qc = useQueryClient()
  const [selectedGroup, setSelectedGroup] = useState('')
  const [activeOnly, setActiveOnly] = useState(true)
  const [msg, setMsg] = useState(null)
  const [tab, setTab] = useState('list')      // 'list' | 'add' | 'import'
  const [selected, setSelected] = useState(new Set())

  // ── Queries ──────────────────────────────────────────────────────────────
  const statsQ = useQuery({ queryKey: ['contact-stats'], queryFn: () => getContactStats().then(r => r.data) })
  const groupsQ = useQuery({ queryKey: ['contact-groups'], queryFn: () => listContactGroups().then(r => r.data) })
  const contactsQ = useQuery({
    queryKey: ['contacts', selectedGroup, activeOnly],
    queryFn: () => listContacts(selectedGroup, activeOnly).then(r => r.data),
  })

  const contacts = contactsQ.data?.contacts || []
  const groups = groupsQ.data?.groups || []
  const stats = statsQ.data || {}
  const emailCsv = contactsQ.data?.email_csv || ''

  // ── Add single contact ───────────────────────────────────────────────────
  const [form, setForm] = useState({ name: '', email: '', group: 'general', tags: '' })
  const addMut = useMutation({
    mutationFn: () => createContact({ ...form, tags: form.tags.split(',').map(t => t.trim()).filter(Boolean) }),
    onSuccess: () => {
      qc.invalidateQueries(['contacts']); qc.invalidateQueries(['contact-stats'])
      setForm({ name: '', email: '', group: 'general', tags: '' })
      setMsg({ ok: true, text: `Contact '${form.email}' added!` })
      setTab('list')
    },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  // ── Bulk import ──────────────────────────────────────────────────────────
  const [importText, setImportText] = useState('')
  const [importGroup, setImportGroup] = useState('general')

  const parseBulkEmails = (text) => {
    // Accept: newline, comma, semicolon separated — with optional "Name <email>" format
    const lines = text.split(/[\n,;]+/).map(l => l.trim()).filter(Boolean)
    return lines.map(line => {
      const match = line.match(/^(.+?)\s*<(.+?)>$/)
      if (match) return { name: match[1].trim(), email: match[2].trim(), group: importGroup, active: true }
      if (line.includes('@')) return { name: line.split('@')[0], email: line, group: importGroup, active: true }
      return null
    }).filter(Boolean)
  }

  const importMut = useMutation({
    mutationFn: () => {
      const parsed = parseBulkEmails(importText)
      if (!parsed.length) throw new Error('No valid emails found.')
      return importContacts(parsed)
    },
    onSuccess: (res) => {
      qc.invalidateQueries(['contacts']); qc.invalidateQueries(['contact-stats'])
      setImportText('')
      setMsg({ ok: true, text: res.data.message })
      setTab('list')
    },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  // ── Delete / Deactivate ───────────────────────────────────────────────────
  const deleteMut = useMutation({
    mutationFn: (email) => deleteContact(email),
    onSuccess: () => { qc.invalidateQueries(['contacts']); qc.invalidateQueries(['contact-stats']) },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })
  const deactivateMut = useMutation({
    mutationFn: (email) => deactivateContact(email),
    onSuccess: () => { qc.invalidateQueries(['contacts']); qc.invalidateQueries(['contact-stats']) },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  // ── Selection helpers ─────────────────────────────────────────────────────
  const toggleAll = () => {
    if (selected.size === contacts.length) setSelected(new Set())
    else setSelected(new Set(contacts.map(c => c.email)))
  }
  const toggleOne = (email) => {
    const s = new Set(selected)
    s.has(email) ? s.delete(email) : s.add(email)
    setSelected(s)
  }
  const selectedCsv = [...selected].join(', ')

  // ── Copy to clipboard ─────────────────────────────────────────────────────
  const copyEmails = (csv) => {
    navigator.clipboard?.writeText(csv)
    setMsg({ ok: true, text: `Copied ${csv.split(',').length} email(s) to clipboard!` })
    setTimeout(() => setMsg(null), 3000)
  }

  // ── Use in Campaign (navigate to campaigns with emails pre-filled) ─────────
  const useinCampaign = (csv) => {
    sessionStorage.setItem('campaign_recipients', csv)
    window.location.href = '/campaigns?from=contacts'
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Contacts</h1>
          <p className="text-slate-500 text-sm mt-1">Manage your recipient database for bulk campaigns</p>
        </div>
        <div className="flex gap-2">
          <Btn size="sm" variant="secondary" onClick={() => qc.invalidateQueries(['contacts'])}>
            <RefreshCw size={13} /> Refresh
          </Btn>
          <Btn size="sm" onClick={() => setTab('import')}>
            <Upload size={13} /> Import Emails
          </Btn>
          <Btn size="sm" onClick={() => setTab('add')}>
            <Plus size={13} /> Add Contact
          </Btn>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Contacts', val: stats.total ?? '—' },
          { label: 'Active',         val: stats.active ?? '—', color: 'text-green-400' },
          { label: 'Inactive',       val: stats.inactive ?? '—', color: 'text-slate-500' },
          { label: 'Groups',         val: stats.groups ?? '—', color: 'text-violet-400' },
        ].map(({ label, val, color }) => (
          <Card key={label} className="text-center py-4">
            <p className="text-slate-400 text-xs mb-1">{label}</p>
            <p className={`text-2xl font-bold ${color || 'text-white'}`}>{val}</p>
          </Card>
        ))}
      </div>

      {/* Message */}
      {msg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {msg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />} {msg.text}
          <button className="ml-auto opacity-60 hover:opacity-100" onClick={() => setMsg(null)}>✕</button>
        </div>
      )}

      {/* Tab Switcher */}
      <div className="flex gap-2 mb-6">
        {['list', 'add', 'import'].map(t => (
          <Btn key={t} size="sm" variant={tab === t ? 'primary' : 'secondary'} onClick={() => setTab(t)}>
            {t === 'list' ? <><Users size={13} /> Contact List</> : t === 'add' ? <><Plus size={13} /> Add Single</> : <><Upload size={13} /> Bulk Import</>}
          </Btn>
        ))}
      </div>

      {/* ── TAB: List ───────────────────────────────────────────────────────── */}
      {tab === 'list' && (
        <div className="space-y-4">
          {/* Filters + Bulk actions bar */}
          <Card className="flex flex-wrap items-center gap-3">
            {/* Group filter */}
            <div className="flex items-center gap-2">
              <Filter size={14} className="text-slate-400" />
              <select
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-violet-500"
                value={selectedGroup}
                onChange={e => { setSelectedGroup(e.target.value); setSelected(new Set()) }}
              >
                <option value="">All Groups</option>
                {groups.map(g => (
                  <option key={g} value={g}>{g} ({groupsQ.data?.counts?.[g] ?? 0})</option>
                ))}
              </select>
            </div>

            {/* Active toggle */}
            <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
              <input type="checkbox" checked={activeOnly} onChange={e => setActiveOnly(e.target.checked)}
                className="accent-violet-500" />
              Active only
            </label>

            <span className="text-slate-500 text-sm ml-auto">
              {contacts.length} contacts
              {selected.size > 0 && ` · ${selected.size} selected`}
            </span>

            {/* Action buttons */}
            {contacts.length > 0 && (
              <>
                <Btn size="sm" variant="secondary" onClick={() => copyEmails(selected.size > 0 ? selectedCsv : emailCsv)}>
                  <Download size={13} /> Copy Emails
                </Btn>
                <Btn size="sm" onClick={() => useinCampaign(selected.size > 0 ? selectedCsv : emailCsv)}>
                  <Send size={13} /> Use in Campaign
                  {selected.size > 0 ? ` (${selected.size})` : ` (All ${contacts.length})`}
                </Btn>
              </>
            )}
          </Card>

          {/* Table */}
          <Card className="overflow-hidden p-0">
            {contactsQ.isLoading ? (
              <div className="flex justify-center py-12"><Spinner /></div>
            ) : contacts.length === 0 ? (
              <div className="flex flex-col items-center py-16 text-slate-500">
                <Users size={40} className="mb-3 opacity-20" />
                <p className="text-sm">No contacts yet.</p>
                <Btn size="sm" className="mt-4" onClick={() => setTab('import')}>
                  <Upload size={13} /> Import your first contacts
                </Btn>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700/60 bg-slate-800/40">
                    <th className="p-3 w-10">
                      <input type="checkbox" checked={selected.size === contacts.length} onChange={toggleAll}
                        className="accent-violet-500 cursor-pointer" />
                    </th>
                    <th className="p-3 text-left text-slate-400 font-medium">Name</th>
                    <th className="p-3 text-left text-slate-400 font-medium">Email</th>
                    <th className="p-3 text-left text-slate-400 font-medium">Group</th>
                    <th className="p-3 text-left text-slate-400 font-medium">Status</th>
                    <th className="p-3 text-right text-slate-400 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map((c, i) => (
                    <tr key={c.email}
                      className={`border-b border-slate-700/30 transition-colors ${selected.has(c.email) ? 'bg-violet-500/5' : i % 2 === 0 ? 'bg-transparent' : 'bg-slate-800/20'} hover:bg-slate-700/20`}>
                      <td className="p-3">
                        <input type="checkbox" checked={selected.has(c.email)} onChange={() => toggleOne(c.email)}
                          className="accent-violet-500 cursor-pointer" />
                      </td>
                      <td className="p-3 text-white font-medium">{c.name}</td>
                      <td className="p-3 text-slate-300">{c.email}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded-full text-xs bg-violet-500/10 text-violet-400 border border-violet-500/20">
                          {c.group || 'general'}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs border ${c.active !== false ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-slate-700/40 text-slate-500 border-slate-600/30'}`}>
                          {c.active !== false ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {c.active !== false && (
                            <button title="Deactivate" onClick={() => deactivateMut.mutate(c.email)}
                              className="p-1.5 rounded-lg text-slate-400 hover:text-yellow-400 hover:bg-yellow-400/10 transition-colors">
                              <UserX size={13} />
                            </button>
                          )}
                          <button title="Delete" onClick={() => { if (confirm(`Delete ${c.email}?`)) deleteMut.mutate(c.email) }}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-400/10 transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
      )}

      {/* ── TAB: Add Single Contact ──────────────────────────────────────────── */}
      {tab === 'add' && (
        <Card className="max-w-lg">
          <SectionTitle>Add Contact</SectionTitle>
          <div className="space-y-4">
            <Input id="c-name" label="Full Name *" placeholder="John Smith"
              value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            <Input id="c-email" label="Email Address *" placeholder="john@example.com" type="email"
              value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">Group</label>
              <select className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                value={form.group} onChange={e => setForm(f => ({ ...f, group: e.target.value }))}>
                {['general', 'leads', 'customers', 'vip', 'newsletter', 'internal', 'support'].map(g =>
                  <option key={g} value={g}>{g}</option>)}
                {groups.filter(g => !['general','leads','customers','vip','newsletter','internal','support'].includes(g)).map(g =>
                  <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <Input id="c-tags" label="Tags (comma-separated, optional)" placeholder="vip, newsletter"
              value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} />
            <div className="flex gap-3 pt-2">
              <Btn onClick={() => addMut.mutate()} disabled={addMut.isPending || !form.name || !form.email}>
                <Plus size={14} /> {addMut.isPending ? 'Adding…' : 'Add Contact'}
              </Btn>
              <Btn variant="secondary" onClick={() => setTab('list')}>Cancel</Btn>
            </div>
          </div>
        </Card>
      )}

      {/* ── TAB: Bulk Import ─────────────────────────────────────────────────── */}
      {tab === 'import' && (
        <Card className="max-w-2xl">
          <SectionTitle>Bulk Import Contacts</SectionTitle>
          <p className="text-slate-400 text-sm mb-4">
            Paste emails one per line, or comma / semicolon separated.<br />
            Supports formats: <code className="text-violet-400">email@domain.com</code> or <code className="text-violet-400">John Smith &lt;email@domain.com&gt;</code>
          </p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">Assign Group</label>
              <select className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                value={importGroup} onChange={e => setImportGroup(e.target.value)}>
                {['general', 'leads', 'customers', 'vip', 'newsletter', 'internal', 'support'].map(g =>
                  <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1.5">
                Email List * &nbsp;
                <span className="text-slate-500 font-normal">
                  ({parseBulkPreview(importText)} emails detected)
                </span>
              </label>
              <textarea
                rows={14}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-violet-500 resize-y"
                placeholder={`john@gmail.com\njane@yahoo.com, mike@outlook.com\nAlice Smith <alice@company.com>`}
                value={importText}
                onChange={e => setImportText(e.target.value)}
              />
            </div>
            <div className="flex gap-3">
              <Btn onClick={() => importMut.mutate()} disabled={importMut.isPending || !importText.trim()}>
                <Upload size={14} /> {importMut.isPending ? 'Importing…' : 'Import Contacts'}
              </Btn>
              <Btn variant="secondary" onClick={() => setTab('list')}>Cancel</Btn>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

// Tiny helper — count valid emails in the textarea without importing
function parseBulkPreview(text) {
  if (!text.trim()) return 0
  return text.split(/[\n,;]+/).map(l => l.trim()).filter(l => l.includes('@')).length
}
