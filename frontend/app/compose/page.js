'use client'
import { useState } from 'react'
import { sendEmail } from '@/lib/api'
import { Card, Btn, Input, Textarea, Select, SectionTitle } from '@/components/ui'
import { Send, Plus, Trash2, CheckCircle, AlertCircle } from 'lucide-react'

const TEMPLATES = [
  'demo_booking_confirm.html','demo_reschedule_confirm.html','demo_cancel_confirm.html',
  'newsletter.html','product_promotion.html','support_acknowledgment.html',
  'internal_incident_alert.html','video_announcement.html','welcome.html',
  'form_submission_ack.html','inquiry_auto_reply.html',
]

export default function ComposePage() {
  const [form, setForm] = useState({
    to: '', cc: '', bcc: '', subject: '', from_name: 'SyncRivo',
    body_text: '', body_html: '', template_name: '', is_confidential: false,
    reply_to: '',
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSend = async () => {
    setLoading(true)
    setResult(null)
    try {
      const payload = {
        to_emails: form.to.split(',').map(e => e.trim()).filter(Boolean),
        cc_emails: form.cc ? form.cc.split(',').map(e => e.trim()).filter(Boolean) : undefined,
        bcc_emails: form.bcc ? form.bcc.split(',').map(e => e.trim()).filter(Boolean) : undefined,
        subject: form.subject || undefined,
        from_name: form.from_name || undefined,
        body_text: form.body_text || undefined,
        body_html: form.body_html || undefined,
        template_name: form.template_name || undefined,
        is_confidential: form.is_confidential,
        reply_to: form.reply_to || undefined,
      }
      const res = await sendEmail(payload)
      setResult({ ok: true, msg: res.data?.message || 'Email sent successfully!', id: res.data?.message_id })
    } catch (e) {
      setResult({ ok: false, msg: e.response?.data?.detail || e.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Compose Email</h1>
        <p className="text-slate-500 text-sm mt-1">Send a single email immediately via the configured SMTP provider</p>
      </div>

      <Card>
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4">
            <Input id="to" label="To *" placeholder="email1@example.com, email2@example.com" value={form.to} onChange={e => set('to', e.target.value)} />
            <div className="grid grid-cols-2 gap-4">
              <Input id="cc" label="CC" placeholder="cc@example.com" value={form.cc} onChange={e => set('cc', e.target.value)} />
              <Input id="bcc" label="BCC" placeholder="bcc@example.com" value={form.bcc} onChange={e => set('bcc', e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input id="subject" label="Subject" placeholder="Your email subject line" value={form.subject} onChange={e => set('subject', e.target.value)} />
              <Input id="from_name" label="From Name" placeholder="SyncRivo" value={form.from_name} onChange={e => set('from_name', e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input id="reply_to" label="Reply-To" placeholder="support@syncrivo.ai" value={form.reply_to} onChange={e => set('reply_to', e.target.value)} />
              <Select id="template" label="Template (optional)" value={form.template_name} onChange={e => set('template_name', e.target.value)}>
                <option value="">— No template —</option>
                {TEMPLATES.map(t => <option key={t} value={t}>{t}</option>)}
              </Select>
            </div>
          </div>

          <div className="border-t border-slate-800 pt-5">
            <SectionTitle>Email Body</SectionTitle>
            <div className="space-y-4">
              <Textarea id="body_text" label="Plain Text Body" rows={4} placeholder="Plain text version of your email..." value={form.body_text} onChange={e => set('body_text', e.target.value)} />
              <Textarea id="body_html" label="HTML Body" rows={6} placeholder="<p>HTML version...</p>" value={form.body_html} onChange={e => set('body_html', e.target.value)} />
            </div>
          </div>

          <div className="flex items-center gap-3 pt-1">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={form.is_confidential} onChange={e => set('is_confidential', e.target.checked)}
                className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-violet-600 focus:ring-violet-500" />
              <span className="text-sm text-slate-400">Mark as Confidential</span>
            </label>
          </div>

          {result && (
            <div className={`flex items-start gap-3 p-4 rounded-lg border ${result.ok ? 'bg-green-500/10 border-green-500/30 text-green-400' : 'bg-red-500/10 border-red-500/30 text-red-400'}`}>
              {result.ok ? <CheckCircle size={16} className="mt-0.5 shrink-0" /> : <AlertCircle size={16} className="mt-0.5 shrink-0" />}
              <div className="text-sm">
                <p>{result.msg}</p>
                {result.id && <p className="text-xs opacity-70 mt-1">Message-ID: {result.id}</p>}
              </div>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Btn onClick={handleSend} disabled={loading || !form.to}>
              <Send size={14} />
              {loading ? 'Sending…' : 'Send Email'}
            </Btn>
            <Btn variant="secondary" onClick={() => { setForm(f => ({ ...f, to: '', cc: '', bcc: '', subject: '', body_text: '', body_html: '' })); setResult(null) }}>
              Clear
            </Btn>
          </div>
        </div>
      </Card>
    </div>
  )
}
