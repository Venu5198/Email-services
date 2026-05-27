'use client'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { previewTemplate, createTemplate, deleteTemplate, getTemplate } from '@/lib/api'
import { Card, Btn, Input, Textarea, SectionTitle, Spinner } from '@/components/ui'
import { FileText, Eye, Save, Trash2, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react'

const BUILTIN = [
  'demo_booking_confirm.html','demo_reschedule_confirm.html','demo_cancel_confirm.html',
  'demo_reminder_1h.html','demo_reminder_24h.html','newsletter.html',
  'product_promotion.html','support_acknowledgment.html','internal_incident_alert.html',
  'video_announcement.html','welcome.html','form_submission_ack.html',
  'inquiry_auto_reply.html','order_confirmation.html','marketing_article.html',
  'service_request_notify.html',
]

export default function TemplatesPage() {
  const [selected, setSelected] = useState('')
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewSubject, setPreviewSubject] = useState('')
  const [contextStr, setContextStr] = useState(JSON.stringify({
    username: "John Doe",
    customer_name: "John Doe",
    company_name: "SyncRivo",
    support_email: "support@syncrivo.ai",
    ticket_id: "TKT-001",
    issue_summary: "Login issue on dashboard",
    response_sla: "4 hours",
    submitter_email: "john@example.com",
    priority: "medium",
    inquiry_type: "general",
    expected_response_hours: 4,
    cta_url: "https://syncrivo.ai",
    featured_articles: [],
    promotions: []
  }, null, 2))
  const [subjectTmpl, setSubjectTmpl] = useState('')
  const [msg, setMsg] = useState(null)
  const [tab, setTab] = useState('builtin')
  const [newTemplate, setNewTemplate] = useState({ template_name: '', body_html: '', body_text: '', subject_template: '' })

  const previewMut = useMutation({
    mutationFn: async () => {
      let ctx = {}
      try { ctx = JSON.parse(contextStr) } catch { throw new Error('Invalid JSON context') }
      const res = await previewTemplate(selected, ctx, subjectTmpl || undefined)
      return res.data
    },
    onSuccess: (d) => {
      setPreviewHtml(d.rendered_html || '')
      setPreviewSubject(d.rendered_subject || '')
      setMsg(null)
    },
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  const saveMut = useMutation({
    mutationFn: () => createTemplate(newTemplate),
    onSuccess: () => setMsg({ ok: true, text: `Template '${newTemplate.template_name}' saved!` }),
    onError: e => setMsg({ ok: false, text: e.response?.data?.detail || e.message }),
  })

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Templates</h1>
        <p className="text-slate-500 text-sm mt-1">Preview and manage Jinja2 email templates</p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-2 mb-6">
        {['builtin', 'create'].map(t => (
          <Btn key={t} size="sm" variant={tab === t ? 'primary' : 'secondary'} onClick={() => setTab(t)}>
            {t === 'builtin' ? '📄 Preview Templates' : '✏️ Create Template'}
          </Btn>
        ))}
      </div>

      {msg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-5 text-sm ${msg.ok ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
          {msg.ok ? <CheckCircle size={14} /> : <AlertCircle size={14} />} {msg.text}
        </div>
      )}

      {tab === 'builtin' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Left: config */}
          <Card>
            <SectionTitle>Template Preview</SectionTitle>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1.5">Select Template</label>
                <select className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                  value={selected} onChange={e => { setSelected(e.target.value); setPreviewHtml('') }}>
                  <option value="">— Pick a template —</option>
                  {BUILTIN.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <Textarea id="ctx" label="Context (JSON)" rows={6} value={contextStr} onChange={e => setContextStr(e.target.value)}
                placeholder='{"username": "John", "company_name": "SyncRivo"}' />
              <Input id="subj-tmpl" label="Subject Template (optional)" placeholder="Hello {{ username }}!" value={subjectTmpl} onChange={e => setSubjectTmpl(e.target.value)} />
              <Btn onClick={() => previewMut.mutate()} disabled={previewMut.isPending || !selected} className="w-full justify-center">
                <Eye size={14} />
                {previewMut.isPending ? 'Rendering…' : 'Preview Template'}
              </Btn>
            </div>
          </Card>

          {/* Right: rendered preview */}
          <Card className="flex flex-col">
            <SectionTitle>Rendered Output</SectionTitle>
            {previewSubject && (
              <div className="mb-3 p-2 bg-slate-800 rounded-lg">
                <p className="text-xs text-slate-400">Subject:</p>
                <p className="text-sm text-white font-medium">{previewSubject}</p>
              </div>
            )}
            {previewMut.isPending ? <Spinner /> : previewHtml ? (
              <div className="flex-1 bg-white rounded-lg overflow-hidden" style={{ minHeight: 400 }}>
                <iframe srcDoc={previewHtml} className="w-full h-full border-0" style={{ minHeight: 400 }} title="Email Preview" />
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-500 text-sm min-h-[400px]">
                <div className="text-center">
                  <FileText size={36} className="mx-auto mb-3 opacity-20" />
                  <p>Select a template and click Preview</p>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === 'create' && (
        <Card className="max-w-3xl">
          <SectionTitle>Create / Update Template</SectionTitle>
          <div className="space-y-4">
            <Input id="tname" label="Template Name *" placeholder="my_custom_template.html" value={newTemplate.template_name} onChange={e => setNewTemplate(t => ({ ...t, template_name: e.target.value }))} />
            <Input id="tsubj" label="Subject Template" placeholder="Hello {{ username }}!" value={newTemplate.subject_template} onChange={e => setNewTemplate(t => ({ ...t, subject_template: e.target.value }))} />
            <Textarea id="thtml" label="HTML Body (Jinja2)" rows={12}
              placeholder={'<html>\n<body>\n<h1>Hello {{ username }}!</h1>\n<p>Welcome to {{ company_name }}.</p>\n</body>\n</html>'}
              value={newTemplate.body_html} onChange={e => setNewTemplate(t => ({ ...t, body_html: e.target.value }))} />
            <Textarea id="ttext" label="Plain Text Body (optional)" rows={4} placeholder="Hello {{ username }}! Welcome to {{ company_name }}."
              value={newTemplate.body_text} onChange={e => setNewTemplate(t => ({ ...t, body_text: e.target.value }))} />
            <Btn onClick={() => saveMut.mutate()} disabled={saveMut.isPending || !newTemplate.template_name || !newTemplate.body_html}>
              <Save size={14} /> {saveMut.isPending ? 'Saving…' : 'Save Template'}
            </Btn>
          </div>
        </Card>
      )}
    </div>
  )
}
