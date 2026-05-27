'use client'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAnalyticsSummary, getTopClickedUrls, getSenderPoolAnalytics } from '@/lib/api'
import { Card, SectionTitle, Spinner, Select } from '@/components/ui'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { formatNumber, formatPct } from '@/lib/utils'

const TIP_STYLE = { background: '#1e293b', border: '1px solid #334155', borderRadius: 8, color: '#f1f5f9', fontSize: 12 }
const COLORS = ['#7c3aed','#06b6d4','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1']

export default function AnalyticsPage() {
  const [days, setDays] = useState(7)
  const { data: sumRes, isLoading } = useQuery({ queryKey: ['analytics-summary', days], queryFn: () => getAnalyticsSummary(days), refetchInterval: 60000 })
  const { data: urlRes } = useQuery({ queryKey: ['top-urls', days], queryFn: () => getTopClickedUrls(10, days) })
  const { data: poolRes } = useQuery({ queryKey: ['sender-pool-stats'], queryFn: getSenderPoolAnalytics, refetchInterval: 60000 })

  const s = sumRes?.data || {}
  const urls = urlRes?.data?.top_urls || []
  const pool = poolRes?.data || {}
  const accounts = pool.accounts || []

  const engagementData = [
    { name: 'Sent', value: s.emails_sent || 0 },
    { name: 'Opens', value: s.unique_opens || 0 },
    { name: 'Clicks', value: s.unique_clicks || 0 },
    { name: 'Bounces', value: s.bounces || 0 },
    { name: 'Unsubs', value: s.unsubscribes || 0 },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Analytics</h1>
          <p className="text-slate-500 text-sm mt-1">Deep performance metrics for your email campaigns</p>
        </div>
        <Select id="days" value={days} onChange={e => setDays(Number(e.target.value))}>
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </Select>
      </div>

      {isLoading ? <Spinner /> : (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { label: 'Emails Sent', value: formatNumber(s.emails_sent), sub: `${formatNumber(s.emails_failed)} failed` },
              { label: 'Open Rate', value: formatPct(s.open_rate_pct), sub: `${formatNumber(s.unique_opens)} unique opens` },
              { label: 'Click Rate', value: formatPct(s.click_rate_pct), sub: `${formatNumber(s.unique_clicks)} unique clicks` },
              { label: 'Bounces', value: formatNumber(s.bounces), sub: `${formatNumber(s.spam_complaints)} spam complaints` },
            ].map(k => (
              <Card key={k.label} className="!p-4">
                <p className="text-slate-400 text-xs mb-1">{k.label}</p>
                <p className="text-white text-2xl font-bold">{k.value}</p>
                <p className="text-slate-500 text-xs mt-1">{k.sub}</p>
              </Card>
            ))}
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-6">
            {/* Engagement funnel */}
            <Card>
              <SectionTitle>Engagement Funnel</SectionTitle>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={engagementData} barSize={36}>
                  <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TIP_STYLE} />
                  <Bar dataKey="value" fill="#7c3aed" radius={[4, 4, 0, 0]}>
                    {engagementData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>

            {/* Top URLs */}
            <Card>
              <SectionTitle>Top Clicked URLs</SectionTitle>
              {urls.length === 0 ? (
                <p className="text-slate-500 text-sm py-8 text-center">No click data yet — tracking is injected automatically in HTML emails.</p>
              ) : (
                <div className="space-y-3">
                  {urls.slice(0, 8).map((u, i) => (
                    <div key={i}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-300 truncate max-w-[280px]" title={u.url}>{u.url}</span>
                        <span className="text-violet-400 font-semibold ml-2 shrink-0">{u.clicks} clicks</span>
                      </div>
                      <div className="h-1.5 bg-slate-800 rounded-full">
                        <div className="h-full rounded-full bg-violet-500"
                          style={{ width: `${Math.min((u.clicks / (urls[0]?.clicks || 1)) * 100, 100)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* Sender pool bar */}
          <Card>
            <SectionTitle>Sender Pool Usage Today</SectionTitle>
            {accounts.length === 0 ? (
              <p className="text-slate-500 text-sm">No sender accounts registered.</p>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(accounts.length * 36, 120)}>
                <BarChart data={accounts.map(a => ({ name: a.email.split('@')[0], sent: a.sent_today, remaining: Math.max(0, a.daily_limit - a.sent_today) }))} layout="vertical" barSize={14}>
                  <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fill: '#cbd5e1', fontSize: 11 }} axisLine={false} tickLine={false} width={100} />
                  <Tooltip contentStyle={TIP_STYLE} />
                  <Bar dataKey="sent" fill="#7c3aed" name="Sent" radius={[0, 2, 2, 0]} stackId="a" />
                  <Bar dataKey="remaining" fill="#1e293b" name="Remaining" radius={[0, 2, 2, 0]} stackId="a" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
