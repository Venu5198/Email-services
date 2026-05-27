'use client'
import { useQuery } from '@tanstack/react-query'
import { getAnalyticsSummary, getSenderPoolAnalytics, getHealth } from '@/lib/api'
import { formatNumber, formatPct } from '@/lib/utils'
import { StatCard, Spinner, Card, SectionTitle } from '@/components/ui'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { Mail, TrendingUp, MousePointerClick, AlertTriangle, Users, CheckCircle, Wifi, WifiOff } from 'lucide-react'

const CHART_COLORS = ['#7c3aed', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

function HealthDot() {
  const { data } = useQuery({ queryKey: ['health'], queryFn: getHealth, refetchInterval: 15000 })
  const ok = data?.data?.status === 'healthy'
  return (
    <span className={`flex items-center gap-1.5 text-xs ${ok ? 'text-green-400' : 'text-red-400'}`}>
      {ok ? <Wifi size={12} /> : <WifiOff size={12} />}
      {ok ? 'API Connected' : 'API Offline'}
    </span>
  )
}

export default function DashboardPage() {
  const { data: summaryRes, isLoading } = useQuery({
    queryKey: ['analytics-summary', 7],
    queryFn: () => getAnalyticsSummary(7),
    refetchInterval: 30000,
  })
  const { data: poolRes } = useQuery({
    queryKey: ['sender-pool-stats'],
    queryFn: getSenderPoolAnalytics,
    refetchInterval: 60000,
  })

  const s = summaryRes?.data || {}
  const pool = poolRes?.data || {}

  const pieData = [
    { name: 'Opens', value: s.unique_opens || 0 },
    { name: 'Clicks', value: s.unique_clicks || 0 },
    { name: 'Bounces', value: s.bounces || 0 },
    { name: 'Unsubscribed', value: s.unsubscribes || 0 },
  ].filter(d => d.value > 0)

  const accounts = pool.accounts || []

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">Last 7 days · auto-refreshes every 30s</p>
        </div>
        <HealthDot />
      </div>

      {/* Stat Cards */}
      {isLoading ? <Spinner /> : (
        <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
          <StatCard icon={Mail} label="Emails Sent" value={formatNumber(s.emails_sent)} color="violet" />
          <StatCard icon={CheckCircle} label="Open Rate" value={formatPct(s.open_rate_pct)} color="green" />
          <StatCard icon={MousePointerClick} label="Click Rate" value={formatPct(s.click_rate_pct)} color="blue" />
          <StatCard icon={AlertTriangle} label="Bounces" value={formatNumber(s.bounces)} color="red" />
          <StatCard icon={Users} label="Unsubscribed" value={formatNumber(s.unsubscribes)} color="orange" />
          <StatCard icon={TrendingUp} label="Spam Complaints" value={formatNumber(s.spam_complaints)} color="red" />
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
        {/* Engagement donut */}
        <Card>
          <SectionTitle>Engagement Breakdown</SectionTitle>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                  dataKey="value" paddingAngle={3}>
                  {pieData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, color: '#f1f5f9' }} />
                <Legend wrapperStyle={{ color: '#94a3b8', fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-slate-500 text-sm">
              No engagement data yet
            </div>
          )}
        </Card>

        {/* Sender Pool Usage */}
        <Card className="xl:col-span-2">
          <SectionTitle>Sender Pool Quota</SectionTitle>
          <div className="space-y-3 max-h-[220px] overflow-y-auto pr-1">
            {accounts.length === 0 ? (
              <p className="text-slate-500 text-sm">No sender accounts registered.</p>
            ) : accounts.map(acc => (
              <div key={acc.email}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-300 truncate max-w-[220px]">{acc.email}</span>
                  <span className="text-slate-400 ml-2 shrink-0">{acc.sent_today}/{acc.daily_limit}</span>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${acc.usage_pct > 80 ? 'bg-red-500' : acc.usage_pct > 50 ? 'bg-yellow-500' : 'bg-violet-500'}`}
                    style={{ width: `${Math.min(acc.usage_pct, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          {pool.total_sent_today !== undefined && (
            <div className="mt-4 pt-4 border-t border-slate-800 flex gap-6 text-sm">
              <div><span className="text-slate-400">Sent Today </span><span className="text-white font-semibold">{formatNumber(pool.total_sent_today)}</span></div>
              <div><span className="text-slate-400">Remaining </span><span className="text-green-400 font-semibold">{formatNumber(pool.total_remaining_today)}</span></div>
              <div><span className="text-slate-400">Usage </span><span className="text-white font-semibold">{formatPct(pool.overall_usage_pct)}</span></div>
            </div>
          )}
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <SectionTitle>Quick Actions</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { href: '/compose', label: '✉️ Compose Email', desc: 'Send single email' },
            { href: '/campaigns', label: '📢 New Campaign', desc: 'Bulk email blast' },
            { href: '/scheduler', label: '⏰ Schedule Email', desc: 'Set a future send' },
            { href: '/sender-pool', label: '👤 Add Sender', desc: 'Expand capacity' },
          ].map(a => (
            <a key={a.href} href={a.href}
              className="bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl p-4 transition-all cursor-pointer block">
              <p className="text-white font-medium text-sm">{a.label}</p>
              <p className="text-slate-400 text-xs mt-1">{a.desc}</p>
            </a>
          ))}
        </div>
      </Card>
    </div>
  )
}
